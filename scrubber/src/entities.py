"""Entity definitions per compliance regime.

Maps ComplianceRegime to the full set of entity types to detect/redact,
with compliance control annotations.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from src.config import ComplianceRegime


@dataclass(frozen=True)
class EntityDef:
    name: str
    description: str
    compliance_controls: list[str] = field(default_factory=list)


# ─── HIPAA Safe Harbor 18 PHI identifiers ────────────────────────────────────

HIPAA_ENTITIES: list[EntityDef] = [
    EntityDef("PERSON", "Patient/individual names", ["§164.514(b)(2)(i)", "CC6.1"]),
    EntityDef("DATE_TIME", "Dates (DOB, admission, discharge, death)", ["§164.514(b)(2)(i)"]),
    EntityDef("PHONE_NUMBER", "Telephone numbers", ["§164.514(b)(2)(i)"]),
    EntityDef("FAX_NUMBER", "Fax numbers", ["§164.514(b)(2)(i)"]),
    EntityDef("EMAIL_ADDRESS", "Email addresses", ["§164.514(b)(2)(i)"]),
    EntityDef("US_SSN", "Social Security Numbers", ["§164.514(b)(2)(i)", "§164.312(a)(1)"]),
    EntityDef("MEDICAL_RECORD_NUMBER", "Medical record / patient IDs (custom regex)", ["§164.514(b)(2)(i)"]),
    EntityDef("HEALTH_PLAN_BENEFICIARY_NUMBER", "Health plan beneficiary numbers", ["§164.514(b)(2)(i)"]),
    EntityDef("ACCOUNT_NUMBER", "Account numbers", ["§164.514(b)(2)(i)"]),
    EntityDef("CERTIFICATE_LICENSE_NUMBER", "Certificate/license numbers", ["§164.514(b)(2)(i)"]),
    EntityDef("VEHICLE_IDENTIFIER", "Vehicle identifiers and serial numbers", ["§164.514(b)(2)(i)"]),
    EntityDef("DEVICE_IDENTIFIER", "Device identifiers and serial numbers", ["§164.514(b)(2)(i)"]),
    EntityDef("URL", "URLs", ["§164.514(b)(2)(i)"]),
    EntityDef("IP_ADDRESS", "IP addresses", ["§164.514(b)(2)(i)"]),
    EntityDef("BIOMETRIC_IDENTIFIER", "Biometric identifiers", ["§164.514(b)(2)(i)"]),
    EntityDef("FULL_FACE_PHOTO", "Full-face photographs (described)", ["§164.514(b)(2)(i)"]),
    EntityDef("LOCATION", "Geographic locations smaller than state", ["§164.514(b)(2)(i)"]),
    EntityDef("US_HEALTHCARE_NPI", "National Provider Identifier", ["§164.514(b)(2)(i)"]),
    EntityDef("MEDICAL_LICENSE", "Medical license numbers", ["§164.514(b)(2)(i)"]),
]

# ─── PCI-DSS Cardholder Data / Sensitive Authentication Data ─────────────────

PCI_ENTITIES: list[EntityDef] = [
    EntityDef("CREDIT_CARD", "Credit/debit card PAN (with Luhn)", ["Req 3.2", "Req 4.2.1"]),
    EntityDef("CVV", "Card Verification Value (custom regex)", ["Req 3.2.1"]),
    EntityDef("CARD_EXPIRY", "Card expiry dates MM/YY (custom regex)", ["Req 3.2"]),
    EntityDef("IBAN_CODE", "IBAN bank account numbers", ["Req 3.4", "Req 4.2"]),
    EntityDef("US_BANK_NUMBER", "US bank account numbers", ["Req 3.4"]),
    EntityDef("US_SSN", "SSN (identity fraud vector)", ["Req 7.2", "Req 10.2"]),
    EntityDef("PERSON", "Cardholder names", ["Req 3.2"]),
    EntityDef("EMAIL_ADDRESS", "Email addresses", ["Req 7.2"]),
    EntityDef("PHONE_NUMBER", "Phone numbers", ["Req 7.2"]),
    EntityDef("IP_ADDRESS", "IP addresses", ["Req 10.3"]),
    EntityDef("US_DRIVER_LICENSE", "Driver license numbers", ["Req 7.2"]),
    EntityDef("US_PASSPORT", "Passport numbers", ["Req 7.2"]),
    EntityDef("LOCATION", "Billing addresses", ["Req 3.2"]),
    EntityDef("URL", "URLs (potential data exfiltration)", ["Req 1.3"]),
]

# ─── SOC 2 / Baseline (less aggressive) ─────────────────────────────────────

SOC2_ENTITIES: list[EntityDef] = [
    EntityDef("CREDIT_CARD", "Credit card numbers", ["CC6.7"]),
    EntityDef("US_SSN", "SSNs", ["CC6.1"]),
    EntityDef("EMAIL_ADDRESS", "Email addresses", ["CC6.6"]),
    EntityDef("IP_ADDRESS", "IP addresses", ["CC7.2"]),
    EntityDef("US_BANK_NUMBER", "Bank account numbers", ["CC6.7"]),
]

BASELINE_ENTITIES: list[EntityDef] = [
    EntityDef("CREDIT_CARD", "Credit card numbers", []),
    EntityDef("US_SSN", "SSNs", []),
]

ENTITIES_BY_REGIME: dict[ComplianceRegime, list[EntityDef]] = {
    ComplianceRegime.HIPAA: HIPAA_ENTITIES,
    ComplianceRegime.PCI: PCI_ENTITIES,
    ComplianceRegime.SOC2: SOC2_ENTITIES,
    ComplianceRegime.BASELINE: BASELINE_ENTITIES,
}


def entity_types_for_regime(regime: ComplianceRegime) -> list[str]:
    return [e.name for e in ENTITIES_BY_REGIME[regime]]


def controls_for_entity(regime: ComplianceRegime, entity_type: str) -> list[str]:
    for e in ENTITIES_BY_REGIME.get(regime, []):
        if e.name == entity_type:
            return e.compliance_controls
    return []
