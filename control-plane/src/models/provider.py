"""Tenant-scoped provider registry.

Tracks which providers (credential bundles) exist per tenant. Actual secret
values never stored in this DB — they live in Infisical. OpenShell holds the
injected copies. This table is the source-of-truth for what providers exist.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from src.db.base import Base, TimestampMixin, UuidPkMixin


# Known OpenShell provider types and their injected env vars.
PROVIDER_TYPES: dict[str, list[str]] = {
    "claude": ["ANTHROPIC_API_KEY", "CLAUDE_API_KEY"],
    "openai": ["OPENAI_API_KEY"],
    "github": ["GITHUB_TOKEN", "GH_TOKEN"],
    "gitlab": ["GITLAB_TOKEN", "GLAB_TOKEN"],
    "nvidia": ["NVIDIA_API_KEY"],
    "copilot": ["COPILOT_GITHUB_TOKEN", "GH_TOKEN"],
    "generic": [],  # user-defined variables
}


class TenantProvider(Base, UuidPkMixin, TimestampMixin):
    __tablename__ = "tenant_providers"

    organization_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    type: Mapped[str] = mapped_column(String(64), nullable=False)
    # Key names only (never values) — for display + Infisical path resolution.
    credential_keys: Mapped[str] = mapped_column(String(512), nullable=False, server_default="")
    # Infisical secret path prefix for this provider's credentials.
    secret_prefix: Mapped[str] = mapped_column(String(512), nullable=False)
