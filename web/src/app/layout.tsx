import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "ShellForge",
  description: "Enterprise control plane for NVIDIA OpenShell",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="min-h-screen antialiased">{children}</body>
    </html>
  );
}
