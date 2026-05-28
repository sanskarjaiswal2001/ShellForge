.DEFAULT_GOAL := help
.PHONY: help up down restart logs ps clean \
        demo seed reset-data \
        api-dev api-test api-lint api-format api-typecheck \
        migrate migration-new \
        web-dev web-build web-lint \
        proto-gen vendor-protos \
        helm-lint helm-template \
        security-review

# ─────────────────────────────────────────────────────────────────────────────
# Top-level

help: ## Show this help
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / {printf "  \033[36m%-22s\033[0m %s\n", $$1, $$2}' $(MAKEFILE_LIST)

# ─────────────────────────────────────────────────────────────────────────────
# Docker stack

up: ## Start the full local stack (Postgres, Dex, Infisical, OTel, Loki, Grafana, OpenShell)
	docker compose -f deploy/docker-compose.yml up -d
	@echo ""
	@echo "Stack up. URLs:"
	@echo "  Dashboard:   http://localhost:3000"
	@echo "  Control API: http://localhost:8000/docs"
	@echo "  Dex:         http://localhost:5556/dex"
	@echo "  Infisical:   http://localhost:8080"
	@echo "  Grafana:     http://localhost:3001 (admin/admin)"
	@echo "  OpenShell:   grpc://localhost:50051"

down: ## Stop the stack
	docker compose -f deploy/docker-compose.yml down

restart: down up ## Restart the stack

logs: ## Tail stack logs
	docker compose -f deploy/docker-compose.yml logs -f --tail=100

ps: ## Show running services
	docker compose -f deploy/docker-compose.yml ps

clean: ## Stop stack and remove volumes (destroys all data)
	docker compose -f deploy/docker-compose.yml down -v

# ─────────────────────────────────────────────────────────────────────────────
# Demo / seed

demo: up wait-for-ready migrate seed ## Bring up the full demo stack with seed data
	@echo ""
	@echo "═══════════════════════════════════════════════════════════"
	@echo "  ShellForge demo ready"
	@echo "  Login: alice@acme-health.demo / demo1234"
	@echo "  URL:   http://localhost:3000"
	@echo "═══════════════════════════════════════════════════════════"

wait-for-ready:
	@echo "Waiting for services to become ready..."
	@until curl -sf http://localhost:8000/health > /dev/null; do sleep 2; done
	@until curl -sf http://localhost:5556/dex/.well-known/openid-configuration > /dev/null; do sleep 2; done

seed: ## Load demo data (3 orgs, 5 users, audit events)
	cd control-plane && uv run python -m src.scripts.seed

reset-data: clean up wait-for-ready migrate seed ## Wipe and rebuild demo data from scratch

# ─────────────────────────────────────────────────────────────────────────────
# Control plane (Python / FastAPI)

api-dev: ## Run the control plane in dev mode (hot reload)
	cd control-plane && uv run uvicorn src.main:app --reload --host 0.0.0.0 --port 8000

api-test: ## Run control plane tests with coverage
	cd control-plane && uv run pytest tests/ -v --cov=src --cov-report=term-missing --cov-fail-under=80

api-lint: ## Lint control plane
	cd control-plane && uv run ruff check src/ tests/

api-format: ## Format control plane
	cd control-plane && uv run ruff format src/ tests/

api-typecheck: ## Type-check control plane
	cd control-plane && uv run mypy src/

# ─────────────────────────────────────────────────────────────────────────────
# Migrations

migrate: ## Apply database migrations
	cd control-plane && uv run alembic upgrade head

migration-new: ## Create a new migration (usage: make migration-new MSG="add user table")
	cd control-plane && uv run alembic revision --autogenerate -m "$(MSG)"

# ─────────────────────────────────────────────────────────────────────────────
# Frontend

web-dev: ## Run the dashboard in dev mode
	cd web && npm run dev

web-build: ## Build production frontend
	cd web && npm run build

web-lint: ## Lint frontend
	cd web && npm run lint

# ─────────────────────────────────────────────────────────────────────────────
# gRPC / protos

vendor-protos: ## Vendor the OpenShell proto files at the pinned commit
	@mkdir -p vendor/openshell
	@./scripts/vendor-openshell-protos.sh

proto-gen: ## Generate Python gRPC stubs from vendored protos
	@mkdir -p control-plane/src/openshell/proto
	@touch control-plane/src/openshell/proto/__init__.py
	cd control-plane && uv run python -m grpc_tools.protoc \
		-I../vendor/openshell/proto \
		--python_out=src/openshell/proto \
		--grpc_python_out=src/openshell/proto \
		--pyi_out=src/openshell/proto \
		../vendor/openshell/proto/*.proto

# ─────────────────────────────────────────────────────────────────────────────
# Helm

helm-lint: ## Lint the Helm chart
	helm lint deploy/helm/shellforge

helm-template: ## Render Helm chart to stdout
	helm template shellforge deploy/helm/shellforge

# ─────────────────────────────────────────────────────────────────────────────
# Security

security-review: ## Run security-reviewer subagent on staged changes
	@echo "Invoke the security-reviewer subagent via Claude Code before commit."
