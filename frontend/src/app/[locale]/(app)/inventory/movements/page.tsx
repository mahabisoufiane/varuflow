"use client";

import { api } from "@/lib/api-client";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Label } from "@/components/ui/label";
import { useEffect, useState } from "react";
import { ArrowDown, ArrowUp, Minus, Plus } from "lucide-react";

interface Movement {
  id: string; type: "IN" | "OUT" | "ADJUSTMENT"; quantity: number;
  reference: string | null; note: string | null; created_at: string;
  product: { name: string; sku: string; unit: string };
  warehouse: { name: string };
}
interface Product { id: string; name: string; sku: string; unit: string; }
interface WarehouseItem { id: string; name: string; }

export default function MovementsPage() {
  const [movements, setMovements] = useState<Movement[]>([]);
  const [products, setProducts] = useState<Product[]>([]);
  const [warehouses, setWarehouses] = useState<WarehouseItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [open, setOpen] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [form, setForm] = useState({ product_id: "", warehouse_id: "", type: "IN", quantity: "1", reference: "", note: "" });

  async function load() {
    try {
      const [mv, pr, wh] = await Promise.all([
        api.get<Movement[]>("/api/inventory/movements?limit=100"),
        api.get<{ items: Product[] }>("/api/inventory/products?limit=200&is_active=true"),
        api.get<WarehouseItem[]>("/api/inventory/warehouses"),
      ]);
      setMovements(mv);
      setProducts(pr.items);
      setWarehouses(wh);
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { load(); }, []);

  function set(f: string, v: string) { setForm((s) => ({ ...s, [f]: v })); }

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    setError(null);
    try {
      await api.post("/api/inventory/movements", {
        product_id: form.product_id,
        warehouse_id: form.warehouse_id,
        type: form.type,
        quantity: Number(form.quantity),
        reference: form.reference || null,
        note: form.note || null,
      });
      setOpen(false);
      setForm({ product_id: "", warehouse_id: "", type: "IN", quantity: "1", reference: "", note: "" });
      await load();
    } catch (e: any) {
      setError(e.message);
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-[#1a2332]">Stock Movements</h1>
          <p className="text-sm text-muted-foreground">Goods in, goods out, adjustments</p>
        </div>
        <Button size="sm" className="bg-[#1a2332] hover:bg-[#2a3342] text-white" onClick={() => setOpen(true)}>
          <Plus className="mr-1.5 h-3.5 w-3.5" />Record movement
        </Button>
      </div>

      {error && !open && (
        <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-2 text-sm text-red-700">{error}</div>
      )}

      {loading ? (
        <div className="space-y-2 animate-pulse">
          {[1, 2, 3, 4].map((i) => <div key={i} className="h-14 rounded-xl bg-gray-100" />)}
        </div>
      ) : movements.length === 0 ? (
        <div className="rounded-xl border bg-white px-6 py-12 text-center">
          <p className="font-medium text-gray-900">No movements recorded yet</p>
          <p className="mt-1 text-sm text-muted-foreground">Record goods in, out, or manual adjustments.</p>
          <Button size="sm" className="mt-4 bg-[#1a2332] hover:bg-[#2a3342] text-white" onClick={() => setOpen(true)}>
            Record first movement
          </Button>
        </div>
      ) : (
        <div className="rounded-xl border bg-white overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-gray-50 text-xs text-gray-500 uppercase">
              <tr>
                <th className="px-4 py-3 text-left">Type</th>
                <th className="px-4 py-3 text-left">Product</th>
                <th className="px-4 py-3 text-left">Warehouse</th>
                <th className="px-4 py-3 text-right">Qty</th>
                <th className="px-4 py-3 text-left">Reference</th>
                <th className="px-4 py-3 text-left">Date</th>
              </tr>
            </thead>
            <tbody className="divide-y">
              {movements.map((m) => (
                <tr key={m.id} className="hover:bg-gray-50">
                  <td className="px-4 py-3"><MovementBadge type={m.type} /></td>
                  <td className="px-4 py-3">
                    <p className="font-medium">{m.product.name}</p>
                    <p className="text-xs text-muted-foreground">{m.product.sku}</p>
                  </td>
                  <td className="px-4 py-3 text-muted-foreground">{m.warehouse.name}</td>
                  <td className="px-4 py-3 text-right font-mono">{m.quantity} {m.product.unit}</td>
                  <td className="px-4 py-3 text-muted-foreground">{m.reference ?? "—"}</td>
                  <td className="px-4 py-3 text-muted-foreground text-xs">{new Date(m.created_at).toLocaleDateString("sv-SE")}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader><DialogTitle>Record movement</DialogTitle></DialogHeader>
          <form onSubmit={handleCreate} className="space-y-4 pt-2">
            <div className="space-y-1.5">
              <Label>Product *</Label>
              <select required value={form.product_id} onChange={(e) => set("product_id", e.target.value)}
                className="block w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-[#1a2332] focus:outline-none focus:ring-1 focus:ring-[#1a2332]">
                <option value="">Select product…</option>
                {products.map((p) => <option key={p.id} value={p.id}>{p.name} ({p.sku})</option>)}
              </select>
            </div>
            <div className="space-y-1.5">
              <Label>Warehouse *</Label>
              <select required value={form.warehouse_id} onChange={(e) => set("warehouse_id", e.target.value)}
                className="block w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-[#1a2332] focus:outline-none focus:ring-1 focus:ring-[#1a2332]">
                <option value="">Select warehouse…</option>
                {warehouses.map((w) => <option key={w.id} value={w.id}>{w.name}</option>)}
              </select>
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-1.5">
                <Label>Type *</Label>
                <select value={form.type} onChange={(e) => set("type", e.target.value)}
                  className="block w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-[#1a2332] focus:outline-none focus:ring-1 focus:ring-[#1a2332]">
                  <option value="IN">IN — Goods received</option>
                  <option value="OUT">OUT — Goods shipped</option>
                  <option value="ADJUSTMENT">ADJUSTMENT</option>
                </select>
              </div>
              <div className="space-y-1.5">
                <Label>Quantity *</Label>
                <input required type="number" min="1" value={form.quantity} onChange={(e) => set("quantity", e.target.value)}
                  className="block w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-[#1a2332] focus:outline-none focus:ring-1 focus:ring-[#1a2332]" />
              </div>
            </div>
            <div className="space-y-1.5">
              <Label>Reference</Label>
              <input value={form.reference} onChange={(e) => set("reference", e.target.value)} placeholder="Order #, PO #…"
                className="block w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-[#1a2332] focus:outline-none focus:ring-1 focus:ring-[#1a2332]" />
            </div>
            {error && <p className="text-sm text-red-600">{error}</p>}
            <div className="flex justify-end gap-3 pt-2">
              <Button type="button" variant="outline" onClick={() => setOpen(false)}>Cancel</Button>
              <Button type="submit" disabled={saving} className="bg-[#1a2332] hover:bg-[#2a3342] text-white">
                {saving ? "Saving…" : "Record"}
              </Button>
            </div>
          </form>
        </DialogContent>
      </Dialog>
    </div>
  );
}

function MovementBadge({ type }: { type: "IN" | "OUT" | "ADJUSTMENT" }) {
  if (type === "IN") return (
    <span className="inline-flex items-center gap-1 rounded px-2 py-0.5 text-xs font-medium bg-green-100 text-green-700">
      <ArrowDown className="h-3 w-3" />IN
    </span>
  );
  if (type === "OUT") return (
    <span className="inline-flex items-center gap-1 rounded px-2 py-0.5 text-xs font-medium bg-red-100 text-red-700">
      <ArrowUp className="h-3 w-3" />OUT
    </span>
  );
  return (
    <span className="inline-flex items-center gap-1 rounded px-2 py-0.5 text-xs font-medium bg-gray-100 text-gray-700">
      <Minus className="h-3 w-3" />ADJ
    </span>
  );
}
