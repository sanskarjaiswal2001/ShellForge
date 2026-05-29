"""Tenant providers table with RLS

Revision ID: 0006
Revises: 0005
Create Date: 2026-05-29
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "0006"
down_revision: str | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "tenant_providers",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "organization_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("name", sa.String(128), nullable=False, index=True),
        sa.Column("type", sa.String(64), nullable=False),
        sa.Column("credential_keys", sa.String(512), nullable=False, server_default=""),
        sa.Column("secret_prefix", sa.String(512), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("organization_id", "name", name="uq_tenant_providers_org_name"),
    )

    op.execute("ALTER TABLE tenant_providers ENABLE ROW LEVEL SECURITY;")
    op.execute("ALTER TABLE tenant_providers FORCE ROW LEVEL SECURITY;")
    op.execute(
        """
        CREATE POLICY tenant_providers_isolation ON tenant_providers
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
    op.execute("GRANT ALL ON TABLE tenant_providers TO shellforge_admin;")
    op.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE tenant_providers TO shellforge_app;")


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS tenant_providers_isolation ON tenant_providers;")
    op.execute("ALTER TABLE tenant_providers DISABLE ROW LEVEL SECURITY;")
    op.drop_table("tenant_providers")
