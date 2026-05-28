"""Provider factory — wire env-selected backends to protocol consumers.

The ONLY place in the codebase that imports concrete implementations.
Used by FastAPI's dependency-injection system to inject the configured
backend into request handlers.
"""

from __future__ import annotations

from functools import lru_cache

from src.config import Settings, get_settings
from src.interfaces import (
    AuditSink,
    ComputeProvider,
    IdentityProvider,
    PdfRenderer,
    SecretProvider,
)


# ─── Secrets ─────────────────────────────────────────────────────────────


@lru_cache(maxsize=1)
def secret_provider() -> SecretProvider:
    settings = get_settings()
    backend = settings.secret_backend

    if backend == "env":
        from src.providers.secrets.env_provider import EnvSecretProvider
        return EnvSecretProvider(prefix=settings.secret_path_prefix)

    if backend == "infisical":
        from src.providers.secrets.infisical_provider import InfisicalSecretProvider
        return InfisicalSecretProvider(settings)

    if backend == "vault":
        from src.providers.secrets.vault_provider import VaultSecretProvider
        return VaultSecretProvider(settings)

    if backend == "aws":
        from src.providers.secrets.aws_provider import AwsSecretProvider
        return AwsSecretProvider(settings)

    raise ValueError(f"Unknown SECRET_BACKEND: {backend}")


# ─── Identity ────────────────────────────────────────────────────────────


@lru_cache(maxsize=1)
def identity_provider() -> IdentityProvider:
    settings = get_settings()

    if settings.identity_backend == "oidc":
        from src.providers.identity.oidc_provider import OidcIdentityProvider
        return OidcIdentityProvider(
            issuer=settings.oidc_issuer,
            client_id=settings.oidc_client_id,
            client_secret=settings.oidc_client_secret,
            redirect_uri=settings.oidc_redirect_uri,
            jwks_cache_ttl=settings.oidc_jwks_cache_ttl_seconds,
        )

    raise ValueError(f"Unknown IDENTITY_BACKEND: {settings.identity_backend}")


# ─── Audit ───────────────────────────────────────────────────────────────


@lru_cache(maxsize=1)
def audit_sink() -> AuditSink:
    settings = get_settings()

    if settings.audit_backend == "otel":
        from src.providers.audit.otel_sink import OtelAuditSink
        return OtelAuditSink(
            endpoint=settings.otel_exporter_otlp_endpoint,
            protocol=settings.otel_exporter_otlp_protocol,
            service_name=settings.otel_service_name,
        )

    if settings.audit_backend == "stdout":
        from src.providers.audit.stdout_sink import StdoutAuditSink
        return StdoutAuditSink()

    raise ValueError(f"Unknown AUDIT_BACKEND: {settings.audit_backend}")


# ─── Compute (sandbox runtime) ──────────────────────────────────────────


@lru_cache(maxsize=1)
def compute_provider() -> ComputeProvider:
    settings = get_settings()

    if settings.compute_backend == "openshell":
        from src.providers.compute.openshell_provider import OpenShellComputeProvider
        return OpenShellComputeProvider(settings)

    if settings.compute_backend == "docker":
        # Future direct-Docker fallback. Not implemented in MVP.
        raise NotImplementedError("Direct Docker compute backend not yet implemented.")

    if settings.compute_backend == "k8s":
        raise NotImplementedError("k8s compute backend not yet implemented.")

    raise ValueError(f"Unknown COMPUTE_BACKEND: {settings.compute_backend}")


# ─── PDF renderer ───────────────────────────────────────────────────────


@lru_cache(maxsize=1)
def pdf_renderer() -> PdfRenderer:
    settings = get_settings()

    if settings.pdf_backend == "weasyprint":
        from src.providers.pdf.weasyprint_renderer import WeasyprintRenderer
        return WeasyprintRenderer()

    if settings.pdf_backend == "puppeteer":
        raise NotImplementedError("Puppeteer PDF backend not yet implemented.")

    raise ValueError(f"Unknown PDF_BACKEND: {settings.pdf_backend}")


def reset_cache() -> None:
    """For tests: clear the lru_cache so swapped env vars take effect."""
    secret_provider.cache_clear()
    identity_provider.cache_clear()
    audit_sink.cache_clear()
    compute_provider.cache_clear()
    pdf_renderer.cache_clear()
