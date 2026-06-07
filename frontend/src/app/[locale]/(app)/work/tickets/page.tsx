"use client";

import { useState, useEffect } from "react";
import { toast } from "sonner";
import { Ticket, Plus, X } from "lucide-react";
import { api } from "@/lib/api-client";

interface Staff { id: string; name: string }
interface Customer { id: string; name: string }
interface TicketItem {
  id: string; title: string; description: string | null;
  customer_id: string | null; assigned_staff_id: string | null;
  category: string | null; priority: string; status: string;
  due_date: string | null; resolution_notes: string | null;
  created_at: string | null;
}

const STATUS_COLORS: Record<string, string> = {
  open: "bg-blue-100 text-blue-700", in_progress: "bg-amber-100 text-amber-700",
  waiting: "bg-purple-100 text-purple-700", resolved: "bg-green-100 text-green-700",
  closed: "bg-gray-100 text-gray-600",
};
const PRIORITY_COLORS: Record<string, string> = {
  low: "bg-gray-200 text-gray-600", medium: "bg-amber-100 text-amber-700",
  high: "bg-red-100 text-red-700", urgent: "bg-red-200 text-red-800",
};

export default function TicketsPage() {
  const [tickets, setTickets] = useState<TicketItem[]>([]);
  const [staff, setStaff] = useState<Staff[]>([]);
  const [customers, setCustomers] = useState<Customer[]>([]);
  const [loading, setLoading] = useState(true);
  const [filterStatus, setFilterStatus] = useState("");
  const [filterPriority, setFilterPriority] = useState("");
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState({ title: "", description: "", customer_id: "", assigned_staff_id: "", category: "", priority: "medium", due_date: "" });

  async function load() {
    const params = new URLSearchParams();
    if (filterStatus) params.set("status", filterStatus);
    if (filterPriority) params.set("priority", filterPriority);
    const [t, s, c] = await Promise.all([
      api.get<TicketItem[]>(`/api/work/tickets${params.toString() ? "?" + params : ""}`).catch(() => [] as TicketItem[]),
      api.get<Staff[]>("/api/hr/employees").catch(() => [] as Staff[]),
      api.get<Customer[]>("/api/invoicing/customers").catch(() => [] as Customer[]),
    ]);
    setTickets(t); setStaff(s); setCustomers(c); setLoading(false);
  }

  useEffect(() => { load(); }, [filterStatus, filterPriority]);

  async function create() {
    if (!form.title.trim()) { toast.error("Title required"); return; }
    const body = { ...form, customer_id: form.customer_id || null, assigned_staff_id: form.assigned_staff_id || null, due_date: form.due_date || null, category: form.category || null };
    try {
      await api.post<TicketItem>("/api/work/tickets", body);
      toast.success("Ticket created"); setShowForm(false); setForm({ title: "", description: "", customer_id: "", assigned_staff_id: "", category: "", priority: "medium", due_date: "" }); load();
    } catch { toast.error("Failed"); }
  }

  async function updateStatus(id: string, status: string) {
    await api.patch<TicketItem>(`/api/work/tickets/${id}`, { status });
    load();
  }

  async function remove(id: string) {
    await api.delete(`/api/work/tickets/${id}`);
    setTickets(prev => prev.filter(t => t.id !== id)); toast.success("Deleted");
  }

  const staffMap = Object.fromEntries(staff.map(s => [s.id, s.name]));
  const custMap = Object.fromEntries(customers.map(c => [c.id, c.name]));

  if (loading) return <div className="animate-pulse space-y-4">{[1,2,3].map(i => <div key={i} className="h-16 rounded-xl bg-gray-100" />)}</div>;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <h1 className="text-2xl font-semibold text-gray-900">Tickets</h1>
          <p className="mt-1 text-sm text-gray-500">Service request queue for repairs, IT support, and more.</p>
        </div>
        <button onClick={() => setShowForm(true)} className="btn-primary flex items-center gap-2"><Plus className="h-4 w-4" /> New Ticket</button>
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
            <input className="input" placeholder="Category" value={form.category} onChange={e => setForm(p => ({ ...p, category: e.target.value }))} />
            <select className="input" value={form.priority} onChange={e => setForm(p => ({ ...p, priority: e.target.value }))}>
              <option value="low">Low</option><option value="medium">Medium</option><option value="high">High</option><option value="urgent">Urgent</option>
            </select>
            <input className="input" type="date" value={form.due_date} onChange={e => setForm(p => ({ ...p, due_date: e.target.value }))} />
            <textarea className="input col-span-full h-20 resize-none" placeholder="Description…" value={form.description} onChange={e => setForm(p => ({ ...p, description: e.target.value }))} />
          </div>
          <div className="flex gap-2">
            <button onClick={create} className="btn-primary text-sm">Create</button>
            <button onClick={() => setShowForm(false)} className="btn-secondary text-sm">Cancel</button>
          </div>
        </div>
      )}

      <div className="flex gap-2 flex-wrap">
        <select className="input text-sm w-36" value={filterStatus} onChange={e => setFilterStatus(e.target.value)}>
          <option value="">All statuses</option>
          <option value="open">Open</option><option value="in_progress">In Progress</option>
          <option value="waiting">Waiting</option><option value="resolved">Resolved</option><option value="closed">Closed</option>
        </select>
        <select className="input text-sm w-32" value={filterPriority} onChange={e => setFilterPriority(e.target.value)}>
          <option value="">All priorities</option>
          <option value="low">Low</option><option value="medium">Medium</option><option value="high">High</option><option value="urgent">Urgent</option>
        </select>
      </div>

      {tickets.length === 0 && (
        <div className="text-center py-12 text-gray-400"><Ticket className="h-10 w-10 mx-auto mb-3 opacity-40" /><p>No tickets.</p></div>
      )}

      <div className="space-y-2">
        {tickets.map(t => (
          <div key={t.id} className="rounded-xl border border-gray-200 bg-white p-4 flex items-center gap-4">
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2 flex-wrap">
                <span className="font-medium text-gray-900">{t.title}</span>
                <span className={`text-xs px-2 py-0.5 rounded-full ${STATUS_COLORS[t.status]}`}>{t.status.replace("_", " ")}</span>
                <span className={`text-xs px-2 py-0.5 rounded-full ${PRIORITY_COLORS[t.priority]}`}>{t.priority}</span>
                {t.category && <span className="text-xs px-2 py-0.5 rounded bg-gray-100 text-gray-600">{t.category}</span>}
              </div>
              <div className="flex gap-3 text-xs text-gray-500 mt-0.5">
                {t.customer_id && <span>{custMap[t.customer_id] || "Customer"}</span>}
                {t.assigned_staff_id && <span>· {staffMap[t.assigned_staff_id] || "Staff"}</span>}
                {t.due_date && <span>· Due: {t.due_date}</span>}
              </div>
            </div>
            <div className="flex gap-1 flex-shrink-0">
              {t.status === "open" && <button onClick={() => updateStatus(t.id, "in_progress")} className="text-xs px-2 py-1 rounded-lg bg-amber-100 text-amber-700">Start</button>}
              {t.status === "in_progress" && <button onClick={() => updateStatus(t.id, "resolved")} className="text-xs px-2 py-1 rounded-lg bg-green-100 text-green-700">Resolve</button>}
              <button onClick={() => remove(t.id)} className="p-1.5 rounded-lg hover:bg-red-50 text-gray-400 hover:text-red-500"><X className="h-4 w-4" /></button>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
