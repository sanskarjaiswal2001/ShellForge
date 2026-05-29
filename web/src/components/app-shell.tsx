"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import {
  Shield,
  Box,
  FileText,
  Activity,
  FileSignature,
  LogOut,
  ChevronDown,
  Moon,
  Sun,
  KeyRound,
} from "lucide-react";
import { signOut, useSession } from "next-auth/react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { clearActiveUser, DEMO_USERS, getActiveUser, setActiveUser } from "@/lib/demo-auth";
import { cn } from "@/lib/cn";

const NAV = [
  { href: "/dashboard", label: "Overview", icon: Activity },
  { href: "/sandboxes", label: "Sandboxes", icon: Box },
  { href: "/policies", label: "Policies", icon: FileText },
  { href: "/providers", label: "Providers", icon: KeyRound },
  { href: "/audit", label: "Audit", icon: Shield },
  { href: "/compliance", label: "Compliance", icon: FileSignature },
];

interface ActiveUser {
  name: string;
  email: string;
  tenantId: string;
  tenantName: string;
  role: string;
  isDemo: boolean;
  subject?: string;
}

export function AppShell({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const { data: session } = useSession();
  const [activeUser, setUser] = useState<ActiveUser | null>(null);
  const [tenantMenuOpen, setTenantMenuOpen] = useState(false);
  const [theme, setTheme] = useState<"dark" | "light">("dark");

  useEffect(() => {
    // Resolve active user: real NextAuth session > demo localStorage.
    if (session?.user) {
      const s = session as any;
      setUser({
        name: session.user.name ?? session.user.email ?? "Unknown",
        email: session.user.email ?? "",
        tenantId: s.tenant_id ?? "unknown",
        tenantName: s.tenant_id ?? "Unknown",
        role: (s.roles ?? [])[0] ?? "unknown",
        isDemo: false,
      });
    } else {
      const demo = getActiveUser();
      if (!demo) {
        router.replace("/login");
        return;
      }
      setUser({
        name: demo.name,
        email: demo.email,
        tenantId: demo.tenant_id,
        tenantName: demo.tenant_name,
        role: demo.role,
        isDemo: true,
        subject: demo.subject,
      });
    }

    const stored = (localStorage.getItem("shellforge.theme") as "dark" | "light" | null) ?? "dark";
    setTheme(stored);
    document.documentElement.classList.toggle("light", stored === "light");
  }, [router, session]);

  const toggleTheme = () => {
    const next = theme === "dark" ? "light" : "dark";
    setTheme(next);
    localStorage.setItem("shellforge.theme", next);
    document.documentElement.classList.toggle("light", next === "light");
  };

  const handleSignOut = async () => {
    if (activeUser?.isDemo) {
      clearActiveUser();
      router.push("/login");
    } else {
      await signOut({ callbackUrl: "/login" });
    }
  };

  if (!activeUser) return null;

  return (
    <div className="min-h-screen flex flex-col">
      <header className="flex items-center justify-between border-b bg-card px-6 h-14 sticky top-0 z-30">
        <div className="flex items-center gap-2">
          <div className="w-7 h-7 rounded-md bg-gradient-to-br from-blue-600 to-indigo-700 flex items-center justify-center">
            <Shield className="w-4 h-4 text-white" />
          </div>
          <span className="font-semibold tracking-tight">ShellForge</span>
          <Badge variant="outline" className="text-[10px]">Control Plane</Badge>
          {activeUser.isDemo && (
            <Badge variant="secondary" className="text-[10px]">Demo mode</Badge>
          )}
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={toggleTheme}
            className="w-8 h-8 rounded-md hover:bg-secondary flex items-center justify-center"
            title={`Switch to ${theme === "dark" ? "light" : "dark"} mode`}
          >
            {theme === "dark" ? <Sun className="w-4 h-4" /> : <Moon className="w-4 h-4" />}
          </button>

          <div className="relative">
            <button
              onClick={() => setTenantMenuOpen((v) => !v)}
              className="flex items-center gap-2 px-3 py-1.5 rounded-md hover:bg-secondary text-sm"
            >
              <span className="tenant-chip">{activeUser.tenantName}</span>
              <div className="text-left">
                <div className="text-xs font-medium">{activeUser.name}</div>
                <div className="text-[10px] text-muted-foreground">{activeUser.role}</div>
              </div>
              <ChevronDown className="w-4 h-4 text-muted-foreground" />
            </button>

            {tenantMenuOpen && (
              <div
                className="absolute right-0 mt-1 w-72 bg-card border rounded-md shadow-lg z-50 animate-fade-in"
                onMouseLeave={() => setTenantMenuOpen(false)}
              >
                <div className="px-3 py-2 text-[10px] uppercase tracking-wide text-muted-foreground border-b">
                  {activeUser.isDemo ? "Switch demo user" : "Signed in via SSO"}
                </div>

                {activeUser.isDemo && DEMO_USERS.map((u) => (
                  <button
                    key={u.subject}
                    onClick={() => {
                      setActiveUser(u);
                      setTenantMenuOpen(false);
                      window.location.reload();
                    }}
                    className={cn(
                      "w-full text-left px-3 py-2 hover:bg-secondary text-sm border-b last:border-b-0",
                      u.subject === activeUser.subject && "bg-secondary/50"
                    )}
                  >
                    <div className="flex items-center justify-between">
                      <div>
                        <div className="font-medium">{u.name}</div>
                        <div className="text-xs text-muted-foreground">{u.email}</div>
                      </div>
                      <Badge variant="outline" className="text-[10px]">{u.tenant_id}</Badge>
                    </div>
                  </button>
                ))}

                {!activeUser.isDemo && (
                  <div className="px-3 py-2 text-sm text-muted-foreground">
                    <div className="font-medium text-foreground">{activeUser.email}</div>
                    <div className="text-xs mt-0.5">Tenant: {activeUser.tenantId}</div>
                  </div>
                )}

                <button
                  onClick={handleSignOut}
                  className="w-full text-left px-3 py-2 hover:bg-secondary text-sm text-destructive flex items-center gap-2 border-t"
                >
                  <LogOut className="w-3.5 h-3.5" /> Sign out
                </button>
              </div>
            )}
          </div>
        </div>
      </header>

      <div className="flex flex-1 overflow-hidden">
        <nav className="w-56 border-r bg-card flex flex-col gap-0.5 p-3 shrink-0">
          {NAV.map((item) => {
            const Icon = item.icon;
            const active = pathname.startsWith(item.href);
            return (
              <Link
                key={item.href}
                href={item.href}
                className={cn(
                  "flex items-center gap-2.5 px-3 py-2 rounded-md text-sm font-medium transition-colors",
                  active
                    ? "bg-primary text-primary-foreground"
                    : "text-muted-foreground hover:text-foreground hover:bg-secondary"
                )}
              >
                <Icon className="w-4 h-4" />
                {item.label}
              </Link>
            );
          })}
          <div className="mt-auto px-3 py-2 text-[10px] text-muted-foreground">
            <div className="font-mono">v0.1.0 · alpha</div>
            <div className="mt-1">Wraps NVIDIA OpenShell</div>
          </div>
        </nav>

        <main className="flex-1 overflow-y-auto bg-background">{children}</main>
      </div>
    </div>
  );
}
