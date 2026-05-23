"use client";

import { useEffect, useState } from "react";
import { Timer, Plus, Loader2, Trash2 } from "lucide-react";
import { toast } from "sonner";
import { api } from "@/lib/api-client";

interface TimeEntry {
  id: string;
  staff_id: string;
  entry_date: string;
  project: string;
  client: string | null;
  description: string | null;
  hours: string;
  billable: boolean;
  hourly_rate: string | null;
}

interface Summary {
  total_hours: number;
  billable_hours: number;
  by_project: Record<string, number>;
}

function getWeekRange(offset = 0) {
  const now = new Date();
  const day = now.getDay();
  const monday = new Date(now);
  monday.setDate(now.getDate() - ((day + 6) % 7) + offset * 7);
  const sunday = new Date(monday);
  sunday.setDate(monday.getDate() + 6);
  const fmt = (d: Date) => d.toISOString().split("T")[0];
  return { from: fmt(monday), to: fmt(sunday) };
}

export default function TimePage() {
  const [entries, setEntries] = useState<TimeEntry[]>([]);
  const [summary, setSummary] = useState<Summary | null>(null);
  const [loading, setLoading] = useState(true);
  const [weekOffset, setWeekOffset] = useState(0);
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState({ staff_id: "", entry_date: new Date().toISOString().split("T")[0], project: "", client: "", description: "", hours: "", billable: true });

  const { from, to } = getWeekRange(weekOffset);

  async function load() {
    setLoading(true);
    try {
      const [data, sum] = await Promise.all([
        api.get(`/api/hr/time-entries?from_date=${from}&to_date=${to}`),
        api.get(`/api/hr/time-entries/summary?from_date=${from}&to_date=${to}`),
      ]);
      setEntries(data);
      setSummary(sum);
    } catch {
      toast.error("Failed to load time entries");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { load(); }, [from, to]);

  async function create() {
    if (!form.project || !form.hours || !form.entry_date) {
      toast.error("Fill in required fields");
      return;
    }
    try {
      const created = await api.post("/api/hr/time-entries", { ...form, hours: parseFloat(form.hours) });
      setEntries((e) => [created, ...e]);
      setShowForm(false);
      setForm({ staff_id: "", entry_date: new Date().toISOString().split("T")[0], project: "", client: "", description: "", hours: "", billable: true });
      toast.success("Time logged");
      load();
    } catch {
      toast.error("Failed to log time");
    }
  }

  async function remove(id: string) {
    try {
      await api.delete(`/api/hr/time-entries/${id}`);
      setEntries((e) => e.filter((x) => x.id !== id));
      load();
      toast.success("Entry deleted");
    } catch {
      toast.error("Failed to delete");
    }
  }

  const topProject = summary
    ? Object.entries(summary.by_project).sort((a, b) => b[1] - a[1])[0]?.[0] ?? "—"
    : "—";

  return (
    <div className="p-6 max-w-6xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-2">
          <Timer className="w-6 h-6" />
          <h1 className="text-2xl font-semibold">Time Tracking</h1>
        </div>
        <button onClick={() => setShowForm((x) => !x)} className="flex items-center gap-1.5 bg-primary text-primary-foreground rounded px-3 py-1.5 text-sm">
          <Plus className="w-4 h-4" /> Log Time
        </button>
      </div>

      {/* Week nav */}
      <div className="flex items-center gap-3 mb-4">
        <button onClick={() => setWeekOffset((w) => w - 1)} className="border rounded px-2 py-1 text-sm hover:bg-accent">←</button>
        <span className="text-sm font-medium">{from} – {to}</span>
        <button onClick={() => setWeekOffset((w) => w + 1)} className="border rounded px-2 py-1 text-sm hover:bg-accent">→</button>
        {weekOffset !== 0 && <button onClick={() => setWeekOffset(0)} className="text-xs text-muted-foreground underline">This week</button>}
      </div>

      {/* KPI bar */}
      {summary && (
        <div className="grid grid-cols-3 gap-4 mb-6">
          <div className="border rounded p-3 text-center">
            <p className="text-xl font-bold">{summary.total_hours.toFixed(1)}</p>
            <p className="text-xs text-muted-foreground">Total Hours</p>
          </div>
          <div className="border rounded p-3 text-center">
            <p className="text-xl font-bold">{summary.billable_hours.toFixed(1)}</p>
            <p className="text-xs text-muted-foreground">Billable Hours</p>
          </div>
          <div className="border rounded p-3 text-center">
            <p className="text-xl font-bold truncate">{topProject}</p>
            <p className="text-xs text-muted-foreground">Top Project</p>
          </div>
        </div>
      )}

      {showForm && (
        <div className="border rounded p-4 mb-6 grid grid-cols-2 gap-3 max-w-lg">
          <div>
            <label className="text-xs font-medium text-muted-foreground">Date</label>
            <input type="date" className="border rounded px-2 py-1.5 text-sm w-full mt-1" value={form.entry_date} onChange={(e) => setForm((f) => ({ ...f, entry_date: e.target.value }))} />
          </div>
          <div>
            <label className="text-xs font-medium text-muted-foreground">Project *</label>
            <input className="border rounded px-2 py-1.5 text-sm w-full mt-1" value={form.project} onChange={(e) => setForm((f) => ({ ...f, project: e.target.value }))} />
          </div>
          <div>
            <label className="text-xs font-medium text-muted-foreground">Client</label>
            <input className="border rounded px-2 py-1.5 text-sm w-full mt-1" value={form.client} onChange={(e) => setForm((f) => ({ ...f, client: e.target.value }))} />
          </div>
          <div>
            <label className="text-xs font-medium text-muted-foreground">Hours *</label>
            <input type="number" step="0.25" min="0.25" className="border rounded px-2 py-1.5 text-sm w-full mt-1" value={form.hours} onChange={(e) => setForm((f) => ({ ...f, hours: e.target.value }))} />
          </div>
          <div className="col-span-2">
            <label className="text-xs font-medium text-muted-foreground">Description</label>
            <input className="border rounded px-2 py-1.5 text-sm w-full mt-1" value={form.description} onChange={(e) => setForm((f) => ({ ...f, description: e.target.value }))} />
          </div>
          <div className="col-span-2 flex items-center gap-2">
            <input type="checkbox" id="billable" checked={form.billable} onChange={(e) => setForm((f) => ({ ...f, billable: e.target.checked }))} />
            <label htmlFor="billable" className="text-sm">Billable</label>
          </div>
          <div className="col-span-2 flex gap-2">
            <button onClick={create} className="bg-primary text-primary-foreground rounded px-3 py-1.5 text-sm">Log</button>
            <button onClick={() => setShowForm(false)} className="border rounded px-3 py-1.5 text-sm">Cancel</button>
          </div>
        </div>
      )}

      {loading ? (
        <div className="flex items-center justify-center h-40">
          <Loader2 className="w-6 h-6 animate-spin" />
        </div>
      ) : entries.length === 0 ? (
        <p className="text-sm text-muted-foreground">No entries this week.</p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b text-left text-muted-foreground">
                <th className="py-2 pr-4 font-medium">Date</th>
                <th className="py-2 pr-4 font-medium">Project</th>
                <th className="py-2 pr-4 font-medium">Client</th>
                <th className="py-2 pr-4 font-medium">Description</th>
                <th className="py-2 pr-4 font-medium">Hours</th>
                <th className="py-2 pr-4 font-medium">Billable</th>
                <th className="py-2 font-medium"></th>
              </tr>
            </thead>
            <tbody className="divide-y">
              {entries.map((e) => (
                <tr key={e.id}>
                  <td className="py-2 pr-4">{e.entry_date}</td>
                  <td className="py-2 pr-4 font-medium">{e.project}</td>
                  <td className="py-2 pr-4 text-muted-foreground">{e.client ?? "—"}</td>
                  <td className="py-2 pr-4 text-muted-foreground max-w-xs truncate">{e.description ?? "—"}</td>
                  <td className="py-2 pr-4 font-medium">{parseFloat(e.hours).toFixed(2)}</td>
                  <td className="py-2 pr-4">
                    <span className={`text-xs px-2 py-0.5 rounded-full ${e.billable ? "bg-blue-100 text-blue-800" : "bg-gray-100 text-gray-600"}`}>{e.billable ? "Yes" : "No"}</span>
                  </td>
                  <td className="py-2">
                    <button onClick={() => remove(e.id)} className="text-destructive hover:opacity-70">
                      <Trash2 className="w-4 h-4" />
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
