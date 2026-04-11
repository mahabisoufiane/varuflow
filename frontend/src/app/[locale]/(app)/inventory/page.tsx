"use client";

import { api } from "@/lib/api-client";
import { Link } from "@/i18n/navigation";
import { useEffect, useState } from "react";
import { toast } from "sonner";
import { cn } from "@/lib/utils";
import {
  AlertTriangle, ArrowRight, CheckCircle2, Package,
  Plus, TrendingDown, Warehouse, Activity, ShoppingCart, Search,
} from "lucide-react";

interface StockLevel {
  id: string;
  product_id: string;
  warehouse_id: string;
  quantity: number;
  min_threshold: number;
  is_low: boolean;
  product: { id: string; name: string; sku: string; unit: string; category?: string };
  warehouse: { id: string; name: string };
}

function StockBar({ qty, min }: { qty: number; min: number }) {
  const pct = min > 0 ? Math.min(100, Math.round((qty / (min * 3)) * 100)) : 100;
  const color = pct <= 33 ? "bg-red-400" : pct <= 66 ? "bg-amber-400" : "bg-emerald-400";
  return (
    <div className="flex items-center gap-2">
      <div className="h-1.5 w-16 rounded-full overflow-hidden" style={{ background: "var(--vf-bg-elevated)" }}>
        <div className={cn("h-full rounded-full transition-all", color)} style={{ width: `${pct}%` }} />
      </div>
      <span className="tabular-nums text-[13px] font-semibold vf-text-1">{qty}</span>
    </div>
  );
}

export default function InventoryPage() {
  const [stock, setStock]     = useState<StockLevel[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch]   = useState("");

  useEffect(() => {
    api.get<StockLevel[]>("/api/inventory/stock")
      .then(setStock)
      .catch((e) => toast.error((e as Error).message))
      .finally(() => setLoading(false));
  }, []);

  const lowStock        = stock.filter(s => s.is_low);
  const totalProducts   = new Set(stock.map(s => s.product_id)).size;
  const totalWarehouses = new Set(stock.map(s => s.warehouse_id)).size;
  const healthyCount    = stock.length - lowStock.length;

  const filtered = stock.filter(s =>
    s.product.name.toLowerCase().includes(search.toLowerCase()) ||
    s.product.sku.toLowerCase().includes(search.toLowerCase())
  );

  const NAV_TILES = [
    { href: "/inventory/products",        icon: Package,      label: "Products",        sub: `${totalProducts} items`       },
    { href: "/inventory/warehouses",      icon: Warehouse,    label: "Warehouses",      sub: `${totalWarehouses} locations` },
    { href: "/inventory/movements",       icon: Activity,     label: "Movements",       sub: "Record stock in/out"          },
    { href: "/inventory/purchase-orders", icon: ShoppingCart, label: "Purchase Orders", sub: "Reorder from suppliers"       },
  ];

  return (
    <div className="space-y-6">

      {/* ── Header ─────────────────────────────────────────────────────── */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold tracking-tight vf-text-1">Inventory</h1>
          <p className="text-xs vf-text-m mt-0.5">Stock levels across all warehouses</p>
        </div>
        <Link href="/inventory/products/new" className="vf-btn text-xs">
          <Plus className="h-3.5 w-3.5" />Add product
        </Link>
      </div>

      {/* ── KPI strip ───────────────────────────────────────────────────── */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        {[
          { label: "Products",   value: totalProducts,   icon: <Package className="h-4 w-4" />,      col: "text-indigo-400 bg-indigo-500/10"  },
          { label: "Warehouses", value: totalWarehouses, icon: <Warehouse className="h-4 w-4" />,    col: "text-violet-400 bg-violet-500/10"  },
          { label: "Low stock",  value: lowStock.length, icon: <TrendingDown className="h-4 w-4" />, col: lowStock.length > 0 ? "text-red-400 bg-red-500/10" : "text-emerald-400 bg-emerald-500/10" },
          { label: "Healthy",    value: healthyCount,    icon: <CheckCircle2 className="h-4 w-4" />, col: "text-emerald-400 bg-emerald-500/10" },
        ].map(({ label, value, icon, col }) => (
          <div key={label} className="vf-section p-4" style={{ borderRadius: 14 }}>
            <div className={cn("inline-flex h-9 w-9 items-center justify-center rounded-xl mb-3", col)}>{icon}</div>
            <p className="text-[10px] font-semibold vf-text-m uppercase tracking-wide mb-1">{label}</p>
            <p className="text-xl font-bold tabular-nums vf-text-1">{loading ? "—" : value}</p>
          </div>
        ))}
      </div>

      {/* ── Nav tiles ───────────────────────────────────────────────────── */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        {NAV_TILES.map(({ href, icon: Icon, label, sub }) => (
          <Link key={href} href={href}
            className="group vf-section p-4 flex items-center gap-3 hover:shadow-card transition-all"
            style={{ borderRadius: 14 }}
            onMouseEnter={(e) => (e.currentTarget.style.background = "var(--vf-bg-elevated)")}
            onMouseLeave={(e) => (e.currentTarget.style.background = "var(--vf-bg-surface)")}>
            <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl"
              style={{ background: "var(--vf-bg-elevated)" }}>
              <Icon className="h-4 w-4 vf-text-m group-hover:text-indigo-500 transition-colors" />
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-[13px] font-semibold vf-text-1">{label}</p>
              <p className="text-xs vf-text-m truncate mt-0.5">{sub}</p>
            </div>
            <ArrowRight className="h-4 w-4 shrink-0 vf-text-m group-hover:text-indigo-500 transition-colors" />
          </Link>
        ))}
      </div>

      {/* ── Low stock alerts ────────────────────────────────────────────── */}
      {!loading && lowStock.length > 0 && (
        <div className="rounded-xl p-5"
          style={{ background: "rgba(239,68,68,0.05)", border: "1px solid rgba(239,68,68,0.18)" }}>
          <div className="flex items-center gap-2 mb-4">
            <AlertTriangle className="h-4 w-4 text-red-400" />
            <h2 className="text-[13px] font-semibold text-red-400">Low stock alerts</h2>
            <span className="ml-auto rounded-full bg-red-500 px-2 py-0.5 text-[10px] font-bold text-white">
              {lowStock.length}
            </span>
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
            {lowStock.map(s => (
              <div key={s.id} className="vf-section flex items-center gap-3 px-4 py-3">
                <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-red-500/10">
                  <AlertTriangle className="h-3.5 w-3.5 text-red-400" />
                </div>
                <div className="flex-1 min-w-0">
                  <p className="text-[13px] font-semibold vf-text-1 truncate">{s.product.name}</p>
                  <p className="text-xs vf-text-m">{s.product.sku} · {s.warehouse.name}</p>
                </div>
                <div className="text-right shrink-0">
                  <p className="text-[14px] font-bold text-red-400 tabular-nums">{s.quantity}</p>
                  <p className="text-[11px] vf-text-m">min {s.min_threshold}</p>
                </div>
              </div>
            ))}
          </div>
          <Link href="/inventory/purchase-orders/new"
            className="mt-3 flex items-center justify-center gap-1.5 rounded-xl py-2.5 text-xs font-semibold text-red-400 hover:bg-red-500/10 transition-colors"
            style={{ border: "1px solid rgba(239,68,68,0.2)" }}>
            <ShoppingCart className="h-3.5 w-3.5" />Create purchase order
          </Link>
        </div>
      )}

      {/* ── Stock table ──────────────────────────────────────────────────── */}
      <div className="vf-section">
        <div className="vf-section-header">
          <h2 className="text-[13px] font-semibold vf-text-1">All stock levels</h2>
          <div className="relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-3.5 w-3.5 vf-text-m pointer-events-none" />
            <input
              value={search}
              onChange={e => setSearch(e.target.value)}
              placeholder="Search product or SKU…"
              className="vf-input text-xs pl-8 w-52"
              style={{ height: 34 }}
            />
          </div>
        </div>

        {loading ? (
          <div>
            {[1,2,3,4].map(i => (
              <div key={i} className="flex gap-4 px-5 py-4" style={{ borderBottom: "1px solid var(--vf-divider)" }}>
                <div className="h-4 w-40 skeleton rounded" />
                <div className="h-4 w-20 skeleton rounded" />
                <div className="ml-auto h-4 w-24 skeleton rounded" />
              </div>
            ))}
          </div>
        ) : filtered.length === 0 ? (
          <div className="py-16 text-center">
            <div className="mx-auto mb-3 flex h-12 w-12 items-center justify-center rounded-2xl"
              style={{ background: "var(--vf-bg-elevated)" }}>
              <Package className="h-6 w-6 vf-text-m" />
            </div>
            <p className="text-sm font-medium vf-text-2">{search ? "No results found" : "No stock data yet"}</p>
            <p className="text-xs vf-text-m mt-1">
              {search ? "Try a different search term" : "Add products to see stock levels here"}
            </p>
          </div>
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr style={{ borderBottom: "1px solid var(--vf-border)", background: "var(--vf-bg-elevated)" }}>
                <th className="px-5 py-3 text-left text-[11px] font-semibold uppercase tracking-wide vf-text-m">Product</th>
                <th className="px-5 py-3 text-left text-[11px] font-semibold uppercase tracking-wide vf-text-m">SKU</th>
                <th className="px-5 py-3 text-left text-[11px] font-semibold uppercase tracking-wide vf-text-m hidden md:table-cell">Warehouse</th>
                <th className="px-5 py-3 text-left text-[11px] font-semibold uppercase tracking-wide vf-text-m">Stock level</th>
                <th className="px-5 py-3 text-center text-[11px] font-semibold uppercase tracking-wide vf-text-m hidden sm:table-cell">Status</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map(s => (
                <tr key={s.id} className="vf-row" style={{ borderBottom: "1px solid var(--vf-divider)" }}>
                  <td className="px-5 py-3.5">
                    <Link href={`/inventory/products/${s.product_id}`}
                      className="font-medium vf-text-1 hover:text-indigo-500 transition-colors">
                      {s.product.name}
                    </Link>
                    {s.product.category && (
                      <p className="text-xs vf-text-m mt-0.5">{s.product.category}</p>
                    )}
                  </td>
                  <td className="px-5 py-3.5 font-mono text-xs vf-text-m">{s.product.sku}</td>
                  <td className="px-5 py-3.5 text-[13px] vf-text-2 hidden md:table-cell">{s.warehouse.name}</td>
                  <td className="px-5 py-3.5">
                    <StockBar qty={s.quantity} min={s.min_threshold} />
                    <p className="text-[11px] vf-text-m mt-0.5">min {s.min_threshold} {s.product.unit}</p>
                  </td>
                  <td className="px-5 py-3.5 text-center hidden sm:table-cell">
                    {s.is_low ? (
                      <span className="pill-overdue">
                        <AlertTriangle className="h-3 w-3" />Low
                      </span>
                    ) : (
                      <span className="pill-paid">
                        <CheckCircle2 className="h-3 w-3" />OK
                      </span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
