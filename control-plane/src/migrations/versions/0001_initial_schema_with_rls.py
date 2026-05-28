"""Initial schema with RLS

Creates:
  - organizations, users, audit_events tables
  - Row-Level Security policies tied to ``current_setting('app.current_tenant_id')``
  - Composite indexes with organization_id (or tenant slug) as leading column

Revision ID: 0001
Revises:
Create Date: 2026-05-29
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ─── organizations ──────────────────────────────────────────────────
    op.create_table(
        "organizations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("slug", sa.String(64), nullable=False, unique=True, index=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("default_policy_template", sa.String(64), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )

    # ─── users ──────────────────────────────────────────────────────────
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "organization_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("oidc_subject", sa.String(255), nullable=False, unique=True, index=True),
        sa.Column("email", sa.String(320), nullable=False, index=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column(
            "roles",
            postgresql.ARRAY(sa.String),
            nullable=False,
            server_default="{}",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    # Composite index: tenant_id leading column for efficient tenant-scoped queries.
    op.create_index("ix_users_org_email", "users", ["organization_id", "email"])

    # ─── audit_events ───────────────────────────────────────────────────
    op.create_table(
        "audit_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "organization_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False, index=True),
        sa.Column("class_uid", sa.Integer, nullable=False),
        sa.Column("category_uid", sa.Integer, nullable=False),
        sa.Column("activity_id", sa.Integer, nullable=False),
        sa.Column("actor_user_uid", sa.String(255), nullable=False, index=True),
        sa.Column("actor_user_email", sa.String(320), nullable=False),
        sa.Column("actor_user_role", sa.String(64), nullable=False),
        sa.Column("actor_session_uid", sa.String(64), nullable=True),
        sa.Column("action", sa.String(64), nullable=False, index=True),
        sa.Column("outcome", sa.String(16), nullable=False),
        sa.Column("resource_type", sa.String(64), nullable=False),
        sa.Column("resource_uid", sa.String(255), nullable=False),
        sa.Column("resource_name", sa.String(255), nullable=False),
        sa.Column("resource_labels", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column("prev_hash", sa.String(64), nullable=False),
        sa.Column("event_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("source", sa.String(32), nullable=False),
        sa.Column("details", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    # Composite index: tenant_id leading column + time descending for audit feed.
    op.create_index(
        "ix_audit_events_org_time",
        "audit_events",
        ["organization_id", sa.text("occurred_at DESC")],
    )

    # ─── Row-Level Security ─────────────────────────────────────────────
    # All RLS policies key off the SET LOCAL `app.current_tenant_id`
    # set by the FastAPI tenant_context middleware.
    #
    # Policies match the org slug, NOT the UUID, so seeders / tests can use
    # human-readable identifiers. Subqueries join to organizations.slug.

    op.execute("ALTER TABLE users ENABLE ROW LEVEL SECURITY;")
    op.execute("ALTER TABLE users FORCE ROW LEVEL SECURITY;")
    op.execute(
        """
        CREATE POLICY users_tenant_isolation ON users
            USING (
                organization_id = (
                    SELECT id FROM organizations
                    WHERE slug = current_setting('app.current_tenant_id', TRUE)
                )
            )
            WITH CHECK (
                organization_id = (
                    SELECT id FROM organizations
                    WHERE slug = current_setting('app.current_tenant_id', TRUE)
                )
            );
        """
    )

    op.execute("ALTER TABLE audit_events ENABLE ROW LEVEL SECURITY;")
    op.execute("ALTER TABLE audit_events FORCE ROW LEVEL SECURITY;")
    op.execute(
        """
        CREATE POLICY audit_events_tenant_isolation ON audit_events
            USING (
                organization_id = (
                    SELECT id FROM organizations
                    WHERE slug = current_setting('app.current_tenant_id', TRUE)
                )
            )
            WITH CHECK (
                organization_id = (
                    SELECT id FROM organizations
                    WHERE slug = current_setting('app.current_tenant_id', TRUE)
                )
            );
        """
    )

    # ─── Platform-admin bypass role ─────────────────────────────────────
    # The control plane normally connects as `shellforge`. For platform-admin
    # operations (cross-tenant queries, seed data loading), we use a separate
    # role with BYPASSRLS. Seed script switches role via SET ROLE.
    op.execute(
        """
        DO $$ BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'shellforge_admin') THEN
                CREATE ROLE shellforge_admin BYPASSRLS NOLOGIN;
                GRANT shellforge_admin TO shellforge;
            END IF;
        END $$;
        """
    )


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS audit_events_tenant_isolation ON audit_events;")
    op.execute("DROP POLICY IF EXISTS users_tenant_isolation ON users;")
    op.execute("ALTER TABLE audit_events DISABLE ROW LEVEL SECURITY;")
    op.execute("ALTER TABLE users DISABLE ROW LEVEL SECURITY;")

    op.drop_index("ix_audit_events_org_time", table_name="audit_events")
    op.drop_table("audit_events")
    op.drop_index("ix_users_org_email", table_name="users")
    op.drop_table("users")
    op.drop_table("organizations")

    op.execute("DROP ROLE IF EXISTS shellforge_admin;")
