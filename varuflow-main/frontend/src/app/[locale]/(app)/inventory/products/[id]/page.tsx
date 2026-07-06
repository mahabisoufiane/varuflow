"use client";

import { api } from "@/lib/api-client";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { useRouter, useParams } from "next/navigation";
import { useEffect, useState } from "react";
import { Link } from "@/i18n/navigation";
import { ArrowLeft, Trash2 } from "lucide-react";
import { toast } from "sonner";
import dynamic from "next/dynamic";
import type { OFFResult } from "@/components/barcode/BarcodeInput";

// Lazy-load: BarcodeInput pulls react-zxing (the multi-MB @zxing decoder) —
// see products/new/page.tsx for why a static import is prohibitive here.
const BarcodeInput = dynamic(() => import("@/components/barcode/BarcodeInput"), { ssr: false });

const TAX_RATES = [
  { label: "25% — Standard", value: "25" },
  { label: "12% — Food / Hospitality", value: "12" },
  { label: "6% — Books / Transport", value: "6" },
];

const UNITS = ["st", "kg", "g", "l", "ml", "m", "cm", "box", "pall", "karton", "par"];

interface Product {
  id: string; name: string; sku: string; barcode: string | null;
  category: string | null; unit: string; purchase_price: string;
  sell_price: string; tax_rate: string; description: string | null; is_active: boolean;
}

export default function EditProductPage() {
  const router = useRouter();
  const { id } = useParams<{ id: string }>();

  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [form, setForm] = useState({
    name: "", sku: "", barcode: "", category: "", unit: "st",
    purchase_price: "", sell_price: "", tax_rate: "25", description: "",
  });

  function set(field: string, value: string) {
    setForm((f) => ({ ...f, [field]: value }));
  }

  useEffect(() => {
    api.get<Product>(`/api/inventory/products/${id}`)
      .then((p) => setForm({
        name: p.name, sku: p.sku, barcode: p.barcode ?? "",
        category: p.category ?? "", unit: p.unit,
        purchase_price: p.purchase_price, sell_price: p.sell_price,
        tax_rate: String(Math.round(Number(p.tax_rate))),
        description: p.description ?? "",
      }))
      .catch((e: Error) => setError(e.message))
      .finally(() => setLoading(false));
  }, [id]);

  function handleProductLookup(data: OFFResult) {
    let filled = 0;
    setForm((f) => {
      const next = { ...f };
      if (!next.name && data.name) { next.name = data.name; filled++; }
      if (!next.category && data.category) { next.category = data.category; filled++; }
      return next;
    });
    if (filled > 0) {
      toast.success(`Auto-filled ${filled} field${filled > 1 ? "s" : ""} from OpenFoodFacts`);
    } else {
      toast.info("Fields already filled — no changes made");
    }
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    setError(null);
    try {
      await api.put(`/api/inventory/products/${id}`, {
        name: form.name, sku: form.sku,
        barcode: form.barcode || null,
        category: form.category || null, unit: form.unit,
        purchase_price: form.purchase_price, sell_price: form.sell_price,
        tax_rate: form.tax_rate, description: form.description || null,
      });
      router.push("/inventory/products");
    } catch (e: unknown) {
      setError((e as Error).message);
    } finally {
      setSaving(false);
    }
  }

  async function handleDeactivate() {
    if (!confirm("Deactivate this product?")) return;
    try {
      await api.delete<void>(`/api/inventory/products/${id}`);
      router.push("/inventory/products");
    } catch (e: unknown) {
      setError((e as Error).message);
    }
  }

  if (loading) {
    return (
      <div className="mx-auto max-w-2xl">
        <div className="h-8 w-48 animate-pulse rounded bg-gray-200 dark:bg-gray-700" />
        <div className="mt-6 h-80 animate-pulse rounded-xl bg-gray-100 dark:bg-gray-800" />
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-2xl space-y-6">
      <div className="flex items-start justify-between">
        <div>
          <Button asChild variant="ghost" size="sm" className="mb-2 -ml-2 text-muted-foreground">
            <Link href="/inventory/products"><ArrowLeft className="mr-1 h-3.5 w-3.5" />Products</Link>
          </Button>
          <h1 className="text-2xl font-bold text-[var(--vf-text-primary)] dark:text-gray-100">Edit Product</h1>
        </div>
        <Button variant="ghost" size="sm" className="text-red-500 hover:text-red-700 hover:bg-red-50" onClick={handleDeactivate}>
          <Trash2 className="h-4 w-4 mr-1.5" />Deactivate
        </Button>
      </div>

      <form onSubmit={handleSubmit} className="space-y-5 rounded-xl border bg-white p-6 dark:border-gray-700 dark:bg-gray-800">
        <div className="grid grid-cols-2 gap-4">
          <Field id="name" label="Name *" value={form.name} onChange={(v) => set("name", v)} required />
          <Field id="sku" label="SKU *" value={form.sku} onChange={(v) => set("sku", v)} required />
        </div>

        {/* Barcode — full-width with camera + hardware scanner */}
        <div className="space-y-1.5">
          <Label htmlFor="barcode">Barcode (EAN / Code128 / QR)</Label>
          <BarcodeInput
            id="barcode"
            value={form.barcode}
            onChange={(v) => set("barcode", v)}
            onProductLookup={handleProductLookup}
            placeholder="7310865085313"
          />
        </div>

        <div className="grid grid-cols-2 gap-4">
          <Field id="category" label="Category" value={form.category} onChange={(v) => set("category", v)} />
          <div className="space-y-1.5">
            <Label htmlFor="unit">Unit</Label>
            <select
              id="unit"
              value={form.unit}
              onChange={(e) => set("unit", e.target.value)}
              className="block h-10 w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-[var(--vf-brand-primary)] focus:outline-none focus:ring-1 focus:ring-[var(--vf-brand-primary)] dark:border-gray-600 dark:bg-gray-700 dark:text-gray-100"
            >
              {UNITS.map((u) => <option key={u} value={u}>{u}</option>)}
            </select>
          </div>
        </div>

        <div className="grid grid-cols-2 gap-4">
          <Field id="purchase_price" label="Purchase price (SEK) *" type="number" step="0.01" value={form.purchase_price} onChange={(v) => set("purchase_price", v)} required />
          <Field id="sell_price" label="Sell price (SEK) *" type="number" step="0.01" value={form.sell_price} onChange={(v) => set("sell_price", v)} required />
        </div>

        {form.purchase_price && form.sell_price && Number(form.sell_price) > 0 && (
          <MarginBar purchase={Number(form.purchase_price)} sell={Number(form.sell_price)} />
        )}

        <div className="space-y-1.5">
          <Label htmlFor="tax_rate">VAT rate</Label>
          <select id="tax_rate" value={form.tax_rate} onChange={(e) => set("tax_rate", e.target.value)}
            className="block w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-[var(--vf-brand-primary)] focus:outline-none focus:ring-1 focus:ring-[var(--vf-brand-primary)] dark:border-gray-600 dark:bg-gray-700 dark:text-gray-100">
            {TAX_RATES.map((r) => <option key={r.value} value={r.value}>{r.label}</option>)}
          </select>
        </div>

        <div className="space-y-1.5">
          <Label htmlFor="description">Description</Label>
          <textarea id="description" rows={3} value={form.description} onChange={(e) => set("description", e.target.value)}
            className="block w-full resize-none rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-[var(--vf-brand-primary)] focus:outline-none focus:ring-1 focus:ring-[var(--vf-brand-primary)] dark:border-gray-600 dark:bg-gray-700 dark:text-gray-100" />
        </div>

        {error && <p className="rounded-md bg-red-50 px-3 py-2 text-sm text-red-600">{error}</p>}

        <div className="flex justify-end gap-3 pt-2">
          <Button type="button" variant="outline" onClick={() => router.back()}>Cancel</Button>
          <Button type="submit" disabled={saving} className="bg-[var(--vf-brand-primary)] hover:bg-[var(--vf-brand-primary-hover)] text-white">
            {saving ? "Saving…" : "Save changes"}
          </Button>
        </div>
      </form>
    </div>
  );
}

function MarginBar({ purchase, sell }: { purchase: number; sell: number }) {
  const margin = ((sell - purchase) / sell) * 100;
  const color = margin < 10 ? "bg-red-500" : margin < 25 ? "bg-amber-500" : "bg-emerald-500";
  return (
    <div className="space-y-1">
      <div className="flex justify-between text-xs text-gray-500 dark:text-gray-400">
        <span>Gross margin</span>
        <span className={margin >= 25 ? "font-semibold text-emerald-600 dark:text-emerald-400" : "font-semibold text-amber-600"}>
          {margin.toFixed(1)}%
        </span>
      </div>
      <div className="h-1.5 w-full overflow-hidden rounded-full bg-gray-100 dark:bg-gray-700">
        <div className={`h-full rounded-full transition-all ${color}`} style={{ width: `${Math.min(100, Math.max(0, margin))}%` }} />
      </div>
    </div>
  );
}

function Field({ id, label, value, onChange, placeholder, required, type = "text", step }: {
  id: string; label: string; value: string; onChange: (v: string) => void;
  placeholder?: string; required?: boolean; type?: string; step?: string;
}) {
  return (
    <div className="space-y-1.5">
      <Label htmlFor={id}>{label}</Label>
      <input id={id} type={type} step={step} required={required} value={value}
        onChange={(e) => onChange(e.target.value)} placeholder={placeholder}
        className="block h-10 w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-[var(--vf-brand-primary)] focus:outline-none focus:ring-1 focus:ring-[var(--vf-brand-primary)] dark:border-gray-600 dark:bg-gray-700 dark:text-gray-100" />
    </div>
  );
}
