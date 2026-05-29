"use client";

import { useState } from "react";
import { FileText, Check } from "lucide-react";
import { AppShell } from "@/components/app-shell";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { apiFetch, type PolicyVersionOut } from "@/lib/api";
import { useApi } from "@/lib/hooks";
import { getBearer } from "@/lib/session";

export default function PoliciesPage() {
  const { data: templates } = useApi<string[]>("/policies/templates");
  const { data: versions, refresh } = useApi<PolicyVersionOut[]>("/policies");
  const [selected, setSelected] = useState<string | null>(null);
  const [yaml, setYaml] = useState<string>("");

  const loadTemplate = async (name: string) => {
    const bearer = getBearer();
    if (!bearer) return;
    const res = await apiFetch<{ name: string; yaml: string }>(`/policies/templates/${name}`, { bearer });
    setSelected(name);
    setYaml(res.yaml);
  };

  const adoptTemplate = async () => {
    const bearer = getBearer();
    if (!bearer || !selected) return;
    await apiFetch("/policies", {
      method: "POST",
      bearer,
      body: JSON.stringify({
        name: selected,
        template: selected,
      }),
    });
    await refresh();
    alert(`Adopted ${selected} as a new policy version.`);
  };

  return (
    <AppShell>
      <div className="p-8 max-w-6xl mx-auto">
        <div className="mb-8">
          <h1 className="text-2xl font-bold tracking-tight">Policies</h1>
          <p className="text-sm text-muted-foreground mt-1">
            Compliance-mapped templates and tenant-scoped policy versions.
          </p>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          <div className="lg:col-span-1 space-y-3">
            <h2 className="text-sm font-semibold uppercase tracking-wide text-muted-foreground">Templates</h2>
            {templates?.map((t) => (
              <button
                key={t}
                onClick={() => loadTemplate(t)}
                className={`w-full text-left p-3 rounded-md border transition-colors ${
                  selected === t ? "border-primary bg-primary/5" : "hover:border-primary/30 hover:bg-secondary/30"
                }`}
              >
                <div className="flex items-center gap-2">
                  <FileText className="w-4 h-4 text-primary" />
                  <span className="font-medium text-sm">{t}</span>
                </div>
              </button>
            ))}

            <h2 className="text-sm font-semibold uppercase tracking-wide text-muted-foreground mt-6">Adopted versions</h2>
            {versions?.length === 0 && (
              <p className="text-xs text-muted-foreground">No tenant versions yet.</p>
            )}
            {versions?.map((v) => (
              <div key={v.id} className="p-3 rounded-md bg-secondary/40 text-sm">
                <div className="flex items-center justify-between">
                  <span className="font-medium">{v.name}</span>
                  <Badge variant="outline">v{v.version}</Badge>
                </div>
                <div className="hash-chip mt-1.5">{v.sha256.slice(0, 12)}…</div>
              </div>
            ))}
          </div>

          <Card className="lg:col-span-2 min-h-[500px]">
            <CardHeader className="flex flex-row items-center justify-between">
              <CardTitle className="text-base">
                {selected ?? "Select a template"}
              </CardTitle>
              {selected && (
                <Button size="sm" onClick={adoptTemplate}>
                  <Check className="w-3.5 h-3.5" /> Adopt for tenant
                </Button>
              )}
            </CardHeader>
            <CardContent>
              {selected ? (
                <pre className="text-xs font-mono bg-secondary/50 p-4 rounded-md overflow-x-auto max-h-[500px]">
                  {yaml}
                </pre>
              ) : (
                <div className="text-center py-12 text-muted-foreground text-sm">
                  Pick a template on the left to view + adopt.
                </div>
              )}
            </CardContent>
          </Card>
        </div>
      </div>
    </AppShell>
  );
}
