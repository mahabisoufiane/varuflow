"use client";

import { api } from "@/lib/api-client";
import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { toast } from "sonner";
import {
  Package, Pencil, Plus, Search, Upload, TrendingUp, X, ScanLine,
} from "lucide-react";

interface Product {
  id: string;
  name: string;
  sku: string;
  category: string | null;
  unit: string;
  purchase_price: string;
  sell_price: string;
  tax_rate: string;
  is_active: boolean;
}

function margin(buy: string, sell: string) {
  const b = Number(buy); const s = Number(sell);
  if (s === 0) return null;
  return Math.round(((s - b) / s) * 100);
}

function VatBadge({ rate }: { rate: string }) {
  const n = Number(rate);
  const cls = n === 25 ? "bg-blue-50 text-blue-600 border-blue-200"
    : n === 12 ? "bg-purple-50 text-purple-600 border-purple-200"
    : "bg-gray-100 text-gray-500 border-gray-200";
  return (
    <span className={`inline-flex rounded-full border px-2 py-0.5 text-[10px] font-bold ${cls}`}>{n}%</span>
  );
}

export default function ProductsPage() {
  const [products, setProducts] = useState<Product[]>([]);
  const [total, setTotal] = useState(0);
  const [search, setSearch] = useState("");
  const [loading, setLoading] = useState(false);
  const [importing, setImporting] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);

  async function fetchProducts(q = "") {
    setLoading(true);
    try {
      const params = new URLSearchParams({ limit: "100", is_active: "true" });
      if (q) params.set("search", q);
      const data = await api.get<{ items: Product[]; total: number }>(`/api/inventory/products?${params}`);
      setProducts(data.items);
      setTotal(data.total);
    } catch (e: unknown) { toast.error((e as Error).message); }
    finally { setLoading(false); }
  }

  useEffect(() => { fetchProducts(); }, []);

  async function handleCSVImport(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    setImporting(true);
    try {
      const result = await api.upload<{ created: number; updated: number; errors: string[] }>("/api/inventory/products/import", file);
      toast.success(`Imported: ${result.created} created, ${result.updated} updated`);
      fetchProducts();
    } catch (e: unknown) { toast.error((e as Error).message); }
    finally { setImporting(false); if (fileRef.current) fileRef.current.value = ""; }
  }

  // Live search
  const filtered = products.filter(p =>
    p.name.toLowerCase().includes(search.toLowerCase()) ||
    p.sku.toLowerCase().includes(search.toLowerCase()) ||
    (p.category ?? "").toLowerCase().includes(search.toLowerCase())
  );

  const avgMargin = products.length > 0
    ? Math.round(products.reduce((s, p) => {
        const m = margin(p.purchase_price, p.sell_price);
        return s + (m ?? 0);
      }, 0) / products.length)
    : 0;

  return (
    <div className="space-y-6">

      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-[22px] font-bold tracking-tight text-gray-900">Products</h1>
          <p className="text-xs text-gray-400 mt-0.5">{total} products in catalog</p>
        </div>
        <div className="flex gap-2">
          <input ref={fileRef} type="file" accept=".csv" className="hidden" onChange={handleCSVImport} />
          <button
            disabled={importing}
            onClick={() => fileRef.current?.click()}
            className="inline-flex items-center gap-1.5 rounded-lg border border-gray-200 bg-white px-3 py-1.5 text-sm font-medium text-gray-600 shadow-sm hover:bg-gray-50 transition-colors disabled:opacity-50"
          >
            <Upload className="h-3.5 w-3.5" />{importing ? "Importing…" : "Import CSV"}
          </button>
          <Link
            href="/inventory/products/scan"
            className="inline-flex items-center gap-1.5 rounded-lg bg-gradient-to-br from-indigo-500 to-indigo-600 px-3 py-1.5 text-sm font-semibold text-white shadow-sm hover:shadow-md transition-all"
          >
            <ScanLine className="h-3.5 w-3.5" />Scan
          </Link>
          <Link
            href="/inventory/products/new"
            className="inline-flex items-center gap-1.5 rounded-lg bg-[#0d1117] px-3 py-1.5 text-sm font-medium text-white shadow-sm hover:bg-[#161b22] transition-colors"
          >
            <Plus className="h-3.5 w-3.5" />New product
          </Link>
        </div>
      </div>

      {/* KPI strip */}
      <div className="grid grid-cols-3 gap-3">
        {[
          { label: "Total products",  value: total,                icon: <Package className="h-4 w-4" />,    color: "text-blue-600 bg-blue-50"    },
          { label: "Active",          value: products.length,      icon: <Package className="h-4 w-4" />,    color: "text-emerald-600 bg-emerald-50" },
          { label: "Avg margin",      value: `${avgMargin}%`,      icon: <TrendingUp className="h-4 w-4" />, color: avgMargin < 20 ? "text-red-600 bg-red-50" : "text-indigo-600 bg-indigo-50" },
        ].map(({ label, value, icon, color }) => (
          <div key={label} className="rounded-xl border border-gray-200 bg-white p-4 shadow-sm">
            <div className={`inline-flex h-8 w-8 items-center justify-center rounded-lg ${color} mb-3`}>{icon}</div>
            <p className="text-2xl font-bold tabular-nums text-gray-900">{value}</p>
            <p className="text-xs text-gray-400 mt-0.5">{label}</p>
          </div>
        ))}
      </div>

      {/* Search */}
      <div className="relative">
        <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-gray-400" />
        <input
          value={search}
          onChange={e => setSearch(e.target.value)}
          placeholder="Search by name, SKU, or category…"
          className="w-full rounded-xl border border-gray-200 bg-white py-2.5 pl-9 pr-9 text-sm text-gray-700 placeholder-gray-400 shadow-sm outline-none focus:border-gray-400 transition-colors"
        />
        {search && (
          <button onClick={() => setSearch("")} className="absolute right-3 top-1/2 -translate-y-1/2">
            <X className="h-4 w-4 text-gray-400" />
          </button>
        )}
      </div>
      <p className="text-[11px] text-gray-400 -mt-3">
        CSV format: <code className="rounded bg-gray-100 px-1">name, sku, category, unit, purchase_price, sell_price, tax_rate</code>
      </p>

      {/* Table */}
      {loading ? (
        <div className="divide-y rounded-2xl border border-gray-200 bg-white shadow-sm">
          {[1,2,3,4,5].map(i => (
            <div key={i} className="flex gap-4 px-5 py-4 animate-pulse">
              <div className="h-4 w-40 rounded bg-gray-100" /><div className="h-4 w-20 rounded bg-gray-100" />
              <div className="ml-auto h-4 w-16 rounded bg-gray-100" />
            </div>
          ))}
        </div>
      ) : filtered.length === 0 ? (
        <div className="rounded-2xl border border-dashed border-gray-200 bg-white py-20 text-center">
          <Package className="mx-auto h-8 w-8 text-gray-200 mb-2" />
          <p className="text-sm text-gray-400">{search ? "No products match" : "No products yet"}</p>
          {!search && (
            <div className="mt-4 flex items-center justify-center gap-2">
              <Link href="/inventory/products/scan"
                className="inline-flex items-center gap-1.5 rounded-lg bg-gradient-to-br from-indigo-500 to-indigo-600 px-4 py-2 text-sm font-semibold text-white hover:shadow-md">
                <ScanLine className="h-3.5 w-3.5" />Scan first product
              </Link>
              <Link href="/inventory/products/new"
                className="inline-flex items-center gap-1.5 rounded-lg bg-[#0d1117] px-4 py-2 text-sm font-medium text-white hover:bg-[#161b22]">
                <Plus className="h-3.5 w-3.5" />Add manually
              </Link>
            </div>
          )}
        </div>
      ) : (
        <div className="rounded-2xl border border-gray-200 bg-white shadow-sm overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-100 bg-gray-50/70">
                {["Product", "SKU", "Category", "Buy", "Sell", "Margin", "VAT", ""].map(h => (
                  <th key={h} className={`px-4 py-3 text-[11px] font-semibold uppercase tracking-wide text-gray-400 ${h === "" ? "" : h === "Buy" || h === "Sell" || h === "Margin" ? "text-right" : "text-left"}`}>
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-50">
              {filtered.map(p => {
                const mgn = margin(p.purchase_price, p.sell_price);
                return (
                  <tr key={p.id} className="hover:bg-gray-50/70 transition-colors">
                    <td className="px-4 py-3.5">
                      <span className="font-semibold text-gray-900">{p.name}</span>
                    </td>
                    <td className="px-4 py-3.5 font-mono text-xs text-gray-400">{p.sku}</td>
                    <td className="px-4 py-3.5 text-gray-500">
                      {p.category ? (
                        <span className="rounded-full bg-gray-100 px-2 py-0.5 text-xs font-medium">{p.category}</span>
                      ) : <span className="text-gray-300">—</span>}
                    </td>
                    <td className="px-4 py-3.5 text-right font-mono text-gray-600">{Number(p.purchase_price).toFixed(2)}</td>
                    <td className="px-4 py-3.5 text-right font-mono font-semibold text-gray-900">{Number(p.sell_price).toFixed(2)}</td>
                    <td className="px-4 py-3.5 text-right">
                      {mgn !== null && (
                        <span className={`tabular-nums text-xs font-semibold ${mgn < 20 ? "text-red-500" : mgn < 40 ? "text-amber-500" : "text-emerald-600"}`}>
                          {mgn}%
                        </span>
                      )}
                    </td>
                    <td className="px-4 py-3.5 text-center"><VatBadge rate={p.tax_rate} /></td>
                    <td className="px-4 py-3.5 text-right">
                      <Link
                        href={`/inventory/products/${p.id}`}
                        className="inline-flex h-7 w-7 items-center justify-center rounded-lg hover:bg-gray-100 text-gray-400 hover:text-gray-700 transition-colors"
                      >
                        <Pencil className="h-3.5 w-3.5" />
                      </Link>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
