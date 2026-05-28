"""Centralized configuration via pydantic-settings.

Every swappable backend is selected here via an enum field.
Adding a new backend = adding a literal + a factory entry in providers.factory.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


SecretBackend = Literal["infisical", "vault", "aws", "env"]
AuditBackend = Literal["otel", "stdout"]
ComputeBackend = Literal["openshell", "docker", "k8s"]
PdfBackend = Literal["weasyprint", "puppeteer"]
IdentityBackend = Literal["oidc"]


class Settings(BaseSettings):
    """Application settings, loaded from env vars."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Runtime ─────────────────────────────────────────────────────────
    env: str = "local"
    log_level: str = "INFO"
    control_plane_port: int = 8000

    # ── Database ────────────────────────────────────────────────────────
    database_url: str = "postgresql+asyncpg://shellforge:shellforge@localhost:5432/shellforge"
    database_pool_size: int = 20
    database_max_overflow: int = 10

    # ── Identity / OIDC ─────────────────────────────────────────────────
    identity_backend: IdentityBackend = "oidc"
    oidc_issuer: str = "http://localhost:5556/dex"
    oidc_client_id: str = "shellforge-web"
    oidc_client_secret: str = "local-dev-only-replace-in-prod"
    oidc_redirect_uri: str = "http://localhost:3000/auth/callback"
    oidc_jwks_cache_ttl_seconds: int = 3600

    # ── Secrets backend ─────────────────────────────────────────────────
    secret_backend: SecretBackend = "infisical"
    secret_path_prefix: str = "shellforge/tenants"

    infisical_site_url: str = "http://localhost:8080"
    infisical_project_id: str = ""
    infisical_client_id: str = ""
    infisical_client_secret: str = ""
    infisical_env_slug: str = "dev"

    vault_addr: str = ""
    vault_token: str = ""
    vault_namespace: str = ""

    aws_region: str = "us-east-1"
    aws_access_key_id: str = ""
    aws_secret_access_key: str = ""

    # ── Audit ───────────────────────────────────────────────────────────
    audit_backend: AuditBackend = "otel"
    otel_exporter_otlp_endpoint: str = "http://localhost:4317"
    otel_exporter_otlp_protocol: str = "grpc"
    otel_service_name: str = "shellforge-control-plane"

    audit_hash_chain_enabled: bool = True
    audit_genesis_hash: str = "0" * 64

    # ── Compute provider (OpenShell) ────────────────────────────────────
    compute_backend: ComputeBackend = "openshell"
    openshell_gateway_endpoint: str = "localhost:50051"
    openshell_auth_mode: Literal["mtls", "oidc", "plaintext"] = "plaintext"
    openshell_mtls_ca_cert: str = ""
    openshell_mtls_client_cert: str = ""
    openshell_mtls_client_key: str = ""
    openshell_oidc_token: str = ""
    openshell_default_compute_driver: str = "docker"

    # ── PDF renderer ────────────────────────────────────────────────────
    pdf_backend: PdfBackend = "weasyprint"

    # ── Demo seed ───────────────────────────────────────────────────────
    seed_demo_password: str = "demo1234"
    seed_force: bool = False

    # ── Derived ─────────────────────────────────────────────────────────
    @property
    def is_local(self) -> bool:
        return self.env == "local"

    @property
    def is_production(self) -> bool:
        return self.env == "production"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Cached settings singleton."""
    return Settings()  # type: ignore[call-arg]
