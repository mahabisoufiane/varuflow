"use client";

import { api } from "@/lib/api-client";
import { Label } from "@/components/ui/label";
import { createClient, isSupabaseConfigured } from "@/lib/supabase/client";
import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { toast } from "sonner";
import { cn } from "@/lib/utils";
import { cx } from "@/lib/cx";
import styles from "./page.module.scss";
import { Check, CreditCard, Link2, Link2Off, LogOut, RefreshCw, UserPlus, Trash2, Bell, Smartphone, Shield, Settings2, ChevronDown } from "lucide-react";
import { Link } from "@/i18n/navigation";

interface Org    { id: string; name: string; org_number: string | null; vat_number: string | null; address: string | null; plan: string; }
interface Me     { email: string; role: string; organization: Org; allowed_modules: string[]; plan_modules: string[]; }
interface Member { id: string; user_id: string; role: string; created_at: string; }
interface MemberModules { member_id: string; access_mode: string; assigned_modules: string[]; plan_modules: string[]; }

type Tab = "account" | "team" | "billing" | "integrations" | "notifications";

function Card({ children, className, noPad }: { children: React.ReactNode; className?: string; noPad?: boolean }) {
  return (
    <div className={cn("vf-section", noPad ? "" : "p-6 space-y-4", className)}
      >
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
  const params   = useParams<{ locale: string }>();
  const locale   = params?.locale ?? "en";

  const [displayName,   setDisplayName]   = useState("");
  const [nameSaving,    setNameSaving]    = useState(false);
  const [nameOk,        setNameOk]        = useState(false);

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

  // Module assignment UI state
  const [modulePanel, setModulePanel]         = useState<string | null>(null); // member ID
  const [memberModuleData, setMemberModuleData] = useState<Record<string, MemberModules>>({});
  const [moduleEdits, setModuleEdits]         = useState<Record<string, string[]>>({}); // memberId → checked modules
  const [moduleAccessMode, setModuleAccessMode] = useState<Record<string, string>>({}); // memberId → ALL|RESTRICTED
  const [moduleSaving, setModuleSaving]       = useState(false);

  async function fetchMemberModules(memberId: string) {
    try {
      const data = await api.get<MemberModules>(`/api/team/${memberId}/modules`);
      setMemberModuleData(s => ({ ...s, [memberId]: data }));
      setModuleEdits(s => ({ ...s, [memberId]: data.assigned_modules }));
      setModuleAccessMode(s => ({ ...s, [memberId]: data.access_mode }));
    } catch {}
  }

  async function handleSaveModules(memberId: string) {
    setModuleSaving(true);
    try {
      const mode = moduleAccessMode[memberId] ?? "ALL";
      await api.put(`/api/team/${memberId}/modules`, {
        modules: mode === "ALL" ? [] : (moduleEdits[memberId] ?? []),
        access_mode: mode,
      });
      toast.success("Module access saved");
      setModulePanel(null);
    } catch (e: unknown) {
      toast.error((e as Error).message ?? "Failed to save modules");
    } finally {
      setModuleSaving(false);
    }
  }

  function toggleModulePanel(memberId: string) {
    if (modulePanel === memberId) { setModulePanel(null); return; }
    setModulePanel(memberId);
    if (!memberModuleData[memberId]) fetchMemberModules(memberId);
  }

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
    if (isSupabaseConfigured) {
      supabase.auth.getUser().then(({ data }) => {
        setDisplayName(data.user?.user_metadata?.full_name ?? "");
      });
    }
  }, []);

  async function handleName(e: React.FormEvent) {
    e.preventDefault(); setNameSaving(true); setNameOk(false);
    try {
      const { error } = await supabase.auth.updateUser({ data: { full_name: displayName } });
      if (error) throw error;
      setNameOk(true);
      setTimeout(() => setNameOk(false), 3000);
      toast.success("Name updated");
    } catch (e: unknown) { toast.error((e as Error).message ?? "Failed to save"); }
    finally { setNameSaving(false); }
  }

  async function handleSettingsSignOut() {
    try {
      if (isSupabaseConfigured) await supabase.auth.signOut();
    } catch {}
    window.location.href = `/${locale}/auth/login`;
  }

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
    if (pwForm.next.length < 10) { setPwError("Minimum 10 characters"); return; }
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
      <div className={styles.tabs}>
        {TABS.map(({ key, label }) => (
          <button key={key} onClick={() => setTab(key)}
            className={cx(styles.tab, tab === key && styles.tabActive)}>
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
              <FieldRow label="Plan"  value={me?.organization.plan === "ENTERPRISE" ? "Enterprise" : me?.organization.plan === "PRO" ? "Professional" : "Free"} />
            </div>
          </Card>

          {/* Security & 2FA — links out to the dedicated MFA management page.
              Kept as a deep-link rather than an inline tab because the setup
              flow renders a QR code and needs more vertical space than the
              other tabs. See frontend/src/app/[locale]/(app)/settings/security. */}
          <Link href={`/${locale}/settings/security`} className="block">
            <Card className="hover:opacity-90 transition-opacity cursor-pointer">
              <div className="flex items-center gap-3">
                <Shield className="h-5 w-5 vf-text-m" />
                <div className="flex-1">
                  <h2 className="text-[13px] font-semibold vf-text-1">Security & two-factor auth</h2>
                  <p className="text-xs vf-text-m mt-0.5">Enable TOTP to protect billing and team actions.</p>
                </div>
                <span className="text-xs vf-text-m">→</span>
              </div>
            </Card>
          </Link>

          {/* Personal info */}
          <form onSubmit={handleName}>
            <Card>
              <h2 className="text-[13px] font-semibold vf-text-1">Personal info</h2>
              <div className="space-y-1.5">
                <Label htmlFor="display_name" className="text-xs font-medium vf-text-2">Display name</Label>
                <input id="display_name" value={displayName}
                  onChange={e => setDisplayName(e.target.value)}
                  placeholder="Your name"
                  className="vf-input w-full" />
              </div>
              <div className="flex items-center gap-3">
                <button type="submit" disabled={nameSaving} className="vf-btn disabled:opacity-50">
                  {nameSaving ? "Saving…" : "Save name"}
                </button>
                {nameOk && (
                  <span className="flex items-center gap-1 text-sm text-emerald-400">
                    <Check className="h-4 w-4" />Saved
                  </span>
                )}
              </div>
            </Card>
          </form>

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
                <p className={cx("text-xs text-red-400 rounded-lg px-3 py-2", styles.errorMsg)}>
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
                { id: "next",    label: "New password",         placeholder: "Min. 10 characters" },
                { id: "confirm", label: "Confirm new password", placeholder: "Repeat password"   },
              ].map(({ id, label, placeholder }) => (
                <div key={id} className="space-y-1.5">
                  <Label htmlFor={id} className="text-xs font-medium vf-text-2">{label}</Label>
                  <input id={id} type="password" required minLength={10}
                    value={(pwForm as Record<string, string>)[id]}
                    onChange={e => setPwForm(s => ({ ...s, [id]: e.target.value }))}
                    placeholder={placeholder}
                    className="vf-input w-full" />
                </div>
              ))}
              {pwError && (
                <p className={cx("text-xs text-red-400 rounded-lg px-3 py-2", styles.errorMsg)}>
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

          {/* Data & privacy — owner-only link to GDPR page */}
          {isOwner && (
            <Card>
              <h2 className="text-[13px] font-semibold vf-text-1">Data & privacy</h2>
              <p className="text-xs vf-text-m -mt-2">
                Export every record for your organization, or permanently delete it.
              </p>
              <div className="flex flex-wrap gap-2">
                <a
                  href={`/${locale}/settings/gdpr`}
                  className="vf-btn vf-btn-ghost inline-flex w-fit items-center gap-2"
                >
                  Manage data & privacy →
                </a>
                <a
                  href={`/${locale}/settings/audit`}
                  className="vf-btn vf-btn-ghost inline-flex w-fit items-center gap-2"
                >
                  View audit log →
                </a>
              </div>
            </Card>
          )}

          {/* Sign out */}
          <Card>
            <h2 className="text-[13px] font-semibold vf-text-1">Sign out</h2>
            <p className="text-xs vf-text-m -mt-2">Sign out of your Varuflow account on this device.</p>
            <button
              onClick={handleSettingsSignOut}
              className="vf-btn-ghost inline-flex w-fit items-center gap-2 text-red-400 hover:text-red-300"
            >
              <LogOut className="h-4 w-4" />Sign out
            </button>
          </Card>
        </>
      )}

      {/* ── Team tab ───────────────────────────────────────────────── */}
      {tab === "team" && (
        <div className="space-y-6">
          <Card noPad>
            <div className={cx("px-6 py-4", styles.dividerBottom)}>
              <h2 className="text-[13px] font-semibold vf-text-1">Team members</h2>
              <p className="text-xs vf-text-m mt-0.5">{members.length} member{members.length !== 1 ? "s" : ""}</p>
            </div>
            <div>
              {members.map((m, i) => {
                const isPanelOpen = modulePanel === m.id;
                const mdata = memberModuleData[m.id];
                const mode  = moduleAccessMode[m.id] ?? "ALL";
                const planMods = mdata?.plan_modules ?? [];
                const checked  = moduleEdits[m.id] ?? [];

                return (
                  <div key={m.id}>
                    <div
                      className="flex items-center justify-between px-6 py-3.5"
                      style={{ borderBottom: (i < members.length - 1 || isPanelOpen) ? "1px solid var(--vf-divider)" : undefined }}>
                      <div>
                        <p className="text-[13px] font-medium vf-text-1">User {m.user_id.slice(0, 8)}…</p>
                        <p className="text-xs vf-text-m">Joined {new Date(m.created_at).toLocaleDateString("sv-SE")}</p>
                      </div>
                      <div className="flex items-center gap-2">
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
                          <span className={cx("rounded-full px-2.5 py-0.5 text-xs font-medium vf-text-m capitalize", styles.roleBadge)}>
                            {m.role.toLowerCase()}
                          </span>
                        )}
                        {/* Module assignment button — only for MEMBERs, only for owners/admins */}
                        {isOwner && m.role === "MEMBER" && (
                          <button
                            onClick={() => toggleModulePanel(m.id)}
                            className={cx(cn(
                              "h-7 flex items-center gap-1 px-2 rounded-lg text-[11px] font-medium transition-colors",
                              isPanelOpen
                                ? "bg-indigo-500/15 text-indigo-400"
                                : "vf-text-m hover:vf-text-2",
                            ), styles.iconBtn)}
                            title="Assign modules">
                            <Settings2 className="h-3.5 w-3.5" />
                            <span className="hidden sm:inline">Modules</span>
                            <ChevronDown className={cn("h-3 w-3 transition-transform", isPanelOpen && "rotate-180")} />
                          </button>
                        )}
                        {isOwner && (
                          <button onClick={() => handleRemove(m.id)}
                            className={cx("h-7 w-7 flex items-center justify-center rounded-lg vf-text-m hover:text-red-400 transition-colors", styles.iconBtn)}>
                            <Trash2 className="h-3.5 w-3.5" />
                          </button>
                        )}
                      </div>
                    </div>

                    {/* Module assignment panel */}
                    {isPanelOpen && (
                      <div className="px-6 py-4 space-y-3"
                        style={{ background: "var(--vf-bg-elevated)", borderBottom: i < members.length - 1 ? "1px solid var(--vf-divider)" : undefined }}>
                        <div className="flex items-center gap-3">
                          <span className="text-[12px] font-medium vf-text-2">Access mode</span>
                          <div className={cx("flex rounded-lg overflow-hidden", styles.modeToggle)}>
                            {(["ALL", "RESTRICTED"] as const).map((opt) => (
                              <button key={opt}
                                onClick={() => setModuleAccessMode(s => ({ ...s, [m.id]: opt }))}
                                className={cn(
                                  "px-3 py-1.5 text-[11px] font-semibold transition-colors",
                                  mode === opt ? "bg-indigo-500 text-white" : "vf-text-m hover:vf-text-2"
                                )}>
                                {opt === "ALL" ? "Full access" : "Restricted"}
                              </button>
                            ))}
                          </div>
                        </div>

                        {mode === "RESTRICTED" && (
                          <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
                            {planMods.length === 0 && !mdata && (
                              <p className="text-xs vf-text-m col-span-3">Loading…</p>
                            )}
                            {planMods.map((mod) => (
                              <label key={mod} className={cx(cn(
                                "flex items-center gap-2 rounded-lg px-3 py-2 cursor-pointer select-none text-[12px] transition-colors",
                                checked.includes(mod) ? "bg-indigo-500/10 text-indigo-400" : "vf-text-2 hover:bg-[var(--vf-hover)]"
                              ), styles.iconBtn)}>
                                <input type="checkbox"
                                  checked={checked.includes(mod)}
                                  onChange={() => setModuleEdits(s => ({
                                    ...s,
                                    [m.id]: checked.includes(mod)
                                      ? checked.filter(x => x !== mod)
                                      : [...checked, mod],
                                  }))}
                                  className="accent-indigo-500" />
                                <span className="capitalize">{mod}</span>
                              </label>
                            ))}
                          </div>
                        )}

                        <div className="flex items-center gap-3 pt-1">
                          <button
                            onClick={() => handleSaveModules(m.id)}
                            disabled={moduleSaving}
                            className="vf-btn text-xs h-8 disabled:opacity-50">
                            {moduleSaving ? "Saving…" : "Save"}
                          </button>
                          <button
                            onClick={() => setModulePanel(null)}
                            className="text-xs vf-text-m hover:vf-text-2 transition-colors">
                            Cancel
                          </button>
                        </div>
                      </div>
                    )}
                  </div>
                );
              })}
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
      <div className="vf-section p-6 space-y-5" >
        <h2 className="text-[13px] font-semibold vf-text-1 flex items-center gap-2">
          <CreditCard className="h-4 w-4 text-indigo-400" />Subscription
        </h2>

        <div className="flex items-center gap-3">
          <span className={cn(
            "rounded-full px-3 py-1 text-sm font-semibold",
            plan === "ENTERPRISE"
              ? "text-white"
              : plan === "PRO"
              ? "bg-indigo-600 text-white"
              : "vf-text-m"
          )}
            style={
              plan === "ENTERPRISE"
                ? { background: "linear-gradient(135deg, #F59E0B, #D97706)" }
                : plan !== "PRO"
                ? { background: "var(--vf-bg-elevated)", border: "1px solid var(--vf-border-strong)" }
                : {}
            }>
            {plan === "ENTERPRISE" ? "Enterprise" : plan === "PRO" ? "Professional" : "Starter — 14-day trial"}
          </span>
          {(plan === "PRO" || plan === "ENTERPRISE") && (
            <span className="text-sm vf-text-m">All features unlocked</span>
          )}
        </div>

        {plan === "FREE" && (
          <div className={cx("rounded-xl p-4 space-y-3", styles.brandCard)}>
            <p className="text-sm font-medium text-indigo-400">Your 14-day trial has ended</p>
            <p className="text-xs vf-text-2">Upgrade to continue using all features.</p>
            <ul className="space-y-1.5">
              {["Unlimited invoices & customers", "Up to 10,000 products", "Fortnox integration", "Advanced analytics", "Priority support"].map(f => (
                <li key={f} className="flex items-center gap-2 text-sm vf-text-2">
                  <Check className="h-3.5 w-3.5 text-emerald-400 shrink-0" />{f}
                </li>
              ))}
            </ul>
            <button onClick={handleUpgrade} disabled={loading} className="vf-btn disabled:opacity-50">
              {loading ? "Loading…" : "Upgrade to Starter — 499 kr/mo"}
            </button>
          </div>
        )}

        {(plan === "PRO" || plan === "ENTERPRISE") && (
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
    window.location.href = `${process.env.NEXT_PUBLIC_API_URL ?? ""}/api/integrations/fortnox/connect`;
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
      <div className="vf-section p-6 space-y-5" >
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className={cx("flex h-10 w-10 items-center justify-center rounded-xl", styles.brandCard)}>
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
            <span className={cx("inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-xs font-semibold text-emerald-400", styles.statusConnected)}>
              <span className="h-1.5 w-1.5 rounded-full bg-emerald-400 animate-pulse-dot" />Connected
            </span>
          ) : (
            <span className={cx("inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-xs font-medium vf-text-m", styles.roleBadge)}>
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
                className={cx("ml-auto inline-flex items-center gap-1.5 rounded-lg px-3 h-9 text-xs text-red-400 hover:bg-red-500/10 transition-colors", styles.disconnectBtn)}>
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
interface PushPrefs {
  push_stockout_enabled: boolean;
  push_overdue_enabled: boolean;
  push_portal_order_enabled: boolean;
}

function NotificationsTab() {
  const [permission, setPermission] = useState<NotificationPermission | "unsupported">(
    typeof Notification === "undefined" ? "unsupported" : Notification.permission
  );
  const [requesting, setRequesting] = useState(false);
  const [prefs, setPrefs] = useState<PushPrefs | null>(null);
  const [savingKey, setSavingKey] = useState<keyof PushPrefs | null>(null);

  useEffect(() => {
    api.get<PushPrefs>("/api/notifications/preferences")
      .then(setPrefs)
      .catch(() => {/* signed-out or offline — leave null, render skeleton */});
  }, []);

  async function togglePref(key: keyof PushPrefs) {
    if (!prefs) return;
    const next = { ...prefs, [key]: !prefs[key] };
    // Optimistic: flip immediately so the UI feels snappy; revert on error.
    setPrefs(next);
    setSavingKey(key);
    try {
      const result = await api.put<PushPrefs>("/api/notifications/preferences", {
        [key]: next[key],
      });
      setPrefs(result);
    } catch {
      setPrefs(prefs);
      toast.error("Failed to update preference");
    } finally {
      setSavingKey(null);
    }
  }

  async function handleEnable() {
    if (typeof Notification === "undefined") return;
    setRequesting(true);
    try {
      const result = await Notification.requestPermission();
      setPermission(result);
      if (result === "granted") toast.success("Notifications enabled");
    } finally { setRequesting(false); }
  }

  const prefRows: { key: keyof PushPrefs; title: string; hint: string }[] = [
    { key: "push_overdue_enabled",      title: "Overdue invoices",     hint: "Push 1 day after an invoice's due date." },
    { key: "push_stockout_enabled",     title: "Stock running out",    hint: "Push when a product will run out within 7 days." },
    { key: "push_portal_order_enabled", title: "New portal orders",    hint: "Push when a B2B customer places an order." },
  ];

  return (
    <div className="space-y-4">
      <div className="vf-section p-6 space-y-5" >
        <div className="flex items-center gap-3 mb-1">
          <div className={cx("flex h-9 w-9 items-center justify-center rounded-xl", styles.brandIcon)}>
            <Bell className="h-4 w-4 text-indigo-400" />
          </div>
          <div>
            <h2 className="text-[13px] font-semibold vf-text-1">Push notifications</h2>
            <p className="text-xs vf-text-m">Overdue invoices, low stock, payment confirmations</p>
          </div>
        </div>

        {permission === "unsupported" && (
          <div className={cx("rounded-xl px-4 py-3 text-sm text-amber-300", styles.warningBanner)}>
            Your browser doesn&apos;t support push notifications.
          </div>
        )}
        {permission === "granted" && (
          <div className={cx("flex items-center gap-3 rounded-xl px-4 py-3", styles.successBanner)}>
            <span className={cx("flex h-8 w-8 items-center justify-center rounded-full", styles.successIcon)}>
              <Check className="h-4 w-4 text-emerald-400" />
            </span>
            <div>
              <p className="text-sm font-semibold text-emerald-400">Notifications enabled</p>
              <p className="text-xs text-emerald-500/70">You&apos;ll receive alerts for key events.</p>
            </div>
          </div>
        )}
        {permission === "denied" && (
          <div className={cx("rounded-xl px-4 py-3 text-sm text-red-400", styles.errorMsg)}>
            Notifications are blocked. Click the lock icon in your browser&apos;s address bar to allow them.
          </div>
        )}
        {permission === "default" && (
          <button onClick={handleEnable} disabled={requesting} className="vf-btn disabled:opacity-50">
            {requesting ? "Requesting…" : "Enable notifications"}
          </button>
        )}

        <div className={cx("space-y-3 pt-2", styles.divider)}>
          <p className="text-[10px] font-semibold uppercase tracking-widest vf-text-m">
            Which events should trigger a push?
          </p>
          {prefs === null ? (
            <p className="text-xs vf-text-m">Loading…</p>
          ) : (
            prefRows.map(({ key, title, hint }) => (
              <label
                key={key}
                className="flex items-start justify-between gap-4 cursor-pointer select-none"
              >
                <span className="flex-1">
                  <span className="text-sm vf-text-1 block">{title}</span>
                  <span className="text-xs vf-text-m">{hint}</span>
                </span>
                <button
                  type="button"
                  role="switch"
                  aria-checked={prefs[key]}
                  onClick={() => togglePref(key)}
                  disabled={savingKey === key}
                  className={cn(
                    "relative inline-flex h-5 w-9 shrink-0 items-center rounded-full transition-colors",
                    prefs[key] ? "bg-indigo-500" : "bg-white/10",
                    savingKey === key && "opacity-60",
                  )}
                >
                  <span
                    className={cn(
                      "inline-block h-4 w-4 transform rounded-full bg-white transition-transform",
                      prefs[key] ? "translate-x-4" : "translate-x-0.5",
                    )}
                  />
                </button>
              </label>
            ))
          )}
        </div>
      </div>

      <NightlySummaryCard />

      <div className="vf-section p-6 space-y-3" >
        <div className="flex items-center gap-3 mb-1">
          <div className={cx("flex h-9 w-9 items-center justify-center rounded-xl", styles.brandIcon)}>
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

/* ── Nightly summary (Item 21) ───────────────────────────────────────────── */
interface NightlySummarySettings {
  enabled: boolean;
  time: string; // "HH:MM", snapped server-side to a 15-min grid
}

function NightlySummaryCard() {
  const [state, setState] = useState<NightlySummarySettings | null>(null);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    api.get<NightlySummarySettings>("/api/notifications/nightly-summary")
      .then(setState)
      .catch(() => {/* non-owner or offline — render nothing gracefully */});
  }, []);

  async function save(patch: Partial<NightlySummarySettings>) {
    if (!state) return;
    const prev = state;
    const next = { ...state, ...patch };
    // Optimistic flip so the toggle feels instant.
    setState(next);
    setSaving(true);
    try {
      const saved = await api.put<NightlySummarySettings>(
        "/api/notifications/nightly-summary",
        patch,
      );
      setState(saved);
    } catch (e) {
      setState(prev);
      toast.error((e as Error).message || "Could not save nightly summary settings");
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="vf-section p-6 space-y-4" >
      <div className="flex items-center gap-3 mb-1">
        <div className={cx("flex h-9 w-9 items-center justify-center rounded-xl", styles.brandIcon)}>
          <Bell className="h-4 w-4 text-indigo-400" />
        </div>
        <div>
          <h2 className="text-[13px] font-semibold vf-text-1">Nightly business summary</h2>
          <p className="text-xs vf-text-m">
            Daily email with revenue, orders, low stock, overdue invoices, and an AI insight.
          </p>
        </div>
      </div>

      {state === null ? (
        <p className="text-xs vf-text-m">Loading…</p>
      ) : (
        <>
          <label className="flex items-start justify-between gap-4 cursor-pointer select-none">
            <span className="flex-1">
              <span className="text-sm vf-text-1 block">Send nightly summary</span>
              <span className="text-xs vf-text-m">Delivered to the org owner&apos;s email.</span>
            </span>
            <button
              type="button"
              role="switch"
              aria-checked={state.enabled}
              onClick={() => save({ enabled: !state.enabled })}
              disabled={saving}
              className={cn(
                "relative inline-flex h-5 w-9 shrink-0 items-center rounded-full transition-colors",
                state.enabled ? "bg-indigo-500" : "bg-white/10",
                saving && "opacity-60",
              )}
            >
              <span
                className={cn(
                  "inline-block h-4 w-4 transform rounded-full bg-white transition-transform",
                  state.enabled ? "translate-x-4" : "translate-x-0.5",
                )}
              />
            </button>
          </label>

          <div className={cx("flex items-center gap-3 pt-3", styles.divider)}>
            <Label htmlFor="nightly-summary-time" className="text-sm vf-text-1 flex-1">
              Send at (Europe/Stockholm)
            </Label>
            <input
              id="nightly-summary-time"
              type="time"
              step={900 /* 15 min */}
              value={state.time}
              onChange={(e) => setState({ ...state, time: e.target.value })}
              onBlur={() => state && save({ time: state.time })}
              disabled={saving || !state.enabled}
              className="vf-input w-32"
            />
          </div>
          <p className="text-[11px] vf-text-m">
            Times are snapped to the nearest 15 minutes to match the delivery window.
          </p>
        </>
      )}
    </div>
  );
}
