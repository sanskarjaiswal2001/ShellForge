"""Audit query API — tenant-scoped via RLS."""

from __future__ import annotations

import asyncio
import json
from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.session import tenant_scoped_session
from src.interfaces.identity_provider import IdentityClaims
from src.middleware.auth import get_current_identity
from src.middleware.rbac import require_viewer
from src.middleware.tenant_context import get_tenant_session
from src.models.audit_event import AuditEventRecord


router = APIRouter(prefix="/audit", tags=["audit"])


class AuditEventOut(BaseModel):
    id: UUID
    occurred_at: datetime
    class_uid: int
    activity_id: int
    actor_user_email: str
    actor_user_role: str
    action: str
    outcome: str
    resource_type: str
    resource_uid: str
    resource_name: str
    prev_hash: str
    event_hash: str
    source: str

    model_config = {"from_attributes": True}


@router.get("/events", response_model=list[AuditEventOut])
async def list_audit_events(
    _: IdentityClaims = Depends(require_viewer),
    session: AsyncSession = Depends(get_tenant_session),
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
    action: str | None = None,
    outcome: str | None = None,
) -> list[AuditEventOut]:
    stmt = select(AuditEventRecord).order_by(desc(AuditEventRecord.occurred_at))
    if action:
        stmt = stmt.where(AuditEventRecord.action == action)
    if outcome:
        stmt = stmt.where(AuditEventRecord.outcome == outcome)
    stmt = stmt.limit(limit).offset(offset)

    result = await session.execute(stmt)
    return [AuditEventOut.model_validate(e) for e in result.scalars().all()]


class HashChainVerification(BaseModel):
    valid: bool
    checked: int
    broken_at: UUID | None = None


@router.get("/chain/verify", response_model=HashChainVerification)
async def verify_chain(
    _: IdentityClaims = Depends(require_viewer),
    session: AsyncSession = Depends(get_tenant_session),
) -> HashChainVerification:
    """Re-walk the chain in occurred_at order, confirming every event's
    prev_hash matches the prior event's event_hash."""
    from src.config import get_settings

    stmt = select(AuditEventRecord).order_by(AuditEventRecord.occurred_at)
    result = await session.execute(stmt)
    events = result.scalars().all()

    expected = get_settings().audit_genesis_hash
    for ev in events:
        if ev.prev_hash != expected:
            return HashChainVerification(valid=False, checked=len(events), broken_at=ev.id)
        expected = ev.event_hash

    return HashChainVerification(valid=True, checked=len(events))


# ─── Real-time stream (Server-Sent Events) ──────────────────────────────


@router.get("/stream")
async def audit_stream(
    claims: IdentityClaims = Depends(get_current_identity),
    require_viewer_check: IdentityClaims = Depends(require_viewer),
) -> StreamingResponse:
    """SSE stream of newly-arrived audit events for the requesting tenant.

    Strategy: poll the DB every ~2s for events newer than the last sent UID.
    For higher throughput, swap this for LISTEN/NOTIFY on Postgres.
    """

    async def event_gen():
        last_seen: datetime | None = None
        while True:
            try:
                async with tenant_scoped_session(claims.tenant_id) as session:
                    stmt = select(AuditEventRecord).order_by(AuditEventRecord.occurred_at)
                    if last_seen is not None:
                        stmt = stmt.where(AuditEventRecord.occurred_at > last_seen)
                    else:
                        # On first iteration, return the 10 most recent in order.
                        stmt = (
                            select(AuditEventRecord)
                            .order_by(desc(AuditEventRecord.occurred_at))
                            .limit(10)
                        )

                    result = await session.execute(stmt)
                    events = list(result.scalars().all())

                    if last_seen is None:
                        events = list(reversed(events))

                    for ev in events:
                        payload = {
                            "id": str(ev.id),
                            "occurred_at": ev.occurred_at.isoformat(),
                            "actor_email": ev.actor_user_email,
                            "actor_role": ev.actor_user_role,
                            "action": ev.action,
                            "outcome": ev.outcome,
                            "resource_type": ev.resource_type,
                            "resource_name": ev.resource_name,
                            "event_hash": ev.event_hash,
                            "prev_hash": ev.prev_hash,
                            "class_uid": ev.class_uid,
                            "source": ev.source,
                        }
                        yield f"data: {json.dumps(payload)}\n\n"
                        last_seen = ev.occurred_at
            except Exception as e:  # noqa: BLE001
                yield f"event: error\ndata: {json.dumps({'error': str(e)})}\n\n"

            await asyncio.sleep(2)

    return StreamingResponse(
        event_gen(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
