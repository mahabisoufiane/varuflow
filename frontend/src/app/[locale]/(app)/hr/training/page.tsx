"use client";

import { useState, useEffect } from "react";
import { toast } from "sonner";
import { GraduationCap, Plus, AlertTriangle, Check, X, Filter, Award, Clock } from "lucide-react";

interface Staff { id: string; name: string }
interface TrainingRecord {
  id: string; staff_id: string; training_name: string; provider: string | null;
  category: string; status: string; is_required: boolean;
  completed_at: string | null; expiry_date: string | null;
  required_by_date: string | null; certificate_url: string | null;
  notes: string | null; is_expired: boolean; expiring_soon: boolean; is_overdue: boolean;
}
interface Alert {
  id: string; staff_id: string; staff_name: string; training_name: string;
  category: string; status: string; is_required: boolean;
  expiry_date: string | null; required_by_date: string | null; alert_type: string;
}
interface StaffSummary { staff_id: string; staff_name: string; total: number; completed: number; required_incomplete: number; expired: number; completion_pct: number }

const STATUS_COLORS: Record<string, string> = {
  not_started: "bg-gray-100 text-gray-600",
  in_progress: "bg-blue-100 text-blue-700",
  completed: "bg-green-100 text-green-700",
  expired: "bg-red-100 text-red-700",
};

const CAT_COLORS: Record<string, string> = {
  safety: "bg-red-50 text-red-700", compliance: "bg-orange-50 text-orange-700",
  technical: "bg-blue-50 text-blue-700", soft_skills: "bg-purple-50 text-purple-700",
  product: "bg-teal-50 text-teal-700", language: "bg-green-50 text-green-700",
  other: "bg-gray-100 text-gray-600",
};

const CATEGORIES = ["safety", "compliance", "technical", "soft_skills", "product", "language", "other"];
const STATUSES = ["not_started", "in_progress", "completed", "expired"];

export default function TrainingPage() {
  const apiBase = process.env.NEXT_PUBLIC_API_URL!;
  const f = (url: string, init?: RequestInit) => fetch(`${apiBase}${url}`, { credentials: "include", ...init });

  const [staff, setStaff] = useState<Staff[]>([]);
  const [records, setRecords] = useState<TrainingRecord[]>([]);
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [summaries, setSummaries] = useState<StaffSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [tab, setTab] = useState<"records" | "alerts" | "summary" | "requirements" | "requests">("records");
  const [filterStaff, setFilterStaff] = useState("");
  const [filterCat, setFilterCat] = useState("");
  const [filterStatus, setFilterStatus] = useState("");
  const [requirements, setRequirements] = useState<any[]>([]);
  const [trainingRequests, setTrainingRequests] = useState<any[]>([]);
  const [newReq, setNewReq] = useState({ job_role: "", training_name: "", category: "other", description: "" });
  const [newTrReq, setNewTrReq] = useState({ staff_id: "", training_name: "", provider: "", estimated_cost: "", justification: "" });
  const [showForm, setShowForm] = useState(false);
  const [newRec, setNewRec] = useState({
    staff_id: "", training_name: "", provider: "",
    category: "other", status: "not_started", is_required: false,
    completed_at: "", expiry_date: "", required_by_date: "", notes: "",
  });

  async function load() {
    const params = new URLSearchParams();
    if (filterStaff) params.set("staff_id", filterStaff);
    if (filterCat) params.set("category", filterCat);
    if (filterStatus) params.set("status", filterStatus);
    const [recs, als, sums, emps, reqs, treqs] = await Promise.all([
      f(`/api/hr/training${params.toString() ? "?" + params : ""}`).then(r => r.ok ? r.json() : []),
      f("/api/hr/training/alerts").then(r => r.ok ? r.json() : []),
      f("/api/hr/training/summary").then(r => r.ok ? r.json() : []),
      f("/api/hr/employees").then(r => r.ok ? r.json() : []),
      f("/api/hr/training/requirements").then(r => r.ok ? r.json() : []),
      f("/api/hr/training/requests").then(r => r.ok ? r.json() : []),
    ]);
    setRecords(recs); setAlerts(als); setSummaries(sums); setStaff(emps);
    setRequirements(reqs); setTrainingRequests(treqs);
    setLoading(false);
  }

  useEffect(() => { load(); }, [filterStaff, filterCat, filterStatus]);

  async function createRecord() {
    if (!newRec.staff_id || !newRec.training_name) { toast.error("Staff and training name required"); return; }
    const body = {
      ...newRec,
      provider: newRec.provider || null,
      completed_at: newRec.completed_at || null,
      expiry_date: newRec.expiry_date || null,
      required_by_date: newRec.required_by_date || null,
      notes: newRec.notes || null,
    };
    const res = await f("/api/hr/training", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    if (!res.ok) { toast.error("Failed to create"); return; }
    toast.success("Training record added");
    setShowForm(false);
    setNewRec({ staff_id: "", training_name: "", provider: "", category: "other", status: "not_started", is_required: false, completed_at: "", expiry_date: "", required_by_date: "", notes: "" });
    load();
  }

  async function updateStatus(id: string, status: string) {
    const res = await f(`/api/hr/training/${id}`, {
      method: "PATCH", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ status }),
    });
    if (!res.ok) { toast.error("Failed"); return; }
    const updated = await res.json();
    setRecords(prev => prev.map(r => r.id === id ? updated : r));
    load();
    toast.success("Status updated");
  }

  async function deleteRecord(id: string) {
    await f(`/api/hr/training/${id}`, { method: "DELETE" });
    setRecords(prev => prev.filter(r => r.id !== id));
    load();
    toast.success("Record deleted");
  }

  const staffMap = Object.fromEntries(staff.map(s => [s.id, s.name]));

  if (loading) return <div className="animate-pulse space-y-4">{[1,2,3].map(i => <div key={i} className="h-16 rounded-xl bg-gray-100" />)}</div>;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <h1 className="text-2xl font-semibold text-gray-900">Training Records</h1>
          <p className="mt-1 text-sm text-gray-500">Log certifications, required training and track expiry dates per staff member.</p>
        </div>
        <button onClick={() => setShowForm(true)} className="btn-primary flex items-center gap-2">
          <Plus className="h-4 w-4" /> Add Record
        </button>
      </div>

      {/* Alert banner */}
      {alerts.length > 0 && (
        <div className="rounded-xl border border-amber-300 bg-amber-50 p-4 flex items-start gap-3">
          <AlertTriangle className="h-5 w-5 text-amber-600 flex-shrink-0 mt-0.5" />
          <div>
            <p className="font-semibold text-amber-800">{alerts.length} training alert{alerts.length > 1 ? "s" : ""}</p>
            <p className="text-sm text-amber-700">
              {alerts.filter(a => a.alert_type === "expired").length} expired,{" "}
              {alerts.filter(a => a.alert_type === "expiring_soon").length} expiring within 30 days,{" "}
              {alerts.filter(a => a.alert_type === "overdue").length} overdue
            </p>
          </div>
          <button onClick={() => setTab("alerts")} className="ml-auto text-sm font-medium text-amber-700 hover:underline flex-shrink-0">View →</button>
        </div>
      )}

      {/* Add form */}
      {showForm && (
        <div className="rounded-xl border border-blue-200 bg-blue-50 p-5 space-y-3">
          <p className="text-sm font-semibold text-blue-800">New Training Record</p>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div>
              <label className="text-xs font-medium text-gray-600 block mb-1">Staff member *</label>
              <select className="input" value={newRec.staff_id} onChange={e => setNewRec(p => ({ ...p, staff_id: e.target.value }))}>
                <option value="">Select…</option>
                {staff.map(s => <option key={s.id} value={s.id}>{s.name}</option>)}
              </select>
            </div>
            <div>
              <label className="text-xs font-medium text-gray-600 block mb-1">Training name *</label>
              <input className="input" placeholder="e.g. First Aid Certificate" value={newRec.training_name} onChange={e => setNewRec(p => ({ ...p, training_name: e.target.value }))} />
            </div>
            <div>
              <label className="text-xs font-medium text-gray-600 block mb-1">Provider</label>
              <input className="input" placeholder="Training provider" value={newRec.provider} onChange={e => setNewRec(p => ({ ...p, provider: e.target.value }))} />
            </div>
            <div>
              <label className="text-xs font-medium text-gray-600 block mb-1">Category</label>
              <select className="input" value={newRec.category} onChange={e => setNewRec(p => ({ ...p, category: e.target.value }))}>
                {CATEGORIES.map(c => <option key={c} value={c}>{c.replace("_", " ")}</option>)}
              </select>
            </div>
            <div>
              <label className="text-xs font-medium text-gray-600 block mb-1">Status</label>
              <select className="input" value={newRec.status} onChange={e => setNewRec(p => ({ ...p, status: e.target.value }))}>
                {STATUSES.map(s => <option key={s} value={s}>{s.replace("_", " ")}</option>)}
              </select>
            </div>
            <div>
              <label className="text-xs font-medium text-gray-600 block mb-1">Completed date</label>
              <input className="input" type="date" value={newRec.completed_at} onChange={e => setNewRec(p => ({ ...p, completed_at: e.target.value }))} />
            </div>
            <div>
              <label className="text-xs font-medium text-gray-600 block mb-1">Expiry date</label>
              <input className="input" type="date" value={newRec.expiry_date} onChange={e => setNewRec(p => ({ ...p, expiry_date: e.target.value }))} />
            </div>
            <div>
              <label className="text-xs font-medium text-gray-600 block mb-1">Required by</label>
              <input className="input" type="date" value={newRec.required_by_date} onChange={e => setNewRec(p => ({ ...p, required_by_date: e.target.value }))} />
            </div>
            <label className="flex items-center gap-2 cursor-pointer text-sm text-gray-700 col-span-full">
              <input type="checkbox" checked={newRec.is_required} onChange={e => setNewRec(p => ({ ...p, is_required: e.target.checked }))} className="rounded" />
              Mark as required training for this role
            </label>
          </div>
          <div className="flex gap-2">
            <button onClick={createRecord} className="btn-primary text-sm">Save Record</button>
            <button onClick={() => setShowForm(false)} className="btn-secondary text-sm">Cancel</button>
          </div>
        </div>
      )}

      {/* Tabs */}
      <div className="flex gap-2 border-b border-gray-200">
        {([
          { key: "records", label: `Records (${records.length})` },
          { key: "alerts",  label: `Alerts (${alerts.length})` },
          { key: "summary", label: "Staff Summary" },
          { key: "requirements", label: `Role Requirements` },
          { key: "requests", label: `Requests (${trainingRequests.filter((r: any) => r.status === "pending").length})` },
        ] as const).map(t => (
          <button key={t.key} onClick={() => setTab(t.key)}
            className={`px-4 py-2 text-sm font-medium border-b-2 -mb-px transition-all ${
              tab === t.key ? "border-blue-500 text-blue-600" : "border-transparent text-gray-500 hover:text-gray-700"
            }`}>{t.label}</button>
        ))}
      </div>

      {/* Records tab */}
      {tab === "records" && (
        <div className="space-y-4">
          {/* Filters */}
          <div className="flex gap-2 flex-wrap">
            <select className="input text-sm w-48" value={filterStaff} onChange={e => setFilterStaff(e.target.value)}>
              <option value="">All staff</option>
              {staff.map(s => <option key={s.id} value={s.id}>{s.name}</option>)}
            </select>
            <select className="input text-sm w-36" value={filterCat} onChange={e => setFilterCat(e.target.value)}>
              <option value="">All categories</option>
              {CATEGORIES.map(c => <option key={c} value={c}>{c.replace("_", " ")}</option>)}
            </select>
            <select className="input text-sm w-36" value={filterStatus} onChange={e => setFilterStatus(e.target.value)}>
              <option value="">All statuses</option>
              {STATUSES.map(s => <option key={s} value={s}>{s.replace("_", " ")}</option>)}
            </select>
          </div>

          {records.length === 0 && (
            <div className="text-center py-12 text-gray-400">
              <GraduationCap className="h-10 w-10 mx-auto mb-3 opacity-40" />
              <p>No training records yet. Add your first record above.</p>
            </div>
          )}

          <div className="space-y-2">
            {records.map(rec => (
              <div key={rec.id} className={`rounded-xl border bg-white p-4 flex items-center gap-4 ${
                rec.is_expired ? "border-red-200 bg-red-50/30" : rec.expiring_soon ? "border-amber-200" : "border-gray-200"
              }`}>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="font-semibold text-gray-900">{rec.training_name}</span>
                    {rec.is_required && <span className="text-xs bg-orange-100 text-orange-700 px-1.5 py-0.5 rounded">Required</span>}
                    <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${STATUS_COLORS[rec.status]}`}>{rec.status.replace("_", " ")}</span>
                    <span className={`text-xs px-2 py-0.5 rounded ${CAT_COLORS[rec.category] || CAT_COLORS.other}`}>{rec.category.replace("_", " ")}</span>
                    {rec.is_expired && <span className="text-xs bg-red-100 text-red-700 px-1.5 py-0.5 rounded flex items-center gap-1"><AlertTriangle className="h-3 w-3" />Expired</span>}
                    {rec.expiring_soon && !rec.is_expired && <span className="text-xs bg-amber-100 text-amber-700 px-1.5 py-0.5 rounded flex items-center gap-1"><Clock className="h-3 w-3" />Expiring soon</span>}
                  </div>
                  <div className="flex gap-3 mt-0.5 text-xs text-gray-500 flex-wrap">
                    <span>{staffMap[rec.staff_id] || rec.staff_id}</span>
                    {rec.provider && <span>· {rec.provider}</span>}
                    {rec.completed_at && <span>· Completed {rec.completed_at}</span>}
                    {rec.expiry_date && <span>· Expires {rec.expiry_date}</span>}
                  </div>
                </div>
                <div className="flex items-center gap-2 flex-shrink-0">
                  {rec.status !== "completed" && (
                    <button onClick={() => updateStatus(rec.id, "completed")}
                      className="text-xs px-2 py-1.5 rounded-lg bg-green-100 text-green-700 hover:bg-green-200">
                      Mark done
                    </button>
                  )}
                  {rec.certificate_url && (
                    <a href={rec.certificate_url} target="_blank" rel="noopener noreferrer"
                      className="text-xs px-2 py-1.5 rounded-lg bg-blue-100 text-blue-700 hover:bg-blue-200 flex items-center gap-1">
                      <Award className="h-3 w-3" /> Cert
                    </a>
                  )}
                  <button onClick={() => deleteRecord(rec.id)} className="p-1.5 rounded-lg hover:bg-red-50 text-gray-400 hover:text-red-500">
                    <X className="h-4 w-4" />
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Alerts tab */}
      {tab === "alerts" && (
        <div className="space-y-2">
          {alerts.length === 0 && (
            <div className="text-center py-12 text-green-600">
              <Check className="h-8 w-8 mx-auto mb-2" />
              <p>No training alerts. All certifications are up to date.</p>
            </div>
          )}
          {alerts.map(a => (
            <div key={a.id} className={`rounded-xl border p-4 flex items-center gap-4 ${
              a.alert_type === "expired" ? "border-red-200 bg-red-50" : a.alert_type === "expiring_soon" ? "border-amber-200 bg-amber-50" : "border-orange-200 bg-orange-50"
            }`}>
              <AlertTriangle className={`h-5 w-5 flex-shrink-0 ${a.alert_type === "expired" ? "text-red-500" : "text-amber-500"}`} />
              <div className="flex-1 min-w-0">
                <p className="font-semibold text-gray-900">{a.training_name}</p>
                <div className="flex gap-2 text-xs text-gray-600 mt-0.5 flex-wrap">
                  <span>{a.staff_name}</span>
                  {a.expiry_date && <span>· Expires {a.expiry_date}</span>}
                  {a.required_by_date && !a.expiry_date && <span>· Required by {a.required_by_date}</span>}
                </div>
              </div>
              <span className={`text-xs font-semibold flex-shrink-0 ${
                a.alert_type === "expired" ? "text-red-700" : a.alert_type === "expiring_soon" ? "text-amber-700" : "text-orange-700"
              }`}>
                {a.alert_type === "expired" ? "Expired" : a.alert_type === "expiring_soon" ? "Expiring soon" : "Overdue"}
              </span>
            </div>
          ))}
        </div>
      )}

      {/* Summary tab */}
      {tab === "summary" && (
        <div className="space-y-3">
          {summaries.length === 0 && <p className="text-center py-8 text-gray-400">No training records to summarise.</p>}
          {summaries.map(s => (
            <div key={s.staff_id} className="rounded-xl border border-gray-200 bg-white p-4">
              <div className="flex items-center justify-between mb-2">
                <p className="font-semibold text-gray-900">{s.staff_name}</p>
                <div className="flex gap-2 text-xs">
                  <span className="bg-green-100 text-green-700 px-2 py-0.5 rounded">{s.completed} completed</span>
                  {s.required_incomplete > 0 && <span className="bg-orange-100 text-orange-700 px-2 py-0.5 rounded">{s.required_incomplete} required incomplete</span>}
                  {s.expired > 0 && <span className="bg-red-100 text-red-700 px-2 py-0.5 rounded">{s.expired} expired</span>}
                </div>
              </div>
              <div className="flex items-center gap-2">
                <div className="flex-1 h-2.5 bg-gray-100 rounded-full overflow-hidden">
                  <div
                    className={`h-full rounded-full ${s.completion_pct === 100 ? "bg-green-500" : "bg-blue-500"}`}
                    style={{ width: `${s.completion_pct}%` }}
                  />
                </div>
                <span className="text-xs font-semibold text-gray-600 w-16 text-right">{s.completed}/{s.total} ({Math.round(s.completion_pct)}%)</span>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Requirements tab */}
      {tab === "requirements" && (
        <div className="space-y-4">
          <h3 className="text-sm font-semibold text-gray-900">Mandatory Training by Job Role</h3>
          {/* Add requirement form */}
          <div className="bg-gray-50 rounded-xl p-4 space-y-2">
            <div className="grid grid-cols-2 gap-2">
              <input className="border rounded-lg px-3 py-2 text-sm" placeholder="Job role (e.g. Food Handler)" value={newReq.job_role} onChange={e => setNewReq({ ...newReq, job_role: e.target.value })} />
              <input className="border rounded-lg px-3 py-2 text-sm" placeholder="Required training name" value={newReq.training_name} onChange={e => setNewReq({ ...newReq, training_name: e.target.value })} />
            </div>
            <div className="flex gap-2">
              <select className="border rounded-lg px-3 py-2 text-sm flex-1" value={newReq.category} onChange={e => setNewReq({ ...newReq, category: e.target.value })}>
                {CATEGORIES.map(c => <option key={c} value={c}>{c.replace("_", " ")}</option>)}
              </select>
              <input className="border rounded-lg px-3 py-2 text-sm flex-1" placeholder="Description (optional)" value={newReq.description} onChange={e => setNewReq({ ...newReq, description: e.target.value })} />
              <button onClick={async () => {
                if (!newReq.job_role || !newReq.training_name) { toast.error("Role and training name required"); return; }
                const res = await f("/api/hr/training/requirements", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(newReq) });
                if (res.ok) { toast.success("Requirement added"); setNewReq({ job_role: "", training_name: "", category: "other", description: "" }); load(); }
                else toast.error("Failed to add");
              }} className="px-4 py-2 bg-blue-600 text-white rounded-lg text-sm">Add</button>
            </div>
          </div>
          {/* Requirements list grouped by role */}
          {Object.entries(
            requirements.reduce((acc: Record<string, any[]>, r: any) => {
              (acc[r.job_role] = acc[r.job_role] || []).push(r);
              return acc;
            }, {})
          ).map(([role, reqs]) => (
            <div key={role} className="border rounded-xl p-4">
              <h4 className="font-semibold text-sm mb-2">{role}</h4>
              <div className="space-y-1">
                {(reqs as any[]).map((r: any) => (
                  <div key={r.id} className="flex items-center justify-between text-sm">
                    <span>{r.training_name}</span>
                    <div className="flex items-center gap-2">
                      <span className="text-xs text-gray-400">{r.category}</span>
                      <button onClick={async () => {
                        await f(`/api/hr/training/requirements/${r.id}`, { method: "DELETE" });
                        setRequirements(prev => prev.filter((x: any) => x.id !== r.id));
                      }} className="text-red-400 hover:text-red-600 text-xs">Remove</button>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          ))}
          {requirements.length === 0 && <p className="text-sm text-gray-500">No role requirements defined yet.</p>}
        </div>
      )}

      {/* Training Requests tab */}
      {tab === "requests" && (
        <div className="space-y-4">
          <h3 className="text-sm font-semibold text-gray-900">Training Requests</h3>
          {/* Submit request form */}
          <div className="bg-gray-50 rounded-xl p-4 space-y-2">
            <div className="grid grid-cols-2 gap-2">
              <select className="border rounded-lg px-3 py-2 text-sm" value={newTrReq.staff_id} onChange={e => setNewTrReq({ ...newTrReq, staff_id: e.target.value })}>
                <option value="">Select staff…</option>
                {staff.map((s: any) => <option key={s.id} value={s.id}>{s.name}</option>)}
              </select>
              <input className="border rounded-lg px-3 py-2 text-sm" placeholder="Training name" value={newTrReq.training_name} onChange={e => setNewTrReq({ ...newTrReq, training_name: e.target.value })} />
              <input className="border rounded-lg px-3 py-2 text-sm" placeholder="Provider" value={newTrReq.provider} onChange={e => setNewTrReq({ ...newTrReq, provider: e.target.value })} />
              <input type="number" className="border rounded-lg px-3 py-2 text-sm" placeholder="Est. cost (SEK)" value={newTrReq.estimated_cost} onChange={e => setNewTrReq({ ...newTrReq, estimated_cost: e.target.value })} />
              <input className="border rounded-lg px-3 py-2 text-sm col-span-2" placeholder="Justification" value={newTrReq.justification} onChange={e => setNewTrReq({ ...newTrReq, justification: e.target.value })} />
            </div>
            <button onClick={async () => {
              if (!newTrReq.staff_id || !newTrReq.training_name) { toast.error("Staff and training name required"); return; }
              const body = { ...newTrReq, estimated_cost: newTrReq.estimated_cost ? Number(newTrReq.estimated_cost) : null, provider: newTrReq.provider || null, justification: newTrReq.justification || null };
              const res = await f("/api/hr/training/requests", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
              if (res.ok) { toast.success("Request submitted"); setNewTrReq({ staff_id: "", training_name: "", provider: "", estimated_cost: "", justification: "" }); load(); }
              else toast.error("Failed to submit request");
            }} className="px-4 py-2 bg-blue-600 text-white rounded-lg text-sm">Submit Request</button>
          </div>
          {/* Requests list */}
          <div className="space-y-2">
            {trainingRequests.map((r: any) => (
              <div key={r.id} className="border rounded-xl p-3 flex items-center justify-between">
                <div>
                  <p className="font-medium text-sm">{r.training_name}</p>
                  <p className="text-xs text-gray-400">{r.staff_name} · {r.provider || "—"} · {r.estimated_cost ? `${r.estimated_cost} SEK` : "No cost est."}</p>
                  {r.justification && <p className="text-xs text-gray-500 mt-0.5">{r.justification}</p>}
                  {r.manager_notes && <p className="text-xs text-gray-400 italic mt-0.5">Manager: {r.manager_notes}</p>}
                </div>
                <div className="flex items-center gap-2 flex-shrink-0">
                  <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${
                    r.status === "approved" ? "bg-green-100 text-green-700" :
                    r.status === "rejected" ? "bg-red-100 text-red-700" :
                    r.status === "completed" ? "bg-blue-100 text-blue-700" :
                    "bg-yellow-100 text-yellow-700"
                  }`}>{r.status}</span>
                  {r.status === "pending" && (
                    <>
                      <button onClick={async () => {
                        const res = await f(`/api/hr/training/requests/${r.id}/approve`, { method: "POST", headers: { "Content-Type": "application/json" }, body: "{}" });
                        if (res.ok) { toast.success("Approved"); load(); } else toast.error("Failed");
                      }} className="text-xs text-green-600 hover:underline">Approve</button>
                      <button onClick={async () => {
                        const notes = prompt("Reason for rejection:");
                        if (notes === null) return;
                        const res = await f(`/api/hr/training/requests/${r.id}/reject`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ manager_notes: notes }) });
                        if (res.ok) { toast.success("Rejected"); load(); } else toast.error("Failed");
                      }} className="text-xs text-red-600 hover:underline">Reject</button>
                    </>
                  )}
                </div>
              </div>
            ))}
            {trainingRequests.length === 0 && <p className="text-sm text-gray-500">No training requests yet.</p>}
          </div>
        </div>
      )}
    </div>
  );
}
