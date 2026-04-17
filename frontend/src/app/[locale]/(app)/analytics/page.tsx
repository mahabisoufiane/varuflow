"use client";

import { api } from "@/lib/api-client";
import { createClient } from "@/lib/supabase/client";
import { useEffect, useState, useCallback } from "react";
import { Link } from "@/i18n/navigation";
import {
  AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
  BarChart, Bar, PieChart, Pie, Cell,
} from "recharts";
import { cn } from "@/lib/utils";
import { ArrowRight, Package, TrendingUp, AlertTriangle, Users, Download, ShoppingBag, CheckCircle2 } from "lucide-react";
import { useMoney } from "@/hooks/useMoney";

// Tooltip helpers need a non-hook fmt — Intl auto-picks the user's locale.
const fmt = (n: number) =>
  n.toLocaleString(typeof navigator !== "undefined" ? navigator.language : "en", { minimumFractionDigits: 0 });

interface RevenuePoint { month: string; invoiced: number; collected: number; }
interface TopCustomer { customer_id: string; company_name: string; total_invoiced: number; invoice_count: number; }
interface TopProduct { product_id: string | null; description: string; revenue: number; quantity_sold: number; }
interface StatusBucket { status: string; count: number; total: number; }
interface Analytics {
  from_date: string; to_date: string;
  revenue_points: RevenuePoint[];
  top_customers: TopCustomer[];
  top_products: TopProduct[];
  status_breakdown: StatusBucket[];
  inventory: { total_products: number; total_stock_value: number; low_stock_count: number; warehouse_count: number; };
  overdue: { overdue_count: number; overdue_total: number; oldest_days: number; };
}

function fmtMonth(m: string) {
  const [y, mo] = m.split("-");
  return new Date(Number(y), Number(mo) - 1).toLocaleString("en", { month: "short" });
}

const STATUS_COLORS: Record<string, string> = {
  PAID: "#10b981", SENT: "#6366f1", OVERDUE: "#ef4444", DRAFT: "#94a3b8",
};

function defaultRange() {
  const to = new Date();
  const from = new Date(to);
  from.setMonth(from.getMonth() - 11);
  from.setDate(1);
  return { from: from.toISOString().slice(0, 10), to: to.toISOString().slice(0, 10) };
}

/** Read a CSS variable from :root at runtime — works for both dark and light mode. */
function cssVar(name: string): string {
  if (typeof window === "undefined") return "";
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
}

/** Custom tooltip that reads CSS vars at paint time — always matches the theme. */
function ChartTooltip({ active, payload, label }: {
  active?: boolean;
  payload?: { name: string; value: number; color: string }[];
  label?: string;
}) {
  if (!active || !payload?.length) return null;
  return (
    <div className="vf-section px-3 py-2.5 text-sm shadow-elevated" style={{ minWidth: 160 }}>
      {label && <p className="text-xs vf-text-m font-medium mb-1.5">{label}</p>}
      {payload.map((p) => (
        <div key={p.name} className="flex items-center justify-between gap-4">
          <div className="flex items-center gap-1.5">
            <span className="h-2 w-2 rounded-full shrink-0" style={{ backgroundColor: p.color }} />
            <span className="vf-text-m text-xs">{p.name}</span>
          </div>
          <span className="font-mono font-semibold vf-text-1 text-xs">{fmt(p.value)}</span>
        </div>
      ))}
    </div>
  );
}

function PieTooltip({ active, payload }: {
  active?: boolean;
  payload?: { name: string; value: number; payload: { total: number } }[];
}) {
  if (!active || !payload?.length) return null;
  const p = payload[0];
  return (
    <div className="vf-section px-3 py-2 text-sm shadow-elevated">
      <p className="font-semibold vf-text-1 text-xs">{p.name}</p>
      <p className="vf-text-m text-xs">{p.value} invoices</p>
      <p className="font-mono vf-text-2 text-xs">{fmt(p.payload.total)}</p>
    </div>
  );
}

export default function AnalyticsPage() {
  const { fmt, code: currencyCode } = useMoney();
  const [data, setData]         = useState<Analytics | null>(null);
  const [loading, setLoading]   = useState(true);
  const [error, setError]       = useState<string | null>(null);
  const [exporting, setExporting] = useState(false);
  const [fromDate, setFromDate] = useState("");
  const [toDate, setToDate]     = useState("");

  const load = useCallback((from: string, to: string) => {
    setLoading(true); setError(null);
    api.get<Analytics>(`/api/analytics/overview?from_date=${from}&to_date=${to}`)
      .then(setData).catch((e) => setError(e.message)).finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    const { from, to } = defaultRange();
    setFromDate(from); setToDate(to); load(from, to);
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  async function handleExport() {
    setExporting(true);
    try {
      const url = `${process.env.NEXT_PUBLIC_API_URL}/api/analytics/export/pdf?from_date=${fromDate}&to_date=${toDate}`;
      const supabase = createClient();
      const { data: { session } } = await supabase.auth.getSession();
      const res = await fetch(url, { headers: session ? { Authorization: `Bearer ${session.access_token}` } : {} });
      const blob = await res.blob();
      const a = document.createElement("a");
      a.href = URL.createObjectURL(blob);
      a.download = `analytics-${fromDate}-${toDate}.pdf`;
      a.click();
      URL.revokeObjectURL(a.href);
    } finally { setExporting(false); }
  }

  if (loading) return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div className="space-y-2">
          <div className="h-7 w-32 skeleton rounded-lg" />
          <div className="h-4 w-48 skeleton rounded" />
        </div>
        <div className="flex gap-2">
          <div className="h-9 w-28 skeleton rounded-lg" />
          <div className="h-9 w-28 skeleton rounded-lg" />
        </div>
      </div>
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {[1,2,3,4].map(i => <div key={i} className="h-24 skeleton rounded-xl" />)}
      </div>
      <div className="h-72 skeleton rounded-xl" />
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {[1,2].map(i => <div key={i} className="h-64 skeleton rounded-xl" />)}
      </div>
    </div>
  );

  if (error) return (
    <div className="rounded-xl px-5 py-4 text-sm text-red-400"
      style={{ background: "rgba(239,68,68,0.08)", border: "1px solid rgba(239,68,68,0.2)" }}>
      {error}
    </div>
  );
  if (!data) return null;

  const chartData = data.revenue_points.map((p) => ({
    month: fmtMonth(p.month),
    Invoiced: Number(p.invoiced),
    Collected: Number(p.collected),
  }));

  const totalInvoiced  = data.revenue_points.reduce((s, p) => s + Number(p.invoiced), 0);
  const totalCollected = data.revenue_points.reduce((s, p) => s + Number(p.collected), 0);
  const collectionRate = totalInvoiced > 0 ? Math.round((totalCollected / totalInvoiced) * 100) : 0;

  const pieData = data.status_breakdown.map((b) => ({
    name: b.status, value: b.count, total: Number(b.total),
  }));
  const barData = data.top_products.slice(0, 8).map((p) => ({
    name: p.description.length > 26 ? p.description.slice(0, 24) + "…" : p.description,
    Revenue: Number(p.revenue),
  })).reverse();

  const kpis = [
    {
      label: "Invoiced",
      value: `${fmt(totalInvoiced)} SEK`,
      icon: TrendingUp,
      color: "#6366f1",
      bg: "rgba(99,102,241,0.10)",
      border: "rgba(99,102,241,0.20)",
    },
    {
      label: "Collected",
      value: `${fmt(totalCollected)} SEK`,
      icon: TrendingUp,
      color: "#10b981",
      bg: "rgba(16,185,129,0.10)",
      border: "rgba(16,185,129,0.20)",
    },
    {
      label: "Collection rate",
      value: `${collectionRate}%`,
      icon: TrendingUp,
      color: collectionRate >= 80 ? "#10b981" : "#f59e0b",
      bg: collectionRate >= 80 ? "rgba(16,185,129,0.10)" : "rgba(245,158,11,0.10)",
      border: collectionRate >= 80 ? "rgba(16,185,129,0.20)" : "rgba(245,158,11,0.20)",
    },
    {
      label: "Overdue",
      value: `${fmt(Number(data.overdue.overdue_total))} SEK`,
      icon: AlertTriangle,
      color: data.overdue.overdue_total > 0 ? "#ef4444" : "#64748b",
      bg: data.overdue.overdue_total > 0 ? "rgba(239,68,68,0.10)" : "var(--vf-bg-elevated)",
      border: data.overdue.overdue_total > 0 ? "rgba(239,68,68,0.20)" : "var(--vf-border)",
    },
  ];

  return (
    <div className="space-y-6">

      {/* ── Header + date range ─────────────────────────────────────────── */}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-xl font-bold vf-text-1">Analytics</h1>
          <p className="text-xs vf-text-m mt-0.5">{data.from_date} – {data.to_date}</p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <input type="date" value={fromDate} onChange={(e) => setFromDate(e.target.value)}
            className="vf-input w-auto text-xs" style={{ height: 36 }} />
          <span className="text-xs vf-text-m">to</span>
          <input type="date" value={toDate} onChange={(e) => setToDate(e.target.value)}
            className="vf-input w-auto text-xs" style={{ height: 36 }} />
          <button onClick={() => load(fromDate, toDate)} className="vf-btn text-xs px-4 h-9">Apply</button>
          <button onClick={handleExport} disabled={exporting}
            className="vf-btn-ghost text-xs px-4 h-9 disabled:opacity-60">
            <Download className="h-3.5 w-3.5" />
            {exporting ? "Exporting…" : "PDF"}
          </button>
        </div>
      </div>

      {/* ── KPI row ──────────────────────────────────────────────────────── */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {kpis.map(({ label, value, icon: Icon, color, bg, border }) => (
          <div key={label} className="rounded-xl p-5 transition-all"
            style={{ background: bg, border: `1px solid ${border}` }}>
            <div className="flex items-center gap-2 mb-3">
              <span className="inline-flex h-8 w-8 items-center justify-center rounded-lg"
                style={{ background: `${color}18` }}>
                <Icon className="h-4 w-4" style={{ color }} />
              </span>
              <span className="text-[10px] font-semibold vf-text-m uppercase tracking-wider">{label}</span>
            </div>
            <p className="text-xl font-bold tabular-nums" style={{ color }}>{value}</p>
          </div>
        ))}
      </div>

      {/* ── Revenue area chart ───────────────────────────────────────────── */}
      <div className="vf-section p-6">
        <div className="flex items-center justify-between mb-6">
          <h2 className="font-semibold vf-text-1">Revenue — Invoiced vs Collected</h2>
          <div className="flex items-center gap-4 text-xs vf-text-m">
            <span className="flex items-center gap-1.5">
              <span className="inline-block h-2.5 w-2.5 rounded-full bg-indigo-500" />Invoiced
            </span>
            <span className="flex items-center gap-1.5">
              <span className="inline-block h-2.5 w-2.5 rounded-full bg-emerald-500" />Collected
            </span>
          </div>
        </div>
        <ResponsiveContainer width="100%" height={240}>
          <AreaChart data={chartData} margin={{ top: 4, right: 8, left: 0, bottom: 0 }}>
            <defs>
              <linearGradient id="gInvoiced" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%"  stopColor="#6366f1" stopOpacity={0.3} />
                <stop offset="95%" stopColor="#6366f1" stopOpacity={0} />
              </linearGradient>
              <linearGradient id="gCollected" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%"  stopColor="#10b981" stopOpacity={0.3} />
                <stop offset="95%" stopColor="#10b981" stopOpacity={0} />
              </linearGradient>
            </defs>
            <CartesianGrid strokeDasharray="3 3" stroke="var(--chart-grid)" />
            <XAxis dataKey="month"
              tick={{ fontSize: 11, fill: "var(--chart-tick)" }}
              axisLine={false} tickLine={false} />
            <YAxis
              tick={{ fontSize: 11, fill: "var(--chart-tick)" }}
              tickFormatter={(v) => `${(v / 1000).toFixed(0)}k`}
              axisLine={false} tickLine={false} />
            <Tooltip content={<ChartTooltip />} />
            <Area type="monotone" dataKey="Invoiced"  stroke="#6366f1" fill="url(#gInvoiced)"  strokeWidth={2} dot={false} />
            <Area type="monotone" dataKey="Collected" stroke="#10b981" fill="url(#gCollected)" strokeWidth={2} dot={false} />
          </AreaChart>
        </ResponsiveContainer>
      </div>

      {/* ── Pie + top customers ──────────────────────────────────────────── */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">

        {/* Invoice status donut */}
        <div className="vf-section p-6">
          <h2 className="font-semibold vf-text-1 mb-5 flex items-center gap-2">
            <TrendingUp className="h-4 w-4 text-indigo-400" />Invoice status
          </h2>
          {pieData.length === 0 ? (
            <div className="py-10 text-center">
              <p className="text-sm vf-text-m">No invoices in range</p>
            </div>
          ) : (
            <div className="flex items-center gap-6">
              <ResponsiveContainer width="50%" height={180}>
                <PieChart>
                  <Pie data={pieData} cx="50%" cy="50%" innerRadius={48} outerRadius={76}
                    paddingAngle={3} dataKey="value" strokeWidth={0}>
                    {pieData.map((entry) => (
                      <Cell key={entry.name} fill={STATUS_COLORS[entry.name] ?? "#94a3b8"} />
                    ))}
                  </Pie>
                  <Tooltip content={<PieTooltip />} />
                </PieChart>
              </ResponsiveContainer>
              <div className="flex-1 space-y-2.5">
                {pieData.map((b) => (
                  <div key={b.name} className="flex items-center justify-between">
                    <div className="flex items-center gap-2 text-sm">
                      <div className="h-2.5 w-2.5 rounded-full shrink-0"
                        style={{ backgroundColor: STATUS_COLORS[b.name] ?? "#94a3b8" }} />
                      <span className="vf-text-2 text-xs font-medium">{b.name}</span>
                    </div>
                    <span className="font-bold vf-text-1 text-sm tabular-nums">{b.value}</span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>

        {/* Top customers */}
        <div className="vf-section p-6">
          <div className="flex items-center justify-between mb-5">
            <h2 className="font-semibold vf-text-1 flex items-center gap-2">
              <Users className="h-4 w-4 text-indigo-400" />Top customers
            </h2>
            <Link href="/customers" className="text-xs vf-text-m hover:vf-text-2 transition-colors flex items-center gap-1">
              View all <ArrowRight className="h-3 w-3" />
            </Link>
          </div>
          {data.top_customers.length === 0 ? (
            <div className="py-8 text-center">
              <p className="text-sm vf-text-m">No data in range</p>
            </div>
          ) : (
            <div className="space-y-4">
              {data.top_customers.map((c, idx) => {
                const pct = Math.round((Number(c.total_invoiced) / (Number(data.top_customers[0].total_invoiced) || 1)) * 100);
                return (
                  <div key={c.customer_id}>
                    <div className="flex justify-between items-baseline text-sm mb-1.5">
                      <div className="flex items-center gap-2 min-w-0">
                        <span className="text-[10px] font-bold vf-text-m tabular-nums w-4 shrink-0">
                          {idx + 1}
                        </span>
                        <span className="font-medium vf-text-1 truncate max-w-[160px]">{c.company_name}</span>
                      </div>
                      <span className="font-mono text-xs vf-text-m shrink-0 ml-2">
                        {fmt(Number(c.total_invoiced))} SEK
                      </span>
                    </div>
                    <div className="h-1.5 rounded-full overflow-hidden" style={{ background: "var(--vf-bg-elevated)" }}>
                      <div className="h-1.5 rounded-full bg-indigo-500 transition-all duration-500"
                        style={{ width: `${pct}%` }} />
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </div>

      {/* ── Top products bar chart ───────────────────────────────────────── */}
      {data.top_products.length > 0 && (
        <div className="vf-section p-6">
          <h2 className="font-semibold vf-text-1 mb-6 flex items-center gap-2">
            <ShoppingBag className="h-4 w-4 text-emerald-400" />Top products by revenue ({currencyCode})
          </h2>
          <ResponsiveContainer width="100%" height={Math.max(200, barData.length * 38)}>
            <BarChart data={barData} layout="vertical" margin={{ top: 0, right: 48, left: 8, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--chart-grid)" horizontal={false} />
              <XAxis type="number"
                tick={{ fontSize: 11, fill: "var(--chart-tick)" }}
                tickFormatter={(v) => `${(v / 1000).toFixed(0)}k`}
                axisLine={false} tickLine={false} />
              <YAxis type="category" dataKey="name"
                tick={{ fontSize: 11, fill: "var(--chart-tick)" }}
                width={150} axisLine={false} tickLine={false} />
              <Tooltip
                formatter={(v) => [`${fmt(Number(v))} SEK`, "Revenue"]}
                contentStyle={{
                  background: "var(--vf-bg-surface)",
                  border: "1px solid var(--vf-border)",
                  borderRadius: 10,
                  color: "var(--vf-text-primary)",
                  fontSize: 12,
                }}
              />
              <Bar dataKey="Revenue" fill="#6366f1" radius={[0, 6, 6, 0]} maxBarSize={20} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}

      {/* ── Inventory + overdue ──────────────────────────────────────────── */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">

        {/* Inventory summary */}
        <div className="vf-section p-6">
          <h2 className="font-semibold vf-text-1 flex items-center gap-2 mb-4">
            <Package className="h-4 w-4 text-indigo-400" />Inventory snapshot
          </h2>
          <div className="grid grid-cols-2 gap-3">
            {[
              { label: "Products",    value: data.inventory.total_products,  color: "#6366f1" },
              { label: "Warehouses",  value: data.inventory.warehouse_count, color: "#8b5cf6" },
              { label: "Low stock",   value: data.inventory.low_stock_count, color: data.inventory.low_stock_count > 0 ? "#f59e0b" : "#10b981" },
              { label: "Stock value", value: `${fmt(Number(data.inventory.total_stock_value))} SEK`, color: "#10b981" },
            ].map(({ label, value, color }) => (
              <div key={label} className="vf-stat-tile">
                <p className="text-[10px] vf-text-m font-medium uppercase tracking-wide mb-1">{label}</p>
                <p className="font-bold text-[15px] tabular-nums" style={{ color }}>{value}</p>
              </div>
            ))}
          </div>
        </div>

        {/* Overdue receivables */}
        <div className="vf-section p-6">
          <h2 className="font-semibold vf-text-1 flex items-center gap-2 mb-4">
            <AlertTriangle className={cn("h-4 w-4", data.overdue.overdue_count > 0 ? "text-red-400" : "text-emerald-400")} />
            Overdue receivables
          </h2>
          {data.overdue.overdue_count === 0 ? (
            <div className="flex flex-col items-center justify-center py-6 gap-2">
              <div className="flex h-12 w-12 items-center justify-center rounded-full bg-emerald-500/10">
                <CheckCircle2 className="h-6 w-6 text-emerald-400" />
              </div>
              <p className="text-sm font-semibold vf-text-2">No overdue invoices</p>
              <p className="text-xs vf-text-m">All payments are on track</p>
            </div>
          ) : (
            <div className="space-y-3">
              {[
                { label: "Overdue count",  value: String(data.overdue.overdue_count),               cls: "vf-text-1" },
                { label: "Total overdue",  value: `${fmt(Number(data.overdue.overdue_total))} SEK`,  cls: "text-red-400" },
                { label: "Oldest overdue", value: `${data.overdue.oldest_days} days`,                cls: "vf-text-1" },
              ].map(({ label, value, cls }) => (
                <div key={label} className="flex items-center justify-between py-2"
                  style={{ borderBottom: "1px solid var(--vf-divider)" }}>
                  <span className="text-sm vf-text-m">{label}</span>
                  <span className={cn("text-sm font-semibold tabular-nums", cls)}>{value}</span>
                </div>
              ))}
              <Link href="/invoices?status=OVERDUE"
                className="mt-2 inline-flex items-center gap-1.5 text-xs font-medium text-red-400 hover:text-red-300 transition-colors">
                View overdue invoices <ArrowRight className="h-3 w-3" />
              </Link>
            </div>
          )}
        </div>
      </div>

    </div>
  );
}
