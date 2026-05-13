"use client";

import { api } from "@/lib/api-client";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import Link from "next/link";
import { ArrowLeft, Plus, Trash2 } from "lucide-react";

interface Supplier { id: string; name: string; }
interface Product { id: string; name: string; sku: string; purchase_price: string; unit: string; }
interface LineItem { product_id: string; quantity: number; unit_price: string; }

export default function NewPurchaseOrderPage() {
  const router = useRouter();
  const [suppliers, setSuppliers] = useState<Supplier[]>([]);
  const [products, setProducts] = useState<Product[]>([]);
  const [supplierId, setSupplierId] = useState("");
  const [notes, setNotes] = useState("");
  const [items, setItems] = useState<LineItem[]>([{ product_id: "", quantity: 1, unit_price: "" }]);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([
      api.get<Supplier[]>("/api/inventory/suppliers"),
      api.get<{ items: Product[] }>("/api/inventory/products?limit=200&is_active=true"),
    ]).then(([s, p]) => { setSuppliers(s); setProducts(p.items); })
      .catch((e) => setError(e.message));
  }, []);

  function setItem(i: number, field: keyof LineItem, value: string | number) {
    setItems((prev) => prev.map((item, idx) => {
      if (idx !== i) return item;
      const updated = { ...item, [field]: value };
      // Auto-fill unit_price from product
      if (field === "product_id") {
        const p = products.find((pr) => pr.id === value);
        if (p) updated.unit_price = p.purchase_price;
      }
      return updated;
    }));
  }

  function addLine() { setItems((prev) => [...prev, { product_id: "", quantity: 1, unit_price: "" }]); }
  function removeLine(i: number) { setItems((prev) => prev.filter((_, idx) => idx !== i)); }

  const total = items.reduce((sum, it) => sum + (Number(it.unit_price) * it.quantity || 0), 0);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true); setError(null);
    try {
      await api.post("/api/inventory/purchase-orders", {
        supplier_id: supplierId,
        notes: notes || null,
        items: items.map((it) => ({
          product_id: it.product_id,
          quantity: it.quantity,
          unit_price: it.unit_price,
        })),
      });
      router.push("/inventory/purchase-orders");
    } catch (e: any) { setError(e.message); } finally { setSaving(false); }
  }

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <div>
        <Button asChild variant="ghost" size="sm" className="mb-2 -ml-2 text-muted-foreground">
          <Link href="/inventory/purchase-orders"><ArrowLeft className="mr-1 h-3.5 w-3.5" />Purchase Orders</Link>
        </Button>
        <h1 className="text-2xl font-bold text-[#1a2332]">New Purchase Order</h1>
      </div>

      <form onSubmit={handleSubmit} className="space-y-6">
        <div className="rounded-xl border bg-white p-6 space-y-4">
          <h2 className="font-semibold text-gray-900">Order details</h2>
          <div className="space-y-1.5">
            <Label>Supplier *</Label>
            <select required value={supplierId} onChange={(e) => setSupplierId(e.target.value)}
              className="block w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-[#1a2332] focus:outline-none focus:ring-1 focus:ring-[#1a2332]">
              <option value="">Select supplier…</option>
              {suppliers.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
            </select>
            {suppliers.length === 0 && (
              <p className="text-xs text-muted-foreground">
                No suppliers yet. <Link href="/inventory/suppliers" className="text-[#1a2332] underline">Add one first.</Link>
              </p>
            )}
          </div>
          <div className="space-y-1.5">
            <Label>Notes</Label>
            <textarea rows={2} value={notes} onChange={(e) => setNotes(e.target.value)} placeholder="Delivery instructions, terms…"
              className="block w-full resize-none rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-[#1a2332] focus:outline-none focus:ring-1 focus:ring-[#1a2332]" />
          </div>
        </div>

        <div className="rounded-xl border bg-white p-6 space-y-4">
          <h2 className="font-semibold text-gray-900">Line items</h2>
          <div className="space-y-3">
            {items.map((item, i) => (
              <div key={i} className="flex gap-3 items-end">
                <div className="flex-1 space-y-1.5">
                  {i === 0 && <Label>Product</Label>}
                  <select required value={item.product_id} onChange={(e) => setItem(i, "product_id", e.target.value)}
                    className="block w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-[#1a2332] focus:outline-none focus:ring-1 focus:ring-[#1a2332]">
                    <option value="">Select product…</option>
                    {products.map((p) => <option key={p.id} value={p.id}>{p.name} ({p.sku})</option>)}
                  </select>
                </div>
                <div className="w-24 space-y-1.5">
                  {i === 0 && <Label>Qty</Label>}
                  <input type="number" min="1" required value={item.quantity}
                    onChange={(e) => setItem(i, "quantity", Number(e.target.value))}
                    className="block w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-[#1a2332] focus:outline-none focus:ring-1 focus:ring-[#1a2332]" />
                </div>
                <div className="w-28 space-y-1.5">
                  {i === 0 && <Label>Price (SEK)</Label>}
                  <input type="number" step="0.01" min="0.01" required value={item.unit_price}
                    onChange={(e) => setItem(i, "unit_price", e.target.value)}
                    className="block w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-[#1a2332] focus:outline-none focus:ring-1 focus:ring-[#1a2332]" />
                </div>
                <div className="w-24 space-y-1.5">
                  {i === 0 && <Label>Total</Label>}
                  <p className="py-2 text-sm font-mono text-right text-gray-600">
                    {(Number(item.unit_price) * item.quantity || 0).toFixed(2)}
                  </p>
                </div>
                <div className={i === 0 ? "pb-0.5" : ""}>
                  {items.length > 1 && (
                    <Button type="button" variant="ghost" size="sm" className="h-9 w-9 p-0 text-red-400 hover:text-red-600" onClick={() => removeLine(i)}>
                      <Trash2 className="h-4 w-4" />
                    </Button>
                  )}
                </div>
              </div>
            ))}
          </div>
          <Button type="button" variant="outline" size="sm" onClick={addLine}>
            <Plus className="mr-1.5 h-3.5 w-3.5" />Add line
          </Button>

          <div className="flex justify-end border-t pt-3">
            <div className="text-right">
              <p className="text-xs text-muted-foreground">Total (excl. VAT)</p>
              <p className="text-xl font-bold text-[#1a2332]">
                {total.toLocaleString("sv-SE", { minimumFractionDigits: 2 })} SEK
              </p>
            </div>
          </div>
        </div>

        {error && <p className="rounded-md bg-red-50 px-3 py-2 text-sm text-red-600">{error}</p>}

        <div className="flex justify-end gap-3">
          <Button type="button" variant="outline" onClick={() => router.back()}>Cancel</Button>
          <Button type="submit" disabled={saving} className="bg-[#1a2332] hover:bg-[#2a3342] text-white">
            {saving ? "Creating…" : "Create purchase order"}
          </Button>
        </div>
      </form>
    </div>
  );
}
