# OpenShell Integration Skill

**Trigger:** Any task involving OpenShell gateway communication — sandbox lifecycle, gRPC client code, provider/secret injection, OCSF log tailing, policy application.

---

## Core Rule: Wrap, Never Fork

Pin to commit `6c7950da900921a24aa65e79c7b522ba12fd7875`. All OpenShell calls go through `control-plane/src/openshell/client.py`. Business logic never calls the `openshell` SDK or gRPC stubs directly.

```python
# WRONG
from openshell import SandboxClient
client = SandboxClient(...)

# CORRECT
from src.openshell.client import OpenShellClient
client = OpenShellClient(tenant_id=ctx.tenant_id)
```

---

## Concept Mapping: ShellForge → OpenShell

| ShellForge Concept | OpenShell Concept | Notes |
|---|---|---|
| Organization | Gateway scope | ShellForge enforces tenant isolation above OpenShell |
| Sandbox request | Gateway create call | `CreateSandbox` RPC |
| Policy template | YAML policy file | Passed at create or via `UpdateConfig` |
| Secret bundle | Provider | Attached via `AttachSandboxProvider` |
| Audit event | OCSF log line | Tailed via `WatchSandbox` or `GetSandboxLogs` |

OpenShell's `ObjectMeta` has **no tenant field**. Tenant isolation is 100% ShellForge's responsibility — always tag every OpenShell resource with `labels: {shellforge.io/tenant: <org_id>}` and filter on list operations.

---

## Gateway / Sandbox Model

```
OpenShell Gateway (gRPC :8080 / REST :8080)
    │
    ├── Manages: Providers, Policies, Inference Routes
    │
    └── Orchestrates via Compute Driver (Docker/Podman/k8s/MicroVM)
            │
            └── Sandbox [
                  Supervisor (privileged) ── fetches policy + creds from gateway
                  Policy Proxy (OPA/regorus) ── enforces network L4+L7
                  Agent Process (claude/codex/etc., runs as sandbox:sandbox)
                ]
```

Supervisor initiates outbound connections TO gateway (not inbound). SSH/exec/file-sync/port-forward all go through a single relay stream.

---

## gRPC Client Setup

```python
# control-plane/src/openshell/client.py
import grpc
from openshell.proto import openshell_pb2, openshell_pb2_grpc

class OpenShellClient:
    def __init__(self, endpoint: str, tls_config: TLSConfig | None = None):
        if tls_config:
            creds = grpc.ssl_channel_credentials(
                root_certificates=tls_config.ca_cert,
                private_key=tls_config.client_key,
                certificate_chain=tls_config.client_cert,
            )
            self._channel = grpc.secure_channel(endpoint, creds)
        else:
            self._channel = grpc.insecure_channel(endpoint)
        self._stub = openshell_pb2_grpc.OpenShellServiceStub(self._channel)
```

Auth modes (select via `OPENSHELL_AUTH_MODE` env var):
- `mtls` — mTLS cert-based (certs at `~/.config/openshell/gateways/{name}/mtls/`)
- `oidc` — bearer token in gRPC metadata: `authorization: Bearer <jwt>`
- `plaintext` — local dev, no TLS

---

## Sandbox Lifecycle RPCs

```python
# Create sandbox (returns immediately, poll WatchSandbox for READY state)
response = stub.CreateSandbox(CreateSandboxRequest(
    name="sandbox-<uuid>",
    policy=policy_proto,               # SandboxPolicy message
    provider_names=["claude-prod"],    # pre-attached providers
    labels={"shellforge.io/tenant": org_id, "shellforge.io/user": user_id},
    compute_driver=ComputeDriver.DOCKER,
))

# Poll for READY
for event in stub.WatchSandbox(WatchSandboxRequest(name=sandbox_name)):
    if event.phase == SandboxPhase.READY:
        break
    if event.phase == SandboxPhase.ERROR:
        raise SandboxProvisionError(event.status_detail)

# List (always filter by tenant label)
sandboxes = stub.ListSandboxes(ListSandboxesRequest(
    label_selector="shellforge.io/tenant=acme-health"
))

# Delete
stub.DeleteSandbox(DeleteSandboxRequest(name=sandbox_name))
```

### Sandbox Phases
`PROVISIONING` → `READY` → `ERROR` → `DELETING` → `UNKNOWN`

---

## Policy Application

```python
# Apply (hot-reload for network_policies; static fields require sandbox recreate)
stub.UpdateConfig(UpdateConfigRequest(
    name=sandbox_name,
    scope=SettingScope.SANDBOX,
    policy=policy_proto,
))

# Verify applied (use --wait equivalent)
status = stub.GetSandboxPolicyStatus(GetSandboxPolicyStatusRequest(name=sandbox_name))
```

**Static fields** (`filesystem_policy`, `landlock`, `process`): locked at creation, cannot update.  
**Dynamic fields** (`network_policies`, inference): hot-reloadable without restart.

### Policy YAML → Proto Conversion

```python
import yaml
from openshell.proto import sandbox_pb2
from google.protobuf.json_format import ParseDict

def yaml_to_policy_proto(yaml_str: str) -> sandbox_pb2.SandboxPolicy:
    data = yaml.safe_load(yaml_str)
    return ParseDict(data, sandbox_pb2.SandboxPolicy())
```

---

## Provider / Secret Injection

```python
# Create provider (called once per tenant onboarding)
stub.CreateProvider(CreateProviderRequest(
    name=f"claude-{org_id}",
    type="claude",
    credentials={"ANTHROPIC_API_KEY": secret_value},
    labels={"shellforge.io/tenant": org_id},
))

# Attach to sandbox at creation or after
stub.AttachSandboxProvider(AttachSandboxProviderRequest(
    sandbox_name=sandbox_name,
    provider_name=f"claude-{org_id}",
))
```

**Security guarantee:** credentials never written to sandbox disk. Child process sees placeholder `openshell:resolve:env:ANTHROPIC_API_KEY`; proxy resolves at network layer.

**Never** call `GetSandboxProviderEnvironment` from ShellForge — that RPC exposes real secret values. Only the sandbox supervisor should call it.

---

## OCSF Log Tailing + Re-emission

```python
# Tail OpenShell OCSF logs and re-emit into ShellForge hash chain with tenant tag
async def tail_sandbox_logs(sandbox_name: str, tenant_id: str, emitter: AuditEmitter):
    for log_line in stub.WatchSandbox(WatchSandboxRequest(name=sandbox_name)):
        if log_line.HasField("log"):
            ocsf_event = json.loads(log_line.log.body)
            # Tag with tenant and re-emit into our hash chain
            await emitter.emit(
                event_class=ocsf_event["class_uid"],
                source="openshell",
                tenant_id=tenant_id,
                sandbox_name=sandbox_name,
                raw=ocsf_event,
            )
```

OCSF event classes from OpenShell:
- `4001` — Network Activity (TCP L4)
- `4002` — HTTP Activity (L7 inspected)
- `4007` — SSH Activity
- `1007` — Process Activity
- `2004` — Detection Finding

---

## Proto Generation

OpenShell `.proto` files live at `proto/` in the pinned repo. Generate stubs:

```bash
# scripts/gen-proto.sh
pip install grpcio-tools
python -m grpc_tools.protoc \
  -I./vendor/openshell/proto \
  --python_out=control-plane/src/openshell/proto \
  --grpc_python_out=control-plane/src/openshell/proto \
  vendor/openshell/proto/openshell.proto \
  vendor/openshell/proto/sandbox.proto \
  vendor/openshell/proto/datamodel.proto \
  vendor/openshell/proto/inference.proto
```

Vendor the proto files at pinned commit — do not pull dynamically.

---

## Common Pitfalls

1. **Never use `SET SESSION`** in Postgres — use `SET LOCAL` (transaction-scoped)
2. **Always label OpenShell resources** with `shellforge.io/tenant` — ObjectMeta has no tenant field
3. **Label selectors on List** — always include `shellforge.io/tenant=<org_id>` in list calls
4. **Don't call `GetSandboxProviderEnvironment`** from control plane — secrets stay in supervisor
5. **Policy size limit: 256 KB** — validate before submitting
6. **Wildcard rules**: only first DNS label (`*.example.com` ok, `*.com` rejected)
7. **Static policy fields immutable** — cannot change `filesystem_policy`/`process` after creation
