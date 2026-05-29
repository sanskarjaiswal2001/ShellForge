"use client";

import { useCallback, useEffect, useState } from "react";
import { apiFetch } from "@/lib/api";
import { demoBearer, getActiveUser } from "@/lib/demo-auth";

export function useApi<T>(path: string, deps: unknown[] = []) {
  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const user = getActiveUser();
      if (!user) throw new Error("Not authenticated");
      const result = await apiFetch<T>(path, { bearer: demoBearer(user) });
      setData(result);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [path, ...deps]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  return { data, loading, error, refresh };
}

export function useAuditStream() {
  const [events, setEvents] = useState<any[]>([]);
  const [connected, setConnected] = useState(false);

  useEffect(() => {
    const user = getActiveUser();
    if (!user) return;

    // EventSource doesn't support custom headers; pass bearer as query param.
    // The control plane SSE endpoint accepts ?token=<bearer> as fallback.
    // (In real prod, use a stable session cookie.)
    const bearer = demoBearer(user);
    const url = `/api/proxy/audit/stream?token=${encodeURIComponent(bearer)}`;

    // Fall back to polling — EventSource auth is finicky.
    let alive = true;
    let lastSeen: string | null = null;

    const poll = async () => {
      while (alive) {
        try {
          const result = await apiFetch<any[]>("/audit/events?limit=50", { bearer });
          if (lastSeen === null) {
            // initial load
            setEvents(result);
          } else {
            const newer = result.filter((e) => e.occurred_at > lastSeen!);
            if (newer.length > 0) {
              setEvents((prev) => [...newer, ...prev].slice(0, 100));
            }
          }
          if (result.length > 0) {
            const max = result.reduce((m, e) => (e.occurred_at > m ? e.occurred_at : m), "");
            lastSeen = max;
          }
          setConnected(true);
        } catch {
          setConnected(false);
        }
        await new Promise((r) => setTimeout(r, 2500));
      }
    };
    void poll();
    return () => { alive = false; };
  }, []);

  return { events, connected };
}
