"""Audit sink protocol.

ShellForge audit events are OCSF v1.7.0-formatted, hash-chained, and emitted
via OpenTelemetry OTLP by default. The protocol exists so that audit
emission can be swapped (e.g., direct-to-Splunk) without changing call sites.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Protocol, runtime_checkable


@dataclass(frozen=True, slots=True)
class AuditActor:
    """Who performed the action."""

    user_uid: str
    user_email: str
    user_role: str
    session_uid: str | None = None


@dataclass(frozen=True, slots=True)
class AuditResource:
    """What the action was performed on."""

    type: str                              # "sandbox" | "policy" | "user" | etc.
    uid: str                               # internal ID
    name: str                              # human-readable
    labels: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class AuditEvent:
    """A single audit event, ready for OCSF emission."""

    # Identity
    event_uid: str                         # ULID, ShellForge-generated
    occurred_at: datetime
    tenant_id: str

    # OCSF classification
    class_uid: int                         # 3002 auth, 6003 API, 4001 net, 4002 http
    activity_id: int                       # OCSF activity within the class
    category_uid: int                      # OCSF top-level category

    # Actor + action + resource
    actor: AuditActor
    action: str                            # e.g. "sandbox.created"
    resource: AuditResource
    outcome: str                           # "SUCCESS" | "FAILURE" | "BLOCKED"

    # Hash chain
    prev_hash: str                         # sha256 of previous event for this tenant
    event_hash: str                        # sha256 of this event's canonical JSON

    # Provenance
    source: str                            # "shellforge" | "openshell"

    # Free-form details (OCSF-mappable)
    details: dict[str, Any] = field(default_factory=dict)


@runtime_checkable
class AuditSink(Protocol):
    """Pluggable audit transport."""

    async def emit(self, event: AuditEvent) -> None:
        """Send a single audit event. Must be non-blocking on the request path."""
        ...

    async def flush(self) -> None:
        """Force-flush any buffered events. Called on shutdown."""
        ...
