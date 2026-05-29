"""Sandboxes + policy versions tables with RLS

Revision ID: 0002
Revises: 0001
Create Date: 2026-05-29
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ─── sandboxes ──────────────────────────────────────────────────────
    op.create_table(
        "sandboxes",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "organization_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "created_by_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("name", sa.String(128), nullable=False, index=True),
        sa.Column("compute_uid", sa.String(255), nullable=False),
        sa.Column("agent", sa.String(64), nullable=False),
        sa.Column("policy_template", sa.String(64), nullable=False),
        sa.Column("phase", sa.String(32), nullable=False),
        sa.Column("last_phase_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("labels", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("organization_id", "name", name="uq_sandboxes_org_name"),
    )

    # ─── policy_versions ────────────────────────────────────────────────
    op.create_table(
        "policy_versions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "organization_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("name", sa.String(128), nullable=False, index=True),
        sa.Column("version", sa.Integer, nullable=False),
        sa.Column("template", sa.String(64), nullable=False),
        sa.Column("yaml_content", sa.Text, nullable=False),
        sa.Column("sha256", sa.String(64), nullable=False),
        sa.Column(
            "created_by_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("organization_id", "name", "version", name="uq_policy_versions_org_name_ver"),
    )

    # ─── RLS ────────────────────────────────────────────────────────────
    for tbl in ("sandboxes", "policy_versions"):
        op.execute(f"ALTER TABLE {tbl} ENABLE ROW LEVEL SECURITY;")
        op.execute(f"ALTER TABLE {tbl} FORCE ROW LEVEL SECURITY;")
        op.execute(
            f"""
            CREATE POLICY {tbl}_tenant_isolation ON {tbl}
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


def downgrade() -> None:
    for tbl in ("sandboxes", "policy_versions"):
        op.execute(f"DROP POLICY IF EXISTS {tbl}_tenant_isolation ON {tbl};")
        op.execute(f"ALTER TABLE {tbl} DISABLE ROW LEVEL SECURITY;")
    op.drop_table("policy_versions")
    op.drop_table("sandboxes")
