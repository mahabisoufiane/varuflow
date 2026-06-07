"use client";

import { useState, useEffect } from "react";
import { toast } from "sonner";
import { api } from "@/lib/api-client";
import { TrendingDown, AlertTriangle, Check, RefreshCw, UserX, UserCheck } from "lucide-react";

interface ChurnedCustomer {
  id: string; name: string; email: string; churned_at: string | null;
  churn_reason: string | null; churn_reason_label: string; churn_score: number | null;
  revenue_lost_12m: number; last_invoice_date: string | null;
  type: "explicit" | "inferred"; days_inactive?: number;
}

interface RiskCustomer {
  id: string; name: string; email: string; churn_score: number;
  days_inactive: number; invoices_l12m: number; invoices_prev_12m: number;
  rev_l12m: number; rev_prev_12m: number; risk_level: "high" | "medium" | "low";
}

interface ChurnOverview {
  churned_customers: ChurnedCustomer[];
  at_risk_customers: ChurnedCustomer[];
  monthly_churn: { month: string; count: number }[];
  reasons_breakdown: { reason: string; label: string; count: number }[];
  summary: {
    total_churned: number; total_at_risk: number;
    total_revenue_lost: number; churn_rate_pct: number;
    active_customers: number; period_months: number;
  };
  reason_options: { value: string; label: string }[];
}

const RISK_COLORS = { high: "text-red-600 bg-red-50 border-red-200", medium: "text-amber-600 bg-amber-50 border-amber-200", low: "text-green-600 bg-green-50 border-green-200" };
const RISK_BAR = { high: "bg-red-500", medium: "bg-amber-400", low: "bg-green-400" };

export default function ChurnPage() {

  const [overview, setOverview] = useState<ChurnOverview | null>(null);
  const [riskScores, setRiskScores] = useState<RiskCustomer[]>([]);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState<"churned" | "at_risk" | "risk_scores">("churned");
  const [months, setMonths] = useState(12);

  // Mark churned dialog
  const [markId, setMarkId] = useState<string | null>(null);
  const [markReason, setMarkReason] = useState("");

  const fmt = (v: number) => v.toLocaleString("sv-SE", { maximumFractionDigits: 0 });

  async function load(m: number) {
    setLoading(true);
    try {
      const [ov, rs] = await Promise.all([
        api.get<ChurnOverview>(`/api/growth/churn/overview?months=${m}`),
        api.get<RiskCustomer[]>("/api/growth/churn/risk-scores"),
      ]);
      setOverview(ov);
      setRiskScores(rs);
    } catch {
      // overview stays null — error state handled below
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { load(months); }, [months]);

  async function markChurned(customerId: string) {
    try {
      await api.post("/api/growth/churn/mark-churned", { customer_id: customerId, churn_reason: markReason || null });
      toast.success("Customer marked as churned");
      setMarkId(null);
      load(months);
    } catch {
      toast.error("Failed");
    }
  }

  async function reactivate(customerId: string) {
    try {
      await api.post(`/api/growth/churn/unmark-churned?customer_id=${customerId}`, {});
      toast.success("Customer reactivated");
      load(months);
    } catch {
      toast.error("Failed");
    }
  }

  if (loading) return <div className="animate-pulse space-y-4">{[1,2,3].map(i => <div key={i} className="h-24 rounded-xl bg-gray-100" />)}</div>;
  if (!overview) return <p className="text-gray-500 p-4">Failed to load churn data.</p>;

  const { summary, reasons_breakdown, monthly_churn, reason_options } = overview;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <h1 className="text-2xl font-semibold text-gray-900">Churn Dashboard</h1>
          <p className="mt-1 text-sm text-gray-500">Track lost customers, understand why they left, and identify who&apos;s at risk next.</p>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-sm text-gray-500">Period:</span>
          {[3, 6, 12].map(m => (
            <button key={m} onClick={() => setMonths(m)}
              className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-all ${months === m ? "bg-blue-500 text-white" : "bg-gray-100 text-gray-700 hover:bg-gray-200"}`}>
              {m}m
            </button>
          ))}
          <button onClick={() => load(months)} className="p-1.5 rounded-lg bg-gray-100 hover:bg-gray-200 text-gray-500">
            <RefreshCw className="h-4 w-4" />
          </button>
        </div>
      </div>

      {/* Summary */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
        <div className="rounded-xl border border-red-200 bg-red-50 p-4">
          <p className="text-xs font-medium text-red-600 uppercase">Churned</p>
          <p className="text-2xl font-bold text-red-700 mt-1">{summary.total_churned}</p>
          <p className="text-xs text-red-500">last {summary.period_months} months</p>
        </div>
        <div className="rounded-xl border border-amber-200 bg-amber-50 p-4">
          <p className="text-xs font-medium text-amber-600 uppercase">At Risk</p>
          <p className="text-2xl font-bold text-amber-700 mt-1">{summary.total_at_risk}</p>
          <p className="text-xs text-amber-500">90+ days inactive</p>
        </div>
        <div className="rounded-xl border border-gray-200 bg-white p-4">
          <p className="text-xs font-medium text-gray-500 uppercase">Revenue Lost</p>
          <p className="text-2xl font-bold text-gray-900 mt-1">{fmt(summary.total_revenue_lost)}</p>
          <p className="text-xs text-gray-400">12-month rev of churned</p>
        </div>
        <div className="rounded-xl border border-gray-200 bg-white p-4">
          <p className="text-xs font-medium text-gray-500 uppercase">Churn Rate</p>
          <p className="text-2xl font-bold text-gray-900 mt-1">{summary.churn_rate_pct}%</p>
          <p className="text-xs text-gray-400">{summary.active_customers} active customers</p>
        </div>
      </div>

      {/* Monthly churn sparkline + reasons */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        {monthly_churn.length > 0 && (
          <div className="rounded-xl border border-gray-200 bg-white p-4">
            <p className="text-sm font-semibold text-gray-700 mb-3">Monthly Churn</p>
            <div className="flex items-end gap-1.5 h-20">
              {monthly_churn.map(m => {
                const maxCount = Math.max(...monthly_churn.map(x => x.count), 1);
                const h = Math.max(4, (m.count / maxCount) * 72);
                return (
                  <div key={m.month} className="flex flex-col items-center flex-1 gap-1" title={`${m.month}: ${m.count}`}>
                    <div className="rounded-sm bg-red-400 w-full" style={{ height: `${h}px` }} />
                    <span className="text-[9px] text-gray-400 hidden sm:block">{m.month.slice(5)}</span>
                  </div>
                );
              })}
            </div>
          </div>
        )}

        {reasons_breakdown.length > 0 && (
          <div className="rounded-xl border border-gray-200 bg-white p-4">
            <p className="text-sm font-semibold text-gray-700 mb-3">Churn Reasons</p>
            <div className="space-y-2">
              {reasons_breakdown.slice(0, 5).map(r => {
                const total = reasons_breakdown.reduce((s, x) => s + x.count, 0);
                const pct = total > 0 ? Math.round(r.count / total * 100) : 0;
                return (
                  <div key={r.reason} className="flex items-center gap-2">
                    <span className="text-xs text-gray-600 w-32 truncate">{r.label}</span>
                    <div className="flex-1 h-2 bg-gray-100 rounded-full overflow-hidden">
                      <div className="h-full bg-red-400 rounded-full" style={{ width: `${pct}%` }} />
                    </div>
                    <span className="text-xs text-gray-500 w-8 text-right">{r.count}</span>
                  </div>
                );
              })}
            </div>
          </div>
        )}
      </div>

      {/* Tabs */}
      <div className="flex gap-2 border-b border-gray-200">
        {([
          { key: "churned", label: `Churned (${overview.churned_customers.length})` },
          { key: "at_risk", label: `At Risk (${overview.at_risk_customers.length})` },
          { key: "risk_scores", label: `Risk Scores (${riskScores.length})` },
        ] as const).map(tab => (
          <button key={tab.key} onClick={() => setActiveTab(tab.key)}
            className={`px-4 py-2 text-sm font-medium border-b-2 -mb-px transition-all ${
              activeTab === tab.key ? "border-blue-500 text-blue-600" : "border-transparent text-gray-500 hover:text-gray-700"
            }`}>{tab.label}</button>
        ))}
      </div>

      {/* Mark churned dialog */}
      {markId && (
        <div className="rounded-xl border border-red-200 bg-red-50 p-4 space-y-3">
          <p className="text-sm font-semibold text-red-800">Mark as Churned</p>
          <select className="input" value={markReason} onChange={e => setMarkReason(e.target.value)}>
            <option value="">Select reason (optional)</option>
            {reason_options.map(r => <option key={r.value} value={r.value}>{r.label}</option>)}
          </select>
          <div className="flex gap-2">
            <button onClick={() => markChurned(markId)} className="text-sm px-3 py-1.5 rounded-lg bg-red-600 text-white hover:bg-red-700">Confirm Churn</button>
            <button onClick={() => setMarkId(null)} className="btn-secondary text-sm">Cancel</button>
          </div>
        </div>
      )}

      {/* Churned customers */}
      {activeTab === "churned" && (
        <div className="space-y-2">
          {overview.churned_customers.length === 0 && (
            <div className="text-center py-12 text-gray-400">
              <UserCheck className="h-8 w-8 mx-auto mb-2 opacity-40" />
              <p>No explicitly churned customers in this period.</p>
            </div>
          )}
          {overview.churned_customers.map(c => (
            <div key={c.id} className="rounded-xl border border-gray-200 bg-white p-4 flex items-center justify-between gap-4">
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 flex-wrap">
                  <span className="font-medium text-gray-900">{c.name}</span>
                  <span className="text-xs text-red-600 bg-red-50 px-2 py-0.5 rounded-full">{c.churn_reason_label || "Reason unknown"}</span>
                </div>
                <p className="text-xs text-gray-500 mt-0.5">{c.email} · Churned {c.churned_at ? new Date(c.churned_at).toLocaleDateString("sv-SE") : "—"}</p>
              </div>
              <div className="text-right flex-shrink-0">
                <p className="text-sm font-semibold text-red-700">−{fmt(c.revenue_lost_12m)}</p>
                <p className="text-xs text-gray-400">12m revenue</p>
              </div>
              <button onClick={() => reactivate(c.id)} className="flex-shrink-0 p-1.5 rounded-lg hover:bg-green-50 text-gray-400 hover:text-green-600" title="Reactivate">
                <UserCheck className="h-4 w-4" />
              </button>
            </div>
          ))}
        </div>
      )}

      {/* At-risk customers */}
      {activeTab === "at_risk" && (
        <div className="space-y-2">
          {overview.at_risk_customers.length === 0 && (
            <div className="text-center py-12 text-gray-400">
              <Check className="h-8 w-8 mx-auto mb-2 opacity-40 text-green-500" />
              <p>No customers with 90+ days inactivity.</p>
            </div>
          )}
          {overview.at_risk_customers.map(c => (
            <div key={c.id} className="rounded-xl border border-amber-200 bg-white p-4 flex items-center justify-between gap-4">
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 flex-wrap">
                  <span className="font-medium text-gray-900">{c.name}</span>
                  <span className="text-xs text-amber-600 bg-amber-50 px-2 py-0.5 rounded-full">
                    <AlertTriangle className="h-3 w-3 inline mr-0.5" />
                    {c.days_inactive}d inactive
                  </span>
                </div>
                <p className="text-xs text-gray-500 mt-0.5">{c.email} · Last invoice: {c.last_invoice_date || "Never"}</p>
              </div>
              <div className="text-right flex-shrink-0">
                <p className="text-sm font-semibold text-gray-700">{fmt(c.revenue_lost_12m)}</p>
                <p className="text-xs text-gray-400">12m revenue</p>
              </div>
              <button onClick={() => setMarkId(c.id)} className="flex-shrink-0 p-1.5 rounded-lg hover:bg-red-50 text-gray-400 hover:text-red-500" title="Mark as churned">
                <UserX className="h-4 w-4" />
              </button>
            </div>
          ))}
        </div>
      )}

      {/* Risk scores */}
      {activeTab === "risk_scores" && (
        <div className="space-y-2">
          {riskScores.length === 0 && <p className="text-center py-8 text-gray-400">No risk score data available.</p>}
          {riskScores.slice(0, 50).map(c => (
            <div key={c.id} className={`rounded-xl border p-4 flex items-center gap-4 ${RISK_COLORS[c.risk_level]}`}>
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 flex-wrap">
                  <span className="font-medium text-gray-900">{c.name}</span>
                  <span className="text-xs font-medium capitalize">{c.risk_level} risk</span>
                </div>
                <div className="flex gap-4 text-xs text-gray-500 mt-0.5 flex-wrap">
                  <span>{c.days_inactive}d inactive</span>
                  <span>{c.invoices_l12m} inv last 12m (was {c.invoices_prev_12m})</span>
                  <span>Rev {c.rev_l12m.toLocaleString("sv-SE", { maximumFractionDigits: 0 })} (was {c.rev_prev_12m.toLocaleString("sv-SE", { maximumFractionDigits: 0 })})</span>
                </div>
              </div>
              <div className="flex-shrink-0 w-24">
                <div className="flex justify-between text-xs mb-1">
                  <span>Risk</span>
                  <span className="font-semibold">{c.churn_score}</span>
                </div>
                <div className="h-2 bg-gray-200 rounded-full overflow-hidden">
                  <div className={`h-full rounded-full ${RISK_BAR[c.risk_level]}`} style={{ width: `${c.churn_score}%` }} />
                </div>
              </div>
              <button onClick={() => setMarkId(c.id)} className="flex-shrink-0 p-1.5 rounded-lg hover:bg-red-50 text-gray-400 hover:text-red-500" title="Mark as churned">
                <UserX className="h-4 w-4" />
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
