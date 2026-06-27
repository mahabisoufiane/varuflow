"use client";

import { useEffect, useState } from "react";
import { BarChart2, Loader2 } from "lucide-react";
import { useSearchParams } from "next/navigation";
import { toast } from "sonner";
import { api } from "@/lib/api-client";
import { isPlanGateError, PlanGateBlock } from "@/components/ui/PlanGate";

interface PL {
  project_id: string;
  project_name: string;
  budget: number | null;
  total_hours: number;
  billable_hours: number;
  labour_cost: number;
  total_expenses: number;
  total_cost: number;
  invoiced_value: number;
  margin: number;
  margin_pct: number;
  budget_remaining: number | null;
}

interface Project {
  id: string;
  name: string;
}

export default function PLPage() {
  const searchParams = useSearchParams();
  const [projects, setProjects] = useState<Project[]>([]);
  const [projectId, setProjectId] = useState(searchParams.get("project_id") ?? "");
  const [pl, setPl] = useState<PL | null>(null);
  const [loading, setLoading] = useState(false);
  const [planBlocked, setPlanBlocked] = useState<{ module: string; currentPlan: string } | null>(null);

  useEffect(() => {
    api.get("/api/projects").then((list) => {
      setProjects(list);
      if (!projectId && list.length > 0) setProjectId(list[0].id);
    }).catch((err) => {
      if (isPlanGateError(err)) {
        setPlanBlocked({ module: (err as any).module ?? "hr", currentPlan: (err as any).currentPlan ?? "FREE" });
        return;
      }
      toast.error("Failed to load projects");
    });
  }, []);

  useEffect(() => {
    if (!projectId) return;
    setLoading(true);
    api.get(`/api/projects/${projectId}/pl`)
      .then(setPl)
      .catch(() => { toast.error("Failed to load P&L"); setPl(null); })
      .finally(() => setLoading(false));
  }, [projectId]);

  const budgetPct = pl?.budget && pl.budget > 0 ? Math.min(100, (pl.total_cost / pl.budget) * 100) : null;

  if (planBlocked) return <PlanGateBlock module={planBlocked.module} currentPlan={planBlocked.currentPlan} featureName="Project P&L" />;

  return (
    <div className="p-6 max-w-4xl mx-auto">
      <div className="flex items-center gap-2 mb-6">
        <BarChart2 className="w-6 h-6" />
        <h1 className="text-2xl font-semibold">Project P&L</h1>
      </div>

      <div className="mb-6">
        <label className="text-xs font-medium text-muted-foreground">Project</label>
        <select className="border rounded px-2 py-1.5 text-sm mt-1 min-w-[280px] block" value={projectId} onChange={(e) => setProjectId(e.target.value)}>
          <option value="">— select —</option>
          {projects.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
        </select>
      </div>

      {loading && <div className="flex items-center justify-center h-40"><Loader2 className="w-6 h-6 animate-spin" /></div>}

      {!loading && pl && (
        <div className="space-y-4">
          <h2 className="text-lg font-semibold">{pl.project_name}</h2>

          {/* KPI grid */}
          <div className="grid grid-cols-4 gap-3">
            {[
              { label: "Total Hours", value: `${pl.total_hours.toFixed(1)} h`, sub: `${pl.billable_hours.toFixed(1)} billable` },
              { label: "Labour Cost", value: `${pl.labour_cost.toLocaleString()} SEK` },
              { label: "Expenses", value: `${pl.total_expenses.toLocaleString()} SEK` },
              { label: "Total Cost", value: `${pl.total_cost.toLocaleString()} SEK`, highlight: true },
            ].map(({ label, value, sub, highlight }) => (
              <div key={label} className={`border rounded-lg p-3 ${highlight ? "border-orange-200 bg-orange-50" : ""}`}>
                <p className="text-xs text-muted-foreground">{label}</p>
                <p className={`text-lg font-semibold mt-0.5 ${highlight ? "text-orange-700" : ""}`}>{value}</p>
                {sub && <p className="text-xs text-muted-foreground">{sub}</p>}
              </div>
            ))}
          </div>

          <div className="grid grid-cols-3 gap-3">
            <div className="border rounded-lg p-3">
              <p className="text-xs text-muted-foreground">Invoiced Revenue</p>
              <p className="text-lg font-semibold text-blue-700 mt-0.5">{pl.invoiced_value.toLocaleString()} SEK</p>
            </div>
            <div className={`border rounded-lg p-3 ${pl.margin >= 0 ? "border-green-200 bg-green-50" : "border-red-200 bg-red-50"}`}>
              <p className="text-xs text-muted-foreground">Margin</p>
              <p className={`text-lg font-semibold mt-0.5 ${pl.margin >= 0 ? "text-green-700" : "text-red-700"}`}>{pl.margin.toLocaleString()} SEK</p>
              <p className={`text-xs ${pl.margin >= 0 ? "text-green-600" : "text-red-600"}`}>{pl.margin_pct.toFixed(1)}%</p>
            </div>
            {pl.budget ? (
              <div className="border rounded-lg p-3">
                <p className="text-xs text-muted-foreground">Budget</p>
                <p className="text-lg font-semibold mt-0.5">{pl.budget.toLocaleString()} SEK</p>
                <p className={`text-xs ${(pl.budget_remaining ?? 0) < 0 ? "text-red-600" : "text-green-600"}`}>
                  {(pl.budget_remaining ?? 0) >= 0 ? `${pl.budget_remaining?.toLocaleString()} remaining` : `${Math.abs(pl.budget_remaining ?? 0).toLocaleString()} over budget`}
                </p>
              </div>
            ) : (
              <div className="border rounded-lg p-3 border-dashed">
                <p className="text-xs text-muted-foreground">Budget</p>
                <p className="text-sm text-muted-foreground mt-0.5">Not set</p>
              </div>
            )}
          </div>

          {budgetPct !== null && (
            <div>
              <div className="flex items-center justify-between mb-1">
                <p className="text-xs text-muted-foreground">Budget utilization</p>
                <p className="text-xs font-medium">{budgetPct.toFixed(0)}%</p>
              </div>
              <div className="h-2 rounded-full bg-muted overflow-hidden">
                <div
                  className={`h-full rounded-full transition-all ${budgetPct > 90 ? "bg-red-500" : budgetPct > 70 ? "bg-yellow-500" : "bg-green-500"}`}
                  style={{ width: `${budgetPct}%` }}
                />
              </div>
            </div>
          )}

          {/* Breakdown table */}
          <div className="border rounded-lg overflow-hidden">
            <table className="w-full text-sm">
              <thead>
                <tr className="bg-muted/30 border-b">
                  <th className="py-2 px-4 text-left font-medium text-muted-foreground">Item</th>
                  <th className="py-2 px-4 text-right font-medium text-muted-foreground">Amount (SEK)</th>
                </tr>
              </thead>
              <tbody className="divide-y">
                <tr><td className="py-2 px-4">Labour ({pl.total_hours.toFixed(1)} h)</td><td className="py-2 px-4 text-right font-medium">{pl.labour_cost.toLocaleString()}</td></tr>
                <tr><td className="py-2 px-4">Expenses</td><td className="py-2 px-4 text-right font-medium">{pl.total_expenses.toLocaleString()}</td></tr>
                <tr className="font-semibold bg-muted/20"><td className="py-2 px-4">Total Cost</td><td className="py-2 px-4 text-right">{pl.total_cost.toLocaleString()}</td></tr>
                <tr><td className="py-2 px-4">Invoiced Revenue</td><td className="py-2 px-4 text-right text-blue-700 font-medium">{pl.invoiced_value.toLocaleString()}</td></tr>
                <tr className={`font-semibold ${pl.margin >= 0 ? "text-green-700" : "text-red-700"}`}>
                  <td className="py-2 px-4">Margin ({pl.margin_pct.toFixed(1)}%)</td>
                  <td className="py-2 px-4 text-right">{pl.margin.toLocaleString()}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      )}

      {!loading && !pl && projectId && (
        <p className="text-sm text-muted-foreground">Select a project to view its P&L.</p>
      )}
    </div>
  );
}
