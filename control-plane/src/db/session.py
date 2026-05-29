"""Async SQLAlchemy engine + session factory + tenant context setter."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.sql import text

from src.config import get_settings


_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def engine() -> AsyncEngine:
    global _engine
    if _engine is None:
        settings = get_settings()
        # asyncpg defaults to trying TLS; for local Podman deployments the
        # Postgres container has no TLS cert. Force ssl=False so the driver
        # doesn't try to upgrade. In cloud deployments, remove this or pass
        # ssl=True with the CA cert.
        _engine = create_async_engine(
            settings.database_url,
            pool_size=settings.database_pool_size,
            max_overflow=settings.database_max_overflow,
            pool_pre_ping=True,
            echo=False,
            connect_args={"ssl": False},
        )
    return _engine


def session_factory() -> async_sessionmaker[AsyncSession]:
    global _session_factory
    if _session_factory is None:
        _session_factory = async_sessionmaker(
            engine(), expire_on_commit=False, autoflush=False
        )
    return _session_factory


@asynccontextmanager
async def tenant_scoped_session(tenant_id: str | None) -> AsyncIterator[AsyncSession]:
    """Open a session within a transaction that has ``app.current_tenant_id``
    set to ``tenant_id`` via ``SET LOCAL``.

    SET LOCAL is TRANSACTION-scoped, NEVER session-scoped — using SET (without
    LOCAL) would leak tenant context between requests sharing a pooled
    connection. This is the #1 RLS footgun and the reason the tenant context
    middleware exists.

    If ``tenant_id`` is None (platform-admin requests, internal jobs), RLS
    policies that reference current_tenant_id will return zero rows — which
    is the correct fail-closed behavior.
    """
    async with session_factory()() as session:
        async with session.begin():
            if tenant_id is not None:
                # set_config(name, value, is_local) — parameterizable equivalent
                # of `SET LOCAL`. Required because Postgres does not accept
                # bind parameters in plain SET statements.
                await session.execute(
                    text("SELECT set_config('app.current_tenant_id', :tid, true)")
                    .bindparams(tid=tenant_id)
                )
            yield session
