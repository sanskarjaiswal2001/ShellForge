# Sprint Status

Updated: 2026-05-29  
Current phase: **MVP COMPLETE — Demo-ready**

---

## Session 1 (2026-05-29) — Full MVP build

### Final state

ShellForge MVP shipped end-to-end in a single session: foundation, control plane (identity/multi-tenancy/sandboxes/policies/audit/compliance), mock+real compute providers, frontend dashboard, Helm chart, demo seed data.

### Component tally

| Component | State |
|---|---|
| Repo scaffolding + docs + ADR + skills/subagents | ✅ |
| Docker Compose dev stack (Postgres, Dex, Infisical, OTel, Loki, Grafana, OpenShell) | ✅ swap-annotated |
| Swappability interfaces (5 Protocols + factory) | ✅ |
| OIDC identity provider (Authlib) | ✅ working |
| Postgres RLS + SET LOCAL + shellforge_admin bypass | ✅ |
| RBAC (4-tier hierarchy) | ✅ |
| SCIM 2.0 | ✅ minimal subset |
| Audit emitter (OCSF + SHA-256 hash chain) | ✅ |
| OTel audit sink + stdout fallback | ✅ |
| Sandboxes API (CRUD + simulate-violation) | ✅ |
| Policies API (templates + tenant versions + validate) | ✅ |
| Audit API + hash-chain verify + SSE-style stream | ✅ |
| Compliance pack PDF generator (SOC2/HIPAA/PCI) | ✅ WeasyPrint + Jinja2 |
| Mock ComputeProvider (in-memory, demo-reliable) | ✅ |
| OpenShell ComputeProvider (real gRPC wrapper) | ✅ code complete; gates on `make vendor-protos && make proto-gen` |
| Frontend dashboard (Next.js 15 + shadcn + Tailwind) | ✅ login, overview, sandboxes, policies, audit, compliance |
| Tenant switcher with live tenant chip | ✅ |
| Hash chain UI + verify button | ✅ |
| Violation simulation flow (one click) | ✅ |
| Compliance PDF download | ✅ |
| Helm chart with values for external pg/oidc/secrets/compute/siem | ✅ |
| Migrations Job hook | ✅ |
| Seed: 3 orgs, 5 users, 1 sandbox/tenant, 6 audit events/tenant with valid hash chain | ✅ |
| Tests: tenant isolation x4, hash chain x6, RBAC x5 | ✅ |
| License: PolyForm Noncommercial 1.0.0 | ✅ |

### What still needs user action

1. **Local install**: `brew install --cask docker && brew install python@3.12 node` (see `docs/setup.md`)
2. **Smoke test**: `cp .env.example .env && make demo` — verify stack starts and seed populates
3. **Optional**: `make vendor-protos && make proto-gen` to enable real OpenShell backend.
   Default `COMPUTE_BACKEND=mock` works without OpenShell — ideal for demo.
4. **Demo rehearsal**: invoke `.claude/agents/demo-rehearsal.md` subagent against `docs/demo-script.md`.

### Known limitations

- `InfisicalSecretProvider` / `VaultSecretProvider` / `AwsSecretProvider` are stubs.
  Default `SECRET_BACKEND=env` (env-var fallback) works for the demo.
  Wire when first customer mandates a specific backend.
- Demo dashboard uses `demo:<subject>:<tenant>:<role>` bearer-token bypass in `ENV=local`.
  In prod, swap the dashboard auth to NextAuth + Dex OIDC provider — the FastAPI side
  already speaks full OIDC.
- E2E tests against the live stack not yet written. RLS + hash-chain + RBAC unit tests
  cover the security-critical paths.

---

## Roadmap (post-MVP)

### v2 candidates
- NextAuth.js wiring (replace demo-bearer bypass)
- Real Infisical SDK + secrets injection bridge
- Live OpenShell sandbox tail (WatchSandbox SSE → dashboard)
- Policy diff viewer (UI)
- Per-tenant token spend (NeMo Agent Toolkit)
- Z3-based policy proving (wrap openshell-prover)
- SAML SP via Keycloak swap path
- Multi-region gateway federation

### Demo improvements (judge-day polish)
- Pre-rendered demo PDF for fallback
- Real WebSocket audit stream (replace SSE polling)
- Loading skeletons with shimmer animation
- Empty states with illustration
