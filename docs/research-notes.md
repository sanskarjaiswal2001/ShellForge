# ShellForge Research Notes

Compiled: 2026-05-29  
OpenShell pinned commit: `6c7950da900921a24aa65e79c7b522ba12fd7875` (2026-05-27)  
DeepWiki snapshot commit: `f954e592` (2026-04-22)  
Helm chart: `oci://ghcr.io/nvidia/openshell/helm-chart` (no semantic version in docs — pull and pin at deploy time)

---

## 1. What OpenShell Actually Is

OpenShell is a sandboxed execution runtime for autonomous AI agents. Written in Rust (89.7%), Shell (5.5%), Python (3.7%). Three components:

- **Gateway** (`openshell-server`): control-plane gRPC/HTTP server. Persists state in SQLite (default) or Postgres. Manages provider credentials, orchestrates sandbox lifecycle via pluggable compute drivers, coordinates supervisor relay sessions for SSH/exec/file-sync/port-forward.
- **Supervisor**: privileged process running inside each sandbox. Enforces isolation, fetches policy from gateway, injects credentials into agent processes.
- **Policy Proxy**: runs inside each sandbox's network namespace. Intercepts all egress, evaluates via OPA (using `regorus` Rego engine), enforces allow/deny at L4 and L7.

Key isolation mechanism: gateway does NOT enforce network policy at request time — enforcement is inside the sandbox via supervisor + proxy.

---

## 2. Gateway API Surface

### Transport
- Primary: **gRPC over HTTP/2** (`OpenShellService`, `InferenceService`)
- Secondary: REST/HTTP (OpenAI/Anthropic-compatible inference endpoints: `/v1/chat/completions`, `/v1/completions`, `/v1/responses`, `/v1/messages`)
- WebSocket tunnel workaround for edge proxies (Cloudflare Access) that break gRPC

### Proto files
- `proto/openshell.proto` — 48-RPC primary service
- `proto/sandbox.proto` — `SandboxPolicy`, `NetworkPolicyRule`, `L7Allow`, `L7DenyRule`
- `proto/compute_driver.proto`, `proto/inference.proto`, `proto/datamodel.proto`, `proto/test.proto`

### Key gRPC RPCs (from `openshell.proto`)

**Sandbox lifecycle:**
`CreateSandbox`, `GetSandbox`, `ListSandboxes`, `DeleteSandbox`, `WatchSandbox` (streaming `SandboxStreamEvent`)

**Policy:**
`GetSandboxConfig` → `{policy: SandboxPolicy, revision: uint64, policy_hash: string}`  
`UpdateConfig` → `{name, scope: GLOBAL|SANDBOX, policy?: SandboxPolicy}`  
`ReportPolicyStatus` → `{sandbox_id, version, status: PolicyStatus, load_error}`  
`SubmitPolicyAnalysis`, `ApproveDraftChunk`, `ApproveAllDraftChunks`

**Provider/Credentials:**
`CreateProvider`, `GetProvider`, `ListProviders`, `UpdateProvider`, `DeleteProvider`  
`ListSandboxProviders`, `AttachSandboxProvider`, `DetachSandboxProvider`  
`GetSandboxProviderEnvironment` → `{env_vars: map<string, string>}`  
`RotateProviderCredential`, `ConfigureProviderRefresh`, `GetProviderRefreshStatus`  
`ListProviderProfiles`, `GetProviderProfile`, `ImportProviderProfiles`, `LintProviderProfiles`

**Auth:**
`IssueSandboxToken` — bootstrap credential → sandbox JWT  
`RefreshSandboxToken`  
`CreateSshSession` → temporary SSH creds (alphanumeric charset restriction prevents shell injection)  
`RevokeSshSession`

**Relay:**
`ConnectSupervisor` — bidirectional stream; opened by supervisor at startup  
`RelayStream` — bidirectional byte-stream for raw SSH bytes

**Logs:**
`GetSandboxLogs`, `PushSandboxLogs`, `WatchSandbox` (includes `SandboxLogLine`)

**Inference:**
`GetInferenceBundle` → resolved credentials + endpoints

### Auth Model (5 modes)
1. mTLS — local single-user
2. OIDC with bearer tokens — browser or client credentials flow
3. Cloudflare JWT — edge-authenticated deployments
4. Plaintext — local dev / behind trusted reverse proxy
5. Unauthenticated local — trusted k8s environments only

Sandbox-to-gateway: gateway-minted sandbox JWTs (via `IssueSandboxToken`).

SSH sessions: `CreateSshSession` RPC. Alphanumeric charset restriction on response fields prevents shell injection.

mTLS certs stored in k8s secrets (`openshell-server-tls`, `openshell-server-client-ca`, `openshell-client-tls`).

**Notable:** Commit `3f520dd` (2026-05-27) adds "gRPC auth mode + scope + role declared at handler, enforced at router" — signals active auth scoping work but not yet multi-tenant RBAC.

---

## 3. Policy YAML Schema

Version field: `version: 1`

```yaml
version: 1

filesystem_policy:
  include_workdir: bool           # include CWD in landlock allowlist
  read_only: string[]             # paths
  read_write: string[]            # paths

landlock:
  compatibility: best_effort      # enum: best_effort | hard_requirement

process:
  run_as_user: string             # cannot be root/UID 0
  run_as_group: string

network_policies:
  <block_name>:                   # arbitrary key, multiple blocks allowed
    name: string                  # human-readable
    endpoints:
      - host: string              # required; hostname or glob (first-label only)
        port: int                 # scalar TCP port
        ports: int[]              # multiple TCP ports
        allowed_ips: string[]     # CIDR list (SSRF override for private IP space)
        protocol:                 # activates L7 inspection if set
          type: Rest | Sql
          tls: Auto | Skip
          enforcement: Audit | Enforce
        access: read-only         # preset: expands to GET/HEAD/OPTIONS only
        rules:                    # explicit L7 rules (alternative to access preset)
          - allow:
              method: string
              path: string        # glob supported
    binaries:
      - path: string              # exact or glob (e.g., "/usr/lib/node_modules/@openai/**")
    allow_encoded_slash: bool     # preserves %2F (needed for GitLab)
```

### Policy Domains

| Domain | State | Mechanism | Hot-Reloadable |
|---|---|---|---|
| `filesystem_policy` | Locked at sandbox creation | Landlock LSM | No |
| `process` | Locked at sandbox creation | uid/gid + capabilities | No |
| `network_policies` | Runtime | OPA via `regorus` | Yes |
| Inference routing | Runtime | Privacy Router (`inference.local`) | Yes |

### Validation Rules
- `run_as_user` cannot be root or UID 0
- Paths cannot contain `..` or equal `/`
- Wildcard rules: only first DNS label (`*.example.com` ok, `*.com` rejected)
- Policy size limit: 256 KB
- Idempotent: SHA-256 hash of content

### Policy Proposal API (inside sandbox)
`http://policy.local/v1/proposals` — agent submits proposed rules  
`GET /v1/proposals/{chunk_id}/wait?timeout=300` — long-poll until admin approves/rejects

### L7 Denial Response
Sandboxes receive structured `403 policy_denied` on denied L7 requests.  
Denial events batched, flushed to gateway every 10 seconds.

---

## 4. Provider / Credential Injection Model

Providers are named credential bundles. Gateway stores credentials; supervisor fetches via `GetSandboxProviderEnvironment` at runtime; injected as env vars into the initial agent process.

**Credentials never written to sandbox filesystem.** Real values held only in supervisor process memory. Child processes see placeholder strings (`openshell:resolve:env:<VAR_NAME>`). Proxy intercepts outbound requests and replaces placeholders at network layer.

### Provider Types + Injected Env Vars

| Type | Injected Variables |
|---|---|
| `claude` | `ANTHROPIC_API_KEY`, `CLAUDE_API_KEY` |
| `github` | `GITHUB_TOKEN`, `GH_TOKEN` |
| `gitlab` | `GITLAB_TOKEN`, `GLAB_TOKEN`, `CI_JOB_TOKEN` |
| `nvidia` | `NVIDIA_API_KEY` |
| `openai` | `OPENAI_API_KEY` |
| `copilot` | `COPILOT_GITHUB_TOKEN`, `GH_TOKEN`, `GITHUB_TOKEN` |
| `generic` | user-defined variables |

### Refresh Strategies
`STATIC`, `EXTERNAL`, `OAUTH2_REFRESH_TOKEN`, `OAUTH2_CLIENT_CREDENTIALS`, `GOOGLE_SERVICE_ACCOUNT_JWT`

---

## 5. OCSF Log Format

Schema version: OCSF v1.7.0  
Format: JSONL, one record per line  
Log path: `/var/log/openshell-ocsf.YYYY-MM-DD.log`

### Event Classes

| OCSF Class | Class ID | Trigger |
|---|---|---|
| Network Activity | 4001 | TCP connections (L4) |
| HTTP Activity | 4002 | L7 inspected requests |
| SSH Activity | 4007 | Interactive sandbox access |
| Process Activity | 1007 | Sandbox entrypoint |
| Detection Finding | 2004 | Security bypasses |

### Core Fields Populated
`class_uid`, `category_uid`, `action_id`, `disposition_id`, `actor.process`, `dst_endpoint`, `firewall_rule`, `status_detail`

**Constraint:** never log secrets, credentials, bearer tokens, or query parameters in OCSF messages.

### Integration Targets (native OpenShell mentions)
Splunk, Amazon Security Lake, Elastic

---

## 6. Sandbox Lifecycle

### States
`PROVISIONING` → `READY` → `ERROR` → `DELETING` → `UNKNOWN`

### Compute Drivers
Docker, Podman, MicroVM (experimental, libkrun-based), Kubernetes

### Isolation Layers (in order)
1. Landlock LSM — filesystem paths (locked at creation)
2. Non-root execution — `sandbox:sandbox` user/group
3. Seccomp BPF — blocks dangerous syscalls and raw socket paths
4. Network namespace — all egress forced through local policy proxy
5. Policy proxy (OPA engine) — L4 + L7 evaluation

### Pre-installed in default sandbox
Agents: `claude`, `opencode`, `codex`, `copilot`  
Runtimes: Python 3.14, Node 22  
Tools: `gh`, `git`, `vim`, `nano`, `ping`, `dig`, `nslookup`, `nc`, `traceroute`, `netstat`  
Default network: **all outbound traffic blocked** (default-deny)

---

## 7. Persistence Layer

Backend: SQLite (default, single-player) or PostgreSQL (via `--db-url` / `OPENSHELL_DB_URL`)  
Helm default: `sqlite:/var/openshell/openshell.db`, `1Gi` PVC

Migrations in: `./migrations/sqlite` and `./migrations/postgres`

Schema:
- `objects` table: `object_type`, `id`, `name`, `payload`, timestamps
- Policy revisions: `version`, `policy_payload`, `policy_hash`, `status`

**ObjectMeta fields:** `id` (stable, gateway-generated), `name` (unique per type), `created_at_ms` (epoch ms), `labels` (map<string,string>), `resource_version` (CAS counter)

**Critical gap:** No `namespace`, `tenant_id`, or `org_id` field in `ObjectMeta` — flat namespace, single-tenant by design.

---

## 8. Inference Routing

Virtual hostname: `inference.local:443` — bypasses OPA network policy entirely  
Privacy Router strips `authorization`, `x-api-key`, `host` headers and injects real tokens from stored route config.

Supported patterns: `openai_chat_completions`, `openai_completions`, `anthropic_messages`, `model_discovery`  
Idle timeout: 120s (for reasoning models o1/o3)

---

## 9. Python SDK

```python
from openshell import SandboxClient, TlsConfig

client = SandboxClient.from_active_cluster()
# or: SandboxClient(endpoint="https://gateway:8080", tls=TlsConfig(...))

client.health()
ref = client.create(spec=...)
client.list(limit=100, offset=0)
client.delete("sandbox-name")
```

Auto-discovers mTLS certs from `XDG_CONFIG_HOME/openshell/active_gateway/mtls/`

---

## 10. What Is Explicitly Missing for Multi-Tenant Deployment

1. **No tenant/namespace in ObjectMeta** — flat namespace, all objects co-mingled
2. **No RBAC at API layer** — auth exists (OIDC/mTLS) but no permission model on which user can touch which object
3. **No quota/rate-limiting primitives** in API schema
4. **SQLite default** — not suitable for concurrent multi-tenant writes
5. **Single-player explicit** — "one developer, one environment, one gateway"
6. **No multi-gateway coordination** — no tenant-to-gateway routing
7. **Policy proposal SSRF protection** — omits `allowed_ips` by design; multi-tenant network segmentation must be handled externally
8. **Static policy fields immutable** — `filesystem_policy`, `process` locked at creation; no way to update per-tenant baseline without recreating sandbox
9. **VM runtime experimental** — MicroVM driver not production-ready; macOS limited to Apple Silicon only

---

## 11. Stack Decisions (from research)

### IdP: Dex (OIDC broker)
- Single Go binary, runs in docker-compose in under 2 minutes
- Pluggable connectors: static passwords (local dev) → Okta/Azure AD/Google Workspace/LDAP/SAML (prod)
- Entire swap is a Dex config file change; control plane speaks only OIDC
- Keycloak as an optional swap if customer mandates SAML SP

### Control Plane: Python + FastAPI
- ~2.4x faster prototype velocity vs Go for solo builder
- `grpcio` + `grpcio-tools` generates stubs from `.proto` — adequate for control-plane RPS
- Expose REST/JSON via FastAPI for UI/CLI; use gRPC internally for OpenShell
- Contract: `.proto` + OpenAPI spec; Go rewrite is drop-in swap if needed

### Secrets: Infisical (self-hosted)
- `docker compose up` locally; Helm chart for prod
- `SecretProvider` interface makes backend swappable (Infisical / Vault / AWS SM / env)
- HashiCorp Vault BSL license risk; Infisical MIT-ish
- Vault still supported as a swap target if enterprise mandates it

### Database Isolation: Postgres RLS + SQLAlchemy 2.0 + Alembic
- RLS enforced at DB engine — buggy query cannot leak tenant data
- `SET LOCAL app.current_tenant_id` in FastAPI middleware (transaction-scoped, not session-scoped)
- Composite indexes with `tenant_id` as leading column
- Alembic > Aerich for migration maturity

### Audit: OTel Logs + OCSF schema
```
ShellForge event → OCSF JSON → OTel Logger → OTLP → OTel Collector → [Splunk|Elastic|Loki|S3]
```
- OTel Collector handles fan-out; adding new SIEM = adding exporter to Collector config
- OCSF as event schema (v1.7.0, consistent with what OpenShell emits)
- Local dev: Collector → Loki → Grafana
- Hash chain: each ShellForge event includes SHA-256 of previous event for tamper evidence

---

## 12. Helm Chart Details

Chart location in repo: `deploy/helm/openshell/`  
OCI registry: `oci://ghcr.io/nvidia/openshell/helm-chart`  
No semantic version pinned in docs — **pull and pin at first deploy**

Values of interest:
- `server.disableTls: true` — for local dev behind reverse proxy
- `service.type: ClusterIP`
- DB URL: `OPENSHELL_DB_URL=postgresql://...` to swap from SQLite

---

## 13. Community Sandbox Catalog

Repo: `NVIDIA/OpenShell-Community`  
Available sandboxes: `base`, `droid`, `gemini`, `nvidia-gpu`, `ollama`, `sdg`, `pi`  
Usage: `openshell sandbox create --from ollama`  
Format: Dockerfile + optional Python/Shell setup scripts
