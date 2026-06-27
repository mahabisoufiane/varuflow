"use client";

import { useEffect, useState } from "react";
import { Clock, Plus, Loader2, FileText, Trash2 } from "lucide-react";
import { toast } from "sonner";
import { api } from "@/lib/api-client";
import { isPlanGateError, PlanGateBlock } from "@/components/ui/PlanGate";

interface TimeEntry {
  id: string;
  project_id: string;
  project_name: string | null;
  operator_name: string | null;
  entry_date: string;
  description: string | null;
  hours: number;
  hourly_rate: number;
  billable: boolean;
  invoiced: boolean;
  invoice_id: string | null;
}

interface Project {
  id: string;
  name: string;
  default_hourly_rate: number | null;
  customer_id: string | null;
}

interface Customer {
  id: string;
  company_name: string;
}

export default function TimeEntriesPage() {
  const [entries, setEntries] = useState<TimeEntry[]>([]);
  const [projects, setProjects] = useState<Project[]>([]);
  const [customers, setCustomers] = useState<Customer[]>([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState({ project_id: "", operator_name: "", entry_date: new Date().toISOString().slice(0, 10), description: "", hours: "", hourly_rate: "", billable: true });
  const [filterProject, setFilterProject] = useState("");
  const [filterInvoiced, setFilterInvoiced] = useState<"" | "true" | "false">("");
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [invoiceModal, setInvoiceModal] = useState(false);
  const [invoiceForm, setInvoiceForm] = useState({ customer_id: "", tax_rate: "25" });
  const [generating, setGenerating] = useState(false);
  const [planBlocked, setPlanBlocked] = useState<{ module: string; currentPlan: string } | null>(null);

  async function load() {
    try {
      const params = new URLSearchParams();
      if (filterProject) params.set("project_id", filterProject);
      if (filterInvoiced) params.set("invoiced", filterInvoiced);
      const [entriesList, projList, custResult] = await Promise.all([
        api.get(`/api/projects/time-entries${params.size ? "?" + params : ""}`),
        api.get("/api/projects"),
        api.get("/api/inventory/customers?limit=500").catch(() => ({ items: [] })),
      ]);
      setEntries(entriesList);
      setProjects(projList);
      setCustomers(custResult.items ?? custResult ?? []);
    } catch (err) {
      if (isPlanGateError(err)) {
        setPlanBlocked({ module: (err as any).module ?? "hr", currentPlan: (err as any).currentPlan ?? "FREE" });
        return;
      }
      toast.error("Failed to load time entries");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { load(); }, [filterProject, filterInvoiced]);

  async function logTime() {
    if (!form.project_id || !form.hours || !form.hourly_rate) { toast.error("Fill in project, hours and rate"); return; }
    try {
      const created = await api.post("/api/projects/time-entries", {
        project_id: form.project_id,
        operator_name: form.operator_name || undefined,
        entry_date: form.entry_date,
        description: form.description || undefined,
        hours: parseFloat(form.hours),
        hourly_rate: parseFloat(form.hourly_rate),
        billable: form.billable,
      });
      setEntries((e) => [{ ...created, project_name: projects.find((p) => p.id === form.project_id)?.name ?? null }, ...e]);
      setShowForm(false);
      toast.success("Time logged");
    } catch { toast.error("Failed to log time"); }
  }

  async function deleteEntry(id: string) {
    try {
      await api.delete(`/api/projects/time-entries/${id}`);
      setEntries((e) => e.filter((x) => x.id !== id));
      setSelected((s) => { const n = new Set(s); n.delete(id); return n; });
      toast.success("Deleted");
    } catch (err: any) {
      toast.error(err?.detail ?? "Cannot delete invoiced entry");
    }
  }

  async function generateInvoice() {
    if (!invoiceForm.customer_id) { toast.error("Select customer"); return; }
    setGenerating(true);
    try {
      const result = await api.post("/api/projects/time-entries/generate-invoice", {
        entry_ids: Array.from(selected),
        customer_id: invoiceForm.customer_id,
        tax_rate: parseFloat(invoiceForm.tax_rate),
      });
      toast.success(`Invoice ${result.invoice_number} created — ${result.entry_count} entries, ${result.total_sek.toLocaleString()} SEK`);
      setInvoiceModal(false);
      setSelected(new Set());
      load();
    } catch (err: any) {
      toast.error(err?.detail?.message ?? "Failed to generate invoice");
    } finally {
      setGenerating(false);
    }
  }

  const toggleSelect = (id: string) => setSelected((s) => {
    const n = new Set(s);
    n.has(id) ? n.delete(id) : n.add(id);
    return n;
  });

  const selectedBillableUnInvoiced = entries.filter((e) => selected.has(e.id) && e.billable && !e.invoiced);
  const totalHours = entries.reduce((s, e) => s + e.hours, 0);
  const totalValue = entries.reduce((s, e) => s + e.hours * e.hourly_rate, 0);

  if (planBlocked) return <PlanGateBlock module={planBlocked.module} currentPlan={planBlocked.currentPlan} featureName="Time Entries" />;

  return (
    <div className="p-6 max-w-7xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-2">
          <Clock className="w-6 h-6" />
          <h1 className="text-2xl font-semibold">Time Entries</h1>
        </div>
        <div className="flex gap-2">
          {selected.size > 0 && (
            <button onClick={() => setInvoiceModal(true)} className="flex items-center gap-1.5 bg-green-600 text-white rounded px-3 py-1.5 text-sm">
              <FileText className="w-4 h-4" /> Generate Invoice ({selectedBillableUnInvoiced.length})
            </button>
          )}
          <button onClick={() => setShowForm((x) => !x)} className="flex items-center gap-1.5 bg-primary text-primary-foreground rounded px-3 py-1.5 text-sm">
            <Plus className="w-4 h-4" /> Log Time
          </button>
        </div>
      </div>

      {showForm && (
        <div className="border rounded-lg p-4 mb-6 grid grid-cols-3 gap-3 max-w-2xl">
          <div>
            <label className="text-xs font-medium text-muted-foreground">Project</label>
            <select className="border rounded px-2 py-1.5 text-sm w-full mt-1" value={form.project_id} onChange={(e) => {
              const p = projects.find((x) => x.id === e.target.value);
              setForm((f) => ({ ...f, project_id: e.target.value, hourly_rate: p?.default_hourly_rate?.toString() ?? f.hourly_rate }));
            }}>
              <option value="">— select —</option>
              {projects.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
            </select>
          </div>
          <div>
            <label className="text-xs font-medium text-muted-foreground">Person</label>
            <input className="border rounded px-2 py-1.5 text-sm w-full mt-1" placeholder="Name" value={form.operator_name} onChange={(e) => setForm((f) => ({ ...f, operator_name: e.target.value }))} />
          </div>
          <div>
            <label className="text-xs font-medium text-muted-foreground">Date</label>
            <input type="date" className="border rounded px-2 py-1.5 text-sm w-full mt-1" value={form.entry_date} onChange={(e) => setForm((f) => ({ ...f, entry_date: e.target.value }))} />
          </div>
          <div className="col-span-3">
            <label className="text-xs font-medium text-muted-foreground">Description</label>
            <input className="border rounded px-2 py-1.5 text-sm w-full mt-1" value={form.description} onChange={(e) => setForm((f) => ({ ...f, description: e.target.value }))} />
          </div>
          <div>
            <label className="text-xs font-medium text-muted-foreground">Hours</label>
            <input type="number" step="0.25" min="0.25" className="border rounded px-2 py-1.5 text-sm w-full mt-1" value={form.hours} onChange={(e) => setForm((f) => ({ ...f, hours: e.target.value }))} />
          </div>
          <div>
            <label className="text-xs font-medium text-muted-foreground">Hourly Rate (SEK)</label>
            <input type="number" step="50" className="border rounded px-2 py-1.5 text-sm w-full mt-1" value={form.hourly_rate} onChange={(e) => setForm((f) => ({ ...f, hourly_rate: e.target.value }))} />
          </div>
          <div className="flex items-end pb-1">
            <label className="flex items-center gap-2 text-sm cursor-pointer">
              <input type="checkbox" checked={form.billable} onChange={(e) => setForm((f) => ({ ...f, billable: e.target.checked }))} />
              Billable
            </label>
          </div>
          <div className="col-span-3 flex gap-2">
            <button onClick={logTime} className="bg-primary text-primary-foreground rounded px-3 py-1.5 text-sm">Log</button>
            <button onClick={() => setShowForm(false)} className="border rounded px-3 py-1.5 text-sm">Cancel</button>
          </div>
        </div>
      )}

      {invoiceModal && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50">
          <div className="bg-background rounded-lg p-6 max-w-sm w-full shadow-lg">
            <h3 className="font-semibold mb-1">Generate Invoice</h3>
            <p className="text-xs text-muted-foreground mb-4">{selectedBillableUnInvoiced.length} uninvoiced billable entries selected</p>
            <div className="space-y-3">
              <div>
                <label className="text-xs font-medium text-muted-foreground">Bill to Customer</label>
                <select className="border rounded px-2 py-1.5 text-sm w-full mt-1" value={invoiceForm.customer_id} onChange={(e) => setInvoiceForm((f) => ({ ...f, customer_id: e.target.value }))}>
                  <option value="">— select —</option>
                  {customers.map((c) => <option key={c.id} value={c.id}>{c.company_name}</option>)}
                </select>
              </div>
              <div>
                <label className="text-xs font-medium text-muted-foreground">VAT %</label>
                <input type="number" step="1" className="border rounded px-2 py-1.5 text-sm w-full mt-1" value={invoiceForm.tax_rate} onChange={(e) => setInvoiceForm((f) => ({ ...f, tax_rate: e.target.value }))} />
              </div>
            </div>
            <div className="flex gap-2 justify-end mt-4">
              <button onClick={() => setInvoiceModal(false)} className="border rounded px-3 py-1.5 text-sm">Cancel</button>
              <button onClick={generateInvoice} disabled={generating} className="bg-green-600 text-white rounded px-3 py-1.5 text-sm disabled:opacity-50 flex items-center gap-2">
                {generating && <Loader2 className="w-3 h-3 animate-spin" />} Create Invoice
              </button>
            </div>
          </div>
        </div>
      )}

      <div className="flex gap-3 mb-4 flex-wrap">
        <select className="border rounded px-2 py-1.5 text-sm" value={filterProject} onChange={(e) => setFilterProject(e.target.value)}>
          <option value="">All projects</option>
          {projects.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
        </select>
        <select className="border rounded px-2 py-1.5 text-sm" value={filterInvoiced} onChange={(e) => setFilterInvoiced(e.target.value as "" | "true" | "false")}>
          <option value="">All</option>
          <option value="false">Uninvoiced</option>
          <option value="true">Invoiced</option>
        </select>
        <div className="ml-auto flex items-center gap-4 text-sm text-muted-foreground">
          <span>{totalHours.toFixed(1)} h total</span>
          <span>{totalValue.toLocaleString()} SEK</span>
        </div>
      </div>

      {loading ? (
        <div className="flex items-center justify-center h-40"><Loader2 className="w-6 h-6 animate-spin" /></div>
      ) : entries.length === 0 ? (
        <p className="text-sm text-muted-foreground">No entries found.</p>
      ) : (
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b text-left text-muted-foreground">
              <th className="py-2 pr-3 w-8"><input type="checkbox" onChange={(e) => {
                if (e.target.checked) setSelected(new Set(entries.filter((x) => !x.invoiced && x.billable).map((x) => x.id)));
                else setSelected(new Set());
              }} /></th>
              <th className="py-2 pr-4 font-medium">Date</th>
              <th className="py-2 pr-4 font-medium">Project</th>
              <th className="py-2 pr-4 font-medium">Person</th>
              <th className="py-2 pr-4 font-medium">Description</th>
              <th className="py-2 pr-4 font-medium text-right">Hrs</th>
              <th className="py-2 pr-4 font-medium text-right">Rate</th>
              <th className="py-2 pr-4 font-medium text-right">Amount</th>
              <th className="py-2 pr-4 font-medium">Status</th>
              <th />
            </tr>
          </thead>
          <tbody className="divide-y">
            {entries.map((e) => (
              <tr key={e.id} className={selected.has(e.id) ? "bg-accent/50" : ""}>
                <td className="py-2 pr-3">
                  {!e.invoiced && e.billable && (
                    <input type="checkbox" checked={selected.has(e.id)} onChange={() => toggleSelect(e.id)} />
                  )}
                </td>
                <td className="py-2 pr-4 text-muted-foreground">{e.entry_date}</td>
                <td className="py-2 pr-4 font-medium">{e.project_name ?? e.project_id.slice(0, 8)}</td>
                <td className="py-2 pr-4">{e.operator_name ?? "—"}</td>
                <td className="py-2 pr-4 text-muted-foreground max-w-[200px] truncate">{e.description ?? "—"}</td>
                <td className="py-2 pr-4 text-right font-medium">{e.hours.toFixed(2)}</td>
                <td className="py-2 pr-4 text-right">{e.hourly_rate.toLocaleString()}</td>
                <td className="py-2 pr-4 text-right font-medium">{(e.hours * e.hourly_rate).toLocaleString()}</td>
                <td className="py-2 pr-4">
                  {e.invoiced ? (
                    <span className="text-xs bg-blue-100 text-blue-800 px-1.5 py-0.5 rounded-full">Invoiced</span>
                  ) : e.billable ? (
                    <span className="text-xs bg-green-100 text-green-800 px-1.5 py-0.5 rounded-full">Billable</span>
                  ) : (
                    <span className="text-xs bg-gray-100 text-gray-600 px-1.5 py-0.5 rounded-full">Non-bill</span>
                  )}
                </td>
                <td className="py-2">
                  {!e.invoiced && (
                    <button onClick={() => deleteEntry(e.id)} className="text-muted-foreground hover:text-destructive">
                      <Trash2 className="w-3.5 h-3.5" />
                    </button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
