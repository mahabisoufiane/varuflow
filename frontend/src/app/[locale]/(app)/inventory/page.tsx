"use client";

import { api } from "@/lib/api-client";
import { Link } from "@/i18n/navigation";
import { useEffect, useState } from "react";
import { toast } from "sonner";
import { cn } from "@/lib/utils";
import {
  AlertTriangle, ArrowRight, CheckCircle2, Package,
  Plus, TrendingDown, Warehouse, Activity, ShoppingCart,
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
      <div className="h-1.5 w-16 rounded-full bg-white/[0.08] overflow-hidden">
        <div className={cn("h-full rounded-full transition-all", color)} style={{ width: `${pct}%` }} />
      </div>
      <span className="tabular-nums text-[13px] font-semibold text-slate-200">{qty}</span>
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
    { href: "/inventory/products",        icon: Package,      label: "Products",       sub: `${totalProducts} items`       },
    { href: "/inventory/warehouses",      icon: Warehouse,    label: "Warehouses",     sub: `${totalWarehouses} locations` },
    { href: "/inventory/movements",       icon: Activity,     label: "Movements",      sub: "Record stock in/out"          },
    { href: "/inventory/purchase-orders", icon: ShoppingCart, label: "Purchase Orders",sub: "Reorder from suppliers"       },
  ];

  return (
    <div className="space-y-6">

      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-[22px] font-bold tracking-tight text-slate-100">Inventory</h1>
          <p className="text-xs text-slate-600 mt-0.5">Stock levels across all warehouses</p>
        </div>
        <Link href="/inventory/products/new" className="vf-btn text-xs px-3 py-1.5 h-auto">
          <Plus className="h-3.5 w-3.5" />Add product
        </Link>
      </div>

      {/* KPI strip */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        {[
          { label: "Products",   value: totalProducts,   icon: <Package className="h-4 w-4" />,     col: "text-indigo-400 bg-indigo-500/10"  },
          { label: "Warehouses", value: totalWarehouses, icon: <Warehouse className="h-4 w-4" />,   col: "text-violet-400 bg-violet-500/10"  },
          { label: "Low stock",  value: lowStock.length, icon: <TrendingDown className="h-4 w-4" />,col: lowStock.length > 0 ? "text-red-400 bg-red-500/10" : "text-slate-500 bg-white/5" },
          { label: "Healthy",    value: healthyCount,    icon: <CheckCircle2 className="h-4 w-4" />,col: "text-emerald-400 bg-emerald-500/10" },
        ].map(({ label, value, icon, col }) => (
          <div key={label} className="rounded-xl border border-white/[0.06] bg-vf-surface p-4">
            <div className={cn("inline-flex h-8 w-8 items-center justify-center rounded-lg mb-3", col)}>{icon}</div>
            <p className="text-2xl font-bold tabular-nums text-slate-100">{loading ? "—" : value}</p>
            <p className="text-xs text-slate-600 mt-0.5">{label}</p>
          </div>
        ))}
      </div>

      {/* Nav tiles */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        {NAV_TILES.map(({ href, icon: Icon, label, sub }) => (
          <Link key={href} href={href}
            className="group flex items-center gap-3 rounded-xl border border-white/[0.06] bg-vf-surface p-4 hover:border-white/[0.10] hover:bg-vf-elevated transition-all">
            <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-white/[0.04] group-hover:bg-white/[0.07] transition-colors">
              <Icon className="h-4 w-4 text-slate-400 group-hover:text-slate-200 transition-colors" />
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-[13px] font-semibold text-slate-200">{label}</p>
              <p className="text-xs text-slate-600 truncate">{sub}</p>
            </div>
            <ArrowRight className="h-4 w-4 shrink-0 text-slate-700 group-hover:text-slate-500 transition-colors" />
          </Link>
        ))}
      </div>

      {/* Low stock alerts */}
      {!loading && lowStock.length > 0 && (
        <div className="rounded-xl border border-red-500/20 bg-red-500/5 p-4">
          <div className="flex items-center gap-2 mb-3">
            <AlertTriangle className="h-4 w-4 text-red-400" />
            <h2 className="text-[13px] font-semibold text-red-300">Low stock alerts</h2>
            <span className="ml-auto rounded-full bg-red-600 px-2 py-0.5 text-[10px] font-bold text-white">{lowStock.length}</span>
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
            {lowStock.map(s => (
              <div key={s.id} className="flex items-center gap-3 rounded-xl border border-red-500/15 bg-vf-surface px-4 py-3">
                <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-red-500/10">
                  <AlertTriangle className="h-3.5 w-3.5 text-red-400" />
                </div>
                <div className="flex-1 min-w-0">
                  <p className="text-[13px] font-semibold text-slate-200 truncate">{s.product.name}</p>
                  <p className="text-xs text-slate-600">{s.product.sku} · {s.warehouse.name}</p>
                </div>
                <div className="text-right shrink-0">
                  <p className="text-[13px] font-bold text-red-400 tabular-nums">{s.quantity}</p>
                  <p className="text-[11px] text-slate-600">min {s.min_threshold}</p>
                </div>
              </div>
            ))}
          </div>
          <Link href="/inventory/purchase-orders/new"
            className="mt-3 flex items-center justify-center gap-1.5 rounded-xl border border-red-500/20 bg-red-500/5 py-2 text-xs font-semibold text-red-400 hover:bg-red-500/10 transition-colors">
            <ShoppingCart className="h-3.5 w-3.5" />Create purchase order
          </Link>
        </div>
      )}

      {/* Stock table */}
      <div className="rounded-xl border border-white/[0.06] bg-vf-surface overflow-hidden">
        <div className="flex items-center justify-between px-5 py-4 border-b border-white/[0.06]">
          <h2 className="text-[13px] font-semibold text-slate-200">All stock levels</h2>
          <input
            value={search}
            onChange={e => setSearch(e.target.value)}
            placeholder="Search product or SKU…"
            className="vf-input text-xs py-1.5 px-3 h-auto w-52"
          />
        </div>

        {loading ? (
          <div className="divide-y divide-white/[0.04]">
            {[1,2,3,4].map(i => (
              <div key={i} className="flex gap-4 px-5 py-4">
                <div className="h-4 w-40 skeleton rounded" />
                <div className="h-4 w-20 skeleton rounded" />
                <div className="ml-auto h-4 w-24 skeleton rounded" />
              </div>
            ))}
          </div>
        ) : filtered.length === 0 ? (
          <div className="py-16 text-center">
            <Package className="mx-auto h-8 w-8 text-slate-700 mb-2" />
            <p className="text-sm text-slate-600">{search ? "No results" : "No stock data yet"}</p>
          </div>
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-white/[0.06] bg-white/[0.02]">
                <th className="px-5 py-3 text-left text-[11px] font-semibold uppercase tracking-wide text-slate-600">Product</th>
                <th className="px-5 py-3 text-left text-[11px] font-semibold uppercase tracking-wide text-slate-600">SKU</th>
                <th className="px-5 py-3 text-left text-[11px] font-semibold uppercase tracking-wide text-slate-600">Warehouse</th>
                <th className="px-5 py-3 text-left text-[11px] font-semibold uppercase tracking-wide text-slate-600">Stock level</th>
                <th className="px-5 py-3 text-center text-[11px] font-semibold uppercase tracking-wide text-slate-600">Status</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-white/[0.04]">
              {filtered.map(s => (
                <tr key={s.id} className="hover:bg-white/[0.03] transition-colors">
                  <td className="px-5 py-3.5">
                    <Link href={`/inventory/products/${s.product_id}`}
                      className="font-medium text-slate-200 hover:text-indigo-400 transition-colors">
                      {s.product.name}
                    </Link>
                    {s.product.category && (
                      <p className="text-xs text-slate-600">{s.product.category}</p>
                    )}
                  </td>
                  <td className="px-5 py-3.5 font-mono text-xs text-slate-500">{s.product.sku}</td>
                  <td className="px-5 py-3.5 text-[13px] text-slate-400">{s.warehouse.name}</td>
                  <td className="px-5 py-3.5">
                    <StockBar qty={s.quantity} min={s.min_threshold} />
                    <p className="text-[11px] text-slate-600 mt-0.5">min {s.min_threshold} {s.product.unit}</p>
                  </td>
                  <td className="px-5 py-3.5 text-center">
                    {s.is_low ? (
                      <span className="inline-flex items-center gap-1 rounded-full bg-red-500/10 border border-red-500/20 px-2 py-0.5 text-[11px] font-semibold text-red-400">
                        <AlertTriangle className="h-3 w-3" />Low
                      </span>
                    ) : (
                      <span className="inline-flex items-center gap-1 rounded-full bg-emerald-500/10 border border-emerald-500/20 px-2 py-0.5 text-[11px] font-semibold text-emerald-400">
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
