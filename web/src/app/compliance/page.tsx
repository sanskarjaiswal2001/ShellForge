"use client";

import { useState } from "react";
import { FileSignature, Download, ShieldCheck, Lock, FileText } from "lucide-react";
import { AppShell } from "@/components/app-shell";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { getBearer } from "@/lib/session";

interface ControlInfo {
  id: string;
  title: string;
  desc: string;
  evidence: string;
}

interface FrameworkInfo {
  id: "soc2" | "hipaa" | "pci";
  title: string;
  subtitle: string;
  blurb: string;
  controls: ControlInfo[];
  whoNeedsThis: string;
}

const FRAMEWORKS: FrameworkInfo[] = [
  {
    id: "soc2",
    title: "SOC 2 Type II",
    subtitle: "AICPA Trust Services Criteria — Security, Availability, Confidentiality",
    blurb:
      "Annual third-party attestation that your service handles customer data securely. The de-facto standard required by enterprise SaaS buyers before signing a contract.",
    whoNeedsThis:
      "Any SaaS startup selling to mid-market+ companies. Banks, healthcare buyers, and tech enterprises will block procurement without a current SOC 2 Type II report.",
    controls: [
      {
        id: "CC6.1",
        title: "Logical Access Controls",
        desc: "Restrict logical access to information assets via authentication and authorization.",
        evidence:
          "Sandbox creation events with actor identity + role, RBAC enforcement records, and JWT-validated session bindings.",
      },
      {
        id: "CC6.6",
        title: "Authorized Communications",
        desc: "Logical access to system components is restricted to authorized users and processes only.",
        evidence:
          "Network policy enforcement events (allow/audit/deny) per sandbox, with binary-restricted endpoint allowlists.",
      },
      {
        id: "CC6.7",
        title: "Transmission of Data",
        desc: "Restricts transmission of data and removal of confidential information to authorized internal/external users.",
        evidence:
          "TLS-enforced egress on all policy endpoints (tls: Auto), MITM-inspected L7 traffic, blocked exfiltration attempts.",
      },
      {
        id: "CC7.2",
        title: "Detection of Anomalies",
        desc: "Monitors the system for anomalies that are indicative of malicious acts, natural disasters, or errors.",
        evidence:
          "BLOCKED OCSF events on policy violations, real-time audit feed, hash-chain tamper detection.",
      },
      {
        id: "CC8.1",
        title: "Change Management",
        desc: "Authorizes, designs, develops, configures, documents, tests, approves, and implements changes.",
        evidence:
          "Policy version history with SHA-256 hashes, who/when/what for every policy adoption, immutable audit log.",
      },
    ],
  },
  {
    id: "hipaa",
    title: "HIPAA",
    subtitle: "Health Insurance Portability and Accountability Act — 45 CFR Part 164",
    blurb:
      "US federal law governing Protected Health Information (PHI). Anyone touching patient data — hospitals, payers, healthtech, and their business associates — must comply.",
    whoNeedsThis:
      "Any company processing US patient data: EHRs, telehealth, healthtech AI, insurance, claims processing, clinical-trial software. BAA required with every vendor.",
    controls: [
      {
        id: "§164.308(a)(1)",
        title: "Security Management Process",
        desc: "Implement policies and procedures to prevent, detect, contain, and correct security violations.",
        evidence:
          "Default-deny network policy, mandatory policy adoption per sandbox, automated violation detection.",
      },
      {
        id: "§164.308(a)(4)",
        title: "Information Access Management",
        desc: "Authorize access to PHI consistent with the workforce member's role.",
        evidence:
          "RBAC role assignments, sandbox provisioning audit records, deprovisioning on sandbox delete.",
      },
      {
        id: "§164.312(a)(1)",
        title: "Access Control",
        desc: "Implement technical policies and procedures to allow access only to authorized persons or programs.",
        evidence:
          "Tenant-scoped sandbox isolation via Postgres RLS, OIDC-validated user identity on every request.",
      },
      {
        id: "§164.312(b)",
        title: "Audit Controls",
        desc: "Implement mechanisms to record and examine activity in systems containing or using ePHI.",
        evidence:
          "OCSF v1.7.0 audit log with hash-chained integrity, every mutation recorded with actor + resource.",
      },
      {
        id: "§164.312(c)(1)",
        title: "Integrity Controls",
        desc: "Protect ePHI from improper alteration or destruction.",
        evidence:
          "Landlock hard_requirement (cannot degrade), filesystem write paths restricted, SHA-256 chain detects tampering.",
      },
      {
        id: "§164.312(d)",
        title: "Person/Entity Authentication",
        desc: "Verify that persons or entities seeking access are who they claim to be.",
        evidence:
          "OIDC JWT validation (Dex, Okta, Azure AD), refreshed JWKS, SCIM provisioning records.",
      },
      {
        id: "§164.312(e)(2)(ii)",
        title: "Encryption in Transit",
        desc: "Implement a mechanism to encrypt ePHI whenever deemed appropriate.",
        evidence:
          "tls: Auto on every network policy endpoint enforces TLS termination + MITM inspection.",
      },
    ],
  },
  {
    id: "pci",
    title: "PCI DSS v4.0",
    subtitle: "Payment Card Industry Data Security Standard",
    blurb:
      "Mandatory for any company that stores, processes, or transmits cardholder data (CHD) or sensitive authentication data. Enforced by Visa/Mastercard/Amex/Discover via the card brands.",
    whoNeedsThis:
      "Anyone touching credit-card numbers: e-commerce, fintechs, payment processors, billing platforms. Annual ROC (Report on Compliance) or SAQ required.",
    controls: [
      {
        id: "Req 1.3",
        title: "Restrict Inbound/Outbound Traffic",
        desc: "Restrict inbound and outbound traffic to that which is necessary for the CDE.",
        evidence:
          "Default-deny egress policy with explicit allowlist per sandbox; CIDR-restricted access to internal CDE services.",
      },
      {
        id: "Req 3.4",
        title: "PAN Protection",
        desc: "PAN is rendered unreadable anywhere it is stored.",
        evidence:
          "Sandbox filesystem policy restricts writable paths; no persistent storage of CHD outside CDE-approved paths.",
      },
      {
        id: "Req 4.2.1",
        title: "Strong Cryptography in Transmission",
        desc: "Strong cryptography and security protocols safeguard PAN during transmission.",
        evidence:
          "tls: Auto on all PCI-scope endpoints; TLS 1.2+ enforced via OpenShell proxy.",
      },
      {
        id: "Req 6.4",
        title: "Change Management for System Components",
        desc: "Changes to system components in the production environment are managed in accordance with established procedures.",
        evidence:
          "Policy version history with SHA-256 hashes, immutable audit log of policy.applied events.",
      },
      {
        id: "Req 7.2",
        title: "Access Based on Need-to-Know",
        desc: "Define access needs and privilege assignments based on job classification and function.",
        evidence:
          "binaries: restriction on every endpoint; only specified processes may use sensitive endpoints.",
      },
      {
        id: "Req 10.2",
        title: "Audit Logs of All Access",
        desc: "Audit log entries are implemented to support the detection of anomalies and suspicious activity.",
        evidence:
          "enforcement: Enforce mode logs every request decision (allowed/denied) with destination, binary, method, path.",
      },
    ],
  },
];

const PERIODS = [
  { hours: 24, label: "Last 24 hours" },
  { hours: 24 * 7, label: "Last 7 days" },
  { hours: 24 * 30, label: "Last 30 days" },
];

export default function CompliancePage() {
  const [framework, setFramework] = useState<FrameworkInfo["id"]>("soc2");
  const [hours, setHours] = useState(24);
  const [generating, setGenerating] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const selectedFw = FRAMEWORKS.find((f) => f.id === framework)!;

  const generate = async () => {
    setError(null);
    setGenerating(true);
    try {
      const bearer = getBearer();
      if (!bearer) return;
      const url = `/api/proxy/compliance/generate?framework=${framework}&hours=${hours}`;
      const resp = await fetch(url, {
        headers: { Authorization: `Bearer ${bearer}` },
      });
      if (!resp.ok) {
        let detail = resp.statusText;
        try {
          const body = await resp.json();
          detail = typeof body.detail === "string" ? body.detail : JSON.stringify(body);
        } catch {
          /* ignore */
        }
        setError(detail);
        return;
      }
      const blob = await resp.blob();
      const dlUrl = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = dlUrl;
      a.download = `${user.tenant_id}-${framework}-${new Date().toISOString().slice(0, 10)}.pdf`;
      a.click();
      URL.revokeObjectURL(dlUrl);
    } finally {
      setGenerating(false);
    }
  };

  return (
    <AppShell>
      <div className="p-8 max-w-6xl mx-auto">
        <div className="mb-8">
          <h1 className="text-2xl font-bold tracking-tight">Compliance Evidence</h1>
          <p className="text-sm text-muted-foreground mt-1">
            Auditor-ready PDF packs mapping live audit events to control IDs.
          </p>
        </div>

        {/* Framework picker */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-3 mb-6">
          {FRAMEWORKS.map((fw) => {
            const selected = framework === fw.id;
            return (
              <button
                key={fw.id}
                onClick={() => setFramework(fw.id)}
                className={`p-4 rounded-lg border text-left transition-colors ${
                  selected
                    ? "border-primary bg-primary/10 ring-1 ring-primary"
                    : "border-border hover:border-primary/40 hover:bg-secondary/40"
                }`}
              >
                <div className="flex items-center justify-between mb-1">
                  <div className="font-semibold">{fw.title}</div>
                  {selected && <Badge>selected</Badge>}
                </div>
                <div className="text-xs text-muted-foreground">{fw.subtitle}</div>
              </button>
            );
          })}
        </div>

        {/* Selected framework details */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 mb-6">
          <Card className="lg:col-span-1">
            <CardHeader>
              <CardTitle className="text-base flex items-center gap-2">
                <ShieldCheck className="w-4 h-4 text-primary" />
                What this means
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4 text-sm">
              <p className="text-muted-foreground leading-relaxed">{selectedFw.blurb}</p>
              <div>
                <div className="text-[10px] uppercase tracking-wide text-muted-foreground font-semibold mb-1">
                  Who needs this
                </div>
                <p className="text-muted-foreground leading-relaxed">{selectedFw.whoNeedsThis}</p>
              </div>
              <div>
                <div className="text-[10px] uppercase tracking-wide text-muted-foreground font-semibold mb-1">
                  Controls covered
                </div>
                <div className="text-2xl font-bold text-primary">{selectedFw.controls.length}</div>
              </div>
            </CardContent>
          </Card>

          <Card className="lg:col-span-2">
            <CardHeader>
              <CardTitle className="text-base flex items-center gap-2">
                <Lock className="w-4 h-4 text-primary" />
                {selectedFw.title} — controls mapped by ShellForge
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-3 max-h-[480px] overflow-y-auto">
              {selectedFw.controls.map((c) => (
                <div key={c.id} className="p-3 rounded-md border bg-secondary/20">
                  <div className="flex items-start justify-between gap-3 mb-1">
                    <div className="font-mono text-xs font-semibold text-primary whitespace-nowrap">
                      {c.id}
                    </div>
                    <div className="font-medium text-sm flex-1">{c.title}</div>
                  </div>
                  <div className="text-xs text-muted-foreground mb-2">{c.desc}</div>
                  <div className="text-[11px] text-foreground/80 bg-background/50 px-2 py-1.5 rounded border border-border">
                    <span className="text-muted-foreground font-medium">Evidence in your tenant:</span>{" "}
                    {c.evidence}
                  </div>
                </div>
              ))}
            </CardContent>
          </Card>
        </div>

        {/* Period selector */}
        <Card className="mb-6">
          <CardHeader>
            <CardTitle className="text-base flex items-center gap-2">
              <FileText className="w-4 h-4 text-primary" />
              Evidence period
            </CardTitle>
          </CardHeader>
          <CardContent className="flex gap-3 flex-wrap">
            {PERIODS.map((p) => (
              <Button
                key={p.hours}
                variant={hours === p.hours ? "default" : "outline"}
                onClick={() => setHours(p.hours)}
              >
                {p.label}
              </Button>
            ))}
          </CardContent>
        </Card>

        {/* Generate */}
        <Card className="border-primary/30">
          <CardContent className="pt-6 flex items-center justify-between">
            <div>
              <div className="font-medium flex items-center gap-2">
                <FileSignature className="w-4 h-4 text-primary" />
                Generate {selectedFw.title} evidence pack
              </div>
              <div className="text-xs text-muted-foreground mt-1">
                {selectedFw.controls.length} controls · audit events from the {PERIODS.find((p) => p.hours === hours)!.label.toLowerCase()} ·
                hash chain proof
              </div>
            </div>
            <Button onClick={generate} disabled={generating} size="lg">
              <Download className="w-4 h-4" />
              {generating ? "Generating..." : "Generate PDF"}
            </Button>
          </CardContent>
          {error && (
            <CardContent className="pt-0">
              <div className="text-xs text-destructive bg-destructive/10 px-3 py-2 rounded border border-destructive/30">
                {error}
              </div>
            </CardContent>
          )}
        </Card>
      </div>
    </AppShell>
  );
}
