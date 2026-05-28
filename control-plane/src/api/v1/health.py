"""Health endpoints."""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel
from sqlalchemy import text

from src.db.session import session_factory

router = APIRouter(tags=["health"])


class HealthResponse(BaseModel):
    status: str
    database: str


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    db_ok = "up"
    try:
        async with session_factory()() as session:
            await session.execute(text("SELECT 1"))
    except Exception as e:  # noqa: BLE001
        db_ok = f"down: {type(e).__name__}"
    return HealthResponse(status="ok", database=db_ok)


@router.get("/health/live")
async def live() -> dict[str, str]:
    return {"status": "alive"}


@router.get("/health/ready")
async def ready() -> dict[str, str]:
    async with session_factory()() as session:
        await session.execute(text("SELECT 1"))
    return {"status": "ready"}
