"use client";

import { api } from "@/lib/api-client";
import { useEffect, useState, useCallback } from "react";
import Link from "next/link";
import {
  AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
  BarChart, Bar, PieChart, Pie, Cell, Legend,
} from "recharts";
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
  PAID: "#22c55e",
  SENT: "#3b82f6",
  OVERDUE: "#ef4444",
  DRAFT: "#9ca3af",
};

const PIE_COLORS = ["#22c55e", "#3b82f6", "#ef4444", "#9ca3af"];

function defaultRange() {
  const to = new Date();
  const from = new Date(to);
  from.setMonth(from.getMonth() - 11);
  from.setDate(1);
  return {
    from: from.toISOString().slice(0, 10),
    to: to.toISOString().slice(0, 10),
  };
}

export default function AnalyticsPage() {
  const [data, setData] = useState<Analytics | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [exporting, setExporting] = useState(false);
  // Initialize with empty strings to avoid SSR/CSR mismatch from new Date()
  const [fromDate, setFromDate] = useState("");
  const [toDate, setToDate] = useState("");

  const load = useCallback((from: string, to: string) => {
    setLoading(true);
    setError(null);
    api.get<Analytics>(`/api/analytics/overview?from_date=${from}&to_date=${to}`)
      .then(setData)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    const { from, to } = defaultRange();
    setFromDate(from);
    setToDate(to);
    load(from, to);
  }, []);  // eslint-disable-line react-hooks/exhaustive-deps

  function handleApply() { load(fromDate, toDate); }

  async function handleExport() {
    setExporting(true);
    try {
      const url = `${process.env.NEXT_PUBLIC_API_URL}/api/analytics/export/pdf?from_date=${fromDate}&to_date=${toDate}`;
      // Need auth header — fetch manually
      const { createClient } = await import("@/lib/supabase/client");
      const supabase = createClient();
      const { data: { session } } = await supabase.auth.getSession();
      const res = await fetch(url, {
        headers: session ? { Authorization: `Bearer ${session.access_token}` } : {},
      });
      const blob = await res.blob();
      const a = document.createElement("a");
      a.href = URL.createObjectURL(blob);
      a.download = `analytics-${fromDate}-${toDate}.pdf`;
      a.click();
      URL.revokeObjectURL(a.href);
    } finally {
      setExporting(false);
    }
  }

  if (loading) return (
    <div className="space-y-6 animate-pulse">
      <div className="h-8 w-32 rounded bg-gray-100" />
      <div className="grid grid-cols-4 gap-4">{[1,2,3,4].map(i => <div key={i} className="h-24 rounded-xl bg-gray-100" />)}</div>
      <div className="h-72 rounded-xl bg-gray-100" />
      <div className="grid grid-cols-2 gap-4">{[1,2].map(i => <div key={i} className="h-64 rounded-xl bg-gray-100" />)}</div>
    </div>
  );

  if (error) return <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">{error}</div>;
  if (!data) return null;

  const chartData = data.revenue_points.map((p) => ({
    month: fmtMonth(p.month),
    Invoiced: Number(p.invoiced),
    Collected: Number(p.collected),
  }));

  const totalInvoiced = data.revenue_points.reduce((s, p) => s + Number(p.invoiced), 0);
  const totalCollected = data.revenue_points.reduce((s, p) => s + Number(p.collected), 0);
  const collectionRate = totalInvoiced > 0 ? Math.round((totalCollected / totalInvoiced) * 100) : 0;

  const pieData = data.status_breakdown.map((b) => ({
    name: b.status,
    value: b.count,
    total: Number(b.total),
  }));

  const barData = data.top_products.slice(0, 8).map((p) => ({
    name: p.description.length > 28 ? p.description.slice(0, 25) + "…" : p.description,
    Revenue: Number(p.revenue),
  })).reverse();

  return (
    <div className="space-y-6">
      {/* Header + date range */}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold text-[#1a2332]">Analytics</h1>
          <p className="text-sm text-muted-foreground">
            {data.from_date} – {data.to_date}
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <input
            type="date"
            value={fromDate}
            onChange={(e) => setFromDate(e.target.value)}
            className="rounded-md border border-gray-300 px-2.5 py-1.5 text-sm focus:border-[#1a2332] focus:outline-none focus:ring-1 focus:ring-[#1a2332]"
          />
          <span className="text-sm text-muted-foreground">to</span>
          <input
            type="date"
            value={toDate}
            onChange={(e) => setToDate(e.target.value)}
            className="rounded-md border border-gray-300 px-2.5 py-1.5 text-sm focus:border-[#1a2332] focus:outline-none focus:ring-1 focus:ring-[#1a2332]"
          />
          <button
            onClick={handleApply}
            className="rounded-md bg-[#1a2332] px-3 py-1.5 text-sm font-medium text-white hover:bg-[#2a3342]"
          >
            Apply
          </button>
          <button
            onClick={handleExport}
            disabled={exporting}
            className="inline-flex items-center gap-1.5 rounded-md border border-gray-300 bg-white px-3 py-1.5 text-sm font-medium text-gray-700 hover:bg-gray-50 disabled:opacity-60"
          >
            <Download className="h-3.5 w-3.5" />
            {exporting ? "Exporting…" : "Export PDF"}
          </button>
        </div>
      </div>

      {/* KPI row */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {[
          { label: "Invoiced", value: `${fmt(totalInvoiced)} SEK`, icon: TrendingUp, color: "text-blue-600" },
          { label: "Collected", value: `${fmt(totalCollected)} SEK`, icon: TrendingUp, color: "text-green-600" },
          { label: "Collection rate", value: `${collectionRate}%`, icon: TrendingUp, color: collectionRate >= 80 ? "text-green-600" : "text-amber-600" },
          { label: "Overdue", value: `${fmt(Number(data.overdue.overdue_total))} SEK`, icon: AlertTriangle, color: data.overdue.overdue_total > 0 ? "text-red-600" : "text-gray-400" },
        ].map(({ label, value, icon: Icon, color }) => (
          <div key={label} className="rounded-xl border bg-white p-5">
            <div className="flex items-center gap-2 text-muted-foreground mb-1">
              <Icon className={`h-4 w-4 ${color}`} />
              <span className="text-xs uppercase tracking-wide">{label}</span>
            </div>
            <p className={`text-xl font-bold mt-0.5 ${color}`}>{value}</p>
          </div>
        ))}
      </div>

      {/* Revenue area chart */}
      <div className="rounded-xl border bg-white p-6">
        <h2 className="font-semibold text-gray-900 mb-6">Revenue — Invoiced vs Collected (SEK)</h2>
        <ResponsiveContainer width="100%" height={240}>
          <AreaChart data={chartData} margin={{ top: 4, right: 8, left: 0, bottom: 0 }}>
            <defs>
              <linearGradient id="gInvoiced" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="#1a2332" stopOpacity={0.15} />
                <stop offset="95%" stopColor="#1a2332" stopOpacity={0} />
              </linearGradient>
              <linearGradient id="gCollected" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="#22c55e" stopOpacity={0.15} />
                <stop offset="95%" stopColor="#22c55e" stopOpacity={0} />
              </linearGradient>
            </defs>
            <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
            <XAxis dataKey="month" tick={{ fontSize: 11 }} />
            <YAxis tick={{ fontSize: 11 }} tickFormatter={(v) => `${(v / 1000).toFixed(0)}k`} />
            <Tooltip formatter={(v) => [`${fmt(Number(v))} SEK`]} />
            <Legend />
            <Area type="monotone" dataKey="Invoiced" stroke="#1a2332" fill="url(#gInvoiced)" strokeWidth={2} />
            <Area type="monotone" dataKey="Collected" stroke="#22c55e" fill="url(#gCollected)" strokeWidth={2} />
          </AreaChart>
        </ResponsiveContainer>
      </div>

      {/* Pie + top customers */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {/* Invoice status pie */}
        <div className="rounded-xl border bg-white p-6">
          <h2 className="font-semibold text-gray-900 mb-4 flex items-center gap-2">
            <TrendingUp className="h-4 w-4 text-blue-500" />Invoice status
          </h2>
          {pieData.length === 0 ? (
            <p className="text-sm text-muted-foreground text-center py-10">No invoices in range</p>
          ) : (
            <div className="flex items-center gap-4">
              <ResponsiveContainer width="55%" height={200}>
                <PieChart>
                  <Pie
                    data={pieData}
                    cx="50%"
                    cy="50%"
                    innerRadius={50}
                    outerRadius={80}
                    paddingAngle={2}
                    dataKey="value"
                  >
                    {pieData.map((entry, i) => (
                      <Cell key={entry.name} fill={STATUS_COLORS[entry.name] ?? PIE_COLORS[i % PIE_COLORS.length]} />
                    ))}
                  </Pie>
                  <Tooltip formatter={(v, name) => [`${v} invoices`, String(name)]} />
                </PieChart>
              </ResponsiveContainer>
              <div className="flex-1 space-y-2">
                {pieData.map((b, i) => (
                  <div key={b.name} className="flex items-center justify-between text-sm">
                    <div className="flex items-center gap-1.5">
                      <div className="h-2.5 w-2.5 rounded-full" style={{ backgroundColor: STATUS_COLORS[b.name] ?? PIE_COLORS[i % PIE_COLORS.length] }} />
                      <span className="text-gray-600">{b.name}</span>
                    </div>
                    <span className="font-semibold text-gray-900">{b.value}</span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>

        {/* Top customers */}
        <div className="rounded-xl border bg-white p-6 space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="font-semibold text-gray-900 flex items-center gap-2">
              <Users className="h-4 w-4 text-blue-500" />Top customers
            </h2>
            <Link href="/customers" className="text-xs text-muted-foreground hover:text-[#1a2332]">
              View all <ArrowRight className="inline h-3 w-3" />
            </Link>
          </div>
          {data.top_customers.length === 0 ? (
            <p className="text-sm text-muted-foreground text-center py-6">No invoices in range</p>
          ) : (
            <div className="space-y-3">
              {data.top_customers.map((c) => {
                const pct = Math.round((Number(c.total_invoiced) / (Number(data.top_customers[0].total_invoiced) || 1)) * 100);
                return (
                  <div key={c.customer_id}>
                    <div className="flex justify-between text-sm mb-1">
                      <span className="font-medium truncate max-w-[180px]">{c.company_name}</span>
                      <span className="font-mono text-xs text-muted-foreground">{fmt(Number(c.total_invoiced))} SEK</span>
                    </div>
                    <div className="h-1.5 rounded-full bg-gray-100">
                      <div className="h-1.5 rounded-full bg-[#1a2332]" style={{ width: `${pct}%` }} />
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </div>

      {/* Top products horizontal bar */}
      {data.top_products.length > 0 && (
        <div className="rounded-xl border bg-white p-6">
          <h2 className="font-semibold text-gray-900 mb-6 flex items-center gap-2">
            <ShoppingBag className="h-4 w-4 text-emerald-500" />Top products by revenue (SEK)
          </h2>
          <ResponsiveContainer width="100%" height={Math.max(200, barData.length * 36)}>
            <BarChart data={barData} layout="vertical" margin={{ top: 0, right: 40, left: 8, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" horizontal={false} />
              <XAxis type="number" tick={{ fontSize: 11 }} tickFormatter={(v) => `${(v / 1000).toFixed(0)}k`} />
              <YAxis type="category" dataKey="name" tick={{ fontSize: 11 }} width={140} />
              <Tooltip formatter={(v) => [`${fmt(Number(v))} SEK`, "Revenue"]} />
              <Bar dataKey="Revenue" fill="#1a2332" radius={[0, 4, 4, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}

      {/* Inventory + overdue */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div className="rounded-xl border bg-white p-6 space-y-3">
          <h2 className="font-semibold text-gray-900 flex items-center gap-2">
            <Package className="h-4 w-4 text-[#1a2332]" />Inventory
          </h2>
          <div className="grid grid-cols-2 gap-3">
            {[
              { label: "Products", value: data.inventory.total_products },
              { label: "Warehouses", value: data.inventory.warehouse_count },
              { label: "Low stock", value: data.inventory.low_stock_count },
              { label: "Stock value", value: `${fmt(Number(data.inventory.total_stock_value))} SEK` },
            ].map(({ label, value }) => (
              <div key={label} className="rounded-lg bg-gray-50 px-3 py-2">
                <p className="text-xs text-muted-foreground">{label}</p>
                <p className="font-semibold text-gray-900 mt-0.5">{value}</p>
              </div>
            ))}
          </div>
        </div>

        <div className="rounded-xl border bg-white p-6 space-y-3">
          <h2 className="font-semibold text-gray-900 flex items-center gap-2">
            <AlertTriangle className={`h-4 w-4 ${data.overdue.overdue_count > 0 ? "text-red-500" : "text-gray-400"}`} />
            Overdue receivables
          </h2>
          {data.overdue.overdue_count === 0 ? (
            <p className="text-sm text-green-600 font-medium">No overdue invoices</p>
          ) : (
            <div className="space-y-2">
              <div className="flex justify-between text-sm">
                <span className="text-muted-foreground">Overdue invoices</span>
                <span className="font-semibold">{data.overdue.overdue_count}</span>
              </div>
              <div className="flex justify-between text-sm">
                <span className="text-muted-foreground">Total overdue</span>
                <span className="font-semibold text-red-600">{fmt(Number(data.overdue.overdue_total))} SEK</span>
              </div>
              <div className="flex justify-between text-sm">
                <span className="text-muted-foreground">Oldest</span>
                <span className="font-semibold">{data.overdue.oldest_days} days</span>
              </div>
              <Link href="/invoices" className="mt-1 inline-flex items-center gap-1 text-xs text-red-600 hover:underline">
                View overdue invoices <ArrowRight className="h-3 w-3" />
              </Link>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
