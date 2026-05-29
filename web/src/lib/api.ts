// Lightweight API client. Uses Next.js rewrite at /api/proxy/* → control plane.

export interface ApiOptions extends RequestInit {
  bearer?: string;
}

export async function apiFetch<T>(path: string, opts: ApiOptions = {}): Promise<T> {
  const { bearer, ...rest } = opts;
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    Accept: "application/json",
    ...(rest.headers as Record<string, string> | undefined),
  };
  if (bearer) headers.Authorization = `Bearer ${bearer}`;

  const url = path.startsWith("http") ? path : `/api/proxy${path}`;
  const res = await fetch(url, { ...rest, headers, cache: "no-store" });

  if (!res.ok) {
    let detail: string = res.statusText;
    try {
      const body = await res.json();
      const d = body?.detail ?? body;
      if (typeof d === "string") {
        detail = d;
      } else if (Array.isArray(d)) {
        // FastAPI validation errors: [{loc, msg, type, input, ctx}, ...]
        detail = d
          .map((e: unknown) => {
            if (typeof e === "string") return e;
            if (e && typeof e === "object") {
              const obj = e as { loc?: unknown[]; msg?: string };
              const loc = Array.isArray(obj.loc)
                ? obj.loc.filter((p) => p !== "body").join(".")
                : "";
              return loc ? `${loc}: ${obj.msg ?? JSON.stringify(e)}` : obj.msg ?? JSON.stringify(e);
            }
            return String(e);
          })
          .join("; ");
      } else if (d && typeof d === "object") {
        const obj = d as { msg?: string };
        detail = obj.msg ?? JSON.stringify(d);
      }
    } catch {
      /* ignore */
    }
    throw new ApiError(res.status, detail);
  }

  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

// ─── Typed endpoints ─────────────────────────────────────────────────────

export interface OrgOut {
  id: string;
  slug: string;
  name: string;
  default_policy_template: string | null;
}

export interface SandboxOut {
  id: string;
  name: string;
  compute_uid: string;
  agent: string;
  policy_template: string;
  phase: string;
  labels: Record<string, string>;
  created_at: string;
  last_phase_at: string | null;
}

export interface AuditEventOut {
  id: string;
  occurred_at: string;
  class_uid: number;
  activity_id: number;
  actor_user_email: string;
  actor_user_role: string;
  action: string;
  outcome: "SUCCESS" | "FAILURE" | "BLOCKED";
  resource_type: string;
  resource_uid: string;
  resource_name: string;
  prev_hash: string;
  event_hash: string;
  source: string;
}

export interface PolicyVersionOut {
  id: string;
  name: string;
  version: number;
  template: string;
  sha256: string;
  created_at: string;
}
