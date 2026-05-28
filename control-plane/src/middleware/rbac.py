"""Role-based access control.

Roles (cumulative):
  - org:viewer     — read-only within own tenant
  - org:developer  — viewer + sandbox lifecycle within own tenant
  - org:admin      — developer + user mgmt, policy mgmt within own tenant
  - platform:admin — cross-tenant; bypasses RLS via shellforge_admin DB role

JWT role claim is a HINT. For destructive operations, the handler MUST
re-verify the role against the DB (User.roles column). JWTs can lag if the
user was demoted between issuance and use.
"""

from __future__ import annotations

from collections.abc import Callable
from enum import StrEnum

from fastapi import Depends, HTTPException, status

from src.interfaces.identity_provider import IdentityClaims
from src.middleware.auth import get_current_identity


class Role(StrEnum):
    ORG_VIEWER = "org:viewer"
    ORG_DEVELOPER = "org:developer"
    ORG_ADMIN = "org:admin"
    PLATFORM_ADMIN = "platform:admin"


_LEVEL: dict[Role, int] = {
    Role.ORG_VIEWER: 10,
    Role.ORG_DEVELOPER: 20,
    Role.ORG_ADMIN: 30,
    Role.PLATFORM_ADMIN: 100,
}


def require_role(minimum: Role) -> Callable[[IdentityClaims], IdentityClaims]:
    """FastAPI dependency factory: gate an endpoint behind a minimum role."""

    def _checker(claims: IdentityClaims = Depends(get_current_identity)) -> IdentityClaims:
        known_roles = {r.value for r in Role}
        user_levels = [_LEVEL[Role(r)] for r in claims.roles if r in known_roles]
        if not user_levels:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Endpoint requires role >= {minimum.value}",
            )
        if max(user_levels) < _LEVEL[minimum]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Endpoint requires role >= {minimum.value}, you have {claims.roles}",
            )
        return claims

    return _checker


require_viewer = require_role(Role.ORG_VIEWER)
require_developer = require_role(Role.ORG_DEVELOPER)
require_admin = require_role(Role.ORG_ADMIN)
require_platform_admin = require_role(Role.PLATFORM_ADMIN)
