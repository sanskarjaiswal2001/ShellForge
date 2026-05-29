"use client";

import { useCallback, useEffect, useState } from "react";
import { apiFetch } from "@/lib/api";
import { getBearer } from "@/lib/session";

export function useApi<T>(path: string, deps: unknown[] = []) {
  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const bearer = getBearer();
      if (!bearer) throw new Error("Not authenticated");
      const result = await apiFetch<T>(path, { bearer });
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
    const bearer = getBearer();
    if (!bearer) return;

    let alive = true;
    let lastSeen: string | null = null;

    // Poll the REST endpoint for now; the backend delivers events via
    // Postgres LISTEN/NOTIFY internally. A future iteration should open a
    // real SSE EventSource once we have a session-cookie-based auth path
    // (EventSource doesn't support custom headers).
    const poll = async () => {
      while (alive) {
        try {
          const result = await apiFetch<any[]>("/audit/events?limit=50", { bearer });
          if (lastSeen === null) {
            setEvents(result);
          } else {
            const newer = result.filter((e: any) => e.occurred_at > lastSeen!);
            if (newer.length > 0) {
              setEvents((prev) => [...newer, ...prev].slice(0, 100));
            }
          }
          if (result.length > 0) {
            const max = result.reduce(
              (m: string, e: any) => (e.occurred_at > m ? e.occurred_at : m),
              ""
            );
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
    return () => {
      alive = false;
    };
  }, []);

  return { events, connected };
}
