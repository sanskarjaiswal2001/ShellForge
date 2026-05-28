"""Seed demo data: 3 orgs, 5 users, 6 historical audit events, 3 policy violations.

Uses shellforge_admin DB role to bypass RLS while inserting cross-tenant data.

Idempotent: re-running with --force wipes and reloads. Without --force,
existing data is preserved (used for `make demo`).
"""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime, timedelta

import click
import structlog
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.audit.hashing import compute_event_hash
from src.config import get_settings
from src.db.session import session_factory
from src.interfaces.audit_sink import AuditActor, AuditEvent, AuditResource
from src.models.audit_event import AuditEventRecord
from src.models.organization import Organization
from src.models.user import User


log = structlog.get_logger(__name__)


# ─── Demo data definitions ──────────────────────────────────────────────────

DEMO_ORGS = [
    {
        "slug": "acme-health",
        "name": "Acme Health Systems",
        "default_policy_template": "hipaa-healthcare",
        "users": [
            {
                "oidc_subject": "08a8684b-db88-4b73-90a9-3cd1661f5466",
                "email": "alice@acme-health.demo",
                "name": "Alice Chen",
                "roles": ["org:admin"],
            },
            {
                "oidc_subject": "1aa7f8db-7ad9-4f0f-b3e6-c8a8c4f6d5d2",
                "email": "bob@acme-health.demo",
                "name": "Bob Patel",
                "roles": ["org:developer"],
            },
        ],
    },
    {
        "slug": "bolt-bank",
        "name": "Bolt Bank",
        "default_policy_template": "pci-payments",
        "users": [
            {
                "oidc_subject": "2bb8e9ec-8be0-5a10-c4f7-d9b9d5g7e6e3",
                "email": "carol@bolt-bank.demo",
                "name": "Carol Rodriguez",
                "roles": ["org:admin"],
            },
        ],
    },
    {
        "slug": "nexus-corp",
        "name": "Nexus Corp",
        "default_policy_template": "soc2-saas",
        "users": [
            {
                "oidc_subject": "3cc9faff-9cf1-6b21-d5g8-e0c0e6h8f7f4",
                "email": "dave@nexus-corp.demo",
                "name": "Dave Park",
                "roles": ["org:admin"],
            },
        ],
    },
]


# ─── Seed routines ──────────────────────────────────────────────────────────


async def _switch_to_admin(session: AsyncSession) -> None:
    """Use the BYPASSRLS role for cross-tenant seed writes."""
    await session.execute(text("SET LOCAL ROLE shellforge_admin"))


async def _wipe(session: AsyncSession) -> None:
    await _switch_to_admin(session)
    await session.execute(text("TRUNCATE audit_events, users, organizations CASCADE"))
    log.info("seed.wiped")


async def _seed_orgs_and_users(session: AsyncSession) -> dict[str, Organization]:
    await _switch_to_admin(session)
    orgs: dict[str, Organization] = {}
    for org_def in DEMO_ORGS:
        org = Organization(
            slug=org_def["slug"],
            name=org_def["name"],
            default_policy_template=org_def["default_policy_template"],
        )
        session.add(org)
        await session.flush()
        orgs[org.slug] = org

        for user_def in org_def["users"]:
            user = User(
                organization_id=org.id,
                oidc_subject=user_def["oidc_subject"],
                email=user_def["email"],
                name=user_def["name"],
                roles=user_def["roles"],
            )
            session.add(user)
        await session.flush()
        log.info("seed.org", slug=org.slug, user_count=len(org_def["users"]))
    return orgs


async def _seed_audit_events(session: AsyncSession, orgs: dict[str, Organization]) -> None:
    """Emit a few historical audit events per tenant for the demo dashboard."""
    await _switch_to_admin(session)
    genesis = get_settings().audit_genesis_hash

    now = datetime.now(UTC)

    # Per-tenant event log: rolling prev_hash so chain is correct.
    for org_slug, org in orgs.items():
        prev_hash = genesis
        users = [u for u in await _list_users_for_org(session, org.id)]
        admin = users[0]

        # Events to generate per tenant.
        scripted = [
            ("sandbox.created", "SUCCESS", "sandbox", "demo-sandbox-1", 6003, 6, 1, now - timedelta(hours=23)),
            ("policy.applied", "SUCCESS", "policy", org.default_policy_template or "baseline", 6003, 6, 2, now - timedelta(hours=22, minutes=30)),
            ("provider.attached", "SUCCESS", "provider", f"claude-{org_slug}", 6003, 6, 1, now - timedelta(hours=22)),
            ("network.denied", "BLOCKED", "endpoint", "evil-exfil.io:443", 4002, 4, 6, now - timedelta(hours=5)),
            ("network.denied", "BLOCKED", "endpoint", "data-leak.io:443", 4002, 4, 6, now - timedelta(hours=3)),
            ("sandbox.accessed", "SUCCESS", "sandbox", "demo-sandbox-1", 4007, 4, 1, now - timedelta(hours=1)),
        ]

        for action, outcome, rtype, rname, class_uid, cat_uid, act_id, occurred_at in scripted:
            event = AuditEvent(
                event_uid=f"{org_slug}-{action}-{occurred_at.timestamp()}",
                occurred_at=occurred_at,
                tenant_id=org_slug,
                class_uid=class_uid,
                category_uid=cat_uid,
                activity_id=act_id,
                actor=AuditActor(
                    user_uid=admin.oidc_subject,
                    user_email=admin.email,
                    user_role="org:admin",
                ),
                action=action,
                resource=AuditResource(
                    type=rtype,
                    uid=f"{org_slug}/{rname}",
                    name=rname,
                    labels={"shellforge.io/tenant": org_slug},
                ),
                outcome=outcome,
                prev_hash=prev_hash,
                event_hash="",
                source="shellforge",
            )
            event_hash = compute_event_hash(event)

            session.add(
                AuditEventRecord(
                    organization_id=org.id,
                    occurred_at=event.occurred_at,
                    class_uid=event.class_uid,
                    category_uid=event.category_uid,
                    activity_id=event.activity_id,
                    actor_user_uid=event.actor.user_uid,
                    actor_user_email=event.actor.user_email,
                    actor_user_role=event.actor.user_role,
                    action=event.action,
                    outcome=event.outcome,
                    resource_type=event.resource.type,
                    resource_uid=event.resource.uid,
                    resource_name=event.resource.name,
                    resource_labels=event.resource.labels,
                    prev_hash=event.prev_hash,
                    event_hash=event_hash,
                    source=event.source,
                    details={},
                )
            )
            prev_hash = event_hash

        await session.flush()
        log.info("seed.events", org=org_slug, count=len(scripted))


async def _list_users_for_org(session: AsyncSession, org_id) -> list[User]:
    from sqlalchemy import select
    result = await session.execute(select(User).where(User.organization_id == org_id))
    return list(result.scalars().all())


# ─── Entry ──────────────────────────────────────────────────────────────────


async def _run(force: bool) -> None:
    async with session_factory()() as session:
        async with session.begin():
            if force:
                await _wipe(session)
            orgs = await _seed_orgs_and_users(session)
            await _seed_audit_events(session, orgs)

    log.info("seed.done", orgs=len(DEMO_ORGS))


@click.command()
@click.option("--force", is_flag=True, help="Wipe existing data before seeding")
def main(force: bool) -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    structlog.configure(
        processors=[
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.dev.ConsoleRenderer(),
        ],
    )
    asyncio.run(_run(force=force or get_settings().seed_force))


if __name__ == "__main__":
    main()
