"""OIDC bearer-token auth + DB user resolution.

Two auth paths:

1. Real OIDC (production + ENV=local with Dex configured):
   - Validate JWT signature/expiry/audience via JWKS
   - Look up User in DB by `sub` claim → get tenant_id + roles from DB
   - Roles from DB are authoritative; JWT roles are a hint for display only

2. Demo bypass (ENV=local only):
   - Token format: `demo:<subject>:<tenant_id>:<role>`
   - Skips OIDC validation; looks up real DB user by subject
   - Only works when ENV=local — never active in staging/production

This design means the JWT never carries authoritative tenant/role decisions
— the DB is the single source of truth. A compromised or crafted JWT with a
forged tenant_id claim has no effect on authorization.
"""

from __future__ import annotations

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from src.config import get_settings
from src.interfaces.identity_provider import (
    IdentityClaims,
    IdentityProvider,
    InvalidTokenError,
)
from src.providers.factory import identity_provider


_bearer = HTTPBearer(auto_error=False)

# Seeded demo subjects. Used only in ENV=local demo-bearer path.
_DEMO_USERS = {
    "08a8684b-db88-4b73-90a9-3cd1661f5466": ("alice@acme-health.demo", "Alice Chen"),
    "1aa7f8db-7ad9-4f0f-b3e6-c8a8c4f6d5d2": ("bob@acme-health.demo", "Bob Patel"),
    "2bb8e9ec-8be0-5a10-c4f7-d9b9d5g7e6e3": ("carol@bolt-bank.demo", "Carol Rodriguez"),
    "3cc9faff-9cf1-6b21-d5g8-e0c0e6h8f7f4": ("dave@nexus-corp.demo", "Dave Park"),
}


def _parse_demo_token(token: str) -> IdentityClaims | None:
    if not token.startswith("demo:"):
        return None
    parts = token.split(":", 3)
    if len(parts) != 4:
        return None
    _, subject, tenant_id, role = parts
    email, name = _DEMO_USERS.get(subject, (f"{subject}@unknown", subject))
    return IdentityClaims(
        subject=subject,
        email=email,
        name=name,
        tenant_id=tenant_id,
        roles=(role,),
        raw={"demo": True},
    )


async def _enrich_from_db(claims: IdentityClaims) -> IdentityClaims:
    """Look up the DB User record for this OIDC subject and overlay tenant_id
    + roles from the DB, which are authoritative over any JWT claims."""
    from sqlalchemy import select
    from src.db.session import session_factory
    from src.models.user import User
    from src.models.organization import Organization

    async with session_factory()() as session:
        # Must bypass RLS to look up any user by OIDC subject.
        from sqlalchemy import text
        await session.execute(text("SET LOCAL ROLE shellforge_admin"))
        result = await session.execute(
            select(User, Organization)
            .join(Organization, User.organization_id == Organization.id)
            .where(User.oidc_subject == claims.subject)
        )
        row = result.first()

    if row is None:
        # User not in DB yet; return claims with no tenant_id so
        # tenant-scoped endpoints return 403 (not 500).
        return claims

    user, org = row
    return IdentityClaims(
        subject=claims.subject,
        email=user.email or claims.email,
        name=user.name or claims.name,
        tenant_id=org.slug,
        roles=tuple(user.roles),
        raw=claims.raw,
    )


async def get_current_identity(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    idp: IdentityProvider = Depends(identity_provider),
) -> IdentityClaims:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Bearer token required",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Demo-mode bypass (ENV=local only).
    if get_settings().is_local:
        demo = _parse_demo_token(credentials.credentials)
        if demo is not None:
            request.state.identity = demo
            return demo

    # Real OIDC path.
    try:
        jwt_claims = await idp.validate_token(credentials.credentials)
    except InvalidTokenError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid token: {e}",
            headers={"WWW-Authenticate": "Bearer"},
        ) from e

    # Enrich from DB — tenant + roles from DB override JWT claims.
    claims = await _enrich_from_db(jwt_claims)
    request.state.identity = claims
    return claims
