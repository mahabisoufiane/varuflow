"use client";

import { useEffect, useState } from "react";
import { Factory, Plus, Loader2, ChevronRight } from "lucide-react";
import { toast } from "sonner";
import { api } from "@/lib/api-client";
import { isPlanGateError, PlanGateBlock } from "@/components/ui/PlanGate";

interface WorkOrder {
  id: string;
  order_number: string;
  bom_id: string;
  warehouse_id: string;
  status: string;
  planned_qty: number;
  produced_qty: number;
  scheduled_start: string | null;
  scheduled_end: string | null;
  notes: string | null;
}

interface Bom {
  id: string;
  name: string;
  product_id: string;
  is_kit?: boolean;
}

interface Warehouse {
  id: string;
  name: string;
}

const STATUSES = ["draft", "planned", "in_progress", "completed", "cancelled"] as const;
const STATUS_LABELS: Record<string, string> = {
  draft: "Draft",
  planned: "Planned",
  in_progress: "In Progress",
  completed: "Completed",
  cancelled: "Cancelled",
};
const STATUS_COLORS: Record<string, string> = {
  draft: "border-gray-200 bg-gray-50",
  planned: "border-blue-200 bg-blue-50",
  in_progress: "border-yellow-200 bg-yellow-50",
  completed: "border-green-200 bg-green-50",
  cancelled: "border-red-200 bg-red-50",
};

export default function ManufacturingPage() {
  const [orders, setOrders] = useState<WorkOrder[]>([]);
  const [boms, setBoms] = useState<Bom[]>([]);
  const [warehouses, setWarehouses] = useState<Warehouse[]>([]);
  const [loading, setLoading] = useState(true);
  const [planBlocked, setPlanBlocked] = useState<{ module: string; currentPlan: string } | null>(null);
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState({ bom_id: "", warehouse_id: "", planned_qty: 1, notes: "" });
  const [completing, setCompleting] = useState<string | null>(null);
  const [completeQty, setCompleteQty] = useState(1);

  async function load() {
    try {
      const [wos, bomList, whList] = await Promise.all([
        api.get("/api/manufacturing/work-orders"),
        api.get("/api/manufacturing/boms"),
        api.get("/api/inventory/warehouses").catch(() => []),
      ]);
      setOrders(wos);
      setBoms(bomList);
      setWarehouses(whList);
    } catch (err) {
      if (isPlanGateError(err)) {
        setPlanBlocked({ module: (err as any).module ?? "manufacturing", currentPlan: (err as any).currentPlan ?? "FREE" });
      } else {
        toast.error("Failed to load work orders");
      }
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { load(); }, []);

  async function create() {
    if (!form.bom_id || !form.warehouse_id) { toast.error("Select BOM and warehouse"); return; }
    try {
      const created = await api.post("/api/manufacturing/work-orders", form);
      setOrders((o) => [created, ...o]);
      setShowForm(false);
      toast.success(`Work order ${created.order_number} created`);
    } catch { toast.error("Failed to create work order"); }
  }

  async function transition(id: string, action: "plan" | "start" | "cancel") {
    try {
      const updated = await api.post(`/api/manufacturing/work-orders/${id}/${action}`, {});
      setOrders((ords) => ords.map((o) => (o.id === id ? { ...o, ...updated } : o)));
      toast.success("Updated");
    } catch (err: any) {
      const detail = err?.detail?.message ?? err?.detail ?? "Failed";
      toast.error(typeof detail === "string" ? detail : "Stock shortage — check Planning page");
    }
  }

  async function complete(id: string) {
    try {
      const updated = await api.post(`/api/manufacturing/work-orders/${id}/complete`, { produced_qty: completeQty });
      setOrders((ords) => ords.map((o) => (o.id === id ? { ...o, ...updated } : o)));
      setCompleting(null);
      toast.success(`Completed — ${completeQty} units produced`);
    } catch { toast.error("Failed to complete work order"); }
  }

  const bomMap = Object.fromEntries(boms.map((b) => [b.id, b.name]));

  if (planBlocked) {
    return <PlanGateBlock module={planBlocked.module} currentPlan={planBlocked.currentPlan} featureName="Manufacturing" />;
  }

  return (
    <div className="p-6 max-w-7xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-2">
          <Factory className="w-6 h-6" />
          <h1 className="text-2xl font-semibold">Work Orders</h1>
        </div>
        <button onClick={() => setShowForm((x) => !x)} className="flex items-center gap-1.5 bg-primary text-primary-foreground rounded px-3 py-1.5 text-sm">
          <Plus className="w-4 h-4" /> New Work Order
        </button>
      </div>

      {showForm && (
        <div className="border rounded p-4 mb-6 grid grid-cols-2 gap-3 max-w-lg">
          <div>
            <label className="text-xs font-medium text-muted-foreground">BOM</label>
            <select className="border rounded px-2 py-1.5 text-sm w-full mt-1" value={form.bom_id} onChange={(e) => setForm((f) => ({ ...f, bom_id: e.target.value }))}>
              <option value="">— select —</option>
              {boms.filter((b) => !b.is_kit).map((b) => <option key={b.id} value={b.id}>{b.name}</option>)}
            </select>
          </div>
          <div>
            <label className="text-xs font-medium text-muted-foreground">Warehouse</label>
            <select className="border rounded px-2 py-1.5 text-sm w-full mt-1" value={form.warehouse_id} onChange={(e) => setForm((f) => ({ ...f, warehouse_id: e.target.value }))}>
              <option value="">— select —</option>
              {warehouses.map((w) => <option key={w.id} value={w.id}>{w.name}</option>)}
            </select>
          </div>
          <div>
            <label className="text-xs font-medium text-muted-foreground">Planned Qty</label>
            <input type="number" min={1} className="border rounded px-2 py-1.5 text-sm w-full mt-1" value={form.planned_qty} onChange={(e) => setForm((f) => ({ ...f, planned_qty: parseInt(e.target.value) || 1 }))} />
          </div>
          <div>
            <label className="text-xs font-medium text-muted-foreground">Notes</label>
            <input className="border rounded px-2 py-1.5 text-sm w-full mt-1" value={form.notes} onChange={(e) => setForm((f) => ({ ...f, notes: e.target.value }))} />
          </div>
          <div className="col-span-2 flex gap-2">
            <button onClick={create} className="bg-primary text-primary-foreground rounded px-3 py-1.5 text-sm">Create</button>
            <button onClick={() => setShowForm(false)} className="border rounded px-3 py-1.5 text-sm">Cancel</button>
          </div>
        </div>
      )}

      {completing && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50">
          <div className="bg-background rounded-lg p-6 max-w-xs w-full shadow-lg">
            <h3 className="font-semibold mb-3">Complete Work Order</h3>
            <label className="text-xs font-medium text-muted-foreground">Produced Qty</label>
            <input type="number" min={0} className="border rounded px-2 py-1.5 text-sm w-full mt-1 mb-4" value={completeQty} onChange={(e) => setCompleteQty(parseInt(e.target.value) || 0)} />
            <div className="flex gap-2 justify-end">
              <button onClick={() => setCompleting(null)} className="border rounded px-3 py-1.5 text-sm">Cancel</button>
              <button onClick={() => complete(completing)} className="bg-green-600 text-white rounded px-3 py-1.5 text-sm">Complete</button>
            </div>
          </div>
        </div>
      )}

      {loading ? (
        <div className="flex items-center justify-center h-40"><Loader2 className="w-6 h-6 animate-spin" /></div>
      ) : (
        <div className="grid grid-cols-5 gap-3">
          {STATUSES.map((status) => {
            const col = orders.filter((o) => o.status === status);
            return (
              <div key={status} className={`rounded-lg border-2 p-3 min-h-40 ${STATUS_COLORS[status]}`}>
                <p className="text-xs font-semibold uppercase tracking-wide mb-3">{STATUS_LABELS[status]} <span className="font-normal">({col.length})</span></p>
                <div className="space-y-2">
                  {col.map((o) => (
                    <div key={o.id} className="bg-white rounded border p-2 text-xs shadow-sm">
                      <p className="font-semibold">{o.order_number}</p>
                      <p className="text-muted-foreground truncate">{bomMap[o.bom_id] ?? o.bom_id.slice(0, 8)}</p>
                      <p className="mt-1">{o.produced_qty}/{o.planned_qty} units</p>
                      <div className="flex gap-1 mt-2 flex-wrap">
                        {o.status === "draft" && (
                          <button onClick={() => transition(o.id, "plan")} className="bg-blue-100 text-blue-800 rounded px-1.5 py-0.5 text-xs hover:bg-blue-200">Plan</button>
                        )}
                        {o.status === "planned" && (
                          <button onClick={() => transition(o.id, "start")} className="bg-yellow-100 text-yellow-800 rounded px-1.5 py-0.5 text-xs hover:bg-yellow-200">Start</button>
                        )}
                        {o.status === "in_progress" && (
                          <button onClick={() => { setCompleting(o.id); setCompleteQty(o.planned_qty); }} className="bg-green-100 text-green-800 rounded px-1.5 py-0.5 text-xs hover:bg-green-200">Complete</button>
                        )}
                        {(o.status === "draft" || o.status === "planned" || o.status === "in_progress") && (
                          <button onClick={() => transition(o.id, "cancel")} className="bg-red-50 text-red-700 rounded px-1.5 py-0.5 text-xs hover:bg-red-100">Cancel</button>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
