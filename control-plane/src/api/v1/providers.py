"""Provider management API — tenant-scoped credential bundles.

Providers link tenant secrets (in Infisical) to OpenShell's provider system
so AI agents automatically receive the right API keys at sandbox creation.

Flow:
  POST /providers { type: "claude", credentials: { ANTHROPIC_API_KEY: "sk-..." } }
    1. Store credentials in Infisical at:
         shellforge/tenants/<org_id>/providers/<provider_name>/<key>
    2. Create provider in OpenShell compute backend (if active):
         CreateProvider { name: "claude-<org_id>", type: "claude", credentials }
    3. Record provider metadata in DB (keys only, never values).

When creating a sandbox, pass provider_names: ["claude"] — we automatically
resolve to the tenant-namespaced name "claude-<org_id>".
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import EmitterAndSession, get_emitter_and_session
from src.interfaces.audit_sink import AuditActor, AuditResource
from src.interfaces.compute_provider import ComputeProvider
from src.interfaces.identity_provider import IdentityClaims
from src.interfaces.secret_provider import SecretAccessError, SecretProvider
from src.middleware.rbac import require_admin, require_viewer
from src.middleware.tenant_context import get_tenant_session
from src.models.organization import Organization
from src.models.provider import PROVIDER_TYPES, TenantProvider
from src.providers.factory import compute_provider, secret_provider


router = APIRouter(prefix="/providers", tags=["providers"])


# ─── Schemas ────────────────────────────────────────────────────────────────


class ProviderOut(BaseModel):
    id: UUID
    name: str
    type: str
    credential_keys: list[str]
    secret_prefix: str
    created_at: datetime

    model_config = {"from_attributes": True}

    @classmethod
    def from_record(cls, p: TenantProvider) -> "ProviderOut":
        return cls(
            id=p.id,
            name=p.name,
            type=p.type,
            credential_keys=p.credential_keys.split(",") if p.credential_keys else [],
            secret_prefix=p.secret_prefix,
            created_at=p.created_at,
        )


class ProviderCreate(BaseModel):
    name: str = Field(
        min_length=1,
        max_length=64,
        pattern=r"^[a-z][a-z0-9-]*$",
        description="Short slug, e.g. 'claude'. Will be namespaced to 'claude-<tenant>'.",
    )
    type: str = Field(
        description="Provider type: claude|openai|github|gitlab|nvidia|copilot|generic"
    )
    credentials: dict[str, str] = Field(
        description="Secret values to store. Keys match the env vars injected into sandboxes.",
        min_length=1,
    )


# ─── Routes ─────────────────────────────────────────────────────────────────


@router.get("", response_model=list[ProviderOut])
async def list_providers(
    _: IdentityClaims = Depends(require_viewer),
    session: AsyncSession = Depends(get_tenant_session),
) -> list[ProviderOut]:
    result = await session.execute(
        select(TenantProvider).order_by(TenantProvider.created_at)
    )
    return [ProviderOut.from_record(p) for p in result.scalars().all()]


@router.get("/types", response_model=dict[str, list[str]])
async def list_provider_types(
    _: IdentityClaims = Depends(require_viewer),
) -> dict[str, list[str]]:
    """Return known provider types and the env vars they inject."""
    return PROVIDER_TYPES


@router.post("", response_model=ProviderOut, status_code=status.HTTP_201_CREATED)
async def create_provider(
    payload: ProviderCreate,
    claims: IdentityClaims = Depends(require_admin),
    es: EmitterAndSession = Depends(get_emitter_and_session),
    compute: ComputeProvider = Depends(compute_provider),
    secrets: SecretProvider = Depends(secret_provider),
) -> ProviderOut:
    session = es.session

    if payload.type not in PROVIDER_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown provider type '{payload.type}'. Valid: {list(PROVIDER_TYPES)}",
        )

    org = (
        await session.execute(
            select(Organization).where(Organization.slug == claims.tenant_id)
        )
    ).scalar_one()

    namespaced_name = f"{payload.name}-{claims.tenant_id}"
    from src.config import get_settings
    secret_prefix = f"{get_settings().secret_path_prefix}/{org.id}/providers/{payload.name}"

    # 1. Store credentials in secrets backend.
    try:
        for key, value in payload.credentials.items():
            await secrets.set(f"{secret_prefix}/{key}", value)
    except SecretAccessError as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Secrets backend rejected credentials: {e}. "
                   "Check SECRET_BACKEND + backend credentials in .env.",
        ) from e

    # 2. Propagate to compute backend.
    try:
        await compute.create_provider(
            tenant_id=claims.tenant_id,
            name=namespaced_name,
            provider_type=payload.type,
            credentials=payload.credentials,
        )
    except NotImplementedError:
        pass  # mock backend: no-op, that's fine
    except Exception as e:  # noqa: BLE001
        # Don't fail if compute can't create — secrets are still stored.
        import structlog
        structlog.get_logger(__name__).warning(
            "provider.compute_create_failed", error=str(e), provider=namespaced_name
        )

    # 3. Record metadata (keys only, not values) in DB.
    record = TenantProvider(
        organization_id=org.id,
        name=namespaced_name,
        type=payload.type,
        credential_keys=",".join(payload.credentials.keys()),
        secret_prefix=secret_prefix,
    )
    session.add(record)
    await session.flush()

    await es.emitter.emit(
        session=session,
        tenant_id=claims.tenant_id,
        organization_id=org.id,
        actor=AuditActor(
            user_uid=claims.subject,
            user_email=claims.email,
            user_role=_primary_role(claims),
        ),
        action="provider.created",
        resource=AuditResource(
            type="provider",
            uid=str(record.id),
            name=namespaced_name,
            labels={"type": payload.type},
        ),
        outcome="SUCCESS",
        class_uid=6003,
        category_uid=6,
        activity_id=1,
        details={"type": payload.type, "credential_keys": list(payload.credentials.keys())},
    )
    return ProviderOut.from_record(record)


@router.delete("/{provider_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_provider(
    provider_id: UUID,
    claims: IdentityClaims = Depends(require_admin),
    es: EmitterAndSession = Depends(get_emitter_and_session),
    secrets: SecretProvider = Depends(secret_provider),
) -> None:
    session = es.session
    result = await session.execute(
        select(TenantProvider).where(TenantProvider.id == provider_id)
    )
    record = result.scalar_one_or_none()
    if record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Provider not found")

    org = (
        await session.execute(
            select(Organization).where(Organization.id == record.organization_id)
        )
    ).scalar_one()

    # Remove secrets from Infisical.
    for key in (record.credential_keys or "").split(","):
        if key:
            await secrets.delete(f"{record.secret_prefix}/{key}")

    await session.delete(record)

    await es.emitter.emit(
        session=session,
        tenant_id=claims.tenant_id,
        organization_id=org.id,
        actor=AuditActor(
            user_uid=claims.subject,
            user_email=claims.email,
            user_role=_primary_role(claims),
        ),
        action="provider.deleted",
        resource=AuditResource(
            type="provider",
            uid=str(provider_id),
            name=record.name,
        ),
        outcome="SUCCESS",
        class_uid=6003,
        category_uid=6,
        activity_id=4,
    )


def _primary_role(claims: IdentityClaims) -> str:
    for role in ["platform:admin", "org:admin", "org:developer", "org:viewer"]:
        if role in claims.roles:
            return role
    return "unknown"
