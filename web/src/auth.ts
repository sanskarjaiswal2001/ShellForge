/**
 * NextAuth v5 configuration — Dex as OIDC provider.
 *
 * Auth flow:
 *   Browser → NextAuth login → redirect to Dex /auth
 *     → Dex validates (static password / Okta / Azure AD etc.)
 *     → Redirect back to NextAuth callback
 *     → Token stored in encrypted NextAuth session cookie
 *     → Access token forwarded to control-plane as Bearer header
 *
 * The `tenant_id` and `roles` claims are injected by Dex from the user's
 * group membership. The control-plane validates them independently.
 *
 * To swap IdP: change OIDC_ISSUER in .env to point at any RFC-6749 IdP.
 * No code changes required — Dex (or the new IdP) is the token source.
 */

import NextAuth from "next-auth";
import type { NextAuthConfig } from "next-auth";

const config: NextAuthConfig = {
  providers: [
    {
      id: "dex",
      name: "Dex SSO",
      type: "oidc",
      issuer: process.env.OIDC_ISSUER ?? "http://localhost:5556/dex",
      clientId: process.env.OIDC_CLIENT_ID ?? "shellforge-web",
      clientSecret: process.env.OIDC_CLIENT_SECRET ?? "local-dev-only-replace-in-prod",
      // Request groups claim so we get roles from Dex.
      authorization: {
        params: {
          scope: "openid email profile groups",
        },
      },
    },
  ],

  callbacks: {
    async jwt({ token, account, profile }) {
      if (account && profile) {
        // Extract ShellForge claims from the ID token.
        token.access_token = account.access_token;
        token.id_token = account.id_token;
        token.tenant_id = (profile as any).tenant_id ?? null;
        token.roles = (profile as any).roles ?? (profile as any).groups ?? [];
        token.name = profile.name ?? profile.email;
      }
      return token;
    },
    async session({ session, token }) {
      return {
        ...session,
        access_token: token.access_token as string | undefined,
        id_token: token.id_token as string | undefined,
        tenant_id: token.tenant_id as string | null,
        roles: token.roles as string[],
      };
    },
  },

  pages: {
    signIn: "/login",
    error: "/login",
  },

  // In production: use database adapter for session persistence.
  // For local dev: JWT strategy (no extra DB table needed).
  session: { strategy: "jwt" },
};

export const { handlers, auth, signIn, signOut } = NextAuth(config);
