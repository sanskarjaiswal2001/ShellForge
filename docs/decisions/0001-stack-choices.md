# ADR 0001: Stack Choices

Date: 2026-05-29  
Status: Proposed — awaiting sign-off  
Author: ShellForge initial session

---

## Context

ShellForge is a 4-week solo build targeting an internal AI innovation contest. The system wraps NVIDIA OpenShell's gRPC API to add multi-tenancy, SSO, audit, and compliance tooling. Constraints:

- Solo developer, 4-week window
- Must demo convincingly on judging day
- Must be architecturally defensible to a Betsol client architect
- Components must be swappable without code changes (client environments vary: Okta vs Azure AD, Vault vs AWS SM, Splunk vs Elastic)
- OpenShell is Rust-based; its gRPC API is the integration point

---

## Decision 1: Control Plane Language — Python + FastAPI

### Options Considered

| Option | Pros | Cons |
|---|---|---|
| **Python + FastAPI** | 2.4x faster prototype velocity; grpcio mature for control-plane RPS; Pydantic v2 = schema-validated API with auto docs; SQLAlchemy 2.0 async ORM; vast ecosystem | Slower than Go at runtime; GIL (mitigated by async) |
| Go | Better gRPC native story; goroutines; single binary deploy | Slower to prototype; ORM ecosystem weaker (sqlc, ent); solo-buildable but slower |

### Decision: Python + FastAPI

Control-plane call volumes (hundreds to low thousands RPS) are well within Python's async capabilities. The value here is schema auto-documentation (FastAPI OpenAPI), Pydantic validation matching OpenShell's proto semantics, and velocity.

**Contract boundary:** `.proto` files are source of truth for the OpenShell interface. FastAPI exports an OpenAPI spec. If a Go rewrite is needed (performance, hiring), it's a drop-in swap — clients speak to the same interface.

**gRPC:** `grpcio` + `grpcio-tools` generates Python stubs from OpenShell's `.proto` files. Adequate for control-plane. FastAPI edge for REST/JSON (dashboard, CLI); gRPC internally for OpenShell calls.

---

## Decision 2: SSO / IdP — Dex (OIDC Broker)

### Options Considered

| Option | Pros | Cons |
|---|---|---|
| **Dex** | Single Go binary; docker-compose ready in 2 min; pluggable connectors (Okta, Azure AD, Google, LDAP, SAML); used by ArgoCD, many k8s stacks | Less UI polish than Keycloak; fewer out-of-box features |
| Keycloak | Full-featured; well-known to enterprise architects; SAML SP support | JVM-heavy; complex config; weeks to tune for prod |
| Authelia | Home-lab focused; simple reverse-proxy auth | No enterprise IdP federation; not B2B SaaS |
| Zitadel | gRPC-native; modern | Cannot consume SAML from upstream (only issues it); blocks legacy Ping/ADFS clients |

### Decision: Dex

Dex's connector model is the key property: swapping from local dev (static passwords) to enterprise prod (Okta OIDC connector) is a Dex YAML config change. The ShellForge control plane speaks only OIDC (`OIDC_ISSUER` env var) — zero code changes for any IdP swap.

Keycloak remains available as a swap target if a specific client mandates SAML SP (Keycloak can consume SAML from Ping/ADFS). In practice, modern enterprise clients use OIDC natively (Okta, Azure AD, Google) and Dex handles them directly.

---

## Decision 3: Tenant Isolation — Postgres RLS + App-Layer Filter

### Options Considered

| Option | Pros | Cons |
|---|---|---|
| Schema-per-tenant | Strong isolation; easy to reason about | Migration hell at 50+ tenants; complex Alembic setup |
| App-layer `org_id` WHERE | Simple; portable | One buggy query = data leak; trust depends on code correctness |
| **Postgres RLS + `SET LOCAL`** | DB-enforced isolation; belt-and-suspenders with app filter; tested pattern at scale | Postgres-specific; `SET LOCAL` vs `SET SESSION` footgun (mitigated by middleware) |

### Decision: Postgres RLS + app-layer filter (belt-and-suspenders)

RLS enforced at the DB engine: a buggy SQLAlchemy query cannot leak tenant data. FastAPI middleware sets `SET LOCAL app.current_tenant_id = :tid` at transaction start (transaction-scoped, not session-scoped — critical for connection pools).

App-layer filter remains as an additional safety net and for readability.

**Critical implementation note:** Always `SET LOCAL`, never `SET`. `SET` persists across the connection pool session; `SET LOCAL` is transaction-scoped. This is the #1 footgun with RLS + pooling.

---

## Decision 4: Secrets Management — Infisical (Self-Hosted)

### Options Considered

| Option | Pros | Cons |
|---|---|---|
| **Infisical** | Self-hosted docker-compose locally; Helm for prod; MIT-ish license; InfisicalSecret CRD for k8s | Smaller ecosystem than Vault; fewer dynamic secret types |
| HashiCorp Vault | Industry standard; dynamic secrets (DB rotation, PKI); enterprise trust | BSL license (post-IBM acquisition); heavy to operate; complex unsealing |
| Doppler | Developer-friendly | Cloud-only SaaS; no self-hosted; violates local dev requirement |
| AWS Secrets Manager | Native AWS integration | Cloud-specific; breaks portability |

### Decision: Infisical with `SecretProvider` interface

Infisical runs in docker-compose locally and deploys via Helm to production. HashiCorp Vault is supported as a swap target (many enterprise security teams mandate it). Doppler is excluded (no self-hosted option).

**Interface:**
```python
class SecretProvider(Protocol):
    def get(self, path: str) -> str: ...
    def get_many(self, paths: list[str]) -> dict[str, str]: ...
```
`SECRET_BACKEND=infisical|vault|aws|env` selects implementation at startup.

---

## Decision 5: Audit Store + Hash Chain — Postgres + OTel + OCSF

### Options Considered

| Option | Pros | Cons |
|---|---|---|
| **Postgres + OTel OTLP + OCSF** | OCSF matches OpenShell's native format; OTel Collector handles SIEM fan-out; adding new SIEM = Collector exporter config | OCSF not yet natively parsed by all SIEMs |
| Splunk HEC direct | Familiar to enterprise security | Splunk-only; forces every client to run Splunk |
| Elastic direct | Open source; good OCSF support | Elastic-only |
| Custom event format | Maximum flexibility | Reinventing OCSF; no native SIEM support |

### Decision: OCSF v1.7.0 schema + OTel OTLP emission + Postgres store + OTel Collector fan-out

OCSF is consistent with what OpenShell natively emits (same schema, same version). Using OTel as the transport means:
- Local dev: Collector → Loki → Grafana
- Enterprise: Collector → Splunk HEC / Elastic / Amazon Security Lake (exporter config, no code changes)

Flat `attributes` block on each OTel log record ensures SIEM compatibility even for SIEMs that don't parse OCSF natively.

Hash chain: SHA-256 of canonical JSON, each event includes `prev_hash`. Tamper detection is a hash recomputation over the stored chain. Stored in Postgres alongside the event for queryability.

---

## Consequences

- Postgres is a hard dependency (SQLite is excluded for production)
- Dex must be available for OIDC to function (stateless control plane cannot issue JWTs itself)
- OpenShell Python SDK (`openshell` PyPI) is vendored at pinned commit — no runtime pip install of latest
- `SET LOCAL` must be enforced in middleware — any code that bypasses the middleware can break tenant isolation
- OTel Collector is required even in local dev (Loki exporter for audit visibility)

---

## Sign-Off Required Before Phase 4

These choices commit the team to:
1. Python as the control-plane language for the 4-week build
2. Dex for local SSO (Keycloak for enterprise SAML SP swap)
3. Postgres RLS + Infisical as the primary data/secret stack
4. OTel + OCSF as the audit pipeline

If any of these are blocked by client/contest constraints, raise before Phase 4 begins.
