"""Pytest fixtures.

Tests against a real Postgres (docker-compose). We do NOT mock the DB
because RLS is the whole point — mocking would defeat the test.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.config import Settings, get_settings
from src.db.base import Base


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="session")
async def test_engine():
    """One engine per test session."""
    settings = get_settings()
    engine = create_async_engine(settings.database_url, pool_pre_ping=True)

    # Make sure the schema exists. We rely on `make migrate` to have run.
    async with engine.connect() as conn:
        await conn.execute(text("SELECT 1"))

    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def test_session(test_engine) -> AsyncIterator[AsyncSession]:
    """Per-test transaction that is rolled back at teardown — clean state."""
    factory = async_sessionmaker(test_engine, expire_on_commit=False)
    async with factory() as session:
        # Use admin role so test setup can insert across tenants.
        await session.execute(text("SET ROLE shellforge_admin"))
        yield session
        await session.rollback()


@pytest_asyncio.fixture
async def two_tenants(test_session: AsyncSession) -> tuple[dict, dict]:
    """Two ephemeral tenants with one user each. Returns (tenant_a, tenant_b)
    where each is {org, user}."""
    from src.models.organization import Organization
    from src.models.user import User

    a_slug = f"test-a-{uuid4().hex[:8]}"
    b_slug = f"test-b-{uuid4().hex[:8]}"

    org_a = Organization(slug=a_slug, name=f"Tenant A {a_slug}")
    org_b = Organization(slug=b_slug, name=f"Tenant B {b_slug}")
    test_session.add_all([org_a, org_b])
    await test_session.flush()

    user_a = User(
        organization_id=org_a.id,
        oidc_subject=f"a-{uuid4()}",
        email=f"a@{a_slug}.test",
        name="A",
        roles=["org:admin"],
    )
    user_b = User(
        organization_id=org_b.id,
        oidc_subject=f"b-{uuid4()}",
        email=f"b@{b_slug}.test",
        name="B",
        roles=["org:admin"],
    )
    test_session.add_all([user_a, user_b])
    await test_session.flush()

    return (
        {"org": org_a, "user": user_a, "slug": a_slug},
        {"org": org_b, "user": user_b, "slug": b_slug},
    )
