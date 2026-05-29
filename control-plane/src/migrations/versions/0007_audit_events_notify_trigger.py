"""Postgres NOTIFY trigger on audit_events insert.

Fires pg_notify('audit_events_<org_id>', '<payload_json>') on every INSERT
into audit_events so the API server can push events to connected clients in
real time via asyncpg LISTEN, instead of polling every 2.5 seconds.

The channel name embeds the org_id so RLS isolation is preserved at the
notification layer — each tenant only receives their own events.

Revision ID: 0007
Revises: 0006
Create Date: 2026-05-29
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op


revision: str = "0007"
down_revision: str | None = "0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        CREATE OR REPLACE FUNCTION notify_audit_event()
        RETURNS trigger LANGUAGE plpgsql AS $$
        DECLARE
          channel TEXT;
          payload TEXT;
        BEGIN
          channel := 'audit_events_' || NEW.organization_id;
          payload := json_build_object(
            'id',             NEW.id,
            'occurred_at',    NEW.occurred_at,
            'action',         NEW.action,
            'outcome',        NEW.outcome,
            'actor_email',    NEW.actor_user_email,
            'actor_role',     NEW.actor_user_role,
            'resource_type',  NEW.resource_type,
            'resource_name',  NEW.resource_name,
            'event_hash',     NEW.event_hash,
            'prev_hash',      NEW.prev_hash,
            'source',         NEW.source,
            'class_uid',      NEW.class_uid
          )::TEXT;
          PERFORM pg_notify(channel, payload);
          RETURN NEW;
        END;
        $$;
        """
    )
    op.execute(
        """
        CREATE TRIGGER audit_events_after_insert
            AFTER INSERT ON audit_events
            FOR EACH ROW EXECUTE FUNCTION notify_audit_event();
        """
    )
    # Grant EXECUTE on the function to the runtime role.
    op.execute("GRANT EXECUTE ON FUNCTION notify_audit_event() TO shellforge_app;")


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS audit_events_after_insert ON audit_events;")
    op.execute("DROP FUNCTION IF EXISTS notify_audit_event();")
