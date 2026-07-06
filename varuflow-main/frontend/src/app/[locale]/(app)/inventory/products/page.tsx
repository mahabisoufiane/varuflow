"use client";

import { api } from "@/lib/api-client";
import { Link } from "@/i18n/navigation";
import ContentPanel from "@/components/console/ContentPanel";
import { useEffect, useRef, useState } from "react";
import { useTranslations } from "next-intl";
import { toast } from "sonner";
import {
  Package, Pencil, Plus, Search, Upload, TrendingUp, X,
} from "lucide-react";
import styles from "./page.module.scss";

const VAT_MODULE: Record<string, keyof typeof styles> = { "25": "vat25", "12": "vat12", "0": "vat0" };

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

interface Batch {
  id: string;
  product_id: string;
  warehouse_id: string;
  batch_number: string;
  expiry_date: string | null;
  quantity: number;
}

function margin(buy: string, sell: string) {
  const b = Number(buy); const s = Number(sell);
  if (s === 0) return null;
  return Math.round(((s - b) / s) * 100);
}

function VatBadge({ rate }: { rate: string }) {
  const n = Number(rate);
  return (
    <span className={styles[VAT_MODULE[String(n)] ?? "vat0"]}>{n}%</span>
  );
}

function daysUntil(iso: string): number {
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  const d = new Date(iso);
  return Math.ceil((d.getTime() - today.getTime()) / 86_400_000);
}

function ExpiryBadge({ batch, tExpiry }: { batch: Batch; tExpiry: string }) {
  if (!batch.expiry_date) {
    return (
      <span className={styles.expiryOk}>
        {batch.batch_number}
      </span>
    );
  }
  const left = daysUntil(batch.expiry_date);
  const toneClass: keyof typeof styles =
    left < 7
      ? "expirySoon"
      : left < 30
      ? "expiryWarning"
      : "expiryOk";
  return (
    <span
      title={`${tExpiry}: ${batch.expiry_date} (${batch.quantity} st)`}
      className={styles[toneClass]}
    >
      {batch.batch_number} · {left}d
    </span>
  );
}

export default function ProductsPage() {
  const [products, setProducts] = useState<Product[]>([]);
  const [total, setTotal] = useState(0);
  const [search, setSearch] = useState("");
  const [loading, setLoading] = useState(false);
  const [importing, setImporting] = useState(false);
  const [batchesByProduct, setBatchesByProduct] = useState<Record<string, Batch>>({});
  const [selected, setSelected] = useState<Product | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);
  const t = useTranslations("inventory");

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

  // Fetch every active batch in one call and index by product_id with
  // the earliest-expiring one kept (API already returns them FEFO-sorted
  // so the first match wins). Silent-fail for FREE plans that don't
  // surface the endpoint — inventory page should still render.
  async function fetchBatches() {
    try {
      const rows = await api.get<Batch[]>("/api/inventory/batches?only_active=true");
      const map: Record<string, Batch> = {};
      for (const b of rows) {
        if (!map[b.product_id]) map[b.product_id] = b;
      }
      setBatchesByProduct(map);
    } catch { /* optional enrichment */ }
  }

  useEffect(() => {
    fetchProducts();
    fetchBatches();
  }, []);

  async function handleCSVImport(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;

    // Mirror backend hard limits so the user gets an instant, local error
    // instead of waiting for a 413/415 round-trip.
    const MAX_BYTES = 5 * 1024 * 1024; // 5 MB
    const ALLOWED_EXT = /\.csv$/i;
    if (!ALLOWED_EXT.test(file.name)) {
      toast.error("Only .csv files are supported.");
      if (fileRef.current) fileRef.current.value = "";
      return;
    }
    if (file.size > MAX_BYTES) {
      toast.error("CSV is larger than 5 MB — split into smaller files.");
      if (fileRef.current) fileRef.current.value = "";
      return;
    }

    setImporting(true);
    try {
      const result = await api.upload<{
        created: number;
        updated: number;
        errors: string[];
        // Item 19 — AI auto-categorisation summary. Optional to stay
        // backward-compatible with older backends that omit the fields.
        auto_categorized?: number;
        needs_review?: number;
        ai_skipped?: boolean;
        ai_reason?: string | null;
      }>("/api/inventory/products/import", file);
      toast.success(`Imported: ${result.created} created, ${result.updated} updated`);
      // Surface AI categorisation outcome as a separate toast so the
      // merchant can tell apart the "rows I uploaded" number from the
      // "rows the AI touched" number.
      const autoCat = result.auto_categorized ?? 0;
      const review = result.needs_review ?? 0;
      if (result.ai_skipped) {
        if (result.ai_reason === "ai_not_configured") {
          toast("AI categorisation unavailable — set OPENAI_API_KEY to enable.");
        } else {
          toast("AI categorisation temporarily unavailable — categories left blank.");
        }
      } else if (autoCat > 0 || review > 0) {
        toast.success(
          `AI auto-categorised ${autoCat} product${autoCat === 1 ? "" : "s"}` +
            (review > 0 ? ` • ${review} need manual review` : ""),
        );
      }
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
          { label: "Total products",  value: total,                icon: <Package className="h-4 w-4" />,    color: "text-[var(--vf-brand-primary)] bg-blue-50"    },
          { label: "Active",          value: products.length,      icon: <Package className="h-4 w-4" />,    color: "text-emerald-600 bg-emerald-50" },
          { label: "Avg margin",      value: `${avgMargin}%`,      icon: <TrendingUp className="h-4 w-4" />, color: avgMargin < 20 ? "text-red-600 bg-red-50" : "text-[var(--vf-brand-primary)] bg-[var(--vf-brand-primary-subtle)]" },
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

      {/* Products — ContentPanel (shadcn Table + detail Sheet) */}
      {!loading && filtered.length === 0 ? (
        <div className="rounded-2xl border border-dashed border-gray-200 bg-white py-20 text-center">
          <Package className="mx-auto h-8 w-8 text-gray-200 mb-2" />
          <p className="text-sm text-gray-400">{search ? "No products match" : "No products yet"}</p>
          {!search && (
            <Link href="/inventory/products/new"
              className="mt-4 inline-flex items-center gap-1.5 rounded-lg bg-[#0d1117] px-4 py-2 text-sm font-medium text-white hover:bg-[#161b22]">
              <Plus className="h-3.5 w-3.5" />Add first product
            </Link>
          )}
        </div>
      ) : (
        <div className="overflow-hidden rounded-2xl border border-gray-200 bg-white shadow-sm">
          <ContentPanel<Product>
            hideHeader
            title="Products"
            rows={filtered}
            loading={loading}
            getRowId={(p) => p.id}
            columns={[
              { key: "name", header: "Product", render: (p) => <span className="font-semibold text-foreground">{p.name}</span> },
              { key: "sku", header: "SKU", render: (p) => <span className="font-mono text-xs text-muted-foreground">{p.sku}</span> },
              { key: "category", header: "Category", render: (p) => p.category ? <span className="rounded-full bg-gray-100 px-2 py-0.5 text-xs font-medium">{p.category}</span> : <span className="text-gray-300">—</span> },
              { key: "purchase_price", header: "Buy", className: "text-right", render: (p) => <span className="font-mono">{Number(p.purchase_price).toFixed(2)}</span> },
              { key: "sell_price", header: "Sell", className: "text-right", render: (p) => <span className="font-mono font-semibold">{Number(p.sell_price).toFixed(2)}</span> },
              { key: "margin", header: "Margin", className: "text-right", render: (p) => { const m = margin(p.purchase_price, p.sell_price); return m !== null ? <span className={`tabular-nums text-xs font-semibold ${m < 20 ? "text-red-500" : m < 40 ? "text-amber-500" : "text-emerald-600"}`}>{m}%</span> : null; } },
              { key: "tax_rate", header: "VAT", render: (p) => <VatBadge rate={p.tax_rate} /> },
              { key: "batch", header: t("batch_number"), render: (p) => { const b = batchesByProduct[p.id]; return b ? <ExpiryBadge batch={b} tExpiry={t("expiry_date")} /> : <span className="text-gray-300 text-xs">—</span>; } },
            ]}
            selected={selected}
            onSelect={setSelected}
            detailTitle={(p) => p.name}
            detailDescription={(p) => p.sku}
            renderDetail={(p) => {
              const m = margin(p.purchase_price, p.sell_price);
              const b = batchesByProduct[p.id];
              return (
                <div className="space-y-4">
                  <dl className="divide-y">
                    {([
                      ["SKU", p.sku],
                      ["Category", p.category || "—"],
                      ["Unit", p.unit],
                      ["Buy price", Number(p.purchase_price).toFixed(2)],
                      ["Sell price", Number(p.sell_price).toFixed(2)],
                      ["Margin", m !== null ? `${m}%` : "—"],
                    ] as [string, string][]).map(([label, val]) => (
                      <div key={label} className="grid grid-cols-3 gap-2 py-2.5">
                        <dt className="text-xs font-medium text-muted-foreground">{label}</dt>
                        <dd className="col-span-2 text-sm text-foreground">{val}</dd>
                      </div>
                    ))}
                    <div className="grid grid-cols-3 gap-2 py-2.5">
                      <dt className="text-xs font-medium text-muted-foreground">VAT</dt>
                      <dd className="col-span-2"><VatBadge rate={p.tax_rate} /></dd>
                    </div>
                    {b && (
                      <div className="grid grid-cols-3 gap-2 py-2.5">
                        <dt className="text-xs font-medium text-muted-foreground">{t("batch_number")}</dt>
                        <dd className="col-span-2"><ExpiryBadge batch={b} tExpiry={t("expiry_date")} /></dd>
                      </div>
                    )}
                  </dl>
                  <Link href={`/inventory/products/${p.id}`}
                    className="inline-flex items-center gap-1.5 rounded-lg bg-[#0d1117] px-4 py-2 text-sm font-medium text-white hover:bg-[#161b22]">
                    <Pencil className="h-3.5 w-3.5" />Edit product
                  </Link>
                </div>
              );
            }}
          />
        </div>
      )}
    </div>
  );
}
