// Demo-mode auth helper.
//
// For the contest demo we don't need to wire the full OIDC code flow into
// the React app. Instead, we let the user "log in as" one of the seeded
// demo users and synthesize a local session token that the control plane
// would normally receive from Dex.
//
// In production this is replaced by NextAuth.js or Auth.js with the Dex
// OIDC provider — the bearer-token interface stays the same.

export interface DemoUser {
  subject: string;
  email: string;
  name: string;
  tenant_id: string;
  tenant_name: string;
  role: string;
  policy_template: string;
}

export const DEMO_USERS: DemoUser[] = [
  {
    subject: "08a8684b-db88-4b73-90a9-3cd1661f5466",
    email: "alice@acme-health.demo",
    name: "Alice Chen",
    tenant_id: "acme-health",
    tenant_name: "Acme Health Systems",
    role: "org:admin",
    policy_template: "hipaa-healthcare",
  },
  {
    subject: "1aa7f8db-7ad9-4f0f-b3e6-c8a8c4f6d5d2",
    email: "bob@acme-health.demo",
    name: "Bob Patel",
    tenant_id: "acme-health",
    tenant_name: "Acme Health Systems",
    role: "org:developer",
    policy_template: "hipaa-healthcare",
  },
  {
    subject: "2bb8e9ec-8be0-5a10-c4f7-d9b9d5g7e6e3",
    email: "carol@bolt-bank.demo",
    name: "Carol Rodriguez",
    tenant_id: "bolt-bank",
    tenant_name: "Bolt Bank",
    role: "org:admin",
    policy_template: "pci-payments",
  },
  {
    subject: "3cc9faff-9cf1-6b21-d5g8-e0c0e6h8f7f4",
    email: "dave@nexus-corp.demo",
    name: "Dave Park",
    tenant_id: "nexus-corp",
    tenant_name: "Nexus Corp",
    role: "org:admin",
    policy_template: "soc2-saas",
  },
];

const STORAGE_KEY = "shellforge.demo_user";

export function setActiveUser(user: DemoUser) {
  if (typeof window === "undefined") return;
  localStorage.setItem(STORAGE_KEY, JSON.stringify(user));
}

export function getActiveUser(): DemoUser | null {
  if (typeof window === "undefined") return null;
  const v = localStorage.getItem(STORAGE_KEY);
  if (!v) return null;
  try {
    return JSON.parse(v) as DemoUser;
  } catch {
    return null;
  }
}

export function clearActiveUser() {
  if (typeof window === "undefined") return;
  localStorage.removeItem(STORAGE_KEY);
}

// In demo mode we use a Bearer header carrying the user's subject.
// The control plane's demo-bypass auth middleware (gated by env var)
// accepts these and validates the user against the DB.
export function demoBearer(user: DemoUser): string {
  return `demo:${user.subject}:${user.tenant_id}:${user.role}`;
}
