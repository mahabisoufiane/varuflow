"use client";

import { api } from "@/lib/api-client";
import { useEffect, useState } from "react";
import Link from "next/link";
import {
  AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, BarChart, Bar, Legend,
} from "recharts";
import { ArrowRight, Package, TrendingUp, AlertTriangle, Users } from "lucide-react";

interface RevenuePoint { month: string; invoiced: number; collected: number; }
interface TopCustomer { customer_id: string; company_name: string; total_invoiced: number; invoice_count: number; }
interface Analytics {
  revenue_12m: RevenuePoint[];
  top_customers: TopCustomer[];
  inventory: { total_products: number; total_stock_value: number; low_stock_count: number; warehouse_count: number; };
  overdue: { overdue_count: number; overdue_total: number; oldest_days: number; };
}

function fmt(n: number) { return n.toLocaleString("sv-SE", { minimumFractionDigits: 0 }); }
function fmtMonth(m: string) {
  const [y, mo] = m.split("-");
  return new Date(Number(y), Number(mo) - 1).toLocaleString("en", { month: "short" });
}

export default function AnalyticsPage() {
  const [data, setData] = useState<Analytics | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.get<Analytics>("/api/analytics/overview")
      .then(setData)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  if (loading) return (
    <div className="space-y-6 animate-pulse">
      <div className="h-8 w-32 rounded bg-gray-100" />
      <div className="grid grid-cols-4 gap-4">{[1,2,3,4].map(i => <div key={i} className="h-24 rounded-xl bg-gray-100" />)}</div>
      <div className="h-72 rounded-xl bg-gray-100" />
    </div>
  );

  if (error) return <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">{error}</div>;
  if (!data) return null;

  const chartData = data.revenue_12m.map((p) => ({
    month: fmtMonth(p.month),
    Invoiced: Number(p.invoiced),
    Collected: Number(p.collected),
  }));

  const totalInvoiced = data.revenue_12m.reduce((s, p) => s + Number(p.invoiced), 0);
  const totalCollected = data.revenue_12m.reduce((s, p) => s + Number(p.collected), 0);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-[#1a2332]">Analytics</h1>
        <p className="text-sm text-muted-foreground">Last 12 months</p>
      </div>

      {/* KPI row */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {[
          { label: "Invoiced (12m)", value: `${fmt(totalInvoiced)} SEK`, icon: TrendingUp, color: "text-blue-600" },
          { label: "Collected (12m)", value: `${fmt(totalCollected)} SEK`, icon: TrendingUp, color: "text-green-600" },
          { label: "Stock value", value: `${fmt(Number(data.inventory.total_stock_value))} SEK`, icon: Package, color: "text-[#1a2332]" },
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

      {/* Revenue chart */}
      <div className="rounded-xl border bg-white p-6">
        <h2 className="font-semibold text-gray-900 mb-6">Revenue — Invoiced vs Collected (SEK)</h2>
        <ResponsiveContainer width="100%" height={260}>
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
            <YAxis tick={{ fontSize: 11 }} tickFormatter={(v) => `${(v/1000).toFixed(0)}k`} />
            <Tooltip formatter={(v: number) => [`${fmt(v)} SEK`]} />
            <Legend />
            <Area type="monotone" dataKey="Invoiced" stroke="#1a2332" fill="url(#gInvoiced)" strokeWidth={2} />
            <Area type="monotone" dataKey="Collected" stroke="#22c55e" fill="url(#gCollected)" strokeWidth={2} />
          </AreaChart>
        </ResponsiveContainer>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
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
            <p className="text-sm text-muted-foreground text-center py-6">No invoices yet</p>
          ) : (
            <div className="space-y-3">
              {data.top_customers.map((c, i) => {
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

        {/* Inventory + overdue */}
        <div className="space-y-4">
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
    </div>
  );
}
