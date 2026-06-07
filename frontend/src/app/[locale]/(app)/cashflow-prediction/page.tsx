"use client";

import { api } from "@/lib/api-client";
import { useEffect, useState } from "react";
import { useRouter, useParams } from "next/navigation";
import { toast } from "sonner";
import {
  TrendingUp, AlertTriangle, Plus, RefreshCw, X, Check,
  DollarSign, Users, ChevronDown, ChevronUp, Trash2
} from "lucide-react";
import {
  AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer
} from "recharts";

interface ForecastPoint { date: string; best: number; expected: number; worst: number; }
interface Snapshot { date: string; best: number; expected: number; worst: number; }
interface Recommendation { invoice_id: string; customer_id: string; amount: number; due_date: string; expected_payment: string; avg_delay_days: number; }
interface Scenario { id: string; name: string; description?: string; monthly_delta: number; months_duration: number; is_active: boolean; }

const RANGES = [
  { label: "30 days", days: 30 },
  { label: "60 days", days: 60 },
  { label: "90 days", days: 90 },
];

export default function CashflowPredictionPage() {
  const router = useRouter();
  const params = useParams();
  const locale = params.locale as string;

  const [days, setDays] = useState(90);
  const [alertThreshold, setAlertThreshold] = useState(0);
  const [forecast, setForecast] = useState<{
    projection: ForecastPoint[];
    snapshots: { day_30: Snapshot | null; day_60: Snapshot | null; day_90: Snapshot };
    alert: { date: string; projected_balance: number } | null;
    recommendations: Recommendation[];
    open_invoice_count: number;
    open_invoice_total: number;
  } | null>(null);
  const [scenarios, setScenarios] = useState<Scenario[]>([]);
  const [loading, setLoading] = useState(true);
  const [showAddScenario, setShowAddScenario] = useState(false);
  const [scenarioForm, setScenarioForm] = useState({ name: "", monthly_delta: "", months_duration: "12" });

  async function loadAll() {
    try {
      const [fData, sData] = await Promise.all([
        api.get(`/api/cashflow-prediction/forecast?days=${days}&alert_threshold=${alertThreshold}`),
        api.get("/api/cashflow-prediction/scenarios"),
      ]);
      setForecast(fData);
      setScenarios(sData.items ?? sData);
    } catch (err: any) {
      if (err?.status === 401) router.push(`/${locale}/auth/login`);
      else toast.error("Failed to load forecast");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { loadAll(); }, [days, alertThreshold]);

  async function addScenario(e: React.FormEvent) {
    e.preventDefault();
    try {
      await api.post("/api/cashflow-prediction/scenarios", {
        name: scenarioForm.name,
        monthly_delta: parseFloat(scenarioForm.monthly_delta),
        months_duration: parseInt(scenarioForm.months_duration),
      });
      toast.success("Scenario added");
      setShowAddScenario(false);
      setScenarioForm({ name: "", monthly_delta: "", months_duration: "12" });
      loadAll();
    } catch {
      toast.error("Failed to add scenario");
    }
  }

  async function toggleScenario(sc: Scenario) {
    try {
      await api.patch(`/api/cashflow-prediction/scenarios/${sc.id}`, { is_active: !sc.is_active });
      loadAll();
    } catch {
      toast.error("Failed");
    }
  }

  async function deleteScenario(id: string) {
    try {
      await api.delete(`/api/cashflow-prediction/scenarios/${id}`);
      loadAll();
    } catch {
      toast.error("Failed");
    }
  }

  // Sample every 3rd data point for chart to avoid density
  const chartData = forecast?.projection.filter((_, i) => i % 3 === 0) ?? [];

  const snapshots = forecast?.snapshots;

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">AI Cash Flow Prediction</h1>
          <p className="text-sm text-muted-foreground mt-1">
            Outstanding invoice collection forecast weighted by customer payment history
          </p>
        </div>
        <div className="flex items-center gap-3">
          <div className="flex gap-1 rounded-xl border p-1 bg-background">
            {RANGES.map(r => (
              <button
                key={r.days}
                onClick={() => setDays(r.days)}
                className={`px-3 py-1 text-sm rounded-lg transition-colors font-medium
                  ${days === r.days ? "bg-primary text-primary-foreground" : "hover:bg-muted text-muted-foreground"}`}
              >
                {r.label}
              </button>
            ))}
          </div>
          {loading && <RefreshCw className="h-4 w-4 animate-spin text-muted-foreground" />}
        </div>
      </div>

      {/* Alert banner */}
      {forecast?.alert && (
        <div className="flex items-center gap-3 p-4 rounded-2xl bg-red-50 border border-red-200 text-red-800">
          <AlertTriangle className="h-5 w-5 flex-shrink-0" />
          <p className="text-sm font-medium">
            Projected cash balance drops below {alertThreshold.toLocaleString()} on <strong>{forecast.alert.date}</strong>
            {" "}(expected: {forecast.alert.projected_balance.toLocaleString("sv-SE", { maximumFractionDigits: 0 })})
          </p>
        </div>
      )}

      {/* Snapshot cards */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        {[
          { label: "30-Day Forecast", snap: snapshots?.day_30 },
          { label: "60-Day Forecast", snap: snapshots?.day_60 },
          { label: "90-Day Forecast", snap: snapshots?.day_90 },
        ].map(({ label, snap }) => (
          <div key={label} className="rounded-2xl border bg-card p-5 space-y-2">
            <p className="text-sm text-muted-foreground">{label}</p>
            {snap ? (
              <>
                <p className="text-2xl font-bold">
                  {snap.expected.toLocaleString("sv-SE", { maximumFractionDigits: 0 })}
                </p>
                <div className="flex gap-3 text-xs text-muted-foreground">
                  <span className="text-green-600">▲ {snap.best.toLocaleString("sv-SE", { maximumFractionDigits: 0 })}</span>
                  <span className="text-red-500">▼ {snap.worst.toLocaleString("sv-SE", { maximumFractionDigits: 0 })}</span>
                </div>
              </>
            ) : (
              <p className="text-muted-foreground text-sm">–</p>
            )}
          </div>
        ))}
      </div>

      {/* Chart */}
      {chartData.length > 0 && (
        <div className="rounded-2xl border bg-card p-6">
          <h3 className="font-semibold mb-4">Cash Flow Projection</h3>
          <ResponsiveContainer width="100%" height={280}>
            <AreaChart data={chartData} margin={{ top: 5, right: 20, left: 0, bottom: 5 }}>
              <defs>
                <linearGradient id="best" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#22c55e" stopOpacity={0.2} />
                  <stop offset="95%" stopColor="#22c55e" stopOpacity={0} />
                </linearGradient>
                <linearGradient id="expected" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#3b82f6" stopOpacity={0.3} />
                  <stop offset="95%" stopColor="#3b82f6" stopOpacity={0} />
                </linearGradient>
                <linearGradient id="worst" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#ef4444" stopOpacity={0.15} />
                  <stop offset="95%" stopColor="#ef4444" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
              <XAxis dataKey="date" tick={{ fontSize: 11 }} tickFormatter={d => d.slice(5)} />
              <YAxis tick={{ fontSize: 11 }} tickFormatter={v => v.toLocaleString("sv-SE", { minimumFractionDigits: 0, maximumFractionDigits: 0 })} />
              <Tooltip formatter={(v) => (v as number).toLocaleString("sv-SE", { maximumFractionDigits: 0 })} />
              <Legend />
              <Area type="monotone" dataKey="best" name="Best Case" stroke="#22c55e" fill="url(#best)" strokeWidth={1.5} dot={false} />
              <Area type="monotone" dataKey="expected" name="Expected" stroke="#3b82f6" fill="url(#expected)" strokeWidth={2} dot={false} />
              <Area type="monotone" dataKey="worst" name="Worst Case" stroke="#ef4444" fill="url(#worst)" strokeWidth={1.5} dot={false} />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Recommendations */}
        {(forecast?.recommendations ?? []).length > 0 && (
          <div className="rounded-2xl border bg-card p-5 space-y-3">
            <h3 className="font-semibold flex items-center gap-2">
              <Users className="h-4 w-4 text-primary" />
              Collection Recommendations
            </h3>
            <p className="text-xs text-muted-foreground">
              Prioritise collecting from these customers to maintain cash buffer
            </p>
            <div className="space-y-2">
              {forecast!.recommendations.map((r, i) => (
                <div key={r.invoice_id} className="flex items-center justify-between p-2 rounded-lg bg-muted/40 text-sm">
                  <div>
                    <p className="font-medium">{r.amount.toLocaleString("sv-SE", { maximumFractionDigits: 0 })}</p>
                    <p className="text-xs text-muted-foreground">Expected {r.expected_payment} · avg {r.avg_delay_days}d late</p>
                  </div>
                  {i === 0 && <span className="text-xs bg-red-100 text-red-700 px-2 py-0.5 rounded-full font-medium">Priority</span>}
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Scenarios */}
        <div className="rounded-2xl border bg-card p-5 space-y-3">
          <div className="flex items-center justify-between">
            <h3 className="font-semibold">What-If Scenarios</h3>
            <button
              className="btn-primary text-xs px-2 py-1 flex items-center gap-1"
              onClick={() => setShowAddScenario(true)}
            >
              <Plus className="h-3 w-3" /> Add
            </button>
          </div>
          {scenarios.length === 0 ? (
            <p className="text-sm text-muted-foreground">No scenarios — add one to see impact on the forecast</p>
          ) : (
            <div className="space-y-2">
              {scenarios.map(sc => (
                <div key={sc.id} className="flex items-center justify-between p-2 rounded-lg border text-sm">
                  <div className="flex items-center gap-2 min-w-0">
                    <button
                      onClick={() => toggleScenario(sc)}
                      className={`h-4 w-4 rounded border-2 flex-shrink-0 ${sc.is_active ? "bg-primary border-primary" : "border-muted-foreground"}`}
                    />
                    <div className="min-w-0">
                      <p className="font-medium truncate">{sc.name}</p>
                      <p className={`text-xs ${sc.monthly_delta >= 0 ? "text-green-600" : "text-red-500"}`}>
                        {sc.monthly_delta >= 0 ? "+" : ""}{sc.monthly_delta.toLocaleString()} / month · {sc.months_duration}m
                      </p>
                    </div>
                  </div>
                  <button onClick={() => deleteScenario(sc.id)} className="text-muted-foreground hover:text-red-500 flex-shrink-0">
                    <Trash2 className="h-3.5 w-3.5" />
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Add scenario modal */}
      {showAddScenario && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
          <div className="bg-background rounded-2xl shadow-xl w-full max-w-sm p-6 space-y-4">
            <h2 className="text-lg font-semibold">Add Scenario</h2>
            <p className="text-xs text-muted-foreground">Positive delta = extra revenue. Negative = extra cost.</p>
            <form onSubmit={addScenario} className="space-y-3">
              <div>
                <label className="text-sm font-medium">Name</label>
                <input required className="input mt-1 w-full" placeholder="e.g. Hire 1 person" value={scenarioForm.name} onChange={e => setScenarioForm(f => ({ ...f, name: e.target.value }))} />
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="text-sm font-medium">Monthly delta</label>
                  <input required type="number" className="input mt-1 w-full" placeholder="-3000" value={scenarioForm.monthly_delta} onChange={e => setScenarioForm(f => ({ ...f, monthly_delta: e.target.value }))} />
                </div>
                <div>
                  <label className="text-sm font-medium">Months</label>
                  <input required type="number" min="1" max="60" className="input mt-1 w-full" value={scenarioForm.months_duration} onChange={e => setScenarioForm(f => ({ ...f, months_duration: e.target.value }))} />
                </div>
              </div>
              <div className="flex gap-3 pt-1">
                <button type="button" className="btn-secondary flex-1" onClick={() => setShowAddScenario(false)}>Cancel</button>
                <button type="submit" className="btn-primary flex-1">Add</button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
