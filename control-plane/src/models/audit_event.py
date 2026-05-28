"""Audit event row (also the hash-chain storage)."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from src.db.base import Base, TimestampMixin, UuidPkMixin


class AuditEventRecord(Base, UuidPkMixin, TimestampMixin):
    __tablename__ = "audit_events"

    organization_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )

    # OCSF classification
    class_uid: Mapped[int] = mapped_column(Integer, nullable=False)
    category_uid: Mapped[int] = mapped_column(Integer, nullable=False)
    activity_id: Mapped[int] = mapped_column(Integer, nullable=False)

    # Actor
    actor_user_uid: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    actor_user_email: Mapped[str] = mapped_column(String(320), nullable=False)
    actor_user_role: Mapped[str] = mapped_column(String(64), nullable=False)
    actor_session_uid: Mapped[str | None] = mapped_column(String(64), nullable=True)

    # Action
    action: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    outcome: Mapped[str] = mapped_column(String(16), nullable=False)

    # Resource
    resource_type: Mapped[str] = mapped_column(String(64), nullable=False)
    resource_uid: Mapped[str] = mapped_column(String(255), nullable=False)
    resource_name: Mapped[str] = mapped_column(String(255), nullable=False)
    resource_labels: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default="{}")

    # Hash chain
    prev_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    event_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)

    # Provenance + free-form
    source: Mapped[str] = mapped_column(String(32), nullable=False)
    details: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default="{}")
