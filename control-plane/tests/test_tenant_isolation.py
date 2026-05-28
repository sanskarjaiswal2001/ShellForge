"""Tenant isolation: the sacred invariant.

These tests verify that with the Postgres RLS policies in place, a session
that has SET LOCAL app.current_tenant_id = 'tenant_a' CANNOT see any row
belonging to tenant_b — even with an explicit SELECT * FROM users.

If any of these tests fail, ShellForge is broken at the security layer.
The fix is in the migration / middleware, not the test.
"""

from __future__ import annotations

import pytest
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.audit_event import AuditEventRecord
from src.models.user import User


@pytest.mark.asyncio
async def test_user_query_returns_only_own_tenant(
    test_session: AsyncSession, two_tenants
) -> None:
    a, b = two_tenants

    # Step out of admin role; activate tenant A context.
    await test_session.execute(text("RESET ROLE"))
    await test_session.execute(
        text("SET LOCAL app.current_tenant_id = :t").bindparams(t=a["slug"])
    )

    result = await test_session.execute(select(User))
    visible = result.scalars().all()

    visible_emails = {u.email for u in visible}
    assert a["user"].email in visible_emails, "Own-tenant user must be visible"
    assert b["user"].email not in visible_emails, (
        "CROSS-TENANT LEAK: tenant A query returned tenant B user"
    )


@pytest.mark.asyncio
async def test_user_query_with_no_tenant_context_returns_nothing(
    test_session: AsyncSession, two_tenants
) -> None:
    """Without app.current_tenant_id set, RLS must fail-closed (zero rows)."""
    await test_session.execute(text("RESET ROLE"))
    # Explicitly clear the setting so it's NULL.
    await test_session.execute(text("RESET app.current_tenant_id"))

    result = await test_session.execute(select(User))
    visible = result.scalars().all()

    assert visible == [], "Fail-closed broken: no tenant context returned rows"


@pytest.mark.asyncio
async def test_cannot_insert_user_into_other_tenant(
    test_session: AsyncSession, two_tenants
) -> None:
    """Even if app code tries to insert a User with another tenant's
    organization_id, RLS WITH CHECK should reject it."""
    from sqlalchemy.exc import DBAPIError

    a, b = two_tenants
    await test_session.execute(text("RESET ROLE"))
    await test_session.execute(
        text("SET LOCAL app.current_tenant_id = :t").bindparams(t=a["slug"])
    )

    rogue = User(
        organization_id=b["org"].id,                # tenant B's UUID
        oidc_subject="rogue",
        email="rogue@evil.com",
        name="rogue",
        roles=[],
    )
    test_session.add(rogue)
    with pytest.raises(DBAPIError):
        await test_session.flush()


@pytest.mark.asyncio
async def test_audit_event_isolation(
    test_session: AsyncSession, two_tenants
) -> None:
    """Cross-tenant audit events: same rule, RLS-enforced."""
    from datetime import UTC, datetime
    a, b = two_tenants

    # Insert one event per tenant using admin role.
    for tenant in (a, b):
        test_session.add(
            AuditEventRecord(
                organization_id=tenant["org"].id,
                occurred_at=datetime.now(UTC),
                class_uid=6003,
                category_uid=6,
                activity_id=1,
                actor_user_uid="test",
                actor_user_email="test@test",
                actor_user_role="org:admin",
                action="test.event",
                outcome="SUCCESS",
                resource_type="test",
                resource_uid="test/1",
                resource_name="test1",
                resource_labels={},
                prev_hash="0" * 64,
                event_hash=f"{tenant['slug'][:4]}{'a' * 60}",   # unique per tenant
                source="shellforge",
                details={},
            )
        )
    await test_session.flush()

    # Switch to tenant A's RLS context.
    await test_session.execute(text("RESET ROLE"))
    await test_session.execute(
        text("SET LOCAL app.current_tenant_id = :t").bindparams(t=a["slug"])
    )

    result = await test_session.execute(select(AuditEventRecord))
    events = result.scalars().all()

    assert len(events) >= 1
    assert all(e.organization_id == a["org"].id for e in events), (
        "Tenant A saw tenant B audit events — isolation broken"
    )
