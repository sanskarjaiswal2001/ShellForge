"""Audit hash-chain integrity tests."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from src.audit.hashing import canonical_json, compute_event_hash
from src.interfaces.audit_sink import AuditActor, AuditEvent, AuditResource


def _make_event(prev_hash: str, action: str = "test.action") -> AuditEvent:
    return AuditEvent(
        event_uid=f"evt-{action}",
        occurred_at=datetime(2026, 1, 1, tzinfo=UTC),
        tenant_id="acme-health",
        class_uid=6003,
        activity_id=1,
        category_uid=6,
        actor=AuditActor(user_uid="u1", user_email="u1@test", user_role="org:admin"),
        action=action,
        resource=AuditResource(type="sandbox", uid="sb-1", name="sb"),
        outcome="SUCCESS",
        prev_hash=prev_hash,
        event_hash="",
        source="shellforge",
        details={},
    )


def test_canonical_json_excludes_event_hash() -> None:
    event = _make_event(prev_hash="0" * 64)
    payload = canonical_json(event)
    assert "event_hash" not in payload


def test_canonical_json_is_stable() -> None:
    e1 = _make_event(prev_hash="abc")
    e2 = _make_event(prev_hash="abc")
    assert canonical_json(e1) == canonical_json(e2)


def test_compute_event_hash_is_deterministic() -> None:
    e1 = _make_event(prev_hash="abc")
    e2 = _make_event(prev_hash="abc")
    assert compute_event_hash(e1) == compute_event_hash(e2)


def test_compute_event_hash_changes_with_prev() -> None:
    e1 = _make_event(prev_hash="aaa")
    e2 = _make_event(prev_hash="bbb")
    assert compute_event_hash(e1) != compute_event_hash(e2)


def test_compute_event_hash_changes_with_action() -> None:
    e1 = _make_event(prev_hash="aaa", action="x")
    e2 = _make_event(prev_hash="aaa", action="y")
    assert compute_event_hash(e1) != compute_event_hash(e2)


def test_compute_event_hash_length() -> None:
    h = compute_event_hash(_make_event(prev_hash="0" * 64))
    assert len(h) == 64
    assert all(c in "0123456789abcdef" for c in h)
