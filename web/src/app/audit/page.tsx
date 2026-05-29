"use client";

import { Link2, ShieldCheck, ShieldAlert } from "lucide-react";
import { AppShell } from "@/components/app-shell";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { useState } from "react";
import { apiFetch, type AuditEventOut } from "@/lib/api";
import { useApi } from "@/lib/hooks";
import { getBearer } from "@/lib/session";

export default function AuditPage() {
  const { data: events, loading } = useApi<AuditEventOut[]>("/audit/events?limit=100");
  const [chain, setChain] = useState<{ valid: boolean; checked: number; broken_at: string | null } | null>(null);
  const [verifying, setVerifying] = useState(false);

  const verifyChain = async () => {
    setVerifying(true);
    try {
      const bearer = getBearer();
      if (!bearer) return;
      const result = await apiFetch<{ valid: boolean; checked: number; broken_at: string | null }>(
        "/audit/chain/verify",
        { bearer },
      );
      setChain(result);
    } finally {
      setVerifying(false);
    }
  };

  return (
    <AppShell>
      <div className="p-8 max-w-6xl mx-auto">
        <div className="flex items-start justify-between mb-8">
          <div>
            <h1 className="text-2xl font-bold tracking-tight">Audit Events</h1>
            <p className="text-sm text-muted-foreground mt-1">
              Hash-chained, OCSF v1.7.0, streamed to OTel Collector.
            </p>
          </div>
          <div className="flex items-center gap-3">
            {chain && (
              <Badge variant={chain.valid ? "success" : "destructive"}>
                {chain.valid ? <ShieldCheck className="w-3.5 h-3.5 mr-1" /> : <ShieldAlert className="w-3.5 h-3.5 mr-1" />}
                {chain.valid ? `Chain valid (${chain.checked} events)` : "Chain BROKEN"}
              </Badge>
            )}
            <Button variant="outline" size="sm" onClick={verifyChain} disabled={verifying}>
              <Link2 className="w-3.5 h-3.5" /> {verifying ? "Verifying..." : "Verify hash chain"}
            </Button>
          </div>
        </div>

        <Card>
          <CardHeader>
            <CardTitle className="text-base">Recent events</CardTitle>
          </CardHeader>
          <CardContent className="p-0">
            {loading && <div className="p-6 text-sm text-muted-foreground">Loading...</div>}
            {!loading && (
              <table className="w-full text-sm">
                <thead className="bg-secondary/40 text-xs uppercase tracking-wide text-muted-foreground">
                  <tr>
                    <th className="px-4 py-2 text-left">Time</th>
                    <th className="px-4 py-2 text-left">Actor</th>
                    <th className="px-4 py-2 text-left">Action</th>
                    <th className="px-4 py-2 text-left">Resource</th>
                    <th className="px-4 py-2 text-left">Outcome</th>
                    <th className="px-4 py-2 text-left">Hash</th>
                  </tr>
                </thead>
                <tbody className="divide-y">
                  {events?.map((ev) => (
                    <tr key={ev.id} className="hover:bg-secondary/30 audit-row">
                      <td className="px-4 py-2 text-xs whitespace-nowrap">
                        {new Date(ev.occurred_at).toLocaleString()}
                      </td>
                      <td className="px-4 py-2">
                        <div className="font-medium text-xs">{ev.actor_user_email}</div>
                        <div className="text-[10px] text-muted-foreground">{ev.actor_user_role}</div>
                      </td>
                      <td className="px-4 py-2 font-mono text-xs">{ev.action}</td>
                      <td className="px-4 py-2 text-xs">
                        <div className="font-medium">{ev.resource_name}</div>
                        <div className="text-[10px] text-muted-foreground">{ev.resource_type}</div>
                      </td>
                      <td className="px-4 py-2">
                        {ev.outcome === "BLOCKED" ? (
                          <span className="violation-badge">{ev.outcome}</span>
                        ) : (
                          <Badge variant={ev.outcome === "SUCCESS" ? "success" : "destructive"}>
                            {ev.outcome}
                          </Badge>
                        )}
                      </td>
                      <td className="px-4 py-2">
                        <span className="hash-chip" title={ev.event_hash}>
                          {ev.event_hash.slice(0, 8)}…
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </CardContent>
        </Card>
      </div>
    </AppShell>
  );
}
