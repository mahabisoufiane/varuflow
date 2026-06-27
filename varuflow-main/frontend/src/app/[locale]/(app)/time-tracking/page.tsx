"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api-client";
import { Clock, Plus, Timer, StopCircle, CheckCircle, AlertCircle, BarChart2 } from "lucide-react";
import styles from "./page.module.scss";

interface TimeEntry {
  id: string;
  project_id: string;
  project_name?: string | null;
  operator_name: string | null;
  entry_date: string;
  description: string | null;
  hours: number;
  hourly_rate: number;
  billable: boolean;
  invoiced: boolean;
  invoice_id: string | null;
  approval_status: string;
  created_at: string;
}

interface Project {
  id: string;
  name: string;
  customer_name?: string | null;
  default_hourly_rate: number | null;
  status: string;
}

const APPROVAL_BADGE: Record<string, string> = {
  pending: "bg-yellow-100 text-yellow-700",
  approved: "bg-green-100 text-green-700",
  rejected: "bg-red-100 text-red-700",
};

const APPROVAL_MODULE: Record<string, keyof typeof styles> = {
  pending:  "approvalPending",
  approved: "approvalApproved",
  rejected: "approvalRejected",
};

function today() {
  return new Date().toISOString().slice(0, 10);
}

function fmtHours(h: number) {
  const hh = Math.floor(h);
  const mm = Math.round((h - hh) * 60);
  return `${hh}h ${mm > 0 ? `${mm}m` : ""}`.trim();
}

export default function TimeTrackingPage() {
  const router = useRouter();
  const [entries, setEntries] = useState<TimeEntry[]>([]);
  const [projects, setProjects] = useState<Project[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [tab, setTab] = useState<"mine" | "pending" | "all">("mine");
  const [role, setRole] = useState<string>("MEMBER");

  // Timer
  const [timerRunning, setTimerRunning] = useState(false);
  const [timerStart, setTimerStart] = useState<number | null>(null);
  const [timerSeconds, setTimerSeconds] = useState(0);
  const [timerProject, setTimerProject] = useState("");

  // Create form
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState({
    project_id: "", operator_name: "", entry_date: today(),
    description: "", hours: "", hourly_rate: "", billable: true,
  });
  const [saving, setSaving] = useState(false);

  // Invoice generator
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [invoiceCustomer, setInvoiceCustomer] = useState("");

  async function load() {
    setLoading(true);
    try {
      const [entriesData, projData] = await Promise.all([
        api.get("/api/projects/time-entries"),
        api.get("/api/projects"),
      ]);
      setEntries(Array.isArray(entriesData) ? entriesData : []);
      setProjects(Array.isArray(projData) ? projData : []);
    } catch (e: any) {
      if (e?.status === 401) { router.push("/auth/login"); return; }
      setError("Failed to load time entries");
    } finally {
      setLoading(false);
    }
  }

  async function loadPending() {
    try {
      const data = await api.get("/api/projects/time-entries/pending-approval");
      setEntries(Array.isArray(data) ? data : []);
    } catch (e: any) {
      if (e?.status === 403) { setError("Manager access required for approval queue"); }
    }
  }

  useEffect(() => {
    if (tab === "pending") loadPending();
    else load();
  }, [tab]);

  // Timer tick
  useEffect(() => {
    if (!timerRunning) return;
    const interval = setInterval(() => {
      setTimerSeconds(s => s + 1);
    }, 1000);
    return () => clearInterval(interval);
  }, [timerRunning]);

  function startTimer() {
    if (!timerProject) { alert("Select a project first"); return; }
    setTimerStart(Date.now());
    setTimerSeconds(0);
    setTimerRunning(true);
  }

  async function stopTimer() {
    if (!timerStart) return;
    setTimerRunning(false);
    const elapsed = timerSeconds / 3600;
    const proj = projects.find(p => p.id === timerProject);
    const rate = proj?.default_hourly_rate ?? 0;
    setForm(f => ({
      ...f,
      project_id: timerProject,
      hours: elapsed.toFixed(2),
      hourly_rate: String(rate),
      entry_date: today(),
    }));
    setShowForm(true);
    setTimerStart(null);
    setTimerSeconds(0);
  }

  async function create() {
    if (!form.project_id || !form.hours) { alert("Project and hours required"); return; }
    setSaving(true);
    try {
      const data = await api.post("/api/projects/time-entries", {
        project_id: form.project_id,
        operator_name: form.operator_name || null,
        entry_date: form.entry_date,
        description: form.description || null,
        hours: parseFloat(form.hours),
        hourly_rate: parseFloat(form.hourly_rate) || 0,
        billable: form.billable,
      });
      setEntries(prev => [{ ...data, project_name: projects.find(p => p.id === form.project_id)?.name }, ...prev]);
      setShowForm(false);
      setForm({ project_id: "", operator_name: "", entry_date: today(), description: "", hours: "", hourly_rate: "", billable: true });
    } catch (e: any) {
      alert(e?.data?.detail ?? "Failed to save time entry");
    } finally {
      setSaving(false);
    }
  }

  async function approve(id: string) {
    try {
      await api.post(`/api/projects/time-entries/${id}/approve`, {});
      setEntries(prev => prev.filter(e => e.id !== id));
    } catch { alert("Failed to approve"); }
  }

  async function reject(id: string) {
    try {
      await api.post(`/api/projects/time-entries/${id}/reject`, {});
      setEntries(prev => prev.filter(e => e.id !== id));
    } catch { alert("Failed to reject"); }
  }

  async function deleteEntry(id: string) {
    if (!confirm("Delete this time entry?")) return;
    try {
      await api.delete(`/api/projects/time-entries/${id}`);
      setEntries(prev => prev.filter(e => e.id !== id));
    } catch (e: any) { alert(e?.data?.detail ?? "Failed to delete"); }
  }

  async function generateInvoice() {
    if (selected.size === 0 || !invoiceCustomer) { alert("Select entries and a customer"); return; }
    try {
      const data = await api.post("/api/projects/time-entries/generate-invoice", {
        entry_ids: [...selected], customer_id: invoiceCustomer, tax_rate: 25,
      });
      alert(`Invoice created: ${data.invoice_number} — ${data.total_sek?.toLocaleString()} SEK`);
      setSelected(new Set());
      setInvoiceCustomer("");
      load();
    } catch (e: any) { alert(e?.data?.detail ?? "Failed to generate invoice"); }
  }

  function toggleSelect(id: string) {
    setSelected(prev => {
      const next = new Set(prev);
      next.has(id) ? next.delete(id) : next.add(id);
      return next;
    });
  }

  // Stats
  const totalHours = entries.reduce((s, e) => s + e.hours, 0);
  const billableHours = entries.reduce((s, e) => s + (e.billable ? e.hours : 0), 0);
  const billableValue = entries.reduce((s, e) => s + (e.billable ? e.hours * e.hourly_rate : 0), 0);
  const uninvoiced = entries.filter(e => e.billable && !e.invoiced);

  const timerDisplay = `${String(Math.floor(timerSeconds / 3600)).padStart(2, "0")}:${String(Math.floor((timerSeconds % 3600) / 60)).padStart(2, "0")}:${String(timerSeconds % 60).padStart(2, "0")}`;

  if (loading) return <div className="p-8 text-center text-gray-400">Loading…</div>;

  return (
    <div className="p-6 max-w-5xl mx-auto space-y-6">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Clock className="w-5 h-5 text-indigo-600" />
          <h1 className="text-xl font-bold text-gray-900">Time Tracking</h1>
        </div>
        <button onClick={() => setShowForm(v => !v)} className="btn-primary flex items-center gap-1 text-sm">
          <Plus className="w-4 h-4" /> Log Time
        </button>
      </div>

      {error && <div className="text-red-600 text-sm flex gap-2"><AlertCircle className="w-4 h-4 mt-0.5" />{error}</div>}

      {/* Timer widget */}
      <div className="rounded-xl border bg-white shadow-sm p-4 flex items-center gap-4 flex-wrap">
        <Timer className={`w-5 h-5 ${timerRunning ? "text-green-500 animate-pulse" : "text-gray-400"}`} />
        <div className="font-mono text-2xl font-bold text-gray-800 w-28">{timerDisplay}</div>
        <select
          className="input text-sm"
          value={timerProject}
          onChange={e => setTimerProject(e.target.value)}
          disabled={timerRunning}
        >
          <option value="">Select project…</option>
          {projects.filter(p => p.status === "active").map(p => (
            <option key={p.id} value={p.id}>{p.name}</option>
          ))}
        </select>
        {timerRunning ? (
          <button onClick={stopTimer} className="flex items-center gap-1 px-3 py-1.5 rounded bg-red-600 text-white text-sm hover:bg-red-700">
            <StopCircle className="w-4 h-4" /> Stop & Log
          </button>
        ) : (
          <button onClick={startTimer} className="flex items-center gap-1 px-3 py-1.5 rounded bg-green-600 text-white text-sm hover:bg-green-700">
            <Timer className="w-4 h-4" /> Start Timer
          </button>
        )}
      </div>

      {/* Stats */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        {[
          { label: "Total hours", value: fmtHours(totalHours), icon: Clock },
          { label: "Billable hours", value: fmtHours(billableHours), icon: BarChart2 },
          { label: "Billable value", value: `${billableValue.toLocaleString()} SEK`, icon: CheckCircle },
          { label: "Unbilled entries", value: uninvoiced.length, icon: AlertCircle },
        ].map(stat => (
          <div key={stat.label} className="rounded-xl border bg-white p-3 shadow-sm flex items-center gap-3">
            <stat.icon className="w-4 h-4 text-indigo-500 shrink-0" />
            <div>
              <p className="text-lg font-bold text-gray-900">{stat.value}</p>
              <p className="text-xs text-gray-500">{stat.label}</p>
            </div>
          </div>
        ))}
      </div>

      {/* Create form */}
      {showForm && (
        <div className="rounded-xl border bg-white shadow-sm p-5 space-y-4">
          <h2 className="font-semibold text-gray-800">Log Time</h2>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="text-xs text-gray-500 mb-1 block">Project *</label>
              <select className="input w-full" value={form.project_id} onChange={e => {
                const proj = projects.find(p => p.id === e.target.value);
                setForm(f => ({ ...f, project_id: e.target.value, hourly_rate: proj?.default_hourly_rate ? String(proj.default_hourly_rate) : f.hourly_rate }));
              }}>
                <option value="">— Select project —</option>
                {projects.map(p => <option key={p.id} value={p.id}>{p.name}</option>)}
              </select>
            </div>
            <div>
              <label className="text-xs text-gray-500 mb-1 block">Date *</label>
              <input type="date" className="input w-full" value={form.entry_date} onChange={e => setForm(f => ({ ...f, entry_date: e.target.value }))} />
            </div>
            <div>
              <label className="text-xs text-gray-500 mb-1 block">Hours *</label>
              <input type="number" step="0.25" className="input w-full" placeholder="0.00" value={form.hours} onChange={e => setForm(f => ({ ...f, hours: e.target.value }))} />
            </div>
            <div>
              <label className="text-xs text-gray-500 mb-1 block">Hourly rate</label>
              <input type="number" className="input w-full" placeholder="0.00" value={form.hourly_rate} onChange={e => setForm(f => ({ ...f, hourly_rate: e.target.value }))} />
            </div>
            <div className="col-span-2">
              <label className="text-xs text-gray-500 mb-1 block">Description</label>
              <input className="input w-full" placeholder="What did you work on?" value={form.description} onChange={e => setForm(f => ({ ...f, description: e.target.value }))} />
            </div>
            <div>
              <label className="text-xs text-gray-500 mb-1 block">Your name</label>
              <input className="input w-full" placeholder="Optional" value={form.operator_name} onChange={e => setForm(f => ({ ...f, operator_name: e.target.value }))} />
            </div>
            <div className="flex items-center gap-2 self-end pb-2">
              <input type="checkbox" id="billable" checked={form.billable} onChange={e => setForm(f => ({ ...f, billable: e.target.checked }))} />
              <label htmlFor="billable" className="text-sm cursor-pointer">Billable</label>
            </div>
          </div>
          <div className="flex gap-3">
            <button onClick={create} disabled={saving} className="btn-primary text-sm">{saving ? "Saving…" : "Save"}</button>
            <button onClick={() => setShowForm(false)} className="btn-secondary text-sm">Cancel</button>
          </div>
        </div>
      )}

      {/* Tabs */}
      <div className="flex gap-1 border-b">
        {(["mine", "pending", "all"] as const).map(t => (
          <button key={t} onClick={() => setTab(t)} className={`px-4 py-2 text-sm font-medium border-b-2 -mb-px transition-colors capitalize ${tab === t ? "border-indigo-600 text-indigo-700" : "border-transparent text-gray-500 hover:text-gray-700"}`}>
            {t === "pending" ? "Awaiting approval" : t === "mine" ? "My entries" : "All entries"}
          </button>
        ))}
      </div>

      {/* Invoice from selection */}
      {tab !== "pending" && selected.size > 0 && (
        <div className="rounded-lg bg-indigo-50 border border-indigo-200 p-3 flex items-center gap-3 flex-wrap">
          <span className="text-sm text-indigo-700 font-medium">{selected.size} entries selected</span>
          <input
            className="input text-sm flex-1 min-w-40"
            placeholder="Customer ID for invoice"
            value={invoiceCustomer}
            onChange={e => setInvoiceCustomer(e.target.value)}
          />
          <button onClick={generateInvoice} className="btn-primary text-sm">Generate Invoice</button>
          <button onClick={() => setSelected(new Set())} className="btn-secondary text-sm">Clear</button>
        </div>
      )}

      {/* Entries list */}
      {entries.length === 0 && (
        <div className="text-center py-12 text-gray-400">No time entries found.</div>
      )}

      <div className="space-y-2">
        {entries.map(entry => (
          <div
            key={entry.id}
            className={`rounded-xl border bg-white shadow-sm p-4 flex items-center gap-4 ${selected.has(entry.id) ? "ring-2 ring-indigo-400" : ""}`}
          >
            {tab !== "pending" && !entry.invoiced && entry.billable && (
              <input type="checkbox" checked={selected.has(entry.id)} onChange={() => toggleSelect(entry.id)} className="shrink-0" />
            )}
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2 flex-wrap">
                <span className="font-semibold text-sm text-gray-900">{entry.project_name ?? entry.project_id.slice(0, 8)}</span>
                <span className="text-xs text-gray-400">{entry.entry_date}</span>
                {entry.billable && <span className="text-xs px-1.5 py-0.5 rounded bg-green-50 text-green-700 border border-green-200">Billable</span>}
                {entry.invoiced && <span className="text-xs px-1.5 py-0.5 rounded bg-purple-50 text-purple-700 border border-purple-200">Invoiced</span>}
                <span className={styles[APPROVAL_MODULE[entry.approval_status] ?? "approvalPending"]}>{entry.approval_status}</span>
              </div>
              {entry.description && <p className="text-xs text-gray-500 mt-0.5 truncate">{entry.description}</p>}
              {entry.operator_name && <p className="text-xs text-gray-400">{entry.operator_name}</p>}
            </div>
            <div className="text-right shrink-0 space-y-0.5">
              <p className="font-bold text-gray-900">{fmtHours(entry.hours)}</p>
              {entry.hourly_rate > 0 && (
                <p className="text-xs text-gray-500">{(entry.hours * entry.hourly_rate).toLocaleString()} SEK</p>
              )}
            </div>
            {tab === "pending" ? (
              <div className="flex gap-2 shrink-0">
                <button onClick={() => approve(entry.id)} className="text-xs px-2 py-1 rounded bg-green-600 text-white hover:bg-green-700">Approve</button>
                <button onClick={() => reject(entry.id)} className="text-xs px-2 py-1 rounded bg-red-600 text-white hover:bg-red-700">Reject</button>
              </div>
            ) : !entry.invoiced && (
              <button onClick={() => deleteEntry(entry.id)} className="text-gray-300 hover:text-red-400 text-xl leading-none shrink-0">×</button>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
