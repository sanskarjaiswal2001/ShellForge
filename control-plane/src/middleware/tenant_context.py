"""Tenant-scoped DB session dependency.

Extracts ``tenant_id`` from the validated identity claims, opens a DB session
with ``SET LOCAL app.current_tenant_id`` applied transactionally. The session
is yielded into the handler. RLS policies then enforce isolation at the DB.

NEVER use a plain ``session_factory()`` session in tenant-scoped handlers —
RLS won't have a tenant context and queries will silently return zero rows.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

from fastapi import Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.session import tenant_scoped_session
from src.interfaces.identity_provider import IdentityClaims
from src.middleware.auth import get_current_identity


async def get_tenant_session(
    claims: IdentityClaims = Depends(get_current_identity),
) -> AsyncIterator[AsyncSession]:
    if claims.tenant_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User has no tenant association",
        )

    async with tenant_scoped_session(claims.tenant_id) as session:
        yield session
