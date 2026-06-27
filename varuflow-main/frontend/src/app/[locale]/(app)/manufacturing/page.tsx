"use client";

import { useEffect, useState } from "react";
import { Factory, Plus, Loader2, X, Clock, Trash2 } from "lucide-react";
import { toast } from "sonner";
import { api } from "@/lib/api-client";
import { isPlanGateError, PlanGateBlock } from "@/components/ui/PlanGate";

interface LabourLine {
  id: string;
  operator_name: string;
  hours: string;
  hourly_rate: string | null;
  notes: string | null;
}

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
  labour_lines?: LabourLine[];
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
  const [labourWo, setLabourWo] = useState<WorkOrder | null>(null);
  const [labourForm, setLabourForm] = useState({ operator_name: "", hours: "", hourly_rate: "", notes: "" });
  const [savingLabour, setSavingLabour] = useState(false);

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

  async function addLabour() {
    if (!labourWo || !labourForm.operator_name || !labourForm.hours) {
      toast.error("Operator name and hours are required");
      return;
    }
    setSavingLabour(true);
    try {
      const body: any = {
        operator_name: labourForm.operator_name,
        hours: parseFloat(labourForm.hours),
      };
      if (labourForm.hourly_rate) body.hourly_rate = parseFloat(labourForm.hourly_rate);
      if (labourForm.notes) body.notes = labourForm.notes;
      const line = await api.post(`/api/manufacturing/work-orders/${labourWo.id}/labour`, body);
      const updatedLines = [...(labourWo.labour_lines ?? []), line];
      const updatedWo = { ...labourWo, labour_lines: updatedLines };
      setLabourWo(updatedWo);
      setOrders((ords) => ords.map((o) => o.id === labourWo.id ? updatedWo : o));
      setLabourForm({ operator_name: "", hours: "", hourly_rate: "", notes: "" });
      toast.success("Labour entry added");
    } catch { toast.error("Failed to add labour entry"); }
    finally { setSavingLabour(false); }
  }

  async function deleteLabour(lineId: string) {
    if (!labourWo) return;
    try {
      await api.delete(`/api/manufacturing/work-orders/${labourWo.id}/labour/${lineId}`);
      const updatedLines = (labourWo.labour_lines ?? []).filter((l) => l.id !== lineId);
      const updatedWo = { ...labourWo, labour_lines: updatedLines };
      setLabourWo(updatedWo);
      setOrders((ords) => ords.map((o) => o.id === labourWo.id ? updatedWo : o));
      toast.success("Entry removed");
    } catch { toast.error("Failed to remove entry"); }
  }

  function totalHours(wo: WorkOrder) {
    return (wo.labour_lines ?? []).reduce((sum, l) => sum + parseFloat(l.hours || "0"), 0);
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

      {/* Labour tracking side panel */}
      {labourWo && (
        <div className="fixed inset-0 bg-black/40 flex items-end sm:items-center justify-center z-50">
          <div className="bg-background rounded-t-xl sm:rounded-xl shadow-xl w-full sm:max-w-lg max-h-[90vh] flex flex-col">
            <div className="flex items-center justify-between px-5 py-4 border-b">
              <div>
                <h3 className="font-semibold">{labourWo.order_number} — Labour</h3>
                <p className="text-xs text-muted-foreground">{bomMap[labourWo.bom_id] ?? labourWo.bom_id.slice(0, 8)}</p>
              </div>
              <button onClick={() => setLabourWo(null)} className="text-muted-foreground hover:text-foreground"><X className="w-5 h-5" /></button>
            </div>

            <div className="overflow-y-auto flex-1 px-5 py-4 space-y-4">
              {/* Summary */}
              <div className="flex gap-4 text-sm">
                <span className="text-muted-foreground">Total hours logged:</span>
                <span className="font-semibold">{totalHours(labourWo).toFixed(1)} h</span>
              </div>

              {/* Existing entries */}
              {(labourWo.labour_lines ?? []).length === 0 ? (
                <p className="text-sm text-muted-foreground">No labour entries yet.</p>
              ) : (
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b text-left text-muted-foreground text-xs">
                      <th className="pb-1.5 font-medium">Operator</th>
                      <th className="pb-1.5 font-medium text-right">Hours</th>
                      <th className="pb-1.5 font-medium text-right">Rate</th>
                      <th />
                    </tr>
                  </thead>
                  <tbody className="divide-y">
                    {(labourWo.labour_lines ?? []).map((l) => (
                      <tr key={l.id}>
                        <td className="py-2 pr-2">
                          <p>{l.operator_name}</p>
                          {l.notes && <p className="text-xs text-muted-foreground">{l.notes}</p>}
                        </td>
                        <td className="py-2 text-right font-medium">{parseFloat(l.hours).toFixed(1)} h</td>
                        <td className="py-2 text-right text-muted-foreground text-xs">
                          {l.hourly_rate ? `${parseFloat(l.hourly_rate).toFixed(0)}/h` : "—"}
                        </td>
                        <td className="py-2 pl-2">
                          <button onClick={() => deleteLabour(l.id)} className="text-muted-foreground hover:text-destructive">
                            <Trash2 className="w-3.5 h-3.5" />
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}

              {/* Add entry form */}
              {labourWo.status !== "completed" && labourWo.status !== "cancelled" && (
                <div className="border rounded-lg p-3 space-y-2">
                  <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">Log hours</p>
                  <div className="grid grid-cols-2 gap-2">
                    <div className="col-span-2">
                      <input
                        className="border rounded px-2 py-1.5 text-sm w-full"
                        placeholder="Operator name *"
                        value={labourForm.operator_name}
                        onChange={(e) => setLabourForm((f) => ({ ...f, operator_name: e.target.value }))}
                      />
                    </div>
                    <div>
                      <input
                        type="number" step="0.5" min="0"
                        className="border rounded px-2 py-1.5 text-sm w-full"
                        placeholder="Hours *"
                        value={labourForm.hours}
                        onChange={(e) => setLabourForm((f) => ({ ...f, hours: e.target.value }))}
                      />
                    </div>
                    <div>
                      <input
                        type="number" step="1" min="0"
                        className="border rounded px-2 py-1.5 text-sm w-full"
                        placeholder="Hourly rate (optional)"
                        value={labourForm.hourly_rate}
                        onChange={(e) => setLabourForm((f) => ({ ...f, hourly_rate: e.target.value }))}
                      />
                    </div>
                    <div className="col-span-2">
                      <input
                        className="border rounded px-2 py-1.5 text-sm w-full"
                        placeholder="Notes (optional)"
                        value={labourForm.notes}
                        onChange={(e) => setLabourForm((f) => ({ ...f, notes: e.target.value }))}
                      />
                    </div>
                  </div>
                  <button
                    onClick={addLabour}
                    disabled={savingLabour}
                    className="flex items-center gap-2 bg-primary text-primary-foreground rounded px-3 py-1.5 text-sm disabled:opacity-50"
                  >
                    {savingLabour && <Loader2 className="w-3 h-3 animate-spin" />}
                    Add Entry
                  </button>
                </div>
              )}
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
                      {(o.labour_lines?.length ?? 0) > 0 && (
                        <p className="text-muted-foreground">{totalHours(o).toFixed(1)} h logged</p>
                      )}
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
                        <button
                          onClick={() => setLabourWo(o)}
                          className="flex items-center gap-0.5 bg-gray-100 text-gray-700 rounded px-1.5 py-0.5 text-xs hover:bg-gray-200"
                        >
                          <Clock className="w-3 h-3" /> Labour
                        </button>
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
