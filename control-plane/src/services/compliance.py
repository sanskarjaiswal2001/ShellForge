"""Compliance pack generator: map audit events → compliance controls → PDF."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Literal

from jinja2 import Environment, FileSystemLoader, select_autoescape


Framework = Literal["soc2", "hipaa", "pci"]


# ─── Control mappings ──────────────────────────────────────────────────────
# Action → list of (framework, control_id, control_description)

CONTROL_MAP: dict[str, list[tuple[Framework, str, str]]] = {
    "sandbox.created": [
        ("soc2", "CC6.1", "Logical access controls — restricted sandbox provisioning"),
        ("hipaa", "§164.308(a)(4)", "Information access management — provisioning"),
        ("pci", "Req 7.2", "Access by need-to-know — explicit sandbox creation"),
    ],
    "sandbox.deleted": [
        ("soc2", "CC6.1", "Logical access controls — sandbox termination"),
        ("hipaa", "§164.308(a)(4)", "Information access management — deprovisioning"),
    ],
    "policy.created": [
        ("soc2", "CC8.1", "Change management — policy version control"),
        ("hipaa", "§164.308(a)(8)", "Evaluation — periodic policy review"),
        ("pci", "Req 6.4", "Change control — addresses common vulnerabilities"),
    ],
    "policy.applied": [
        ("soc2", "CC6.1", "Logical access controls — policy enforcement"),
        ("pci", "Req 1.3", "Restrict outbound traffic from CDE"),
    ],
    "provider.attached": [
        ("soc2", "CC6.6", "Authorized communications via approved credentials"),
        ("hipaa", "§164.312(d)", "Authentication mechanisms"),
    ],
    "network.denied": [
        ("soc2", "CC7.2", "Detection of anomalies — denied egress"),
        ("hipaa", "§164.312(b)", "Audit controls — recorded violations"),
        ("pci", "Req 10.2", "Audit logs of all access attempts"),
    ],
    "sandbox.accessed": [
        ("soc2", "CC6.1", "Logical access controls — session record"),
        ("hipaa", "§164.312(b)", "Audit controls — session recorded"),
    ],
    "user.created": [
        ("soc2", "CC6.2", "User identity registration"),
        ("hipaa", "§164.308(a)(3)", "Workforce security — authorization"),
    ],
}


FRAMEWORK_TITLES: dict[Framework, str] = {
    "soc2": "SOC 2 Type II",
    "hipaa": "HIPAA (45 CFR Part 164)",
    "pci": "PCI DSS v4.0",
}


@dataclass
class ControlEvidence:
    control_id: str
    control_description: str
    matched_events: list[dict]


@dataclass
class CompliancePack:
    framework: Framework
    framework_title: str
    organization_slug: str
    organization_name: str
    period_start: datetime
    period_end: datetime
    generated_at: datetime
    evidence_by_control: dict[str, ControlEvidence]
    total_events: int
    blocked_events: int


def collect_evidence(
    framework: Framework,
    org_slug: str,
    org_name: str,
    period_start: datetime,
    period_end: datetime,
    events: list[dict],
) -> CompliancePack:
    by_control: dict[str, ControlEvidence] = {}
    blocked = 0

    for event in events:
        if event.get("outcome") == "BLOCKED":
            blocked += 1
        mappings = CONTROL_MAP.get(event.get("action", ""), [])
        for fw, control_id, desc in mappings:
            if fw != framework:
                continue
            if control_id not in by_control:
                by_control[control_id] = ControlEvidence(
                    control_id=control_id,
                    control_description=desc,
                    matched_events=[],
                )
            by_control[control_id].matched_events.append(event)

    return CompliancePack(
        framework=framework,
        framework_title=FRAMEWORK_TITLES[framework],
        organization_slug=org_slug,
        organization_name=org_name,
        period_start=period_start,
        period_end=period_end,
        generated_at=datetime.now(),
        evidence_by_control=dict(sorted(by_control.items())),
        total_events=len(events),
        blocked_events=blocked,
    )


# ─── HTML rendering ────────────────────────────────────────────────────────


_TEMPLATES_DIR = Path(__file__).resolve().parents[1] / "services" / "templates"


def _env() -> Environment:
    return Environment(
        loader=FileSystemLoader(_TEMPLATES_DIR),
        autoescape=select_autoescape(["html"]),
    )


def render_html(pack: CompliancePack) -> str:
    env = _env()
    tmpl = env.get_template("compliance-pack.html")
    return tmpl.render(pack=pack)
