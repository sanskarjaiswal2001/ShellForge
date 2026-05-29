"use client";

import { useState } from "react";
import { Plus, Box, Trash2, AlertTriangle, X, Terminal } from "lucide-react";
import { AppShell } from "@/components/app-shell";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { apiFetch, ApiError, type SandboxOut } from "@/lib/api";
import { useApi } from "@/lib/hooks";
import { demoBearer, getActiveUser } from "@/lib/demo-auth";
import { ProvisioningTimeline } from "@/components/provisioning-timeline";
import { ConnectionModal } from "@/components/connection-modal";

const POLICY_TEMPLATES = [
  { id: "baseline", label: "Baseline" },
  { id: "hipaa-healthcare", label: "HIPAA — Healthcare AI Agent" },
  { id: "pci-payments", label: "PCI-DSS — Payment Processing" },
  { id: "soc2-saas", label: "SOC 2 — SaaS Development" },
];

const AGENTS = ["claude", "opencode", "codex", "copilot"];

export default function SandboxesPage() {
  const { data: sandboxes, loading, error, refresh } = useApi<SandboxOut[]>("/sandboxes");
  const [creating, setCreating] = useState(false);
  const [createError, setCreateError] = useState<string | null>(null);
  const [showCreate, setShowCreate] = useState(false);
  const [provisioning, setProvisioning] = useState<SandboxOut | null>(null);
  const [connectTo, setConnectTo] = useState<SandboxOut | null>(null);
  const [form, setForm] = useState({
    name: "",
    agent: "claude",
    policy_template: "baseline",
  });

  const submit = async () => {
    setCreating(true);
    setCreateError(null);
    try {
      const user = getActiveUser();
      if (!user) return;
      const result = await apiFetch<SandboxOut>("/sandboxes", {
        method: "POST",
        bearer: demoBearer(user),
        body: JSON.stringify(form),
      });
      setShowCreate(false);
      setForm({ name: "", agent: "claude", policy_template: user.policy_template || "baseline" });
      setProvisioning(result);
      await refresh();
    } catch (e) {
      const msg = e instanceof ApiError ? `[${e.status}] ${e.message}` : e instanceof Error ? e.message : String(e);
      setCreateError(msg);
    } finally {
      setCreating(false);
    }
  };

  const triggerViolation = async (sb: SandboxOut) => {
    const user = getActiveUser();
    if (!user) return;
    await apiFetch(`/sandboxes/${sb.id}/simulate-violation`, {
      method: "POST",
      bearer: demoBearer(user),
      body: JSON.stringify({ destination: "evil-exfil.io" }),
    });
    setTimeout(() => refresh(), 500);
  };

  const removeSandbox = async (sb: SandboxOut) => {
    if (!confirm(`Delete sandbox "${sb.name}"?`)) return;
    const user = getActiveUser();
    if (!user) return;
    await apiFetch(`/sandboxes/${sb.id}`, { method: "DELETE", bearer: demoBearer(user) });
    await refresh();
  };

  return (
    <AppShell>
      <div className="p-8 max-w-6xl mx-auto">
        <div className="flex items-center justify-between mb-8">
          <div>
            <h1 className="text-2xl font-bold tracking-tight">Sandboxes</h1>
            <p className="text-sm text-muted-foreground mt-1">
              Tenant-scoped agent runtimes. Policy enforced at the network layer.
            </p>
          </div>
          <Button onClick={() => setShowCreate((v) => !v)}>
            <Plus className="w-4 h-4" /> New sandbox
          </Button>
        </div>

        {showCreate && (
          <Card className="mb-6 border-primary/30">
            <CardHeader>
              <CardTitle className="text-base">Provision sandbox</CardTitle>
            </CardHeader>
            <CardContent className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <div>
                <label className="text-xs font-medium uppercase tracking-wide text-muted-foreground">Name</label>
                <input
                  className="mt-1 w-full px-3 py-2 border rounded-md text-sm bg-background"
                  value={form.name}
                  onChange={(e) => setForm({ ...form, name: e.target.value })}
                  placeholder="my-sandbox-1"
                />
                <div className="text-[10px] text-muted-foreground mt-1">
                  lowercase, alphanumeric + hyphens
                </div>
              </div>
              <div>
                <label className="text-xs font-medium uppercase tracking-wide text-muted-foreground">Agent</label>
                <select
                  className="mt-1 w-full px-3 py-2 border rounded-md text-sm bg-background"
                  value={form.agent}
                  onChange={(e) => setForm({ ...form, agent: e.target.value })}
                >
                  {AGENTS.map((a) => <option key={a} value={a}>{a}</option>)}
                </select>
              </div>
              <div>
                <label className="text-xs font-medium uppercase tracking-wide text-muted-foreground">Policy template</label>
                <select
                  className="mt-1 w-full px-3 py-2 border rounded-md text-sm bg-background"
                  value={form.policy_template}
                  onChange={(e) => setForm({ ...form, policy_template: e.target.value })}
                >
                  {POLICY_TEMPLATES.map((p) => <option key={p.id} value={p.id}>{p.label}</option>)}
                </select>
              </div>
              {createError && (
                <div className="md:col-span-3 text-xs text-destructive bg-destructive/10 px-3 py-2 rounded border border-destructive/30">
                  {createError}
                </div>
              )}
              <div className="md:col-span-3 flex gap-2 justify-end">
                <Button variant="ghost" onClick={() => { setShowCreate(false); setCreateError(null); }}>Cancel</Button>
                <Button onClick={submit} disabled={!form.name || creating}>
                  {creating ? "Provisioning..." : "Provision"}
                </Button>
              </div>
            </CardContent>
          </Card>
        )}

        {/* Live provisioning panel */}
        {provisioning && (
          <Card className="mb-6 border-blue-500/40">
            <CardHeader className="flex flex-row items-center justify-between">
              <CardTitle className="text-base flex items-center gap-2">
                <span className="w-2 h-2 rounded-full bg-blue-500 animate-pulse" />
                Provisioning <span className="font-mono">{provisioning.name}</span>
              </CardTitle>
              <Button variant="ghost" size="icon" onClick={() => setProvisioning(null)}>
                <X className="w-4 h-4" />
              </Button>
            </CardHeader>
            <CardContent>
              <ProvisioningTimeline
                sandboxId={provisioning.id}
                active={true}
                onComplete={() => {
                  void refresh();
                  setTimeout(() => setProvisioning(null), 1200);
                }}
              />
            </CardContent>
          </Card>
        )}

        {loading && <Skeleton />}
        {error && (
          <Card className="border-destructive/30">
            <CardContent className="pt-6 text-sm text-destructive">{error}</CardContent>
          </Card>
        )}
        {!loading && !error && sandboxes && sandboxes.length === 0 && <Empty />}
        {sandboxes && sandboxes.length > 0 && (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {sandboxes.map((sb) => (
              <SandboxCard
                key={sb.id}
                sb={sb}
                onViolation={() => triggerViolation(sb)}
                onDelete={() => removeSandbox(sb)}
                onShowProvisioning={() => setProvisioning(sb)}
                onConnect={() => setConnectTo(sb)}
              />
            ))}
          </div>
        )}

        {connectTo && (
          <ConnectionModal sandbox={connectTo} onClose={() => setConnectTo(null)} />
        )}
      </div>
    </AppShell>
  );
}

function SandboxCard({
  sb,
  onViolation,
  onDelete,
  onShowProvisioning,
  onConnect,
}: {
  sb: SandboxOut;
  onViolation: () => void;
  onDelete: () => void;
  onShowProvisioning: () => void;
  onConnect: () => void;
}) {
  const phaseColor =
    sb.phase === "READY" ? "success" :
    sb.phase === "ERROR" ? "destructive" :
    "secondary";

  return (
    <Card>
      <CardHeader className="pb-3">
        <div className="flex items-start justify-between">
          <div>
            <CardTitle className="text-base flex items-center gap-2">
              <Box className="w-4 h-4 text-primary" /> {sb.name}
            </CardTitle>
            <div className="text-xs text-muted-foreground mt-1 font-mono">{sb.compute_uid.slice(0, 12)}…</div>
          </div>
          <button onClick={sb.phase === "PROVISIONING" ? onShowProvisioning : undefined}>
            <Badge variant={phaseColor as "success" | "destructive" | "secondary"}>
              {sb.phase === "PROVISIONING" && (
                <span className="w-1.5 h-1.5 rounded-full bg-current animate-pulse mr-1 inline-block" />
              )}
              {sb.phase}
            </Badge>
          </button>
        </div>
      </CardHeader>
      <CardContent className="pt-0 space-y-3">
        <div className="grid grid-cols-2 gap-2 text-xs">
          <Detail label="Agent" value={sb.agent} />
          <Detail label="Policy" value={sb.policy_template} />
        </div>
        <div className="flex gap-2">
          <Button
            variant="default"
            size="sm"
            onClick={onConnect}
            disabled={sb.phase !== "READY"}
            className="flex-1"
          >
            <Terminal className="w-3.5 h-3.5" /> Connect
          </Button>
          <Button variant="outline" size="sm" onClick={onViolation} title="Simulate violation">
            <AlertTriangle className="w-3.5 h-3.5" />
          </Button>
          <Button variant="ghost" size="sm" onClick={onDelete} title="Delete">
            <Trash2 className="w-3.5 h-3.5 text-destructive" />
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}

function Detail({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <div className="uppercase tracking-wide text-[10px] text-muted-foreground">{label}</div>
      <div className="font-medium">{value}</div>
    </div>
  );
}

function Skeleton() {
  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
      {[1, 2, 3].map((i) => (
        <Card key={i}>
          <CardContent className="pt-6">
            <div className="h-4 bg-secondary rounded animate-pulse mb-3 w-2/3" />
            <div className="h-3 bg-secondary/60 rounded animate-pulse w-1/3" />
          </CardContent>
        </Card>
      ))}
    </div>
  );
}

function Empty() {
  return (
    <Card className="border-dashed">
      <CardContent className="pt-12 pb-12 text-center">
        <Box className="w-12 h-12 mx-auto text-muted-foreground/50 mb-3" />
        <h3 className="font-medium">No sandboxes yet</h3>
        <p className="text-sm text-muted-foreground mt-1">
          Provision the first one to see policy enforcement live.
        </p>
      </CardContent>
    </Card>
  );
}
