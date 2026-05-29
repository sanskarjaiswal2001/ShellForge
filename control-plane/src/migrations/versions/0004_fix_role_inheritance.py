"""Make shellforge NOINHERIT so RLS is enforced by default.

CRITICAL: in migration 0001 we did `GRANT shellforge_admin TO shellforge`.
Postgres default behavior is INHERIT, which means `shellforge` automatically
gains `BYPASSRLS` from `shellforge_admin` membership — defeating RLS entirely.

This migration sets `ALTER ROLE shellforge NOINHERIT`, so:
  - Default connections as `shellforge` are subject to RLS (correct).
  - Cross-tenant code must explicitly `SET LOCAL ROLE shellforge_admin`
    inside a transaction (existing seed + platform-admin code does this).

Revision ID: 0004
Revises: 0003
Create Date: 2026-05-29
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op


revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("ALTER ROLE shellforge NOINHERIT;")


def downgrade() -> None:
    op.execute("ALTER ROLE shellforge INHERIT;")
