"use client";

import { api } from "@/lib/api-client";
import { Label } from "@/components/ui/label";
import { createClient } from "@/lib/supabase/client";
import { useEffect, useState } from "react";
import { toast } from "sonner";
import { cn } from "@/lib/utils";
import { Check, CreditCard, Link2, Link2Off, RefreshCw, UserPlus, Trash2, Bell, Smartphone } from "lucide-react";

interface Org    { id: string; name: string; org_number: string | null; vat_number: string | null; address: string | null; plan: string; }
interface Me     { email: string; role: string; organization: Org; }
interface Member { id: string; user_id: string; role: string; created_at: string; }

type Tab = "account" | "team" | "billing" | "integrations" | "notifications";

function Card({ children, className, noPad }: { children: React.ReactNode; className?: string; noPad?: boolean }) {
  return (
    <div className={cn("vf-section", noPad ? "" : "p-6 space-y-4", className)}
      style={{ borderRadius: 14 }}>
      {children}
    </div>
  );
}

function FieldRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="space-y-1.5">
      <label className="text-xs font-medium vf-text-m">{label}</label>
      <div className="vf-input opacity-60 pointer-events-none select-none">{value}</div>
    </div>
  );
}

export default function SettingsPage() {
  const [me, setMe]           = useState<Me | null>(null);
  const [members, setMembers] = useState<Member[]>([]);
  const [loading, setLoading] = useState(true);
  const [tab, setTab]         = useState<Tab>("account");
  const supabase = createClient();

  const [companyForm, setCompanyForm]     = useState({ company_name: "", org_number: "", vat_number: "", address: "" });
  const [companySaving, setCompanySaving] = useState(false);
  const [companyOk, setCompanyOk]         = useState(false);
  const [companyError, setCompanyError]   = useState<string | null>(null);

  const [pwForm, setPwForm]   = useState({ next: "", confirm: "" });
  const [pwSaving, setPwSaving] = useState(false);
  const [pwOk, setPwOk]       = useState(false);
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
    Promise.all([api.get<Me>("/api/auth/me"), api.get<Member[]>("/api/team")])
      .then(([meData, teamData]) => {
        setMe(meData);
        setMembers(teamData);
        setCompanyForm({
          company_name: meData.organization.name,
          org_number:   meData.organization.org_number ?? "",
          vat_number:   meData.organization.vat_number ?? "",
          address:      meData.organization.address ?? "",
        });
      }).catch(() => {}).finally(() => setLoading(false));
  }, []);

  function setC(f: string, v: string) { setCompanyForm(s => ({ ...s, [f]: v })); }

  async function handleCompany(e: React.FormEvent) {
    e.preventDefault(); setCompanySaving(true); setCompanyError(null); setCompanyOk(false);
    try {
      await api.put("/api/auth/org", {
        company_name: companyForm.company_name,
        org_number:   companyForm.org_number || null,
        vat_number:   companyForm.vat_number || null,
        address:      companyForm.address || null,
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

  const TABS: { key: Tab; label: string }[] = [
    { key: "account",       label: "Account"       },
    { key: "team",          label: "Team"          },
    { key: "billing",       label: "Billing"       },
    { key: "integrations",  label: "Integrations"  },
    { key: "notifications", label: "Notifications" },
  ];

  return (
    <div className="max-w-2xl space-y-6">

      {/* ── Header ─────────────────────────────────────────────────── */}
      <div>
        <h1 className="text-xl font-bold vf-text-1">Settings</h1>
        <p className="text-xs vf-text-m mt-0.5">Manage your account and organization</p>
      </div>

      {/* ── Tabs ───────────────────────────────────────────────────── */}
      <div className="flex items-center gap-0.5" style={{ borderBottom: "1px solid var(--vf-border)" }}>
        {TABS.map(({ key, label }) => (
          <button key={key} onClick={() => setTab(key)}
            className={cn(
              "px-3 py-2.5 text-[13px] font-medium transition-all border-b-2 -mb-px",
              tab === key
                ? "border-indigo-500 text-indigo-500"
                : "border-transparent vf-text-m hover:vf-text-2"
            )}>
            {label}
          </button>
        ))}
      </div>

      {/* ── Account tab ────────────────────────────────────────────── */}
      {tab === "account" && (
        <>
          {/* Read-only account info */}
          <Card>
            <h2 className="text-[13px] font-semibold vf-text-1">Account</h2>
            <FieldRow label="Email" value={me?.email ?? ""} />
            <div className="grid grid-cols-2 gap-4">
              <FieldRow label="Role"  value={me?.role.toLowerCase() ?? ""} />
              <FieldRow label="Plan"  value={`${me?.organization.plan.toLowerCase() ?? ""}${me?.organization.plan === "FREE" ? " — Early access" : ""}`} />
            </div>
          </Card>

          {/* Company details */}
          <form onSubmit={handleCompany}>
            <Card>
              <h2 className="text-[13px] font-semibold vf-text-1">Company details</h2>
              <p className="text-xs vf-text-m -mt-2">Shown on invoices and purchase orders.</p>
              {[
                { id: "company_name", label: "Company name *", placeholder: "Svensson AB",           required: true  },
                { id: "org_number",   label: "Org number",     placeholder: "556000-0000",            required: false },
                { id: "vat_number",   label: "VAT number",     placeholder: "SE556000000001",         required: false },
                { id: "address",      label: "Address",        placeholder: "Storgatan 1, Stockholm", required: false },
              ].map(({ id, label, placeholder, required }) => (
                <div key={id} className="space-y-1.5">
                  <Label htmlFor={id} className="text-xs font-medium vf-text-2">{label}</Label>
                  <input id={id} required={required}
                    value={(companyForm as Record<string, string>)[id]}
                    onChange={e => setC(id, e.target.value)}
                    placeholder={placeholder}
                    className="vf-input w-full" />
                </div>
              ))}
              {companyError && (
                <p className="text-xs text-red-400 rounded-lg px-3 py-2"
                  style={{ background: "rgba(239,68,68,0.08)", border: "1px solid rgba(239,68,68,0.2)" }}>
                  {companyError}
                </p>
              )}
              <div className="flex items-center gap-3">
                <button type="submit" disabled={companySaving} className="vf-btn disabled:opacity-50">
                  {companySaving ? "Saving…" : "Save changes"}
                </button>
                {companyOk && (
                  <span className="flex items-center gap-1 text-sm text-emerald-400">
                    <Check className="h-4 w-4" />Saved
                  </span>
                )}
              </div>
            </Card>
          </form>

          {/* Change password */}
          <form onSubmit={handlePassword}>
            <Card>
              <h2 className="text-[13px] font-semibold vf-text-1">Change password</h2>
              {[
                { id: "next",    label: "New password",         placeholder: "Min. 8 characters" },
                { id: "confirm", label: "Confirm new password", placeholder: "Repeat password"   },
              ].map(({ id, label, placeholder }) => (
                <div key={id} className="space-y-1.5">
                  <Label htmlFor={id} className="text-xs font-medium vf-text-2">{label}</Label>
                  <input id={id} type="password" required minLength={8}
                    value={(pwForm as Record<string, string>)[id]}
                    onChange={e => setPwForm(s => ({ ...s, [id]: e.target.value }))}
                    placeholder={placeholder}
                    className="vf-input w-full" />
                </div>
              ))}
              {pwError && (
                <p className="text-xs text-red-400 rounded-lg px-3 py-2"
                  style={{ background: "rgba(239,68,68,0.08)", border: "1px solid rgba(239,68,68,0.2)" }}>
                  {pwError}
                </p>
              )}
              <div className="flex items-center gap-3">
                <button type="submit" disabled={pwSaving} className="vf-btn disabled:opacity-50">
                  {pwSaving ? "Updating…" : "Update password"}
                </button>
                {pwOk && (
                  <span className="flex items-center gap-1 text-sm text-emerald-400">
                    <Check className="h-4 w-4" />Updated
                  </span>
                )}
              </div>
            </Card>
          </form>
        </>
      )}

      {/* ── Team tab ───────────────────────────────────────────────── */}
      {tab === "team" && (
        <div className="space-y-6">
          <Card noPad>
            <div className="px-6 py-4" style={{ borderBottom: "1px solid var(--vf-divider)" }}>
              <h2 className="text-[13px] font-semibold vf-text-1">Team members</h2>
              <p className="text-xs vf-text-m mt-0.5">{members.length} member{members.length !== 1 ? "s" : ""}</p>
            </div>
            <div>
              {members.map((m, i) => (
                <div key={m.id}
                  className="flex items-center justify-between px-6 py-3.5"
                  style={{ borderBottom: i < members.length - 1 ? "1px solid var(--vf-divider)" : undefined }}>
                  <div>
                    <p className="text-[13px] font-medium vf-text-1">User {m.user_id.slice(0, 8)}…</p>
                    <p className="text-xs vf-text-m">Joined {new Date(m.created_at).toLocaleDateString("sv-SE")}</p>
                  </div>
                  <div className="flex items-center gap-3">
                    {isOwner ? (
                      <select
                        value={m.role}
                        onChange={e => handleRoleChange(m.id, e.target.value)}
                        className="vf-input text-xs h-8 py-0 w-auto pr-7">
                        <option value="OWNER">Owner</option>
                        <option value="ADMIN">Admin</option>
                        <option value="MEMBER">Member</option>
                      </select>
                    ) : (
                      <span className="rounded-full px-2.5 py-0.5 text-xs font-medium vf-text-m capitalize"
                        style={{ background: "var(--vf-bg-elevated)", border: "1px solid var(--vf-border-strong)" }}>
                        {m.role.toLowerCase()}
                      </span>
                    )}
                    {isOwner && (
                      <button onClick={() => handleRemove(m.id)}
                        className="h-7 w-7 flex items-center justify-center rounded-lg vf-text-m hover:text-red-400 transition-colors"
                        style={{ border: "1px solid var(--vf-border)" }}>
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
                <h2 className="text-[13px] font-semibold vf-text-1 flex items-center gap-2">
                  <UserPlus className="h-4 w-4 text-indigo-400" />Invite team member
                </h2>
                <div className="flex gap-3">
                  <input type="email" required placeholder="colleague@company.se"
                    value={inviteEmail} onChange={e => setInviteEmail(e.target.value)}
                    className="vf-input flex-1" />
                  <select value={inviteRole} onChange={e => setInviteRole(e.target.value)}
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
                  {inviteOk && (
                    <span className="flex items-center gap-1 text-sm text-emerald-400">
                      <Check className="h-4 w-4" />Invited
                    </span>
                  )}
                </div>
              </Card>
            </form>
          )}
        </div>
      )}

      {tab === "billing"       && <BillingTab plan={me?.organization.plan ?? "FREE"} />}
      {tab === "integrations"  && <IntegrationsTab />}
      {tab === "notifications" && <NotificationsTab />}
    </div>
  );
}

/* ── Billing tab ─────────────────────────────────────────────────────────── */
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
      <div className="vf-section p-6 space-y-5" style={{ borderRadius: 14 }}>
        <h2 className="text-[13px] font-semibold vf-text-1 flex items-center gap-2">
          <CreditCard className="h-4 w-4 text-indigo-400" />Subscription
        </h2>

        <div className="flex items-center gap-3">
          <span className={cn(
            "rounded-full px-3 py-1 text-sm font-semibold",
            plan === "PRO"
              ? "bg-indigo-600 text-white"
              : "vf-text-m"
          )}
            style={plan !== "PRO" ? { background: "var(--vf-bg-elevated)", border: "1px solid var(--vf-border-strong)" } : {}}>
            {plan === "PRO" ? "PRO" : "Free"}
          </span>
          {plan === "PRO" && <span className="text-sm vf-text-m">All features unlocked</span>}
        </div>

        {plan === "FREE" && (
          <div className="rounded-xl p-4 space-y-3"
            style={{ background: "rgba(99,102,241,0.06)", border: "1px solid rgba(99,102,241,0.2)" }}>
            <p className="text-sm font-medium text-indigo-400">Upgrade to Varuflow PRO</p>
            <ul className="space-y-1.5">
              {["Unlimited invoices", "Team members", "Peppol XML export", "Analytics", "Priority support"].map(f => (
                <li key={f} className="flex items-center gap-2 text-sm vf-text-2">
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

/* ── Integrations tab ────────────────────────────────────────────────────── */
function IntegrationsTab() {
  const [status, setStatus]   = useState<{ connected: boolean; token_expiry?: string } | null>(null);
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
      <div className="vf-section p-6 space-y-5" style={{ borderRadius: 14 }}>
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl"
              style={{ background: "rgba(99,102,241,0.1)", border: "1px solid rgba(99,102,241,0.2)" }}>
              <span className="text-lg font-bold text-indigo-400">F</span>
            </div>
            <div>
              <h2 className="text-[13px] font-semibold vf-text-1">Fortnox</h2>
              <p className="text-xs vf-text-m">Swedish accounting software</p>
            </div>
          </div>
          {loading ? (
            <div className="h-8 w-24 skeleton rounded-lg" />
          ) : status?.connected ? (
            <span className="inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-xs font-semibold text-emerald-400"
              style={{ background: "rgba(16,185,129,0.1)", border: "1px solid rgba(16,185,129,0.2)" }}>
              <span className="h-1.5 w-1.5 rounded-full bg-emerald-400 animate-pulse-dot" />Connected
            </span>
          ) : (
            <span className="inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-xs font-medium vf-text-m"
              style={{ background: "var(--vf-bg-elevated)", border: "1px solid var(--vf-border-strong)" }}>
              Not connected
            </span>
          )}
        </div>

        {status?.connected ? (
          <div className="space-y-3">
            <p className="text-sm vf-text-2">
              Sync your data between Varuflow and Fortnox.
              {status.token_expiry && ` Token expires: ${new Date(status.token_expiry).toLocaleDateString("sv-SE")}`}
            </p>
            <div className="flex flex-wrap gap-2">
              <button disabled={syncing === "invoices"} onClick={() => handleSync("invoices")}
                className="vf-btn-ghost text-xs disabled:opacity-50">
                <RefreshCw className={cn("h-3.5 w-3.5", syncing === "invoices" ? "animate-spin" : "")} />
                {syncing === "invoices" ? "Syncing…" : "Push invoices → Fortnox"}
              </button>
              <button disabled={syncing === "customers"} onClick={() => handleSync("customers")}
                className="vf-btn-ghost text-xs disabled:opacity-50">
                <RefreshCw className={cn("h-3.5 w-3.5", syncing === "customers" ? "animate-spin" : "")} />
                {syncing === "customers" ? "Syncing…" : "Pull customers ← Fortnox"}
              </button>
              <button onClick={handleDisconnect}
                className="ml-auto inline-flex items-center gap-1.5 rounded-lg px-3 h-9 text-xs text-red-400 hover:bg-red-500/10 transition-colors"
                style={{ border: "1px solid rgba(239,68,68,0.2)" }}>
                <Link2Off className="h-3.5 w-3.5" />Disconnect
              </button>
            </div>
          </div>
        ) : (
          <div className="space-y-3">
            <p className="text-sm vf-text-2">
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

/* ── Notifications tab ───────────────────────────────────────────────────── */
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
      if (result === "granted") toast.success("Notifications enabled");
    } finally { setRequesting(false); }
  }

  return (
    <div className="space-y-4">
      <div className="vf-section p-6 space-y-5" style={{ borderRadius: 14 }}>
        <div className="flex items-center gap-3 mb-1">
          <div className="flex h-9 w-9 items-center justify-center rounded-xl"
            style={{ background: "rgba(99,102,241,0.1)" }}>
            <Bell className="h-4 w-4 text-indigo-400" />
          </div>
          <div>
            <h2 className="text-[13px] font-semibold vf-text-1">Push notifications</h2>
            <p className="text-xs vf-text-m">Overdue invoices, low stock, payment confirmations</p>
          </div>
        </div>

        {permission === "unsupported" && (
          <div className="rounded-xl px-4 py-3 text-sm text-amber-300"
            style={{ background: "rgba(245,158,11,0.08)", border: "1px solid rgba(245,158,11,0.2)" }}>
            Your browser doesn&apos;t support push notifications.
          </div>
        )}
        {permission === "granted" && (
          <div className="flex items-center gap-3 rounded-xl px-4 py-3"
            style={{ background: "rgba(16,185,129,0.08)", border: "1px solid rgba(16,185,129,0.2)" }}>
            <span className="flex h-8 w-8 items-center justify-center rounded-full"
              style={{ background: "rgba(16,185,129,0.15)" }}>
              <Check className="h-4 w-4 text-emerald-400" />
            </span>
            <div>
              <p className="text-sm font-semibold text-emerald-400">Notifications enabled</p>
              <p className="text-xs text-emerald-500/70">You&apos;ll receive alerts for key events.</p>
            </div>
          </div>
        )}
        {permission === "denied" && (
          <div className="rounded-xl px-4 py-3 text-sm text-red-400"
            style={{ background: "rgba(239,68,68,0.08)", border: "1px solid rgba(239,68,68,0.2)" }}>
            Notifications are blocked. Click the lock icon in your browser&apos;s address bar to allow them.
          </div>
        )}
        {permission === "default" && (
          <button onClick={handleEnable} disabled={requesting} className="vf-btn disabled:opacity-50">
            {requesting ? "Requesting…" : "Enable notifications"}
          </button>
        )}

        <div className="space-y-2 pt-2" style={{ borderTop: "1px solid var(--vf-divider)" }}>
          <p className="text-[10px] font-semibold uppercase tracking-widest vf-text-m">What you&apos;ll be notified about</p>
          {[
            "Invoice overdue (past due date)",
            "Invoice paid via Stripe payment link",
            "Product stock below minimum threshold",
          ].map(label => (
            <div key={label} className="flex items-center gap-2 text-sm vf-text-2">
              <span className="h-1.5 w-1.5 rounded-full bg-indigo-500 shrink-0" />
              {label}
            </div>
          ))}
        </div>
      </div>

      <div className="vf-section p-6 space-y-3" style={{ borderRadius: 14 }}>
        <div className="flex items-center gap-3 mb-1">
          <div className="flex h-9 w-9 items-center justify-center rounded-xl"
            style={{ background: "rgba(99,102,241,0.1)" }}>
            <Smartphone className="h-4 w-4 text-indigo-400" />
          </div>
          <h2 className="text-[13px] font-semibold vf-text-1">Install app</h2>
        </div>
        <p className="text-sm vf-text-2">
          Add Varuflow to your home screen for a native-like experience with offline access.
        </p>
        <p className="text-xs vf-text-m">
          On Chrome/Edge: look for the install icon (⊕) in the address bar.<br />
          On iOS Safari: tap Share → Add to Home Screen.
        </p>
      </div>
    </div>
  );
}
