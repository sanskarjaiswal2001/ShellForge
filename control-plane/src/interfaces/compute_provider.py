"""Compute provider protocol — the sandbox runtime abstraction.

Default implementation wraps NVIDIA OpenShell's gRPC API. The protocol exists
because OpenShell is alpha — if NVIDIA changes the API, or if a client wants
to use a different sandbox runtime (raw Docker, gVisor, Kata, Firecracker),
the implementation can be swapped without changing business logic.

EVERY ComputeProvider implementation MUST tag resources with the tenant_id
so that list/get operations cannot return cross-tenant data.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import AsyncIterator, Protocol, runtime_checkable


class SandboxPhase(StrEnum):
    """Lifecycle state."""

    PROVISIONING = "PROVISIONING"
    READY = "READY"
    ERROR = "ERROR"
    DELETING = "DELETING"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True, slots=True)
class SandboxSpec:
    """What to create. Tenant-agnostic in itself — tenancy is enforced at call site."""

    name: str
    policy_yaml: str
    agent: str                                # "claude" | "codex" | "copilot" | etc.
    providers: tuple[str, ...] = ()           # provider names to attach (tenant-namespaced)
    compute_driver: str = "docker"            # "docker" | "podman" | "kubernetes" | "microvm"
    labels: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class SandboxRef:
    """A reference to a created sandbox."""

    name: str                                 # backend-assigned unique name
    uid: str                                  # backend-assigned UUID
    phase: SandboxPhase
    labels: dict[str, str] = field(default_factory=dict)
    status_detail: str = ""


@dataclass(frozen=True, slots=True)
class SandboxEvent:
    """Streamed lifecycle event from WatchSandbox."""

    sandbox_name: str
    phase: SandboxPhase
    occurred_at: float                        # unix epoch seconds
    message: str = ""


@dataclass(frozen=True, slots=True)
class SandboxLogLine:
    """Streamed OCSF-formatted log line from a sandbox."""

    sandbox_name: str
    ocsf_json: dict[str, object]
    occurred_at: float


@runtime_checkable
class ComputeProvider(Protocol):
    """Pluggable sandbox runtime."""

    async def create_sandbox(self, tenant_id: str, spec: SandboxSpec) -> SandboxRef:
        """Create a sandbox. Implementation MUST tag with tenant_id label."""
        ...

    async def get_sandbox(self, tenant_id: str, name: str) -> SandboxRef:
        """Get a sandbox by name. Must return 404 if the sandbox does not
        belong to ``tenant_id`` (NOT raise PermissionError — leak-free)."""
        ...

    async def list_sandboxes(self, tenant_id: str) -> list[SandboxRef]:
        """List sandboxes for a tenant. MUST filter by tenant label."""
        ...

    async def delete_sandbox(self, tenant_id: str, name: str) -> None:
        """Delete. Must validate tenant ownership first."""
        ...

    async def apply_policy(self, tenant_id: str, name: str, policy_yaml: str) -> None:
        """Hot-reload a sandbox's network policy."""
        ...

    async def watch_sandbox(
        self, tenant_id: str, name: str
    ) -> AsyncIterator[SandboxEvent]:
        """Stream lifecycle events."""
        ...

    async def tail_logs(
        self, tenant_id: str, name: str
    ) -> AsyncIterator[SandboxLogLine]:
        """Stream OCSF log lines from a sandbox."""
        ...

    async def create_provider(
        self, tenant_id: str, name: str, provider_type: str, credentials: dict[str, str]
    ) -> None:
        """Create a tenant-namespaced provider (credential bundle)."""
        ...


class SandboxNotFoundError(LookupError):
    """No sandbox with the given name in the given tenant scope."""


class TenantIsolationError(PermissionError):
    """Internal: raised if implementation detects cross-tenant access attempt.

    Should NEVER be raised in correct code — callers must scope by tenant.
    Hitting this in production is a bug, not a security signal.
    """
