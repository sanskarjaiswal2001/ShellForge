"""Create non-superuser app role so RLS is enforced.

CRITICAL ROOT CAUSE: the Postgres Docker image creates POSTGRES_USER
(shellforge) as the BOOTSTRAP SUPERUSER. Superusers ALWAYS bypass RLS,
and Postgres refuses to let the bootstrap user drop its own superuser
status ("The bootstrap user must have the SUPERUSER attribute.").

Fix: create a separate `shellforge_app` LOGIN role (no SUPERUSER, no
BYPASSRLS), grant it the privileges it needs, and switch the runtime
DATABASE_URL to connect as `shellforge_app`.

  - `shellforge` stays as the migration/admin user (superuser).
  - `shellforge_app` is the runtime user — subject to RLS.
  - `shellforge_admin` (NOLOGIN, BYPASSRLS) remains the explicit-bypass
    role for cross-tenant code via `SET LOCAL ROLE shellforge_admin`.

Revision ID: 0005
Revises: 0004
Create Date: 2026-05-29
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op


revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


APP_PASSWORD = "shellforge_app"  # local-dev only; override via DATABASE_URL in prod


def upgrade() -> None:
    op.execute(
        f"""
        DO $$ BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'shellforge_app') THEN
                CREATE ROLE shellforge_app LOGIN NOSUPERUSER NOBYPASSRLS
                    PASSWORD '{APP_PASSWORD}';
            END IF;
        END $$;
        """
    )
    # Grant minimum-needed privileges on the public schema + existing tables.
    op.execute("GRANT USAGE ON SCHEMA public TO shellforge_app;")
    op.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO shellforge_app;")
    op.execute("GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO shellforge_app;")
    # Future tables created by shellforge automatically grant to shellforge_app.
    op.execute(
        "ALTER DEFAULT PRIVILEGES FOR ROLE shellforge IN SCHEMA public "
        "GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO shellforge_app;"
    )
    op.execute(
        "ALTER DEFAULT PRIVILEGES FOR ROLE shellforge IN SCHEMA public "
        "GRANT USAGE, SELECT ON SEQUENCES TO shellforge_app;"
    )
    # shellforge_app may explicitly SET ROLE shellforge_admin when it needs
    # to bypass RLS (e.g., for the seed script).
    op.execute("GRANT shellforge_admin TO shellforge_app;")


def downgrade() -> None:
    op.execute("REVOKE shellforge_admin FROM shellforge_app;")
    op.execute(
        "ALTER DEFAULT PRIVILEGES FOR ROLE shellforge IN SCHEMA public "
        "REVOKE USAGE, SELECT ON SEQUENCES FROM shellforge_app;"
    )
    op.execute(
        "ALTER DEFAULT PRIVILEGES FOR ROLE shellforge IN SCHEMA public "
        "REVOKE SELECT, INSERT, UPDATE, DELETE ON TABLES FROM shellforge_app;"
    )
    op.execute("REVOKE USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public FROM shellforge_app;")
    op.execute("REVOKE SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public FROM shellforge_app;")
    op.execute("REVOKE USAGE ON SCHEMA public FROM shellforge_app;")
    op.execute("DROP ROLE IF EXISTS shellforge_app;")
