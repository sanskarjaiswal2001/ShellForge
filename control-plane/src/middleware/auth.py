"""OIDC bearer-token auth dependency.

Extracts the bearer JWT from Authorization header, validates via the
IdentityProvider, returns canonical claims. Stores claims on request.state
for downstream middleware (tenant context, audit emitter).
"""

from __future__ import annotations

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from src.interfaces.identity_provider import (
    IdentityClaims,
    IdentityProvider,
    InvalidTokenError,
)
from src.providers.factory import identity_provider


_bearer = HTTPBearer(auto_error=False)


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
