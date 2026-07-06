"use client";

import { useEffect, useState } from "react";
import { useRouter, useParams } from "next/navigation";
import { createClient } from "@/lib/supabase/client";
import { PlusCircle, RefreshCw, ChevronDown, ChevronUp, Send } from "lucide-react";
import { Button } from "@/components/ui/button";
import { toast } from "sonner";
import styles from "./page.module.scss";

interface InvestorUpdate {
  id: string;
  title: string;
  period_month: string;
  status: "draft" | "sent";
  revenue_snapshot: number | null;
  burn_rate: number | null;
  runway_months: number | null;
  key_wins: string | null;
  challenges: string | null;
  next_milestones: string | null;
}

interface Dashboard {
  revenue: number | null;
  burn_rate: number | null;
  runway_months: number | null;
}

const STATUS_COLOR: Record<string, string> = {
  draft: "bg-gray-100 text-gray-600",
  sent: "bg-green-100 text-green-700",
};

const STATUS_MODULE: Record<string, keyof typeof styles> = {
  draft: "statusDraft",
  sent:  "statusSent",
};

function fmtMonth(val: string | null | undefined) {
  if (!val) return "";
  const d = new Date(val + "-01");
  return d.toLocaleDateString("en-US", { month: "long", year: "numeric" });
}

function fmtNum(n: number | null | undefined) {
  if (n == null) return "—";
  return n.toLocaleString();
}

export default function InvestorUpdatesPage() {
  const router = useRouter();
  const params = useParams<{ locale: string }>();
  const locale = params?.locale ?? "en";
  const supabase = createClient();

  const [updates, setUpdates] = useState<InvestorUpdate[]>([]);
  const [dashboard, setDashboard] = useState<Dashboard | null>(null);
  const [loading, setLoading] = useState(true);
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [actionLoading, setActionLoading] = useState<string | null>(null);

  const [showNew, setShowNew] = useState(false);
  const [newForm, setNewForm] = useState({
    title: "", period_month: "", revenue_snapshot: "", burn_rate: "",
    runway_months: "", key_wins: "", challenges: "", next_milestones: "",
  });

  const [sendModal, setSendModal] = useState<{ id: string; emails: string } | null>(null);

  async function getToken() {
    const { data: { session } } = await supabase.auth.getSession();
    return session?.access_token ?? null;
  }
  function apiUrl(p: string) { return `${process.env.NEXT_PUBLIC_API_URL}${p}`; }

  async function load() {
    setLoading(true);
    try {
      const token = await getToken();
      if (!token) { router.push(`/${locale}/auth/login`); return; }
      const [updRes, dashRes] = await Promise.all([
        fetch(apiUrl("/api/investor/updates"), { headers: { Authorization: `Bearer ${token}` } }),
        fetch(apiUrl("/api/investor/updates/dashboard"), { headers: { Authorization: `Bearer ${token}` } }),
      ]);
      if (updRes.status === 401) { router.push(`/${locale}/auth/login`); return; }
      if (updRes.ok) setUpdates(await updRes.json());
      if (dashRes.ok) setDashboard(await dashRes.json());
    } catch {
      toast.error("Failed to load investor updates");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { load(); }, []); // eslint-disable-line react-hooks/exhaustive-deps

  async function createUpdate() {
    if (!newForm.title.trim() || !newForm.period_month) { toast.error("Title and period are required"); return; }
    setActionLoading("create");
    try {
      const token = await getToken();
      if (!token) return;
      const res = await fetch(apiUrl("/api/investor/updates"), {
        method: "POST",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
        body: JSON.stringify({
          title: newForm.title,
          period_month: newForm.period_month,
          revenue_snapshot: newForm.revenue_snapshot ? parseFloat(newForm.revenue_snapshot) : null,
          burn_rate: newForm.burn_rate ? parseFloat(newForm.burn_rate) : null,
          runway_months: newForm.runway_months ? parseInt(newForm.runway_months) : null,
          key_wins: newForm.key_wins || null,
          challenges: newForm.challenges || null,
          next_milestones: newForm.next_milestones || null,
        }),
      });
      if (!res.ok) { const b = await res.json().catch(() => ({})); toast.error(b.detail ?? "Failed to create"); return; }
      toast.success("Update created");
      setShowNew(false);
      setNewForm({ title: "", period_month: "", revenue_snapshot: "", burn_rate: "", runway_months: "", key_wins: "", challenges: "", next_milestones: "" });
      await load();
    } catch { toast.error("Something went wrong"); }
    finally { setActionLoading(null); }
  }

  async function sendUpdate() {
    if (!sendModal) return;
    const emails = sendModal.emails.split("\n").map((e) => e.trim()).filter(Boolean);
    if (!emails.length) { toast.error("Enter at least one email"); return; }
    setActionLoading(sendModal.id + "_send");
    try {
      const token = await getToken();
      if (!token) return;
      const res = await fetch(apiUrl(`/api/investor/updates/${sendModal.id}/send`), {
        method: "POST",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
        body: JSON.stringify({ recipients: emails.map((email) => ({ email, name: "" })) }),
      });
      if (!res.ok) { const b = await res.json().catch(() => ({})); toast.error(b.detail ?? "Failed to send"); return; }
      toast.success("Update sent");
      setSendModal(null);
      await load();
    } catch { toast.error("Something went wrong"); }
    finally { setActionLoading(null); }
  }

  return (
    <div className="mx-auto max-w-4xl space-y-6 p-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-gray-900">Investor Updates</h1>
          <p className="text-sm text-muted-foreground mt-0.5">Monthly investor updates with revenue snapshots.</p>
        </div>
        <Button onClick={() => setShowNew(true)} className="bg-[var(--vf-brand-primary)] hover:bg-[var(--vf-brand-primary-hover)] text-white gap-2">
          <PlusCircle className="h-4 w-4" /> New Update
        </Button>
      </div>

      {/* Dashboard card */}
      {dashboard && (
        <div className="rounded-xl border bg-white shadow-sm p-5 grid grid-cols-3 gap-4">
          {[
            { label: "Latest Revenue", value: fmtNum(dashboard.revenue) },
            { label: "Burn Rate", value: fmtNum(dashboard.burn_rate) },
            { label: "Runway (months)", value: fmtNum(dashboard.runway_months) },
          ].map(({ label, value }) => (
            <div key={label}>
              <p className="text-xs text-muted-foreground">{label}</p>
              <p className="text-lg font-semibold text-gray-900">{value}</p>
            </div>
          ))}
        </div>
      )}

      {/* New update form */}
      {showNew && (
        <div className="rounded-xl border border-[var(--vf-brand-primary)]/20 bg-white p-5 shadow-sm space-y-3">
          <h3 className="text-sm font-semibold text-gray-900">Create Investor Update</h3>
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1">
              <label className="text-xs font-medium text-gray-700">Title *</label>
              <input value={newForm.title} onChange={(e) => setNewForm((f) => ({ ...f, title: e.target.value }))}
                placeholder="Q1 2026 Investor Update"
                className="block w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-[var(--vf-brand-primary)]" />
            </div>
            <div className="space-y-1">
              <label className="text-xs font-medium text-gray-700">Period Month *</label>
              <input type="month" value={newForm.period_month} onChange={(e) => setNewForm((f) => ({ ...f, period_month: e.target.value }))}
                className="block w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-[var(--vf-brand-primary)]" />
            </div>
            <div className="space-y-1">
              <label className="text-xs font-medium text-gray-700">Revenue Snapshot</label>
              <input type="number" value={newForm.revenue_snapshot} onChange={(e) => setNewForm((f) => ({ ...f, revenue_snapshot: e.target.value }))}
                placeholder="0"
                className="block w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-[var(--vf-brand-primary)]" />
            </div>
            <div className="space-y-1">
              <label className="text-xs font-medium text-gray-700">Burn Rate</label>
              <input type="number" value={newForm.burn_rate} onChange={(e) => setNewForm((f) => ({ ...f, burn_rate: e.target.value }))}
                placeholder="0"
                className="block w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-[var(--vf-brand-primary)]" />
            </div>
            <div className="space-y-1">
              <label className="text-xs font-medium text-gray-700">Runway (months)</label>
              <input type="number" value={newForm.runway_months} onChange={(e) => setNewForm((f) => ({ ...f, runway_months: e.target.value }))}
                placeholder="12"
                className="block w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-[var(--vf-brand-primary)]" />
            </div>
          </div>
          {[
            { key: "key_wins" as const, label: "Key Wins" },
            { key: "challenges" as const, label: "Challenges" },
            { key: "next_milestones" as const, label: "Next Milestones" },
          ].map(({ key, label }) => (
            <div key={key} className="space-y-1">
              <label className="text-xs font-medium text-gray-700">{label}</label>
              <textarea rows={2} value={newForm[key]} onChange={(e) => setNewForm((f) => ({ ...f, [key]: e.target.value }))}
                className="block w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-[var(--vf-brand-primary)]" />
            </div>
          ))}
          <div className="flex gap-2">
            <Button variant="outline" onClick={() => setShowNew(false)}>Cancel</Button>
            <Button disabled={actionLoading === "create"} onClick={createUpdate}
              className="bg-[var(--vf-brand-primary)] hover:bg-[var(--vf-brand-primary-hover)] text-white">
              {actionLoading === "create" ? "Creating…" : "Create Update"}
            </Button>
          </div>
        </div>
      )}

      {/* Updates list */}
      {loading && updates.length === 0 ? (
        <div className="text-center py-12"><RefreshCw className="h-6 w-6 animate-spin mx-auto text-muted-foreground" /></div>
      ) : (
        <div className="rounded-xl border bg-white shadow-sm divide-y divide-gray-100">
          {updates.length === 0 ? (
            <div className="py-12 text-center text-gray-500 text-sm">No investor updates yet</div>
          ) : updates.map((u) => {
            const expanded = expandedId === u.id;
            return (
              <div key={u.id}>
                <div className="flex items-center gap-4 px-5 py-4 cursor-pointer hover:bg-gray-50"
                  onClick={() => setExpandedId(expanded ? null : u.id)}>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium text-gray-900">{u.title}</p>
                    <p className="text-xs text-muted-foreground">{fmtMonth(u.period_month)}</p>
                  </div>
                  <div className="flex items-center gap-3">
                    {u.revenue_snapshot != null && (
                      <span className="text-xs text-gray-500">Rev: {fmtNum(u.revenue_snapshot)}</span>
                    )}
                    <span className={styles[STATUS_MODULE[u.status] ?? "statusDraft"]}>
                      {u.status}
                    </span>
                    {u.status === "draft" && (
                      <Button size="sm" onClick={(e) => { e.stopPropagation(); setSendModal({ id: u.id, emails: "" }); }}
                        className="bg-[var(--vf-brand-primary)] hover:bg-[var(--vf-brand-primary-hover)] text-white gap-2">
                        <Send className="h-3 w-3" /> Send
                      </Button>
                    )}
                    {expanded ? <ChevronUp className="h-4 w-4 text-muted-foreground" /> : <ChevronDown className="h-4 w-4 text-muted-foreground" />}
                  </div>
                </div>
                {expanded && (
                  <div className="px-5 pb-4 space-y-3 bg-gray-50">
                    {[
                      { label: "Key Wins", value: u.key_wins },
                      { label: "Challenges", value: u.challenges },
                      { label: "Next Milestones", value: u.next_milestones },
                    ].map(({ label, value }) => value ? (
                      <div key={label}>
                        <p className="text-xs font-semibold text-gray-700 mb-1">{label}</p>
                        <p className="text-sm text-gray-600 whitespace-pre-wrap">{value}</p>
                      </div>
                    ) : null)}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}

      {/* Send modal */}
      {sendModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
          <div className="w-full max-w-md rounded-xl bg-white p-6 shadow-xl space-y-4">
            <h3 className="text-base font-semibold text-gray-900">Send Investor Update</h3>
            <p className="text-sm text-muted-foreground">Enter recipient emails, one per line.</p>
            <textarea rows={5} value={sendModal.emails}
              onChange={(e) => setSendModal((m) => m ? { ...m, emails: e.target.value } : null)}
              placeholder={"investor@example.com\nboard@example.com"}
              className="block w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-[var(--vf-brand-primary)]" />
            <div className="flex gap-2 justify-end">
              <Button variant="outline" onClick={() => setSendModal(null)}>Cancel</Button>
              <Button disabled={actionLoading?.endsWith("_send")} onClick={sendUpdate}
                className="bg-[var(--vf-brand-primary)] hover:bg-[var(--vf-brand-primary-hover)] text-white">
                {actionLoading?.endsWith("_send") ? "Sending…" : "Send"}
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
