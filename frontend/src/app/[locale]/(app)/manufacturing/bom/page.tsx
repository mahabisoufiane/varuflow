"use client";

import { useEffect, useState } from "react";
import { BookCopy, Plus, Loader2, Trash2, Check, X } from "lucide-react";
import { toast } from "sonner";
import { api } from "@/lib/api-client";

interface BomLine {
  id: string;
  component_product_id: string;
  quantity: string;
  unit: string;
  notes: string | null;
}

interface Bom {
  id: string;
  product_id: string;
  name: string;
  is_kit: boolean;
  is_active: boolean;
  lines: BomLine[];
}

interface Product {
  id: string;
  name: string;
  sku: string;
}

export default function BomPage() {
  const [boms, setBoms] = useState<Bom[]>([]);
  const [products, setProducts] = useState<Product[]>([]);
  const [selected, setSelected] = useState<Bom | null>(null);
  const [loading, setLoading] = useState(true);
  const [showCreate, setShowCreate] = useState(false);
  const [createForm, setCreateForm] = useState({ product_id: "", name: "", is_kit: false });
  const [lineForm, setLineForm] = useState({ component_product_id: "", quantity: "", unit: "st" });
  const [showLineForm, setShowLineForm] = useState(false);

  async function load() {
    try {
      const [bomList, productList] = await Promise.all([
        api.get("/api/manufacturing/boms"),
        api.get("/api/inventory/products?limit=500").catch(() => []),
      ]);
      setBoms(bomList);
      if (productList.items) setProducts(productList.items);
      else if (Array.isArray(productList)) setProducts(productList);
    } catch {
      toast.error("Failed to load BOMs");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { load(); }, []);

  const productMap = Object.fromEntries(products.map((p) => [p.id, p]));

  async function createBom() {
    if (!createForm.product_id || !createForm.name) { toast.error("Fill in product and name"); return; }
    try {
      const created = await api.post("/api/manufacturing/boms", createForm);
      setBoms((b) => [created, ...b]);
      setShowCreate(false);
      setCreateForm({ product_id: "", name: "", is_kit: false });
      setSelected(created);
      toast.success("BOM created");
    } catch { toast.error("Failed to create BOM"); }
  }

  async function toggleActive(bom: Bom) {
    try {
      const updated = await api.patch(`/api/manufacturing/boms/${bom.id}`, { is_active: !bom.is_active });
      setBoms((b) => b.map((x) => (x.id === bom.id ? { ...x, ...updated } : x)));
      if (selected?.id === bom.id) setSelected((s) => s ? { ...s, ...updated } : null);
    } catch { toast.error("Failed to update BOM"); }
  }

  async function deleteBom(id: string) {
    try {
      await api.delete(`/api/manufacturing/boms/${id}`);
      setBoms((b) => b.filter((x) => x.id !== id));
      if (selected?.id === id) setSelected(null);
      toast.success("BOM deleted");
    } catch { toast.error("Failed to delete BOM"); }
  }

  async function addLine() {
    if (!selected || !lineForm.component_product_id || !lineForm.quantity) { toast.error("Fill in component and quantity"); return; }
    try {
      const line = await api.post(`/api/manufacturing/boms/${selected.id}/lines`, { ...lineForm, quantity: parseFloat(lineForm.quantity) });
      setBoms((b) => b.map((x) => x.id === selected.id ? { ...x, lines: [...x.lines, line] } : x));
      setSelected((s) => s ? { ...s, lines: [...s.lines, line] } : null);
      setLineForm({ component_product_id: "", quantity: "", unit: "st" });
      setShowLineForm(false);
      toast.success("Component added");
    } catch { toast.error("Failed to add component"); }
  }

  async function deleteLine(lineId: string) {
    if (!selected) return;
    try {
      await api.delete(`/api/manufacturing/boms/${selected.id}/lines/${lineId}`);
      const updated = { ...selected, lines: selected.lines.filter((l) => l.id !== lineId) };
      setBoms((b) => b.map((x) => x.id === selected.id ? updated : x));
      setSelected(updated);
      toast.success("Component removed");
    } catch { toast.error("Failed to remove component"); }
  }

  return (
    <div className="p-6 max-w-7xl mx-auto">
      <div className="flex items-center gap-2 mb-6">
        <BookCopy className="w-6 h-6" />
        <h1 className="text-2xl font-semibold">Bill of Materials</h1>
      </div>

      <div className="grid grid-cols-12 gap-6">
        {/* BOM list */}
        <div className="col-span-4 border rounded-lg p-3">
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-sm font-semibold">BOMs</h3>
            <button onClick={() => setShowCreate((x) => !x)} className="p-1 hover:bg-accent rounded"><Plus className="w-4 h-4" /></button>
          </div>
          {showCreate && (
            <div className="space-y-2 mb-3 border-b pb-3">
              <select className="border rounded px-2 py-1 text-xs w-full" value={createForm.product_id} onChange={(e) => setCreateForm((f) => ({ ...f, product_id: e.target.value }))}>
                <option value="">— finished product —</option>
                {products.map((p) => <option key={p.id} value={p.id}>{p.name} ({p.sku})</option>)}
              </select>
              <input className="border rounded px-2 py-1 text-xs w-full" placeholder="BOM name" value={createForm.name} onChange={(e) => setCreateForm((f) => ({ ...f, name: e.target.value }))} />
              <label className="flex items-center gap-1.5 text-xs">
                <input type="checkbox" checked={createForm.is_kit} onChange={(e) => setCreateForm((f) => ({ ...f, is_kit: e.target.checked }))} />
                Is Kit
              </label>
              <div className="flex gap-1">
                <button onClick={createBom} className="bg-primary text-primary-foreground rounded px-2 py-1 text-xs">Create</button>
                <button onClick={() => setShowCreate(false)} className="border rounded px-2 py-1 text-xs">Cancel</button>
              </div>
            </div>
          )}
          {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : (
            <div className="space-y-1">
              {boms.map((b) => (
                <button key={b.id} onClick={() => setSelected(b)} className={`w-full text-left p-2 rounded text-xs hover:bg-accent ${selected?.id === b.id ? "bg-accent" : ""}`}>
                  <div className="flex items-center justify-between">
                    <span className="font-medium truncate">{b.name}</span>
                    <div className="flex items-center gap-1">
                      {b.is_kit && <span className="bg-purple-100 text-purple-800 px-1 rounded text-[10px]">kit</span>}
                      {!b.is_active && <span className="text-muted-foreground text-[10px]">inactive</span>}
                    </div>
                  </div>
                  <p className="text-muted-foreground">{b.lines.length} component{b.lines.length !== 1 ? "s" : ""}</p>
                </button>
              ))}
            </div>
          )}
        </div>

        {/* BOM editor */}
        <div className="col-span-8 border rounded-lg p-4">
          {selected ? (
            <>
              <div className="flex items-center justify-between mb-4">
                <div>
                  <h3 className="font-semibold">{selected.name}</h3>
                  <p className="text-xs text-muted-foreground">
                    Finished product: {productMap[selected.product_id]?.name ?? selected.product_id.slice(0, 8)}
                    {selected.is_kit && " · Kit"}
                  </p>
                </div>
                <div className="flex gap-2">
                  <button onClick={() => toggleActive(selected)} className="border rounded px-2 py-1 text-xs hover:bg-accent">
                    {selected.is_active ? "Deactivate" : "Activate"}
                  </button>
                  <button onClick={() => deleteBom(selected.id)} className="text-destructive border rounded px-2 py-1 text-xs hover:bg-red-50">Delete BOM</button>
                </div>
              </div>

              <div className="mb-4">
                <div className="flex items-center justify-between mb-2">
                  <h4 className="text-sm font-medium">Components</h4>
                  <button onClick={() => setShowLineForm((x) => !x)} className="flex items-center gap-1 text-xs border rounded px-2 py-1 hover:bg-accent">
                    <Plus className="w-3 h-3" /> Add Component
                  </button>
                </div>
                {showLineForm && (
                  <div className="border rounded p-3 mb-3 grid grid-cols-3 gap-2">
                    <div className="col-span-3">
                      <select className="border rounded px-2 py-1.5 text-xs w-full" value={lineForm.component_product_id} onChange={(e) => setLineForm((f) => ({ ...f, component_product_id: e.target.value }))}>
                        <option value="">— select component —</option>
                        {products.map((p) => <option key={p.id} value={p.id}>{p.name} ({p.sku})</option>)}
                      </select>
                    </div>
                    <div>
                      <input type="number" step="0.001" placeholder="Qty" className="border rounded px-2 py-1 text-xs w-full" value={lineForm.quantity} onChange={(e) => setLineForm((f) => ({ ...f, quantity: e.target.value }))} />
                    </div>
                    <div>
                      <input placeholder="Unit" className="border rounded px-2 py-1 text-xs w-full" value={lineForm.unit} onChange={(e) => setLineForm((f) => ({ ...f, unit: e.target.value }))} />
                    </div>
                    <div className="flex gap-1">
                      <button onClick={addLine} className="bg-primary text-primary-foreground rounded px-2 py-1 text-xs">Add</button>
                      <button onClick={() => setShowLineForm(false)} className="border rounded px-2 py-1 text-xs">×</button>
                    </div>
                  </div>
                )}
                {selected.lines.length === 0 ? (
                  <p className="text-xs text-muted-foreground">No components yet.</p>
                ) : (
                  <table className="w-full text-xs">
                    <thead><tr className="border-b text-muted-foreground"><th className="py-1 text-left font-medium">Component</th><th className="py-1 text-left font-medium">Qty</th><th className="py-1 text-left font-medium">Unit</th><th /></tr></thead>
                    <tbody className="divide-y">
                      {selected.lines.map((l) => (
                        <tr key={l.id}>
                          <td className="py-1.5 pr-2">{productMap[l.component_product_id]?.name ?? l.component_product_id.slice(0, 8)}</td>
                          <td className="py-1.5 pr-2 font-medium">{parseFloat(l.quantity).toFixed(3).replace(/\.?0+$/, "")}</td>
                          <td className="py-1.5 pr-2 text-muted-foreground">{l.unit}</td>
                          <td className="py-1.5"><button onClick={() => deleteLine(l.id)} className="text-destructive hover:opacity-70"><Trash2 className="w-3 h-3" /></button></td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                )}
              </div>
            </>
          ) : (
            <p className="text-sm text-muted-foreground">Select a BOM to view and edit components.</p>
          )}
        </div>
      </div>
    </div>
  );
}
