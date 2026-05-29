"""Policy template + version API."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_emitter_and_session, EmitterAndSession
from src.audit.emitter import AuditEmitter
from src.interfaces.audit_sink import AuditActor, AuditResource
from src.interfaces.identity_provider import IdentityClaims
from src.middleware.rbac import require_admin, require_viewer
from src.middleware.tenant_context import get_tenant_session
from src.models.organization import Organization
from src.models.policy import PolicyVersion
from src.services.policies import (
    KNOWN_TEMPLATES,
    list_templates,
    load_template,
    policy_hash,
    validate_policy_yaml,
)


router = APIRouter(prefix="/policies", tags=["policies"])


# ─── Templates ──────────────────────────────────────────────────────────


class TemplateOut(BaseModel):
    name: str
    yaml: str


@router.get("/templates", response_model=list[str])
async def list_policy_templates(
    _: IdentityClaims = Depends(require_viewer),
) -> list[str]:
    return list_templates()


@router.get("/templates/{name}", response_model=TemplateOut)
async def get_policy_template(
    name: str,
    _: IdentityClaims = Depends(require_viewer),
) -> TemplateOut:
    try:
        return TemplateOut(name=name, yaml=load_template(name))
    except FileNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Template not found")


# ─── Validation ─────────────────────────────────────────────────────────


class ValidateRequest(BaseModel):
    yaml: str


class ValidateResponse(BaseModel):
    valid: bool
    error: str | None = None
    sha256: str | None = None


@router.post("/validate", response_model=ValidateResponse)
async def validate_policy(
    payload: ValidateRequest,
    _: IdentityClaims = Depends(require_viewer),
) -> ValidateResponse:
    ok, err = validate_policy_yaml(payload.yaml)
    return ValidateResponse(
        valid=ok,
        error=err or None,
        sha256=policy_hash(payload.yaml) if ok else None,
    )


# ─── Per-tenant versions ────────────────────────────────────────────────


class PolicyVersionOut(BaseModel):
    id: UUID
    name: str
    version: int
    template: str
    sha256: str
    created_at: datetime

    model_config = {"from_attributes": True}


class PolicyCreate(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    template: str = Field(min_length=1, max_length=64)
    yaml: str | None = None  # if absent, loaded from template


@router.get("", response_model=list[PolicyVersionOut])
async def list_policies(
    _: IdentityClaims = Depends(require_viewer),
    session: AsyncSession = Depends(get_tenant_session),
) -> list[PolicyVersionOut]:
    stmt = select(PolicyVersion).order_by(PolicyVersion.name, desc(PolicyVersion.version))
    result = await session.execute(stmt)
    return [PolicyVersionOut.model_validate(p) for p in result.scalars().all()]


@router.post("", response_model=PolicyVersionOut, status_code=status.HTTP_201_CREATED)
async def create_policy_version(
    payload: PolicyCreate,
    claims: IdentityClaims = Depends(require_admin),
    es: EmitterAndSession = Depends(get_emitter_and_session),
) -> PolicyVersionOut:
    session = es.session
    emitter = es.emitter

    if payload.template not in KNOWN_TEMPLATES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown template: {payload.template}",
        )

    yaml_content = payload.yaml or load_template(payload.template)
    ok, err = validate_policy_yaml(yaml_content)
    if not ok:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=err)

    # Resolve tenant org row.
    org = (
        await session.execute(
            select(Organization).where(Organization.slug == claims.tenant_id)
        )
    ).scalar_one()

    # Next version number per (org, name)
    latest = (
        await session.execute(
            select(PolicyVersion.version)
            .where(
                PolicyVersion.organization_id == org.id,
                PolicyVersion.name == payload.name,
            )
            .order_by(desc(PolicyVersion.version))
            .limit(1)
        )
    ).scalar_one_or_none()
    next_version = (latest or 0) + 1

    user = es.user
    record = PolicyVersion(
        organization_id=org.id,
        name=payload.name,
        version=next_version,
        template=payload.template,
        yaml_content=yaml_content,
        sha256=policy_hash(yaml_content),
        created_by_user_id=user.id if user else None,
    )
    session.add(record)
    await session.flush()

    await emitter.emit(
        session=session,
        tenant_id=claims.tenant_id,
        organization_id=org.id,
        actor=AuditActor(
            user_uid=claims.subject,
            user_email=claims.email,
            user_role=_primary_role(claims),
        ),
        action="policy.created",
        resource=AuditResource(
            type="policy",
            uid=str(record.id),
            name=f"{payload.name}@v{next_version}",
            labels={"template": payload.template, "sha256": record.sha256[:16]},
        ),
        outcome="SUCCESS",
        class_uid=6003,
        category_uid=6,
        activity_id=1,
        details={"template": payload.template, "version": next_version},
    )

    return PolicyVersionOut.model_validate(record)


def _primary_role(claims: IdentityClaims) -> str:
    priority = ["platform:admin", "org:admin", "org:developer", "org:viewer"]
    for role in priority:
        if role in claims.roles:
            return role
    return "unknown"
