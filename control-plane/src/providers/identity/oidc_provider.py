"""OIDC identity provider.

Validates JWTs against the upstream OIDC issuer's JWKS, extracts canonical
claims. Compatible with any RFC-6749/8693 OIDC IdP — Dex (local), Okta,
Azure AD, Google Workspace, Keycloak, etc.

Custom claims contract (set in Dex / IdP):
    sub           — stable user ID
    email         — user email
    name          — display name
    tenant_id     — ShellForge org slug (e.g. "acme-health")
    roles         — list[str] of platform roles
"""

from __future__ import annotations

import time

import httpx
from authlib.jose import JsonWebKey, JsonWebToken, JoseError
from authlib.oidc.discovery import get_well_known_url

from src.interfaces.identity_provider import (
    IdentityClaims,
    IdentityProvider,
    InvalidTokenError,
)


class OidcIdentityProvider(IdentityProvider):
    def __init__(
        self,
        issuer: str,
        client_id: str,
        client_secret: str,
        redirect_uri: str,
        jwks_cache_ttl: int = 3600,
    ) -> None:
        self._issuer = issuer.rstrip("/")
        self._client_id = client_id
        self._client_secret = client_secret
        self._redirect_uri = redirect_uri
        self._jwks_cache_ttl = jwks_cache_ttl

        self._jwks: JsonWebKey | None = None
        self._jwks_fetched_at: float = 0.0
        self._oidc_config: dict[str, object] | None = None
        self._jwt = JsonWebToken(["RS256", "ES256"])

    async def _load_oidc_config(self) -> dict[str, object]:
        if self._oidc_config is not None:
            return self._oidc_config

        well_known = get_well_known_url(self._issuer, external=True)
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(well_known)
            resp.raise_for_status()
            self._oidc_config = resp.json()
        return self._oidc_config

    async def _load_jwks(self) -> JsonWebKey:
        if (
            self._jwks is not None
            and (time.time() - self._jwks_fetched_at) < self._jwks_cache_ttl
        ):
            return self._jwks

        cfg = await self._load_oidc_config()
        jwks_uri = cfg["jwks_uri"]
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(str(jwks_uri))
            resp.raise_for_status()
            self._jwks = JsonWebKey.import_key_set(resp.json())
            self._jwks_fetched_at = time.time()
        return self._jwks

    async def validate_token(self, token: str) -> IdentityClaims:
        try:
            jwks = await self._load_jwks()
            claims = self._jwt.decode(token, key=jwks)
            claims.validate(now=int(time.time()), leeway=30)
        except JoseError as e:
            raise InvalidTokenError(f"Token validation failed: {e}") from e

        sub = str(claims.get("sub", ""))
        if not sub:
            raise InvalidTokenError("Token missing 'sub' claim")

        # tenant_id may be missing on the very first login (before user is
        # associated with an org). Caller must handle None.
        tenant_id = claims.get("tenant_id")

        roles_raw = claims.get("roles") or claims.get("groups") or []
        roles = tuple(str(r) for r in roles_raw) if isinstance(roles_raw, list) else ()

        return IdentityClaims(
            subject=sub,
            email=str(claims.get("email", "")),
            name=str(claims.get("name", claims.get("preferred_username", ""))),
            tenant_id=str(tenant_id) if tenant_id else None,
            roles=roles,
            raw=dict(claims),
        )

    async def authorization_url(self, state: str, nonce: str) -> str:
        cfg = await self._load_oidc_config()
        endpoint = str(cfg["authorization_endpoint"])
        from urllib.parse import urlencode

        params = {
            "response_type": "code",
            "client_id": self._client_id,
            "redirect_uri": self._redirect_uri,
            "scope": "openid email profile groups",
            "state": state,
            "nonce": nonce,
        }
        return f"{endpoint}?{urlencode(params)}"

    async def exchange_code(self, code: str) -> tuple[str, str]:
        cfg = await self._load_oidc_config()
        token_endpoint = str(cfg["token_endpoint"])

        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(
                token_endpoint,
                data={
                    "grant_type": "authorization_code",
                    "code": code,
                    "redirect_uri": self._redirect_uri,
                    "client_id": self._client_id,
                    "client_secret": self._client_secret,
                },
            )
            resp.raise_for_status()
            payload = resp.json()

        access_token = payload.get("access_token", "")
        id_token = payload.get("id_token", "")
        if not access_token or not id_token:
            raise InvalidTokenError("Token endpoint returned incomplete response")

        return access_token, id_token
