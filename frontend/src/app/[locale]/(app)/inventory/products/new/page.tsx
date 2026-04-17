"use client";

import { api } from "@/lib/api-client";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { useRouter } from "next/navigation";
import { useState } from "react";
import Link from "next/link";
import { ArrowLeft, ScanLine } from "lucide-react";
import { useMoney } from "@/hooks/useMoney";
import BarcodeScanner from "@/components/app/BarcodeScanner";

export default function NewProductPage() {
  const router = useRouter();
  const { code: currencyCode, vatRates, config } = useMoney();
  const defaultVat = String(config?.vat.standard_rate_pct ?? vatRates[0] ?? 25);

  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [scannerOpen, setScannerOpen] = useState(false);
  const [form, setForm] = useState({
    name: "", sku: "", barcode: "", category: "", unit: "st",
    purchase_price: "", sell_price: "", tax_rate: defaultVat, description: "",
  });

  function set(field: string, value: string) {
    setForm((f) => ({ ...f, [field]: value }));
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    setError(null);
    try {
      await api.post("/api/inventory/products", {
        name: form.name,
        sku: form.sku,
        barcode: form.barcode || null,
        category: form.category || null,
        unit: form.unit,
        purchase_price: form.purchase_price,
        sell_price: form.sell_price,
        tax_rate: form.tax_rate,
        description: form.description || null,
      });
      router.push("/inventory/products");
    } catch (e: unknown) {
      setError((e as Error).message ?? "Failed to create product");
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="mx-auto max-w-2xl space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <Button asChild variant="ghost" size="sm" className="mb-2 -ml-2 text-muted-foreground">
            <Link href="/inventory/products"><ArrowLeft className="mr-1 h-3.5 w-3.5" />Products</Link>
          </Button>
          <h1 className="text-2xl font-bold text-[#1a2332]">New Product</h1>
        </div>
        <Link
          href="/inventory/products/scan"
          className="inline-flex items-center gap-1.5 rounded-lg bg-gradient-to-br from-indigo-500 to-indigo-600 px-3 py-2 text-sm font-semibold text-white shadow-sm hover:shadow-md"
        >
          <ScanLine className="h-4 w-4" /> Scan instead
        </Link>
      </div>

      <form onSubmit={handleSubmit} className="space-y-5 rounded-xl border bg-white p-6">
        <div className="grid grid-cols-2 gap-4">
          <Field id="name" label="Name *" value={form.name} onChange={(v) => set("name", v)} placeholder="Ekologisk havregryn" required />
          <Field id="sku" label="SKU *" value={form.sku} onChange={(v) => set("sku", v)} placeholder="HAV-001" required />
        </div>
        <div className="grid grid-cols-2 gap-4">
          <div className="space-y-1.5">
            <Label htmlFor="barcode">Barcode (EAN)</Label>
            <div className="flex gap-2">
              <input
                id="barcode" type="text"
                value={form.barcode}
                onChange={(e) => set("barcode", e.target.value)}
                placeholder="7310865085313"
                className="block w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-[#1a2332] focus:outline-none focus:ring-1 focus:ring-[#1a2332]"
              />
              <button
                type="button"
                onClick={() => setScannerOpen(true)}
                className="shrink-0 rounded-md border border-gray-300 bg-white px-3 py-2 text-sm hover:bg-gray-50"
                title="Scan with camera"
              >
                <ScanLine className="h-4 w-4" />
              </button>
            </div>
          </div>
          <Field id="category" label="Category" value={form.category} onChange={(v) => set("category", v)} placeholder="Spannmål" />
        </div>
        <div className="grid grid-cols-2 gap-4">
          <Field id="unit" label="Unit" value={form.unit} onChange={(v) => set("unit", v)} placeholder="kg" />
          <div />
        </div>
        <div className="grid grid-cols-2 gap-4">
          <Field id="purchase_price" label={`Purchase price (${currencyCode}) *`} type="number" step="0.01" value={form.purchase_price} onChange={(v) => set("purchase_price", v)} placeholder="12.50" required />
          <Field id="sell_price" label={`Sell price (${currencyCode}) *`} type="number" step="0.01" value={form.sell_price} onChange={(v) => set("sell_price", v)} placeholder="24.00" required />
        </div>

        <div className="space-y-1.5">
          <Label htmlFor="tax_rate">VAT rate</Label>
          <select
            id="tax_rate"
            value={form.tax_rate}
            onChange={(e) => set("tax_rate", e.target.value)}
            className="block w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-[#1a2332] focus:outline-none focus:ring-1 focus:ring-[#1a2332]"
          >
            {vatRates.map((r) => (
              <option key={r} value={String(r)}>{r}%</option>
            ))}
          </select>
        </div>

        <div className="space-y-1.5">
          <Label htmlFor="description">Description</Label>
          <textarea
            id="description"
            rows={3}
            value={form.description}
            onChange={(e) => set("description", e.target.value)}
            className="block w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-[#1a2332] focus:outline-none focus:ring-1 focus:ring-[#1a2332] resize-none"
          />
        </div>

        {error && (
          <p className="rounded-md bg-red-50 px-3 py-2 text-sm text-red-600">{error}</p>
        )}

        <div className="flex justify-end gap-3 pt-2">
          <Button type="button" variant="outline" onClick={() => router.back()}>Cancel</Button>
          <Button type="submit" disabled={saving} className="bg-[#1a2332] hover:bg-[#2a3342] text-white">
            {saving ? "Saving…" : "Create product"}
          </Button>
        </div>
      </form>

      {scannerOpen && (
        <BarcodeScanner
          onResult={(code) => {
            set("barcode", code);
            setScannerOpen(false);
            if (typeof navigator !== "undefined" && "vibrate" in navigator) {
              navigator.vibrate(40);
            }
          }}
          onClose={() => setScannerOpen(false)}
        />
      )}
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
      <input
        id={id} type={type} step={step} required={required}
        value={value} onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        className="block w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-[#1a2332] focus:outline-none focus:ring-1 focus:ring-[#1a2332]"
      />
    </div>
  );
}
