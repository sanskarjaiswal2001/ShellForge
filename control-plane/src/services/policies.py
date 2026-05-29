"""Policy template loading + version management."""

from __future__ import annotations

import hashlib
from pathlib import Path

import yaml


POLICIES_DIR = Path(__file__).resolve().parents[3] / "policies"

KNOWN_TEMPLATES = {
    "baseline": "baseline.yaml",
    "hipaa-healthcare": "hipaa-healthcare.yaml",
    "pci-payments": "pci-payments.yaml",
    "soc2-saas": "soc2-saas.yaml",
}


def list_templates() -> list[str]:
    return sorted(KNOWN_TEMPLATES.keys())


def load_template(name: str) -> str:
    if name not in KNOWN_TEMPLATES:
        raise FileNotFoundError(f"Unknown policy template: {name}")
    path = POLICIES_DIR / KNOWN_TEMPLATES[name]
    return path.read_text()


def validate_policy_yaml(yaml_str: str) -> tuple[bool, str]:
    """Returns (is_valid, error_message). Best-effort schema check."""
    if len(yaml_str.encode("utf-8")) > 262_144:
        return False, "Policy exceeds 256 KB limit"

    try:
        data = yaml.safe_load(yaml_str)
    except yaml.YAMLError as e:
        return False, f"Invalid YAML: {e}"

    if not isinstance(data, dict):
        return False, "Top-level must be a mapping"
    if data.get("version") != 1:
        return False, "Missing or unsupported `version: 1`"

    process = data.get("process", {})
    if process.get("run_as_user") in ("root", "0"):
        return False, "run_as_user cannot be root or UID 0"

    fs = data.get("filesystem_policy", {})
    for path_list in (fs.get("read_only", []), fs.get("read_write", [])):
        for p in path_list or []:
            if ".." in p:
                return False, f"Path contains '..': {p}"
            if p == "/":
                return False, "Path cannot equal '/'"

    return True, ""


def policy_hash(yaml_str: str) -> str:
    return hashlib.sha256(yaml_str.encode("utf-8")).hexdigest()
