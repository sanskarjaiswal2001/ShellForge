/**
 * Unified session helper.
 *
 * Provides a single `getBearer()` function that:
 *   1. Returns a real NextAuth ID token when a real OIDC session exists.
 *   2. Falls back to demo-bearer when ENV=local and a demo user is selected.
 *
 * All API calls use this so switching from demo to real auth requires no
 * changes to page components.
 */

"use client";

import { useSession } from "next-auth/react";
import { getActiveUser, demoBearer } from "@/lib/demo-auth";

export interface SessionState {
  bearer: string | null;
  email: string | null;
  name: string | null;
  tenantId: string | null;
  roles: string[];
  isDemo: boolean;
  isAuthenticated: boolean;
}

export function useShellForgeSession(): SessionState {
  const { data: session } = useSession();

  // Real NextAuth session takes priority.
  if (session) {
    const s = session as any;
    return {
      bearer: s.id_token ?? s.access_token ?? null,
      email: session.user?.email ?? null,
      name: session.user?.name ?? null,
      tenantId: s.tenant_id ?? null,
      roles: s.roles ?? [],
      isDemo: false,
      isAuthenticated: true,
    };
  }

  // Demo fallback (ENV=local only).
  const demoUser = getActiveUser();
  if (demoUser) {
    return {
      bearer: demoBearer(demoUser),
      email: demoUser.email,
      name: demoUser.name,
      tenantId: demoUser.tenant_id,
      roles: [demoUser.role],
      isDemo: true,
      isAuthenticated: true,
    };
  }

  return {
    bearer: null,
    email: null,
    name: null,
    tenantId: null,
    roles: [],
    isDemo: false,
    isAuthenticated: false,
  };
}

/** Client-side bearer getter for non-hook contexts (e.g. form submit handlers). */
export function getBearer(): string | null {
  // Try localStorage demo user first (synchronous, no async needed).
  const demoUser = getActiveUser();
  if (demoUser) return demoBearer(demoUser);
  // Real session handled by useShellForgeSession hook.
  return null;
}
