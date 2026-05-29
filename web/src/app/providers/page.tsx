"use client";

import { useState } from "react";
import { KeyRound, Plus, Trash2, Eye, EyeOff } from "lucide-react";
import { AppShell } from "@/components/app-shell";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { apiFetch, ApiError } from "@/lib/api";
import { useApi } from "@/lib/hooks";
import { getBearer } from "@/lib/session";

interface ProviderOut {
  id: string;
  name: string;
  type: string;
  credential_keys: string[];
  secret_prefix: string;
  created_at: string;
}

interface ProviderTypeInfo {
  [type: string]: string[];
}

const TYPE_COLORS: Record<string, string> = {
  claude: "bg-amber-500/15 text-amber-400 border-amber-500/30",
  openai: "bg-green-500/15 text-green-400 border-green-500/30",
  github: "bg-slate-500/15 text-slate-300 border-slate-500/30",
  gitlab: "bg-orange-500/15 text-orange-400 border-orange-500/30",
  nvidia: "bg-emerald-500/15 text-emerald-400 border-emerald-500/30",
  copilot: "bg-blue-500/15 text-blue-400 border-blue-500/30",
  generic: "bg-purple-500/15 text-purple-400 border-purple-500/30",
};

export default function ProvidersPage() {
  const { data: providers, loading, error, refresh } = useApi<ProviderOut[]>("/providers");
  const { data: types } = useApi<ProviderTypeInfo>("/providers/types");
  const [showCreate, setShowCreate] = useState(false);
  const [creating, setCreating] = useState(false);
  const [createError, setCreateError] = useState<string | null>(null);
  const [showValues, setShowValues] = useState(false);
  const [form, setForm] = useState({
    name: "",
    type: "claude",
    credentials: {} as Record<string, string>,
  });

  const selectedType = form.type;
  const expectedKeys: string[] = types?.[selectedType] ?? [];

  const handleTypeChange = (t: string) => {
    setForm({ name: t, type: t, credentials: {} });
  };

  const setCredential = (key: string, value: string) => {
    setForm((prev) => ({ ...prev, credentials: { ...prev.credentials, [key]: value } }));
  };

  const submit = async () => {
    setCreating(true);
    setCreateError(null);
    try {
      const bearer = getBearer();
      if (!bearer) throw new Error("Not authenticated");
      await apiFetch("/providers", {
        method: "POST",
        bearer,
        body: JSON.stringify({
          name: form.name,
          type: form.type,
          credentials: form.credentials,
        }),
      });
      setShowCreate(false);
      setForm({ name: "", type: "claude", credentials: {} });
      await refresh();
    } catch (e) {
      const msg = e instanceof ApiError ? `[${e.status}] ${e.message}` : e instanceof Error ? e.message : String(e);
      setCreateError(msg);
    } finally {
      setCreating(false);
    }
  };

  const deleteProvider = async (id: string, name: string) => {
    if (!confirm(`Delete provider "${name}"? Credentials will be removed from the secrets backend.`)) return;
    const bearer = getBearer();
    if (!bearer) return;
    await apiFetch(`/providers/${id}`, { method: "DELETE", bearer });
    await refresh();
  };

  return (
    <AppShell>
      <div className="p-8 max-w-5xl mx-auto">
        <div className="flex items-center justify-between mb-8">
          <div>
            <h1 className="text-2xl font-bold tracking-tight">Providers</h1>
            <p className="text-sm text-muted-foreground mt-1">
              Credential bundles injected into sandboxes at runtime. Secrets stored in{" "}
              <span className="font-mono text-xs">Infisical</span>, never in this DB.
            </p>
          </div>
          <Button onClick={() => setShowCreate((v) => !v)}>
            <Plus className="w-4 h-4" /> Add provider
          </Button>
        </div>

        {showCreate && (
          <Card className="mb-6 border-primary/30">
            <CardHeader>
              <CardTitle className="text-base">Register provider</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="text-xs font-medium uppercase tracking-wide text-muted-foreground block mb-1">
                    Type
                  </label>
                  <select
                    className="w-full px-3 py-2 border rounded-md text-sm bg-background"
                    value={form.type}
                    onChange={(e) => handleTypeChange(e.target.value)}
                  >
                    {Object.keys(types ?? {}).map((t) => (
                      <option key={t} value={t}>{t}</option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="text-xs font-medium uppercase tracking-wide text-muted-foreground block mb-1">
                    Name (slug)
                  </label>
                  <input
                    className="w-full px-3 py-2 border rounded-md text-sm bg-background"
                    value={form.name}
                    onChange={(e) => setForm({ ...form, name: e.target.value })}
                    placeholder={form.type}
                  />
                  <div className="text-[10px] text-muted-foreground mt-1">
                    Will be namespaced to <span className="font-mono">{form.name || form.type}-&lt;tenant&gt;</span>
                  </div>
                </div>
              </div>

              {expectedKeys.length > 0 && (
                <div>
                  <div className="flex items-center justify-between mb-2">
                    <label className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                      Credentials
                    </label>
                    <button
                      onClick={() => setShowValues((v) => !v)}
                      className="text-xs text-muted-foreground flex items-center gap-1"
                    >
                      {showValues ? <EyeOff className="w-3 h-3" /> : <Eye className="w-3 h-3" />}
                      {showValues ? "Hide" : "Show"} values
                    </button>
                  </div>
                  <div className="space-y-2">
                    {expectedKeys.map((key) => (
                      <div key={key} className="flex items-center gap-3">
                        <label className="font-mono text-xs w-40 shrink-0 text-muted-foreground">{key}</label>
                        <input
                          type={showValues ? "text" : "password"}
                          className="flex-1 px-3 py-1.5 border rounded-md text-sm bg-background font-mono"
                          value={form.credentials[key] ?? ""}
                          onChange={(e) => setCredential(key, e.target.value)}
                          placeholder={`Enter ${key}`}
                          autoComplete="off"
                        />
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {createError && (
                <div className="text-xs text-destructive bg-destructive/10 px-3 py-2 rounded border border-destructive/30">
                  {createError}
                </div>
              )}

              <div className="flex gap-2 justify-end">
                <Button variant="ghost" onClick={() => { setShowCreate(false); setCreateError(null); }}>
                  Cancel
                </Button>
                <Button
                  onClick={submit}
                  disabled={creating || !form.name || Object.keys(form.credentials).length === 0}
                >
                  {creating ? "Registering..." : "Register provider"}
                </Button>
              </div>
            </CardContent>
          </Card>
        )}

        {loading && (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {[1, 2].map((i) => (
              <Card key={i}>
                <CardContent className="pt-6">
                  <div className="h-4 bg-secondary rounded animate-pulse mb-3 w-1/2" />
                  <div className="h-3 bg-secondary/60 rounded animate-pulse w-1/3" />
                </CardContent>
              </Card>
            ))}
          </div>
        )}

        {error && (
          <Card className="border-destructive/30">
            <CardContent className="pt-6 text-sm text-destructive">{error}</CardContent>
          </Card>
        )}

        {!loading && providers?.length === 0 && (
          <Card className="border-dashed">
            <CardContent className="pt-12 pb-12 text-center">
              <KeyRound className="w-12 h-12 mx-auto text-muted-foreground/50 mb-3" />
              <h3 className="font-medium">No providers yet</h3>
              <p className="text-sm text-muted-foreground mt-1">
                Add a provider so sandboxes can receive API keys automatically.
              </p>
            </CardContent>
          </Card>
        )}

        {providers && providers.length > 0 && (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {providers.map((p) => (
              <Card key={p.id}>
                <CardHeader className="pb-3">
                  <div className="flex items-start justify-between">
                    <div>
                      <CardTitle className="text-base flex items-center gap-2">
                        <KeyRound className="w-4 h-4 text-primary" />
                        {p.name}
                      </CardTitle>
                      <div className="text-xs text-muted-foreground mt-1 font-mono">{p.id.slice(0, 8)}…</div>
                    </div>
                    <span
                      className={`text-[11px] px-2 py-0.5 rounded border font-medium ${
                        TYPE_COLORS[p.type] ?? TYPE_COLORS.generic
                      }`}
                    >
                      {p.type}
                    </span>
                  </div>
                </CardHeader>
                <CardContent className="pt-0 space-y-3">
                  <div>
                    <div className="text-[10px] uppercase tracking-wide text-muted-foreground mb-1">
                      Injected env vars
                    </div>
                    <div className="flex flex-wrap gap-1">
                      {p.credential_keys.map((k) => (
                        <span key={k} className="font-mono text-[10px] bg-secondary px-1.5 py-0.5 rounded">
                          {k}
                        </span>
                      ))}
                    </div>
                  </div>
                  <div className="text-[10px] text-muted-foreground font-mono break-all">
                    {p.secret_prefix}
                  </div>
                  <div className="flex justify-end">
                    <Button variant="ghost" size="sm" onClick={() => deleteProvider(p.id, p.name)}>
                      <Trash2 className="w-3.5 h-3.5 text-destructive" />
                    </Button>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        )}
      </div>
    </AppShell>
  );
}
