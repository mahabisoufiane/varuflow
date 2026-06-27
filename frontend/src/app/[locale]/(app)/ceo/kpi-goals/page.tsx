"use client";

import { useState, useEffect } from "react";
import { toast } from "sonner";
import { Plus, Trash2, Target, CheckCircle2, AlertTriangle, TrendingUp } from "lucide-react";

const METRIC_KEYS = [
  { key: "revenue_total", label: "Total Revenue (invoiced)" },
  { key: "revenue_collected", label: "Revenue Collected" },
  { key: "new_customers", label: "New Customers Acquired" },
  { key: "gross_margin_pct", label: "Gross Margin %" },
  { key: "invoice_paid_rate", label: "Invoice Paid-on-Time Rate %" },
  { key: "outstanding_ar", label: "Outstanding AR (lower = better)" },
  { key: "expense_total", label: "Total Expenses (lower = better)" },
  { key: "invoices_sent", label: "Invoices Sent" },
];

const PERIODS = [
  { label: "Q1 2026", start: "2026-01-01", end: "2026-03-31" },
  { label: "Q2 2026", start: "2026-04-01", end: "2026-06-30" },
  { label: "Q3 2026", start: "2026-07-01", end: "2026-09-30" },
  { label: "Q4 2026", start: "2026-10-01", end: "2026-12-31" },
  { label: "FY 2026", start: "2026-01-01", end: "2026-12-31" },
  { label: "May 2026", start: "2026-05-01", end: "2026-05-31" },
  { label: "Custom", start: "", end: "" },
];

interface Goal {
  id: string; name: string; metric_key: string; metric_label: string;
  target_value: number; actual_value: number; progress_pct: number;
  period_label: string; period_start: string; period_end: string;
  currency: string; is_active: boolean; lower_is_better: boolean; on_track: boolean;
}

function ProgressRing({ pct, size = 80, onTrack }: { pct: number; size?: number; onTrack: boolean }) {
  const r = (size - 8) / 2;
  const circ = 2 * Math.PI * r;
  const dash = (pct / 100) * circ;
  const color = pct >= 100 ? "#10b981" : onTrack ? "#3b82f6" : pct >= 50 ? "#f59e0b" : "#ef4444";
  return (
    <svg width={size} height={size} className="-rotate-90">
      <circle cx={size/2} cy={size/2} r={r} fill="none" stroke="#e5e7eb" strokeWidth="6" />
      <circle cx={size/2} cy={size/2} r={r} fill="none" stroke={color} strokeWidth="6"
        strokeDasharray={`${dash} ${circ}`} strokeLinecap="round" />
      <text x={size/2} y={size/2} textAnchor="middle" dominantBaseline="central"
        fill={color} fontSize="13" fontWeight="bold" className="rotate-90" transform={`rotate(90 ${size/2} ${size/2})`}>
        {Math.round(pct)}%
      </text>
    </svg>
  );
}

export default function KpiGoalsPage() {
  const apiBase = process.env.NEXT_PUBLIC_API_URL!;
  const [goals, setGoals] = useState<Goal[]>([]);
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState({
    name: "", metric_key: "revenue_total", target_value: "",
    period_label: "Q2 2026", period_start: "2026-04-01", period_end: "2026-06-30",
    currency: "SEK", customPeriod: false,
  });

  const f = (url: string, opts?: RequestInit) =>
    fetch(`${apiBase}${url}`, { credentials: "include", ...opts });

  async function load() {
    const res = await f("/api/ceo/goals");
    if (res.ok) setGoals((await res.json()).goals);
  }
  useEffect(() => { load(); }, []);

  function handlePeriodPreset(label: string) {
    const p = PERIODS.find(x => x.label === label);
    if (p && label !== "Custom") {
      setForm(f => ({ ...f, period_label: label, period_start: p.start, period_end: p.end, customPeriod: false }));
    } else {
      setForm(f => ({ ...f, period_label: "", customPeriod: true }));
    }
  }

  async function create() {
    if (!form.name.trim()) { toast.error("Enter a goal name"); return; }
    if (!form.target_value || isNaN(Number(form.target_value))) { toast.error("Enter a valid target"); return; }
    const res = await f("/api/ceo/goals", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        name: form.name, metric_key: form.metric_key,
        target_value: Number(form.target_value),
        period_label: form.period_label, period_start: form.period_start, period_end: form.period_end,
        currency: form.currency,
      }),
    });
    if (res.ok) {
      toast.success("Goal created");
      setShowForm(false);
      await load();
    } else {
      const e = await res.json();
      toast.error(e.detail || "Failed");
    }
  }

  async function del(id: string) {
    await f(`/api/ceo/goals/${id}`, { method: "DELETE" });
    setGoals(g => g.filter(x => x.id !== id));
    toast.success("Goal deleted");
  }

  async function toggle(id: string, is_active: boolean) {
    await f(`/api/ceo/goals/${id}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ is_active: !is_active }),
    });
    await load();
  }

  const fmt = (v: number, key: string) =>
    key.endsWith("_pct") || key === "invoice_paid_rate" || key === "gross_margin_pct"
      ? `${v.toFixed(1)}%`
      : v.toLocaleString("sv-SE", { maximumFractionDigits: 0 });

  const active = goals.filter(g => g.is_active);
  const achieved = active.filter(g => g.progress_pct >= 100).length;
  const onTrack = active.filter(g => g.on_track && g.progress_pct < 100).length;
  const atRisk = active.filter(g => !g.on_track).length;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-gray-900">KPI Goals</h1>
          <p className="mt-1 text-sm text-gray-500">Set quantitative targets and track real-time progress.</p>
        </div>
        <button onClick={() => setShowForm(true)} className="btn-primary flex items-center gap-1.5">
          <Plus className="h-3.5 w-3.5" /> New Goal
        </button>
      </div>

      {/* Summary row */}
      {active.length > 0 && (
        <div className="grid grid-cols-3 gap-4">
          {[
            { label: "Achieved", count: achieved, color: "text-green-600", bg: "bg-green-50 border-green-200", icon: CheckCircle2 },
            { label: "On Track", count: onTrack,   color: "text-blue-600",  bg: "bg-blue-50 border-blue-200",  icon: TrendingUp },
            { label: "At Risk",  count: atRisk,    color: "text-red-600",   bg: "bg-red-50 border-red-200",    icon: AlertTriangle },
          ].map(s => (
            <div key={s.label} className={`rounded-xl border p-4 text-center ${s.bg}`}>
              <p className={`text-2xl font-bold ${s.color}`}>{s.count}</p>
              <p className="text-xs text-gray-500 mt-0.5 flex items-center justify-center gap-1">
                <s.icon className={`h-3 w-3 ${s.color}`} />{s.label}
              </p>
            </div>
          ))}
        </div>
      )}

      {/* New goal form */}
      {showForm && (
        <div className="rounded-xl border border-blue-200 bg-blue-50 p-5 space-y-4">
          <p className="text-sm font-semibold text-blue-800">New KPI Goal</p>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <input className="input col-span-2" placeholder="Goal name (e.g. Q2 Revenue Target)" value={form.name}
              onChange={e => setForm(f => ({ ...f, name: e.target.value }))} />
            <div>
              <label className="text-xs font-medium text-gray-700 mb-1 block">Metric</label>
              <select className="input w-full" value={form.metric_key} onChange={e => setForm(f => ({ ...f, metric_key: e.target.value }))}>
                {METRIC_KEYS.map(m => <option key={m.key} value={m.key}>{m.label}</option>)}
              </select>
            </div>
            <div>
              <label className="text-xs font-medium text-gray-700 mb-1 block">Target Value</label>
              <input className="input w-full" type="number" placeholder="100000" value={form.target_value}
                onChange={e => setForm(f => ({ ...f, target_value: e.target.value }))} />
            </div>
            <div>
              <label className="text-xs font-medium text-gray-700 mb-1 block">Period</label>
              <select className="input w-full" value={form.customPeriod ? "Custom" : form.period_label}
                onChange={e => handlePeriodPreset(e.target.value)}>
                {PERIODS.map(p => <option key={p.label} value={p.label}>{p.label}</option>)}
              </select>
            </div>
            {form.customPeriod && (
              <>
                <div>
                  <label className="text-xs font-medium text-gray-700 mb-1 block">Period Label</label>
                  <input className="input" placeholder="e.g. H1 2026" value={form.period_label}
                    onChange={e => setForm(f => ({ ...f, period_label: e.target.value }))} />
                </div>
                <input className="input" type="date" value={form.period_start}
                  onChange={e => setForm(f => ({ ...f, period_start: e.target.value }))} />
                <input className="input" type="date" value={form.period_end}
                  onChange={e => setForm(f => ({ ...f, period_end: e.target.value }))} />
              </>
            )}
          </div>
          <div className="flex gap-2">
            <button onClick={create} className="btn-primary">Create Goal</button>
            <button onClick={() => setShowForm(false)} className="btn-secondary">Cancel</button>
          </div>
        </div>
      )}

      {goals.length === 0 ? (
        <div className="rounded-xl border border-dashed border-gray-300 p-12 text-center">
          <Target className="h-8 w-8 text-gray-300 mx-auto mb-3" />
          <p className="text-sm text-gray-400">No KPI goals yet. Set your first revenue or margin target.</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          {goals.map(g => (
            <div key={g.id} className={`rounded-xl border bg-white p-5 ${!g.is_active ? "opacity-50" : ""} ${
              g.progress_pct >= 100 ? "border-green-300" : g.on_track ? "border-gray-200" : "border-amber-300"
            }`}>
              <div className="flex items-start justify-between gap-3">
                <div className="flex items-center gap-4">
                  <ProgressRing pct={g.progress_pct} onTrack={g.on_track} />
                  <div>
                    <p className="font-semibold text-gray-900">{g.name}</p>
                    <p className="text-xs text-gray-500">{g.metric_label}</p>
                    <p className="text-xs text-gray-400 mt-0.5">{g.period_label}</p>
                  </div>
                </div>
                <div className="flex gap-1 flex-shrink-0">
                  <button onClick={() => toggle(g.id, g.is_active)} className="btn-sm-outline text-xs">
                    {g.is_active ? "Pause" : "Resume"}
                  </button>
                  <button onClick={() => del(g.id)} className="btn-sm-danger-outline">
                    <Trash2 className="h-3.5 w-3.5" />
                  </button>
                </div>
              </div>
              <div className="mt-4 flex justify-between items-center text-sm">
                <div>
                  <span className="text-xs text-gray-500">Actual </span>
                  <span className="font-bold text-gray-900">{fmt(g.actual_value, g.metric_key)}</span>
                </div>
                <div className="text-right">
                  <span className="text-xs text-gray-500">Target </span>
                  <span className="font-bold text-gray-700">{fmt(g.target_value, g.metric_key)}</span>
                </div>
              </div>
              <div className="mt-2 h-1.5 bg-gray-100 rounded-full overflow-hidden">
                <div className={`h-full rounded-full ${
                  g.progress_pct >= 100 ? "bg-green-500" : g.on_track ? "bg-blue-500" : "bg-amber-400"
                }`} style={{ width: `${Math.min(100, g.progress_pct)}%` }} />
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
