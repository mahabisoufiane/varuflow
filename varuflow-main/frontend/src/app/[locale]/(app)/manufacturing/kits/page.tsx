"use client";

import { useEffect, useState } from "react";
import { Package2, Plus, Loader2, Wrench } from "lucide-react";
import { toast } from "sonner";
import { api } from "@/lib/api-client";
import { isPlanGateError, PlanGateBlock } from "@/components/ui/PlanGate";

interface BomLine {
  id: string;
  component_product_id: string;
  quantity: string;
  unit: string;
}

interface Kit {
  id: string;
  product_id: string;
  name: string;
  is_active: boolean;
  lines: BomLine[];
}

interface Product {
  id: string;
  name: string;
  sku: string;
}

interface Warehouse {
  id: string;
  name: string;
}

export default function KitsPage() {
  const [kits, setKits] = useState<Kit[]>([]);
  const [products, setProducts] = useState<Product[]>([]);
  const [warehouses, setWarehouses] = useState<Warehouse[]>([]);
  const [loading, setLoading] = useState(true);
  const [showCreate, setShowCreate] = useState(false);
  const [createForm, setCreateForm] = useState({ product_id: "", name: "" });
  const [selectedKit, setSelectedKit] = useState<Kit | null>(null);
  const [lineForm, setLineForm] = useState({ component_product_id: "", quantity: "", unit: "st" });
  const [showLineForm, setShowLineForm] = useState(false);
  const [buildingKit, setBuildingKit] = useState<Kit | null>(null);
  const [buildForm, setBuildForm] = useState({ qty: 1, warehouse_id: "" });
  const [building, setBuilding] = useState(false);
  const [planBlocked, setPlanBlocked] = useState<{ module: string; currentPlan: string } | null>(null);

  async function load() {
    try {
      const [kitList, productList, whList] = await Promise.all([
        api.get("/api/manufacturing/kits"),
        api.get("/api/inventory/products?limit=500").catch(() => []),
        api.get("/api/inventory/warehouses").catch(() => []),
      ]);
      setKits(kitList);
      if (productList.items) setProducts(productList.items);
      else if (Array.isArray(productList)) setProducts(productList);
      setWarehouses(whList);
    } catch (err) {
      if (isPlanGateError(err)) {
        setPlanBlocked({ module: (err as any).module ?? "manufacturing", currentPlan: (err as any).currentPlan ?? "FREE" });
        return;
      }
      toast.error("Failed to load kits");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { load(); }, []);

  const productMap = Object.fromEntries(products.map((p) => [p.id, p]));

  async function createKit() {
    if (!createForm.product_id || !createForm.name) { toast.error("Fill in product and name"); return; }
    try {
      const created = await api.post("/api/manufacturing/kits", { ...createForm, is_kit: true });
      setKits((k) => [created, ...k]);
      setShowCreate(false);
      setSelectedKit(created);
      toast.success("Kit created");
    } catch { toast.error("Failed to create kit"); }
  }

  async function addLine() {
    if (!selectedKit || !lineForm.component_product_id || !lineForm.quantity) { toast.error("Fill in component and qty"); return; }
    try {
      const line = await api.post(`/api/manufacturing/boms/${selectedKit.id}/lines`, { ...lineForm, quantity: parseFloat(lineForm.quantity) });
      const updated = { ...selectedKit, lines: [...selectedKit.lines, line] };
      setKits((k) => k.map((x) => x.id === selectedKit.id ? updated : x));
      setSelectedKit(updated);
      setLineForm({ component_product_id: "", quantity: "", unit: "st" });
      setShowLineForm(false);
      toast.success("Component added");
    } catch { toast.error("Failed to add component"); }
  }

  async function build() {
    if (!buildingKit || !buildForm.warehouse_id) { toast.error("Select warehouse"); return; }
    setBuilding(true);
    try {
      const result = await api.post(`/api/manufacturing/kits/${buildingKit.id}/build`, buildForm);
      toast.success(`Built ${result.produced_qty}× ${buildingKit.name} — ${result.movements.length} stock movements applied`);
      setBuildingKit(null);
    } catch (err: any) {
      toast.error(err?.detail?.message ?? "Failed to build kit — check stock levels");
    } finally {
      setBuilding(false);
    }
  }

  if (planBlocked) return <PlanGateBlock module={planBlocked.module} currentPlan={planBlocked.currentPlan} featureName="Kits" />;

  return (
    <div className="p-6 max-w-6xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-2">
          <Package2 className="w-6 h-6" />
          <h1 className="text-2xl font-semibold">Physical Kits</h1>
        </div>
        <button onClick={() => setShowCreate((x) => !x)} className="flex items-center gap-1.5 bg-primary text-primary-foreground rounded px-3 py-1.5 text-sm">
          <Plus className="w-4 h-4" /> New Kit
        </button>
      </div>

      {showCreate && (
        <div className="border rounded p-4 mb-6 grid grid-cols-2 gap-3 max-w-lg">
          <div>
            <label className="text-xs font-medium text-muted-foreground">Finished Product</label>
            <select className="border rounded px-2 py-1.5 text-sm w-full mt-1" value={createForm.product_id} onChange={(e) => setCreateForm((f) => ({ ...f, product_id: e.target.value }))}>
              <option value="">— select —</option>
              {products.map((p) => <option key={p.id} value={p.id}>{p.name} ({p.sku})</option>)}
            </select>
          </div>
          <div>
            <label className="text-xs font-medium text-muted-foreground">Kit Name</label>
            <input className="border rounded px-2 py-1.5 text-sm w-full mt-1" value={createForm.name} onChange={(e) => setCreateForm((f) => ({ ...f, name: e.target.value }))} />
          </div>
          <div className="col-span-2 flex gap-2">
            <button onClick={createKit} className="bg-primary text-primary-foreground rounded px-3 py-1.5 text-sm">Create Kit</button>
            <button onClick={() => setShowCreate(false)} className="border rounded px-3 py-1.5 text-sm">Cancel</button>
          </div>
        </div>
      )}

      {buildingKit && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50">
          <div className="bg-background rounded-lg p-6 max-w-sm w-full shadow-lg">
            <h3 className="font-semibold mb-1">Build Kit: {buildingKit.name}</h3>
            <p className="text-xs text-muted-foreground mb-4">This will immediately consume components and increment finished goods stock.</p>
            <div className="space-y-3">
              <div>
                <label className="text-xs font-medium text-muted-foreground">Quantity to Build</label>
                <input type="number" min={1} className="border rounded px-2 py-1.5 text-sm w-full mt-1" value={buildForm.qty} onChange={(e) => setBuildForm((f) => ({ ...f, qty: parseInt(e.target.value) || 1 }))} />
              </div>
              <div>
                <label className="text-xs font-medium text-muted-foreground">Warehouse</label>
                <select className="border rounded px-2 py-1.5 text-sm w-full mt-1" value={buildForm.warehouse_id} onChange={(e) => setBuildForm((f) => ({ ...f, warehouse_id: e.target.value }))}>
                  <option value="">— select —</option>
                  {warehouses.map((w) => <option key={w.id} value={w.id}>{w.name}</option>)}
                </select>
              </div>
            </div>
            <div className="flex gap-2 justify-end mt-4">
              <button onClick={() => setBuildingKit(null)} className="border rounded px-3 py-1.5 text-sm">Cancel</button>
              <button onClick={build} disabled={building} className="bg-primary text-primary-foreground rounded px-3 py-1.5 text-sm disabled:opacity-50 flex items-center gap-2">
                {building && <Loader2 className="w-3 h-3 animate-spin" />} Build
              </button>
            </div>
          </div>
        </div>
      )}

      {loading ? (
        <div className="flex items-center justify-center h-40"><Loader2 className="w-6 h-6 animate-spin" /></div>
      ) : (
        <div className="grid grid-cols-12 gap-6">
          <div className="col-span-4 space-y-3">
            {kits.map((k) => (
              <button key={k.id} onClick={() => setSelectedKit(k)} className={`w-full text-left border rounded-lg p-3 hover:bg-accent transition-colors ${selectedKit?.id === k.id ? "ring-2 ring-primary" : ""}`}>
                <div className="flex items-center justify-between mb-1">
                  <p className="font-medium text-sm">{k.name}</p>
                  {!k.is_active && <span className="text-xs text-muted-foreground">inactive</span>}
                </div>
                <p className="text-xs text-muted-foreground">{productMap[k.product_id]?.name ?? k.product_id.slice(0, 8)}</p>
                <p className="text-xs text-muted-foreground">{k.lines.length} component{k.lines.length !== 1 ? "s" : ""}</p>
                <button
                  onClick={(e) => { e.stopPropagation(); setBuildingKit(k); setBuildForm({ qty: 1, warehouse_id: "" }); }}
                  className="mt-2 flex items-center gap-1 text-xs bg-primary text-primary-foreground rounded px-2 py-1"
                >
                  <Wrench className="w-3 h-3" /> Build
                </button>
              </button>
            ))}
            {kits.length === 0 && <p className="text-sm text-muted-foreground">No kits yet.</p>}
          </div>

          <div className="col-span-8 border rounded-lg p-4">
            {selectedKit ? (
              <>
                <div className="mb-4">
                  <h3 className="font-semibold">{selectedKit.name}</h3>
                  <p className="text-xs text-muted-foreground">Finished product: {productMap[selectedKit.product_id]?.name ?? selectedKit.product_id.slice(0, 8)}</p>
                </div>
                <div className="flex items-center justify-between mb-2">
                  <h4 className="text-sm font-medium">Components</h4>
                  <button onClick={() => setShowLineForm((x) => !x)} className="flex items-center gap-1 text-xs border rounded px-2 py-1 hover:bg-accent">
                    <Plus className="w-3 h-3" /> Add
                  </button>
                </div>
                {showLineForm && (
                  <div className="border rounded p-3 mb-3 grid grid-cols-3 gap-2">
                    <div className="col-span-3">
                      <select className="border rounded px-2 py-1.5 text-xs w-full" value={lineForm.component_product_id} onChange={(e) => setLineForm((f) => ({ ...f, component_product_id: e.target.value }))}>
                        <option value="">— component product —</option>
                        {products.map((p) => <option key={p.id} value={p.id}>{p.name} ({p.sku})</option>)}
                      </select>
                    </div>
                    <input type="number" step="0.001" placeholder="Qty" className="border rounded px-2 py-1 text-xs" value={lineForm.quantity} onChange={(e) => setLineForm((f) => ({ ...f, quantity: e.target.value }))} />
                    <input placeholder="Unit" className="border rounded px-2 py-1 text-xs" value={lineForm.unit} onChange={(e) => setLineForm((f) => ({ ...f, unit: e.target.value }))} />
                    <div className="flex gap-1">
                      <button onClick={addLine} className="bg-primary text-primary-foreground rounded px-2 py-1 text-xs">Add</button>
                      <button onClick={() => setShowLineForm(false)} className="border rounded px-2 py-1 text-xs">×</button>
                    </div>
                  </div>
                )}
                {selectedKit.lines.length === 0 ? (
                  <p className="text-xs text-muted-foreground">No components. Add components to define what gets consumed when building this kit.</p>
                ) : (
                  <table className="w-full text-xs">
                    <thead><tr className="border-b text-muted-foreground"><th className="py-1 text-left">Component</th><th className="py-1 text-left">Qty / Unit</th></tr></thead>
                    <tbody className="divide-y">
                      {selectedKit.lines.map((l) => (
                        <tr key={l.id}>
                          <td className="py-1.5">{productMap[l.component_product_id]?.name ?? l.component_product_id.slice(0, 8)}</td>
                          <td className="py-1.5 font-medium">{parseFloat(l.quantity).toFixed(3).replace(/\.?0+$/, "")} {l.unit}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                )}
              </>
            ) : (
              <p className="text-sm text-muted-foreground">Select a kit to view components or click Build to assemble.</p>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
