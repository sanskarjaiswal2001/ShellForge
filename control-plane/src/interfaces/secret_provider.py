"""Secret provider protocol.

Hides Infisical / Vault / AWS Secrets Manager / env-var behind one interface.
Backend selected at startup via ``SECRET_BACKEND`` env var.

Path conventions:
  - Tenant-scoped: ``shellforge/tenants/<org_id>/<key>``
  - Platform-scoped: ``shellforge/platform/<key>``

Implementations must enforce tenant isolation: a query for tenant A's path
must never return tenant B's secret, even on backend misconfiguration.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class SecretProvider(Protocol):
    """A pluggable secrets backend."""

    async def get(self, path: str) -> str:
        """Fetch a single secret value.

        Args:
            path: Backend-agnostic dotted/slash path, e.g.
                ``shellforge/tenants/acme-health/anthropic_api_key``.

        Raises:
            SecretNotFoundError: Path does not exist.
            SecretAccessError: Backend rejected the request.
        """
        ...

    async def get_many(self, paths: list[str]) -> dict[str, str]:
        """Batch fetch — backends should optimize when possible."""
        ...

    async def set(self, path: str, value: str) -> None:
        """Create or update a secret."""
        ...

    async def delete(self, path: str) -> None:
        """Delete a secret. Idempotent — deleting a missing path is a no-op."""
        ...

    async def list_paths(self, prefix: str) -> list[str]:
        """List secret paths under a prefix. Returns names only, never values."""
        ...


class SecretNotFoundError(KeyError):
    """Requested secret path does not exist."""


class SecretAccessError(RuntimeError):
    """Backend rejected the request (auth, network, quota)."""
