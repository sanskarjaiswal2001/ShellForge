"use client";

import { useState } from "react";
import { FileSignature, Download } from "lucide-react";
import { AppShell } from "@/components/app-shell";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { demoBearer, getActiveUser } from "@/lib/demo-auth";

const FRAMEWORKS = [
  { id: "soc2", title: "SOC 2 Type II", desc: "Trust Services Criteria — CC6.1, CC6.6, CC7.2 etc." },
  { id: "hipaa", title: "HIPAA", desc: "45 CFR Part 164 — §164.308, §164.312 controls" },
  { id: "pci", title: "PCI DSS v4.0", desc: "Reqs 1.3, 6.4, 7.2, 10.2" },
];

const PERIODS = [
  { hours: 24, label: "Last 24 hours" },
  { hours: 24 * 7, label: "Last 7 days" },
  { hours: 24 * 30, label: "Last 30 days" },
];

export default function CompliancePage() {
  const [framework, setFramework] = useState("soc2");
  const [hours, setHours] = useState(24);
  const [generating, setGenerating] = useState(false);

  const generate = async () => {
    setGenerating(true);
    try {
      const user = getActiveUser();
      if (!user) return;
      const url = `/api/proxy/compliance/generate?framework=${framework}&hours=${hours}`;
      const resp = await fetch(url, {
        headers: { Authorization: `Bearer ${demoBearer(user)}` },
      });
      if (!resp.ok) {
        alert(`Generation failed: ${await resp.text()}`);
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
      <div className="p-8 max-w-4xl mx-auto">
        <div className="mb-8">
          <h1 className="text-2xl font-bold tracking-tight">Compliance Evidence</h1>
          <p className="text-sm text-muted-foreground mt-1">
            Generate auditor-ready PDF packs mapping live audit events to control IDs.
          </p>
        </div>

        <Card className="mb-6">
          <CardHeader>
            <CardTitle className="text-base">Framework</CardTitle>
          </CardHeader>
          <CardContent className="grid grid-cols-1 md:grid-cols-3 gap-3">
            {FRAMEWORKS.map((fw) => (
              <button
                key={fw.id}
                onClick={() => setFramework(fw.id)}
                className={`p-4 rounded-md border text-left transition-colors ${
                  framework === fw.id ? "border-primary bg-primary/5" : "hover:border-primary/30"
                }`}
              >
                <div className="flex items-center justify-between mb-1">
                  <div className="font-medium text-sm">{fw.title}</div>
                  {framework === fw.id && <Badge variant="default">selected</Badge>}
                </div>
                <div className="text-xs text-muted-foreground">{fw.desc}</div>
              </button>
            ))}
          </CardContent>
        </Card>

        <Card className="mb-6">
          <CardHeader>
            <CardTitle className="text-base">Period</CardTitle>
          </CardHeader>
          <CardContent className="flex gap-3">
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

        <Card>
          <CardContent className="pt-6 flex items-center justify-between">
            <div>
              <div className="font-medium text-sm flex items-center gap-2">
                <FileSignature className="w-4 h-4 text-primary" />
                Generate evidence pack
              </div>
              <div className="text-xs text-muted-foreground mt-1">
                Audit events mapped to control IDs, hash chain verified, PDF.
              </div>
            </div>
            <Button onClick={generate} disabled={generating} size="lg">
              <Download className="w-4 h-4" />
              {generating ? "Generating..." : "Generate PDF"}
            </Button>
          </CardContent>
        </Card>
      </div>
    </AppShell>
  );
}
