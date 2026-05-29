"use client";

import { useRouter } from "next/navigation";
import { Shield, Lock, ExternalLink } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { DEMO_USERS, setActiveUser } from "@/lib/demo-auth";
import { signIn } from "next-auth/react";

export default function LoginPage() {
  const router = useRouter();

  const loginAsDemoUser = (subject: string) => {
    const user = DEMO_USERS.find((u) => u.subject === subject);
    if (!user) return;
    setActiveUser(user);
    router.push("/dashboard");
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-background bg-grid p-6 relative">
      <div className="w-full max-w-md space-y-4">
        {/* Logo + title */}
        <div className="text-center mb-6">
          <div className="inline-flex w-12 h-12 rounded-xl bg-gradient-to-br from-blue-600 to-indigo-700 items-center justify-center shadow-lg shadow-blue-500/20 mb-4">
            <Shield className="w-6 h-6 text-white" />
          </div>
          <h1 className="text-2xl font-bold tracking-tight">ShellForge</h1>
          <p className="text-sm text-muted-foreground mt-1">
            Enterprise control plane for NVIDIA OpenShell
          </p>
        </div>

        {/* Real OIDC SSO */}
        <Card className="border-primary/30">
          <CardHeader className="pb-3">
            <CardTitle className="text-sm flex items-center gap-2">
              <Lock className="w-4 h-4 text-primary" />
              Sign in with SSO
              <Badge variant="outline" className="text-[10px] ml-auto">Dex OIDC</Badge>
            </CardTitle>
          </CardHeader>
          <CardContent>
            <Button
              className="w-full"
              onClick={() => signIn("dex", { callbackUrl: "/dashboard" })}
            >
              <ExternalLink className="w-4 h-4" />
              Continue with SSO
            </Button>
            <p className="text-xs text-muted-foreground mt-2 text-center">
              Dex broker → Okta / Azure AD / Google / LDAP / SAML
            </p>
          </CardContent>
        </Card>

        {/* Demo users — shown only in local dev */}
        <Card className="border-border/50 opacity-90">
          <CardHeader className="pb-3">
            <CardTitle className="text-sm text-muted-foreground flex items-center gap-2">
              Demo users
              <Badge variant="secondary" className="text-[10px]">ENV=local only</Badge>
            </CardTitle>
          </CardHeader>
          <CardContent className="p-0">
            <div className="divide-y divide-border/50">
              {DEMO_USERS.map((user) => (
                <button
                  key={user.subject}
                  onClick={() => loginAsDemoUser(user.subject)}
                  className="w-full px-5 py-3 text-left hover:bg-secondary/40 transition-colors flex items-center justify-between"
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
          </CardContent>
        </Card>

        <p className="text-center text-xs text-muted-foreground">
          PolyForm Noncommercial 1.0.0 · sanskarjaiswal2001/ShellForge
        </p>
      </div>
    </div>
  );
}
