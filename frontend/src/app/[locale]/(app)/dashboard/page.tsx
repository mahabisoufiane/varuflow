"use client";

import { api } from "@/lib/api-client";
import Link from "next/link";
import { useEffect, useState } from "react";
import { AlertTriangle, ArrowRight, FileText, Package, TrendingUp } from "lucide-react";

interface StockLevel { product: { name: string; sku: string }; warehouse: { name: string }; quantity: number; min_threshold: number; }
interface Invoice { id: string; invoice_number: string; customer: { company_name: string }; total_sek: string; due_date: string; status: string; }
interface Movement { id: string; type: string; product: { name: string }; quantity: number; created_at: string; }

export default function DashboardPage() {
  const [lowStock, setLowStock] = useState<StockLevel[]>([]);
  const [openInvoices, setOpenInvoices] = useState<Invoice[]>([]);
  const [recentMovements, setRecentMovements] = useState<Movement[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([
      api.get<StockLevel[]>("/api/inventory/stock?low_stock_only=true").catch(() => []),
      api.get<Invoice[]>("/api/invoicing/invoices?status=SENT").catch(() => []),
      api.get<Movement[]>("/api/inventory/movements?limit=5").catch(() => []),
    ]).then(([stock, invoices, movements]) => {
      setLowStock(stock.slice(0, 5));
      setOpenInvoices(invoices.slice(0, 5));
      setRecentMovements(movements);
    }).finally(() => setLoading(false));
  }, []);

  const outstanding = openInvoices.reduce((s, i) => s + Number(i.total_sek), 0);

  if (loading) return (
    <div className="space-y-6 animate-pulse">
      <div className="h-8 w-40 rounded bg-gray-100" />
      <div className="grid grid-cols-3 gap-4">{[1, 2, 3].map((i) => <div key={i} className="h-24 rounded-xl bg-gray-100" />)}</div>
      <div className="grid grid-cols-2 gap-4">{[1, 2].map((i) => <div key={i} className="h-48 rounded-xl bg-gray-100" />)}</div>
    </div>
  );

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-[#1a2332]">Dashboard</h1>
        <p className="text-sm text-muted-foreground">Your business at a glance</p>
      </div>

      {/* KPI cards */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <div className="rounded-xl border bg-white p-5">
          <div className="flex items-center gap-2 text-muted-foreground mb-1">
            <FileText className="h-4 w-4" />
            <span className="text-xs uppercase tracking-wide">Outstanding</span>
          </div>
          <p className="text-2xl font-bold text-[#1a2332]">
            {outstanding.toLocaleString("sv-SE", { minimumFractionDigits: 2 })} SEK
          </p>
          <Link href="/invoices" className="mt-2 inline-flex items-center gap-1 text-xs text-muted-foreground hover:text-[#1a2332]">
            View invoices <ArrowRight className="h-3 w-3" />
          </Link>
        </div>

        <div className="rounded-xl border bg-white p-5">
          <div className="flex items-center gap-2 text-muted-foreground mb-1">
            <AlertTriangle className="h-4 w-4" />
            <span className="text-xs uppercase tracking-wide">Low stock</span>
          </div>
          <p className="text-2xl font-bold text-[#1a2332]">{lowStock.length}</p>
          <Link href="/inventory" className="mt-2 inline-flex items-center gap-1 text-xs text-muted-foreground hover:text-[#1a2332]">
            View inventory <ArrowRight className="h-3 w-3" />
          </Link>
        </div>

        <div className="rounded-xl border bg-white p-5">
          <div className="flex items-center gap-2 text-muted-foreground mb-1">
            <TrendingUp className="h-4 w-4" />
            <span className="text-xs uppercase tracking-wide">Open invoices</span>
          </div>
          <p className="text-2xl font-bold text-[#1a2332]">{openInvoices.length}</p>
          <Link href="/invoices?status=SENT" className="mt-2 inline-flex items-center gap-1 text-xs text-muted-foreground hover:text-[#1a2332]">
            View sent <ArrowRight className="h-3 w-3" />
          </Link>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {/* Low stock alerts */}
        <div className="rounded-xl border bg-white p-5 space-y-3">
          <div className="flex items-center justify-between">
            <h2 className="font-semibold text-gray-900 flex items-center gap-2">
              <Package className="h-4 w-4 text-amber-500" />Low stock alerts
            </h2>
            <Link href="/inventory" className="text-xs text-muted-foreground hover:text-[#1a2332]">View all</Link>
          </div>
          {lowStock.length === 0 ? (
            <p className="text-sm text-muted-foreground py-4 text-center">All products are well-stocked</p>
          ) : (
            <div className="divide-y">
              {lowStock.map((sl, i) => (
                <div key={i} className="flex items-center justify-between py-2.5 text-sm">
                  <div>
                    <p className="font-medium text-gray-900">{sl.product.name}</p>
                    <p className="text-xs text-muted-foreground">{sl.product.sku} · {sl.warehouse.name}</p>
                  </div>
                  <span className="rounded bg-amber-100 px-2 py-0.5 text-xs font-medium text-amber-700">
                    {sl.quantity} left
                  </span>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Open invoices */}
        <div className="rounded-xl border bg-white p-5 space-y-3">
          <div className="flex items-center justify-between">
            <h2 className="font-semibold text-gray-900 flex items-center gap-2">
              <FileText className="h-4 w-4 text-blue-500" />Open invoices
            </h2>
            <Link href="/invoices" className="text-xs text-muted-foreground hover:text-[#1a2332]">View all</Link>
          </div>
          {openInvoices.length === 0 ? (
            <p className="text-sm text-muted-foreground py-4 text-center">No outstanding invoices</p>
          ) : (
            <div className="divide-y">
              {openInvoices.map((inv) => (
                <div key={inv.id} className="flex items-center justify-between py-2.5 text-sm">
                  <div>
                    <Link href={`/invoices/${inv.id}`} className="font-medium text-[#1a2332] hover:underline">
                      {inv.invoice_number}
                    </Link>
                    <p className="text-xs text-muted-foreground">{inv.customer.company_name} · Due {inv.due_date}</p>
                  </div>
                  <span className="font-mono text-sm font-medium">
                    {Number(inv.total_sek).toLocaleString("sv-SE", { minimumFractionDigits: 0 })} SEK
                  </span>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Recent movements */}
      {recentMovements.length > 0 && (
        <div className="rounded-xl border bg-white p-5 space-y-3">
          <div className="flex items-center justify-between">
            <h2 className="font-semibold text-gray-900">Recent stock movements</h2>
            <Link href="/inventory/movements" className="text-xs text-muted-foreground hover:text-[#1a2332]">View all</Link>
          </div>
          <div className="divide-y">
            {recentMovements.map((m) => (
              <div key={m.id} className="flex items-center justify-between py-2 text-sm">
                <div className="flex items-center gap-3">
                  <span className={`rounded px-1.5 py-0.5 text-xs font-medium ${
                    m.type === "IN" ? "bg-green-100 text-green-700" :
                    m.type === "OUT" ? "bg-red-100 text-red-700" : "bg-gray-100 text-gray-700"
                  }`}>{m.type}</span>
                  <span className="font-medium">{m.product.name}</span>
                </div>
                <div className="flex items-center gap-4 text-muted-foreground text-xs">
                  <span className="font-mono">{m.quantity}</span>
                  <span>{new Date(m.created_at).toLocaleDateString("sv-SE")}</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
