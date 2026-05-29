# ShellForge Setup Guide

Step-by-step instructions to bring up the full local stack on macOS.

## Prerequisites

| Tool | Version | macOS install |
|---|---|---|
| Podman | 5+ | `brew install podman` (Docker Desktop is paid for commercial use) |
| Python | 3.12+ | `brew install python@3.12` |
| uv | 0.5+ | `curl -LsSf https://astral.sh/uv/install.sh \| sh` |
| Node | 20+ | `brew install node@20` |
| Pango | 1.50+ | `brew install pango` (WeasyPrint runtime dep) |
| Helm | 3.14+ (only if testing Helm chart) | `brew install helm` |
| Git | 2.40+ | `brew install git` |

Initialize Podman VM:
```bash
podman machine init --cpus 4 --memory 6144 --disk-size 50
podman machine start
```

## First-time Setup

```bash
# 1. Clone
git clone git@github.com:sanskarjaiswal2001/ShellForge.git
cd ShellForge

# 2. Copy env template
cp .env.example .env
# Edit .env if you want to swap any backend — defaults work out of the box.

# 3. Install control-plane deps
cd control-plane
uv sync
cd ..

# 4. Install web deps
cd web
npm install
cd ..

# 5. (optional) Vendor OpenShell protos to enable real OpenShell backend
# COMPUTE_BACKEND=mock works without OpenShell — perfect for demo.
# make vendor-protos && make proto-gen
```

## Running the Stack

```bash
# 1. Bring up infrastructure containers (Podman / Docker auto-detected)
make up

# 2. Apply DB migrations (creates RLS policies, app role, etc.)
make migrate

# 3. Seed demo data (3 orgs, 4 users, 3 sandboxes, 18 audit events)
make seed

# 4. Start the control plane (separate terminal, for hot reload)
DYLD_FALLBACK_LIBRARY_PATH=$(brew --prefix)/lib make api-dev

# 5. Start the dashboard (separate terminal)
make web-dev
```

Or just `make demo` for steps 1-3 in one shot.

Service URLs:

| Service | URL | Notes |
|---|---|---|
| Dashboard | http://localhost:3000 | Login via demo user picker |
| Control API docs | http://localhost:8000/docs | FastAPI auto-generated |
| Dex (OIDC) | http://localhost:5556/dex | OIDC issuer |
| Infisical | http://localhost:8080 | Secrets backend |
| Grafana | http://localhost:3001 | admin/admin |
| OpenShell gRPC | localhost:50051 | Opt-in: `podman compose --profile openshell up -d` |

## Why two database users?

ShellForge enforces tenant isolation via Postgres Row-Level Security.
Superusers ALWAYS bypass RLS, and Postgres refuses to drop superuser from
its bootstrap user. So:

- **`shellforge`** (POSTGRES_USER): bootstrap superuser. Used ONLY by
  Alembic migrations. Set via `ALEMBIC_DATABASE_URL`.
- **`shellforge_app`** (created by migration 0005): regular login role,
  NOSUPERUSER + NOBYPASSRLS. Used by the FastAPI runtime. Set via
  `DATABASE_URL`.
- **`shellforge_admin`** (NOLOGIN, BYPASSRLS): explicit-bypass role for
  cross-tenant operations (seed script, platform-admin endpoints). Code
  switches into this via `SET LOCAL ROLE shellforge_admin`.

## Why DYLD_FALLBACK_LIBRARY_PATH?

WeasyPrint (PDF renderer) needs Pango / GLib / Cairo at runtime. On macOS,
Homebrew installs these in `/opt/homebrew/lib` which is not on the default
`dyld` search path. Set `DYLD_FALLBACK_LIBRARY_PATH=$(brew --prefix)/lib`
when running the control plane locally.

In production (Linux containers) Pango is installed system-wide and this
env var is not needed.

## Swapping Backends

### Identity (Dex → Okta)

Edit `deploy/dex/config.yaml`:
1. Remove `staticPasswords` block
2. Uncomment the `connectors:` Okta block, fill in client ID/secret
3. `podman compose restart dex` (or `docker compose restart dex`)

No control-plane code changes. Dex is a broker; control plane only speaks OIDC.

### Secrets (Infisical → Vault)

Edit `.env`:
```
SECRET_BACKEND=vault
VAULT_ADDR=https://vault.corp.local:8200
VAULT_TOKEN=<token>
```

Wire `src/providers/secrets/vault_provider.py` (currently stubbed).

### Compute (mock → real OpenShell)

```
make vendor-protos     # pulls OpenShell .proto files at pinned commit
make proto-gen         # generates Python gRPC stubs
# edit .env:
COMPUTE_BACKEND=openshell
# bring up OpenShell:
podman compose --profile openshell up -d openshell-gateway
```

### SIEM (Loki → Splunk)

Edit `deploy/otel-collector/config.yaml`:
1. Uncomment the `splunk_hec` exporter block
2. Add `splunk_hec` to `service.pipelines.logs.exporters`
3. `podman compose restart otel-collector`

Zero application code changes.

## Resetting

```bash
make clean     # stop + remove all volumes (destroys data)
make demo      # bring up clean stack with fresh seed data
```

## Troubleshooting

### `make up` fails with "Cannot connect to the Docker daemon"
You're using Docker Desktop and it's not running. Start it or switch to Podman:
```bash
brew install podman
podman machine init && podman machine start
```

### `make up` fails with "unknown shorthand flag: 'f'"
The compose plugin is missing. Either:
- Symlink standalone binary: `ln -sf $(brew --prefix)/bin/docker-compose ~/.docker/cli-plugins/docker-compose`
- Or use Podman (`brew install podman`) — Makefile auto-detects.

### Control plane crashes with "cannot load library 'libgobject-2.0-0'"
Pango not installed or DYLD path missing:
```bash
brew install pango
DYLD_FALLBACK_LIBRARY_PATH=$(brew --prefix)/lib make api-dev
```

### Tenant data leaking across orgs in queries
You're connecting as a Postgres superuser. RLS is bypassed unconditionally
for superusers. Confirm `DATABASE_URL` uses `shellforge_app`, not `shellforge`.
