"use client";

import { useEffect, useState } from "react";
import { Check, Loader2, Circle } from "lucide-react";
import { apiFetch } from "@/lib/api";
import { demoBearer, getActiveUser } from "@/lib/demo-auth";
import { cn } from "@/lib/cn";

interface TimelineEntry {
  key: string;
  message: string;
  status: "in_progress" | "done" | "failed";
  started_at: string;
  updated_at: string;
}

interface Props {
  sandboxId: string;
  active: boolean;
  onComplete?: () => void;
}

export function ProvisioningTimeline({ sandboxId, active, onComplete }: Props) {
  const [entries, setEntries] = useState<TimelineEntry[]>([]);

  useEffect(() => {
    if (!active) return;
    const user = getActiveUser();
    if (!user) return;

    let stopped = false;
    let lastStatus: string | null = null;

    const poll = async () => {
      while (!stopped) {
        try {
          const result = await apiFetch<TimelineEntry[]>(
            `/sandboxes/${sandboxId}/timeline`,
            { bearer: demoBearer(user) }
          );
          setEntries(result);
          const lastEntry = result[result.length - 1];
          if (lastEntry?.key === "ready" && lastEntry.status === "done" && lastStatus !== "ready_done") {
            lastStatus = "ready_done";
            onComplete?.();
            stopped = true;
            return;
          }
        } catch {
          /* keep polling */
        }
        await new Promise((r) => setTimeout(r, 400));
      }
    };
    void poll();
    return () => {
      stopped = true;
    };
  }, [sandboxId, active, onComplete]);

  if (entries.length === 0) {
    return (
      <div className="text-xs text-muted-foreground flex items-center gap-2 py-2">
        <Loader2 className="w-3.5 h-3.5 animate-spin" /> Waiting for gateway response…
      </div>
    );
  }

  return (
    <div className="space-y-1.5 relative">
      {entries.map((e) => (
        <div key={e.key} className="flex items-center gap-2.5 text-xs">
          {e.status === "done" && (
            <div className="w-4 h-4 rounded-full bg-green-600/20 border border-green-500 flex items-center justify-center shrink-0">
              <Check className="w-2.5 h-2.5 text-green-500" strokeWidth={3} />
            </div>
          )}
          {e.status === "in_progress" && (
            <div className="w-4 h-4 rounded-full bg-blue-600/20 border border-blue-500 flex items-center justify-center shrink-0">
              <Loader2 className="w-2.5 h-2.5 text-blue-400 animate-spin" />
            </div>
          )}
          {e.status === "failed" && (
            <div className="w-4 h-4 rounded-full bg-destructive/20 border border-destructive flex items-center justify-center shrink-0">
              <Circle className="w-2.5 h-2.5 text-destructive fill-destructive" />
            </div>
          )}
          <span
            className={cn(
              "flex-1",
              e.status === "done" && "text-foreground/70",
              e.status === "in_progress" && "text-foreground font-medium",
              e.status === "failed" && "text-destructive"
            )}
          >
            {e.message}
          </span>
        </div>
      ))}
    </div>
  );
}
