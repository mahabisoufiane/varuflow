"use client";
import { useEffect, useState, useCallback } from "react";
import {
  TrendingUp, TrendingDown, AlertTriangle, Plus, Trash2,
  ChevronRight, BarChart3,
} from "lucide-react";
import { api } from "@/lib/api-client";
import { toast } from "sonner";
import styles from "./page.module.scss";

// ── Types ─────────────────────────────────────────────────────────────────────

interface DayPoint {
  date: string;
  inflows: number;
  outflows: number;
  net: number;
  balance: number;
}
interface CashFlowItem {
  id: string;
  source: "invoice" | "recurring" | "expense" | "purchase_order" | "payroll" | "adjustment";
  label: string;
  best_date: string;
  worst_date: string;
  amount: number;
}
interface Adjustment {
  id: string;
  adjustment_date: string;
  label: string;
  amount: number;
  note: string | null;
}
interface CashFlowData {
  horizon_days: number;
  best_case: DayPoint[];
  worst_case: DayPoint[];
  items: CashFlowItem[];
  adjustments: Adjustment[];
  best_negative_dates: string[];
  worst_negative_dates: string[];
}

// ── Helpers ───────────────────────────────────────────────────────────────────

function fmt(n: number) {
  return n.toLocaleString("sv-SE", { minimumFractionDigits: 0, maximumFractionDigits: 0 });
}
function fmtK(n: number) {
  if (Math.abs(n) >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (Math.abs(n) >= 1_000) return `${(n / 1_000).toFixed(1)}k`;
  return String(Math.round(n));
}

/** Group daily points into calendar weeks (Mon–Sun ISO approach) */
function toWeekly(days: DayPoint[]): { label: string; inflows: number; outflows: number; balance: number }[] {
  if (!days.length) return [];
  const weeks: Record<string, { inflows: number; outflows: number; balance: number; lastBalance: number }> = {};

  for (const d of days) {
    const dt = new Date(d.date);
    // ISO week start = Monday
    const day = dt.getDay(); // 0=Sun
    const diff = (day === 0 ? -6 : 1) - day;
    const mon = new Date(dt);
    mon.setDate(dt.getDate() + diff);
    const key = mon.toISOString().slice(0, 10);
    if (!weeks[key]) weeks[key] = { inflows: 0, outflows: 0, balance: 0, lastBalance: 0 };
    weeks[key].inflows += d.inflows;
    weeks[key].outflows += d.outflows;
    weeks[key].lastBalance = d.balance;
  }

  return Object.entries(weeks)
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([weekStart, v]) => ({
      label: new Date(weekStart).toLocaleDateString("en-GB", { day: "numeric", month: "short" }),
      inflows: v.inflows,
      outflows: v.outflows,
      balance: v.lastBalance,
    }));
}

const SOURCE_LABELS: Record<string, string> = {
  invoice: "Outstanding Invoices",
  recurring: "Recurring Income",
  expense: "Approved Expenses",
  purchase_order: "Purchase Orders",
  payroll: "Payroll",
  adjustment: "Manual Adjustments",
};
const SOURCE_COLOR: Record<string, string> = {
  invoice: "bg-blue-100 text-blue-700",
  recurring: "bg-purple-100 text-purple-700",
  expense: "bg-red-100 text-red-700",
  purchase_order: "bg-orange-100 text-orange-700",
  payroll: "bg-rose-100 text-rose-700",
  adjustment: "bg-gray-100 text-gray-700",
};

// ── Chart ─────────────────────────────────────────────────────────────────────

function CashChart({
  series,
  scenario,
}: {
  series: DayPoint[];
  scenario: "best" | "worst";
}) {
  const weeks = toWeekly(series);
  if (!weeks.length) return <p className="text-sm text-gray-400">No data</p>;

  const maxVal = Math.max(...weeks.flatMap((w) => [w.inflows, w.outflows]), 1);
  const H = 140;

  return (
    <div className="space-y-2">
      <div className="flex items-end gap-1 h-40 overflow-x-auto pb-1">
        {weeks.map((w) => {
          const inH = Math.max((w.inflows / maxVal) * H, w.inflows > 0 ? 2 : 0);
          const outH = Math.max((w.outflows / maxVal) * H, w.outflows > 0 ? 2 : 0);
          const bal = w.balance;
          return (
            <div key={w.label} className="flex flex-col items-center gap-0.5 group relative min-w-[40px] flex-1">
              {/* Tooltip */}
              <div className="absolute bottom-full left-1/2 -translate-x-1/2 mb-1 hidden group-hover:block z-10 bg-gray-900 text-white text-[10px] rounded px-2 py-1 whitespace-nowrap shadow">
                <div className="font-semibold">{w.label}</div>
                <div className="text-green-300">In {fmtK(w.inflows)}</div>
                <div className="text-red-300">Out {fmtK(w.outflows)}</div>
                <div className={bal >= 0 ? "text-blue-300" : "text-orange-300"}>
                  Pos {fmtK(bal)}
                </div>
              </div>
              <div className="flex items-end gap-0.5 w-full">
                <div
                  className={`flex-1 rounded-t ${scenario === "best" ? "bg-green-400" : "bg-yellow-400"}`}
                  style={{ height: inH }}
                />
                <div className="flex-1 bg-red-300 rounded-t" style={{ height: outH }} />
              </div>
              {/* Balance dot */}
              <div className={`w-1.5 h-1.5 rounded-full ${bal >= 0 ? "bg-green-500" : "bg-red-500"}`} />
            </div>
          );
        })}
      </div>
      <div className="flex gap-1 overflow-x-auto">
        {weeks.map((w) => (
          <div key={w.label} className="min-w-[40px] flex-1 text-center text-[9px] text-gray-400 leading-tight">
            {w.label}
          </div>
        ))}
      </div>
      <div className="flex items-center gap-4 text-xs text-gray-500">
        <span className="flex items-center gap-1.5">
          <span className={`inline-block w-3 h-2.5 rounded-sm ${scenario === "best" ? "bg-green-400" : "bg-yellow-400"}`} />
          Inflows
        </span>
        <span className="flex items-center gap-1.5">
          <span className="inline-block w-3 h-2.5 rounded-sm bg-red-300" />
          Outflows
        </span>
        <span className="flex items-center gap-1.5">
          <span className="inline-block w-1.5 h-1.5 rounded-full bg-green-500" />/<span className="inline-block w-1.5 h-1.5 rounded-full bg-red-500" />
          Net position
        </span>
      </div>
    </div>
  );
}

// ── Balance Sparkline ─────────────────────────────────────────────────────────

function BalanceSparkline({ bestSeries, worstSeries }: { bestSeries: DayPoint[]; worstSeries: DayPoint[] }) {
  const all = [...bestSeries.map((d) => d.balance), ...worstSeries.map((d) => d.balance)];
  const minVal = Math.min(...all, 0);
  const maxVal = Math.max(...all, 1);
  const range = maxVal - minVal || 1;
  const W = 400;
  const H = 60;
  const n = bestSeries.length;

  const toY = (v: number) => H - ((v - minVal) / range) * H;
  const toX = (i: number) => (i / Math.max(n - 1, 1)) * W;

  const bestPath = bestSeries.map((d, i) => `${i === 0 ? "M" : "L"}${toX(i).toFixed(1)},${toY(d.balance).toFixed(1)}`).join(" ");
  const worstPath = worstSeries.map((d, i) => `${i === 0 ? "M" : "L"}${toX(i).toFixed(1)},${toY(d.balance).toFixed(1)}`).join(" ");
  const zeroY = toY(0);

  return (
    <div className="overflow-hidden rounded">
      <svg viewBox={`0 0 ${W} ${H}`} className="w-full h-16" preserveAspectRatio="none">
        {/* Zero line */}
        <line x1="0" y1={zeroY} x2={W} y2={zeroY} stroke="#e5e7eb" strokeWidth="1" strokeDasharray="4 2" />
        {/* Worst case (orange) */}
        <path d={worstPath} fill="none" stroke="#f97316" strokeWidth="1.5" opacity="0.5" />
        {/* Best case (blue) */}
        <path d={bestPath} fill="none" stroke="#3b82f6" strokeWidth="2" />
      </svg>
      <div className="flex items-center gap-4 text-[10px] text-gray-400 mt-1">
        <span className="flex items-center gap-1"><span className="inline-block w-4 h-0.5 bg-blue-500" />Best case</span>
        <span className="flex items-center gap-1"><span className="inline-block w-4 h-0.5 bg-orange-400 opacity-60" />Worst case</span>
      </div>
    </div>
  );
}

// ── Summary cards ─────────────────────────────────────────────────────────────

function SummaryCard({ label, best, worst, invert }: { label: string; best: number; worst: number; invert?: boolean }) {
  return (
    <div className="bg-white border rounded-xl p-4 space-y-1">
      <p className="text-xs font-medium text-gray-400 uppercase tracking-wide">{label}</p>
      <div className="flex items-end gap-2">
        <p className={`text-xl font-bold ${invert ? (best < 0 ? "text-red-500" : "text-green-600") : "text-[var(--vf-text-primary)]"}`}>
          {fmt(best)}
        </p>
        <span className="text-xs text-gray-300 pb-0.5">SEK</span>
      </div>
      {worst !== best && (
        <p className="text-xs text-gray-400">Worst: {fmt(worst)} SEK</p>
      )}
    </div>
  );
}

// ── Page ──────────────────────────────────────────────────────────────────────

export default function CashFlowPage() {
  const [data, setData] = useState<CashFlowData | null>(null);
  const [loading, setLoading] = useState(true);
  const [horizon, setHorizon] = useState(90);
  const [scenario, setScenario] = useState<"best" | "worst">("best");

  // Adjustments form
  const [adjDate, setAdjDate] = useState("");
  const [adjLabel, setAdjLabel] = useState("");
  const [adjAmount, setAdjAmount] = useState("");
  const [adjNote, setAdjNote] = useState("");
  const [adjSaving, setAdjSaving] = useState(false);
  const [adjOpen, setAdjOpen] = useState(false);

  // Item breakdown expand
  const [expandedSource, setExpandedSource] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const d = await api.get<CashFlowData>(`/api/reports/cashflow?horizon=${horizon}`);
      // Convert string numbers to numbers
      const parse = (s: DayPoint[]) =>
        s.map((p) => ({
          ...p,
          inflows: Number(p.inflows),
          outflows: Number(p.outflows),
          net: Number(p.net),
          balance: Number(p.balance),
        }));
      d.best_case = parse(d.best_case);
      d.worst_case = parse(d.worst_case);
      d.items = d.items.map((i) => ({ ...i, amount: Number(i.amount) }));
      d.adjustments = d.adjustments.map((a) => ({ ...a, amount: Number(a.amount) }));
      setData(d);
    } catch {
      toast.error("Failed to load cash flow forecast");
    } finally {
      setLoading(false);
    }
  }, [horizon]);

  useEffect(() => { load(); }, [load]);

  async function addAdjustment() {
    if (!adjDate || !adjLabel || !adjAmount) { toast.error("Fill in date, label, and amount"); return; }
    setAdjSaving(true);
    try {
      await api.post("/api/reports/cashflow/adjustments", {
        adjustment_date: adjDate,
        label: adjLabel,
        amount: Number(adjAmount),
        note: adjNote || null,
      });
      setAdjDate(""); setAdjLabel(""); setAdjAmount(""); setAdjNote("");
      setAdjOpen(false);
      await load();
      toast.success("Adjustment added");
    } catch {
      toast.error("Failed to add adjustment");
    } finally {
      setAdjSaving(false);
    }
  }

  async function deleteAdjustment(id: string) {
    try {
      await api.delete(`/api/reports/cashflow/adjustments/${id}`);
      await load();
      toast.success("Removed");
    } catch {
      toast.error("Failed to remove adjustment");
    }
  }

  // Derived
  const series = data ? (scenario === "best" ? data.best_case : data.worst_case) : [];
  const lastBalance = series.at(-1)?.balance ?? 0;
  const totalInflows = series.reduce((s, d) => s + d.inflows, 0);
  const totalOutflows = series.reduce((s, d) => s + d.outflows, 0);

  const bestLastBalance = data?.best_case.at(-1)?.balance ?? 0;
  const worstLastBalance = data?.worst_case.at(-1)?.balance ?? 0;
  const bestTotalInflows = data?.best_case.reduce((s, d) => s + d.inflows, 0) ?? 0;
  const worstTotalInflows = data?.worst_case.reduce((s, d) => s + d.inflows, 0) ?? 0;
  const bestTotalOutflows = data?.best_case.reduce((s, d) => s + d.outflows, 0) ?? 0;
  const worstTotalOutflows = data?.worst_case.reduce((s, d) => s + d.outflows, 0) ?? 0;

  const negDates = scenario === "best" ? (data?.best_negative_dates ?? []) : (data?.worst_negative_dates ?? []);

  // Group items by source
  const bySource = (data?.items ?? []).reduce<Record<string, CashFlowItem[]>>((acc, it) => {
    (acc[it.source] ??= []).push(it);
    return acc;
  }, {});

  return (
    <div className="p-6 space-y-6 max-w-5xl">
      {/* Header */}
      <div className="flex items-start justify-between gap-4 flex-wrap">
        <div className="flex items-center gap-3">
          <BarChart3 size={22} className="text-[var(--vf-text-primary)]" />
          <div>
            <h1 className="text-xl font-bold text-[var(--vf-text-primary)]">Cash Flow Forecast</h1>
            {data && (
              <p className="text-sm text-gray-400 mt-0.5">
                Next {horizon} days · {data.items.length} items
              </p>
            )}
          </div>
        </div>

        {/* Horizon + scenario selectors */}
        <div className="flex gap-2 flex-wrap">
          <div className={styles.periodSelector}>
            {([30, 60, 90] as const).map((h) => (
              <button
                key={h}
                onClick={() => setHorizon(h)}
                className={`${styles.periodBtn} ${horizon === h ? styles.periodBtnActive : ""}`}
              >
                {h}d
              </button>
            ))}
          </div>
          <div className={styles.periodSelector}>
            {(["best", "worst"] as const).map((s) => (
              <button
                key={s}
                onClick={() => setScenario(s)}
                className={`${styles.periodBtn} ${scenario === s ? styles.periodBtnActive : ""} capitalize`}
              >
                {s === "best" ? "Best case" : "Worst case"}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Alert banner */}
      {negDates.length > 0 && (
        <div className="flex items-start gap-3 bg-red-50 border border-red-200 rounded-xl p-4">
          <AlertTriangle size={18} className="text-red-500 mt-0.5 flex-shrink-0" />
          <div>
            <p className="text-sm font-semibold text-red-700">Projected negative balance</p>
            <p className="text-xs text-red-600 mt-0.5">
              {scenario === "best" ? "Best-case" : "Worst-case"} scenario shows negative cash position on{" "}
              {negDates.length} day{negDates.length > 1 ? "s" : ""}.
              First occurrence: {negDates[0]}.
            </p>
          </div>
        </div>
      )}

      {/* Loading skeleton */}
      {loading && !data && (
        <div className="grid grid-cols-3 gap-4">
          {[1, 2, 3].map((i) => <div key={i} className="h-24 rounded-xl bg-gray-100 animate-pulse" />)}
        </div>
      )}

      {data && (
        <>
          {/* Summary KPIs */}
          <div className={styles.kpiGrid}>
            <SummaryCard label="Expected inflows" best={bestTotalInflows} worst={worstTotalInflows} />
            <SummaryCard label="Expected outflows" best={bestTotalOutflows} worst={worstTotalOutflows} />
            <SummaryCard
              label="Net position"
              best={bestLastBalance}
              worst={worstLastBalance}
              invert
            />
          </div>

          {/* Balance trend (both scenarios) */}
          <div className={styles.chartCard}>
            <p className="text-sm font-semibold text-gray-700 mb-4">
              Cumulative cash position — {horizon}-day horizon
            </p>
            <BalanceSparkline bestSeries={data.best_case} worstSeries={data.worst_case} />
          </div>

          {/* Weekly bar chart */}
          <div className="bg-white border rounded-xl p-5">
            <div className="flex items-center justify-between mb-4">
              <p className="text-sm font-semibold text-gray-700">Weekly inflows vs outflows</p>
              <span className={`text-xs px-2 py-0.5 rounded font-medium ${
                scenario === "best" ? "bg-green-100 text-green-700" : "bg-yellow-100 text-yellow-700"
              }`}>
                {scenario === "best" ? "Best case" : "Worst case"}
              </span>
            </div>
            <CashChart series={scenario === "best" ? data.best_case : data.worst_case} scenario={scenario} />
          </div>

          {/* Source breakdown */}
          <div className="bg-white border rounded-xl p-5 space-y-3">
            <p className="text-sm font-semibold text-gray-700">Breakdown by source</p>
            {Object.entries(bySource).map(([source, items]) => {
              const totalAmt = items.reduce((s, i) => s + i.amount, 0);
              const isExpanded = expandedSource === source;
              return (
                <div key={source} className="border rounded-lg overflow-hidden">
                  <button
                    onClick={() => setExpandedSource(isExpanded ? null : source)}
                    className="w-full flex items-center justify-between px-4 py-3 hover:bg-gray-50 transition-colors"
                  >
                    <div className="flex items-center gap-3">
                      <span className={`text-xs font-medium px-2 py-0.5 rounded ${SOURCE_COLOR[source] ?? "bg-gray-100 text-gray-700"}`}>
                        {SOURCE_LABELS[source] ?? source}
                      </span>
                      <span className="text-xs text-gray-400">{items.length} item{items.length !== 1 ? "s" : ""}</span>
                    </div>
                    <div className="flex items-center gap-2">
                      <span className={`text-sm font-mono font-semibold ${totalAmt >= 0 ? "text-green-600" : "text-red-500"}`}>
                        {totalAmt >= 0 ? "+" : ""}{fmt(totalAmt)} SEK
                      </span>
                      <ChevronRight size={14} className={`text-gray-400 transition-transform ${isExpanded ? "rotate-90" : ""}`} />
                    </div>
                  </button>
                  {isExpanded && (
                    <div className="border-t divide-y">
                      {items.map((item) => (
                        <div key={item.id} className="px-4 py-2 flex items-center justify-between text-sm">
                          <div>
                            <p className="text-gray-700 text-xs">{item.label}</p>
                            <p className="text-[10px] text-gray-400 mt-0.5">
                              Best: {item.best_date}
                              {item.best_date !== item.worst_date && ` · Worst: ${item.worst_date}`}
                            </p>
                          </div>
                          <span className={`font-mono text-xs font-semibold ${item.amount >= 0 ? "text-green-600" : "text-red-500"}`}>
                            {item.amount >= 0 ? "+" : ""}{fmt(item.amount)} SEK
                          </span>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              );
            })}
          </div>

          {/* Manual adjustments */}
          <div className="bg-white border rounded-xl p-5 space-y-4">
            <div className="flex items-center justify-between">
              <p className="text-sm font-semibold text-gray-700">Manual adjustments</p>
              <button
                onClick={() => setAdjOpen(!adjOpen)}
                className="flex items-center gap-1.5 px-3 py-1.5 bg-[var(--vf-brand-primary)] text-white rounded text-xs hover:opacity-90"
              >
                <Plus size={13} /> Add
              </button>
            </div>

            {adjOpen && (
              <div className="bg-gray-50 rounded-lg p-4 space-y-3">
                <p className="text-xs font-medium text-gray-500">
                  Positive amount = expected inflow, negative = expected outflow
                </p>
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="block text-xs text-gray-400 mb-1">Date</label>
                    <input
                      type="date"
                      value={adjDate}
                      onChange={(e) => setAdjDate(e.target.value)}
                      className="w-full border rounded px-2 py-1.5 text-sm focus:outline-none"
                    />
                  </div>
                  <div>
                    <label className="block text-xs text-gray-400 mb-1">Amount (SEK)</label>
                    <input
                      type="number"
                      placeholder="e.g. 50000 or -20000"
                      value={adjAmount}
                      onChange={(e) => setAdjAmount(e.target.value)}
                      className="w-full border rounded px-2 py-1.5 text-sm focus:outline-none"
                    />
                  </div>
                </div>
                <div>
                  <label className="block text-xs text-gray-400 mb-1">Label</label>
                  <input
                    type="text"
                    placeholder="e.g. Client X paying late"
                    value={adjLabel}
                    onChange={(e) => setAdjLabel(e.target.value)}
                    className="w-full border rounded px-2 py-1.5 text-sm focus:outline-none"
                  />
                </div>
                <div>
                  <label className="block text-xs text-gray-400 mb-1">Note (optional)</label>
                  <input
                    type="text"
                    placeholder="Additional context"
                    value={adjNote}
                    onChange={(e) => setAdjNote(e.target.value)}
                    className="w-full border rounded px-2 py-1.5 text-sm focus:outline-none"
                  />
                </div>
                <div className="flex gap-2 justify-end">
                  <button onClick={() => setAdjOpen(false)} className="px-3 py-1.5 border rounded text-sm">Cancel</button>
                  <button
                    onClick={addAdjustment}
                    disabled={adjSaving}
                    className="px-4 py-1.5 bg-[var(--vf-brand-primary)] text-white rounded text-sm disabled:opacity-50"
                  >
                    {adjSaving ? "Saving…" : "Save"}
                  </button>
                </div>
              </div>
            )}

            {data.adjustments.length === 0 ? (
              <p className="text-xs text-gray-400 text-center py-2">
                No manual adjustments yet. Add one to account for known timing changes.
              </p>
            ) : (
              <div className="divide-y border rounded-lg overflow-hidden">
                {data.adjustments.map((adj) => (
                  <div key={adj.id} className="flex items-center justify-between px-4 py-3">
                    <div>
                      <p className="text-sm font-medium text-gray-700">{adj.label}</p>
                      <p className="text-xs text-gray-400">{adj.adjustment_date}{adj.note ? ` · ${adj.note}` : ""}</p>
                    </div>
                    <div className="flex items-center gap-3">
                      <span className={`font-mono text-sm font-semibold ${adj.amount >= 0 ? "text-green-600" : "text-red-500"}`}>
                        {adj.amount >= 0 ? "+" : ""}{fmt(adj.amount)} SEK
                      </span>
                      <button onClick={() => deleteAdjustment(adj.id)} className="text-gray-300 hover:text-red-500">
                        <Trash2 size={14} />
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Upcoming high-impact days table */}
          {series.filter((d) => Math.abs(d.net) > 0).length > 0 && (
            <div className="bg-white border rounded-xl p-5">
              <p className="text-sm font-semibold text-gray-700 mb-4">
                Top cash movement days ({scenario === "best" ? "best" : "worst"} case)
              </p>
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-xs text-gray-400 border-b">
                    <th className="text-left py-2 font-medium">Date</th>
                    <th className="text-right py-2 font-medium">Inflows</th>
                    <th className="text-right py-2 font-medium">Outflows</th>
                    <th className="text-right py-2 font-medium">Net</th>
                    <th className="text-right py-2 font-medium">Running balance</th>
                  </tr>
                </thead>
                <tbody>
                  {series
                    .filter((d) => Math.abs(d.net) > 0)
                    .sort((a, b) => Math.abs(b.net) - Math.abs(a.net))
                    .slice(0, 15)
                    .map((d) => (
                      <tr key={d.date} className="border-b last:border-0 hover:bg-gray-50">
                        <td className="py-2 text-gray-600">{d.date}</td>
                        <td className="py-2 text-right text-green-600 font-mono">
                          {d.inflows > 0 ? `+${fmt(d.inflows)}` : "—"}
                        </td>
                        <td className="py-2 text-right text-red-500 font-mono">
                          {d.outflows > 0 ? `(${fmt(d.outflows)})` : "—"}
                        </td>
                        <td className={`py-2 text-right font-mono font-semibold ${d.net >= 0 ? "text-green-600" : "text-red-500"}`}>
                          {fmt(d.net)}
                        </td>
                        <td className={`py-2 text-right font-mono ${d.balance >= 0 ? "text-gray-700" : "text-red-500 font-semibold"}`}>
                          {fmt(d.balance)}
                        </td>
                      </tr>
                    ))}
                </tbody>
              </table>
            </div>
          )}
        </>
      )}
    </div>
  );
}
