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
