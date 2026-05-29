"""Grant table privileges to shellforge_admin role.

Migrations 0001/0002 created the shellforge_admin BYPASSRLS role but did
not grant it table-level INSERT/UPDATE/DELETE/SELECT privileges. Tables
are owned by the `shellforge` login role; switching SESSION ROLE to
shellforge_admin loses the owner's implicit privileges.

This migration grants ALL privileges on every existing + future table to
shellforge_admin, plus USAGE on the schema.

Revision ID: 0003
Revises: 0002
Create Date: 2026-05-29
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op


revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # USAGE on schema
    op.execute("GRANT USAGE ON SCHEMA public TO shellforge_admin;")

    # Privileges on all existing tables + sequences
    op.execute("GRANT ALL ON ALL TABLES IN SCHEMA public TO shellforge_admin;")
    op.execute("GRANT ALL ON ALL SEQUENCES IN SCHEMA public TO shellforge_admin;")

    # Default privileges for future tables/sequences created by shellforge
    op.execute(
        "ALTER DEFAULT PRIVILEGES FOR ROLE shellforge IN SCHEMA public "
        "GRANT ALL ON TABLES TO shellforge_admin;"
    )
    op.execute(
        "ALTER DEFAULT PRIVILEGES FOR ROLE shellforge IN SCHEMA public "
        "GRANT ALL ON SEQUENCES TO shellforge_admin;"
    )


def downgrade() -> None:
    op.execute(
        "ALTER DEFAULT PRIVILEGES FOR ROLE shellforge IN SCHEMA public "
        "REVOKE ALL ON SEQUENCES FROM shellforge_admin;"
    )
    op.execute(
        "ALTER DEFAULT PRIVILEGES FOR ROLE shellforge IN SCHEMA public "
        "REVOKE ALL ON TABLES FROM shellforge_admin;"
    )
    op.execute("REVOKE ALL ON ALL SEQUENCES IN SCHEMA public FROM shellforge_admin;")
    op.execute("REVOKE ALL ON ALL TABLES IN SCHEMA public FROM shellforge_admin;")
    op.execute("REVOKE USAGE ON SCHEMA public FROM shellforge_admin;")
