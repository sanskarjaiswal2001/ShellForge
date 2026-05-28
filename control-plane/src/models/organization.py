"""Organization (tenant)."""

from __future__ import annotations

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.db.base import Base, TimestampMixin, UuidPkMixin


class Organization(Base, UuidPkMixin, TimestampMixin):
    __tablename__ = "organizations"

    slug: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    default_policy_template: Mapped[str | None] = mapped_column(String(64), nullable=True)

    users: Mapped[list["User"]] = relationship(  # noqa: F821  forward ref
        "User", back_populates="organization", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Organization slug={self.slug}>"
