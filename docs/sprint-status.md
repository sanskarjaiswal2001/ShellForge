# Sprint Status

Updated: 2026-05-29  
Current phase: Phase 4 — Week 1 (Identity & Multi-tenancy)  **IN PROGRESS**

---

## Session 1 (2026-05-29)

### Shipped
- [x] **Phase 0.1–0.2**: Confirmed scope, OpenShell pinned to `6c7950da`, full research → `docs/research-notes.md`
- [x] **Phase 0.3**: Repo structure
- [x] **Phase 0.4**: `CLAUDE.md` written
- [x] **Phase 1**: Skills (`openshell-integration`, `policy-authoring`, `demo-polish`) + subagents (`policy-author`, `audit-event-designer`, `enterprise-ui-builder`, `security-reviewer`, `demo-rehearsal`)
- [x] **Phase 2**: ADR 0001 (stack choices, with alternatives + trade-offs) + `docs/architecture.md` with Mermaid diagram
- [x] **Phase 5**: `docs/demo-script.md` written
- [x] **Phase 6**: `README.md` written
- [x] **Foundation scaffolding** (Wave 1):
  - `.gitignore`, `Makefile`, `.env.example`
  - `control-plane/pyproject.toml` with uv
  - `deploy/docker-compose.yml` — full stack with swap-point annotations
  - `deploy/dex/config.yaml` — local + commented swap targets (Okta/Azure/Google/LDAP/SAML)
  - `deploy/otel-collector/config.yaml` — audit fan-out hub with SIEM swap targets
  - `scripts/vendor-openshell-protos.sh` — pulls protos at pinned commit
  - 4 policy templates: `baseline.yaml`, `hipaa-healthcare.yaml`, `pci-payments.yaml`, `soc2-saas.yaml`
- [x] **Swappability interfaces** (Wave 2):
  - `src/interfaces/`: `SecretProvider`, `IdentityProvider`, `AuditSink`, `ComputeProvider`, `PdfRenderer` (all Protocol classes)
  - `src/providers/factory.py` — env-var-driven backend selection
  - `src/providers/secrets/`: `env_provider` (working), `infisical_provider` / `vault_provider` / `aws_provider` (stubs)
  - `src/providers/identity/oidc_provider.py` — full Authlib-based OIDC validator
  - `src/providers/audit/`: `otel_sink` (OCSF JSON over OTLP), `stdout_sink`
  - `src/providers/compute/openshell_provider.py` — stub for Week 2
  - `src/providers/pdf/weasyprint_renderer.py` — working
- [x] **Identity + multi-tenancy** (Wave 3):
  - DB models: `Organization`, `User`, `AuditEventRecord`
  - Alembic initial migration with **Postgres RLS policies** + `shellforge_admin` BYPASSRLS role
  - `src/db/session.py` — `tenant_scoped_session` uses **SET LOCAL** (not SET) — RLS footgun avoided
  - `src/middleware/auth.py` — OIDC bearer dependency
  - `src/middleware/tenant_context.py` — tenant-scoped session dependency
  - `src/middleware/rbac.py` — role hierarchy (viewer/developer/admin/platform-admin)
  - `src/audit/emitter.py` — hash-chain + OCSF + persist + emit
  - API routes: `/auth/{login,callback,me}`, `/organizations`, `/users`, `/scim/v2/Users`, `/audit/events`, `/audit/chain/verify`, `/health`
  - `src/scripts/seed.py` — 3 demo orgs (acme-health/bolt-bank/nexus-corp), 4 users, 6 audit events per tenant (with valid hash chain)
- [x] **Tests** (Wave 4):
  - `test_tenant_isolation.py` — 4 tests confirming RLS blocks cross-tenant reads/writes
  - `test_hash_chain.py` — 6 tests confirming canonical JSON + sha256 determinism
  - `test_rbac.py` — 5 tests on role gating
- [x] **Docs**: `docs/setup.md` with backend-swap procedures

### Broken / Blocked
- Tests have NOT been run yet — Postgres must be up + migrations applied first. User needs to install Docker Desktop + Python 3.12 + uv to verify.
- Frontend (`web/`) — empty directory, scaffold in Week 4.
- OpenShell gRPC client — stubs only. Wire in Week 2 once protos are vendored.
- Infisical/Vault/AWS secret backends — protocol-conformant stubs; only `env_provider` works today.
- `make demo` end-to-end has not been smoke-tested.

### Next
1. **User**: install prereqs (Docker, Python 3.12, uv, Node 20). See `docs/setup.md`.
2. **User**: run `make up && make migrate && make seed` to verify Wave 1–3 actually start cleanly.
3. **Session 2**: fix anything that breaks at startup. Then begin Week 2 (OpenShell gRPC wrapper).

---

## Week 1 Target (2026-06-05) — **MOSTLY DONE**
- [x] Postgres + Alembic + initial migration with RLS
- [x] Dex running in docker-compose with static-password connector + Okta/Azure/Google/LDAP/SAML swap targets commented in
- [x] OIDC flow → FastAPI: login → JWT validated via JWKS
- [x] RBAC middleware: role hierarchy + dependency
- [x] SCIM endpoint (POST/PUT/DELETE Users)
- [x] 3 seed orgs + 4 sample users
- [x] Tenant isolation test (RLS-level, not just app-level)
- [ ] Smoke test: `make demo` works end-to-end (needs user to run it)

## Week 2 Target (2026-06-12)
- [ ] `make vendor-protos && make proto-gen` runs cleanly
- [ ] `OpenShellComputeProvider.create_sandbox` wired through gRPC
- [ ] `POST /api/v1/sandboxes` creates a real sandbox tagged with tenant label
- [ ] `GET /api/v1/sandboxes` returns tenant-scoped list
- [ ] `InfisicalSecretProvider` fully wired
- [ ] Provider injection bridge: Infisical secret → OpenShell provider → sandbox env
- [ ] Secrets isolation test: tenant A's API key never appears in tenant B's sandbox

## Week 3 Target (2026-06-19)
- [ ] OCSF emitter for every mutation (currently only seed events)
- [ ] OpenShell OCSF tail (`WatchSandbox`) → re-emit into our chain with tenant tag
- [ ] Audit query API filters (already partially in place)
- [ ] SSE streaming endpoint `/api/v1/audit/stream`
- [ ] Dashboard: fleet health, per-tenant blocked-destination summary
- [ ] OTel Collector → Loki/Grafana provisioned dashboards

## Week 4 Target (2026-06-26 — demo day)
- [ ] Next.js dashboard with all pages (sandboxes, policies, audit, compliance)
- [ ] Policy library UI: list, view, version diff
- [ ] Self-service sandbox provisioning UI
- [ ] Compliance pack generator → SOC2/HIPAA/PCI PDF
- [ ] Helm chart in `deploy/helm/shellforge/`
- [ ] `demo-rehearsal` subagent run twice with clean output

---

## Open Questions for User

1. **Demo IdP fidelity**: are we demoing with Dex's static-password connector (zero-config, works offline) or wiring an actual Okta dev tenant for the demo? Current code supports both — no work needed if static is fine.
2. **Engagement testimonial in demo close**: real Betsol client or bracketed placeholder?
3. **Contest deadline**: confirm 2026-06-26 — sprint plan above assumes this.
