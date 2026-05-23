"use client";

import { useEffect, useState } from "react";
import { Repeat2, Plus, Loader2, FileText, Trash2 } from "lucide-react";
import { toast } from "sonner";
import { api } from "@/lib/api-client";

interface Retainer {
  id: string;
  project_id: string;
  project_name: string | null;
  customer_id: string;
  customer_name: string | null;
  name: string;
  monthly_fee: number;
  monthly_cap_hours: number | null;
  billing_day: number;
  is_active: boolean;
  created_at: string;
}

interface Project {
  id: string;
  name: string;
}

interface Customer {
  id: string;
  company_name: string;
}

export default function RetainersPage() {
  const [retainers, setRetainers] = useState<Retainer[]>([]);
  const [projects, setProjects] = useState<Project[]>([]);
  const [customers, setCustomers] = useState<Customer[]>([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState({ project_id: "", customer_id: "", name: "", monthly_fee: "", monthly_cap_hours: "", billing_day: "1" });
  const [billing, setBilling] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([
      api.get("/api/projects/retainers"),
      api.get("/api/projects"),
      api.get("/api/inventory/customers?limit=500").catch(() => ({ items: [] })),
    ]).then(([ret, projs, custs]) => {
      setRetainers(ret);
      setProjects(projs);
      setCustomers(custs.items ?? custs ?? []);
    }).catch(() => toast.error("Failed to load retainers")).finally(() => setLoading(false));
  }, []);

  async function create() {
    if (!form.project_id || !form.customer_id || !form.name || !form.monthly_fee) {
      toast.error("Fill in all required fields"); return;
    }
    try {
      const created = await api.post("/api/projects/retainers", {
        project_id: form.project_id, customer_id: form.customer_id, name: form.name,
        monthly_fee: parseFloat(form.monthly_fee),
        monthly_cap_hours: form.monthly_cap_hours ? parseFloat(form.monthly_cap_hours) : undefined,
        billing_day: parseInt(form.billing_day) || 1,
      });
      setRetainers((r) => [created, ...r]);
      setShowForm(false);
      toast.success("Retainer created");
    } catch { toast.error("Failed to create retainer"); }
  }

  async function bill(id: string) {
    setBilling(id);
    try {
      const result = await api.post(`/api/projects/retainers/${id}/bill`, {});
      toast.success(`Invoice ${result.invoice_number} created — ${result.total_sek.toLocaleString()} SEK`);
    } catch (err: any) {
      toast.error(err?.detail ?? "Failed to bill retainer");
    } finally {
      setBilling(null);
    }
  }

  async function toggle(r: Retainer) {
    try {
      const updated = await api.patch(`/api/projects/retainers/${r.id}`, { is_active: !r.is_active });
      setRetainers((list) => list.map((x) => x.id === r.id ? { ...x, ...updated } : x));
    } catch { toast.error("Failed to update"); }
  }

  async function remove(id: string) {
    try {
      await api.delete(`/api/projects/retainers/${id}`);
      setRetainers((list) => list.filter((x) => x.id !== id));
      toast.success("Deleted");
    } catch { toast.error("Failed to delete"); }
  }

  return (
    <div className="p-6 max-w-5xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-2">
          <Repeat2 className="w-6 h-6" />
          <h1 className="text-2xl font-semibold">Retainer Billing</h1>
        </div>
        <button onClick={() => setShowForm((x) => !x)} className="flex items-center gap-1.5 bg-primary text-primary-foreground rounded px-3 py-1.5 text-sm">
          <Plus className="w-4 h-4" /> New Retainer
        </button>
      </div>

      {showForm && (
        <div className="border rounded-lg p-4 mb-6 grid grid-cols-2 gap-3 max-w-lg">
          <div>
            <label className="text-xs font-medium text-muted-foreground">Project</label>
            <select className="border rounded px-2 py-1.5 text-sm w-full mt-1" value={form.project_id} onChange={(e) => setForm((f) => ({ ...f, project_id: e.target.value }))}>
              <option value="">— select —</option>
              {projects.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
            </select>
          </div>
          <div>
            <label className="text-xs font-medium text-muted-foreground">Customer</label>
            <select className="border rounded px-2 py-1.5 text-sm w-full mt-1" value={form.customer_id} onChange={(e) => setForm((f) => ({ ...f, customer_id: e.target.value }))}>
              <option value="">— select —</option>
              {customers.map((c) => <option key={c.id} value={c.id}>{c.company_name}</option>)}
            </select>
          </div>
          <div className="col-span-2">
            <label className="text-xs font-medium text-muted-foreground">Retainer Name</label>
            <input className="border rounded px-2 py-1.5 text-sm w-full mt-1" value={form.name} onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))} />
          </div>
          <div>
            <label className="text-xs font-medium text-muted-foreground">Monthly Fee (SEK)</label>
            <input type="number" step="1000" className="border rounded px-2 py-1.5 text-sm w-full mt-1" value={form.monthly_fee} onChange={(e) => setForm((f) => ({ ...f, monthly_fee: e.target.value }))} />
          </div>
          <div>
            <label className="text-xs font-medium text-muted-foreground">Monthly Cap Hours</label>
            <input type="number" step="1" placeholder="optional" className="border rounded px-2 py-1.5 text-sm w-full mt-1" value={form.monthly_cap_hours} onChange={(e) => setForm((f) => ({ ...f, monthly_cap_hours: e.target.value }))} />
          </div>
          <div>
            <label className="text-xs font-medium text-muted-foreground">Billing Day (day of month)</label>
            <input type="number" min={1} max={28} className="border rounded px-2 py-1.5 text-sm w-full mt-1" value={form.billing_day} onChange={(e) => setForm((f) => ({ ...f, billing_day: e.target.value }))} />
          </div>
          <div className="col-span-2 flex gap-2">
            <button onClick={create} className="bg-primary text-primary-foreground rounded px-3 py-1.5 text-sm">Create</button>
            <button onClick={() => setShowForm(false)} className="border rounded px-3 py-1.5 text-sm">Cancel</button>
          </div>
        </div>
      )}

      {loading ? (
        <div className="flex items-center justify-center h-40"><Loader2 className="w-6 h-6 animate-spin" /></div>
      ) : retainers.length === 0 ? (
        <p className="text-sm text-muted-foreground">No retainers yet.</p>
      ) : (
        <div className="grid grid-cols-1 gap-4">
          {retainers.map((r) => (
            <div key={r.id} className={`border rounded-lg p-4 ${!r.is_active ? "opacity-60" : ""}`}>
              <div className="flex items-start justify-between">
                <div>
                  <div className="flex items-center gap-2">
                    <h3 className="font-semibold">{r.name}</h3>
                    <span className={`text-xs px-1.5 py-0.5 rounded-full font-medium ${r.is_active ? "bg-green-100 text-green-800" : "bg-gray-100 text-gray-600"}`}>
                      {r.is_active ? "Active" : "Inactive"}
                    </span>
                  </div>
                  <p className="text-xs text-muted-foreground mt-0.5">
                    {r.customer_name ?? r.customer_id.slice(0, 8)} · {r.project_name ?? r.project_id.slice(0, 8)}
                  </p>
                </div>
                <div className="text-right">
                  <p className="font-semibold">{r.monthly_fee.toLocaleString()} SEK/mo</p>
                  {r.monthly_cap_hours && <p className="text-xs text-muted-foreground">Cap: {r.monthly_cap_hours}h/mo</p>}
                  <p className="text-xs text-muted-foreground">Bills on day {r.billing_day}</p>
                </div>
              </div>
              <div className="flex gap-2 mt-3">
                {r.is_active && (
                  <button onClick={() => bill(r.id)} disabled={billing === r.id} className="flex items-center gap-1.5 bg-primary text-primary-foreground rounded px-3 py-1.5 text-xs disabled:opacity-50">
                    {billing === r.id ? <Loader2 className="w-3 h-3 animate-spin" /> : <FileText className="w-3 h-3" />}
                    Bill Now
                  </button>
                )}
                <button onClick={() => toggle(r)} className="border rounded px-3 py-1.5 text-xs hover:bg-accent">
                  {r.is_active ? "Pause" : "Activate"}
                </button>
                <button onClick={() => remove(r.id)} className="border rounded px-3 py-1.5 text-xs text-destructive hover:bg-red-50 ml-auto">
                  <Trash2 className="w-3 h-3" />
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
