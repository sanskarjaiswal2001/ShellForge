"""Audit emitter — builds AuditEvent, computes hash chain, persists, emits.

Every mutation in ShellForge goes through this emitter. Bypassing it means
no audit row and no hash-chain link — the security-reviewer subagent fails
on commits that touch state without calling the emitter.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.audit.hashing import compute_event_hash
from src.config import get_settings
from src.interfaces.audit_sink import (
    AuditActor,
    AuditEvent,
    AuditResource,
    AuditSink,
)
from src.models.audit_event import AuditEventRecord


class AuditEmitter:
    """Build → hash → persist → emit."""

    def __init__(self, sink: AuditSink) -> None:
        self._sink = sink

    async def emit(
        self,
        *,
        session: AsyncSession,
        tenant_id: str,                  # org slug for hash chain lookup
        organization_id: str,            # UUID for FK
        actor: AuditActor,
        action: str,
        resource: AuditResource,
        outcome: str,
        class_uid: int,
        category_uid: int,
        activity_id: int,
        source: str = "shellforge",
        details: dict[str, Any] | None = None,
    ) -> AuditEvent:
        prev_hash = await self._latest_hash_for_tenant(session, organization_id)

        event = AuditEvent(
            event_uid=str(uuid4()),
            occurred_at=datetime.now(UTC),
            tenant_id=tenant_id,
            class_uid=class_uid,
            activity_id=activity_id,
            category_uid=category_uid,
            actor=actor,
            action=action,
            resource=resource,
            outcome=outcome,
            prev_hash=prev_hash,
            event_hash="",                # filled below
            source=source,
            details=details or {},
        )
        # Compute hash on the in-progress event (event_hash excluded by canonical_json).
        event_hash = compute_event_hash(event)
        event = AuditEvent(**{**event.__dict__, "event_hash": event_hash})

        # Persist
        record = AuditEventRecord(
            organization_id=organization_id,
            occurred_at=event.occurred_at,
            class_uid=event.class_uid,
            category_uid=event.category_uid,
            activity_id=event.activity_id,
            actor_user_uid=actor.user_uid,
            actor_user_email=actor.user_email,
            actor_user_role=actor.user_role,
            actor_session_uid=actor.session_uid,
            action=event.action,
            outcome=event.outcome,
            resource_type=resource.type,
            resource_uid=resource.uid,
            resource_name=resource.name,
            resource_labels=resource.labels,
            prev_hash=event.prev_hash,
            event_hash=event.event_hash,
            source=event.source,
            details=event.details,
        )
        session.add(record)
        await session.flush()

        # Emit via OTel / stdout (fire and forget after flush).
        await self._sink.emit(event)
        return event

    async def _latest_hash_for_tenant(
        self, session: AsyncSession, organization_id: str
    ) -> str:
        stmt = (
            select(AuditEventRecord.event_hash)
            .where(AuditEventRecord.organization_id == organization_id)
            .order_by(desc(AuditEventRecord.occurred_at))
            .limit(1)
        )
        result = await session.execute(stmt)
        latest = result.scalar_one_or_none()
        if latest:
            return latest
        return get_settings().audit_genesis_hash
