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
import { ArrowRight, Package, TrendingUp, AlertTriangle, Users, Download, ShoppingBag } from "lucide-react";

interface RevenuePoint { month: string; invoiced: number; collected: number; }
interface TopCustomer { customer_id: string; company_name: string; total_invoiced: number; invoice_count: number; }
interface TopProduct { product_id: string | null; description: string; revenue: number; quantity_sold: number; }
interface StatusBucket { status: string; count: number; total: number; }
interface Analytics {
  from_date: string;
  to_date: string;
  revenue_points: RevenuePoint[];
  top_customers: TopCustomer[];
  top_products: TopProduct[];
  status_breakdown: StatusBucket[];
  inventory: { total_products: number; total_stock_value: number; low_stock_count: number; warehouse_count: number; };
  overdue: { overdue_count: number; overdue_total: number; oldest_days: number; };
}

function fmt(n: number) { return n.toLocaleString("sv-SE", { minimumFractionDigits: 0 }); }
function fmtMonth(m: string) {
  const [y, mo] = m.split("-");
  return new Date(Number(y), Number(mo) - 1).toLocaleString("en", { month: "short" });
}

const STATUS_COLORS: Record<string, string> = {
  PAID: "#10b981", SENT: "#6366f1", OVERDUE: "#ef4444", DRAFT: "#475569",
};

function defaultRange() {
  const to = new Date();
  const from = new Date(to);
  from.setMonth(from.getMonth() - 11);
  from.setDate(1);
  return { from: from.toISOString().slice(0, 10), to: to.toISOString().slice(0, 10) };
}

export default function AnalyticsPage() {
  const [data, setData]       = useState<Analytics | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError]     = useState<string | null>(null);
  const [exporting, setExporting] = useState(false);
  const [fromDate, setFromDate] = useState("");
  const [toDate, setToDate]   = useState("");

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
      <div className="h-8 w-32 skeleton rounded" />
      <div className="grid grid-cols-4 gap-4">{[1,2,3,4].map(i => <div key={i} className="h-24 skeleton rounded-xl" />)}</div>
      <div className="h-72 skeleton rounded-xl" />
      <div className="grid grid-cols-2 gap-4">{[1,2].map(i => <div key={i} className="h-64 skeleton rounded-xl" />)}</div>
    </div>
  );

  if (error) return (
    <div className="rounded-lg border border-red-500/20 bg-red-500/10 px-4 py-3 text-sm text-red-400">{error}</div>
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

  const pieData = data.status_breakdown.map((b) => ({ name: b.status, value: b.count, total: Number(b.total) }));
  const barData = data.top_products.slice(0, 8).map((p) => ({
    name: p.description.length > 28 ? p.description.slice(0, 25) + "…" : p.description,
    Revenue: Number(p.revenue),
  })).reverse();

  return (
    <div className="space-y-6">

      {/* Header + date range */}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold vf-text-1">Analytics</h1>
          <p className="text-sm text-slate-600">{data.from_date} – {data.to_date}</p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <input type="date" value={fromDate} onChange={(e) => setFromDate(e.target.value)}
            className="vf-input w-auto text-xs py-1.5" />
          <span className="text-sm text-slate-600">to</span>
          <input type="date" value={toDate} onChange={(e) => setToDate(e.target.value)}
            className="vf-input w-auto text-xs py-1.5" />
          <button onClick={() => load(fromDate, toDate)} className="vf-btn text-xs px-3 py-1.5 h-auto">Apply</button>
          <button onClick={handleExport} disabled={exporting}
            className="vf-btn-ghost text-xs px-3 py-1.5 h-auto disabled:opacity-60">
            <Download className="h-3.5 w-3.5" />
            {exporting ? "Exporting…" : "Export PDF"}
          </button>
        </div>
      </div>

      {/* KPI row */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {[
          { label: "Invoiced",        value: `${fmt(totalInvoiced)} SEK`,   icon: TrendingUp,   col: "text-indigo-400" },
          { label: "Collected",       value: `${fmt(totalCollected)} SEK`,  icon: TrendingUp,   col: "text-emerald-400" },
          { label: "Collection rate", value: `${collectionRate}%`,          icon: TrendingUp,   col: collectionRate >= 80 ? "text-emerald-400" : "text-amber-400" },
          { label: "Overdue",         value: `${fmt(Number(data.overdue.overdue_total))} SEK`, icon: AlertTriangle, col: data.overdue.overdue_total > 0 ? "text-red-400" : "text-slate-600" },
        ].map(({ label, value, icon: Icon, col }) => (
          <div key={label} className="rounded-xl border border-white/[0.06] bg-vf-surface p-5">
            <div className={cn("flex items-center gap-2 mb-2", col)}>
              <Icon className="h-4 w-4" />
              <span className="text-[10px] uppercase tracking-widest text-slate-600">{label}</span>
            </div>
            <p className={cn("text-xl font-bold mt-0.5 tabular-nums", col)}>{value}</p>
          </div>
        ))}
      </div>

      {/* Revenue area chart */}
      <div className="rounded-xl border border-white/[0.06] bg-vf-surface p-6">
        <h2 className="font-semibold vf-text-1 mb-6">Revenue — Invoiced vs Collected (SEK)</h2>
        <ResponsiveContainer width="100%" height={240}>
          <AreaChart data={chartData} margin={{ top: 4, right: 8, left: 0, bottom: 0 }}>
            <defs>
              <linearGradient id="gInvoiced" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="#6366f1" stopOpacity={0.25} />
                <stop offset="95%" stopColor="#6366f1" stopOpacity={0} />
              </linearGradient>
              <linearGradient id="gCollected" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="#10b981" stopOpacity={0.25} />
                <stop offset="95%" stopColor="#10b981" stopOpacity={0} />
              </linearGradient>
            </defs>
            <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
            <XAxis dataKey="month" tick={{ fontSize: 11, fill: "#475569" }} axisLine={false} tickLine={false} />
            <YAxis tick={{ fontSize: 11, fill: "#475569" }} tickFormatter={(v) => `${(v / 1000).toFixed(0)}k`} axisLine={false} tickLine={false} />
            <Tooltip
              contentStyle={{ background: "#1A1E29", border: "1px solid rgba(255,255,255,0.08)", borderRadius: 8, color: "#F1F5F9" }}
              formatter={(v) => [`${fmt(Number(v))} SEK`]}
            />
            <Area type="monotone" dataKey="Invoiced" stroke="#6366f1" fill="url(#gInvoiced)" strokeWidth={2} />
            <Area type="monotone" dataKey="Collected" stroke="#10b981" fill="url(#gCollected)" strokeWidth={2} />
          </AreaChart>
        </ResponsiveContainer>
      </div>

      {/* Pie + top customers */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {/* Invoice status pie */}
        <div className="rounded-xl border border-white/[0.06] bg-vf-surface p-6">
          <h2 className="font-semibold vf-text-1 mb-4 flex items-center gap-2">
            <TrendingUp className="h-4 w-4 text-indigo-400" />Invoice status
          </h2>
          {pieData.length === 0 ? (
            <p className="text-sm text-slate-600 text-center py-10">No invoices in range</p>
          ) : (
            <div className="flex items-center gap-4">
              <ResponsiveContainer width="55%" height={200}>
                <PieChart>
                  <Pie data={pieData} cx="50%" cy="50%" innerRadius={50} outerRadius={80} paddingAngle={2} dataKey="value">
                    {pieData.map((entry, i) => (
                      <Cell key={entry.name} fill={STATUS_COLORS[entry.name] ?? "#475569"} />
                    ))}
                  </Pie>
                  <Tooltip
                    contentStyle={{ background: "#1A1E29", border: "1px solid rgba(255,255,255,0.08)", borderRadius: 8, color: "#F1F5F9" }}
                    formatter={(v, name) => [`${v} invoices`, String(name)]}
                  />
                </PieChart>
              </ResponsiveContainer>
              <div className="flex-1 space-y-2">
                {pieData.map((b) => (
                  <div key={b.name} className="flex items-center justify-between text-sm">
                    <div className="flex items-center gap-1.5">
                      <div className="h-2.5 w-2.5 rounded-full" style={{ backgroundColor: STATUS_COLORS[b.name] ?? "#475569" }} />
                      <span className="text-slate-500">{b.name}</span>
                    </div>
                    <span className="font-semibold vf-text-1">{b.value}</span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>

        {/* Top customers */}
        <div className="rounded-xl border border-white/[0.06] bg-vf-surface p-6 space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="font-semibold vf-text-1 flex items-center gap-2">
              <Users className="h-4 w-4 text-indigo-400" />Top customers
            </h2>
            <Link href="/customers" className="text-xs text-slate-600 hover:text-slate-300 transition-colors">
              View all <ArrowRight className="inline h-3 w-3" />
            </Link>
          </div>
          {data.top_customers.length === 0 ? (
            <p className="text-sm text-slate-600 text-center py-6">No invoices in range</p>
          ) : (
            <div className="space-y-3">
              {data.top_customers.map((c) => {
                const pct = Math.round((Number(c.total_invoiced) / (Number(data.top_customers[0].total_invoiced) || 1)) * 100);
                return (
                  <div key={c.customer_id}>
                    <div className="flex justify-between text-sm mb-1">
                      <span className="font-medium text-slate-300 truncate max-w-[180px]">{c.company_name}</span>
                      <span className="font-mono text-xs text-slate-600">{fmt(Number(c.total_invoiced))} SEK</span>
                    </div>
                    <div className="h-1.5 rounded-full bg-white/[0.06]">
                      <div className="h-1.5 rounded-full bg-indigo-500" style={{ width: `${pct}%` }} />
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </div>

      {/* Top products bar */}
      {data.top_products.length > 0 && (
        <div className="rounded-xl border border-white/[0.06] bg-vf-surface p-6">
          <h2 className="font-semibold vf-text-1 mb-6 flex items-center gap-2">
            <ShoppingBag className="h-4 w-4 text-emerald-400" />Top products by revenue (SEK)
          </h2>
          <ResponsiveContainer width="100%" height={Math.max(200, barData.length * 36)}>
            <BarChart data={barData} layout="vertical" margin={{ top: 0, right: 40, left: 8, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" horizontal={false} />
              <XAxis type="number" tick={{ fontSize: 11, fill: "#475569" }} tickFormatter={(v) => `${(v / 1000).toFixed(0)}k`} axisLine={false} tickLine={false} />
              <YAxis type="category" dataKey="name" tick={{ fontSize: 11, fill: "#475569" }} width={140} axisLine={false} tickLine={false} />
              <Tooltip
                contentStyle={{ background: "#1A1E29", border: "1px solid rgba(255,255,255,0.08)", borderRadius: 8, color: "#F1F5F9" }}
                formatter={(v) => [`${fmt(Number(v))} SEK`, "Revenue"]}
              />
              <Bar dataKey="Revenue" fill="#6366f1" radius={[0, 4, 4, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}

      {/* Inventory + overdue */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div className="rounded-xl border border-white/[0.06] bg-vf-surface p-6 space-y-3">
          <h2 className="font-semibold vf-text-1 flex items-center gap-2">
            <Package className="h-4 w-4 text-indigo-400" />Inventory
          </h2>
          <div className="grid grid-cols-2 gap-3">
            {[
              { label: "Products",    value: data.inventory.total_products },
              { label: "Warehouses",  value: data.inventory.warehouse_count },
              { label: "Low stock",   value: data.inventory.low_stock_count },
              { label: "Stock value", value: `${fmt(Number(data.inventory.total_stock_value))} SEK` },
            ].map(({ label, value }) => (
              <div key={label} className="rounded-lg bg-white/[0.03] border border-white/[0.04] px-3 py-2">
                <p className="text-xs text-slate-600">{label}</p>
                <p className="font-semibold vf-text-1 mt-0.5">{value}</p>
              </div>
            ))}
          </div>
        </div>

        <div className="rounded-xl border border-white/[0.06] bg-vf-surface p-6 space-y-3">
          <h2 className="font-semibold vf-text-1 flex items-center gap-2">
            <AlertTriangle className={cn("h-4 w-4", data.overdue.overdue_count > 0 ? "text-red-400" : "text-slate-600")} />
            Overdue receivables
          </h2>
          {data.overdue.overdue_count === 0 ? (
            <p className="text-sm text-emerald-400 font-medium">No overdue invoices</p>
          ) : (
            <div className="space-y-2">
              {[
                { label: "Overdue invoices", value: String(data.overdue.overdue_count),              cls: "vf-text-1" },
                { label: "Total overdue",    value: `${fmt(Number(data.overdue.overdue_total))} SEK`, cls: "text-red-400" },
                { label: "Oldest",           value: `${data.overdue.oldest_days} days`,               cls: "vf-text-1" },
              ].map(({ label, value, cls }) => (
                <div key={label} className="flex justify-between text-sm">
                  <span className="text-slate-500">{label}</span>
                  <span className={cn("font-semibold", cls)}>{value}</span>
                </div>
              ))}
              <Link href="/invoices" className="mt-1 inline-flex items-center gap-1 text-xs text-red-400 hover:text-red-300 transition-colors">
                View overdue invoices <ArrowRight className="h-3 w-3" />
              </Link>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
