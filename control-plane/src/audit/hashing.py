"""Canonical JSON + SHA-256 hashing for the audit hash chain."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict
from datetime import datetime
from typing import Any

from src.interfaces.audit_sink import AuditEvent


def _default(o: Any) -> Any:
    if isinstance(o, datetime):
        return o.isoformat()
    raise TypeError(f"Not JSON-serializable: {type(o).__name__}")


def canonical_json(event: AuditEvent) -> str:
    payload = asdict(event)
    # Exclude the event_hash from its own hash computation.
    payload.pop("event_hash", None)
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), default=_default)


def compute_event_hash(event: AuditEvent) -> str:
    return hashlib.sha256(canonical_json(event).encode("utf-8")).hexdigest()
