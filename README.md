# ShellForge

Enterprise control plane for NVIDIA OpenShell — multi-tenant, SSO-enabled, audit-ready, Helm-deployable.

## Problem

NVIDIA OpenShell is alpha software, single-player mode. It provides powerful AI agent sandboxing (Landlock, seccomp, OPA network policy) but lacks everything regulated enterprises need: multi-tenancy, SSO/RBAC, tamper-evident audit logging, compliance reporting, and production Helm packaging. Any Betsol client wanting to deploy AI coding agents needs what OpenShell isn't shipping yet.

## Solution

ShellForge is the production control plane that sits above OpenShell. It adds:

- **Multi-tenancy** — hard tenant isolation via Postgres RLS, every OpenShell resource labeled and scoped per org
- **SSO/RBAC** — OIDC via Dex (pluggable: Okta, Azure AD, Google Workspace, LDAP, SAML)
- **Audit trail** — OCSF v1.7.0 events with SHA-256 hash chain, streamed via OpenTelemetry to any SIEM
- **Compliance packs** — one-click SOC2/HIPAA/PCI evidence PDF with control-to-event mapping
- **Policy management** — compliance policy templates (HIPAA, PCI, SOC2, baseline), version history, self-service provisioning
- **Helm chart** — `values.yaml` slots for external Postgres, Vault/Infisical, OIDC issuer, SIEM target

## Architecture

```
Browser/CLI
    │ OIDC (Dex → Okta/Azure AD/Google/LDAP)
    ▼
┌─────────────────────────────────────────────────────┐
│  FastAPI Control Plane                              │
│  ┌──────────┐  ┌──────────┐  ┌─────────────────┐  │
│  │ Auth/RBAC│  │ Tenants  │  │ Policy Library  │  │
│  │ (Dex/JWT)│  │ (Pg RLS) │  │ (YAML templates)│  │
│  └──────────┘  └──────────┘  └─────────────────┘  │
└────────────────────────┬────────────────────────────┘
                         │ gRPC (mTLS or OIDC bearer)
                         ▼
              OpenShell Gateway
              (pinned commit 6c7950d)
                         │
                         ▼
              Sandbox [Agent: claude/codex/...]
              (Landlock + seccomp + OPA network proxy)
                         │ OCSF logs
                         ▼
              OTel Collector ──► Loki/Grafana (local)
                              └─► Splunk HEC / Elastic (prod)
```

## Quickstart

```bash
git clone https://github.com/betsol/shellforge
cd shellforge
make demo
```

`make demo` starts the full stack (Postgres, Dex, Infisical, OpenShell, OTel Collector, Loki, Grafana) and seeds 3 demo orgs (acme-health, bolt-bank, nexus-corp) with users, sandboxes, and audit events.

Dashboard: http://localhost:3000  
Login: `alice@acme-health.demo` / `demo1234`

## Roadmap

### MVP (this submission)
- Multi-tenant identity + RBAC (Dex OIDC, Postgres RLS)
- Sandbox lifecycle management (OpenShell gRPC wrapper)
- Policy templates: baseline, HIPAA, PCI, SOC2
- OCSF audit events with hash chain
- Compliance pack PDF generator
- docker-compose dev stack + Helm chart skeleton

### v2
- Per-tenant token spend billing (NeMo Agent Toolkit integration)
- Formal policy verification (Z3 SMT prover integration, wrapping OpenShell's `openshell-prover`)
- Multi-region gateway federation
- Terraform provider
- SCIM 2.0 enterprise provisioning

## Credits

Sandbox runtime: [NVIDIA OpenShell](https://github.com/NVIDIA/OpenShell) (Apache 2.0)  
ShellForge adds the enterprise control plane above it.
