"""OpenShell compute provider — wraps NVIDIA OpenShell gRPC.

Activated when COMPUTE_BACKEND=openshell. Generates gRPC stubs from the
vendored protos at the pinned commit (`make vendor-protos && make proto-gen`).

If the generated stubs are absent at import time (proto-gen not yet run),
this class raises at construction with a clear setup-required error.
Fall back to COMPUTE_BACKEND=mock for demo.

Tenant isolation invariants enforced here:
  - Every CreateSandbox attaches label `shellforge.io/tenant=<tenant_id>`
  - Every ListSandboxes uses label_selector for the requesting tenant
  - GetSandboxProviderEnvironment is NEVER called from this code path
"""

from __future__ import annotations

import importlib
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Any

import grpc

from src.config import Settings
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
USER_LABEL_KEY = "shellforge.io/user"


def _try_import_stubs() -> tuple[Any, Any, Any] | None:
    """Returns (openshell_pb2, openshell_pb2_grpc, sandbox_pb2) or None
    if proto-gen has not been run yet."""
    try:
        openshell_pb2 = importlib.import_module("src.openshell.proto.openshell_pb2")
        openshell_pb2_grpc = importlib.import_module("src.openshell.proto.openshell_pb2_grpc")
        sandbox_pb2 = importlib.import_module("src.openshell.proto.sandbox_pb2")
        return openshell_pb2, openshell_pb2_grpc, sandbox_pb2
    except ImportError:
        return None


class OpenShellComputeProvider(ComputeProvider):
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

        stubs = _try_import_stubs()
        if stubs is None:
            raise RuntimeError(
                "OpenShell gRPC stubs not generated. Run `make vendor-protos && "
                "make proto-gen` to pull and generate them, or set "
                "COMPUTE_BACKEND=mock for demo without OpenShell."
            )
        self._pb2, self._pb2_grpc, self._sandbox_pb2 = stubs

        self._channel = self._build_channel()
        self._stub = self._pb2_grpc.OpenShellServiceStub(self._channel)

    def _build_channel(self) -> grpc.aio.Channel:
        endpoint = self._settings.openshell_gateway_endpoint
        mode = self._settings.openshell_auth_mode

        if mode == "mtls":
            with open(self._settings.openshell_mtls_ca_cert, "rb") as f:
                ca = f.read()
            with open(self._settings.openshell_mtls_client_cert, "rb") as f:
                cert = f.read()
            with open(self._settings.openshell_mtls_client_key, "rb") as f:
                key = f.read()
            creds = grpc.ssl_channel_credentials(
                root_certificates=ca, private_key=key, certificate_chain=cert
            )
            return grpc.aio.secure_channel(endpoint, creds)

        if mode == "oidc":
            call_creds = grpc.access_token_call_credentials(
                self._settings.openshell_oidc_token
            )
            tls_creds = grpc.ssl_channel_credentials()
            creds = grpc.composite_channel_credentials(tls_creds, call_creds)
            return grpc.aio.secure_channel(endpoint, creds)

        # plaintext (local dev only)
        return grpc.aio.insecure_channel(endpoint)

    # ─── Sandbox lifecycle ──────────────────────────────────────────────

    async def create_sandbox(self, tenant_id: str, spec: SandboxSpec) -> SandboxRef:
        labels = {**spec.labels, TENANT_LABEL_KEY: tenant_id}
        # Convert YAML policy to proto.
        policy_proto = self._yaml_to_policy_proto(spec.policy_yaml)

        request = self._pb2.CreateSandboxRequest(
            name=spec.name,
            policy=policy_proto,
            provider_names=list(spec.providers),
            labels=labels,
            compute_driver=spec.compute_driver,
        )
        response = await self._stub.CreateSandbox(request)
        return self._ref_from_response(response, labels)

    async def get_sandbox(self, tenant_id: str, name: str) -> SandboxRef:
        try:
            response = await self._stub.GetSandbox(self._pb2.GetSandboxRequest(name=name))
        except grpc.aio.AioRpcError as e:
            if e.code() == grpc.StatusCode.NOT_FOUND:
                raise SandboxNotFoundError(name) from e
            raise

        labels = dict(response.labels)
        # Defense in depth: never return cross-tenant resources, even if
        # OpenShell returns them (e.g., a misconfigured gateway).
        if labels.get(TENANT_LABEL_KEY) != tenant_id:
            raise SandboxNotFoundError(name)

        return self._ref_from_response(response, labels)

    async def list_sandboxes(self, tenant_id: str) -> list[SandboxRef]:
        request = self._pb2.ListSandboxesRequest(
            label_selector=f"{TENANT_LABEL_KEY}={tenant_id}"
        )
        response = await self._stub.ListSandboxes(request)
        return [self._ref_from_response(s, dict(s.labels)) for s in response.sandboxes]

    async def delete_sandbox(self, tenant_id: str, name: str) -> None:
        # Ownership check first.
        await self.get_sandbox(tenant_id, name)
        await self._stub.DeleteSandbox(self._pb2.DeleteSandboxRequest(name=name))

    async def apply_policy(self, tenant_id: str, name: str, policy_yaml: str) -> None:
        await self.get_sandbox(tenant_id, name)
        policy_proto = self._yaml_to_policy_proto(policy_yaml)
        request = self._pb2.UpdateConfigRequest(
            name=name,
            scope=self._pb2.SettingScope.SANDBOX,
            policy=policy_proto,
        )
        await self._stub.UpdateConfig(request)

    async def watch_sandbox(
        self, tenant_id: str, name: str
    ) -> AsyncIterator[SandboxEvent]:
        await self.get_sandbox(tenant_id, name)
        async for event in self._stub.WatchSandbox(
            self._pb2.WatchSandboxRequest(name=name)
        ):
            yield SandboxEvent(
                sandbox_name=name,
                phase=SandboxPhase(self._pb2.SandboxPhase.Name(event.phase)),
                occurred_at=datetime.now(UTC).timestamp(),
                message=event.status_detail,
            )

    async def tail_logs(
        self, tenant_id: str, name: str
    ) -> AsyncIterator[SandboxLogLine]:
        await self.get_sandbox(tenant_id, name)
        async for event in self._stub.WatchSandbox(
            self._pb2.WatchSandboxRequest(name=name, include_logs=True)
        ):
            if not event.HasField("log"):
                continue
            import json
            try:
                ocsf = json.loads(event.log.body)
            except json.JSONDecodeError:
                continue
            yield SandboxLogLine(
                sandbox_name=name,
                ocsf_json=ocsf,
                occurred_at=datetime.now(UTC).timestamp(),
            )

    async def create_provider(
        self,
        tenant_id: str,
        name: str,
        provider_type: str,
        credentials: dict[str, str],
    ) -> None:
        request = self._pb2.CreateProviderRequest(
            name=name,
            type=provider_type,
            credentials=credentials,
            labels={TENANT_LABEL_KEY: tenant_id},
        )
        await self._stub.CreateProvider(request)

    # ─── Helpers ────────────────────────────────────────────────────────

    def _yaml_to_policy_proto(self, yaml_str: str):
        import yaml
        from google.protobuf.json_format import ParseDict

        data = yaml.safe_load(yaml_str)
        # Strip the version field which is implicit in proto.
        data.pop("version", None)
        return ParseDict(data, self._sandbox_pb2.SandboxPolicy())

    def _ref_from_response(self, sandbox_msg, labels: dict[str, str]) -> SandboxRef:
        phase_name = self._pb2.SandboxPhase.Name(sandbox_msg.phase)
        return SandboxRef(
            name=sandbox_msg.name,
            uid=sandbox_msg.uid,
            phase=SandboxPhase(phase_name),
            labels=labels,
            status_detail=getattr(sandbox_msg, "status_detail", ""),
        )
