"use client";

import { useState, useEffect } from "react";
import { toast } from "sonner";
import { Plus, Play, Trash2, GitBranch, TrendingUp, TrendingDown } from "lucide-react";
import { api } from "@/lib/api-client";

interface Adjustment {
  id: string; label: string; category: string;
  monthly_change: number; start_month_offset: number; end_month_offset?: number;
}
interface Scenario { id: string; name: string; description?: string; horizon_months: number; adjustment_count: number; updated_at: string }
interface SeriesPoint { day: number; date: string; balance: number }
interface RunResult {
  name: string; adjustments: Adjustment[];
  base: { series: SeriesPoint[]; balance_30d: number; balance_60d: number; balance_90d: number };
  scenario: { series: SeriesPoint[]; balance_30d: number; balance_60d: number; balance_90d: number };
  delta_30d: number; delta_60d: number; delta_90d: number;
}

const CATEGORIES = [
  { value: "expense", label: "Monthly Expense (+cost)" },
  { value: "revenue", label: "Monthly Revenue (+inflow)" },
  { value: "one_time_outflow", label: "One-time Outflow" },
  { value: "one_time_inflow", label: "One-time Inflow" },
];

function DeltaBadge({ value }: { value: number }) {
  const pos = value >= 0;
  const Icon = pos ? TrendingUp : TrendingDown;
  return (
    <span className={`inline-flex items-center gap-1 text-xs font-medium px-2 py-0.5 rounded-full ${
      pos ? "bg-green-100 text-green-700" : "bg-red-100 text-red-600"
    }`}>
      <Icon className="h-3 w-3" />{pos ? "+" : ""}{value.toLocaleString("sv-SE", { maximumFractionDigits: 0 })}
    </span>
  );
}

export default function ScenariosPage() {
  const [scenarios, setScenarios] = useState<Scenario[]>([]);
  const [showForm, setShowForm] = useState(false);
  const [runResult, setRunResult] = useState<RunResult | null>(null);
  const [running, setRunning] = useState(false);
  const [form, setForm] = useState({
    name: "", description: "", horizon_months: 3,
    adjustments: [] as Omit<Adjustment, "id">[],
  });
  const [newAdj, setNewAdj] = useState<Omit<Adjustment, "id">>({
    label: "", category: "expense", monthly_change: -50000, start_month_offset: 0,
  });

  async function load() {
    try {
      const data = await api.get<{ scenarios: Scenario[] }>("/api/ceo/scenarios");
      setScenarios(data.scenarios);
    } catch {}
  }
  useEffect(() => { load(); }, []);

  function addAdjustment() {
    if (!newAdj.label.trim()) { toast.error("Enter a label"); return; }
    setForm(f => ({ ...f, adjustments: [...f.adjustments, { ...newAdj }] }));
    setNewAdj({ label: "", category: "expense", monthly_change: -50000, start_month_offset: 0 });
  }

  async function create() {
    if (!form.name.trim()) { toast.error("Scenario name required"); return; }
    if (form.adjustments.length === 0) { toast.error("Add at least one adjustment"); return; }
    try {
      await api.post("/api/ceo/scenarios", { ...form });
      toast.success("Scenario saved");
      setShowForm(false);
      setForm({ name: "", description: "", horizon_months: 3, adjustments: [] });
      await load();
    } catch {
      toast.error("Failed");
    }
  }

  async function runScenario(id: string) {
    setRunning(true);
    try {
      const data = await api.post<RunResult>(`/api/ceo/scenarios/${id}/run`, {});
      setRunResult(data);
    } catch {
      toast.error("Run failed");
    } finally {
      setRunning(false);
    }
  }

  async function del(id: string) {
    try {
      await api.delete(`/api/ceo/scenarios/${id}`);
    } catch {}
    setScenarios(s => s.filter(x => x.id !== id));
    if (runResult) setRunResult(null);
    toast.success("Deleted");
  }

  const fmt = (v: number) => v.toLocaleString("sv-SE", { maximumFractionDigits: 0 });

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-gray-900">Scenario Planning</h1>
          <p className="mt-1 text-sm text-gray-500">Model cash impact of hires, contracts, cuts, or one-time events.</p>
        </div>
        <button onClick={() => setShowForm(true)} className="btn-primary flex items-center gap-1.5">
          <Plus className="h-3.5 w-3.5" /> New Scenario
        </button>
      </div>

      {/* New scenario form */}
      {showForm && (
        <div className="rounded-xl border border-blue-200 bg-blue-50 p-5 space-y-4">
          <p className="text-sm font-semibold text-blue-800">Build Scenario</p>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <input className="input col-span-2" placeholder="Scenario name (e.g. Hire 2 engineers + new contract)"
              value={form.name} onChange={e => setForm(f => ({ ...f, name: e.target.value }))} />
            <input className="input col-span-2" placeholder="Description (optional)"
              value={form.description} onChange={e => setForm(f => ({ ...f, description: e.target.value }))} />
            <div>
              <label className="text-xs font-medium text-gray-700 mb-1 block">Forecast Horizon</label>
              <select className="input w-full" value={form.horizon_months} onChange={e => setForm(f => ({ ...f, horizon_months: Number(e.target.value) }))}>
                {[1,2,3,6,9,12].map(m => <option key={m} value={m}>{m} month{m > 1 ? "s" : ""}</option>)}
              </select>
            </div>
          </div>

          {/* Adjustments */}
          <div className="space-y-2">
            <p className="text-xs font-semibold text-gray-700">Adjustments</p>
            {form.adjustments.map((adj, i) => (
              <div key={i} className="flex items-center gap-3 bg-white rounded-lg border border-gray-200 px-3 py-2">
                <span className="text-sm flex-1">{adj.label}</span>
                <span className={`text-xs font-medium px-1.5 py-0.5 rounded ${adj.monthly_change >= 0 ? "bg-green-100 text-green-700" : "bg-red-100 text-red-600"}`}>
                  {adj.monthly_change >= 0 ? "+" : ""}{fmt(adj.monthly_change)}/mo
                </span>
                <span className="text-xs text-gray-400 capitalize">{adj.category.replace("_", " ")}</span>
                <button onClick={() => setForm(f => ({ ...f, adjustments: f.adjustments.filter((_, idx) => idx !== i) }))}
                  className="text-gray-300 hover:text-red-500"><Trash2 className="h-3.5 w-3.5" /></button>
              </div>
            ))}

            {/* Add new adjustment */}
            <div className="rounded-lg border border-gray-200 bg-white p-3 space-y-2">
              <p className="text-xs font-medium text-gray-600">Add Adjustment</p>
              <div className="grid grid-cols-2 gap-2">
                <input className="input text-sm col-span-2" placeholder="Label (e.g. 2 new hires)" value={newAdj.label}
                  onChange={e => setNewAdj(a => ({ ...a, label: e.target.value }))} />
                <select className="input text-sm" value={newAdj.category} onChange={e => setNewAdj(a => ({ ...a, category: e.target.value }))}>
                  {CATEGORIES.map(c => <option key={c.value} value={c.value}>{c.label}</option>)}
                </select>
                <input className="input text-sm" type="number" placeholder="Monthly amount (negative = cost)"
                  value={newAdj.monthly_change}
                  onChange={e => setNewAdj(a => ({ ...a, monthly_change: Number(e.target.value) }))} />
                <div>
                  <label className="text-xs text-gray-500">Starts in month</label>
                  <input className="input text-sm w-full" type="number" min={0} max={11} value={newAdj.start_month_offset}
                    onChange={e => setNewAdj(a => ({ ...a, start_month_offset: Number(e.target.value) }))} />
                </div>
              </div>
              <button onClick={addAdjustment} className="btn-secondary text-xs">+ Add to Scenario</button>
            </div>
          </div>

          <div className="flex gap-2">
            <button onClick={create} className="btn-primary">Save Scenario</button>
            <button onClick={() => setShowForm(false)} className="btn-secondary">Cancel</button>
          </div>
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Scenario list */}
        <div className="space-y-3">
          {scenarios.length === 0 && (
            <div className="rounded-xl border border-dashed border-gray-300 p-10 text-center">
              <GitBranch className="h-7 w-7 text-gray-300 mx-auto mb-2" />
              <p className="text-sm text-gray-400">No scenarios yet. Create one to model what-if situations.</p>
            </div>
          )}
          {scenarios.map(s => (
            <div key={s.id} className="rounded-xl border border-gray-200 bg-white p-4">
              <div className="flex items-start justify-between gap-3">
                <div>
                  <p className="font-medium text-gray-900">{s.name}</p>
                  <p className="text-xs text-gray-500 mt-0.5">
                    {s.adjustment_count} adjustment{s.adjustment_count !== 1 ? "s" : ""} · {s.horizon_months}mo horizon
                  </p>
                </div>
                <div className="flex gap-2">
                  <button onClick={() => runScenario(s.id)} disabled={running}
                    className="btn-sm-outline flex items-center gap-1">
                    <Play className="h-3 w-3" /> {running ? "…" : "Run"}
                  </button>
                  <button onClick={() => del(s.id)} className="btn-sm-danger-outline"><Trash2 className="h-3.5 w-3.5" /></button>
                </div>
              </div>
            </div>
          ))}
        </div>

        {/* Run results */}
        {runResult && (
          <div className="rounded-xl border border-gray-200 bg-white p-5 space-y-4">
            <p className="text-sm font-semibold text-gray-700">&quot;{runResult.name}&quot; vs Base</p>

            {/* Delta summary */}
            <div className="grid grid-cols-3 gap-3">
              {[
                { label: "30-day impact", delta: runResult.delta_30d, scenario: runResult.scenario.balance_30d, base: runResult.base.balance_30d },
                { label: "60-day impact", delta: runResult.delta_60d, scenario: runResult.scenario.balance_60d, base: runResult.base.balance_60d },
                { label: "90-day impact", delta: runResult.delta_90d, scenario: runResult.scenario.balance_90d, base: runResult.base.balance_90d },
              ].map(item => (
                <div key={item.label} className="text-center">
                  <p className="text-xs text-gray-500">{item.label}</p>
                  <DeltaBadge value={item.delta} />
                  <p className="text-xs text-gray-400 mt-1">{fmt(item.scenario)}</p>
                </div>
              ))}
            </div>

            {/* Combined sparkline */}
            {runResult.base.series.length > 1 && (
              <div className="rounded-lg border border-gray-100 bg-gray-50 p-3">
                <div className="flex items-center gap-4 text-xs text-gray-500 mb-2">
                  <span className="flex items-center gap-1"><span className="w-4 h-0.5 bg-gray-400 inline-block" /> Base</span>
                  <span className="flex items-center gap-1"><span className="w-4 h-0.5 bg-blue-500 inline-block" /> Scenario</span>
                </div>
                <div className="h-32">
                  <svg viewBox={`0 0 ${runResult.base.series.length * 12} 128`} className="w-full h-full" preserveAspectRatio="none">
                    {(() => {
                      const base = runResult.base.series;
                      const scen = runResult.scenario.series;
                      const allVals = [...base.map(s => s.balance), ...scen.map(s => s.balance)];
                      const mn = Math.min(...allVals, 0), mx = Math.max(...allVals, 1);
                      const range = mx - mn || 1;
                      const toY = (v: number) => 128 - ((v - mn) / range) * 108 - 10;
                      const pts = (arr: SeriesPoint[]) => arr.map((s, i) => `${i*12+6},${toY(s.balance)}`).join(" ");
                      const zeroY = toY(0);
                      return (
                        <>
                          {mn < 0 && <line x1="0" y1={zeroY} x2={base.length*12} y2={zeroY} stroke="#d1d5db" strokeWidth="1" strokeDasharray="3,3" />}
                          <polyline points={pts(base)} fill="none" stroke="#9ca3af" strokeWidth="1.5" strokeDasharray="4,2" />
                          <polyline points={pts(scen)} fill="none" stroke="#3b82f6" strokeWidth="2" />
                        </>
                      );
                    })()}
                  </svg>
                </div>
              </div>
            )}

            {/* Adjustment list */}
            <div className="space-y-1">
              <p className="text-xs font-medium text-gray-600">Adjustments Applied</p>
              {runResult.adjustments.map((adj, i) => (
                <div key={i} className="flex justify-between text-xs text-gray-600">
                  <span>{adj.label}</span>
                  <span className={adj.monthly_change >= 0 ? "text-green-600" : "text-red-600"}>
                    {adj.monthly_change >= 0 ? "+" : ""}{fmt(adj.monthly_change)}/mo
                  </span>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
