"use client";

import { api } from "@/lib/api-client";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { createClient } from "@/lib/supabase/client";
import { useEffect, useState } from "react";
import { toast } from "sonner";
import { Check, CreditCard, Link2, Link2Off, RefreshCw, UserPlus, Trash2 } from "lucide-react";

interface Org { id: string; name: string; org_number: string | null; vat_number: string | null; address: string | null; plan: string; }
interface Me { email: string; role: string; organization: Org; }
interface Member { id: string; user_id: string; role: string; created_at: string; }

type Tab = "account" | "team" | "billing" | "integrations" | "notifications";

export default function SettingsPage() {
  const [me, setMe] = useState<Me | null>(null);
  const [members, setMembers] = useState<Member[]>([]);
  const [loading, setLoading] = useState(false);
  const [tab, setTab] = useState<Tab>("account");
  const supabase = createClient();
  
  // Company form
  const [companyForm, setCompanyForm] = useState({ company_name: "", org_number: "", vat_number: "", address: "" });
  const [companySaving, setCompanySaving] = useState(false);
  const [companyOk, setCompanyOk] = useState(false);
  const [companyError, setCompanyError] = useState<string | null>(null);

  // Password form
  const [pwForm, setPwForm] = useState({ next: "", confirm: "" });
  const [pwSaving, setPwSaving] = useState(false);
  const [pwOk, setPwOk] = useState(false);
  const [pwError, setPwError] = useState<string | null>(null);

  // Invite form
  const [inviteEmail, setInviteEmail] = useState("");
  const [inviteRole, setInviteRole] = useState("MEMBER");
  const [inviting, setInviting] = useState(false);
  const [inviteOk, setInviteOk] = useState(false);
  const [inviteError, setInviteError] = useState<string | null>(null);

  async function loadMembers() {
    try { setMembers(await api.get<Member[]>("/api/team")); } catch {}
  }

  useEffect(() => {
    Promise.all([
      api.get<Me>("/api/auth/me"),
      api.get<Member[]>("/api/team"),
    ]).then(([meData, teamData]) => {
      setMe(meData);
      setMembers(teamData);
      setCompanyForm({
        company_name: meData.organization.name,
        org_number: meData.organization.org_number ?? "",
        vat_number: meData.organization.vat_number ?? "",
        address: meData.organization.address ?? "",
      });
    }).catch(() => {}).finally(() => setLoading(false));
  }, []);

  function setC(f: string, v: string) { setCompanyForm((s) => ({ ...s, [f]: v })); }

  async function handleCompany(e: React.FormEvent) {
    e.preventDefault(); setCompanySaving(true); setCompanyError(null); setCompanyOk(false);
    try {
      await api.put("/api/auth/org", {
        company_name: companyForm.company_name,
        org_number: companyForm.org_number || null,
        vat_number: companyForm.vat_number || null,
        address: companyForm.address || null,
      });
      setCompanyOk(true);
      setTimeout(() => setCompanyOk(false), 3000);
    } catch (e: any) { setCompanyError(e.message); } finally { setCompanySaving(false); }
  }

  async function handlePassword(e: React.FormEvent) {
    e.preventDefault(); setPwError(null); setPwOk(false);
    if (pwForm.next !== pwForm.confirm) { setPwError("Passwords don't match"); return; }
    if (pwForm.next.length < 8) { setPwError("Minimum 8 characters"); return; }
    setPwSaving(true);
    try {
      const { error } = await supabase.auth.updateUser({ password: pwForm.next });
      if (error) throw new Error(error.message);
      setPwForm({ next: "", confirm: "" });
      setPwOk(true);
      setTimeout(() => setPwOk(false), 3000);
    } catch (e: any) { setPwError(e.message); } finally { setPwSaving(false); }
  }

  async function handleInvite(e: React.FormEvent) {
    e.preventDefault(); setInviting(true); setInviteError(null); setInviteOk(false);
    try {
      await api.post("/api/team/invite", { email: inviteEmail, role: inviteRole });
      setInviteEmail(""); setInviteOk(true);
      setTimeout(() => setInviteOk(false), 3000);
      await loadMembers();
    } catch (e: any) { setInviteError(e.message); } finally { setInviting(false); }
  }

  async function handleRemove(memberId: string) {
    if (!confirm("Remove this team member?")) return;
    try {
      await api.delete(`/api/team/${memberId}`);
      await loadMembers();
    } catch (e: any) { setInviteError(e.message); }
  }

  async function handleRoleChange(memberId: string, role: string) {
    try {
      await api.patch(`/api/team/${memberId}/role`, { role });
      await loadMembers();
    } catch (e: any) { setInviteError(e.message); }
  }

  if (loading) return (
    <div className="space-y-4 animate-pulse max-w-2xl">
      <div className="h-8 w-32 rounded bg-gray-100" />
      <div className="h-48 rounded-xl bg-gray-100" />
    </div>
  );

  const isOwner = me?.role === "OWNER";

  return (
    <div className="max-w-2xl space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-[#1a2332]">Settings</h1>
        <p className="text-sm text-muted-foreground">Manage your account and organization</p>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 border-b">
        {(["account", "team", "billing", "integrations", "notifications"] as Tab[]).map((t) => (
          <button key={t} onClick={() => setTab(t)}
            className={`px-4 py-2 text-sm font-medium capitalize border-b-2 -mb-px transition-colors ${
              tab === t ? "border-[#1a2332] text-[#1a2332]" : "border-transparent text-muted-foreground hover:text-gray-900"
            }`}>
            {t}
          </button>
        ))}
      </div>

      {tab === "account" && (
        <>
          {/* Account info */}
          <div className="rounded-xl border bg-white p-6 space-y-4">
            <h2 className="font-semibold text-gray-900">Account</h2>
            <div className="space-y-1.5">
              <Label>Email</Label>
              <p className="rounded-md border border-gray-200 bg-gray-50 px-3 py-2 text-sm text-gray-600">{me?.email}</p>
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-1.5">
                <Label>Role</Label>
                <p className="rounded-md border border-gray-200 bg-gray-50 px-3 py-2 text-sm text-gray-600 capitalize">{me?.role.toLowerCase()}</p>
              </div>
              <div className="space-y-1.5">
                <Label>Plan</Label>
                <p className="rounded-md border border-gray-200 bg-gray-50 px-3 py-2 text-sm text-gray-600 capitalize">
                  {me?.organization.plan.toLowerCase()} {me?.organization.plan === "FREE" && "— Early access"}
                </p>
              </div>
            </div>
          </div>

          {/* Company details */}
          <form onSubmit={handleCompany} className="rounded-xl border bg-white p-6 space-y-4">
            <h2 className="font-semibold text-gray-900">Company details</h2>
            <p className="text-xs text-muted-foreground">Shown on invoices and purchase orders.</p>
            {[
              { id: "company_name", label: "Company name *", placeholder: "Svensson AB", required: true },
              { id: "org_number", label: "Org number", placeholder: "556000-0000" },
              { id: "vat_number", label: "VAT number", placeholder: "SE556000000001" },
              { id: "address", label: "Address", placeholder: "Storgatan 1, Stockholm" },
            ].map(({ id, label, placeholder, required }) => (
              <div key={id} className="space-y-1.5">
                <Label htmlFor={id}>{label}</Label>
                <input id={id} required={required} value={(companyForm as any)[id]}
                  onChange={(e) => setC(id, e.target.value)} placeholder={placeholder}
                  className="block w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-[#1a2332] focus:outline-none focus:ring-1 focus:ring-[#1a2332]" />
              </div>
            ))}
            {companyError && <p className="text-sm text-red-600">{companyError}</p>}
            <div className="flex items-center gap-3">
              <Button type="submit" disabled={companySaving} className="bg-[#1a2332] hover:bg-[#2a3342] text-white">
                {companySaving ? "Saving…" : "Save changes"}
              </Button>
              {companyOk && <span className="flex items-center gap-1 text-sm text-green-600"><Check className="h-4 w-4" />Saved</span>}
            </div>
          </form>

          {/* Change password */}
          <form onSubmit={handlePassword} className="rounded-xl border bg-white p-6 space-y-4">
            <h2 className="font-semibold text-gray-900">Change password</h2>
            {[
              { id: "next", label: "New password", placeholder: "Min. 8 characters" },
              { id: "confirm", label: "Confirm new password", placeholder: "Repeat password" },
            ].map(({ id, label, placeholder }) => (
              <div key={id} className="space-y-1.5">
                <Label htmlFor={id}>{label}</Label>
                <input id={id} type="password" required minLength={8} value={(pwForm as any)[id]}
                  onChange={(e) => setPwForm((s) => ({ ...s, [id]: e.target.value }))} placeholder={placeholder}
                  className="block w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-[#1a2332] focus:outline-none focus:ring-1 focus:ring-[#1a2332]" />
              </div>
            ))}
            {pwError && <p className="text-sm text-red-600">{pwError}</p>}
            <div className="flex items-center gap-3">
              <Button type="submit" disabled={pwSaving} className="bg-[#1a2332] hover:bg-[#2a3342] text-white">
                {pwSaving ? "Updating…" : "Update password"}
              </Button>
              {pwOk && <span className="flex items-center gap-1 text-sm text-green-600"><Check className="h-4 w-4" />Updated</span>}
            </div>
          </form>
        </>
      )}

      {tab === "team" && (
        <div className="space-y-6">
          {/* Members list */}
          <div className="rounded-xl border bg-white overflow-hidden">
            <div className="px-6 py-4 border-b">
              <h2 className="font-semibold text-gray-900">Team members</h2>
              <p className="text-xs text-muted-foreground mt-0.5">{members.length} member{members.length !== 1 ? "s" : ""}</p>
            </div>
            <div className="divide-y">
              {members.map((m) => (
                <div key={m.id} className="flex items-center justify-between px-6 py-3">
                  <div>
                    <p className="text-sm font-medium text-gray-900">User {m.user_id.slice(0, 8)}…</p>
                    <p className="text-xs text-muted-foreground">Joined {new Date(m.created_at).toLocaleDateString("sv-SE")}</p>
                  </div>
                  <div className="flex items-center gap-3">
                    {isOwner ? (
                      <select value={m.role}
                        onChange={(e) => handleRoleChange(m.id, e.target.value)}
                        className="rounded-md border border-gray-200 px-2 py-1 text-xs focus:border-[#1a2332] focus:outline-none">
                        <option value="OWNER">Owner</option>
                        <option value="ADMIN">Admin</option>
                        <option value="MEMBER">Member</option>
                      </select>
                    ) : (
                      <span className="rounded bg-gray-100 px-2 py-0.5 text-xs font-medium capitalize">{m.role.toLowerCase()}</span>
                    )}
                    {isOwner && (
                      <Button variant="ghost" size="sm" className="h-7 w-7 p-0 text-red-400 hover:text-red-600"
                        onClick={() => handleRemove(m.id)}>
                        <Trash2 className="h-3.5 w-3.5" />
                      </Button>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Invite form */}
          {isOwner && (
            <form onSubmit={handleInvite} className="rounded-xl border bg-white p-6 space-y-4">
              <h2 className="font-semibold text-gray-900 flex items-center gap-2">
                <UserPlus className="h-4 w-4" />Invite team member
              </h2>
              <div className="flex gap-3">
                <input type="email" required placeholder="colleague@company.se" value={inviteEmail}
                  onChange={(e) => setInviteEmail(e.target.value)}
                  className="flex-1 rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-[#1a2332] focus:outline-none focus:ring-1 focus:ring-[#1a2332]" />
                <select value={inviteRole} onChange={(e) => setInviteRole(e.target.value)}
                  className="rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-[#1a2332] focus:outline-none focus:ring-1 focus:ring-[#1a2332]">
                  <option value="MEMBER">Member</option>
                  <option value="ADMIN">Admin</option>
                </select>
              </div>
              {inviteError && <p className="text-sm text-red-600">{inviteError}</p>}
              <div className="flex items-center gap-3">
                <Button type="submit" disabled={inviting} className="bg-[#1a2332] hover:bg-[#2a3342] text-white">
                  {inviting ? "Inviting…" : "Send invite"}
                </Button>
                {inviteOk && <span className="flex items-center gap-1 text-sm text-green-600"><Check className="h-4 w-4" />Invited</span>}
              </div>
            </form>
          )}
        </div>
      )}

      {tab === "billing" && (
        <BillingTab plan={me?.organization.plan ?? "FREE"} />
      )}

      {tab === "integrations" && <IntegrationsTab />}

      {tab === "notifications" && <NotificationsTab />}
    </div>
  );
}

function BillingTab({ plan }: { plan: string }) {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleUpgrade() {
    setLoading(true); setError(null);
    try {
      const res = await api.post<{ url: string }>("/api/billing/checkout", {});
      window.location.href = res.url;
    } catch (e: any) {
      setError(e.message ?? "Failed to open checkout");
    } finally {
      setLoading(false);
    }
  }

  async function handlePortal() {
    setLoading(true); setError(null);
    try {
      const res = await api.post<{ url: string }>("/api/billing/portal", {});
      window.location.href = res.url;
    } catch (e: any) {
      setError(e.message ?? "Failed to open portal");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="space-y-4">
      <div className="rounded-xl border bg-white p-6 space-y-4">
        <h2 className="font-semibold text-gray-900 flex items-center gap-2">
          <CreditCard className="h-4 w-4" />Subscription
        </h2>

        <div className="flex items-center gap-3">
          <span className={`rounded-full px-3 py-1 text-sm font-medium ${
            plan === "PRO" ? "bg-[#1a2332] text-white" : "bg-gray-100 text-gray-700"
          }`}>
            {plan === "PRO" ? "PRO" : "Free"}
          </span>
          {plan === "PRO" && (
            <span className="text-sm text-gray-500">All features unlocked</span>
          )}
        </div>

        {plan === "FREE" && (
          <div className="rounded-lg border border-[#1a2332]/20 bg-[#1a2332]/5 p-4 space-y-3">
            <p className="text-sm font-medium text-[#1a2332]">Upgrade to Varuflow PRO</p>
            <ul className="space-y-1 text-sm text-gray-600">
              {["Unlimited invoices", "Team members", "Peppol XML export", "Analytics", "Priority support"].map((f) => (
                <li key={f} className="flex items-center gap-2">
                  <Check className="h-3.5 w-3.5 text-green-500 shrink-0" />{f}
                </li>
              ))}
            </ul>
            <Button onClick={handleUpgrade} disabled={loading} className="bg-[#1a2332] hover:bg-[#2a3342] text-white">
              {loading ? "Loading…" : "Upgrade now"}
            </Button>
          </div>
        )}

        {plan === "PRO" && (
          <Button variant="outline" onClick={handlePortal} disabled={loading}>
            {loading ? "Loading…" : "Manage subscription"}
          </Button>
        )}

        {error && <p className="text-sm text-red-600">{error}</p>}
      </div>
    </div>
  );
}

function IntegrationsTab() {
  const [status, setStatus] = useState<{ connected: boolean; token_expiry?: string } | null>(null);
  const [syncing, setSyncing] = useState<"invoices" | "customers" | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    api.get<{ connected: boolean; token_expiry?: string }>("/api/integrations/fortnox/status")
      .then(setStatus).catch(() => setStatus({ connected: false })).finally(() => setLoading(false));
  }, []);

  async function handleConnect() {
    window.location.href = `${process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"}/api/integrations/fortnox/connect`;
  }

  async function handleDisconnect() {
    if (!confirm("Disconnect Fortnox?")) return;
    try {
      await api.delete("/api/integrations/fortnox/disconnect");
      setStatus({ connected: false });
      toast.success("Fortnox disconnected");
    } catch (e: any) { toast.error(e.message); }
  }

  async function handleSync(type: "invoices" | "customers") {
    setSyncing(type);
    try {
      const res = await api.post<{ synced: number; errors: string[] }>(
        `/api/integrations/fortnox/sync-${type}`, {}
      );
      toast.success(`Synced ${res.synced} ${type}${res.errors.length ? ` (${res.errors.length} errors)` : ""}`);
    } catch (e: any) { toast.error(e.message); }
    finally { setSyncing(null); }
  }

  return (
    <div className="space-y-4">
      <div className="rounded-xl border border-gray-200 bg-white p-6 space-y-5 shadow-sm">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-blue-50">
              <span className="text-lg font-bold text-blue-700">F</span>
            </div>
            <div>
              <h2 className="font-semibold text-gray-900">Fortnox</h2>
              <p className="text-xs text-gray-400">Swedish accounting software</p>
            </div>
          </div>
          {loading ? (
            <div className="h-8 w-24 animate-pulse rounded-lg bg-gray-100" />
          ) : status?.connected ? (
            <span className="inline-flex items-center gap-1.5 rounded-full bg-emerald-50 px-3 py-1 text-xs font-semibold text-emerald-700 border border-emerald-200">
              <span className="h-1.5 w-1.5 rounded-full bg-emerald-500" />Connected
            </span>
          ) : (
            <span className="inline-flex items-center gap-1.5 rounded-full bg-gray-100 px-3 py-1 text-xs font-medium text-gray-500">
              Not connected
            </span>
          )}
        </div>

        {status?.connected ? (
          <div className="space-y-3">
            <p className="text-sm text-gray-500">
              Sync your data between Varuflow and Fortnox.
              {status.token_expiry && ` Token expires: ${new Date(status.token_expiry).toLocaleDateString("sv-SE")}`}
            </p>
            <div className="flex flex-wrap gap-2">
              <Button variant="outline" size="sm" disabled={syncing === "invoices"} onClick={() => handleSync("invoices")}>
                <RefreshCw className={`mr-1.5 h-3.5 w-3.5 ${syncing === "invoices" ? "animate-spin" : ""}`} />
                {syncing === "invoices" ? "Syncing…" : "Push invoices → Fortnox"}
              </Button>
              <Button variant="outline" size="sm" disabled={syncing === "customers"} onClick={() => handleSync("customers")}>
                <RefreshCw className={`mr-1.5 h-3.5 w-3.5 ${syncing === "customers" ? "animate-spin" : ""}`} />
                {syncing === "customers" ? "Syncing…" : "Pull customers ← Fortnox"}
              </Button>
              <Button variant="ghost" size="sm" className="text-red-500 hover:text-red-700 hover:bg-red-50 ml-auto" onClick={handleDisconnect}>
                <Link2Off className="mr-1.5 h-3.5 w-3.5" />Disconnect
              </Button>
            </div>
          </div>
        ) : (
          <div className="space-y-3">
            <p className="text-sm text-gray-500">
              Connect Fortnox to automatically sync invoices and import customers.
              Requires a Fortnox account with the bookkeeping add-on.
            </p>
            <Button onClick={handleConnect} className="bg-[#0f1724] hover:bg-[#1a2840] text-white">
              <Link2 className="mr-1.5 h-4 w-4" />Connect Fortnox
            </Button>
          </div>
        )}
      </div>
    </div>
  );
}

function NotificationsTab() {
  const [permission, setPermission] = useState<NotificationPermission | "unsupported">(
    typeof Notification === "undefined" ? "unsupported" : Notification.permission
  );
  const [requesting, setRequesting] = useState(false);

  async function handleEnable() {
    if (typeof Notification === "undefined") return;
    setRequesting(true);
    try {
      const result = await Notification.requestPermission();
      setPermission(result);
      if (result === "granted") {
        // Register SW push subscription
        const reg = await navigator.serviceWorker.getRegistration("/sw.js");
        if (reg) {
          toast.success("Notifications enabled");
        }
      }
    } finally {
      setRequesting(false);
    }
  }

  return (
    <div className="space-y-4">
      <div className="rounded-xl border bg-white p-6 space-y-5">
        <div>
          <h2 className="font-semibold text-gray-900">Push notifications</h2>
          <p className="mt-1 text-sm text-muted-foreground">
            Get notified about overdue invoices, low stock alerts, and payment confirmations.
          </p>
        </div>

        {permission === "unsupported" && (
          <div className="rounded-lg border border-yellow-200 bg-yellow-50 px-4 py-3 text-sm text-yellow-800">
            Your browser doesn&apos;t support push notifications.
          </div>
        )}

        {permission === "granted" && (
          <div className="flex items-center gap-3 rounded-lg border border-green-200 bg-green-50 px-4 py-3">
            <span className="flex h-8 w-8 items-center justify-center rounded-full bg-green-100">
              <Check className="h-4 w-4 text-green-600" />
            </span>
            <div>
              <p className="text-sm font-semibold text-green-900">Notifications enabled</p>
              <p className="text-xs text-green-700">You&apos;ll receive alerts for key events.</p>
            </div>
          </div>
        )}

        {permission === "denied" && (
          <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800">
            Notifications are blocked. To enable them, click the lock icon in your browser&apos;s address bar and allow notifications.
          </div>
        )}

        {permission === "default" && (
          <Button
            onClick={handleEnable}
            disabled={requesting}
            className="bg-[#1a2332] hover:bg-[#2a3342] text-white"
          >
            {requesting ? "Requesting…" : "Enable notifications"}
          </Button>
        )}

        <div className="space-y-3 pt-2 border-t">
          <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">What you&apos;ll be notified about</p>
          {[
            "Invoice overdue (past due date)",
            "Invoice paid via Stripe payment link",
            "Product stock below minimum threshold",
          ].map((label) => (
            <div key={label} className="flex items-center gap-2 text-sm text-gray-700">
              <span className="h-1.5 w-1.5 rounded-full bg-[#1a2332]" />
              {label}
            </div>
          ))}
        </div>
      </div>

      <div className="rounded-xl border bg-white p-6 space-y-3">
        <h2 className="font-semibold text-gray-900">Install app</h2>
        <p className="text-sm text-muted-foreground">
          Add Varuflow to your home screen for a native-like experience with offline access.
        </p>
        <p className="text-xs text-muted-foreground">
          On Chrome/Edge: look for the install icon (⊕) in the address bar.<br />
          On iOS Safari: tap Share → Add to Home Screen.
        </p>
      </div>
    </div>
  );
}
