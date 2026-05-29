"use client";

import { useEffect, useState } from "react";
import { X, Terminal, Copy, Info, AlertTriangle, Check } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { apiFetch, type SandboxOut } from "@/lib/api";
import { getBearer } from "@/lib/session";

interface ConnectionInfo {
  backend: string;
  is_real: boolean;
  summary: string;
  cli_command?: string | null;
  ssh_command?: string | null;
  web_terminal_url?: string | null;
  notes: string[];
}

interface Props {
  sandbox: SandboxOut;
  onClose: () => void;
}

export function ConnectionModal({ sandbox, onClose }: Props) {
  const [info, setInfo] = useState<ConnectionInfo | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState<string | null>(null);

  useEffect(() => {
    const bearer = getBearer();
    if (!bearer) return;
    apiFetch<ConnectionInfo>(`/sandboxes/${sandbox.id}/connection`, { bearer })
      .then(setInfo)
      .catch((e) => setError(e instanceof Error ? e.message : String(e)));
  }, [sandbox.id]);

  const copy = async (label: string, text: string) => {
    await navigator.clipboard.writeText(text);
    setCopied(label);
    setTimeout(() => setCopied(null), 1500);
  };

  return (
    <div
      className="fixed inset-0 z-50 bg-black/70 backdrop-blur-sm flex items-start justify-center p-8 overflow-y-auto"
      onClick={onClose}
    >
      <div
        className="bg-card border rounded-lg shadow-2xl w-full max-w-2xl mt-12"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between px-6 py-4 border-b">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-md bg-primary/10 flex items-center justify-center">
              <Terminal className="w-4 h-4 text-primary" />
            </div>
            <div>
              <div className="font-semibold">{sandbox.name}</div>
              <div className="text-xs text-muted-foreground font-mono">
                {sandbox.compute_uid.slice(0, 16)}
              </div>
            </div>
          </div>
          <Button variant="ghost" size="icon" onClick={onClose}>
            <X className="w-4 h-4" />
          </Button>
        </div>

        <div className="p-6 space-y-5">
          {error && (
            <div className="text-sm text-destructive bg-destructive/10 px-3 py-2 rounded border border-destructive/30">
              {error}
            </div>
          )}

          {info && (
            <>
              <div className="flex items-center gap-2">
                <Badge variant={info.is_real ? "success" : "secondary"}>
                  Backend: {info.backend}
                </Badge>
                {!info.is_real && (
                  <Badge variant="outline" className="border-amber-500/40 text-amber-500">
                    <AlertTriangle className="w-3 h-3 mr-1" />
                    Demo / no real container
                  </Badge>
                )}
                <Badge variant="outline">{sandbox.phase}</Badge>
              </div>

              <div className="text-sm leading-relaxed text-foreground/80">
                {info.summary}
              </div>

              {info.cli_command && (
                <CommandBlock
                  label="CLI"
                  description="OpenShell CLI on your laptop. You + teammates with access can both run this."
                  command={info.cli_command}
                  onCopy={() => copy("cli", info.cli_command!)}
                  copied={copied === "cli"}
                />
              )}

              {info.ssh_command && (
                <CommandBlock
                  label="SSH (with editor attach)"
                  description="Same gateway, with IDE forwarding (VSCode / Cursor)."
                  command={info.ssh_command}
                  onCopy={() => copy("ssh", info.ssh_command!)}
                  copied={copied === "ssh"}
                />
              )}

              {info.notes.length > 0 && (
                <div className="border rounded-md bg-secondary/30 p-4">
                  <div className="flex items-center gap-2 text-xs uppercase tracking-wide font-semibold text-muted-foreground mb-2">
                    <Info className="w-3.5 h-3.5" />
                    Notes
                  </div>
                  <ul className="space-y-1.5 text-sm">
                    {info.notes.map((n, i) => (
                      <li key={i} className="flex gap-2">
                        <span className="text-muted-foreground">·</span>
                        <span className="text-foreground/80">{n}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              <div className="border rounded-md p-4 bg-background">
                <div className="text-xs uppercase tracking-wide font-semibold text-muted-foreground mb-2">
                  Sharing access with teammates
                </div>
                <ul className="space-y-1.5 text-sm text-foreground/80">
                  <li>
                    1. Invite them to the <span className="font-mono text-primary">{sandbox.labels["shellforge.io/tenant"]}</span>{" "}
                    org via the Users page (or SCIM from your IdP).
                  </li>
                  <li>
                    2. They sign in via SSO; their org-scoped JWT lands them here automatically.
                  </li>
                  <li>
                    3. {info.is_real ? "Both share the same gateway endpoint — concurrent CLI/SSH sessions OK." : "Both see the same sandbox row + audit events. (Real-shared-shell needs OpenShell backend.)"}
                  </li>
                </ul>
              </div>
            </>
          )}

          {!info && !error && (
            <div className="text-sm text-muted-foreground">Loading connection info…</div>
          )}
        </div>
      </div>
    </div>
  );
}

function CommandBlock({
  label,
  description,
  command,
  onCopy,
  copied,
}: {
  label: string;
  description: string;
  command: string;
  onCopy: () => void;
  copied: boolean;
}) {
  return (
    <div>
      <div className="flex items-center justify-between mb-1">
        <div className="text-xs uppercase tracking-wide font-semibold text-muted-foreground">{label}</div>
        <Button variant="ghost" size="sm" onClick={onCopy} className="h-6 text-[10px]">
          {copied ? <Check className="w-3 h-3 mr-1 text-green-500" /> : <Copy className="w-3 h-3 mr-1" />}
          {copied ? "Copied" : "Copy"}
        </Button>
      </div>
      <div className="text-xs text-muted-foreground mb-2">{description}</div>
      <pre className="font-mono text-xs bg-background border rounded-md p-3 overflow-x-auto">
        $ {command}
      </pre>
    </div>
  );
}
