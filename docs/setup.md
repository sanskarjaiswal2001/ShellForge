# ShellForge Setup Guide

Step-by-step instructions to bring up the full local stack.

## Prerequisites

| Tool | Version | macOS install |
|---|---|---|
| Docker Desktop | 4.30+ | `brew install --cask docker` |
| Python | 3.12+ | `brew install python@3.12` |
| uv | 0.5+ | `curl -LsSf https://astral.sh/uv/install.sh \| sh` |
| Node | 20+ | `brew install node@20` |
| Helm | 3.14+ (only if testing Helm chart) | `brew install helm` |
| Git | 2.40+ | `brew install git` |

Verify:
```bash
docker --version
uv --version
python3.12 --version
node --version
```

## First-time Setup

```bash
# 1. Clone
git clone <repo-url> shellforge
cd shellforge

# 2. Copy env template
cp .env.example .env
# Edit .env if you want to swap any backend — defaults work out of the box.

# 3. Install control-plane deps
cd control-plane
uv sync
cd ..

# 4. Install web deps (Week 4 — skip for now if not yet built)
# cd web && npm install && cd ..

# 5. Vendor OpenShell protos (Week 2 — skip for now)
# make vendor-protos
# make proto-gen
```

## Running the Stack

```bash
# Bring up infrastructure services (Postgres, Dex, Infisical, OTel, Loki, Grafana, OpenShell)
make up

# Wait for services to be ready, then apply migrations
make migrate

# Seed demo data (3 orgs, 5 users, audit events)
make seed

# Or do all of the above in one shot
make demo
```

Service URLs after `make demo`:

| Service | URL | Notes |
|---|---|---|
| Dashboard | http://localhost:3000 | Built in Week 4 |
| Control API docs | http://localhost:8000/docs | FastAPI auto-generated |
| Dex (OIDC) | http://localhost:5556/dex | Login provider |
| Infisical | http://localhost:8080 | Secrets backend |
| Grafana | http://localhost:3001 | admin/admin |
| OpenShell gRPC | localhost:50051 | Internal — use control plane |

## Running the Control Plane in Dev Mode

The docker-compose stack ships a pre-built control-plane container, but for
active dev you'll want hot-reload:

```bash
# Stop just the container (leaves DB/Dex/etc. running)
docker compose -f deploy/docker-compose.yml stop control-plane

# Run locally with reload
make api-dev
```

## Running Tests

```bash
# Tests require Postgres running and migrations applied.
make up && make migrate

# Then
make api-test
```

## Swapping Backends

### Identity (Dex → Okta)

Edit `deploy/dex/config.yaml`:
1. Remove `staticPasswords` block
2. Uncomment the `connectors:` Okta block, fill in client ID/secret
3. `docker compose restart dex`

No control-plane code changes — Dex is a broker, the control plane only
talks OIDC.

### Secrets (Infisical → Vault)

Edit `.env`:
```
SECRET_BACKEND=vault
VAULT_ADDR=https://vault.corp.local:8200
VAULT_TOKEN=<token>
```

Then implement `src/providers/secrets/vault_provider.py` (currently stubbed).

### SIEM (Loki → Splunk)

Edit `deploy/otel-collector/config.yaml`:
1. Uncomment the `splunk_hec` exporter block
2. Add `splunk_hec` to `service.pipelines.logs.exporters`
3. `docker compose restart otel-collector`

Zero application code changes.

## Resetting

```bash
make clean     # stop + remove all volumes (destroys data)
make demo      # bring up clean stack with fresh seed data
```
