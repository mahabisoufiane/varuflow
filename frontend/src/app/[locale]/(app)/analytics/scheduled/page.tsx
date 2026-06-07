"use client";

import { useState, useEffect } from "react";
import { toast } from "sonner";
import { Plus, Trash2, Mail, Check, X, Clock } from "lucide-react";
import { api } from "@/lib/api-client";
import styles from "./page.module.scss";

interface ScheduledReport {
  id: string; name: string; report_type: string; cron_expr: string; timezone: string;
  is_active: boolean; recipients: {email: string; name?: string}[];
  last_sent_at?: string; next_send_at?: string;
}

const REPORT_TYPES = [
  { value: "analytics_overview", label: "Analytics Overview" },
  { value: "pnl", label: "Profit & Loss" },
  { value: "cash_flow", label: "Cash Flow" },
] as const;

const CRON_PRESETS = [
  { label: "Every Monday 8am", value: "0 8 * * 1" },
  { label: "Every Friday 5pm", value: "0 17 * * 5" },
  { label: "1st of month 9am", value: "0 9 1 * *" },
  { label: "Daily 7am", value: "0 7 * * *" },
  { label: "Custom", value: "" },
];

function parseCron(expr: string): string {
  const preset = CRON_PRESETS.find(p => p.value === expr);
  return preset ? preset.label : expr;
}

export default function ScheduledReportsPage() {
  const [scheduled, setScheduled] = useState<ScheduledReport[]>([]);
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState({
    name: "", report_type: "analytics_overview", cron_expr: "0 8 * * 1",
    customCron: "", timezone: "Europe/Stockholm", recipientEmail: "", recipients: [] as {email: string; name?: string}[],
  });
  const [cronMode, setCronMode] = useState<"preset" | "custom">("preset");

  async function load() {
    try {
      const data = await api.get<{scheduled: ScheduledReport[]}>("/api/bi/scheduled");
      setScheduled(data.scheduled);
    } catch {}
  }
  useEffect(() => { load(); }, []);

  function addRecipient() {
    const email = form.recipientEmail.trim();
    if (!email || !email.includes("@")) { toast.error("Invalid email"); return; }
    if (form.recipients.find(r => r.email === email)) { toast.error("Already added"); return; }
    setForm(f => ({ ...f, recipients: [...f.recipients, { email }], recipientEmail: "" }));
  }

  async function create() {
    if (!form.name.trim()) { toast.error("Enter a name"); return; }
    if (form.recipients.length === 0) { toast.error("Add at least one recipient"); return; }
    const cron = cronMode === "custom" ? form.customCron : form.cron_expr;
    if (!cron) { toast.error("Set a schedule"); return; }
    try {
      await api.post("/api/bi/scheduled", {
        name: form.name, report_type: form.report_type,
        cron_expr: cron, timezone: form.timezone,
        recipients: form.recipients, config: {},
      });
      toast.success("Scheduled report created");
      setShowForm(false);
      setForm({ name: "", report_type: "analytics_overview", cron_expr: "0 8 * * 1", customCron: "", timezone: "Europe/Stockholm", recipientEmail: "", recipients: [] });
      await load();
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Failed");
    }
  }

  async function toggle(id: string, is_active: boolean) {
    await api.patch(`/api/bi/scheduled/${id}`, { is_active: !is_active });
    await load();
  }

  async function del(id: string) {
    try {
      await api.delete(`/api/bi/scheduled/${id}`);
    } catch {}
    setScheduled(s => s.filter(x => x.id !== id));
    toast.success("Deleted");
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-gray-900">Scheduled Reports</h1>
          <p className="mt-1 text-sm text-gray-500">Send weekly or monthly reports to stakeholders automatically.</p>
        </div>
        <button onClick={() => setShowForm(true)} className="btn-primary flex items-center gap-1.5">
          <Plus className="h-3.5 w-3.5" /> Schedule Report
        </button>
      </div>

      {showForm && (
        <div className="rounded-xl border border-blue-200 bg-blue-50 p-5 space-y-4">
          <p className="text-sm font-semibold text-blue-800">New Scheduled Report</p>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <input className="input col-span-2" placeholder="Report name (e.g. Weekly CEO Revenue)" value={form.name} onChange={e => setForm(f => ({ ...f, name: e.target.value }))} />
            <div>
              <label className="text-xs font-medium text-gray-700 mb-1 block">Report Type</label>
              <select className="input w-full" value={form.report_type} onChange={e => setForm(f => ({ ...f, report_type: e.target.value }))}>
                {REPORT_TYPES.map(t => <option key={t.value} value={t.value}>{t.label}</option>)}
              </select>
            </div>
            <div>
              <label className="text-xs font-medium text-gray-700 mb-1 block">Timezone</label>
              <select className="input w-full" value={form.timezone} onChange={e => setForm(f => ({ ...f, timezone: e.target.value }))}>
                {["Europe/Stockholm", "Europe/Oslo", "Europe/Copenhagen", "UTC", "America/New_York", "Asia/Dubai"].map(tz => (
                  <option key={tz} value={tz}>{tz}</option>
                ))}
              </select>
            </div>
          </div>

          {/* Schedule picker */}
          <div>
            <label className="text-xs font-medium text-gray-700 mb-1 block">Schedule</label>
            <div className="flex gap-2 items-center mb-2">
              <button onClick={() => setCronMode("preset")} className={`px-2.5 py-1 rounded text-xs font-medium ${cronMode === "preset" ? "bg-blue-500 text-white" : "bg-white text-gray-600 border border-gray-200"}`}>Preset</button>
              <button onClick={() => setCronMode("custom")} className={`px-2.5 py-1 rounded text-xs font-medium ${cronMode === "custom" ? "bg-blue-500 text-white" : "bg-white text-gray-600 border border-gray-200"}`}>Custom cron</button>
            </div>
            {cronMode === "preset" ? (
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
                {CRON_PRESETS.filter(p => p.value).map(p => (
                  <button key={p.value} onClick={() => setForm(f => ({ ...f, cron_expr: p.value }))}
                    className={`px-2.5 py-1.5 rounded-lg text-xs text-left border transition-all ${form.cron_expr === p.value ? "border-blue-500 bg-blue-50 text-blue-700" : "border-gray-200 bg-white text-gray-600 hover:border-gray-300"}`}>
                    {p.label}
                  </button>
                ))}
              </div>
            ) : (
              <input className="input font-mono" placeholder="0 8 * * 1 (cron expression)" value={form.customCron} onChange={e => setForm(f => ({ ...f, customCron: e.target.value }))} />
            )}
          </div>

          {/* Recipients */}
          <div>
            <label className="text-xs font-medium text-gray-700 mb-1 block">Recipients</label>
            <div className="flex gap-2">
              <input className="input flex-1" type="email" placeholder="ceo@company.com" value={form.recipientEmail} onChange={e => setForm(f => ({ ...f, recipientEmail: e.target.value }))}
                onKeyDown={e => { if (e.key === "Enter") addRecipient(); }} />
              <button onClick={addRecipient} className="btn-secondary">Add</button>
            </div>
            {form.recipients.length > 0 && (
              <div className="mt-2 flex flex-wrap gap-2">
                {form.recipients.map(r => (
                  <span key={r.email} className="flex items-center gap-1 bg-blue-100 text-blue-800 text-xs px-2 py-0.5 rounded-full">
                    {r.email}
                    <button onClick={() => setForm(f => ({ ...f, recipients: f.recipients.filter(x => x.email !== r.email) }))}><X className="h-3 w-3" /></button>
                  </span>
                ))}
              </div>
            )}
          </div>

          <div className="flex gap-2">
            <button onClick={create} className="btn-primary">Create Schedule</button>
            <button onClick={() => setShowForm(false)} className="btn-secondary">Cancel</button>
          </div>
        </div>
      )}

      {scheduled.length === 0 ? (
        <div className="rounded-xl border border-dashed border-gray-300 p-12 text-center text-sm text-gray-400">
          No scheduled reports. Click <strong>Schedule Report</strong> to get started.
        </div>
      ) : (
        <div className="space-y-3">
          {scheduled.map(s => (
            <div key={s.id} className={`rounded-xl border bg-white p-5 ${s.is_active ? "border-gray-200" : "border-gray-100 opacity-60"}`}>
              <div className="flex items-start justify-between gap-4">
                <div className="flex items-start gap-3">
                  <Mail className="h-5 w-5 text-blue-400 flex-shrink-0 mt-0.5" />
                  <div>
                    <p className="font-medium text-gray-900">{s.name}</p>
                    <p className="text-xs text-gray-500 mt-0.5">
                      {REPORT_TYPES.find(t => t.value === s.report_type)?.label} ·{" "}
                      <span className="font-mono">{parseCron(s.cron_expr)}</span> · {s.timezone}
                    </p>
                    <p className="text-xs text-gray-400 mt-0.5">
                      {s.recipients.map(r => r.email).join(", ")}
                    </p>
                  </div>
                </div>
                <div className="flex items-center gap-2 flex-shrink-0">
                  <span className={styles[s.is_active ? "statusActive" : "statusInactive"]}>
                    {s.is_active ? "Active" : "Paused"}
                  </span>
                  <button onClick={() => toggle(s.id, s.is_active)} className="btn-sm-outline" title={s.is_active ? "Pause" : "Resume"}>
                    {s.is_active ? <X className="h-3.5 w-3.5" /> : <Check className="h-3.5 w-3.5" />}
                  </button>
                  <button onClick={() => del(s.id)} className="btn-sm-danger-outline"><Trash2 className="h-3.5 w-3.5" /></button>
                </div>
              </div>
              {(s.last_sent_at || s.next_send_at) && (
                <div className="mt-3 flex gap-4 text-xs text-gray-400">
                  {s.last_sent_at && (
                    <span className="flex items-center gap-1"><Check className="h-3 w-3 text-green-500" /> Last sent: {new Date(s.last_sent_at).toLocaleString()}</span>
                  )}
                  {s.next_send_at && (
                    <span className="flex items-center gap-1"><Clock className="h-3 w-3 text-blue-400" /> Next: {new Date(s.next_send_at).toLocaleString()}</span>
                  )}
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
