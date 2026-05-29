"""OIDC bearer-token auth dependency.

Extracts the bearer JWT from Authorization header, validates via the
IdentityProvider, returns canonical claims. Stores claims on request.state
for downstream middleware (tenant context, audit emitter).

Demo-mode bypass (ENV=local only): accepts tokens of the form
    demo:<subject>:<tenant_id>:<role>
which skip OIDC validation and synthesize claims directly. Used by the
demo dashboard so judging-day works even if Dex is unreachable.
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


def _parse_demo_token(token: str) -> IdentityClaims | None:
    """Returns claims if this is a demo token; None otherwise."""
    if not token.startswith("demo:"):
        return None
    parts = token.split(":", 3)
    if len(parts) != 4:
        return None
    _, subject, tenant_id, role = parts
    # Lookup email from seed data.
    known = {
        "08a8684b-db88-4b73-90a9-3cd1661f5466": ("alice@acme-health.demo", "Alice Chen"),
        "1aa7f8db-7ad9-4f0f-b3e6-c8a8c4f6d5d2": ("bob@acme-health.demo", "Bob Patel"),
        "2bb8e9ec-8be0-5a10-c4f7-d9b9d5g7e6e3": ("carol@bolt-bank.demo", "Carol Rodriguez"),
        "3cc9faff-9cf1-6b21-d5g8-e0c0e6h8f7f4": ("dave@nexus-corp.demo", "Dave Park"),
    }
    email, name = known.get(subject, (f"{subject}@unknown", subject))
    return IdentityClaims(
        subject=subject,
        email=email,
        name=name,
        tenant_id=tenant_id,
        roles=(role,),
        raw={"demo": True},
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

    # Demo-mode bypass.
    if get_settings().is_local:
        demo = _parse_demo_token(credentials.credentials)
        if demo is not None:
            request.state.identity = demo
            return demo

    try:
        claims = await idp.validate_token(credentials.credentials)
    except InvalidTokenError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid token: {e}",
            headers={"WWW-Authenticate": "Bearer"},
        ) from e

    # Stash claims on request state so tenant middleware + audit emitter
    # can find them without re-validating.
    request.state.identity = claims
    return claims
