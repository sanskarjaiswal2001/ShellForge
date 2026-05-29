"""Custom Presidio recognizers for entities not in the default set.

Adds:
  - MedicalRecordNumberRecognizer (MRN) — HIPAA §164.514(b)(2)(i)
  - CVVRecognizer — PCI Req 3.2.1
  - CardExpiryRecognizer — PCI Req 3.2
  - GlinerRecognizer — open-vocabulary NER via GLiNER model
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from presidio_analyzer import Pattern, PatternRecognizer

if TYPE_CHECKING:
    from presidio_analyzer import RecognizerResult


class MedicalRecordNumberRecognizer(PatternRecognizer):
    """Detects common Medical Record Number (MRN) formats.

    MRNs are typically numeric (6–12 digits), sometimes prefixed with
    letters. Very context-dependent — we match on label + value proximity.
    """

    PATTERNS = [
        Pattern(
            name="mrn_labeled",
            regex=r"\b(?:MRN|Medical\s+Record(?:\s+Number)?|Patient\s+ID|Pt(?:\.|\s+)ID)\s*[:#\-]?\s*([A-Z]{0,3}\d{5,12})\b",
            score=0.85,
        ),
        Pattern(
            name="mrn_bare_format",
            # 8–10 digit standalone number — lower confidence without label
            regex=r"\b([A-Z]{1,3}\d{6,10}|[0-9]{8,10})\b",
            score=0.35,
        ),
    ]

    def __init__(self) -> None:
        super().__init__(
            supported_entity="MEDICAL_RECORD_NUMBER",
            patterns=self.PATTERNS,
            context=["mrn", "medical record", "patient id", "chart", "record number", "emr", "ehr"],
        )


class CVVRecognizer(PatternRecognizer):
    """Detects card CVV/CVC/CVN values.

    3–4 digit codes near card-security keywords. Low standalone score
    because 3-digit numbers are common — context words boost confidence.
    """

    PATTERNS = [
        Pattern(
            name="cvv_labeled",
            regex=r"\b(?:CVV|CVV2|CVC|CVC2|CVN|security\s+code)\s*[:#=\-]?\s*(\d{3,4})\b",
            score=0.9,
        ),
        Pattern(
            name="cvv_bare",
            regex=r"\b(\d{3,4})\b",
            score=0.1,  # must be boosted by context
        ),
    ]

    def __init__(self) -> None:
        super().__init__(
            supported_entity="CVV",
            patterns=self.PATTERNS,
            context=["cvv", "cvc", "security code", "card verification", "cvv2", "cvc2"],
        )


class CardExpiryRecognizer(PatternRecognizer):
    """Detects card expiry dates (MM/YY, MM-YY, MM/YYYY)."""

    PATTERNS = [
        Pattern(
            name="expiry_slash",
            regex=r"\b(0[1-9]|1[0-2])\s*/\s*(\d{2}|\d{4})\b",
            score=0.5,
        ),
        Pattern(
            name="expiry_labeled",
            regex=r"\b(?:expiry|expiration|exp\.?|valid\s+thru|valid\s+through)\s*[:#]?\s*(0[1-9]|1[0-2])\s*[/\-]\s*(\d{2}|\d{4})\b",
            score=0.95,
        ),
    ]

    def __init__(self) -> None:
        super().__init__(
            supported_entity="CARD_EXPIRY",
            patterns=self.PATTERNS,
            context=["expiry", "expiration", "exp", "valid thru", "valid through", "card"],
        )


class HealthPlanBeneficiaryRecognizer(PatternRecognizer):
    """Detects health plan member / beneficiary IDs."""

    PATTERNS = [
        Pattern(
            name="health_plan_id",
            regex=r"\b(?:member\s+id|beneficiary\s+id|subscriber\s+id|insurance\s+id)\s*[:#]?\s*([A-Z0-9]{6,20})\b",
            score=0.85,
        ),
    ]

    def __init__(self) -> None:
        super().__init__(
            supported_entity="HEALTH_PLAN_BENEFICIARY_NUMBER",
            patterns=self.PATTERNS,
            context=["member id", "beneficiary", "subscriber", "insurance", "plan", "coverage"],
        )


def build_gliner_recognizer(model_name: str, entity_types: list[str]):
    """Build a Presidio EntityRecognizer backed by GLiNER.

    GLiNER is an open-vocabulary NER model — entity labels are passed
    at inference time, no retraining needed. This recognizer runs GLiNER
    on a text chunk and returns Presidio-formatted RecognizerResult items.

    Returns None if GLiNER or the model is not available (falls back to
    the Presidio defaults only, which is still safe — just lower recall).
    """
    try:
        from gliner import GLiNER
        from presidio_analyzer import EntityRecognizer, RecognizerResult

        class GLiNERRecognizer(EntityRecognizer):
            SUPPORTED_ENTITIES = entity_types

            def __init__(self):
                self._model = GLiNER.from_pretrained(model_name)
                super().__init__(supported_entities=self.SUPPORTED_ENTITIES, name="GLiNERRecognizer")

            def load(self) -> None:
                pass  # loaded in __init__

            def analyze(self, text: str, entities: list[str], nlp_artifacts=None) -> list[RecognizerResult]:
                results: list[RecognizerResult] = []
                # GLiNER works best on chunks ≤ 512 tokens.
                chunk_size = 400
                words = text.split()
                chunks: list[tuple[int, str]] = []
                for i in range(0, len(words), chunk_size):
                    chunk = " ".join(words[i : i + chunk_size])
                    start_char = len(" ".join(words[:i])) + (1 if i else 0)
                    chunks.append((start_char, chunk))

                for offset, chunk in chunks:
                    # Use entity types that overlap with what caller wants.
                    labels = [e for e in entities if e in self.SUPPORTED_ENTITIES]
                    if not labels:
                        continue
                    predictions = self._model.predict_entities(chunk, labels, threshold=0.5)
                    for pred in predictions:
                        results.append(
                            RecognizerResult(
                                entity_type=pred["label"].upper(),
                                start=offset + pred["start"],
                                end=offset + pred["end"],
                                score=pred["score"],
                            )
                        )
                return results

        return GLiNERRecognizer()
    except ImportError:
        return None
    except Exception:  # noqa: BLE001 — model download fails offline
        return None
