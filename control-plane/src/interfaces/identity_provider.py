"""Identity provider protocol.

Validates OIDC JWTs and returns the canonical claims ShellForge cares about.
Today there is only one implementation (OIDC via Dex), but the interface
exists so that a future federation layer can be slotted in without touching
business logic.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable


@dataclass(frozen=True, slots=True)
class IdentityClaims:
    """Canonical user identity claims, IdP-agnostic."""

    subject: str               # stable user ID (OIDC `sub`)
    email: str
    name: str
    tenant_id: str | None      # organization slug claim, e.g. "acme-health"
    roles: tuple[str, ...]     # platform roles, e.g. ("org:admin",)
    raw: dict[str, object]     # full token payload for debugging


@runtime_checkable
class IdentityProvider(Protocol):
    """OIDC validator + claims extractor."""

    async def validate_token(self, token: str) -> IdentityClaims:
        """Verify the JWT signature, audience, expiry; return canonical claims.

        Raises:
            InvalidTokenError: Signature invalid, expired, or audience mismatch.
        """
        ...

    async def authorization_url(self, state: str, nonce: str) -> str:
        """Build the IdP's authorization endpoint URL for a login redirect."""
        ...

    async def exchange_code(self, code: str) -> tuple[str, str]:
        """Exchange an OIDC auth code for (access_token, id_token)."""
        ...


class InvalidTokenError(Exception):
    """Token failed validation."""
