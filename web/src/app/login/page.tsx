"use client";

import { useRouter } from "next/navigation";
import { Shield, Lock } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { DEMO_USERS, setActiveUser } from "@/lib/demo-auth";

export default function LoginPage() {
  const router = useRouter();

  const loginAs = (subject: string) => {
    const user = DEMO_USERS.find((u) => u.subject === subject);
    if (!user) return;
    setActiveUser(user);
    router.push("/dashboard");
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-background bg-grid p-6 relative">
      <div className="w-full max-w-md">
        <div className="text-center mb-8">
          <div className="inline-flex w-12 h-12 rounded-xl bg-gradient-to-br from-blue-600 to-indigo-700 items-center justify-center shadow-lg shadow-blue-500/20 mb-4">
            <Shield className="w-6 h-6 text-white" />
          </div>
          <h1 className="text-2xl font-bold tracking-tight">ShellForge</h1>
          <p className="text-sm text-muted-foreground mt-1">
            Enterprise control plane for NVIDIA OpenShell
          </p>
        </div>

        <div className="bg-card border rounded-lg shadow-sm overflow-hidden">
          <div className="px-5 py-4 border-b bg-secondary/30">
            <div className="flex items-center gap-2">
              <Lock className="w-4 h-4 text-muted-foreground" />
              <span className="text-sm font-medium">Sign in with SSO</span>
              <Badge variant="outline" className="text-[10px] ml-auto">
                Dex OIDC
              </Badge>
            </div>
            <p className="text-xs text-muted-foreground mt-1.5">
              Demo: pick a seeded user. Prod connector swaps to Okta / Azure AD / Google.
            </p>
          </div>

          <div className="divide-y">
            {DEMO_USERS.map((user) => (
              <button
                key={user.subject}
                onClick={() => loginAs(user.subject)}
                className="w-full px-5 py-3 text-left hover:bg-secondary/50 transition-colors flex items-center justify-between group"
              >
                <div>
                  <div className="font-medium text-sm">{user.name}</div>
                  <div className="text-xs text-muted-foreground">{user.email}</div>
                </div>
                <div className="flex items-center gap-2">
                  <Badge variant="outline" className="text-[10px]">{user.role}</Badge>
                  <span className="tenant-chip text-[10px]">{user.tenant_id}</span>
                </div>
              </button>
            ))}
          </div>
        </div>

        <p className="text-center text-xs text-muted-foreground mt-6">
          PolyForm Noncommercial 1.0.0 · sanskarjaiswal2001/ShellForge
        </p>
      </div>
    </div>
  );
}
