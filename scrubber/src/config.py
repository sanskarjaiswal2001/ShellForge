"""Scrubber configuration."""

from __future__ import annotations

from enum import StrEnum
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class ComplianceRegime(StrEnum):
    HIPAA = "hipaa"
    PCI = "pci"
    SOC2 = "soc2"
    BASELINE = "baseline"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="SCRUBBER_",
        extra="ignore",
    )

    # Which compliance regime this instance enforces.
    # Set via SCRUBBER_REGIME env var injected into the sandbox.
    regime: ComplianceRegime = ComplianceRegime.HIPAA

    # Upstream API endpoints (where to forward after scrubbing)
    anthropic_upstream: str = "https://api.anthropic.com"
    openai_upstream: str = "https://api.openai.com"

    # Streaming: collect all chunks then scrub before returning.
    # Slightly higher latency but PII can't leak via split tokens.
    stream_mode: str = "accumulate"  # accumulate | passthrough

    # Mistral/Ollama endpoint for async audit (NOT on the sync path).
    ollama_endpoint: str = "http://host.docker.internal:11434"
    ollama_model: str = "mistral"
    async_audit_enabled: bool = True

    # GLiNER model to use inside Presidio.
    gliner_model: str = "knowledgator/gliner-pii-base-v1.0"

    port: int = 8888


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
