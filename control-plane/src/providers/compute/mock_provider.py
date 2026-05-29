"""Mock compute provider — demo-reliable, in-memory fake.

Used when OpenShell is not available (CI, offline demo, OpenShell image
pull failures). Behaviorally identical to a real provider from the
control plane's perspective: tagged sandboxes, tenant-scoped lists,
policy application, lifecycle events.

Critical for demo reliability: if OpenShell's alpha image fails to pull
on judging day, set COMPUTE_BACKEND=mock and the dashboard still works.

NOT suitable for any non-demo use — there's no real isolation, no real
network policy enforcement.
"""

from __future__ import annotations

import asyncio
from collections import defaultdict
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from datetime import UTC, datetime
from uuid import uuid4

from src.interfaces.compute_provider import (
    ComputeProvider,
    SandboxEvent,
    SandboxLogLine,
    SandboxNotFoundError,
    SandboxPhase,
    SandboxRef,
    SandboxSpec,
)


TENANT_LABEL_KEY = "shellforge.io/tenant"


@dataclass
class _MockSandbox:
    name: str
    uid: str
    tenant_id: str
    spec: SandboxSpec
    phase: SandboxPhase = SandboxPhase.PROVISIONING
    status_detail: str = ""
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    log_lines: list[dict] = field(default_factory=list)


@dataclass
class _MockProvider:
    name: str
    tenant_id: str
    type: str
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))


class MockComputeProvider(ComputeProvider):
    """In-memory sandbox + provider registry, keyed by tenant_id."""

    def __init__(self) -> None:
        self._sandboxes: dict[str, _MockSandbox] = {}             # name -> sandbox
        self._providers: dict[str, _MockProvider] = {}            # name -> provider
        self._lock = asyncio.Lock()
        # Event subscribers per sandbox name → asyncio.Queue
        self._event_subscribers: dict[str, list[asyncio.Queue]] = defaultdict(list)

    # ─── Sandbox lifecycle ──────────────────────────────────────────────

    async def create_sandbox(self, tenant_id: str, spec: SandboxSpec) -> SandboxRef:
        async with self._lock:
            if spec.name in self._sandboxes:
                # Idempotent re-create returns existing.
                existing = self._sandboxes[spec.name]
                if existing.tenant_id != tenant_id:
                    # Name collision across tenants — different namespaces in our model.
                    raise PermissionError(
                        "Name collision detected; sandbox names are not currently namespaced."
                    )
                return self._to_ref(existing)

            uid = str(uuid4())
            labels = {**spec.labels, TENANT_LABEL_KEY: tenant_id}
            tagged_spec = SandboxSpec(
                name=spec.name,
                policy_yaml=spec.policy_yaml,
                agent=spec.agent,
                providers=spec.providers,
                compute_driver=spec.compute_driver,
                labels=labels,
            )
            sandbox = _MockSandbox(name=spec.name, uid=uid, tenant_id=tenant_id, spec=tagged_spec)
            self._sandboxes[spec.name] = sandbox

        # Simulate provisioning lifecycle in the background.
        asyncio.create_task(self._simulate_provisioning(spec.name))
        return self._to_ref(sandbox)

    async def get_sandbox(self, tenant_id: str, name: str) -> SandboxRef:
        async with self._lock:
            sandbox = self._sandboxes.get(name)
            if sandbox is None or sandbox.tenant_id != tenant_id:
                # 404, never 403 — never leak cross-tenant existence.
                raise SandboxNotFoundError(name)
            return self._to_ref(sandbox)

    async def list_sandboxes(self, tenant_id: str) -> list[SandboxRef]:
        async with self._lock:
            return [
                self._to_ref(s)
                for s in self._sandboxes.values()
                if s.tenant_id == tenant_id
            ]

    async def delete_sandbox(self, tenant_id: str, name: str) -> None:
        async with self._lock:
            sandbox = self._sandboxes.get(name)
            if sandbox is None or sandbox.tenant_id != tenant_id:
                raise SandboxNotFoundError(name)
            sandbox.phase = SandboxPhase.DELETING
        await asyncio.sleep(0.1)
        async with self._lock:
            self._sandboxes.pop(name, None)

    async def apply_policy(self, tenant_id: str, name: str, policy_yaml: str) -> None:
        async with self._lock:
            sandbox = self._sandboxes.get(name)
            if sandbox is None or sandbox.tenant_id != tenant_id:
                raise SandboxNotFoundError(name)
            sandbox.spec = SandboxSpec(
                name=sandbox.spec.name,
                policy_yaml=policy_yaml,
                agent=sandbox.spec.agent,
                providers=sandbox.spec.providers,
                compute_driver=sandbox.spec.compute_driver,
                labels=sandbox.spec.labels,
            )

    async def watch_sandbox(
        self, tenant_id: str, name: str
    ) -> AsyncIterator[SandboxEvent]:
        async with self._lock:
            sandbox = self._sandboxes.get(name)
            if sandbox is None or sandbox.tenant_id != tenant_id:
                raise SandboxNotFoundError(name)
            queue: asyncio.Queue = asyncio.Queue()
            self._event_subscribers[name].append(queue)

        try:
            while True:
                event = await queue.get()
                yield event
                if event.phase in (SandboxPhase.ERROR, SandboxPhase.READY, SandboxPhase.DELETING):
                    # Caller can choose to break; we keep the stream open for live updates.
                    pass
        finally:
            async with self._lock:
                if queue in self._event_subscribers[name]:
                    self._event_subscribers[name].remove(queue)

    async def tail_logs(
        self, tenant_id: str, name: str
    ) -> AsyncIterator[SandboxLogLine]:
        async with self._lock:
            sandbox = self._sandboxes.get(name)
            if sandbox is None or sandbox.tenant_id != tenant_id:
                raise SandboxNotFoundError(name)
            for line in sandbox.log_lines:
                yield SandboxLogLine(
                    sandbox_name=name,
                    ocsf_json=line,
                    occurred_at=line.get("time", 0) / 1000,
                )

    async def create_provider(
        self,
        tenant_id: str,
        name: str,
        provider_type: str,
        credentials: dict[str, str],
    ) -> None:
        async with self._lock:
            self._providers[name] = _MockProvider(
                name=name,
                tenant_id=tenant_id,
                type=provider_type,
            )
        # NB: credentials are intentionally NOT stored — mock provider does
        # not persist secrets in memory either.

    # ─── Internal ──────────────────────────────────────────────────────

    async def _simulate_provisioning(self, name: str) -> None:
        # Realistic lifecycle: PROVISIONING (2s) → READY.
        await self._broadcast_event(name, SandboxPhase.PROVISIONING, "Requesting sandbox...")
        await asyncio.sleep(0.5)
        await self._broadcast_event(name, SandboxPhase.PROVISIONING, "Pulling image...")
        await asyncio.sleep(0.8)
        await self._broadcast_event(name, SandboxPhase.PROVISIONING, "Starting sandbox...")
        await asyncio.sleep(0.5)

        async with self._lock:
            sandbox = self._sandboxes.get(name)
            if sandbox is None:
                return
            sandbox.phase = SandboxPhase.READY

        await self._broadcast_event(name, SandboxPhase.READY, "Sandbox ready")

    async def _broadcast_event(self, name: str, phase: SandboxPhase, message: str) -> None:
        event = SandboxEvent(
            sandbox_name=name,
            phase=phase,
            occurred_at=datetime.now(UTC).timestamp(),
            message=message,
        )
        async with self._lock:
            sandbox = self._sandboxes.get(name)
            if sandbox is not None:
                sandbox.phase = phase
                sandbox.status_detail = message
            subs = list(self._event_subscribers.get(name, []))
        for q in subs:
            await q.put(event)

    @staticmethod
    def _to_ref(s: _MockSandbox) -> SandboxRef:
        return SandboxRef(
            name=s.name,
            uid=s.uid,
            phase=s.phase,
            labels=dict(s.spec.labels),
            status_detail=s.status_detail,
        )

    # ─── Test helpers (not part of protocol) ────────────────────────────

    async def simulate_violation(self, name: str, destination: str) -> dict:
        """Generate a realistic policy violation OCSF event for demo purposes."""
        async with self._lock:
            sandbox = self._sandboxes.get(name)
            if sandbox is None:
                raise SandboxNotFoundError(name)

        event = {
            "class_uid": 4002,
            "category_uid": 4,
            "activity_id": 6,
            "time": int(datetime.now(UTC).timestamp() * 1000),
            "actor": {
                "process": {"name": "curl", "file": {"path": "/usr/bin/curl"}},
            },
            "dst_endpoint": {"hostname": destination.split(":")[0], "port": 443},
            "firewall_rule": {
                "name": "policy-deny",
                "desc": "Endpoint not in allowlist",
            },
            "status_detail": "Denied",
            "sandbox_name": name,
            "tenant_id": sandbox.tenant_id,
        }
        async with self._lock:
            sandbox.log_lines.append(event)
        return event
