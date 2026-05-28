# Policy Authoring Skill

**Trigger:** Any task creating, editing, or validating OpenShell policy YAML — including compliance template generation, policy version diffs, and policy validation.

---

## OpenShell Policy YAML: Full Schema

```yaml
version: 1                          # required

filesystem_policy:                  # STATIC — locked at sandbox creation, cannot update
  include_workdir: bool             # include CWD in landlock allowlist (default: false)
  read_only:                        # paths agent can read but not write
    - /usr
    - /lib
    - /proc/self
    - /etc
  read_write:                       # paths agent can read and write
    - /sandbox
    - /tmp
    - /dev/null

landlock:                           # STATIC
  compatibility: best_effort        # best_effort | hard_requirement

process:                            # STATIC
  run_as_user: sandbox              # cannot be root or UID 0
  run_as_group: sandbox

network_policies:                   # DYNAMIC — hot-reloadable at runtime
  <block_name>:                     # arbitrary key, multiple blocks allowed
    name: string                    # human-readable name
    endpoints:
      - host: api.github.com        # hostname; wildcard in first label only
        port: 443                   # scalar TCP port
        ports: [443, 8443]          # OR multiple ports
        protocol:                   # activates L7 inspection
          type: Rest                # Rest | Sql
          tls: Auto                 # Auto | Skip
          enforcement: Enforce      # Enforce | Audit
        access: read-only           # preset: GET/HEAD/OPTIONS only
        rules:                      # OR explicit L7 rules instead of access preset
          - allow:
              method: POST
              path: "/api/v4/projects/*/repository/files*"
        allowed_ips:                # CIDR allowlist for private IP (SSRF override)
          - "10.42.0.0/16"
        allow_encoded_slash: bool   # preserve %2F (needed for GitLab)
    binaries:                       # which processes may use this endpoint
      - path: /usr/bin/curl
      - path: "/usr/lib/node_modules/@openai/**"  # glob supported
```

### Wildcard Rules for `host`
- `*.example.com` — matches `api.example.com` (single first label)
- `**.example.com` — matches `a.b.example.com` (recursive)
- `*-aiplatform.googleapis.com` — intra-label wildcard (valid)
- `*.com` — **REJECTED** (TLD wildcards forbidden)
- `inference.local` — bypasses OPA entirely (inference router)

### Validation Constraints
- `run_as_user` cannot be root or UID 0
- Paths: no `..`, no path equal to `/`
- Policy size: 256 KB max
- SSRF: RFC 1918 ranges blocked by default unless `allowed_ips` specified
- Wildcard: only in first DNS label

---

## Compliance Policy Templates

### Template: Baseline (no compliance regime)

```yaml
version: 1

filesystem_policy:
  include_workdir: true
  read_only: [/usr, /lib, /proc/self, /etc, /var/log]
  read_write: [/sandbox, /tmp, /dev/null]

landlock:
  compatibility: best_effort

process:
  run_as_user: sandbox
  run_as_group: sandbox

network_policies:
  package_registries:
    name: "Package Registries"
    endpoints:
      - host: "*.npmjs.com"
        port: 443
        protocol: { type: Rest, tls: Auto, enforcement: Enforce }
        access: read-only
      - host: "*.pypi.org"
        port: 443
        protocol: { type: Rest, tls: Auto, enforcement: Enforce }
        access: read-only
  github:
    name: "GitHub"
    endpoints:
      - host: github.com
        port: 443
        protocol: { type: Rest, tls: Auto, enforcement: Enforce }
        rules:
          - allow: { method: GET, path: "/*" }
          - allow: { method: POST, path: "/*/git-upload-pack" }
        binaries:
          - { path: /usr/bin/git }
          - { path: /usr/bin/gh }
```

### Template: HIPAA (healthcare AI agent)

Compliance controls satisfied: HIPAA §164.312(a)(1), §164.312(e)(2)(ii), §164.308(a)(1)

```yaml
version: 1

filesystem_policy:
  include_workdir: true
  read_only: [/usr, /lib, /proc/self, /etc]
  read_write: [/sandbox, /tmp]
  # No /dev/null write — prevent data destruction

landlock:
  compatibility: hard_requirement    # HIPAA: cannot degrade to permissive mode

process:
  run_as_user: sandbox
  run_as_group: sandbox

network_policies:
  # HIPAA §164.312(e)(2)(ii): Encrypt in transit
  # All endpoints must use tls: Auto (terminate) to enforce TLS inspection
  anthropic_inference:
    name: "Anthropic API (HIPAA - PHI must not leave)"
    endpoints:
      - host: api.anthropic.com
        port: 443
        protocol: { type: Rest, tls: Auto, enforcement: Enforce }
        rules:
          - allow: { method: POST, path: "/v1/messages" }
        binaries:
          - { path: /sandbox/.venv/bin/python }
  github_scm:
    name: "GitHub SCM (code only, no PHI)"
    endpoints:
      - host: github.com
        port: 443
        protocol: { type: Rest, tls: Auto, enforcement: Enforce }
        rules:
          - allow: { method: GET, path: "/*" }
          - allow: { method: POST, path: "/*/git-upload-pack" }
        binaries:
          - { path: /usr/bin/git }
  # All other outbound: blocked (default-deny)
  # No wildcard rules — HIPAA requires explicit allowlist
```

HIPAA control annotations:
- `hard_requirement` landlock → §164.312(c)(1): Integrity controls cannot be bypassed
- `tls: Auto` on all endpoints → §164.312(e)(2)(ii): Encryption in transit
- Explicit allowlist, no wildcards → §164.312(a)(1): Access control
- Default-deny → §164.308(a)(1): Risk management

### Template: PCI-DSS (payment card processing)

Controls: PCI DSS v4.0 Requirements 1.3, 6.4, 7.2

```yaml
version: 1

filesystem_policy:
  include_workdir: true
  read_only: [/usr, /lib, /proc/self, /etc]
  read_write: [/sandbox/workspace, /tmp]
  # No /root, no /home/sandbox (PCI 3.4: no persistent CHD storage)

landlock:
  compatibility: hard_requirement    # PCI 1.3: no exceptions to network controls

process:
  run_as_user: sandbox
  run_as_group: sandbox

network_policies:
  payment_processor:
    name: "Payment Processor API (PCI segmented)"
    endpoints:
      - host: api.stripe.com          # or Braintree/Adyen — specify exactly
        port: 443
        protocol: { type: Rest, tls: Auto, enforcement: Enforce }
        rules:
          - allow: { method: GET, path: "/v1/charges*" }
          - allow: { method: POST, path: "/v1/payment_intents" }
        binaries:
          - { path: /sandbox/.venv/bin/python }
  internal_services:
    name: "Internal CDE Services (RFC 1918)"
    endpoints:
      - host: payments-internal.corp.local
        port: 8443
        allowed_ips: ["10.0.0.0/8"]   # PCI: explicit CIDR, not open RFC 1918
        protocol: { type: Rest, tls: Auto, enforcement: Enforce }
        access: read-only
  scm:
    name: "Source Control"
    endpoints:
      - host: github.com
        port: 443
        protocol: { type: Rest, tls: Auto, enforcement: Enforce }
        rules:
          - allow: { method: GET, path: "/*" }
          - allow: { method: POST, path: "/*/git-upload-pack" }
        binaries:
          - { path: /usr/bin/git }
```

### Template: SOC 2 Type II

Controls: CC6.1, CC6.6, CC6.7, CC7.2

```yaml
version: 1

filesystem_policy:
  include_workdir: true
  read_only: [/usr, /lib, /proc/self, /etc, /var/log]
  read_write: [/sandbox, /tmp]

landlock:
  compatibility: best_effort         # SOC2 CC6.1: reasonable, not absolute

process:
  run_as_user: sandbox
  run_as_group: sandbox

network_policies:
  # CC6.6: Logical access restricted to authorized communications
  # CC6.7: Transmissions over public networks protected
  package_registries:
    name: "Package Registries (CC6.6)"
    endpoints:
      - host: "*.npmjs.com"
        port: 443
        protocol: { type: Rest, tls: Auto, enforcement: Audit }  # Audit for SOC2 evidence
        access: read-only
      - host: "*.pypi.org"
        port: 443
        protocol: { type: Rest, tls: Auto, enforcement: Audit }
        access: read-only
  ai_providers:
    name: "AI Provider APIs (CC6.7)"
    endpoints:
      - host: api.anthropic.com
        port: 443
        protocol: { type: Rest, tls: Auto, enforcement: Enforce }
        rules:
          - allow: { method: POST, path: "/v1/messages" }
  github:
    name: "GitHub (CC6.6)"
    endpoints:
      - host: github.com
        port: 443
        protocol: { type: Rest, tls: Auto, enforcement: Audit }
        access: read-only
      - host: github.com
        port: 443
        protocol: { type: Rest, tls: Auto, enforcement: Enforce }
        rules:
          - allow: { method: POST, path: "/*" }
        binaries:
          - { path: /usr/bin/git }
```

---

## Compliance Control Mapping

| Policy Field | HIPAA | PCI DSS v4 | SOC 2 |
|---|---|---|---|
| `landlock: hard_requirement` | §164.312(c)(1) | Req 1.3.1 | CC6.1 |
| `tls: Auto` on all endpoints | §164.312(e)(2)(ii) | Req 4.2.1 | CC6.7 |
| Explicit allowlist (no wildcards) | §164.312(a)(1) | Req 1.3 | CC6.6 |
| Default-deny network | §164.308(a)(1) | Req 1.3.2 | CC6.6 |
| `enforcement: Audit` | §164.312(b) | Req 10.2 | CC7.2 |
| `enforcement: Enforce` on sensitive | §164.312(a)(1) | Req 6.4 | CC6.1 |
| No write to sensitive paths | §164.312(c)(1) | Req 3.4 | CC6.1 |

---

## Common Policy Mistakes

1. **Overly permissive network block** — `host: "*"` catches anything, then OPA evaluates; use specific hosts
2. **Missing `binaries` restriction** — without `binaries`, ANY process can use the endpoint
3. **Using `tls: Skip`** — defeats MITM inspection, breaks HIPAA/PCI compliance evidence
4. **Wildcard in non-first label** — `api.*.example.com` is rejected; must be `*.example.com`
5. **Missing `allowed_ips` for private hosts** — RFC 1918 blocked by default; `allowed_ips` required
6. **`enforcement: Audit` only for sensitive paths** — audit logs but doesn't block; use `Enforce` for compliance
7. **Forgetting `allow_encoded_slash: true`** for GitLab (breaks path routing without it)
8. **Not using `hard_requirement`** for regulated sandboxes — `best_effort` may silently downgrade

---

## Validation Steps (run before applying)

```bash
# Size check
wc -c policy.yaml  # must be < 262144 bytes (256 KB)

# Basic YAML validity
python -c "import yaml; yaml.safe_load(open('policy.yaml'))"

# OpenShell validation (if gateway is running)
openshell policy set --policy policy.yaml --wait [sandbox-name]

# ShellForge validation endpoint
POST /api/v1/policies/validate
Content-Type: application/json
{"yaml": "<policy yaml string>"}
```
