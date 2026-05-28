"""RBAC role-level tests."""

from __future__ import annotations

import pytest
from fastapi import HTTPException

from src.interfaces.identity_provider import IdentityClaims
from src.middleware.rbac import Role, require_role


def _claims(roles: tuple[str, ...]) -> IdentityClaims:
    return IdentityClaims(
        subject="u1",
        email="u1@test",
        name="u1",
        tenant_id="acme-health",
        roles=roles,
        raw={},
    )


def test_admin_can_access_developer_endpoint() -> None:
    checker = require_role(Role.ORG_DEVELOPER)
    claims = _claims(roles=("org:admin",))
    assert checker(claims) is claims


def test_viewer_cannot_access_admin_endpoint() -> None:
    checker = require_role(Role.ORG_ADMIN)
    claims = _claims(roles=("org:viewer",))
    with pytest.raises(HTTPException) as ex:
        checker(claims)
    assert ex.value.status_code == 403


def test_no_roles_denied() -> None:
    checker = require_role(Role.ORG_VIEWER)
    claims = _claims(roles=())
    with pytest.raises(HTTPException) as ex:
        checker(claims)
    assert ex.value.status_code == 403


def test_unknown_roles_ignored() -> None:
    """Unknown role claims must not grant access."""
    checker = require_role(Role.ORG_DEVELOPER)
    claims = _claims(roles=("admin", "superuser"))   # not in Role enum
    with pytest.raises(HTTPException) as ex:
        checker(claims)
    assert ex.value.status_code == 403


def test_platform_admin_can_access_anything() -> None:
    checker = require_role(Role.ORG_ADMIN)
    claims = _claims(roles=("platform:admin",))
    assert checker(claims) is claims
