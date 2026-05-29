"""ShellForge PII scrubbing proxy — entry point."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI
from fastapi.responses import JSONResponse

from src.config import get_settings
from src.proxy import router as proxy_router
from src.scrubber import PiiScrubber, _get_scrubber


def _configure_logging() -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )


@asynccontextmanager
async def _lifespan(app: FastAPI) -> AsyncIterator[None]:
    _configure_logging()
    log = structlog.get_logger(__name__)
    settings = get_settings()
    log.info(
        "scrubber.startup",
        regime=settings.regime.value,
        stream_mode=settings.stream_mode,
        gliner_model=settings.gliner_model,
        async_audit=settings.async_audit_enabled,
    )
    # Warm up the scrubber (loads spaCy + GLiNER model on first call)
    try:
        scrubber = _get_scrubber()
        log.info("scrubber.warmup.done")
    except Exception as e:  # noqa: BLE001
        log.error("scrubber.warmup.failed", error=str(e))
    yield
    log.info("scrubber.shutdown")


app = FastAPI(
    title="ShellForge PII Scrubbing Proxy",
    version="0.1.0",
    description=(
        "Transparent reverse proxy that scrubs PII/PHI/PCD from LLM API calls "
        "before they leave the compliance boundary. Regime-aware: HIPAA (18 PHI categories), "
        "PCI-DSS (PAN, CVV, IBAN), SOC2."
    ),
    lifespan=_lifespan,
)

app.include_router(proxy_router)


@app.get("/health")
async def health() -> dict:
    settings = get_settings()
    return {"status": "ok", "regime": settings.regime.value}


@app.post("/scrub")
async def scrub_text(body: dict) -> dict:
    """Direct scrub endpoint for testing. POST {text: '...'}"""
    scrubber = _get_scrubber()
    text = body.get("text", "")
    result = scrubber.scrub(text)
    return {
        "scrubbed_text": result.scrubbed_text,
        "entities_found": result.entities_found,
        "duration_ms": round(result.scrub_duration_ms, 1),
        "regime": result.regime,
    }
