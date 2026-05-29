"""Shared FastAPI dependencies."""

from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass

from fastapi import Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.audit.emitter import AuditEmitter
from src.interfaces.audit_sink import AuditSink
from src.interfaces.identity_provider import IdentityClaims
from src.middleware.auth import get_current_identity
from src.middleware.tenant_context import get_tenant_session
from src.models.user import User
from src.providers.factory import audit_sink


@dataclass
class EmitterAndSession:
    session: AsyncSession
    emitter: AuditEmitter
    user: User | None


def get_audit_emitter(sink: AuditSink = Depends(audit_sink)) -> AuditEmitter:
    return AuditEmitter(sink)


async def get_emitter_and_session(
    session: AsyncSession = Depends(get_tenant_session),
    claims: IdentityClaims = Depends(get_current_identity),
    emitter: AuditEmitter = Depends(get_audit_emitter),
) -> AsyncIterator[EmitterAndSession]:
    """One-stop bundle for tenant-scoped handlers that emit audit events."""
    user = (
        await session.execute(select(User).where(User.oidc_subject == claims.subject))
    ).scalar_one_or_none()
    yield EmitterAndSession(session=session, emitter=emitter, user=user)
