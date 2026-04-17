"use client";

/**
 * Mobile-first scan-to-add flow.
 *
 * Core UX:
 *  1. User opens /inventory/products/scan on phone.
 *  2. Camera opens full-screen; point at barcode; haptic buzz on read.
 *  3. If the code already exists in org → show product card with
 *     "+1 / +5 / +10" stock-in buttons (single tap = stock movement).
 *  4. If unknown → fetch Open Food Facts for name/brand/category
 *     pre-fill; show MINIMAL form (name, sell price, purchase price).
 *     Tap save → product created → flash confirmation → scanner resumes.
 *
 * Why this matters:
 *  Traditional "add product" flows take 30–60 seconds of typing per SKU.
 *  Scan-first flow drops to 5–10 seconds: scan → accept pre-fill → price → save.
 */

import { useCallback, useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { toast } from "sonner";
import {
  Camera, CheckCircle2, Loader2, Plus, ScanLine, X, Package, ArrowLeft,
} from "lucide-react";
import { Link } from "@/i18n/navigation";
import BarcodeScanner from "@/components/app/BarcodeScanner";
import { api } from "@/lib/api-client";
import { useMoney } from "@/hooks/useMoney";

type Product = {
  id: string;
  name: string;
  sku: string;
  barcode: string | null;
  sell_price: string | number;
  purchase_price: string | number;
  unit: string;
};

type BarcodeLookup = {
  found: boolean;
  barcode: string;
  name?: string | null;
  brand?: string | null;
  category?: string | null;
  quantity?: string | null;
  image_url?: string | null;
};

type Warehouse = { id: string; name: string };

/* ── Haptic helper ─────────────────────────────────────────────────────────── */
function buzz(ms = 40) {
  if (typeof navigator !== "undefined" && "vibrate" in navigator) {
    navigator.vibrate(ms);
  }
}

export default function ProductScanPage() {
  const router = useRouter();
  const params = useParams();
  const locale = (params?.locale as string) ?? "en";
  const { fmt, code: currencyCode, config } = useMoney();

  const [scanning, setScanning] = useState(true);
  const [processing, setProcessing] = useState(false);
  const [existing, setExisting] = useState<Product | null>(null);
  const [lookup, setLookup] = useState<BarcodeLookup | null>(null);
  const [warehouses, setWarehouses] = useState<Warehouse[]>([]);
  const [defaultWh, setDefaultWh] = useState<string | null>(null);

  const [form, setForm] = useState({
    name: "",
    sku: "",
    purchase_price: "",
    sell_price: "",
  });

  /* ── Load warehouses once (so +N quick-add knows where to write) ────────── */
  useEffect(() => {
    api
      .get<Warehouse[]>("/api/inventory/warehouses")
      .then((list) => {
        setWarehouses(list);
        if (list.length > 0) setDefaultWh(list[0].id);
      })
      .catch(() => { /* ignore — we only need wh for quick-add */ });
  }, []);

  /* ── The scan pipeline ──────────────────────────────────────────────────── */
  const handleScan = useCallback(async (code: string) => {
    buzz(50);
    setScanning(false);
    setProcessing(true);
    setExisting(null);
    setLookup(null);

    try {
      // Step 1 — does this org already stock this barcode?
      const known = await api.get<Product | null>(
        `/api/inventory/products/by-barcode/${encodeURIComponent(code)}`
      );
      if (known && known.id) {
        setExisting(known);
        setProcessing(false);
        return;
      }

      // Step 2 — unknown → hit Open Food Facts to pre-fill.
      const lk = await api.get<BarcodeLookup>(
        `/api/inventory/products/barcode-lookup/${encodeURIComponent(code)}`
      );
      setLookup(lk);
      setForm({
        name: lk.found ? (lk.name || lk.brand || "") : "",
        sku: `SKU-${code.slice(-6)}`,
        purchase_price: "",
        sell_price: "",
      });
    } catch (e: unknown) {
      toast.error((e as Error).message ?? "Scan failed");
      setScanning(true);
    } finally {
      setProcessing(false);
    }
  }, []);

  /* ── Quick stock-in for an existing product (tap +N) ────────────────────── */
  async function quickStockIn(qty: number) {
    if (!existing || !defaultWh) return;
    setProcessing(true);
    try {
      await api.post("/api/inventory/movements", {
        product_id: existing.id,
        warehouse_id: defaultWh,
        quantity: qty,
        type: "IN",
        note: "Scan received",
      });
      buzz(30);
      toast.success(`+${qty} ${existing.unit} of ${existing.name}`);
      reset();
    } catch (e: unknown) {
      toast.error((e as Error).message ?? "Stock-in failed");
    } finally {
      setProcessing(false);
    }
  }

  /* ── Create the new product ─────────────────────────────────────────────── */
  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    if (!lookup) return;
    setProcessing(true);
    try {
      await api.post("/api/inventory/products", {
        name: form.name.trim(),
        sku: form.sku.trim() || `SKU-${lookup.barcode.slice(-6)}`,
        barcode: lookup.barcode,
        unit: "st",
        purchase_price: form.purchase_price || "0.01",
        sell_price: form.sell_price || "0.01",
        tax_rate: String(config?.vat.standard_rate_pct ?? 25),
        category: lookup.category || null,
      });
      buzz(60);
      toast.success(`Added ${form.name}`);
      reset();
    } catch (e: unknown) {
      const msg = (e as Error).message ?? "Create failed";
      // duplicate SKU — retry with a unique one
      if (msg.toLowerCase().includes("sku") && msg.toLowerCase().includes("exists")) {
        setForm((f) => ({ ...f, sku: `${f.sku}-${Date.now().toString().slice(-4)}` }));
        toast.error("SKU exists — retry with new suffix.");
      } else {
        toast.error(msg);
      }
    } finally {
      setProcessing(false);
    }
  }

  function reset() {
    setExisting(null);
    setLookup(null);
    setForm({ name: "", sku: "", purchase_price: "", sell_price: "" });
    setScanning(true);
  }

  /* ── Render ─────────────────────────────────────────────────────────────── */
  return (
    <div className="mx-auto max-w-md space-y-4 pb-20">
      {/* Header */}
      <div className="flex items-center justify-between">
        <Link
          href="/inventory/products"
          className="flex items-center gap-1.5 text-sm vf-text-m hover:vf-text-1"
        >
          <ArrowLeft className="h-4 w-4" /> Products
        </Link>
        <div className="flex items-center gap-1.5 rounded-full px-2.5 py-1 text-[11px] font-medium"
          style={{ background: "rgba(99,102,241,0.1)", color: "rgb(129,140,248)" }}>
          <ScanLine className="h-3 w-3" /> Scan mode
        </div>
      </div>

      <div>
        <h1 className="text-2xl font-bold vf-text-1">Scan to add</h1>
        <p className="text-sm vf-text-m mt-0.5">
          Point your camera at any barcode. We&apos;ll auto-detect if it&apos;s already
          in stock, or pre-fill a new product from the global catalogue.
        </p>
      </div>

      {/* Scanner — full-width on mobile */}
      {scanning && (
        <BarcodeScanner
          onResult={handleScan}
          onClose={() => router.push(`/${locale}/inventory/products`)}
        />
      )}

      {/* Processing */}
      {processing && !existing && !lookup && (
        <div className="vf-section p-8 text-center space-y-3" style={{ borderRadius: 16 }}>
          <Loader2 className="h-6 w-6 animate-spin mx-auto vf-text-m" />
          <p className="text-sm vf-text-m">Looking up barcode…</p>
        </div>
      )}

      {/* Known product — quick +N buttons */}
      {existing && (
        <div className="vf-section p-5 space-y-4" style={{ borderRadius: 16 }}>
          <div className="flex items-start gap-3">
            <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl"
              style={{ background: "rgba(34,197,94,0.1)" }}>
              <CheckCircle2 className="h-5 w-5 text-emerald-400" />
            </div>
            <div className="min-w-0 flex-1">
              <p className="text-[11px] font-semibold uppercase tracking-widest text-emerald-400">
                Already in stock
              </p>
              <h2 className="text-base font-bold vf-text-1 truncate">{existing.name}</h2>
              <p className="text-xs vf-text-m truncate">
                SKU {existing.sku} · {fmt(Number(existing.sell_price))} / {existing.unit}
              </p>
            </div>
          </div>

          <div className="grid grid-cols-3 gap-2">
            {[1, 5, 10].map((n) => (
              <button
                key={n}
                onClick={() => quickStockIn(n)}
                disabled={processing || !defaultWh}
                className="flex flex-col items-center justify-center gap-0.5 rounded-xl py-4 text-base font-bold vf-btn disabled:opacity-40"
              >
                <Plus className="h-4 w-4 opacity-60" />+{n}
              </button>
            ))}
          </div>

          {!defaultWh && warehouses.length === 0 && (
            <p className="text-[11px] text-amber-400">
              Create a warehouse first to log stock movements.
            </p>
          )}
          {warehouses.length > 1 && defaultWh && (
            <select
              value={defaultWh}
              onChange={(e) => setDefaultWh(e.target.value)}
              className="vf-input w-full text-xs"
            >
              {warehouses.map((w) => (
                <option key={w.id} value={w.id}>Receive into {w.name}</option>
              ))}
            </select>
          )}

          <button
            onClick={reset}
            className="flex w-full items-center justify-center gap-2 rounded-xl py-2.5 text-sm vf-btn-ghost"
          >
            <Camera className="h-4 w-4" /> Scan another
          </button>
        </div>
      )}

      {/* Unknown product — minimal create form */}
      {lookup && !existing && (
        <form
          onSubmit={handleCreate}
          className="vf-section p-5 space-y-4"
          style={{ borderRadius: 16 }}
        >
          <div className="flex items-start gap-3">
            {lookup.image_url ? (
              <img
                src={lookup.image_url}
                alt=""
                className="h-14 w-14 rounded-xl object-cover shrink-0"
                style={{ background: "var(--vf-bg-elevated)" }}
              />
            ) : (
              <div className="flex h-14 w-14 shrink-0 items-center justify-center rounded-xl"
                style={{ background: "rgba(99,102,241,0.1)" }}>
                <Package className="h-6 w-6 text-indigo-400" />
              </div>
            )}
            <div className="min-w-0 flex-1">
              <p className="text-[11px] font-semibold uppercase tracking-widest"
                style={{ color: lookup.found ? "rgb(129,140,248)" : "var(--vf-text-muted)" }}>
                {lookup.found ? "Found in global catalogue" : "New product"}
              </p>
              <p className="text-xs vf-text-m mt-0.5 font-mono truncate">{lookup.barcode}</p>
              {lookup.brand && <p className="text-xs vf-text-m">{lookup.brand}</p>}
            </div>
            <button
              type="button"
              onClick={reset}
              className="shrink-0 rounded-full p-1.5 vf-text-m hover:vf-text-1"
            >
              <X className="h-4 w-4" />
            </button>
          </div>

          <div className="space-y-2">
            <label className="text-[11px] font-semibold uppercase tracking-widest vf-text-m">
              Product name
            </label>
            <input
              required
              value={form.name}
              onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))}
              placeholder="Ekologisk havregryn"
              className="vf-input w-full text-base"
              autoFocus={!form.name}
            />
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-2">
              <label className="text-[11px] font-semibold uppercase tracking-widest vf-text-m">
                Buy price
              </label>
              <input
                required
                type="number"
                step="0.01"
                inputMode="decimal"
                value={form.purchase_price}
                onChange={(e) => setForm((f) => ({ ...f, purchase_price: e.target.value }))}
                placeholder="0.00"
                className="vf-input w-full text-base tabular-nums"
              />
            </div>
            <div className="space-y-2">
              <label className="text-[11px] font-semibold uppercase tracking-widest vf-text-m">
                Sell price ({currencyCode})
              </label>
              <input
                required
                type="number"
                step="0.01"
                inputMode="decimal"
                value={form.sell_price}
                onChange={(e) => setForm((f) => ({ ...f, sell_price: e.target.value }))}
                placeholder="0.00"
                className="vf-input w-full text-base tabular-nums"
              />
            </div>
          </div>

          <details className="text-xs">
            <summary className="cursor-pointer vf-text-m">Advanced</summary>
            <div className="mt-2 space-y-2">
              <input
                value={form.sku}
                onChange={(e) => setForm((f) => ({ ...f, sku: e.target.value }))}
                placeholder="SKU"
                className="vf-input w-full"
              />
            </div>
          </details>

          <button
            type="submit"
            disabled={processing || !form.name || !form.sell_price}
            className="flex w-full items-center justify-center gap-2 rounded-xl py-3.5 text-base font-semibold vf-btn disabled:opacity-40"
          >
            {processing ? (
              <><Loader2 className="h-4 w-4 animate-spin" /> Saving…</>
            ) : (
              <><Plus className="h-4 w-4" /> Add product</>
            )}
          </button>
        </form>
      )}

      {/* Idle — show a 'resume scan' button so the user can dismiss and restart */}
      {!scanning && !processing && !existing && !lookup && (
        <button
          onClick={() => setScanning(true)}
          className="flex w-full items-center justify-center gap-2 rounded-xl py-3.5 text-base font-semibold vf-btn"
        >
          <Camera className="h-5 w-5" /> Start scanning
        </button>
      )}
    </div>
  );
}
