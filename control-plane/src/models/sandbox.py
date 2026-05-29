"""Sandbox model — control-plane record. Ground truth lives in OpenShell;
this row exists for tenant-scoped queries, audit, and human-readable name
resolution.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from src.db.base import Base, TimestampMixin, UuidPkMixin


class Sandbox(Base, UuidPkMixin, TimestampMixin):
    __tablename__ = "sandboxes"

    organization_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    created_by_user_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    name: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    compute_uid: Mapped[str] = mapped_column(String(255), nullable=False)
    agent: Mapped[str] = mapped_column(String(64), nullable=False)
    policy_template: Mapped[str] = mapped_column(String(64), nullable=False)
    phase: Mapped[str] = mapped_column(String(32), nullable=False)
    last_phase_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    labels: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default="{}")
