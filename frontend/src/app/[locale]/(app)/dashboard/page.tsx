"use client";

import { api } from "@/lib/api-client";
import Link from "next/link";
import { useEffect, useState } from "react";
import {
  AlertTriangle, ArrowRight, ArrowUpRight, FileText,
  Package, Plus, ShoppingCart, TrendingUp,
} from "lucide-react";
import AiActionCards from "@/components/app/AiActionCards";

interface StockLevel { product: { name: string; sku: string }; warehouse: { name: string }; quantity: number; min_threshold: number; }
interface Invoice { id: string; invoice_number: string; customer: { company_name: string }; total_sek: string; due_date: string; status: string; }
interface Movement { id: string; type: string; product: { name: string }; quantity: number; created_at: string; }

function fmt(n: number) {
  return n.toLocaleString("sv-SE", { minimumFractionDigits: 0, maximumFractionDigits: 0 });
}

function Skeleton({ className }: { className?: string }) {
  return <div className={`animate-pulse rounded-lg bg-gray-100 ${className ?? ""}`} />;
}

export default function DashboardPage() {
  const [lowStock, setLowStock] = useState<StockLevel[]>([]);
  const [openInvoices, setOpenInvoices] = useState<Invoice[]>([]);
  const [recentMovements, setRecentMovements] = useState<Movement[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([
      api.get<StockLevel[]>("/api/inventory/stock?low_stock_only=true").catch(() => []),
      api.get<Invoice[]>("/api/invoicing/invoices?status=SENT").catch(() => []),
      api.get<Movement[]>("/api/inventory/movements?limit=6").catch(() => []),
    ]).then(([stock, invoices, movements]) => {
      setLowStock(stock.slice(0, 5));
      setOpenInvoices(invoices.slice(0, 5));
      setRecentMovements(movements);
    }).finally(() => setLoading(false));
  }, []);

  const outstanding = openInvoices.reduce((s, i) => s + Number(i.total_sek), 0);
  const today = new Date().toLocaleDateString("sv-SE", { weekday: "long", day: "numeric", month: "long" });

  if (loading) return (
    <div className="space-y-6">
      <Skeleton className="h-7 w-64" />
      <Skeleton className="h-36 w-full" />
      <div className="grid grid-cols-3 gap-4">
        {[1,2,3].map(i => <Skeleton key={i} className="h-28" />)}
      </div>
      <div className="grid grid-cols-2 gap-4">
        {[1,2].map(i => <Skeleton key={i} className="h-56" />)}
      </div>
    </div>
  );

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <p className="text-sm text-gray-400 capitalize">{today}</p>
          <h1 className="text-2xl font-bold text-gray-900 mt-0.5">Dashboard</h1>
        </div>
        <div className="flex gap-2">
          <Link href="/inventory/products/new"
            className="inline-flex items-center gap-1.5 rounded-lg border border-gray-200 bg-white px-3 py-1.5 text-sm font-medium text-gray-700 shadow-sm hover:bg-gray-50 transition-colors">
            <Plus className="h-3.5 w-3.5" />Product
          </Link>
          <Link href="/invoices/new"
            className="inline-flex items-center gap-1.5 rounded-lg bg-[#0f1724] px-3 py-1.5 text-sm font-medium text-white shadow-sm hover:bg-[#1a2840] transition-colors">
            <Plus className="h-3.5 w-3.5" />Invoice
          </Link>
        </div>
      </div>

      {/* Hero revenue card */}
      <div className="relative overflow-hidden rounded-2xl bg-gradient-to-br from-[#0f1724] via-[#1a2840] to-[#0f1724] p-6 text-white shadow-lg">
        <div className="absolute inset-0 opacity-10"
          style={{ backgroundImage: "radial-gradient(circle at 70% 50%, #3b82f6 0%, transparent 60%)" }} />
        <div className="relative flex items-start justify-between">
          <div>
            <p className="text-sm text-blue-200/70 font-medium">Outstanding receivables</p>
            <p className="mt-1 text-4xl font-bold tracking-tight">
              {fmt(outstanding)} <span className="text-xl font-normal text-blue-200/60">SEK</span>
            </p>
            <p className="mt-2 text-sm text-blue-200/60">
              {openInvoices.length} {openInvoices.length === 1 ? "invoice" : "invoices"} awaiting payment
            </p>
          </div>
          <Link href="/invoices?status=SENT"
            className="flex items-center gap-1 rounded-lg bg-white/10 px-3 py-1.5 text-sm hover:bg-white/20 transition-colors">
            View all <ArrowUpRight className="h-3.5 w-3.5" />
          </Link>
        </div>
      </div>

      {/* KPI row */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <KpiCard
          icon={<AlertTriangle className="h-4 w-4" />}
          iconBg="bg-amber-100 text-amber-600"
          label="Low stock items"
          value={String(lowStock.length)}
          href="/inventory"
          linkLabel="Go to inventory"
        />
        <KpiCard
          icon={<FileText className="h-4 w-4" />}
          iconBg="bg-blue-100 text-blue-600"
          label="Open invoices"
          value={String(openInvoices.length)}
          href="/invoices"
          linkLabel="Go to invoices"
        />
        <KpiCard
          icon={<ShoppingCart className="h-4 w-4" />}
          iconBg="bg-emerald-100 text-emerald-600"
          label="Cash register"
          value="Open"
          href="/pos"
          linkLabel="Open register"
        />
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {/* Low stock */}
        <Panel
          title="Low stock alerts"
          icon={<Package className="h-4 w-4 text-amber-500" />}
          linkHref="/inventory"
          linkLabel="View all"
        >
          {lowStock.length === 0 ? (
            <EmptyState text="All products well-stocked" />
          ) : lowStock.map((sl, i) => (
            <div key={i} className="flex items-center justify-between py-2.5">
              <div className="min-w-0">
                <p className="truncate text-sm font-medium text-gray-900">{sl.product.name}</p>
                <p className="text-xs text-gray-400">{sl.product.sku} · {sl.warehouse.name}</p>
              </div>
              <span className="ml-3 shrink-0 rounded-full bg-amber-50 px-2.5 py-0.5 text-xs font-semibold text-amber-700 border border-amber-200">
                {sl.quantity} left
              </span>
            </div>
          ))}
        </Panel>

        {/* Open invoices */}
        <Panel
          title="Awaiting payment"
          icon={<FileText className="h-4 w-4 text-blue-500" />}
          linkHref="/invoices"
          linkLabel="View all"
        >
          {openInvoices.length === 0 ? (
            <EmptyState text="No outstanding invoices" />
          ) : openInvoices.map((inv) => (
            <div key={inv.id} className="flex items-center justify-between py-2.5">
              <div className="min-w-0">
                <Link href={`/invoices/${inv.id}`} className="text-sm font-medium text-gray-900 hover:text-blue-600 transition-colors">
                  {inv.invoice_number}
                </Link>
                <p className="text-xs text-gray-400">{inv.customer.company_name} · Due {inv.due_date}</p>
              </div>
              <span className="ml-3 shrink-0 font-mono text-sm font-semibold text-gray-900">
                {fmt(Number(inv.total_sek))} kr
              </span>
            </div>
          ))}
        </Panel>
      </div>

      {/* AI Action Cards */}
      <AiActionCards />

      {/* Recent movements */}
      {recentMovements.length > 0 && (
        <Panel
          title="Recent stock movements"
          icon={<TrendingUp className="h-4 w-4 text-gray-400" />}
          linkHref="/inventory/movements"
          linkLabel="View all"
          noDivide
        >
          <div className="grid gap-2">
            {recentMovements.map((m) => (
              <div key={m.id} className="flex items-center gap-3 rounded-lg bg-gray-50 px-3 py-2 text-sm">
                <span className={`shrink-0 rounded-md px-1.5 py-0.5 text-[11px] font-bold ${
                  m.type === "IN" ? "bg-emerald-100 text-emerald-700" :
                  m.type === "OUT" ? "bg-red-100 text-red-700" : "bg-gray-200 text-gray-600"
                }`}>{m.type}</span>
                <span className="flex-1 min-w-0 truncate font-medium text-gray-900">{m.product.name}</span>
                <span className="font-mono text-gray-500">{m.quantity}</span>
                <span className="text-xs text-gray-400">{new Date(m.created_at).toLocaleDateString("sv-SE")}</span>
              </div>
            ))}
          </div>
        </Panel>
      )}
    </div>
  );
}

function KpiCard({ icon, iconBg, label, value, href, linkLabel }: {
  icon: React.ReactNode; iconBg: string; label: string; value: string; href: string; linkLabel: string;
}) {
  return (
    <div className="rounded-xl border border-gray-200 bg-white p-5 shadow-sm">
      <div className="flex items-center justify-between">
        <span className={`inline-flex h-8 w-8 items-center justify-center rounded-lg ${iconBg}`}>{icon}</span>
      </div>
      <p className="mt-3 text-3xl font-bold text-gray-900">{value}</p>
      <p className="mt-0.5 text-sm text-gray-500">{label}</p>
      <Link href={href} className="mt-3 inline-flex items-center gap-1 text-xs font-medium text-gray-400 hover:text-gray-900 transition-colors">
        {linkLabel} <ArrowRight className="h-3 w-3" />
      </Link>
    </div>
  );
}

function Panel({ title, icon, linkHref, linkLabel, children, noDivide }: {
  title: string; icon: React.ReactNode; linkHref: string; linkLabel: string;
  children: React.ReactNode; noDivide?: boolean;
}) {
  return (
    <div className="rounded-xl border border-gray-200 bg-white p-5 shadow-sm">
      <div className="flex items-center justify-between mb-3">
        <h2 className="flex items-center gap-2 text-sm font-semibold text-gray-900">
          {icon}{title}
        </h2>
        <Link href={linkHref} className="flex items-center gap-1 text-xs text-gray-400 hover:text-gray-900 transition-colors">
          {linkLabel} <ArrowRight className="h-3 w-3" />
        </Link>
      </div>
      <div className={noDivide ? "" : "divide-y divide-gray-100"}>{children}</div>
    </div>
  );
}

function EmptyState({ text }: { text: string }) {
  return <p className="py-6 text-center text-sm text-gray-400">{text}</p>;
}
