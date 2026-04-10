"use client";

import { api } from "@/lib/api-client";
import { Label } from "@/components/ui/label";
import { createClient } from "@/lib/supabase/client";
import { useEffect, useState } from "react";
import { toast } from "sonner";
import { cn } from "@/lib/utils";
import { Check, CreditCard, Link2, Link2Off, RefreshCw, UserPlus, Trash2 } from "lucide-react";

interface Org { id: string; name: string; org_number: string | null; vat_number: string | null; address: string | null; plan: string; }
interface Me { email: string; role: string; organization: Org; }
interface Member { id: string; user_id: string; role: string; created_at: string; }

type Tab = "account" | "team" | "billing" | "integrations" | "notifications";

function Card({ children, className }: { children: React.ReactNode; className?: string }) {
  return (
    <div className={cn("rounded-xl border border-white/[0.06] bg-vf-surface p-6 space-y-4", className)}>
      {children}
    </div>
  );
}

export default function SettingsPage() {
  const [me, setMe]         = useState<Me | null>(null);
  const [members, setMembers] = useState<Member[]>([]);
  const [loading, setLoading] = useState(true);
  const [tab, setTab]       = useState<Tab>("account");
  const supabase = createClient();

  const [companyForm, setCompanyForm] = useState({ company_name: "", org_number: "", vat_number: "", address: "" });
  const [companySaving, setCompanySaving] = useState(false);
  const [companyOk, setCompanyOk] = useState(false);
  const [companyError, setCompanyError] = useState<string | null>(null);

  const [pwForm, setPwForm] = useState({ next: "", confirm: "" });
  const [pwSaving, setPwSaving] = useState(false);
  const [pwOk, setPwOk] = useState(false);
  const [pwError, setPwError] = useState<string | null>(null);

  const [inviteEmail, setInviteEmail] = useState("");
  const [inviteRole, setInviteRole]   = useState("MEMBER");
  const [inviting, setInviting]       = useState(false);
  const [inviteOk, setInviteOk]       = useState(false);
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
    } catch (e: unknown) { setCompanyError((e as Error).message); }
    finally { setCompanySaving(false); }
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
    } catch (e: unknown) { setPwError((e as Error).message); }
    finally { setPwSaving(false); }
  }

  async function handleInvite(e: React.FormEvent) {
    e.preventDefault(); setInviting(true); setInviteError(null); setInviteOk(false);
    try {
      await api.post("/api/team/invite", { email: inviteEmail, role: inviteRole });
      setInviteEmail(""); setInviteOk(true);
      setTimeout(() => setInviteOk(false), 3000);
      await loadMembers();
    } catch (e: unknown) { setInviteError((e as Error).message); }
    finally { setInviting(false); }
  }

  async function handleRemove(memberId: string) {
    if (!confirm("Remove this team member?")) return;
    try {
      await api.delete(`/api/team/${memberId}`);
      await loadMembers();
    } catch (e: unknown) { setInviteError((e as Error).message); }
  }

  async function handleRoleChange(memberId: string, role: string) {
    try {
      await api.patch(`/api/team/${memberId}/role`, { role });
      await loadMembers();
    } catch (e: unknown) { setInviteError((e as Error).message); }
  }

  if (loading) return (
    <div className="space-y-4 max-w-2xl">
      <div className="h-8 w-32 skeleton rounded" />
      <div className="h-48 skeleton rounded-xl" />
    </div>
  );

  const isOwner = me?.role === "OWNER";

  return (
    <div className="max-w-2xl space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-slate-100">Settings</h1>
        <p className="text-sm text-slate-600">Manage your account and organization</p>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 border-b border-white/[0.06]">
        {(["account", "team", "billing", "integrations", "notifications"] as Tab[]).map((t) => (
          <button key={t} onClick={() => setTab(t)}
            className={cn(
              "px-4 py-2 text-[13px] font-medium capitalize border-b-2 -mb-px transition-colors",
              tab === t ? "border-indigo-500 text-slate-100" : "border-transparent text-slate-600 hover:text-slate-300"
            )}>
            {t}
          </button>
        ))}
      </div>

      {tab === "account" && (
        <>
          {/* Account info */}
          <Card>
            <h2 className="font-semibold text-slate-100">Account</h2>
            <div className="space-y-1.5">
              <Label className="text-xs text-slate-400">Email</Label>
              <p className="rounded-lg border border-white/[0.06] bg-white/[0.03] px-3 py-2 text-sm text-slate-400">{me?.email}</p>
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-1.5">
                <Label className="text-xs text-slate-400">Role</Label>
                <p className="rounded-lg border border-white/[0.06] bg-white/[0.03] px-3 py-2 text-sm text-slate-400 capitalize">{me?.role.toLowerCase()}</p>
              </div>
              <div className="space-y-1.5">
                <Label className="text-xs text-slate-400">Plan</Label>
                <p className="rounded-lg border border-white/[0.06] bg-white/[0.03] px-3 py-2 text-sm text-slate-400 capitalize">
                  {me?.organization.plan.toLowerCase()} {me?.organization.plan === "FREE" && "— Early access"}
                </p>
              </div>
            </div>
          </Card>

          {/* Company details */}
          <form onSubmit={handleCompany}>
            <Card>
              <h2 className="font-semibold text-slate-100">Company details</h2>
              <p className="text-xs text-slate-600">Shown on invoices and purchase orders.</p>
              {[
                { id: "company_name", label: "Company name *", placeholder: "Svensson AB", required: true },
                { id: "org_number",   label: "Org number",     placeholder: "556000-0000" },
                { id: "vat_number",   label: "VAT number",     placeholder: "SE556000000001" },
                { id: "address",      label: "Address",        placeholder: "Storgatan 1, Stockholm" },
              ].map(({ id, label, placeholder, required }) => (
                <div key={id} className="space-y-1.5">
                  <Label htmlFor={id} className="text-xs text-slate-400">{label}</Label>
                  <input id={id} required={required} value={(companyForm as Record<string, string>)[id]}
                    onChange={(e) => setC(id, e.target.value)} placeholder={placeholder}
                    className="vf-input" />
                </div>
              ))}
              {companyError && <p className="text-xs text-red-400 bg-red-500/10 border border-red-500/20 rounded-lg px-3 py-2">{companyError}</p>}
              <div className="flex items-center gap-3">
                <button type="submit" disabled={companySaving} className="vf-btn disabled:opacity-50">
                  {companySaving ? "Saving…" : "Save changes"}
                </button>
                {companyOk && <span className="flex items-center gap-1 text-sm text-emerald-400"><Check className="h-4 w-4" />Saved</span>}
              </div>
            </Card>
          </form>

          {/* Change password */}
          <form onSubmit={handlePassword}>
            <Card>
              <h2 className="font-semibold text-slate-100">Change password</h2>
              {[
                { id: "next",    label: "New password",          placeholder: "Min. 8 characters" },
                { id: "confirm", label: "Confirm new password",  placeholder: "Repeat password"   },
              ].map(({ id, label, placeholder }) => (
                <div key={id} className="space-y-1.5">
                  <Label htmlFor={id} className="text-xs text-slate-400">{label}</Label>
                  <input id={id} type="password" required minLength={8} value={(pwForm as Record<string, string>)[id]}
                    onChange={(e) => setPwForm((s) => ({ ...s, [id]: e.target.value }))} placeholder={placeholder}
                    className="vf-input" />
                </div>
              ))}
              {pwError && <p className="text-xs text-red-400 bg-red-500/10 border border-red-500/20 rounded-lg px-3 py-2">{pwError}</p>}
              <div className="flex items-center gap-3">
                <button type="submit" disabled={pwSaving} className="vf-btn disabled:opacity-50">
                  {pwSaving ? "Updating…" : "Update password"}
                </button>
                {pwOk && <span className="flex items-center gap-1 text-sm text-emerald-400"><Check className="h-4 w-4" />Updated</span>}
              </div>
            </Card>
          </form>
        </>
      )}

      {tab === "team" && (
        <div className="space-y-6">
          <Card className="!p-0 !space-y-0 overflow-hidden">
            <div className="px-6 py-4 border-b border-white/[0.06]">
              <h2 className="font-semibold text-slate-100">Team members</h2>
              <p className="text-xs text-slate-600 mt-0.5">{members.length} member{members.length !== 1 ? "s" : ""}</p>
            </div>
            <div className="divide-y divide-white/[0.04]">
              {members.map((m) => (
                <div key={m.id} className="flex items-center justify-between px-6 py-3">
                  <div>
                    <p className="text-[13px] font-medium text-slate-200">User {m.user_id.slice(0, 8)}…</p>
                    <p className="text-xs text-slate-600">Joined {new Date(m.created_at).toLocaleDateString("sv-SE")}</p>
                  </div>
                  <div className="flex items-center gap-3">
                    {isOwner ? (
                      <select value={m.role}
                        onChange={(e) => handleRoleChange(m.id, e.target.value)}
                        className="rounded-md border border-white/[0.08] bg-vf-elevated px-2 py-1 text-xs text-slate-300 focus:border-indigo-500 focus:outline-none">
                        <option value="OWNER">Owner</option>
                        <option value="ADMIN">Admin</option>
                        <option value="MEMBER">Member</option>
                      </select>
                    ) : (
                      <span className="rounded bg-white/5 px-2 py-0.5 text-xs font-medium text-slate-400 capitalize">{m.role.toLowerCase()}</span>
                    )}
                    {isOwner && (
                      <button onClick={() => handleRemove(m.id)}
                        className="h-7 w-7 flex items-center justify-center rounded-lg text-slate-600 hover:text-red-400 hover:bg-red-500/10 transition-colors">
                        <Trash2 className="h-3.5 w-3.5" />
                      </button>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </Card>

          {isOwner && (
            <form onSubmit={handleInvite}>
              <Card>
                <h2 className="font-semibold text-slate-100 flex items-center gap-2">
                  <UserPlus className="h-4 w-4 text-indigo-400" />Invite team member
                </h2>
                <div className="flex gap-3">
                  <input type="email" required placeholder="colleague@company.se" value={inviteEmail}
                    onChange={(e) => setInviteEmail(e.target.value)}
                    className="vf-input flex-1" />
                  <select value={inviteRole} onChange={(e) => setInviteRole(e.target.value)}
                    className="vf-input w-auto">
                    <option value="MEMBER">Member</option>
                    <option value="ADMIN">Admin</option>
                  </select>
                </div>
                {inviteError && <p className="text-xs text-red-400">{inviteError}</p>}
                <div className="flex items-center gap-3">
                  <button type="submit" disabled={inviting} className="vf-btn disabled:opacity-50">
                    {inviting ? "Inviting…" : "Send invite"}
                  </button>
                  {inviteOk && <span className="flex items-center gap-1 text-sm text-emerald-400"><Check className="h-4 w-4" />Invited</span>}
                </div>
              </Card>
            </form>
          )}
        </div>
      )}

      {tab === "billing" && <BillingTab plan={me?.organization.plan ?? "FREE"} />}
      {tab === "integrations" && <IntegrationsTab />}
      {tab === "notifications" && <NotificationsTab />}
    </div>
  );
}

function BillingTab({ plan }: { plan: string }) {
  const [loading, setLoading] = useState(false);
  const [error, setError]     = useState<string | null>(null);

  async function handleUpgrade() {
    setLoading(true); setError(null);
    try {
      const res = await api.post<{ url: string }>("/api/billing/checkout", {});
      window.location.href = res.url;
    } catch (e: unknown) { setError((e as Error).message ?? "Failed to open checkout"); }
    finally { setLoading(false); }
  }

  async function handlePortal() {
    setLoading(true); setError(null);
    try {
      const res = await api.post<{ url: string }>("/api/billing/portal", {});
      window.location.href = res.url;
    } catch (e: unknown) { setError((e as Error).message ?? "Failed to open portal"); }
    finally { setLoading(false); }
  }

  return (
    <div className="space-y-4">
      <div className="rounded-xl border border-white/[0.06] bg-vf-surface p-6 space-y-4">
        <h2 className="font-semibold text-slate-100 flex items-center gap-2">
          <CreditCard className="h-4 w-4 text-indigo-400" />Subscription
        </h2>
        <div className="flex items-center gap-3">
          <span className={cn(
            "rounded-full px-3 py-1 text-sm font-semibold",
            plan === "PRO" ? "bg-indigo-600 text-white" : "bg-white/5 text-slate-400 border border-white/[0.08]"
          )}>
            {plan === "PRO" ? "PRO" : "Free"}
          </span>
          {plan === "PRO" && <span className="text-sm text-slate-500">All features unlocked</span>}
        </div>

        {plan === "FREE" && (
          <div className="rounded-lg border border-indigo-500/20 bg-indigo-500/5 p-4 space-y-3">
            <p className="text-sm font-medium text-indigo-300">Upgrade to Varuflow PRO</p>
            <ul className="space-y-1 text-sm text-slate-400">
              {["Unlimited invoices", "Team members", "Peppol XML export", "Analytics", "Priority support"].map((f) => (
                <li key={f} className="flex items-center gap-2">
                  <Check className="h-3.5 w-3.5 text-emerald-400 shrink-0" />{f}
                </li>
              ))}
            </ul>
            <button onClick={handleUpgrade} disabled={loading} className="vf-btn disabled:opacity-50">
              {loading ? "Loading…" : "Upgrade now"}
            </button>
          </div>
        )}

        {plan === "PRO" && (
          <button onClick={handlePortal} disabled={loading} className="vf-btn-ghost disabled:opacity-50">
            {loading ? "Loading…" : "Manage subscription"}
          </button>
        )}

        {error && <p className="text-xs text-red-400">{error}</p>}
      </div>
    </div>
  );
}

function IntegrationsTab() {
  const [status, setStatus] = useState<{ connected: boolean; token_expiry?: string } | null>(null);
  const [syncing, setSyncing] = useState<"invoices" | "customers" | null>(null);
  const [loading, setLoading] = useState(true);

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
    } catch (e: unknown) { toast.error((e as Error).message); }
  }

  async function handleSync(type: "invoices" | "customers") {
    setSyncing(type);
    try {
      const res = await api.post<{ synced: number; errors: string[] }>(`/api/integrations/fortnox/sync-${type}`, {});
      toast.success(`Synced ${res.synced} ${type}${res.errors.length ? ` (${res.errors.length} errors)` : ""}`);
    } catch (e: unknown) { toast.error((e as Error).message); }
    finally { setSyncing(null); }
  }

  return (
    <div className="space-y-4">
      <div className="rounded-xl border border-white/[0.06] bg-vf-surface p-6 space-y-5">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-indigo-500/10 border border-indigo-500/20">
              <span className="text-lg font-bold text-indigo-400">F</span>
            </div>
            <div>
              <h2 className="font-semibold text-slate-100">Fortnox</h2>
              <p className="text-xs text-slate-600">Swedish accounting software</p>
            </div>
          </div>
          {loading ? (
            <div className="h-8 w-24 skeleton rounded-lg" />
          ) : status?.connected ? (
            <span className="inline-flex items-center gap-1.5 rounded-full bg-emerald-500/10 border border-emerald-500/20 px-3 py-1 text-xs font-semibold text-emerald-400">
              <span className="h-1.5 w-1.5 rounded-full bg-emerald-400 animate-pulse-dot" />Connected
            </span>
          ) : (
            <span className="inline-flex items-center gap-1.5 rounded-full bg-white/5 border border-white/[0.08] px-3 py-1 text-xs font-medium text-slate-500">
              Not connected
            </span>
          )}
        </div>

        {status?.connected ? (
          <div className="space-y-3">
            <p className="text-sm text-slate-500">
              Sync your data between Varuflow and Fortnox.
              {status.token_expiry && ` Token expires: ${new Date(status.token_expiry).toLocaleDateString("sv-SE")}`}
            </p>
            <div className="flex flex-wrap gap-2">
              <button disabled={syncing === "invoices"} onClick={() => handleSync("invoices")} className="vf-btn-ghost text-xs px-3 py-1.5 h-auto disabled:opacity-50">
                <RefreshCw className={cn("h-3.5 w-3.5", syncing === "invoices" ? "animate-spin" : "")} />
                {syncing === "invoices" ? "Syncing…" : "Push invoices → Fortnox"}
              </button>
              <button disabled={syncing === "customers"} onClick={() => handleSync("customers")} className="vf-btn-ghost text-xs px-3 py-1.5 h-auto disabled:opacity-50">
                <RefreshCw className={cn("h-3.5 w-3.5", syncing === "customers" ? "animate-spin" : "")} />
                {syncing === "customers" ? "Syncing…" : "Pull customers ← Fortnox"}
              </button>
              <button onClick={handleDisconnect} className="ml-auto text-xs px-3 py-1.5 rounded-lg text-red-400 hover:bg-red-500/10 transition-colors flex items-center gap-1.5">
                <Link2Off className="h-3.5 w-3.5" />Disconnect
              </button>
            </div>
          </div>
        ) : (
          <div className="space-y-3">
            <p className="text-sm text-slate-500">
              Connect Fortnox to automatically sync invoices and import customers.
              Requires a Fortnox account with the bookkeeping add-on.
            </p>
            <button onClick={handleConnect} className="vf-btn">
              <Link2 className="h-4 w-4" />Connect Fortnox
            </button>
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
        const reg = await navigator.serviceWorker.getRegistration("/sw.js");
        if (reg) toast.success("Notifications enabled");
      }
    } finally { setRequesting(false); }
  }

  return (
    <div className="space-y-4">
      <div className="rounded-xl border border-white/[0.06] bg-vf-surface p-6 space-y-5">
        <div>
          <h2 className="font-semibold text-slate-100">Push notifications</h2>
          <p className="mt-1 text-sm text-slate-500">
            Get notified about overdue invoices, low stock alerts, and payment confirmations.
          </p>
        </div>

        {permission === "unsupported" && (
          <div className="rounded-lg border border-amber-500/20 bg-amber-500/5 px-4 py-3 text-sm text-amber-300">
            Your browser doesn&apos;t support push notifications.
          </div>
        )}
        {permission === "granted" && (
          <div className="flex items-center gap-3 rounded-lg border border-emerald-500/20 bg-emerald-500/10 px-4 py-3">
            <span className="flex h-8 w-8 items-center justify-center rounded-full bg-emerald-500/15">
              <Check className="h-4 w-4 text-emerald-400" />
            </span>
            <div>
              <p className="text-sm font-semibold text-emerald-300">Notifications enabled</p>
              <p className="text-xs text-emerald-500">You&apos;ll receive alerts for key events.</p>
            </div>
          </div>
        )}
        {permission === "denied" && (
          <div className="rounded-lg border border-red-500/20 bg-red-500/5 px-4 py-3 text-sm text-red-400">
            Notifications are blocked. Click the lock icon in your browser&apos;s address bar to allow them.
          </div>
        )}
        {permission === "default" && (
          <button onClick={handleEnable} disabled={requesting} className="vf-btn disabled:opacity-50">
            {requesting ? "Requesting…" : "Enable notifications"}
          </button>
        )}

        <div className="space-y-3 pt-2 border-t border-white/[0.06]">
          <p className="text-xs font-semibold text-slate-600 uppercase tracking-wide">What you&apos;ll be notified about</p>
          {[
            "Invoice overdue (past due date)",
            "Invoice paid via Stripe payment link",
            "Product stock below minimum threshold",
          ].map((label) => (
            <div key={label} className="flex items-center gap-2 text-sm text-slate-500">
              <span className="h-1.5 w-1.5 rounded-full bg-indigo-500" />
              {label}
            </div>
          ))}
        </div>
      </div>

      <div className="rounded-xl border border-white/[0.06] bg-vf-surface p-6 space-y-3">
        <h2 className="font-semibold text-slate-100">Install app</h2>
        <p className="text-sm text-slate-500">
          Add Varuflow to your home screen for a native-like experience with offline access.
        </p>
        <p className="text-xs text-slate-600">
          On Chrome/Edge: look for the install icon (⊕) in the address bar.<br />
          On iOS Safari: tap Share → Add to Home Screen.
        </p>
      </div>
    </div>
  );
}
