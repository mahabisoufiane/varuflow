"use client";

import { api } from "@/lib/api-client";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { useRouter, useParams } from "next/navigation";
import { useEffect, useState } from "react";
import Link from "next/link";
import { ArrowLeft, Trash2 } from "lucide-react";

const TAX_RATES = [
  { label: "25% — Standard", value: "25" },
  { label: "12% — Food / Hospitality", value: "12" },
  { label: "6% — Books / Transport", value: "6" },
];

interface Product {
  id: string; name: string; sku: string; category: string | null;
  unit: string; purchase_price: string; sell_price: string;
  tax_rate: string; description: string | null; is_active: boolean;
}

export default function EditProductPage() {
  const router = useRouter();
  const { id } = useParams<{ id: string }>();

  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [form, setForm] = useState({
    name: "", sku: "", category: "", unit: "st",
    purchase_price: "", sell_price: "", tax_rate: "25", description: "",
  });

  function set(field: string, value: string) {
    setForm((f) => ({ ...f, [field]: value }));
  }

  useEffect(() => {
    api.get<Product>(`/api/inventory/products/${id}`)
      .then((p) => setForm({
        name: p.name, sku: p.sku, category: p.category ?? "",
        unit: p.unit, purchase_price: p.purchase_price,
        sell_price: p.sell_price,
        tax_rate: String(Math.round(Number(p.tax_rate))),
        description: p.description ?? "",
      }))
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [id]);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    setError(null);
    try {
      await api.put(`/api/inventory/products/${id}`, {
        name: form.name, sku: form.sku,
        category: form.category || null, unit: form.unit,
        purchase_price: form.purchase_price, sell_price: form.sell_price,
        tax_rate: form.tax_rate, description: form.description || null,
      });
      router.push("/inventory/products");
    } catch (e: any) {
      setError(e.message);
    } finally {
      setSaving(false);
    }
  }

  async function handleDeactivate() {
    if (!confirm("Deactivate this product?")) return;
    try {
      await api.delete(`/api/inventory/products/${id}`);
      router.push("/inventory/products");
    } catch (e: any) {
      setError(e.message);
    }
  }

  if (loading) {
    return (
      <div className="mx-auto max-w-2xl">
        <div className="h-8 w-48 animate-pulse rounded bg-gray-200" />
        <div className="mt-6 h-80 animate-pulse rounded-xl bg-gray-100" />
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
          <h1 className="text-2xl font-bold text-[#1a2332]">Edit Product</h1>
        </div>
        <Button variant="ghost" size="sm" className="text-red-500 hover:text-red-700 hover:bg-red-50" onClick={handleDeactivate}>
          <Trash2 className="h-4 w-4 mr-1.5" />Deactivate
        </Button>
      </div>

      <form onSubmit={handleSubmit} className="space-y-5 rounded-xl border bg-white p-6">
        <div className="grid grid-cols-2 gap-4">
          <Field id="name" label="Name *" value={form.name} onChange={(v) => set("name", v)} required />
          <Field id="sku" label="SKU *" value={form.sku} onChange={(v) => set("sku", v)} required />
        </div>
        <div className="grid grid-cols-2 gap-4">
          <Field id="category" label="Category" value={form.category} onChange={(v) => set("category", v)} />
          <Field id="unit" label="Unit" value={form.unit} onChange={(v) => set("unit", v)} />
        </div>
        <div className="grid grid-cols-2 gap-4">
          <Field id="purchase_price" label="Purchase price (SEK) *" type="number" step="0.01" value={form.purchase_price} onChange={(v) => set("purchase_price", v)} required />
          <Field id="sell_price" label="Sell price (SEK) *" type="number" step="0.01" value={form.sell_price} onChange={(v) => set("sell_price", v)} required />
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="tax_rate">VAT rate</Label>
          <select id="tax_rate" value={form.tax_rate} onChange={(e) => set("tax_rate", e.target.value)}
            className="block w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-[#1a2332] focus:outline-none focus:ring-1 focus:ring-[#1a2332]">
            {TAX_RATES.map((r) => <option key={r.value} value={r.value}>{r.label}</option>)}
          </select>
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="description">Description</Label>
          <textarea id="description" rows={3} value={form.description} onChange={(e) => set("description", e.target.value)}
            className="block w-full resize-none rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-[#1a2332] focus:outline-none focus:ring-1 focus:ring-[#1a2332]" />
        </div>
        {error && <p className="rounded-md bg-red-50 px-3 py-2 text-sm text-red-600">{error}</p>}
        <div className="flex justify-end gap-3 pt-2">
          <Button type="button" variant="outline" onClick={() => router.back()}>Cancel</Button>
          <Button type="submit" disabled={saving} className="bg-[#1a2332] hover:bg-[#2a3342] text-white">
            {saving ? "Saving…" : "Save changes"}
          </Button>
        </div>
      </form>
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
        className="block w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-[#1a2332] focus:outline-none focus:ring-1 focus:ring-[#1a2332]" />
    </div>
  );
}
