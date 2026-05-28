# ShellForge — Project Memory

Read this at the start of every session. Update `docs/sprint-status.md` at end of every session.

---

## What ShellForge Is

Enterprise control plane wrapping NVIDIA OpenShell (alpha, single-player) into a multi-tenant, SSO-enabled, audit-ready, Helm-deployable platform for AI coding agents in regulated client environments.

**Competitive wedge:** Any rival can demo agent spawning. ShellForge makes agents deployable in actual client production (multi-tenancy, SSO/RBAC, tamper-evident audit, compliance packs).

**Demo stack (3 fake orgs always present):**
- `acme-health` — HIPAA policy sandbox
- `bolt-bank` — PCI policy sandbox  
- `nexus-corp` — SOC2 policy sandbox

---

## OpenShell Integration

**Pinned commit:** `6c7950da900921a24aa65e79c7b522ba12fd7875` (2026-05-27)  
**Helm chart:** `oci://ghcr.io/nvidia/openshell/helm-chart` (pin version at first pull)  
**Python SDK:** `openshell` PyPI package

**Rule:** Wrap, never fork. All OpenShell interaction goes through `control-plane/src/openshell/client.py` (`OpenShellClient` class). Never call `openshell` SDK directly from business logic.

**Key OpenShell concepts:**
- Gateway = OpenShell's API server (gRPC + REST)
- Sandbox = isolated agent runtime with Landlock/seccomp/network namespace + OPA proxy
- Provider = named credential bundle injected as env vars into sandbox
- Policy = YAML defining filesystem (static), network (hot-reload), process (static) rules
- ObjectMeta has no tenant/namespace field — ShellForge adds tenant isolation above OpenShell

---

## Tenant Isolation Invariant (SACRED)

**Every database query MUST filter by `organization_id`.** No exceptions.

Implementation:
- FastAPI middleware sets `SET LOCAL app.current_tenant_id = :tid` (transaction-scoped, never session-scoped)
- Postgres RLS policies reference `current_setting('app.current_tenant_id')`
- App-layer SQLAlchemy queries also filter by `organization_id` (belt-and-suspenders)
- Composite indexes: `tenant_id` as leading column on all tenant-scoped tables

Run `security-reviewer` subagent before ANY commit touching auth, secrets, or data access.

---

## Stack

### Control Plane
- Language: **Python 3.12+**
- Framework: **FastAPI** (async, OpenAPI auto-docs)
- ORM: **SQLAlchemy 2.0** (async) + **Alembic** migrations
- DB: **PostgreSQL** with RLS
- gRPC client: **grpcio** + **grpcio-tools** (stubs generated from OpenShell `.proto`)
- Validation: **Pydantic v2**
- Runtime: **uvicorn** + **gunicorn**

### Secrets
- **Infisical** (self-hosted docker-compose locally; Helm for prod)
- Interface: `SecretProvider` protocol in `control-plane/src/secrets/provider.py`
- Swap: `SECRET_BACKEND=infisical|vault|aws|env` env var

### Identity / SSO
- **Dex** (OIDC broker)
- Local dev: Dex static passwords connector
- Prod: Dex → Okta/Azure AD/Google Workspace connector (config-only swap)
- Keycloak optional swap if customer mandates SAML SP
- Interface: control plane speaks OIDC only — `OIDC_ISSUER` env var, never IdP-specific SDK

### Frontend
- **Next.js 15** (App Router, server components preferred)
- **shadcn/ui** + **Tailwind CSS**
- **Zod** for form validation
- Every page: loading + empty + error states
- Tables: server-side pagination
- No `console.log` in production code

### Audit
- Event schema: **OCSF v1.7.0** (consistent with OpenShell's native logs)
- Emission: **OpenTelemetry Logs (OTLP)**
- Pipeline: `ShellForge event → OCSF JSON → OTel Logger → OTLP → OTel Collector → SIEM`
- Hash chain: each event includes SHA-256 of previous event (tamper evidence)
- Local dev: OTel Collector → Loki → Grafana
- Enterprise swap: add exporter to Collector config (Splunk HEC, Elastic, Amazon Security Lake)

### Container / Infra
- Local dev: `docker-compose.yml`
- Prod: Helm chart in `deploy/helm/`
- `make demo` → working stack with seed data in 3 commands

---

## Commands

```bash
# Local dev
make up          # docker-compose up (DB, Dex, Infisical, OpenShell, OTel, Loki, Grafana)
make down        # docker-compose down
make seed        # load 3 orgs, 5 users, 10 audit events, 2 policy violations
make demo        # up + seed (one command for judging day)

# Control plane
cd control-plane
uv run alembic upgrade head       # run migrations
uv run uvicorn src.main:app --reload
uv run pytest tests/ -v --cov=src --cov-report=term-missing

# Generate gRPC stubs from OpenShell protos
make proto-gen

# Lint / format
uv run ruff check src/ tests/
uv run ruff format src/ tests/
uv run mypy src/

# Frontend
cd web
npm run dev
npm run build
npm run lint
```

---

## Commit Style

Conventional commits. No attribution suffix (disabled globally).

```
feat: add tenant-scoped sandbox listing endpoint
fix: prevent cross-tenant provider env var leak
refactor: extract SecretProvider interface
test: add isolation tests for acme-health/bolt-bank boundary
chore: pin OpenShell commit to 6c7950d
```

One commit per logical unit, not per session.

---

## Subagent Invocation Guide

| Task | Invoke |
|---|---|
| Any OpenShell gRPC / sandbox lifecycle code | `openshell-integration` skill |
| Create/edit/validate policy YAML | `policy-author` subagent |
| Design audit event schema or SIEM mapping | `audit-event-designer` subagent |
| Build dashboard UI pages | `enterprise-ui-builder` subagent |
| Any commit touching auth/secrets/data access | `security-reviewer` subagent (MANDATORY) |
| Demo script, seed data, UI polish | `demo-polish` skill |
| Pre-merge validation of demo path | `demo-rehearsal` subagent |

---

## Architecture Overview

```
Browser/CLI
    │ OIDC (Dex)
    ▼
FastAPI Control Plane ──── Postgres (RLS) ──── Alembic
    │                           │
    │                      Infisical (secrets)
    │
    ├── gRPC ──► OpenShell Gateway ──► Sandbox [Agent]
    │               (pinned commit)
    │
    └── OTel ──► OTel Collector ──► Loki/Grafana (local)
                                 └─► Splunk/Elastic (prod)
```

---

## Session Protocol

**Start of session:**
1. Read this file
2. Read `docs/sprint-status.md`
3. Check current week's target

**End of session:**
1. Update `docs/sprint-status.md` (what shipped, what's broken, what's next)
2. Commit everything in logical units
3. Note any scope creep decisions
