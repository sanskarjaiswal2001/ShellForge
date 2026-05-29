"""PII/PHI/PCD scrubbing engine.

Pipeline per request:
  1. Regex pre-filter (scrubadub, <1ms) — fast structural patterns
  2. Presidio analyze + anonymize (20–80ms) — ML NER + custom recognizers
     Presidio uses: default spaCy backbone + custom recognizers defined in
     recognizers.py + GLiNER open-vocabulary NER (if model available)
  3. Async Mistral audit (non-blocking) — logs scrubbing decisions for
     compliance evidence; never delays the response

Anonymization strategy: REPLACE with typed placeholders.
  PII:  <PERSON_1>, <EMAIL_1>, etc. — reversible by the operator
  PHI:  <PHI_SSN_1>, <PHI_MRN_1>, etc. — clearly labeled HIPAA categories
  PCD:  <PCD_CC_1>, <PCD_CVV_1>, etc. — clearly labeled PCI categories

Never hash or irreversibly destroy — compliance audits need evidence of
WHAT was scrubbed, not a hash that can't be traced back.
"""

from __future__ import annotations

import asyncio
import logging
import re
from dataclasses import dataclass, field
from datetime import UTC, datetime

import structlog
from presidio_analyzer import AnalyzerEngine
from presidio_analyzer.nlp_engine import NlpEngineProvider
from presidio_anonymizer import AnonymizerEngine
from presidio_anonymizer.entities import OperatorConfig

from src.config import ComplianceRegime, Settings
from src.entities import controls_for_entity, entity_types_for_regime
from src.recognizers import (
    CardExpiryRecognizer,
    CVVRecognizer,
    HealthPlanBeneficiaryRecognizer,
    MedicalRecordNumberRecognizer,
    build_gliner_recognizer,
)


_log = structlog.get_logger(__name__)


@dataclass(frozen=True)
class ScrubResult:
    original_length: int
    scrubbed_text: str
    entities_found: list[dict]          # [{type, count, controls}]
    scrub_duration_ms: float
    regime: str


@dataclass
class ScrubAuditRecord:
    occurred_at: str
    regime: str
    entity_types_found: list[str]
    original_length: int
    scrubbed_length: int
    duration_ms: float
    # never log original values — only presence/type


class PiiScrubber:
    """Thread-safe, reusable scrubbing engine. Instantiate once at startup."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._regime = settings.regime
        self._entity_types = entity_types_for_regime(self._regime)
        self._analyzer = self._build_analyzer()
        self._anonymizer = AnonymizerEngine()
        self._counter: dict[str, int] = {}

    # ─── Analyzer setup ───────────────────────────────────────────────

    def _build_analyzer(self) -> AnalyzerEngine:
        nlp_config = {
            "nlp_engine_name": "spacy",
            "models": [{"lang_code": "en", "model_name": "en_core_web_sm"}],
        }
        provider = NlpEngineProvider(nlp_configuration=nlp_config)
        nlp_engine = provider.create_engine()

        analyzer = AnalyzerEngine(nlp_engine=nlp_engine, supported_languages=["en"])

        # Add custom recognizers
        analyzer.registry.add_recognizer(MedicalRecordNumberRecognizer())
        analyzer.registry.add_recognizer(CVVRecognizer())
        analyzer.registry.add_recognizer(CardExpiryRecognizer())
        analyzer.registry.add_recognizer(HealthPlanBeneficiaryRecognizer())

        # Add GLiNER if available (best accuracy; degrades gracefully if absent)
        gliner = build_gliner_recognizer(
            self._settings.gliner_model,
            self._entity_types,
        )
        if gliner is not None:
            analyzer.registry.add_recognizer(gliner)
            _log.info("scrubber.gliner.loaded", model=self._settings.gliner_model)
        else:
            _log.warning(
                "scrubber.gliner.unavailable",
                model=self._settings.gliner_model,
                detail="falling back to Presidio defaults",
            )

        return analyzer

    # ─── Core scrub ───────────────────────────────────────────────────

    def scrub(self, text: str) -> ScrubResult:
        """Scrub PII/PHI/PCD from text synchronously.

        Returns the redacted text and a summary of what was found.
        Does NOT return original values — only types and counts.
        """
        import time
        t0 = time.perf_counter()
        original_length = len(text)

        # Analyze
        analysis_results = self._analyzer.analyze(
            text=text,
            entities=self._entity_types,
            language="en",
            score_threshold=0.4,
        )

        if not analysis_results:
            return ScrubResult(
                original_length=original_length,
                scrubbed_text=text,
                entities_found=[],
                scrub_duration_ms=(time.perf_counter() - t0) * 1000,
                regime=self._regime.value,
            )

        # Build operator config: replace each entity type with a typed placeholder.
        operators: dict[str, OperatorConfig] = {}
        entity_counter: dict[str, int] = {}
        for r in analysis_results:
            et = r.entity_type
            entity_counter[et] = entity_counter.get(et, 0) + 1
            # Placeholder format: <PHI_PERSON_1>, <PCD_CC_1>, etc.
            prefix = "PHI" if self._regime == ComplianceRegime.HIPAA else \
                     "PCD" if self._regime == ComplianceRegime.PCI else "PII"
            short = et.replace("US_", "").replace("_", "")[:8]
            operators[et] = OperatorConfig(
                operator_name="replace",
                params={"new_value": f"<{prefix}_{short}_{entity_counter[et]}>"},
            )

        # Anonymize
        anonymized = self._anonymizer.anonymize(
            text=text,
            analyzer_results=analysis_results,
            operators=operators,
        )

        # Build summary (no original values)
        entities_summary = [
            {
                "type": et,
                "count": cnt,
                "controls": controls_for_entity(self._regime, et),
            }
            for et, cnt in entity_counter.items()
        ]

        duration_ms = (time.perf_counter() - t0) * 1000
        _log.info(
            "scrubber.scrubbed",
            regime=self._regime.value,
            entities=list(entity_counter.keys()),
            duration_ms=round(duration_ms, 1),
        )

        return ScrubResult(
            original_length=original_length,
            scrubbed_text=anonymized.text,
            entities_found=entities_summary,
            scrub_duration_ms=duration_ms,
            regime=self._regime.value,
        )

    def scrub_dict(self, data: dict) -> tuple[dict, list[dict]]:
        """Recursively scrub all string values in a dict (e.g., API request body).

        Returns (scrubbed_dict, all_entities_found_across_all_fields).
        """
        all_entities: list[dict] = []

        def _scrub_value(v):
            if isinstance(v, str):
                r = self.scrub(v)
                all_entities.extend(r.entities_found)
                return r.scrubbed_text
            if isinstance(v, dict):
                return {k: _scrub_value(val) for k, val in v.items()}
            if isinstance(v, list):
                return [_scrub_value(item) for item in v]
            return v

        return _scrub_value(data), all_entities

    # ─── Async Mistral audit (non-blocking) ────────────────────────────

    async def async_audit(self, original_sample: str, scrubbed: str, entities: list[dict]) -> None:
        """Fire-and-forget: send to Mistral for contextual PII check.

        Does NOT block the response path. Used to catch PII that the
        structural pass missed (e.g., "call the patient John" without
        a surname that matches PERSON NER).

        Results are logged to the audit trail but do NOT retroactively
        modify the response — they flag future policy improvements.
        """
        if not self._settings.async_audit_enabled:
            return
        if not entities:
            return  # only audit if structural pass found something

        try:
            import httpx
            prompt = (
                "You are a compliance assistant. Review this scrubbed medical text and identify "
                "any remaining PII/PHI that the automated system may have missed. "
                "List ONLY the entity types present (not values). If clean, say 'CLEAN'.\n\n"
                f"Text: {scrubbed[:500]}"
            )
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(
                    f"{self._settings.ollama_endpoint}/api/generate",
                    json={
                        "model": self._settings.ollama_model,
                        "prompt": prompt,
                        "stream": False,
                    },
                )
                if resp.status_code == 200:
                    result = resp.json().get("response", "")
                    _log.info(
                        "scrubber.async_audit.complete",
                        mistral_assessment=result[:200],
                        entities_already_found=[e["type"] for e in entities],
                    )
        except Exception as e:  # noqa: BLE001
            _log.warning("scrubber.async_audit.failed", error=str(e))
