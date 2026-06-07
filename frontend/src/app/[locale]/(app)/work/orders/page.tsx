"use client";

import { useState, useEffect } from "react";
import { toast } from "sonner";
import { Wrench, Plus, X, MapPin } from "lucide-react";
import { api } from "@/lib/api-client";

interface Staff { id: string; name: string }
interface Customer { id: string; name: string }
interface WorkOrder {
  id: string; title: string; description: string | null;
  customer_id: string | null; assigned_staff_id: string | null;
  priority: string; status: string; scheduled_date: string | null;
  location: string | null; parts_used: any[]; completed_at: string | null;
  created_at: string | null;
}

const STATUS_COLORS: Record<string, string> = {
  open: "bg-blue-100 text-blue-700", in_progress: "bg-amber-100 text-amber-700",
  completed: "bg-green-100 text-green-700", cancelled: "bg-gray-100 text-gray-600",
};

export default function WorkOrdersPage() {
  const [orders, setOrders] = useState<WorkOrder[]>([]);
  const [staff, setStaff] = useState<Staff[]>([]);
  const [customers, setCustomers] = useState<Customer[]>([]);
  const [loading, setLoading] = useState(true);
  const [filterStatus, setFilterStatus] = useState("");
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState({ title: "", description: "", customer_id: "", assigned_staff_id: "", priority: "medium", scheduled_date: "", location: "" });

  async function load() {
    const params = filterStatus ? `?status=${filterStatus}` : "";
    const [o, s, c] = await Promise.all([
      api.get<WorkOrder[]>(`/api/work/work-orders${params}`).catch(() => [] as WorkOrder[]),
      api.get<Staff[]>("/api/hr/employees").catch(() => [] as Staff[]),
      api.get<Customer[]>("/api/invoicing/customers").catch(() => [] as Customer[]),
    ]);
    setOrders(o); setStaff(s); setCustomers(c); setLoading(false);
  }

  useEffect(() => { load(); }, [filterStatus]);

  async function create() {
    if (!form.title.trim()) { toast.error("Title required"); return; }
    const body = { ...form, customer_id: form.customer_id || null, assigned_staff_id: form.assigned_staff_id || null, scheduled_date: form.scheduled_date || null };
    try {
      await api.post<WorkOrder>("/api/work/work-orders", body);
      toast.success("Work order created"); setShowForm(false); setForm({ title: "", description: "", customer_id: "", assigned_staff_id: "", priority: "medium", scheduled_date: "", location: "" }); load();
    } catch { toast.error("Failed"); }
  }

  async function updateStatus(id: string, status: string) {
    await api.patch<WorkOrder>(`/api/work/work-orders/${id}`, { status });
    load();
  }

  async function remove(id: string) {
    await api.delete(`/api/work/work-orders/${id}`);
    setOrders(prev => prev.filter(o => o.id !== id)); toast.success("Deleted");
  }

  const staffMap = Object.fromEntries(staff.map(s => [s.id, s.name]));
  const custMap = Object.fromEntries(customers.map(c => [c.id, c.name]));

  if (loading) return <div className="animate-pulse space-y-4">{[1,2,3].map(i => <div key={i} className="h-16 rounded-xl bg-gray-100" />)}</div>;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <h1 className="text-2xl font-semibold text-gray-900">Work Orders</h1>
          <p className="mt-1 text-sm text-gray-500">Field service and maintenance jobs.</p>
        </div>
        <button onClick={() => setShowForm(true)} className="btn-primary flex items-center gap-2"><Plus className="h-4 w-4" /> New Order</button>
      </div>

      {showForm && (
        <div className="rounded-xl border border-blue-200 bg-blue-50 p-5 space-y-3">
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <input className="input col-span-full" placeholder="Title" value={form.title} onChange={e => setForm(p => ({ ...p, title: e.target.value }))} />
            <select className="input" value={form.customer_id} onChange={e => setForm(p => ({ ...p, customer_id: e.target.value }))}>
              <option value="">No customer</option>{customers.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}
            </select>
            <select className="input" value={form.assigned_staff_id} onChange={e => setForm(p => ({ ...p, assigned_staff_id: e.target.value }))}>
              <option value="">Unassigned</option>{staff.map(s => <option key={s.id} value={s.id}>{s.name}</option>)}
            </select>
            <select className="input" value={form.priority} onChange={e => setForm(p => ({ ...p, priority: e.target.value }))}>
              <option value="low">Low</option><option value="medium">Medium</option><option value="high">High</option><option value="urgent">Urgent</option>
            </select>
            <input className="input" type="datetime-local" value={form.scheduled_date} onChange={e => setForm(p => ({ ...p, scheduled_date: e.target.value }))} />
            <input className="input col-span-full" placeholder="Location" value={form.location} onChange={e => setForm(p => ({ ...p, location: e.target.value }))} />
            <textarea className="input col-span-full h-20 resize-none" placeholder="Description…" value={form.description} onChange={e => setForm(p => ({ ...p, description: e.target.value }))} />
          </div>
          <div className="flex gap-2">
            <button onClick={create} className="btn-primary text-sm">Create</button>
            <button onClick={() => setShowForm(false)} className="btn-secondary text-sm">Cancel</button>
          </div>
        </div>
      )}

      <div className="flex gap-2">
        {["", "open", "in_progress", "completed", "cancelled"].map(s => (
          <button key={s} onClick={() => setFilterStatus(s)}
            className={`px-3 py-1.5 text-sm rounded-lg border ${filterStatus === s ? "border-blue-400 bg-blue-50 text-blue-700" : "border-gray-200 text-gray-600 hover:bg-gray-50"}`}>
            {s ? s.replace("_", " ") : "All"}
          </button>
        ))}
      </div>

      {orders.length === 0 && (
        <div className="text-center py-12 text-gray-400"><Wrench className="h-10 w-10 mx-auto mb-3 opacity-40" /><p>No work orders.</p></div>
      )}

      <div className="space-y-2">
        {orders.map(wo => (
          <div key={wo.id} className="rounded-xl border border-gray-200 bg-white p-4 flex items-center gap-4">
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2 flex-wrap">
                <span className="font-medium text-gray-900">{wo.title}</span>
                <span className={`text-xs px-2 py-0.5 rounded-full ${STATUS_COLORS[wo.status]}`}>{wo.status.replace("_", " ")}</span>
                <span className={`text-xs px-2 py-0.5 rounded-full ${wo.priority === "urgent" ? "bg-red-100 text-red-700" : wo.priority === "high" ? "bg-orange-100 text-orange-700" : "bg-gray-100 text-gray-600"}`}>{wo.priority}</span>
              </div>
              <div className="flex gap-3 text-xs text-gray-500 mt-0.5 flex-wrap">
                {wo.customer_id && <span>{custMap[wo.customer_id] || "Customer"}</span>}
                {wo.assigned_staff_id && <span>· {staffMap[wo.assigned_staff_id] || "Staff"}</span>}
                {wo.location && <span className="flex items-center gap-0.5"><MapPin className="h-3 w-3" />{wo.location}</span>}
                {wo.scheduled_date && <span>· {new Date(wo.scheduled_date).toLocaleDateString("sv-SE")}</span>}
              </div>
            </div>
            <div className="flex gap-1 flex-shrink-0">
              {wo.status === "open" && <button onClick={() => updateStatus(wo.id, "in_progress")} className="text-xs px-2 py-1 rounded-lg bg-amber-100 text-amber-700 hover:bg-amber-200">Start</button>}
              {wo.status === "in_progress" && <button onClick={() => updateStatus(wo.id, "completed")} className="text-xs px-2 py-1 rounded-lg bg-green-100 text-green-700 hover:bg-green-200">Complete</button>}
              <button onClick={() => remove(wo.id)} className="p-1.5 rounded-lg hover:bg-red-50 text-gray-400 hover:text-red-500"><X className="h-4 w-4" /></button>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
