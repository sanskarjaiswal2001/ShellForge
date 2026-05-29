"""Organizations API — platform-admin only for create/list across tenants;
org-admin for read of own tenant.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.session import session_factory
from src.interfaces.identity_provider import IdentityClaims
from src.middleware.rbac import require_admin, require_platform_admin
from src.models.organization import Organization


router = APIRouter(prefix="/organizations", tags=["organizations"])


class OrganizationOut(BaseModel):
    id: UUID
    slug: str
    name: str
    default_policy_template: str | None

    model_config = {"from_attributes": True}


class OrganizationCreate(BaseModel):
    slug: str = Field(min_length=2, max_length=64, pattern=r"^[a-z][a-z0-9-]*$")
    name: str = Field(min_length=1, max_length=255)
    default_policy_template: str | None = None


@router.get("", response_model=list[OrganizationOut])
async def list_organizations(
    _: IdentityClaims = Depends(require_platform_admin),
) -> list[OrganizationOut]:
    # Platform-admin path: needs to see all orgs. Use a session WITHOUT
    # tenant context — RLS bypassed via shellforge_admin DB role.
    async with session_factory()() as session:
        from sqlalchemy import text
        await session.execute(text("SET LOCAL ROLE shellforge_admin"))
        result = await session.execute(select(Organization).order_by(Organization.slug))
        return [OrganizationOut.model_validate(o) for o in result.scalars().all()]


@router.post("", response_model=OrganizationOut, status_code=status.HTTP_201_CREATED)
async def create_organization(
    payload: OrganizationCreate,
    _: IdentityClaims = Depends(require_platform_admin),
) -> OrganizationOut:
    async with session_factory()() as session:
        async with session.begin():
            from sqlalchemy import text
            await session.execute(text("SET LOCAL ROLE shellforge_admin"))
            org = Organization(
                slug=payload.slug,
                name=payload.name,
                default_policy_template=payload.default_policy_template,
            )
            session.add(org)
        await session.refresh(org)
        return OrganizationOut.model_validate(org)


@router.get("/me", response_model=OrganizationOut)
async def my_organization(
    claims: IdentityClaims = Depends(require_admin),
) -> OrganizationOut:
    if claims.tenant_id is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No tenant")
    async with session_factory()() as session:
        from sqlalchemy import text
        await session.execute(
            text("SELECT set_config('app.current_tenant_id', :t, true)")
            .bindparams(t=claims.tenant_id)
        )
        result = await session.execute(
            select(Organization).where(Organization.slug == claims.tenant_id)
        )
        org = result.scalar_one_or_none()
        if org is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Org not found")
        return OrganizationOut.model_validate(org)
