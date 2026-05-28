"""SCIM 2.0 endpoints (minimal subset).

RFC 7643/7644 — used by IdPs (Okta, Azure AD) to provision/deprovision users.
This is a stripped-down implementation: just User resource POST/PUT/DELETE,
which is what most IdPs need for the basic lifecycle.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.interfaces.identity_provider import IdentityClaims
from src.middleware.rbac import require_admin
from src.middleware.tenant_context import get_tenant_session
from src.models.user import User


router = APIRouter(prefix="/scim/v2", tags=["scim"])


class ScimName(BaseModel):
    givenName: str = ""
    familyName: str = ""
    formatted: str = ""


class ScimEmail(BaseModel):
    value: str
    primary: bool = True


class ScimUser(BaseModel):
    schemas: list[str] = ["urn:ietf:params:scim:schemas:core:2.0:User"]
    id: str | None = None
    externalId: str | None = None
    userName: str
    name: ScimName = ScimName()
    emails: list[ScimEmail] = []
    active: bool = True


def _to_scim(user: User) -> ScimUser:
    return ScimUser(
        id=str(user.id),
        externalId=user.oidc_subject,
        userName=user.email,
        name=ScimName(formatted=user.name),
        emails=[ScimEmail(value=user.email, primary=True)],
        active=True,
    )


@router.post("/Users", response_model=ScimUser, status_code=status.HTTP_201_CREATED)
async def scim_create_user(
    payload: ScimUser,
    claims: IdentityClaims = Depends(require_admin),
    session: AsyncSession = Depends(get_tenant_session),
) -> ScimUser:
    from src.models.organization import Organization

    org_result = await session.execute(
        select(Organization).where(Organization.slug == claims.tenant_id)
    )
    org = org_result.scalar_one_or_none()
    if org is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No tenant context")

    email = payload.emails[0].value if payload.emails else payload.userName
    user = User(
        organization_id=org.id,
        oidc_subject=payload.externalId or payload.userName,
        email=email,
        name=payload.name.formatted or payload.userName,
        roles=["org:viewer"],   # SCIM-provisioned users start as viewer
    )
    session.add(user)
    await session.flush()
    return _to_scim(user)


@router.put("/Users/{user_id}", response_model=ScimUser)
async def scim_update_user(
    user_id: UUID,
    payload: ScimUser,
    _: IdentityClaims = Depends(require_admin),
    session: AsyncSession = Depends(get_tenant_session),
) -> ScimUser:
    result = await session.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    if payload.emails:
        user.email = payload.emails[0].value
    if payload.name.formatted:
        user.name = payload.name.formatted
    await session.flush()
    return _to_scim(user)


@router.delete("/Users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def scim_delete_user(
    user_id: UUID,
    _: IdentityClaims = Depends(require_admin),
    session: AsyncSession = Depends(get_tenant_session),
) -> None:
    result = await session.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None:
        # SCIM spec: idempotent delete. Cross-tenant delete also returns 404.
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    await session.delete(user)
