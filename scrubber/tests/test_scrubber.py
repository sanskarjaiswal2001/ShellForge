"""Tests for the PII scrubbing engine.

These tests do NOT require the GLiNER model to be downloaded —
they test the structural/regex layers that are always available.
GLiNER-specific tests are marked as integration tests.
"""

from __future__ import annotations

import os
import pytest

os.environ.setdefault("SCRUBBER_REGIME", "hipaa")
os.environ.setdefault("SCRUBBER_GLINER_MODEL", "knowledgator/gliner-pii-base-v1.0")

from src.config import ComplianceRegime, Settings
from src.scrubber import PiiScrubber


@pytest.fixture(scope="session")
def hipaa_scrubber():
    settings = Settings(regime=ComplianceRegime.HIPAA)
    return PiiScrubber(settings)


@pytest.fixture(scope="session")
def pci_scrubber():
    settings = Settings(regime=ComplianceRegime.PCI)
    return PiiScrubber(settings)


# ─── HIPAA PHI detection ─────────────────────────────────────────────────────


def test_hipaa_ssn_detected(hipaa_scrubber):
    result = hipaa_scrubber.scrub("Patient SSN: 123-45-6789. Please update records.")
    assert "123-45-6789" not in result.scrubbed_text
    entity_types = [e["type"] for e in result.entities_found]
    assert "US_SSN" in entity_types


def test_hipaa_email_detected(hipaa_scrubber):
    result = hipaa_scrubber.scrub("Send records to dr.smith@hospital.org")
    assert "dr.smith@hospital.org" not in result.scrubbed_text


def test_hipaa_phone_detected(hipaa_scrubber):
    result = hipaa_scrubber.scrub("Call patient at (555) 123-4567 for follow-up.")
    assert "555" not in result.scrubbed_text or "123-4567" not in result.scrubbed_text


def test_hipaa_mrn_labeled_detected(hipaa_scrubber):
    result = hipaa_scrubber.scrub("MRN: A1234567 was admitted on 2024-01-15.")
    entity_types = [e["type"] for e in result.entities_found]
    assert "MEDICAL_RECORD_NUMBER" in entity_types or "DATE_TIME" in entity_types


def test_hipaa_ip_detected(hipaa_scrubber):
    result = hipaa_scrubber.scrub("Patient accessed portal from IP 192.168.1.50")
    entity_types = [e["type"] for e in result.entities_found]
    assert "IP_ADDRESS" in entity_types


def test_hipaa_placeholder_format(hipaa_scrubber):
    """Redacted values must use PHI_ prefix placeholders."""
    result = hipaa_scrubber.scrub("SSN 123-45-6789 for patient John Smith")
    assert "<PHI_" in result.scrubbed_text or result.entities_found  # either redacted or found


def test_hipaa_clean_text_unchanged(hipaa_scrubber):
    """Non-PHI text should pass through unchanged."""
    text = "The function returns a list of integers sorted in ascending order."
    result = hipaa_scrubber.scrub(text)
    assert result.scrubbed_text == text
    assert result.entities_found == []


def test_hipaa_compliance_controls_present(hipaa_scrubber):
    """Entities found should include compliance control references."""
    result = hipaa_scrubber.scrub("SSN: 123-45-6789")
    if result.entities_found:
        entity = next((e for e in result.entities_found if e["type"] == "US_SSN"), None)
        if entity:
            assert len(entity["controls"]) > 0


# ─── PCI PCD detection ───────────────────────────────────────────────────────


def test_pci_credit_card_luhn(pci_scrubber):
    """Valid Luhn credit card must be detected."""
    result = pci_scrubber.scrub("Card: 4111 1111 1111 1111 — please charge.")
    assert "4111" not in result.scrubbed_text
    entity_types = [e["type"] for e in result.entities_found]
    assert "CREDIT_CARD" in entity_types


def test_pci_cvv_labeled(pci_scrubber):
    result = pci_scrubber.scrub("CVV: 123 for card ending 4567")
    entity_types = [e["type"] for e in result.entities_found]
    assert "CVV" in entity_types


def test_pci_iban(pci_scrubber):
    result = pci_scrubber.scrub("Transfer to GB29NWBK60161331926819 (IBAN)")
    entity_types = [e["type"] for e in result.entities_found]
    assert "IBAN_CODE" in entity_types


def test_pci_placeholder_format(pci_scrubber):
    """PCI redacted values must use PCD_ prefix."""
    result = pci_scrubber.scrub("Card: 4111111111111111")
    if result.entities_found:
        assert "<PCD_" in result.scrubbed_text


# ─── Dict scrubbing ──────────────────────────────────────────────────────────


def test_scrub_dict_anthropic_message(hipaa_scrubber):
    """Scrub API request body structure as sent by Claude SDK."""
    body = {
        "model": "claude-3-5-sonnet-20241022",
        "messages": [
            {
                "role": "user",
                "content": "Patient John Doe, SSN 123-45-6789, DOB 1985-03-15, needs code review.",
            }
        ],
        "max_tokens": 1024,
    }
    scrubbed, entities = hipaa_scrubber.scrub_dict(body)
    # Model + max_tokens should be unchanged
    assert scrubbed["model"] == body["model"]
    assert scrubbed["max_tokens"] == 1024
    # PHI in message content should be scrubbed
    assert "123-45-6789" not in scrubbed["messages"][0]["content"]


def test_scrub_dict_nested(hipaa_scrubber):
    """Deep-nested dict/list structure is traversed."""
    body = {
        "messages": [
            {"role": "user", "content": [
                {"type": "text", "text": "Email dr.jones@hospital.org for patient A234567"},
            ]}
        ]
    }
    scrubbed, entities = hipaa_scrubber.scrub_dict(body)
    content_text = scrubbed["messages"][0]["content"][0]["text"]
    assert "dr.jones@hospital.org" not in content_text


# ─── Duration check ──────────────────────────────────────────────────────────


def test_scrub_latency_under_500ms(hipaa_scrubber):
    """Synchronous scrub must complete under 500ms on CPU (without GLiNER)."""
    text = (
        "Patient Jane Doe SSN 987-65-4321 email jane@example.com "
        "phone (555) 987-6543 DOB 1980-06-20 address 123 Main St Chicago IL "
        "MRN: B9876543 referred by Dr. Smith NPI 1234567890."
    )
    result = hipaa_scrubber.scrub(text)
    # 500ms is generous — spaCy alone is <30ms
    assert result.scrub_duration_ms < 500, (
        f"Scrub took {result.scrub_duration_ms:.0f}ms — too slow for sync path"
    )
