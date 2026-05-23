"use client";

import { api } from "@/lib/api-client";
import { useEffect, useState } from "react";
import { useRouter, useParams } from "next/navigation";
import { toast } from "sonner";
import {
  Package, Plus, RefreshCw, ChevronRight, ArrowUp, ArrowDown,
  CheckCircle, AlertTriangle, TrendingUp, Layers
} from "lucide-react";

interface KitComponent {
  component_product_id: string;
  quantity: number;
}

interface Kit {
  id: string;
  product_id: string;
  product_name?: string;
  name: string;
  description?: string;
  custom_price?: number;
  effective_price: number;
  component_cost: number;
  margin_percent: number;
  is_active: boolean;
  components: KitComponent[];
  availability: {
    max_kits_assembleable: number;
    components: Array<{
      component_product_id: string;
      quantity_required_per_kit: number;
      stock_available: number;
      kits_possible_from_this_component: number;
    }>;
  };
}

interface AssemblyLog {
  id: string;
  direction: string;
  quantity: number;
  notes?: string;
  assembled_at: string;
}

export default function KittingPage() {
  const router = useRouter();
  const params = useParams();
  const locale = params.locale as string;

  const [kits, setKits] = useState<Kit[]>([]);
  const [loading, setLoading] = useState(true);
  const [selected, setSelected] = useState<Kit | null>(null);
  const [log, setLog] = useState<AssemblyLog[]>([]);
  const [showCreate, setShowCreate] = useState(false);
  const [assembleDir, setAssembleDir] = useState<"assemble" | "disassemble" | null>(null);
  const [assembleQty, setAssembleQty] = useState("1");
  const [assembleNote, setAssembleNote] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const [form, setForm] = useState({
    name: "", description: "", custom_price: "",
    product_id: "",
    components: [{ component_product_id: "", quantity: "1" }],
  });

  async function load() {
    try {
      const data = await api.get("/api/kits");
      setKits(data.items ?? data);
    } catch (err: any) {
      if (err?.status === 401) router.push(`/${locale}/auth/login`);
      else toast.error("Failed to load kits");
    } finally {
      setLoading(false);
    }
  }

  async function loadLog(kitId: string) {
    try {
      const data = await api.get(`/api/kits/${kitId}/assemblies`);
      setLog(data.items ?? data);
    } catch {
      setLog([]);
    }
  }

  useEffect(() => { load(); }, []);

  function selectKit(kit: Kit) {
    setSelected(kit);
    loadLog(kit.id);
    setAssembleDir(null);
  }

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    setSubmitting(true);
    try {
      await api.post("/api/kits", {
        name: form.name,
        description: form.description || undefined,
        product_id: form.product_id,
        custom_price: form.custom_price ? parseFloat(form.custom_price) : undefined,
        components: form.components
          .filter(c => c.component_product_id)
          .map(c => ({ component_product_id: c.component_product_id, quantity: parseFloat(c.quantity) })),
      });
      toast.success("Kit created");
      setShowCreate(false);
      setForm({ name: "", description: "", custom_price: "", product_id: "", components: [{ component_product_id: "", quantity: "1" }] });
      load();
    } catch {
      toast.error("Failed to create kit");
    } finally {
      setSubmitting(false);
    }
  }

  async function handleAssemble() {
    if (!selected || !assembleDir) return;
    setSubmitting(true);
    try {
      await api.post(`/api/kits/${selected.id}/assemble`, {
        direction: assembleDir,
        quantity: parseFloat(assembleQty),
        notes: assembleNote || undefined,
      });
      toast.success(assembleDir === "assemble" ? "Kit assembled successfully" : "Kit disassembled successfully");
      setAssembleDir(null);
      setAssembleQty("1");
      setAssembleNote("");
      await load();
      // Refresh selected kit
      const fresh = await api.get(`/api/kits/${selected.id}`);
      setSelected(fresh);
      loadLog(selected.id);
    } catch (err: any) {
      toast.error(err?.detail ?? "Operation failed");
    } finally {
      setSubmitting(false);
    }
  }

  const availColor = (n: number) => n === 0 ? "text-red-600" : n < 5 ? "text-amber-500" : "text-green-600";

  return (
    <div className="flex h-full">
      {/* Left: kit list */}
      <div className="w-72 border-r flex flex-col bg-background">
        <div className="p-4 border-b flex items-center justify-between">
          <h2 className="font-semibold text-sm">Kit Definitions</h2>
          <button className="btn-primary text-xs px-2 py-1 flex items-center gap-1" onClick={() => setShowCreate(true)}>
            <Plus className="h-3 w-3" /> New Kit
          </button>
        </div>
        {loading ? (
          <div className="flex-1 flex items-center justify-center">
            <RefreshCw className="h-5 w-5 animate-spin text-muted-foreground" />
          </div>
        ) : kits.length === 0 ? (
          <div className="flex-1 flex flex-col items-center justify-center p-6 text-center">
            <Layers className="h-10 w-10 text-muted-foreground mb-3" />
            <p className="text-sm font-medium">No kits defined</p>
            <p className="text-xs text-muted-foreground mt-1">Create your first kit bundle</p>
          </div>
        ) : (
          <div className="flex-1 overflow-y-auto">
            {kits.map(kit => (
              <button
                key={kit.id}
                onClick={() => selectKit(kit)}
                className={`w-full text-left px-4 py-3 border-b hover:bg-muted/40 transition-colors flex items-center justify-between
                  ${selected?.id === kit.id ? "bg-primary/5 border-l-2 border-l-primary" : ""}`}
              >
                <div className="min-w-0">
                  <p className="font-medium text-sm truncate">{kit.name}</p>
                  <p className={`text-xs font-semibold mt-0.5 ${availColor(kit.availability.max_kits_assembleable)}`}>
                    {kit.availability.max_kits_assembleable} available
                  </p>
                </div>
                <ChevronRight className="h-4 w-4 text-muted-foreground flex-shrink-0" />
              </button>
            ))}
          </div>
        )}
      </div>

      {/* Right: kit detail */}
      <div className="flex-1 overflow-y-auto p-6">
        {!selected ? (
          <div className="flex flex-col items-center justify-center h-full text-center">
            <Package className="h-16 w-16 text-muted-foreground mb-4" />
            <h2 className="text-xl font-semibold">Select a Kit</h2>
            <p className="text-sm text-muted-foreground mt-2">
              Choose a kit from the left panel to view details, check availability, or run assembly
            </p>
          </div>
        ) : (
          <div className="max-w-2xl space-y-6">
            <div className="flex items-start justify-between">
              <div>
                <h1 className="text-2xl font-bold">{selected.name}</h1>
                {selected.description && (
                  <p className="text-sm text-muted-foreground mt-1">{selected.description}</p>
                )}
              </div>
              <span className={`text-xs px-2 py-1 rounded-full font-medium ${selected.is_active ? "bg-green-100 text-green-700" : "bg-gray-100 text-gray-600"}`}>
                {selected.is_active ? "Active" : "Inactive"}
              </span>
            </div>

            {/* Price & margin cards */}
            <div className="grid grid-cols-3 gap-4">
              <div className="rounded-xl border bg-card p-4">
                <p className="text-xs text-muted-foreground">Kit Price</p>
                <p className="text-xl font-bold mt-1">{selected.effective_price.toFixed(2)}</p>
                {selected.custom_price && <p className="text-xs text-muted-foreground">Custom</p>}
              </div>
              <div className="rounded-xl border bg-card p-4">
                <p className="text-xs text-muted-foreground">Component Cost</p>
                <p className="text-xl font-bold mt-1">{selected.component_cost.toFixed(2)}</p>
              </div>
              <div className="rounded-xl border bg-card p-4">
                <p className="text-xs text-muted-foreground">Margin</p>
                <p className={`text-xl font-bold mt-1 flex items-center gap-1 ${selected.margin_percent >= 0 ? "text-green-600" : "text-red-600"}`}>
                  <TrendingUp className="h-4 w-4" />
                  {selected.margin_percent.toFixed(1)}%
                </p>
              </div>
            </div>

            {/* Availability */}
            <div className="rounded-xl border bg-card p-4 space-y-3">
              <div className="flex items-center justify-between">
                <h3 className="font-semibold">Component Availability</h3>
                <span className={`text-lg font-bold ${availColor(selected.availability.max_kits_assembleable)}`}>
                  {selected.availability.max_kits_assembleable} kits ready
                </span>
              </div>
              <div className="space-y-2">
                {selected.availability.components.map((c, i) => (
                  <div key={i} className="flex items-center justify-between text-sm border rounded-lg p-2">
                    <span className="text-muted-foreground font-mono text-xs">{c.component_product_id.slice(0, 8)}…</span>
                    <span>Req: {c.quantity_required_per_kit}</span>
                    <span className={c.stock_available >= c.quantity_required_per_kit ? "text-green-600" : "text-red-600"}>
                      Stock: {c.stock_available}
                    </span>
                    <span className={`font-medium ${c.kits_possible_from_this_component === 0 ? "text-red-600" : "text-muted-foreground"}`}>
                      → {Math.floor(c.kits_possible_from_this_component)} kits
                    </span>
                  </div>
                ))}
              </div>
            </div>

            {/* Assemble / Disassemble */}
            <div className="rounded-xl border bg-card p-4 space-y-3">
              <h3 className="font-semibold">Assembly Actions</h3>
              {assembleDir ? (
                <div className="space-y-3">
                  <p className="text-sm font-medium text-primary capitalize">{assembleDir} kits</p>
                  <div className="grid grid-cols-2 gap-3">
                    <div>
                      <label className="text-xs font-medium text-muted-foreground">Quantity</label>
                      <input
                        type="number" min="1" step="1" className="input mt-1 w-full"
                        value={assembleQty}
                        onChange={e => setAssembleQty(e.target.value)}
                      />
                    </div>
                    <div>
                      <label className="text-xs font-medium text-muted-foreground">Notes (optional)</label>
                      <input className="input mt-1 w-full" value={assembleNote} onChange={e => setAssembleNote(e.target.value)} />
                    </div>
                  </div>
                  <div className="flex gap-2">
                    <button className="btn-secondary text-sm" onClick={() => setAssembleDir(null)}>Cancel</button>
                    <button className="btn-primary text-sm flex items-center gap-2" onClick={handleAssemble} disabled={submitting}>
                      {submitting && <RefreshCw className="h-3.5 w-3.5 animate-spin" />}
                      Confirm {assembleDir}
                    </button>
                  </div>
                </div>
              ) : (
                <div className="flex gap-3">
                  <button
                    className="btn-primary flex items-center gap-2 text-sm"
                    onClick={() => setAssembleDir("assemble")}
                    disabled={selected.availability.max_kits_assembleable === 0}
                  >
                    <ArrowUp className="h-4 w-4" /> Assemble
                  </button>
                  <button
                    className="btn-secondary flex items-center gap-2 text-sm"
                    onClick={() => setAssembleDir("disassemble")}
                  >
                    <ArrowDown className="h-4 w-4" /> Disassemble
                  </button>
                </div>
              )}
            </div>

            {/* Assembly log */}
            {log.length > 0 && (
              <div className="rounded-xl border bg-card overflow-hidden">
                <h3 className="font-semibold px-4 py-3 border-b">Assembly Log</h3>
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead className="bg-muted/50">
                      <tr>
                        <th className="text-left px-4 py-2 font-medium">Action</th>
                        <th className="text-right px-4 py-2 font-medium">Qty</th>
                        <th className="text-left px-4 py-2 font-medium">Notes</th>
                        <th className="text-left px-4 py-2 font-medium">Date</th>
                      </tr>
                    </thead>
                    <tbody>
                      {log.map(entry => (
                        <tr key={entry.id} className="border-t">
                          <td className="px-4 py-2">
                            <span className={`flex items-center gap-1 text-xs font-medium ${entry.direction === "assemble" ? "text-green-600" : "text-amber-600"}`}>
                              {entry.direction === "assemble" ? <ArrowUp className="h-3 w-3" /> : <ArrowDown className="h-3 w-3" />}
                              {entry.direction}
                            </span>
                          </td>
                          <td className="px-4 py-2 text-right font-medium">{entry.quantity}</td>
                          <td className="px-4 py-2 text-muted-foreground">{entry.notes ?? "—"}</td>
                          <td className="px-4 py-2 text-muted-foreground">
                            {new Date(entry.assembled_at).toLocaleDateString("sv-SE")}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}
          </div>
        )}
      </div>

      {/* Create Kit modal */}
      {showCreate && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
          <div className="bg-background rounded-2xl shadow-xl w-full max-w-lg p-6 space-y-4 max-h-[90vh] overflow-y-auto">
            <h2 className="text-lg font-semibold">Create Kit Definition</h2>
            <form onSubmit={handleCreate} className="space-y-4">
              <div>
                <label className="text-sm font-medium">Kit Name</label>
                <input required className="input mt-1 w-full" value={form.name} onChange={e => setForm(f => ({ ...f, name: e.target.value }))} />
              </div>
              <div>
                <label className="text-sm font-medium">Kit Product ID (finished SKU)</label>
                <input required className="input mt-1 w-full font-mono text-sm" placeholder="UUID of the kit product" value={form.product_id} onChange={e => setForm(f => ({ ...f, product_id: e.target.value }))} />
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="text-sm font-medium">Description (optional)</label>
                  <input className="input mt-1 w-full" value={form.description} onChange={e => setForm(f => ({ ...f, description: e.target.value }))} />
                </div>
                <div>
                  <label className="text-sm font-medium">Custom Price (optional)</label>
                  <input type="number" step="0.01" className="input mt-1 w-full" placeholder="Leave blank = sum of components" value={form.custom_price} onChange={e => setForm(f => ({ ...f, custom_price: e.target.value }))} />
                </div>
              </div>
              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <label className="text-sm font-medium">Components</label>
                  <button type="button" className="text-xs text-primary hover:underline" onClick={() => setForm(f => ({ ...f, components: [...f.components, { component_product_id: "", quantity: "1" }] }))}>
                    + Add component
                  </button>
                </div>
                {form.components.map((comp, i) => (
                  <div key={i} className="flex gap-2 items-center">
                    <input
                      className="input flex-1 font-mono text-xs"
                      placeholder="Component product ID"
                      value={comp.component_product_id}
                      onChange={e => setForm(f => ({
                        ...f,
                        components: f.components.map((c, j) => j === i ? { ...c, component_product_id: e.target.value } : c)
                      }))}
                    />
                    <input
                      type="number" step="0.01" min="0.01"
                      className="input w-20"
                      placeholder="Qty"
                      value={comp.quantity}
                      onChange={e => setForm(f => ({
                        ...f,
                        components: f.components.map((c, j) => j === i ? { ...c, quantity: e.target.value } : c)
                      }))}
                    />
                    {form.components.length > 1 && (
                      <button type="button" className="text-red-500 text-xs" onClick={() => setForm(f => ({ ...f, components: f.components.filter((_, j) => j !== i) }))}>✕</button>
                    )}
                  </div>
                ))}
              </div>
              <div className="flex gap-3 pt-2">
                <button type="button" className="btn-secondary flex-1" onClick={() => setShowCreate(false)}>Cancel</button>
                <button type="submit" className="btn-primary flex-1" disabled={submitting}>
                  {submitting ? <RefreshCw className="h-4 w-4 animate-spin mx-auto" /> : "Create Kit"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
