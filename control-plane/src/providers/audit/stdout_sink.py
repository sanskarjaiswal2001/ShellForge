"""Stdout audit sink — useful for tests and local dev when OTel is down."""

from __future__ import annotations

import json
from dataclasses import asdict

import structlog

from src.interfaces.audit_sink import AuditEvent, AuditSink

_log = structlog.get_logger(__name__)


class StdoutAuditSink(AuditSink):
    async def emit(self, event: AuditEvent) -> None:
        payload = asdict(event)
        payload["occurred_at"] = event.occurred_at.isoformat()
        _log.info("audit.event", **payload)

    async def flush(self) -> None:
        return
