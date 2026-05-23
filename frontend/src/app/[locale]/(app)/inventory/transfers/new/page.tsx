"use client";

import { api } from "@/lib/api-client";
import { Button } from "@/components/ui/button";
import { useRouter } from "@/i18n/navigation";
import { useEffect, useState } from "react";
import { toast } from "sonner";
import { Plus, Trash2 } from "lucide-react";

interface Warehouse {
  id: string;
  name: string;
}

interface Product {
  id: string;
  name: string;
  sku: string;
}

interface LineDraft {
  product_id: string;
  qty_requested: number;
  batch_id?: string | null;
}

export default function NewStockTransferPage() {
  const router = useRouter();
  const [warehouses, setWarehouses] = useState<Warehouse[]>([]);
  const [products, setProducts] = useState<Product[]>([]);
  const [fromId, setFromId] = useState("");
  const [toId, setToId] = useState("");
  const [notes, setNotes] = useState("");
  const [lines, setLines] = useState<LineDraft[]>([
    { product_id: "", qty_requested: 1 },
  ]);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    Promise.all([
      api.get<Warehouse[]>("/api/inventory/warehouses"),
      api.get<Product[]>("/api/inventory/products"),
    ])
      .then(([w, p]) => {
        setWarehouses(w);
        setProducts(p);
      })
      .catch((e: any) => toast.error(e.message));
  }, []);

  function updateLine(idx: number, patch: Partial<LineDraft>) {
    setLines((prev) => prev.map((l, i) => (i === idx ? { ...l, ...patch } : l)));
  }

  function addLine() {
    setLines((prev) => [...prev, { product_id: "", qty_requested: 1 }]);
  }

  function removeLine(idx: number) {
    setLines((prev) => prev.filter((_, i) => i !== idx));
  }

  async function submit() {
    if (!fromId || !toId || fromId === toId) {
      toast.error("Source and destination warehouses must differ");
      return;
    }
    const clean = lines.filter((l) => l.product_id && l.qty_requested > 0);
    if (clean.length === 0) {
      toast.error("Add at least one line");
      return;
    }
    setSaving(true);
    try {
      const res = await api.post<{ id: string }>("/api/stock-transfers", {
        from_warehouse_id: fromId,
        to_warehouse_id: toId,
        notes: notes || null,
        lines: clean,
      });
      toast.success("Transfer created");
      router.push(`/inventory/transfers/${res.id}`);
    } catch (e: any) {
      toast.error(e.message);
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="space-y-6 max-w-3xl">
      <div>
        <h1 className="text-2xl font-bold text-[#1a2332]">New stock transfer</h1>
        <p className="text-sm text-muted-foreground">
          Create a draft transfer between two warehouses. Stock is not moved
          until the transfer is shipped.
        </p>
      </div>

      <div className="grid grid-cols-2 gap-4">
        <label className="space-y-1">
          <span className="text-sm font-medium">From warehouse</span>
          <select
            className="w-full rounded border px-3 py-2"
            value={fromId}
            onChange={(e) => setFromId(e.target.value)}
          >
            <option value="">Select…</option>
            {warehouses.map((w) => (
              <option key={w.id} value={w.id}>
                {w.name}
              </option>
            ))}
          </select>
        </label>
        <label className="space-y-1">
          <span className="text-sm font-medium">To warehouse</span>
          <select
            className="w-full rounded border px-3 py-2"
            value={toId}
            onChange={(e) => setToId(e.target.value)}
          >
            <option value="">Select…</option>
            {warehouses.map((w) => (
              <option key={w.id} value={w.id} disabled={w.id === fromId}>
                {w.name}
              </option>
            ))}
          </select>
        </label>
      </div>

      <div className="space-y-2">
        <div className="flex items-center justify-between">
          <span className="text-sm font-medium">Lines</span>
          <Button size="sm" variant="outline" onClick={addLine}>
            <Plus className="mr-1 h-3 w-3" /> Add line
          </Button>
        </div>
        <div className="space-y-2">
          {lines.map((line, idx) => (
            <div key={idx} className="flex gap-2 items-center">
              <select
                className="flex-1 rounded border px-3 py-2 text-sm"
                value={line.product_id}
                onChange={(e) => updateLine(idx, { product_id: e.target.value })}
              >
                <option value="">Pick product…</option>
                {products.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.name} ({p.sku})
                  </option>
                ))}
              </select>
              <input
                type="number"
                min={1}
                className="w-24 rounded border px-3 py-2 text-sm tabular-nums"
                value={line.qty_requested}
                onChange={(e) =>
                  updateLine(idx, {
                    qty_requested: Math.max(1, parseInt(e.target.value) || 1),
                  })
                }
              />
              {lines.length > 1 && (
                <button
                  type="button"
                  onClick={() => removeLine(idx)}
                  className="p-2 text-gray-400 hover:text-red-600"
                  aria-label="Remove line"
                >
                  <Trash2 className="h-4 w-4" />
                </button>
              )}
            </div>
          ))}
        </div>
      </div>

      <label className="block space-y-1">
        <span className="text-sm font-medium">Notes (optional)</span>
        <textarea
          className="w-full rounded border px-3 py-2 text-sm"
          rows={3}
          value={notes}
          onChange={(e) => setNotes(e.target.value)}
          maxLength={2000}
        />
      </label>

      <div className="flex gap-2">
        <Button
          onClick={submit}
          disabled={saving}
          className="bg-[#1a2332] hover:bg-[#2a3342] text-white"
        >
          {saving ? "Creating…" : "Create transfer"}
        </Button>
        <Button variant="outline" onClick={() => router.back()}>
          Cancel
        </Button>
      </div>
    </div>
  );
}
