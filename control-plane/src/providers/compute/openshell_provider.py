"""OpenShell compute provider — wraps NVIDIA OpenShell gRPC (pinned 6c7950d).

Activated when COMPUTE_BACKEND=openshell. Requires generated stubs:
    make vendor-protos && make proto-gen

Tenant isolation is NEVER delegated to OpenShell (ObjectMeta has no tenant
field). We enforce it here via labels + label_selector:
  - Every CreateSandbox attaches label `shellforge.io/tenant=<tenant_id>`
  - Every ListSandboxes uses label_selector to scope by tenant
  - GetSandbox validates tenant label before returning — cross-tenant is 404
  - GetSandboxProviderEnvironment is NEVER called here (supervisor only)
"""

from __future__ import annotations

import importlib
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Any

import grpc
import grpc.aio

from src.config import Settings
from src.interfaces.compute_provider import (
    ComputeProvider,
    SandboxEvent,
    SandboxLogLine,
    SandboxNotFoundError,
    SandboxPhase,
    SandboxRef,
    SandboxSpec,
    TenantIsolationError,
)


TENANT_LABEL_KEY = "shellforge.io/tenant"
USER_LABEL_KEY = "shellforge.io/user"

# Mapping from OpenShell agent name to the community sandbox image.
# When COMPUTE_BACKEND=openshell, create_sandbox uses the community image
# so the agent is pre-installed. Fallback to bare shell if unknown.
AGENT_IMAGES: dict[str, str] = {
    "claude": "ghcr.io/nvidia/openshell-community/claude:latest",
    "opencode": "ghcr.io/nvidia/openshell-community/base:latest",
    "codex": "ghcr.io/nvidia/openshell-community/base:latest",
    "copilot": "ghcr.io/nvidia/openshell-community/base:latest",
}
DEFAULT_IMAGE = "ghcr.io/nvidia/openshell-community/base:latest"


_PHASE_MAP: dict[int, SandboxPhase] = {
    0: SandboxPhase.UNKNOWN,       # SANDBOX_PHASE_UNSPECIFIED
    1: SandboxPhase.PROVISIONING,  # SANDBOX_PHASE_PROVISIONING
    2: SandboxPhase.READY,         # SANDBOX_PHASE_READY
    3: SandboxPhase.ERROR,         # SANDBOX_PHASE_ERROR
    4: SandboxPhase.DELETING,      # SANDBOX_PHASE_DELETING
    5: SandboxPhase.UNKNOWN,       # SANDBOX_PHASE_UNKNOWN
}


def _load_stubs() -> tuple[Any, Any, Any, Any, Any]:
    """Import generated stubs lazily so the module can be imported even if
    proto-gen has not been run (e.g. when COMPUTE_BACKEND=mock)."""
    import src.openshell  # registers proto dir on sys.path  # noqa: F401

    pb2 = importlib.import_module("src.openshell.proto.openshell_pb2")
    pb2_grpc = importlib.import_module("src.openshell.proto.openshell_pb2_grpc")
    sandbox_pb2 = importlib.import_module("src.openshell.proto.sandbox_pb2")
    datamodel_pb2 = importlib.import_module("src.openshell.proto.datamodel_pb2")
    inference_pb2 = importlib.import_module("src.openshell.proto.inference_pb2")
    return pb2, pb2_grpc, sandbox_pb2, datamodel_pb2, inference_pb2


class OpenShellComputeProvider(ComputeProvider):
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

        try:
            self._pb2, self._pb2_grpc, self._sandbox_pb2, self._dm_pb2, _ = _load_stubs()
        except ImportError as e:
            raise RuntimeError(
                "OpenShell gRPC stubs not generated. "
                "Run `make vendor-protos && make proto-gen`, or set "
                "COMPUTE_BACKEND=mock for demo without OpenShell."
            ) from e

        self._channel = self._build_channel()
        self._stub = self._pb2_grpc.OpenShellStub(self._channel)

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
            token = self._settings.openshell_oidc_token
            call_creds = grpc.access_token_call_credentials(token)
            tls_creds = grpc.ssl_channel_credentials()
            combined = grpc.composite_channel_credentials(tls_creds, call_creds)
            return grpc.aio.secure_channel(endpoint, combined)

        # plaintext — local dev only
        return grpc.aio.insecure_channel(endpoint)

    # ─── Sandbox lifecycle ──────────────────────────────────────────────

    async def create_sandbox(self, tenant_id: str, spec: SandboxSpec) -> SandboxRef:
        labels = {
            **spec.labels,
            TENANT_LABEL_KEY: tenant_id,
        }
        policy_proto = self._yaml_to_policy(spec.policy_yaml)
        image = AGENT_IMAGES.get(spec.agent, DEFAULT_IMAGE)
        template = self._pb2.SandboxTemplate(image=image)

        os_spec = self._pb2.SandboxSpec(
            template=template,
            policy=policy_proto,
            providers=list(spec.providers),
        )
        request = self._pb2.CreateSandboxRequest(
            spec=os_spec,
            name=spec.name,
            labels=labels,
        )
        response = await self._stub.CreateSandbox(request)
        return self._sandbox_to_ref(response.sandbox)

    async def get_sandbox(self, tenant_id: str, name: str) -> SandboxRef:
        try:
            response = await self._stub.GetSandbox(
                self._pb2.GetSandboxRequest(name=name)
            )
        except grpc.aio.AioRpcError as e:
            if e.code() == grpc.StatusCode.NOT_FOUND:
                raise SandboxNotFoundError(name) from e
            raise

        ref = self._sandbox_to_ref(response.sandbox)
        # Cross-tenant check — never reveal existence of another tenant's sandbox.
        if ref.labels.get(TENANT_LABEL_KEY) != tenant_id:
            raise SandboxNotFoundError(name)
        return ref

    async def list_sandboxes(self, tenant_id: str) -> list[SandboxRef]:
        response = await self._stub.ListSandboxes(
            self._pb2.ListSandboxesRequest(
                label_selector=f"{TENANT_LABEL_KEY}={tenant_id}",
                limit=500,
            )
        )
        return [self._sandbox_to_ref(s) for s in response.sandboxes]

    async def delete_sandbox(self, tenant_id: str, name: str) -> None:
        await self.get_sandbox(tenant_id, name)  # ownership check
        await self._stub.DeleteSandbox(self._pb2.DeleteSandboxRequest(name=name))

    async def apply_policy(self, tenant_id: str, name: str, policy_yaml: str) -> None:
        await self.get_sandbox(tenant_id, name)  # ownership check
        policy_proto = self._yaml_to_policy(policy_yaml)
        await self._stub.UpdateConfig(
            self._pb2.UpdateConfigRequest(
                name=name,
                policy=policy_proto,
            )
        )

    async def watch_sandbox(
        self, tenant_id: str, name: str
    ) -> AsyncIterator[SandboxEvent]:
        await self.get_sandbox(tenant_id, name)  # ownership check
        async for event in self._stub.WatchSandbox(
            self._pb2.WatchSandboxRequest(name=name)
        ):
            if event.HasField("sandbox"):
                phase = _PHASE_MAP.get(event.sandbox.phase, SandboxPhase.UNKNOWN)
                detail = event.sandbox.status.message if event.sandbox.HasField("status") else ""
                yield SandboxEvent(
                    sandbox_name=name,
                    phase=phase,
                    occurred_at=datetime.now(UTC).timestamp(),
                    message=detail,
                )

    async def tail_logs(
        self, tenant_id: str, name: str
    ) -> AsyncIterator[SandboxLogLine]:
        await self.get_sandbox(tenant_id, name)  # ownership check
        import json
        async for event in self._stub.WatchSandbox(
            self._pb2.WatchSandboxRequest(name=name)
        ):
            if event.HasField("log"):
                try:
                    ocsf = json.loads(event.log.body)
                except (json.JSONDecodeError, AttributeError):
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
        labels = {TENANT_LABEL_KEY: tenant_id}
        provider = self._dm_pb2.Provider(
            metadata=self._dm_pb2.ObjectMeta(name=name, labels=labels),
            type=provider_type,
            credentials=credentials,
        )
        await self._stub.CreateProvider(
            self._pb2.CreateProviderRequest(provider=provider)
        )

    # ─── Helpers ────────────────────────────────────────────────────────

    def _yaml_to_policy(self, yaml_str: str):
        if not yaml_str:
            return self._sandbox_pb2.SandboxPolicy()
        import yaml
        from google.protobuf.json_format import ParseDict

        data = yaml.safe_load(yaml_str)
        data.pop("version", None)
        try:
            return ParseDict(data, self._sandbox_pb2.SandboxPolicy(), ignore_unknown_fields=True)
        except Exception:  # noqa: BLE001
            return self._sandbox_pb2.SandboxPolicy()

    def _sandbox_to_ref(self, sandbox) -> SandboxRef:
        phase = _PHASE_MAP.get(sandbox.phase, SandboxPhase.UNKNOWN)
        labels = dict(sandbox.metadata.labels)
        status_detail = ""
        if sandbox.HasField("status"):
            status_detail = sandbox.status.message
        return SandboxRef(
            name=sandbox.metadata.name,
            uid=sandbox.metadata.id,
            phase=phase,
            labels=labels,
            status_detail=status_detail,
        )
