"""Users API — tenant-scoped via RLS."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.interfaces.identity_provider import IdentityClaims
from src.middleware.rbac import require_admin, require_viewer
from src.middleware.tenant_context import get_tenant_session
from src.models.user import User


router = APIRouter(prefix="/users", tags=["users"])


class UserOut(BaseModel):
    id: UUID
    organization_id: UUID
    oidc_subject: str
    email: str
    name: str
    roles: list[str]

    model_config = {"from_attributes": True}


class UserCreate(BaseModel):
    oidc_subject: str = Field(min_length=1, max_length=255)
    email: EmailStr
    name: str = Field(min_length=1, max_length=255)
    roles: list[str] = Field(default_factory=list)


@router.get("", response_model=list[UserOut])
async def list_users(
    _: IdentityClaims = Depends(require_viewer),
    session: AsyncSession = Depends(get_tenant_session),
) -> list[UserOut]:
    # RLS will scope to current tenant automatically.
    result = await session.execute(select(User).order_by(User.email))
    return [UserOut.model_validate(u) for u in result.scalars().all()]


@router.post("", response_model=UserOut, status_code=status.HTTP_201_CREATED)
async def create_user(
    payload: UserCreate,
    claims: IdentityClaims = Depends(require_admin),
    session: AsyncSession = Depends(get_tenant_session),
) -> UserOut:
    # Resolve the requesting tenant's org UUID via RLS-scoped session.
    from src.models.organization import Organization

    org_result = await session.execute(
        select(Organization).where(Organization.slug == claims.tenant_id)
    )
    org = org_result.scalar_one_or_none()
    if org is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No tenant context")

    user = User(
        organization_id=org.id,
        oidc_subject=payload.oidc_subject,
        email=payload.email,
        name=payload.name,
        roles=payload.roles,
    )
    session.add(user)
    await session.flush()
    return UserOut.model_validate(user)


@router.get("/{user_id}", response_model=UserOut)
async def get_user(
    user_id: UUID,
    _: IdentityClaims = Depends(require_viewer),
    session: AsyncSession = Depends(get_tenant_session),
) -> UserOut:
    result = await session.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None:
        # RLS returns nothing if cross-tenant — still 404, never 403.
        # Never leak whether a user exists in another tenant.
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return UserOut.model_validate(user)
