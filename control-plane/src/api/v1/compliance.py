"""Compliance evidence pack API — generates SOC2/HIPAA/PCI PDFs."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.interfaces.identity_provider import IdentityClaims
from src.interfaces.pdf_renderer import PdfRenderer
from src.middleware.rbac import require_viewer
from src.middleware.tenant_context import get_tenant_session
from src.models.audit_event import AuditEventRecord
from src.models.organization import Organization
from src.providers.factory import pdf_renderer
from src.services.compliance import Framework, collect_evidence, render_html


router = APIRouter(prefix="/compliance", tags=["compliance"])


@router.get("/frameworks", response_model=list[str])
async def list_frameworks(
    _: IdentityClaims = Depends(require_viewer),
) -> list[str]:
    return ["soc2", "hipaa", "pci"]


@router.get("/generate")
async def generate_pack(
    framework: Framework = Query(default="soc2"),
    hours: int = Query(default=24, ge=1, le=720),
    claims: IdentityClaims = Depends(require_viewer),
    session: AsyncSession = Depends(get_tenant_session),
    renderer: PdfRenderer = Depends(pdf_renderer),
) -> Response:
    org = (
        await session.execute(
            select(Organization).where(Organization.slug == claims.tenant_id)
        )
    ).scalar_one_or_none()
    if org is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Org not found")

    period_end = datetime.now(UTC)
    period_start = period_end - timedelta(hours=hours)

    result = await session.execute(
        select(AuditEventRecord)
        .where(AuditEventRecord.occurred_at >= period_start)
        .where(AuditEventRecord.occurred_at <= period_end)
        .order_by(AuditEventRecord.occurred_at)
    )
    events = []
    for ev in result.scalars().all():
        events.append({
            "occurred_at": ev.occurred_at.isoformat(),
            "actor_email": ev.actor_user_email,
            "actor_role": ev.actor_user_role,
            "action": ev.action,
            "outcome": ev.outcome,
            "resource_name": ev.resource_name,
            "resource_type": ev.resource_type,
            "event_hash": ev.event_hash,
            "prev_hash": ev.prev_hash,
        })

    pack = collect_evidence(
        framework=framework,
        org_slug=org.slug,
        org_name=org.name,
        period_start=period_start,
        period_end=period_end,
        events=events,
    )
    html = render_html(pack)
    pdf_bytes = await renderer.render(html)

    filename = f"{org.slug}-{framework}-{period_end.strftime('%Y%m%d')}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
