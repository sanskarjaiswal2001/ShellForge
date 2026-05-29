"use client";

import { AppShell } from "@/components/app-shell";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Box, Activity, Ban, ShieldCheck } from "lucide-react";
import { useApi } from "@/lib/hooks";
import type { SandboxOut, AuditEventOut } from "@/lib/api";

export default function DashboardPage() {
  const { data: sandboxes } = useApi<SandboxOut[]>("/sandboxes");
  const { data: events } = useApi<AuditEventOut[]>("/audit/events?limit=100");

  const total = sandboxes?.length ?? 0;
  const ready = sandboxes?.filter((s) => s.phase === "READY").length ?? 0;
  const blocked = events?.filter((e) => e.outcome === "BLOCKED").length ?? 0;
  const recent = events?.slice(0, 6) ?? [];

  return (
    <AppShell>
      <div className="p-8 max-w-6xl mx-auto">
        <div className="mb-8">
          <h1 className="text-2xl font-bold tracking-tight">Overview</h1>
          <p className="text-sm text-muted-foreground mt-1">
            Fleet health, recent activity, and compliance posture.
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-8">
          <Stat icon={Box} label="Sandboxes" value={total} accent="text-blue-600" />
          <Stat icon={ShieldCheck} label="Ready" value={ready} accent="text-green-600" />
          <Stat icon={Ban} label="Violations (24h)" value={blocked} accent="text-red-600" />
          <Stat icon={Activity} label="Audit events" value={events?.length ?? 0} accent="text-indigo-600" />
        </div>

        <Card>
          <CardHeader>
            <CardTitle className="text-base">Recent activity</CardTitle>
          </CardHeader>
          <CardContent>
            {recent.length === 0 ? (
              <p className="text-sm text-muted-foreground">No events yet.</p>
            ) : (
              <div className="space-y-2">
                {recent.map((ev) => (
                  <div
                    key={ev.id}
                    className="flex items-center justify-between p-2 rounded-md bg-secondary/30 hover:bg-secondary/60 transition-colors"
                  >
                    <div className="flex items-center gap-3">
                      <Badge variant={outcomeVariant(ev.outcome)}>{ev.outcome}</Badge>
                      <div>
                        <div className="text-sm font-medium">{ev.action}</div>
                        <div className="text-xs text-muted-foreground">
                          {ev.actor_user_email} · {ev.resource_name}
                        </div>
                      </div>
                    </div>
                    <div className="text-right">
                      <div className="text-xs text-muted-foreground">
                        {new Date(ev.occurred_at).toLocaleTimeString()}
                      </div>
                      <span className="hash-chip">{ev.event_hash.slice(0, 8)}…</span>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </AppShell>
  );
}

function Stat({
  icon: Icon,
  label,
  value,
  accent,
}: {
  icon: any;
  label: string;
  value: number;
  accent: string;
}) {
  return (
    <Card>
      <CardContent className="pt-6">
        <div className="flex items-center justify-between mb-2">
          <div className={`text-3xl font-bold ${accent}`}>{value}</div>
          <Icon className={`w-5 h-5 ${accent} opacity-70`} />
        </div>
        <div className="text-xs uppercase tracking-wide text-muted-foreground">{label}</div>
      </CardContent>
    </Card>
  );
}

function outcomeVariant(outcome: string): "default" | "secondary" | "destructive" | "success" {
  if (outcome === "BLOCKED") return "destructive";
  if (outcome === "SUCCESS") return "success";
  if (outcome === "FAILURE") return "destructive";
  return "secondary";
}
