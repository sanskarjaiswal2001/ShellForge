"""Sandbox API — tenant-scoped via RLS + ComputeProvider abstraction."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import EmitterAndSession, get_emitter_and_session
from src.interfaces.audit_sink import AuditActor, AuditResource
from src.interfaces.compute_provider import (
    ComputeProvider,
    SandboxNotFoundError,
    SandboxSpec,
)
from src.interfaces.identity_provider import IdentityClaims
from src.middleware.rbac import require_developer, require_viewer
from src.middleware.tenant_context import get_tenant_session
from src.models.organization import Organization
from src.models.sandbox import Sandbox
from src.providers.factory import compute_provider
from src.services.policies import KNOWN_TEMPLATES, load_template


router = APIRouter(prefix="/sandboxes", tags=["sandboxes"])


# ─── Schemas ────────────────────────────────────────────────────────────


class SandboxOut(BaseModel):
    id: UUID
    name: str
    compute_uid: str
    agent: str
    policy_template: str
    phase: str
    labels: dict
    created_at: datetime
    last_phase_at: datetime | None

    model_config = {"from_attributes": True}


class SandboxCreate(BaseModel):
    name: str = Field(min_length=2, max_length=64, pattern=r"^[a-z][a-z0-9-]*$")
    agent: str = Field(default="claude", pattern=r"^(claude|opencode|codex|copilot)$")
    policy_template: str = Field(default="baseline")
    provider_names: list[str] = Field(default_factory=list)
    compute_driver: str = "docker"


class ViolationRequest(BaseModel):
    destination: str = Field(min_length=1, max_length=255)


# ─── Routes ─────────────────────────────────────────────────────────────


@router.get("", response_model=list[SandboxOut])
async def list_sandboxes(
    claims: IdentityClaims = Depends(require_viewer),
    session: AsyncSession = Depends(get_tenant_session),
    compute: ComputeProvider = Depends(compute_provider),
) -> list[SandboxOut]:
    result = await session.execute(select(Sandbox).order_by(Sandbox.created_at.desc()))
    sandboxes = list(result.scalars().all())

    # Sync phase from compute backend for non-terminal states. Without this,
    # freshly-provisioned sandboxes are stuck in PROVISIONING in the UI.
    dirty = False
    for s in sandboxes:
        if s.phase in ("READY", "ERROR", "DELETING"):
            continue
        try:
            ref = await compute.get_sandbox(claims.tenant_id, s.name)
            if ref.phase.value != s.phase:
                s.phase = ref.phase.value
                s.last_phase_at = datetime.now(UTC)
                dirty = True
        except Exception:  # noqa: BLE001
            continue
    if dirty:
        await session.flush()

    return [SandboxOut.model_validate(s) for s in sandboxes]


@router.post("", response_model=SandboxOut, status_code=status.HTTP_201_CREATED)
async def create_sandbox(
    payload: SandboxCreate,
    claims: IdentityClaims = Depends(require_developer),
    es: EmitterAndSession = Depends(get_emitter_and_session),
    compute: ComputeProvider = Depends(compute_provider),
) -> SandboxOut:
    if payload.policy_template not in KNOWN_TEMPLATES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown policy template: {payload.policy_template}",
        )

    session = es.session
    org = (
        await session.execute(
            select(Organization).where(Organization.slug == claims.tenant_id)
        )
    ).scalar_one()

    # Resolve tenant-namespaced provider names.
    providers = tuple(f"{name}-{claims.tenant_id}" for name in payload.provider_names)

    spec = SandboxSpec(
        name=payload.name,
        policy_yaml=load_template(payload.policy_template),
        agent=payload.agent,
        providers=providers,
        compute_driver=payload.compute_driver,
        labels={
            "shellforge.io/tenant": claims.tenant_id,
            "shellforge.io/user": claims.subject,
            "shellforge.io/agent": payload.agent,
            "shellforge.io/policy_template": payload.policy_template,
        },
    )

    try:
        ref = await compute.create_sandbox(claims.tenant_id, spec)
    except Exception as e:  # noqa: BLE001
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Compute provider rejected: {e}",
        ) from e

    record = Sandbox(
        organization_id=org.id,
        created_by_user_id=es.user.id if es.user else None,
        name=ref.name,
        compute_uid=ref.uid,
        agent=payload.agent,
        policy_template=payload.policy_template,
        phase=ref.phase.value,
        last_phase_at=datetime.now(UTC),
        labels=ref.labels,
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
        action="sandbox.created",
        resource=AuditResource(
            type="sandbox",
            uid=str(record.id),
            name=record.name,
            labels={
                "agent": payload.agent,
                "policy_template": payload.policy_template,
            },
        ),
        outcome="SUCCESS",
        class_uid=6003,
        category_uid=6,
        activity_id=1,
        details={
            "compute_uid": record.compute_uid,
            "providers_attached": list(providers),
        },
    )
    return SandboxOut.model_validate(record)


@router.get("/{sandbox_id}", response_model=SandboxOut)
async def get_sandbox(
    sandbox_id: UUID,
    claims: IdentityClaims = Depends(require_viewer),
    session: AsyncSession = Depends(get_tenant_session),
    compute: ComputeProvider = Depends(compute_provider),
) -> SandboxOut:
    result = await session.execute(select(Sandbox).where(Sandbox.id == sandbox_id))
    sandbox = result.scalar_one_or_none()
    if sandbox is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sandbox not found")

    # Sync phase from compute backend (mock auto-progresses; openshell reflects gateway).
    try:
        ref = await compute.get_sandbox(claims.tenant_id, sandbox.name)
        if ref.phase.value != sandbox.phase:
            sandbox.phase = ref.phase.value
            sandbox.last_phase_at = datetime.now(UTC)
            await session.flush()
    except Exception:  # noqa: BLE001
        pass  # leave DB-cached phase

    return SandboxOut.model_validate(sandbox)


class ConnectionInfo(BaseModel):
    """How to actually USE the sandbox.

    Backend-dependent: mock returns demo-mode info; OpenShell returns the
    real CLI commands + SSH endpoint."""
    backend: str
    is_real: bool
    summary: str
    cli_command: str | None = None
    ssh_command: str | None = None
    web_terminal_url: str | None = None
    notes: list[str] = []


@router.get("/{sandbox_id}/connection", response_model=ConnectionInfo)
async def get_sandbox_connection(
    sandbox_id: UUID,
    claims: IdentityClaims = Depends(require_viewer),
    session: AsyncSession = Depends(get_tenant_session),
) -> ConnectionInfo:
    from src.config import get_settings
    settings = get_settings()

    result = await session.execute(select(Sandbox).where(Sandbox.id == sandbox_id))
    sandbox = result.scalar_one_or_none()
    if sandbox is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sandbox not found")

    backend = settings.compute_backend
    if backend == "mock":
        return ConnectionInfo(
            backend="mock",
            is_real=False,
            summary=(
                "This sandbox lives in the control plane's in-memory mock backend — "
                "no real container, no real agent, no real network namespace. "
                "It exists to demonstrate the full ShellForge lifecycle (provisioning "
                "stages, policy application, audit emission, violation simulation) "
                "without depending on the alpha-stage OpenShell upstream."
            ),
            notes=[
                "All audit events are real — they hit Postgres + OTel.",
                "Policy is applied virtually (no traffic to enforce).",
                "Simulate violation triggers a real OCSF event in the audit chain.",
                "To run a REAL sandbox: set COMPUTE_BACKEND=openshell and start the gateway via `podman compose --profile openshell up -d openshell-gateway`.",
            ],
        )

    if backend == "openshell":
        gw = settings.openshell_gateway_endpoint
        return ConnectionInfo(
            backend="openshell",
            is_real=True,
            summary=(
                f"This is a real isolated runtime managed by NVIDIA OpenShell. "
                f"It runs as a container on the gateway's compute driver "
                f"({settings.openshell_default_compute_driver}). Connect with the "
                f"OpenShell CLI."
            ),
            cli_command=f"openshell sandbox connect {sandbox.name}",
            ssh_command=(
                f"openshell --gateway-endpoint={gw} sandbox connect {sandbox.name} "
                f"--editor vscode"
            ),
            notes=[
                f"Gateway endpoint: {gw}",
                f"Compute driver: {settings.openshell_default_compute_driver}",
                f"Agent: {sandbox.agent} (pre-installed in the sandbox image)",
                "Filesystem is Landlock-restricted per the active policy.",
                "All egress goes through the policy proxy.",
            ],
        )

    return ConnectionInfo(
        backend=backend,
        is_real=False,
        summary=f"Compute backend `{backend}` is not implemented in MVP.",
    )


class TimelineEntry(BaseModel):
    key: str
    message: str
    status: str  # "in_progress" | "done" | "failed"
    started_at: str
    updated_at: str


@router.get("/{sandbox_id}/timeline", response_model=list[TimelineEntry])
async def get_sandbox_timeline(
    sandbox_id: UUID,
    claims: IdentityClaims = Depends(require_viewer),
    session: AsyncSession = Depends(get_tenant_session),
    compute: ComputeProvider = Depends(compute_provider),
) -> list[TimelineEntry]:
    """Per-stage provisioning timeline. Mock backend produces 7 stages;
    OpenShell backend will use real WatchSandbox events when wired."""
    result = await session.execute(select(Sandbox).where(Sandbox.id == sandbox_id))
    sandbox = result.scalar_one_or_none()
    if sandbox is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sandbox not found")

    if hasattr(compute, "get_timeline"):
        try:
            entries = await compute.get_timeline(claims.tenant_id, sandbox.name)
            return [TimelineEntry(**e) for e in entries]
        except Exception:  # noqa: BLE001
            return []
    return []


@router.delete("/{sandbox_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_sandbox(
    sandbox_id: UUID,
    claims: IdentityClaims = Depends(require_developer),
    es: EmitterAndSession = Depends(get_emitter_and_session),
    compute: ComputeProvider = Depends(compute_provider),
) -> None:
    session = es.session
    result = await session.execute(select(Sandbox).where(Sandbox.id == sandbox_id))
    record = result.scalar_one_or_none()
    if record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sandbox not found")

    org = (
        await session.execute(
            select(Organization).where(Organization.id == record.organization_id)
        )
    ).scalar_one()

    try:
        await compute.delete_sandbox(claims.tenant_id, record.name)
    except SandboxNotFoundError:
        # Already gone in compute layer — proceed to remove the row.
        pass

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
        action="sandbox.deleted",
        resource=AuditResource(
            type="sandbox",
            uid=str(record.id),
            name=record.name,
        ),
        outcome="SUCCESS",
        class_uid=6003,
        category_uid=6,
        activity_id=4,
    )


@router.post("/{sandbox_id}/simulate-violation", status_code=status.HTTP_202_ACCEPTED)
async def simulate_violation(
    sandbox_id: UUID,
    payload: ViolationRequest,
    claims: IdentityClaims = Depends(require_developer),
    es: EmitterAndSession = Depends(get_emitter_and_session),
    compute: ComputeProvider = Depends(compute_provider),
) -> dict:
    """Demo helper: trigger a realistic policy-violation event without an
    actual sandbox exfil attempt. Used by the demo script to make the
    violation visible in the live audit feed."""
    session = es.session
    result = await session.execute(select(Sandbox).where(Sandbox.id == sandbox_id))
    record = result.scalar_one_or_none()
    if record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sandbox not found")

    org = (
        await session.execute(
            select(Organization).where(Organization.id == record.organization_id)
        )
    ).scalar_one()

    # If the compute provider supports it (mock provider does), also log
    # the event into the sandbox's own log buffer.
    if hasattr(compute, "simulate_violation"):
        try:
            await compute.simulate_violation(record.name, payload.destination)
        except Exception:  # noqa: BLE001
            pass

    event = await es.emitter.emit(
        session=session,
        tenant_id=claims.tenant_id,
        organization_id=org.id,
        actor=AuditActor(
            user_uid=claims.subject,
            user_email=claims.email,
            user_role=_primary_role(claims),
        ),
        action="network.denied",
        resource=AuditResource(
            type="endpoint",
            uid=f"{record.name}/{payload.destination}",
            name=payload.destination,
            labels={"sandbox": record.name},
        ),
        outcome="BLOCKED",
        class_uid=4002,
        category_uid=4,
        activity_id=6,
        source="openshell",
        details={
            "destination": payload.destination,
            "policy": record.policy_template,
            "reason": "endpoint not in allowlist",
        },
    )
    return {"event_uid": event.event_uid, "event_hash": event.event_hash}


def _primary_role(claims: IdentityClaims) -> str:
    priority = ["platform:admin", "org:admin", "org:developer", "org:viewer"]
    for role in priority:
        if role in claims.roles:
            return role
    return "unknown"
