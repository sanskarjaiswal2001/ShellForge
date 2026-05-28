"""OIDC auth endpoints — login redirect, callback, me."""

from __future__ import annotations

import secrets

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import RedirectResponse
from pydantic import BaseModel

from src.interfaces.identity_provider import IdentityClaims, IdentityProvider
from src.middleware.auth import get_current_identity
from src.providers.factory import identity_provider

router = APIRouter(prefix="/auth", tags=["auth"])


class MeResponse(BaseModel):
    subject: str
    email: str
    name: str
    tenant_id: str | None
    roles: list[str]


@router.get("/login")
async def login(idp: IdentityProvider = Depends(identity_provider)) -> RedirectResponse:
    """Build OIDC authorization URL and redirect."""
    state = secrets.token_urlsafe(32)
    nonce = secrets.token_urlsafe(32)
    url = await idp.authorization_url(state=state, nonce=nonce)
    response = RedirectResponse(url=url)
    # In a real app: persist state + nonce in encrypted cookie for callback verification.
    response.set_cookie("oidc_state", state, httponly=True, samesite="lax", max_age=600)
    response.set_cookie("oidc_nonce", nonce, httponly=True, samesite="lax", max_age=600)
    return response


class TokenResponse(BaseModel):
    access_token: str
    id_token: str
    token_type: str = "Bearer"


@router.get("/callback", response_model=TokenResponse)
async def callback(
    code: str,
    state: str,
    idp: IdentityProvider = Depends(identity_provider),
) -> TokenResponse:
    """Exchange auth code for tokens. (Demo flow — does not verify cookie state here.)"""
    try:
        access_token, id_token = await idp.exchange_code(code)
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e
    return TokenResponse(access_token=access_token, id_token=id_token)


@router.get("/me", response_model=MeResponse)
async def me(claims: IdentityClaims = Depends(get_current_identity)) -> MeResponse:
    return MeResponse(
        subject=claims.subject,
        email=claims.email,
        name=claims.name,
        tenant_id=claims.tenant_id,
        roles=list(claims.roles),
    )
