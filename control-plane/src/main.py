"""ShellForge control-plane entry point."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src import __version__
from src.api.v1 import router as v1_router
from src.config import get_settings


def _configure_logging() -> None:
    settings = get_settings()
    level = getattr(logging, settings.log_level.upper(), logging.INFO)
    logging.basicConfig(level=level, format="%(message)s")

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(level),
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )


async def _hydrate_compute_from_db() -> None:
    """On startup, register every DB sandbox with the compute provider.

    Mock provider is in-memory and loses state across restarts; without
    re-registering, existing sandboxes 404 from the compute view and the
    UI shows them stuck in PROVISIONING. No-op for real OpenShell (the
    gateway already owns state)."""
    from sqlalchemy import select, text
    from src.db.session import session_factory
    from src.models.organization import Organization
    from src.models.sandbox import Sandbox
    from src.providers.factory import compute_provider

    compute = compute_provider()
    if not hasattr(compute, "adopt_existing"):
        return

    log = structlog.get_logger(__name__)
    async with session_factory()() as session:
        async with session.begin():
            await session.execute(text("SET LOCAL ROLE shellforge_admin"))
            result = await session.execute(
                select(Sandbox, Organization).join(
                    Organization, Sandbox.organization_id == Organization.id
                )
            )
            count = 0
            for sandbox, org in result.all():
                await compute.adopt_existing(
                    tenant_id=org.slug,
                    name=sandbox.name,
                    uid=sandbox.compute_uid,
                    agent=sandbox.agent,
                    labels=dict(sandbox.labels) if sandbox.labels else {},
                )
                # Force phase to READY for adopted sandboxes — they
                # were created in some previous run and we have no way
                # to replay the lifecycle.
                if sandbox.phase != "READY":
                    sandbox.phase = "READY"
                count += 1
            log.info("shellforge.hydrate", adopted=count)


@asynccontextmanager
async def _lifespan(app: FastAPI) -> AsyncIterator[None]:  # noqa: ARG001
    _configure_logging()
    log = structlog.get_logger(__name__)
    settings = get_settings()
    log.info(
        "shellforge.startup",
        version=__version__,
        env=settings.env,
        secret_backend=settings.secret_backend,
        audit_backend=settings.audit_backend,
        compute_backend=settings.compute_backend,
    )
    try:
        await _hydrate_compute_from_db()
    except Exception as e:  # noqa: BLE001
        log.warning("shellforge.hydrate.failed", error=str(e))
    yield
    log.info("shellforge.shutdown")


def create_app() -> FastAPI:
    app = FastAPI(
        title="ShellForge Control Plane",
        version=__version__,
        description=(
            "Enterprise control plane for NVIDIA OpenShell — multi-tenant, "
            "SSO-enabled, audit-ready."
        ),
        lifespan=_lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:3000"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(v1_router)
    return app


app = create_app()
