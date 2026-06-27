"use client";

/**
 * Approval Queue & Rules
 *
 * Wires:
 *   GET    /api/governance/rules
 *   POST   /api/governance/rules
 *   PATCH  /api/governance/rules/{id}
 *   DELETE /api/governance/rules/{id}
 *   GET    /api/governance/approvals?status=...
 *   GET    /api/governance/approvals/summary
 *   POST   /api/governance/approvals/{id}/approve
 *   POST   /api/governance/approvals/{id}/reject
 *   POST   /api/governance/approvals/{id}/escalate
 *   POST   /api/governance/approvals/escalate-overdue
 *   GET    /api/governance/delegates
 *   POST   /api/governance/delegates
 *   DELETE /api/governance/delegates/{id}
 */
import { useCallback, useEffect, useState } from "react";
import {
  ClipboardCheck, Plus, Check, X, Settings, AlertTriangle,
  ShieldAlert, Users2, RefreshCw, Loader2, TrendingUp, Trash2,
} from "lucide-react";
import { toast } from "sonner";
import { api } from "@/lib/api-client";

// ─── Types ───────────────────────────────────────────────────────────────────

interface ApprovalRule {
  id: string; resource_type: string; threshold_amount: number; currency: string;
  required_approver_role: string; description: string | null; is_active: boolean;
  escalation_days: number | null; notify_email: string | null;
}
interface ApprovalRequest {
  id: string; resource_type: string; resource_id: string; resource_label: string | null;
  amount: number | null; currency: string; status: string;
  requested_by: string; requested_by_email: string | null;
  requested_at: string; reviewed_at: string | null; reviewer_note: string | null;
  rule_id: string | null; escalated_at: string | null; escalated_to_role: string | null;
}
interface Summary {
  pending: number; approved: number; rejected: number; escalated: number; pending_amount: number;
}
interface Delegate {
  id: string; delegated_from_role: string; delegated_to_user_id: string;
  delegated_to_email: string | null; valid_from: string; valid_until: string; note: string | null;
}

// ─── Helpers ─────────────────────────────────────────────────────────────────

const fmt  = (v: number) => v.toLocaleString("sv-SE", { maximumFractionDigits: 0 });
const fmtD = (iso: string) => new Date(iso).toLocaleDateString("sv-SE");

function daysPending(iso: string): number {
  return Math.floor((Date.now() - new Date(iso).getTime()) / 86_400_000);
}

const RESOURCE_LABELS: Record<string, string> = {
  invoice:        "Invoice",
  expense:        "Expense",
  purchase_order: "Purchase Order",
  quote:          "Quote",
};

const STATUS_STYLE: Record<string, string> = {
  pending:  "bg-amber-500/15 text-amber-300 border border-amber-500/30",
  approved: "bg-emerald-500/15 text-emerald-300 border border-emerald-500/30",
  rejected: "bg-rose-500/15 text-rose-300 border border-rose-500/30",
};

// ─── Review Panel (inline) ────────────────────────────────────────────────────

function ReviewPanel({
  req, onDone,
}: { req: ApprovalRequest; onDone: () => void }) {
  const [note, setNote]     = useState("");
  const [saving, setSaving] = useState<"approve" | "reject" | null>(null);

  const act = async (action: "approve" | "reject") => {
    setSaving(action);
    try {
      await api.post(`/api/governance/approvals/${req.id}/${action}`, { reviewer_note: note || undefined });
      toast.success(action === "approve" ? "Approved" : "Rejected");
      onDone();
    } catch (e: unknown) {
      toast.error(e instanceof Error ? e.message : "Failed");
    } finally { setSaving(null); }
  };

  return (
    <div className="mt-3 pt-3 border-t border-white/10 space-y-2">
      <textarea
        className="vf-input text-xs w-full h-14 resize-none"
        placeholder="Add a note (optional)…"
        value={note}
        onChange={e => setNote(e.target.value)}
      />
      <div className="flex gap-2">
        <button
          onClick={() => act("approve")} disabled={!!saving}
          className="vf-btn text-xs px-3 py-1.5 flex items-center gap-1.5 bg-emerald-500/20 text-emerald-300 hover:bg-emerald-500/30"
        >
          {saving === "approve" ? <Loader2 className="w-3 h-3 animate-spin" /> : <Check className="w-3 h-3" />}
          Approve
        </button>
        <button
          onClick={() => act("reject")} disabled={!!saving}
          className="vf-btn text-xs px-3 py-1.5 flex items-center gap-1.5 bg-rose-500/20 text-rose-300 hover:bg-rose-500/30"
        >
          {saving === "reject" ? <Loader2 className="w-3 h-3 animate-spin" /> : <X className="w-3 h-3" />}
          Reject
        </button>
      </div>
    </div>
  );
}

// ─── Main Page ────────────────────────────────────────────────────────────────

type Tab = "queue" | "rules" | "delegates";

export default function ApprovalsPage() {
  const [tab,             setTab]             = useState<Tab>("queue");
  const [rules,           setRules]           = useState<ApprovalRule[]>([]);
  const [requests,        setRequests]        = useState<ApprovalRequest[]>([]);
  const [delegates,       setDelegates]       = useState<Delegate[]>([]);
  const [summary,         setSummary]         = useState<Summary | null>(null);
  const [loading,         setLoading]         = useState(true);
  const [filterStatus,    setFilterStatus]    = useState("pending");
  const [reviewingId,     setReviewingId]     = useState<string | null>(null);
  const [showRuleForm,    setShowRuleForm]     = useState(false);
  const [showDelegForm,   setShowDelegForm]   = useState(false);
  const [escalatingAll,   setEscalatingAll]   = useState(false);

  const [ruleForm, setRuleForm] = useState({
    resource_type: "expense", threshold_amount: 5000, currency: "SEK",
    required_approver_role: "OWNER", description: "",
    escalation_days: "", notify_email: "",
  });

  const [delegForm, setDelegForm] = useState({
    delegated_from_role: "OWNER", delegated_to_user_id: "",
    delegated_to_email: "", valid_from: "", valid_until: "", note: "",
  });

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [ruleData, reqData, sumData, dlgData] = await Promise.all([
        api.get<ApprovalRule[]>("/api/governance/rules"),
        api.get<ApprovalRequest[]>(`/api/governance/approvals?status=${filterStatus}`),
        api.get<Summary>("/api/governance/approvals/summary"),
        api.get<Delegate[]>("/api/governance/delegates"),
      ]);
      setRules(ruleData);
      setRequests(reqData);
      setSummary(sumData);
      setDelegates(dlgData);
    } catch (e: unknown) {
      toast.error(e instanceof Error ? e.message : "Failed to load");
    } finally { setLoading(false); }
  }, [filterStatus]);

  useEffect(() => { load(); }, [load]);

  const createRule = async () => {
    if (!ruleForm.threshold_amount) { toast.error("Threshold required"); return; }
    try {
      await api.post("/api/governance/rules", {
        ...ruleForm,
        threshold_amount: Number(ruleForm.threshold_amount),
        escalation_days: ruleForm.escalation_days ? Number(ruleForm.escalation_days) : undefined,
        notify_email: ruleForm.notify_email || undefined,
        description: ruleForm.description || undefined,
      });
      toast.success("Rule created");
      setShowRuleForm(false);
      await load();
    } catch (e: unknown) { toast.error(e instanceof Error ? e.message : "Failed"); }
  };

  const toggleRule = async (rule: ApprovalRule) => {
    try {
      await api.patch(`/api/governance/rules/${rule.id}`, { is_active: !rule.is_active });
      setRules(prev => prev.map(r => r.id === rule.id ? { ...r, is_active: !r.is_active } : r));
    } catch (e: unknown) { toast.error(e instanceof Error ? e.message : "Failed"); }
  };

  const deleteRule = async (id: string) => {
    try {
      await api.delete(`/api/governance/rules/${id}`);
      setRules(prev => prev.filter(r => r.id !== id));
      toast.success("Rule deleted");
    } catch (e: unknown) { toast.error(e instanceof Error ? e.message : "Failed"); }
  };

  const escalateAll = async () => {
    setEscalatingAll(true);
    try {
      const res = await api.post<{ escalated: number }>("/api/governance/approvals/escalate-overdue", {});
      toast.success(`${res.escalated} request(s) escalated`);
      await load();
    } catch (e: unknown) { toast.error(e instanceof Error ? e.message : "Failed"); }
    finally { setEscalatingAll(false); }
  };

  const escalateOne = async (id: string) => {
    try {
      await api.post(`/api/governance/approvals/${id}/escalate`, {});
      toast.success("Escalated");
      await load();
    } catch (e: unknown) { toast.error(e instanceof Error ? e.message : "Failed"); }
  };

  const createDelegate = async () => {
    if (!delegForm.delegated_to_user_id || !delegForm.valid_from || !delegForm.valid_until) {
      toast.error("User ID, start and end dates are required"); return;
    }
    try {
      await api.post("/api/governance/delegates", {
        ...delegForm,
        delegated_to_email: delegForm.delegated_to_email || undefined,
        note: delegForm.note || undefined,
      });
      toast.success("Delegate added");
      setShowDelegForm(false);
      await load();
    } catch (e: unknown) { toast.error(e instanceof Error ? e.message : "Failed"); }
  };

  const deleteDelegate = async (id: string) => {
    try {
      await api.delete(`/api/governance/delegates/${id}`);
      setDelegates(prev => prev.filter(d => d.id !== id));
      toast.success("Delegate removed");
    } catch (e: unknown) { toast.error(e instanceof Error ? e.message : "Failed"); }
  };

  return (
    <div className="max-w-5xl mx-auto px-4 py-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <ClipboardCheck className="w-6 h-6 text-indigo-400" />
          <div>
            <h1 className="text-xl font-bold vf-text-1">Approval Chain</h1>
            <p className="text-xs vf-text-m mt-0.5">Spending controls, review queue, and delegation</p>
          </div>
        </div>
        <button onClick={load} className="vf-btn-ghost text-xs px-3 py-1.5">
          <RefreshCw className="w-3.5 h-3.5 mr-1.5 inline" />Refresh
        </button>
      </div>

      {/* Summary cards */}
      {summary && (
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          <div className="vf-section p-4">
            <p className="text-xs vf-text-m">Pending</p>
            <p className="text-2xl font-bold text-amber-400 mt-1">{summary.pending}</p>
            <p className="text-xs vf-text-m">{fmt(summary.pending_amount)} total value</p>
          </div>
          <div className="vf-section p-4">
            <p className="text-xs vf-text-m">Approved</p>
            <p className="text-2xl font-bold text-emerald-400 mt-1">{summary.approved}</p>
          </div>
          <div className="vf-section p-4">
            <p className="text-xs vf-text-m">Rejected</p>
            <p className="text-2xl font-bold text-rose-400 mt-1">{summary.rejected}</p>
          </div>
          <div className="vf-section p-4">
            <p className="text-xs vf-text-m">Escalated</p>
            <p className={`text-2xl font-bold mt-1 ${summary.escalated > 0 ? "text-orange-400" : "vf-text-1"}`}>
              {summary.escalated}
            </p>
          </div>
        </div>
      )}

      {/* Tabs */}
      <div className="flex gap-1 border-b border-white/10 pb-0">
        {([
          { key: "queue",     label: "Queue",     icon: ClipboardCheck },
          { key: "rules",     label: "Rules",     icon: Settings },
          { key: "delegates", label: "Delegates", icon: Users2 },
        ] as const).map(({ key, label, icon: Icon }) => (
          <button key={key} onClick={() => setTab(key)}
            className={`flex items-center gap-1.5 px-4 py-2 text-xs font-medium border-b-2 -mb-px transition-all ${
              tab === key ? "border-indigo-500 text-indigo-300" : "border-transparent vf-text-m hover:vf-text-1"
            }`}>
            <Icon className="w-3.5 h-3.5" />{label}
            {key === "queue" && summary && summary.pending > 0 && (
              <span className="bg-amber-500/20 text-amber-300 text-[10px] px-1.5 py-0.5 rounded-full ml-1">
                {summary.pending}
              </span>
            )}
          </button>
        ))}
      </div>

      {loading && (
        <div className="flex justify-center py-12"><Loader2 className="w-5 h-5 animate-spin vf-text-m" /></div>
      )}

      {/* ── Queue ── */}
      {!loading && tab === "queue" && (
        <div className="space-y-4">
          <div className="flex items-center gap-2 justify-between flex-wrap">
            <div className="flex gap-1">
              {(["pending", "approved", "rejected"] as const).map(s => (
                <button key={s} onClick={() => setFilterStatus(s)}
                  className={`px-3 py-1.5 rounded text-xs font-medium capitalize transition-all ${
                    filterStatus === s ? "bg-indigo-500/20 text-indigo-300 ring-1 ring-indigo-500/40" : "vf-btn-ghost"
                  }`}>{s}</button>
              ))}
            </div>
            {filterStatus === "pending" && (
              <button onClick={escalateAll} disabled={escalatingAll}
                className="vf-btn-ghost text-xs px-3 py-1.5 text-orange-400">
                {escalatingAll
                  ? <Loader2 className="w-3.5 h-3.5 animate-spin inline" />
                  : <ShieldAlert className="w-3.5 h-3.5 inline mr-1" />}
                Escalate Overdue
              </button>
            )}
          </div>

          {requests.length === 0 && (
            <div className="vf-section p-10 text-center vf-text-m text-sm">
              <ClipboardCheck className="w-8 h-8 mx-auto mb-3 opacity-30" />
              No {filterStatus} approvals
            </div>
          )}

          <div className="space-y-2">
            {requests.map(req => {
              const days = daysPending(req.requested_at);
              const isEscalated = !!req.escalated_at;
              const isOpen = reviewingId === req.id;

              return (
                <div key={req.id}
                  className={`vf-section p-4 space-y-0 ${isEscalated ? "ring-1 ring-orange-500/40" : ""}`}>
                  <div className="flex items-start justify-between gap-3">
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 flex-wrap">
                        <p className="font-semibold vf-text-1 text-sm truncate">
                          {req.resource_label || req.resource_id}
                        </p>
                        <span className={`text-[10px] px-2 py-0.5 rounded-full font-medium ${STATUS_STYLE[req.status]}`}>
                          {req.status}
                        </span>
                        {isEscalated && (
                          <span className="text-[10px] px-2 py-0.5 rounded-full bg-orange-500/15 text-orange-300 border border-orange-500/30 font-medium flex items-center gap-1">
                            <ShieldAlert className="w-2.5 h-2.5" />Escalated → {req.escalated_to_role}
                          </span>
                        )}
                      </div>
                      <p className="text-xs vf-text-m mt-0.5">
                        {RESOURCE_LABELS[req.resource_type] ?? req.resource_type}
                        {" · "}{req.requested_by_email || req.requested_by}
                        {" · "}{fmtD(req.requested_at)}
                        {req.status === "pending" && days > 0 && (
                          <span className={days >= 7 ? " text-rose-400 font-medium" : " text-amber-400"}>
                            {" · "}{days}d waiting
                          </span>
                        )}
                      </p>
                      {req.reviewer_note && (
                        <p className="text-xs vf-text-m mt-1 italic">"{req.reviewer_note}"</p>
                      )}
                    </div>
                    <div className="text-right shrink-0">
                      {req.amount != null && (
                        <p className="text-sm font-mono font-bold vf-text-1">
                          {fmt(req.amount)} {req.currency}
                        </p>
                      )}
                      {req.status === "pending" && (
                        <div className="flex gap-1 mt-1 justify-end">
                          {!isEscalated && (
                            <button onClick={() => escalateOne(req.id)}
                              className="vf-btn-ghost text-[10px] px-1.5 py-1 text-orange-400">
                              Escalate
                            </button>
                          )}
                          <button
                            onClick={() => setReviewingId(isOpen ? null : req.id)}
                            className="vf-btn text-xs px-3 py-1.5"
                          >
                            {isOpen ? "Cancel" : "Review"}
                          </button>
                        </div>
                      )}
                    </div>
                  </div>

                  {isOpen && req.status === "pending" && (
                    <ReviewPanel req={req} onDone={async () => { setReviewingId(null); await load(); }} />
                  )}
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* ── Rules ── */}
      {!loading && tab === "rules" && (
        <div className="space-y-4">
          <div className="flex justify-between items-center">
            <p className="text-xs vf-text-m">Transactions at or above a threshold enter the approval queue.</p>
            <button onClick={() => setShowRuleForm(true)} className="vf-btn text-xs px-3 py-1.5">
              <Plus className="w-3.5 h-3.5 mr-1.5 inline" />New Rule
            </button>
          </div>

          {showRuleForm && (
            <div className="vf-section p-5 space-y-4">
              <p className="font-semibold vf-text-1 text-sm">New Approval Rule</p>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="text-xs vf-text-m block mb-1">Resource type</label>
                  <select className="vf-input text-sm w-full" value={ruleForm.resource_type}
                    onChange={e => setRuleForm(p => ({ ...p, resource_type: e.target.value }))}>
                    {Object.entries(RESOURCE_LABELS).map(([v, l]) => <option key={v} value={v}>{l}</option>)}
                  </select>
                </div>
                <div>
                  <label className="text-xs vf-text-m block mb-1">Required approver</label>
                  <select className="vf-input text-sm w-full" value={ruleForm.required_approver_role}
                    onChange={e => setRuleForm(p => ({ ...p, required_approver_role: e.target.value }))}>
                    <option value="OWNER">Owner (CEO)</option>
                    <option value="ADMIN">Admin or Owner</option>
                  </select>
                </div>
                <div>
                  <label className="text-xs vf-text-m block mb-1">Threshold amount</label>
                  <input type="number" className="vf-input text-sm w-full"
                    value={ruleForm.threshold_amount}
                    onChange={e => setRuleForm(p => ({ ...p, threshold_amount: Number(e.target.value) }))} />
                </div>
                <div>
                  <label className="text-xs vf-text-m block mb-1">Currency</label>
                  <input className="vf-input text-sm w-full" value={ruleForm.currency} maxLength={3}
                    onChange={e => setRuleForm(p => ({ ...p, currency: e.target.value.toUpperCase() }))} />
                </div>
                <div>
                  <label className="text-xs vf-text-m block mb-1">
                    Escalation (days without decision)
                  </label>
                  <input type="number" placeholder="e.g. 3" className="vf-input text-sm w-full"
                    value={ruleForm.escalation_days}
                    onChange={e => setRuleForm(p => ({ ...p, escalation_days: e.target.value }))} />
                </div>
                <div>
                  <label className="text-xs vf-text-m block mb-1">
                    Notify email when triggered
                  </label>
                  <input type="email" placeholder="ceo@company.com" className="vf-input text-sm w-full"
                    value={ruleForm.notify_email}
                    onChange={e => setRuleForm(p => ({ ...p, notify_email: e.target.value }))} />
                </div>
                <div className="col-span-2">
                  <label className="text-xs vf-text-m block mb-1">Description (optional)</label>
                  <input className="vf-input text-sm w-full"
                    placeholder="e.g. Owner must approve purchase orders above 10,000 SEK"
                    value={ruleForm.description}
                    onChange={e => setRuleForm(p => ({ ...p, description: e.target.value }))} />
                </div>
              </div>
              <div className="flex gap-2">
                <button onClick={createRule} className="vf-btn text-xs px-4 py-2">Create</button>
                <button onClick={() => setShowRuleForm(false)} className="vf-btn-ghost text-xs px-3 py-2">Cancel</button>
              </div>
            </div>
          )}

          {rules.length === 0 && !showRuleForm && (
            <div className="vf-section p-10 text-center vf-text-m text-sm">
              <Settings className="w-7 h-7 mx-auto mb-3 opacity-30" />
              No rules configured. Add one to enforce spending limits.
            </div>
          )}

          <div className="space-y-2">
            {rules.map(rule => (
              <div key={rule.id}
                className={`vf-section p-4 flex items-start justify-between gap-4 ${!rule.is_active ? "opacity-50" : ""}`}>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="font-medium vf-text-1 text-sm capitalize">
                      {RESOURCE_LABELS[rule.resource_type] ?? rule.resource_type}s
                    </span>
                    <span className="text-xs vf-text-m">≥ {fmt(rule.threshold_amount)} {rule.currency}</span>
                    <span className="text-[10px] px-2 py-0.5 bg-indigo-500/15 text-indigo-300 rounded">
                      → {rule.required_approver_role}
                    </span>
                    {rule.escalation_days && (
                      <span className="text-[10px] px-2 py-0.5 bg-orange-500/15 text-orange-300 rounded">
                        Escalates after {rule.escalation_days}d
                      </span>
                    )}
                    <span className={`text-[10px] px-2 py-0.5 rounded-full ${rule.is_active ? "bg-emerald-500/15 text-emerald-300" : "bg-gray-500/15 text-gray-400"}`}>
                      {rule.is_active ? "Active" : "Inactive"}
                    </span>
                  </div>
                  {rule.description && <p className="text-xs vf-text-m mt-0.5">{rule.description}</p>}
                  {rule.notify_email && (
                    <p className="text-xs vf-text-m mt-0.5">
                      Notifies <span className="vf-text-1">{rule.notify_email}</span>
                    </p>
                  )}
                </div>
                <div className="flex items-center gap-2 shrink-0">
                  <button onClick={() => toggleRule(rule)}
                    className="vf-btn-ghost text-xs px-2 py-1.5">
                    {rule.is_active ? "Disable" : "Enable"}
                  </button>
                  <button onClick={() => deleteRule(rule.id)}
                    className="vf-btn-ghost p-1.5 text-rose-400">
                    <X className="w-4 h-4" />
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* ── Delegates ── */}
      {!loading && tab === "delegates" && (
        <div className="space-y-4">
          <div className="flex justify-between items-center">
            <p className="text-xs vf-text-m">
              Delegates allow a staff member to approve on behalf of a role while the
              primary approver is away.
            </p>
            <button onClick={() => setShowDelegForm(true)} className="vf-btn text-xs px-3 py-1.5">
              <Plus className="w-3.5 h-3.5 mr-1.5 inline" />Add Delegate
            </button>
          </div>

          {showDelegForm && (
            <div className="vf-section p-5 space-y-4">
              <p className="font-semibold vf-text-1 text-sm">New Approval Delegate</p>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="text-xs vf-text-m block mb-1">Role being delegated</label>
                  <select className="vf-input text-sm w-full" value={delegForm.delegated_from_role}
                    onChange={e => setDelegForm(p => ({ ...p, delegated_from_role: e.target.value }))}>
                    <option value="OWNER">Owner</option>
                    <option value="ADMIN">Admin</option>
                  </select>
                </div>
                <div>
                  <label className="text-xs vf-text-m block mb-1">Delegate's email</label>
                  <input type="email" className="vf-input text-sm w-full"
                    placeholder="delegate@company.com"
                    value={delegForm.delegated_to_email}
                    onChange={e => setDelegForm(p => ({ ...p, delegated_to_email: e.target.value }))} />
                </div>
                <div>
                  <label className="text-xs vf-text-m block mb-1">Staff ID (UUID)</label>
                  <input className="vf-input text-sm w-full font-mono"
                    placeholder="xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
                    value={delegForm.delegated_to_user_id}
                    onChange={e => setDelegForm(p => ({ ...p, delegated_to_user_id: e.target.value }))} />
                </div>
                <div />
                <div>
                  <label className="text-xs vf-text-m block mb-1">Valid from</label>
                  <input type="date" className="vf-input text-sm w-full"
                    value={delegForm.valid_from}
                    onChange={e => setDelegForm(p => ({ ...p, valid_from: e.target.value }))} />
                </div>
                <div>
                  <label className="text-xs vf-text-m block mb-1">Valid until</label>
                  <input type="date" className="vf-input text-sm w-full"
                    value={delegForm.valid_until}
                    onChange={e => setDelegForm(p => ({ ...p, valid_until: e.target.value }))} />
                </div>
                <div className="col-span-2">
                  <label className="text-xs vf-text-m block mb-1">Note (optional)</label>
                  <input className="vf-input text-sm w-full"
                    placeholder="e.g. Covering while Alice is on parental leave"
                    value={delegForm.note}
                    onChange={e => setDelegForm(p => ({ ...p, note: e.target.value }))} />
                </div>
              </div>
              <div className="flex gap-2">
                <button onClick={createDelegate} className="vf-btn text-xs px-4 py-2">Add</button>
                <button onClick={() => setShowDelegForm(false)} className="vf-btn-ghost text-xs px-3 py-2">Cancel</button>
              </div>
            </div>
          )}

          {delegates.length === 0 && !showDelegForm && (
            <div className="vf-section p-10 text-center vf-text-m text-sm">
              <Users2 className="w-7 h-7 mx-auto mb-3 opacity-30" />
              No active delegates. Use this when an approver is on leave.
            </div>
          )}

          <div className="space-y-2">
            {delegates.map(d => {
              const now = new Date();
              const from  = new Date(d.valid_from);
              const until = new Date(d.valid_until);
              const isActive = now >= from && now <= until;
              return (
                <div key={d.id} className={`vf-section p-4 flex items-start justify-between gap-4 ${!isActive ? "opacity-55" : ""}`}>
                  <div>
                    <div className="flex items-center gap-2">
                      <p className="font-medium vf-text-1 text-sm">
                        {d.delegated_to_email || d.delegated_to_user_id.slice(0, 8) + "…"}
                      </p>
                      <span className="text-[10px] px-2 py-0.5 bg-indigo-500/15 text-indigo-300 rounded">
                        covers {d.delegated_from_role}
                      </span>
                      {isActive && (
                        <span className="text-[10px] px-2 py-0.5 bg-emerald-500/15 text-emerald-300 rounded">Active</span>
                      )}
                    </div>
                    <p className="text-xs vf-text-m mt-0.5">
                      {d.valid_from} → {d.valid_until}
                      {d.note && ` · ${d.note}`}
                    </p>
                  </div>
                  <button onClick={() => deleteDelegate(d.id)} className="vf-btn-ghost p-1.5 text-rose-400 shrink-0">
                    <Trash2 className="w-4 h-4" />
                  </button>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}
