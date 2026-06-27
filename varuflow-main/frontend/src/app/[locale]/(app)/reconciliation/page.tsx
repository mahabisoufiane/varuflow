"use client";
import { useEffect, useState } from "react";
import { RoleGuard } from "@/components/app/RoleContext";
import { api } from "@/lib/api-client";
import { toast } from "sonner";
import { CheckCircle, Clock, AlertCircle, ArrowUpCircle, BarChart3, Filter } from "lucide-react";
import { isPlanGateError, PlanGateBlock } from "@/components/ui/PlanGate";
import styles from "./page.module.scss";

interface PaymentRow {
  id: string;
  invoice_number: string;
  invoice_total: number;
  invoice_amount_paid: number;
  invoice_outstanding: number;
  currency: string;
  amount: number;
  payment_date: string;
  method: string;
  match_status: "matched" | "partial" | "unmatched";
  overpaid: number;
}

interface Summary {
  period: string;
  from_date: string;
  to_date: string;
  total_received: number;
  payment_count: number;
  unmatched_invoices: number;
  partial_invoices: number;
  overpaid_invoices: number;
  by_method: { method: string; total: number; count: number }[];
}

interface Invoice {
  id: string;
  invoice_number: string;
  customer_id: string | null;
  total_amount: number;
  amount_paid?: number;
  outstanding?: number;
  overpaid_by?: number;
  currency: string;
  due_date: string | null;
  status: string;
  days_overdue?: number;
}

const MATCH_BADGE = {
  matched: "bg-green-100 text-green-700",
  partial: "bg-yellow-100 text-yellow-700",
  unmatched: "bg-red-100 text-red-700",
};

const MATCH_MODULE: Record<string, keyof typeof styles> = {
  matched:   "matchMatched",
  partial:   "matchPartial",
  unmatched: "matchUnmatched",
};

function ReconciliationPageInner() {
  const [tab, setTab] = useState<"overview" | "unmatched" | "partial" | "overpaid">("overview");
  const [period, setPeriod] = useState("month");
  const [summary, setSummary] = useState<Summary | null>(null);
  const [payments, setPayments] = useState<PaymentRow[]>([]);
  const [unmatched, setUnmatched] = useState<Invoice[]>([]);
  const [partial, setPartial] = useState<Invoice[]>([]);
  const [overpaid, setOverpaid] = useState<Invoice[]>([]);
  const [loading, setLoading] = useState(true);
  const [planBlocked, setPlanBlocked] = useState<{ module: string; currentPlan: string } | null>(null);

  useEffect(() => { loadSummary(); loadOverview(); }, [period]);
  useEffect(() => {
    if (tab === "unmatched") loadUnmatched();
    else if (tab === "partial") loadPartial();
    else if (tab === "overpaid") loadOverpaid();
  }, [tab]);

  async function loadSummary() {
    try {
      const data = await api.get(`/api/reconciliation/summary?period=${period}`);
      setSummary(data);
    } catch { toast.error("Failed to load summary"); }
  }

  async function loadOverview() {
    setLoading(true);
    try {
      const data = await api.get("/api/reconciliation?limit=100");
      setPayments(Array.isArray(data) ? data : []);
    } catch (err) {
      if (isPlanGateError(err)) {
        setPlanBlocked({ module: (err as any).module ?? "finance", currentPlan: (err as any).currentPlan ?? "FREE" });
        return;
      }
      toast.error("Failed to load payments");
    }
    finally { setLoading(false); }
  }

  async function loadUnmatched() {
    try {
      const data = await api.get("/api/reconciliation/unmatched");
      setUnmatched(Array.isArray(data) ? data : []);
    } catch { toast.error("Failed to load"); }
  }

  async function loadPartial() {
    try {
      const data = await api.get("/api/reconciliation/partial");
      setPartial(Array.isArray(data) ? data : []);
    } catch { toast.error("Failed to load"); }
  }

  async function loadOverpaid() {
    try {
      const data = await api.get("/api/reconciliation/overpaid");
      setOverpaid(Array.isArray(data) ? data : []);
    } catch { toast.error("Failed to load"); }
  }

  if (planBlocked) return <PlanGateBlock module={planBlocked.module} currentPlan={planBlocked.currentPlan} featureName="Payment Reconciliation" />;

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold flex items-center gap-2"><BarChart3 size={22} /> Payment Reconciliation</h1>
          <p className="text-sm text-gray-500 mt-0.5">Match payments to invoices and review outstanding balances</p>
        </div>
        <select value={period} onChange={e => setPeriod(e.target.value)} className="input">
          <option value="today">Today</option>
          <option value="week">Last 7 days</option>
          <option value="month">This month</option>
          <option value="year">This year</option>
        </select>
      </div>

      {/* Summary cards */}
      {summary && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          {[
            { label: "Total received", value: `${summary.total_received.toLocaleString("sv-SE", { minimumFractionDigits: 2 })}`, sub: `${summary.payment_count} payments`, icon: <CheckCircle size={18} />, color: "text-green-600" },
            { label: "Unmatched", value: summary.unmatched_invoices, sub: "awaiting payment", icon: <Clock size={18} />, color: "text-yellow-600" },
            { label: "Partial payments", value: summary.partial_invoices, sub: "outstanding balance", icon: <AlertCircle size={18} />, color: "text-amber-600" },
            { label: "Overpaid", value: summary.overpaid_invoices, sub: "exceed invoice total", icon: <ArrowUpCircle size={18} />, color: "text-purple-600" },
          ].map(c => (
            <div key={c.label} className="bg-white border rounded-lg p-4">
              <div className={`${c.color} mb-1`}>{c.icon}</div>
              <p className="text-lg font-bold">{c.value}</p>
              <p className="text-xs text-gray-500">{c.label}</p>
              <p className="text-[10px] text-gray-400">{c.sub}</p>
            </div>
          ))}
        </div>
      )}

      {/* Payment method breakdown */}
      {summary?.by_method && summary.by_method.length > 0 && (
        <div className="bg-white border rounded-lg p-4">
          <h3 className="font-semibold text-sm mb-3">Payment Method Breakdown</h3>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            {summary.by_method.map(m => (
              <div key={m.method} className="border rounded-lg p-3 bg-gray-50">
                <p className="text-xs font-semibold text-gray-600 capitalize">{m.method.replace("_", " ")}</p>
                <p className="text-base font-bold mt-1">{m.total.toLocaleString("sv-SE", { minimumFractionDigits: 2 })}</p>
                <p className="text-[10px] text-gray-400">{m.count} transactions</p>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Tab bar */}
      <div className="flex gap-1 border-b">
        {(["overview", "unmatched", "partial", "overpaid"] as const).map(t => (
          <button key={t} onClick={() => setTab(t)}
            className={`px-4 py-2 text-sm font-medium capitalize ${tab === t ? "border-b-2 border-[#1a2332] text-[#1a2332]" : "text-gray-500"}`}>
            {t.charAt(0).toUpperCase() + t.slice(1)}
            {t === "unmatched" && summary && summary.unmatched_invoices > 0 && (
              <span className="ml-1.5 px-1.5 py-0.5 rounded-full bg-red-500 text-white text-[10px]">{summary.unmatched_invoices}</span>
            )}
            {t === "partial" && summary && summary.partial_invoices > 0 && (
              <span className="ml-1.5 px-1.5 py-0.5 rounded-full bg-amber-500 text-white text-[10px]">{summary.partial_invoices}</span>
            )}
          </button>
        ))}
      </div>

      {/* ── Overview tab ─────────────────────────────────────────── */}
      {tab === "overview" && (
        <div className="bg-white border rounded-lg overflow-hidden">
          {loading ? (
            <p className="p-4 text-sm text-gray-400">Loading…</p>
          ) : payments.length === 0 ? (
            <p className="p-6 text-center text-sm text-gray-400">No payments found.</p>
          ) : (
            <table className="w-full text-xs">
              <thead className="bg-gray-50 border-b">
                <tr>
                  {["Invoice", "Match", "Payment date", "Method", "Invoice total", "Paid", "Outstanding"].map(h => (
                    <th key={h} className="px-3 py-2 text-left font-semibold text-gray-500">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {payments.map(p => (
                  <tr key={p.id} className="border-b hover:bg-gray-50">
                    <td className="px-3 py-2 font-medium">{p.invoice_number}</td>
                    <td className="px-3 py-2">
                      <span className={styles[MATCH_MODULE[p.match_status] ?? "matchUnmatched"]}>
                        {p.match_status.charAt(0).toUpperCase() + p.match_status.slice(1)}
                      </span>
                    </td>
                    <td className="px-3 py-2 text-gray-500">{new Date(p.payment_date).toLocaleDateString()}</td>
                    <td className="px-3 py-2 capitalize">{p.method.replace("_", " ").toLowerCase()}</td>
                    <td className="px-3 py-2 font-mono">{p.invoice_total.toFixed(2)} {p.currency}</td>
                    <td className="px-3 py-2 font-mono text-green-700">{p.invoice_amount_paid.toFixed(2)}</td>
                    <td className={`px-3 py-2 font-mono ${p.invoice_outstanding > 0 ? "text-red-600" : "text-gray-400"}`}>
                      {p.overpaid > 0 ? `+${p.overpaid.toFixed(2)} over` : p.invoice_outstanding.toFixed(2)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}

      {/* ── Unmatched tab ────────────────────────────────────────── */}
      {tab === "unmatched" && (
        <div className="bg-white border rounded-lg overflow-hidden">
          {unmatched.length === 0 ? (
            <div className="p-8 text-center text-gray-400">
              <CheckCircle size={32} className="mx-auto mb-2 text-green-400" />
              <p className="text-sm font-medium text-green-600">All caught up!</p>
              <p className="text-xs mt-1">No unmatched invoices.</p>
            </div>
          ) : (
            <table className="w-full text-xs">
              <thead className="bg-gray-50 border-b">
                <tr>
                  {["Invoice", "Amount", "Due date", "Overdue", "Status"].map(h => (
                    <th key={h} className="px-4 py-2 text-left font-semibold text-gray-500">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {unmatched.map(inv => (
                  <tr key={inv.id} className="border-b hover:bg-gray-50">
                    <td className="px-4 py-2 font-medium">{inv.invoice_number}</td>
                    <td className="px-4 py-2 font-mono">{inv.total_amount.toFixed(2)} {inv.currency}</td>
                    <td className="px-4 py-2 text-gray-500">{inv.due_date ? new Date(inv.due_date).toLocaleDateString() : "—"}</td>
                    <td className="px-4 py-2">
                      {(inv.days_overdue ?? 0) > 0 ? (
                        <span className="text-red-600 font-medium">{inv.days_overdue}d overdue</span>
                      ) : <span className="text-gray-400">Not due yet</span>}
                    </td>
                    <td className="px-4 py-2">
                      <span className="px-2 py-0.5 rounded-full text-[10px] bg-yellow-100 text-yellow-700 capitalize">
                        {inv.status.toLowerCase()}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}

      {/* ── Partial tab ───────────────────────────────────────────── */}
      {tab === "partial" && (
        <div className="bg-white border rounded-lg overflow-hidden">
          {partial.length === 0 ? (
            <p className="p-6 text-center text-sm text-gray-400">No partially paid invoices.</p>
          ) : (
            <table className="w-full text-xs">
              <thead className="bg-gray-50 border-b">
                <tr>
                  {["Invoice", "Total", "Paid", "Outstanding", "Due date"].map(h => (
                    <th key={h} className="px-4 py-2 text-left font-semibold text-gray-500">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {partial.map(inv => {
                  const pct = inv.total_amount > 0 ? ((inv.amount_paid ?? 0) / inv.total_amount * 100) : 0;
                  return (
                    <tr key={inv.id} className="border-b hover:bg-gray-50">
                      <td className="px-4 py-2 font-medium">{inv.invoice_number}</td>
                      <td className="px-4 py-2 font-mono">{inv.total_amount.toFixed(2)} {inv.currency}</td>
                      <td className="px-4 py-2">
                        <div className="flex items-center gap-2">
                          <div className="flex-1 bg-gray-200 rounded-full h-1.5 w-16">
                            <div className="bg-green-500 h-1.5 rounded-full" style={{ width: `${pct}%` }} />
                          </div>
                          <span className="font-mono text-green-700">{(inv.amount_paid ?? 0).toFixed(2)}</span>
                        </div>
                      </td>
                      <td className="px-4 py-2 font-mono text-red-600">{(inv.outstanding ?? 0).toFixed(2)}</td>
                      <td className="px-4 py-2 text-gray-500">{inv.due_date ? new Date(inv.due_date).toLocaleDateString() : "—"}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          )}
        </div>
      )}

      {/* ── Overpaid tab ─────────────────────────────────────────── */}
      {tab === "overpaid" && (
        <div className="bg-white border rounded-lg overflow-hidden">
          {overpaid.length === 0 ? (
            <p className="p-6 text-center text-sm text-gray-400">No overpaid invoices.</p>
          ) : (
            <table className="w-full text-xs">
              <thead className="bg-gray-50 border-b">
                <tr>
                  {["Invoice", "Invoice total", "Total paid", "Overpaid by", "Currency"].map(h => (
                    <th key={h} className="px-4 py-2 text-left font-semibold text-gray-500">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {overpaid.map(inv => (
                  <tr key={inv.id} className="border-b hover:bg-gray-50">
                    <td className="px-4 py-2 font-medium">{inv.invoice_number}</td>
                    <td className="px-4 py-2 font-mono">{inv.total_amount.toFixed(2)}</td>
                    <td className="px-4 py-2 font-mono">{(inv.amount_paid ?? 0).toFixed(2)}</td>
                    <td className="px-4 py-2 font-mono text-purple-600">+{(inv.overpaid_by ?? 0).toFixed(2)}</td>
                    <td className="px-4 py-2">{inv.currency}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}
    </div>
  );
}

export default function ReconciliationPage() {
  return (
    <RoleGuard minRole="ADMIN">
      <ReconciliationPageInner />
    </RoleGuard>
  );
}
