"use client";

import { useState, useEffect } from "react";
import { toast } from "sonner";
import { FlaskConical, Plus, Play, Trash2, Users, TrendingUp, TrendingDown } from "lucide-react";
import { api } from "@/lib/api-client";
import styles from "./page.module.scss";

interface Experiment {
  id: string; name: string; description: string | null; status: string;
  control_label: string; variant_label: string;
  control_price_pct_change: number; variant_price_pct_change: number;
  assigned_control_ids: string[]; assigned_variant_ids: string[];
  start_date: string | null; end_date: string | null;
}
interface Customer { id: string; name: string; email: string }
interface Results {
  experiment: Experiment;
  control: { avg_invoice_value: number; total_revenue: number; invoice_count: number; customer_count: number };
  variant: { avg_invoice_value: number; total_revenue: number; invoice_count: number; customer_count: number };
  lift_pct: number; expected_lift_pct: number;
}

const STATUS_COLORS: Record<string, string> = {
  draft: "bg-gray-100 text-gray-600",
  active: "bg-green-100 text-green-700",
  paused: "bg-yellow-100 text-yellow-700",
  completed: "bg-blue-100 text-blue-700",
};

const STATUS_MODULE: Record<string, keyof typeof styles> = {
  draft:     "statusDraft",
  active:    "statusActive",
  paused:    "statusPaused",
  completed: "statusCompleted",
};

export default function ExperimentsPage() {
  const [experiments, setExperiments] = useState<Experiment[]>([]);
  const [customers, setCustomers] = useState<Customer[]>([]);
  const [loading, setLoading] = useState(true);
  const [activeExp, setActiveExp] = useState<string | null>(null);
  const [results, setResults] = useState<Record<string, Results>>({});
  const [showForm, setShowForm] = useState(false);
  const [newExp, setNewExp] = useState({
    name: "", description: "",
    control_label: "Control (current prices)",
    variant_label: "Variant (+10%)",
    control_price_pct_change: 0,
    variant_price_pct_change: 0.10,
    start_date: "", end_date: "",
  });

  const fmt = (v: number) => v.toLocaleString("sv-SE", { maximumFractionDigits: 0 });

  useEffect(() => {
    Promise.all([
      api.get<Experiment[]>("/api/growth/experiments").catch(() => []),
      api.get<Customer[]>("/api/growth/experiments/customers-pool").catch(() => []),
    ]).then(([exps, custs]) => {
      setExperiments(exps ?? []);
      setCustomers(custs ?? []);
    }).finally(() => setLoading(false));
  }, []);

  async function createExperiment() {
    if (!newExp.name) { toast.error("Name is required"); return; }
    try {
      const created = await api.post<Experiment>("/api/growth/experiments", {
        ...newExp,
        start_date: newExp.start_date || null,
        end_date: newExp.end_date || null,
      });
      setExperiments(prev => [created, ...prev]);
      setShowForm(false);
      toast.success("Experiment created");
    } catch { toast.error("Failed to create experiment"); }
  }

  async function activateExperiment(id: string) {
    try {
      const updated = await api.patch<Experiment>(`/api/growth/experiments/${id}`, { status: "active" });
      setExperiments(prev => prev.map(e => e.id === id ? updated : e));
      toast.success("Experiment activated");
    } catch { toast.error("Failed to activate"); }
  }

  async function loadResults(id: string) {
    try {
      const data = await api.get<Results>(`/api/growth/experiments/${id}/results`);
      setResults(prev => ({ ...prev, [id]: data }));
      setActiveExp(id);
    } catch { toast.error("Failed to load results"); }
  }

  async function deleteExperiment(id: string) {
    try {
      await api.delete(`/api/growth/experiments/${id}`);
      setExperiments(prev => prev.filter(e => e.id !== id));
      toast.success("Experiment deleted");
    } catch { toast.error("Failed to delete experiment"); }
  }

  async function autoAssign(exp: Experiment) {
    const shuffled = [...customers].sort(() => Math.random() - 0.5);
    const mid = Math.floor(shuffled.length / 2);
    const control_ids = shuffled.slice(0, mid).map(c => c.id);
    const variant_ids = shuffled.slice(mid).map(c => c.id);
    try {
      const updated = await api.post<Experiment>(`/api/growth/experiments/${exp.id}/assign`, { control_ids, variant_ids });
      setExperiments(prev => prev.map(e => e.id === exp.id ? updated : e));
      toast.success(`Assigned ${control_ids.length}/${variant_ids.length} customers`);
    } catch { toast.error("Failed to assign"); }
  }

  if (loading) return <div className="animate-pulse space-y-4">{[1,2].map(i => <div key={i} className="h-32 rounded-xl bg-gray-100" />)}</div>;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-gray-900">Pricing Experiments</h1>
          <p className="mt-1 text-sm text-gray-500">A/B test price changes on customer cohorts and measure revenue impact.</p>
        </div>
        <button onClick={() => setShowForm(true)} className="btn-primary flex items-center gap-2">
          <Plus className="h-4 w-4" /> New Experiment
        </button>
      </div>

      {showForm && (
        <div className="rounded-xl border border-blue-200 bg-blue-50 p-5 space-y-4">
          <p className="text-sm font-semibold text-blue-800">New Experiment</p>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <input className="input sm:col-span-2" placeholder="Experiment name *" value={newExp.name} onChange={e => setNewExp(p => ({ ...p, name: e.target.value }))} />
            <div>
              <label className="text-xs font-medium text-gray-600 block mb-1">Control label</label>
              <input className="input" value={newExp.control_label} onChange={e => setNewExp(p => ({ ...p, control_label: e.target.value }))} />
            </div>
            <div>
              <label className="text-xs font-medium text-gray-600 block mb-1">Variant label</label>
              <input className="input" value={newExp.variant_label} onChange={e => setNewExp(p => ({ ...p, variant_label: e.target.value }))} />
            </div>
            <div>
              <label className="text-xs font-medium text-gray-600 block mb-1">Control price change</label>
              <input className="input" type="number" step="0.01" value={newExp.control_price_pct_change} onChange={e => setNewExp(p => ({ ...p, control_price_pct_change: parseFloat(e.target.value) || 0 }))} />
              <p className="text-xs text-gray-400 mt-0.5">0 = no change · 0.10 = +10%</p>
            </div>
            <div>
              <label className="text-xs font-medium text-gray-600 block mb-1">Variant price change</label>
              <input className="input" type="number" step="0.01" value={newExp.variant_price_pct_change} onChange={e => setNewExp(p => ({ ...p, variant_price_pct_change: parseFloat(e.target.value) || 0 }))} />
            </div>
            <div>
              <label className="text-xs font-medium text-gray-600 block mb-1">Start date</label>
              <input className="input" type="date" value={newExp.start_date} onChange={e => setNewExp(p => ({ ...p, start_date: e.target.value }))} />
            </div>
            <div>
              <label className="text-xs font-medium text-gray-600 block mb-1">End date</label>
              <input className="input" type="date" value={newExp.end_date} onChange={e => setNewExp(p => ({ ...p, end_date: e.target.value }))} />
            </div>
          </div>
          <div className="flex gap-2">
            <button onClick={createExperiment} className="btn-primary text-sm">Create</button>
            <button onClick={() => setShowForm(false)} className="btn-secondary text-sm">Cancel</button>
          </div>
        </div>
      )}

      {experiments.length === 0 && (
        <div className="text-center py-16 text-gray-400">
          <FlaskConical className="h-10 w-10 mx-auto mb-3 opacity-40" />
          <p>No experiments yet. Create your first A/B pricing test.</p>
        </div>
      )}

      <div className="space-y-4">
        {experiments.map(exp => {
          const r = results[exp.id];
          const isActive = activeExp === exp.id;
          return (
            <div key={exp.id} className="rounded-xl border border-gray-200 bg-white overflow-hidden">
              <div className="p-5">
                <div className="flex items-start justify-between gap-4">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 flex-wrap">
                      <h3 className="font-semibold text-gray-900">{exp.name}</h3>
                      <span className={styles[STATUS_MODULE[exp.status] ?? "statusDraft"]}>{exp.status}</span>
                    </div>
                    <div className="mt-2 flex gap-6 text-sm text-gray-500">
                      <span className="flex items-center gap-1">
                        <Users className="h-3.5 w-3.5" />
                        {exp.assigned_control_ids.length} control · {exp.assigned_variant_ids.length} variant
                      </span>
                      {exp.start_date && <span>From {exp.start_date}</span>}
                      {exp.end_date && <span>To {exp.end_date}</span>}
                    </div>
                    <div className="mt-2 flex gap-4 text-xs text-gray-400">
                      <span className="bg-gray-100 px-2 py-1 rounded">{exp.control_label}: {exp.control_price_pct_change === 0 ? "No change" : `${(exp.control_price_pct_change * 100).toFixed(0)}%`}</span>
                      <span className="bg-purple-50 text-purple-700 px-2 py-1 rounded">{exp.variant_label}: {exp.variant_price_pct_change > 0 ? "+" : ""}{(exp.variant_price_pct_change * 100).toFixed(0)}%</span>
                    </div>
                  </div>
                  <div className="flex gap-2 flex-shrink-0">
                    {exp.status === "draft" && (
                      <>
                        <button onClick={() => autoAssign(exp)} className="text-xs px-2 py-1.5 rounded-lg bg-gray-100 text-gray-700 hover:bg-gray-200">Auto-assign</button>
                        <button onClick={() => activateExperiment(exp.id)} className="text-xs px-2 py-1.5 rounded-lg bg-blue-100 text-blue-700 hover:bg-blue-200 flex items-center gap-1">
                          <Play className="h-3 w-3" /> Activate
                        </button>
                      </>
                    )}
                    <button onClick={() => loadResults(exp.id)} className="text-xs px-2 py-1.5 rounded-lg bg-green-100 text-green-700 hover:bg-green-200">Results</button>
                    <button onClick={() => deleteExperiment(exp.id)} className="text-xs p-1.5 rounded-lg hover:bg-red-50 text-gray-400 hover:text-red-500">
                      <Trash2 className="h-3.5 w-3.5" />
                    </button>
                  </div>
                </div>
              </div>

              {r && isActive && (
                <div className="border-t border-gray-100 p-5 bg-gray-50">
                  <p className="text-sm font-semibold text-gray-700 mb-4">Results</p>
                  <div className="grid grid-cols-2 gap-4">
                    {[["control", r.control, exp.control_label], ["variant", r.variant, exp.variant_label]] .map(([key, stats, label]) => {
                      const s = stats as typeof r.control;
                      return (
                        <div key={key as string} className={`rounded-xl border p-4 ${key === "variant" ? "border-purple-200 bg-purple-50" : "border-gray-200 bg-white"}`}>
                          <p className="text-xs font-semibold text-gray-500 uppercase mb-2">{label as string}</p>
                          <div className="space-y-1">
                            <div className="flex justify-between text-sm"><span className="text-gray-500">Customers</span><span className="font-medium">{s.customer_count}</span></div>
                            <div className="flex justify-between text-sm"><span className="text-gray-500">Invoices</span><span className="font-medium">{s.invoice_count}</span></div>
                            <div className="flex justify-between text-sm"><span className="text-gray-500">Total revenue</span><span className="font-medium">{fmt(s.total_revenue)}</span></div>
                            <div className="flex justify-between text-sm"><span className="text-gray-500">Avg invoice</span><span className="font-semibold">{fmt(s.avg_invoice_value)}</span></div>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                  <div className={`mt-4 rounded-xl p-4 flex items-center gap-3 ${r.lift_pct >= 0 ? "bg-green-50 border border-green-200" : "bg-red-50 border border-red-200"}`}>
                    {r.lift_pct >= 0
                      ? <TrendingUp className="h-5 w-5 text-green-500 flex-shrink-0" />
                      : <TrendingDown className="h-5 w-5 text-red-500 flex-shrink-0" />
                    }
                    <div>
                      <p className={`font-semibold ${r.lift_pct >= 0 ? "text-green-800" : "text-red-800"}`}>
                        Revenue lift: {r.lift_pct >= 0 ? "+" : ""}{r.lift_pct}%
                      </p>
                      <p className="text-xs text-gray-500">Expected: +{(r.expected_lift_pct).toFixed(1)}% · Actual avg invoice change</p>
                    </div>
                  </div>
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
