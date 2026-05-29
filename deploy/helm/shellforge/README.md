# ShellForge Helm Chart

Deploys the ShellForge control plane + dashboard to any Kubernetes cluster.

## Installation

```bash
helm install shellforge ./deploy/helm/shellforge \
  --namespace shellforge --create-namespace \
  -f my-values.yaml
```

## Required values

The chart does NOT ship Postgres, OIDC, or OpenShell — it expects you to
provide externally-managed services. The minimum `my-values.yaml`:

```yaml
database:
  url: "postgresql+asyncpg://shellforge:****@postgres.svc:5432/shellforge"

oidc:
  issuer: "https://yourtenant.okta.com"
  clientId: "shellforge"
  clientSecret: "****"
  redirectUri: "https://shellforge.example.com/auth/callback"

audit:
  otelEndpoint: "http://otel-collector.observability:4317"

compute:
  openshell:
    endpoint: "openshell-gateway.openshell:50051"
```

## Backend swaps

| Component | Swap via |
|---|---|
| Postgres | `database.url` |
| IdP | `oidc.issuer` (any RFC-6749 OIDC issuer) |
| Secrets | `secrets.backend` (infisical/vault/aws) |
| Compute | `compute.backend` (openshell/mock) |
| Audit SIEM | `audit.otelEndpoint` + OTel Collector exporter config |

## Render without installing

```bash
helm template shellforge ./deploy/helm/shellforge -f my-values.yaml
```
