"use client";

/**
 * Budget vs Actual P&L
 *
 * Wires:
 *   GET    /api/accounting/budgets
 *   POST   /api/accounting/budgets
 *   GET    /api/accounting/budgets/{id}
 *   PUT    /api/accounting/budgets/{id}/lines
 *   POST   /api/accounting/budgets/{id}/approve
 *   GET    /api/accounting/budgets/{id}/vs-actual?year=&month=
 */
import { useCallback, useEffect, useState } from "react";
import { PiggyBank, Loader2, Plus, RefreshCw, CheckCircle } from "lucide-react";
import { toast } from "sonner";
import { api } from "@/lib/api-client";
import styles from "./page.module.scss";
import { isPlanGateError, PlanGateBlock } from "@/components/ui/PlanGate";

// ─── Types ──────────────────────────────────────────────────────────────────

interface BudgetLine {
  id: string;
  account_code: string;
  month: number;
  amount: string;
}

interface Budget {
  id: string;
  name: string;
  fiscal_year: number;
  status: string;
  approved_at: string | null;
  created_at: string;
  lines: BudgetLine[];
}

interface VsActualLine {
  account_code: string;
  month: number;
  budget: string;
  actual: string;
  variance: string;
  variance_pct: string | null;
}

// ─── Helpers ────────────────────────────────────────────────────────────────

const MONTHS = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"];
const fmt = (n: string | number) =>
  Number(n).toLocaleString("sv-SE", { minimumFractionDigits: 0, maximumFractionDigits: 0 });

const BAS_ACCOUNTS = [
  { code: "3000", name: "Försäljning" },
  { code: "4000", name: "Inköp av varor" },
  { code: "7210", name: "Löner" },
  { code: "7510", name: "Arbetsgivaravgifter" },
  { code: "7830", name: "Avskrivningar" },
];

const STATUS_COLORS: Record<string, string> = {
  DRAFT: "text-amber-400 bg-amber-400/10",
  APPROVED: "text-emerald-400 bg-emerald-400/10",
};

const STATUS_MODULE: Record<string, keyof typeof styles> = {
  DRAFT:    "statusDraft",
  APPROVED: "statusApproved",
};

// ─── Component ──────────────────────────────────────────────────────────────

export default function BudgetPage() {
  const [budgets, setBudgets]       = useState<Budget[]>([]);
  const [loading, setLoading]       = useState(true);
  const [selected, setSelected]     = useState<Budget | null>(null);
  const [tab, setTab]               = useState<"edit" | "vs-actual">("edit");
  const [showCreate, setShowCreate] = useState(false);

  const currentYear = new Date().getFullYear();
  const currentMonth = new Date().getMonth() + 1;

  const [createForm, setCreateForm] = useState({ name: `FY${currentYear} Budget`, fiscal_year: String(currentYear) });
  const [vsMonth, setVsMonth]       = useState(currentMonth);
  const [vsYear, setVsYear]         = useState(currentYear);
  const [vsData, setVsData]         = useState<VsActualLine[] | null>(null);
  const [vsLoading, setVsLoading]   = useState(false);

  const [planBlocked, setPlanBlocked] = useState<{ module: string; currentPlan: string } | null>(null);

  // Editable cells: {account_code: {month: value}}
  const [cells, setCells] = useState<Record<string, Record<number, string>>>({});

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const data = await api.get<Budget[]>("/api/accounting/budgets");
      setBudgets(data);
    } catch (err) {
      if (isPlanGateError(err)) {
        setPlanBlocked({ module: (err as any).module ?? "finance", currentPlan: (err as any).currentPlan ?? "FREE" });
        return;
      }
      toast.error(err instanceof Error ? err.message : "Failed to load budgets");
    } finally { setLoading(false); }
  }, []);

  useEffect(() => { load(); }, [load]);

  const initCells = (b: Budget) => {
    const map: Record<string, Record<number, string>> = {};
    for (const acc of BAS_ACCOUNTS) {
      map[acc.code] = {};
      for (let m = 1; m <= 12; m++) map[acc.code][m] = "0";
    }
    for (const l of b.lines) {
      if (!map[l.account_code]) map[l.account_code] = {};
      map[l.account_code][l.month] = l.amount;
    }
    setCells(map);
  };

  const selectBudget = (b: Budget) => {
    setSelected(b);
    initCells(b);
    setTab("edit");
    setVsData(null);
  };

  const handleCreate = async () => {
    if (!createForm.name) { toast.error("Name required"); return; }
    try {
      const data = await api.post<Budget>("/api/accounting/budgets", {
        name: createForm.name,
        fiscal_year: parseInt(createForm.fiscal_year),
      });
      toast.success("Budget created");
      setShowCreate(false);
      await load();
      selectBudget(data);
    } catch (e: unknown) { toast.error(e instanceof Error ? e.message : "Failed"); }
  };

  const handleSaveLines = async () => {
    if (!selected) return;
    const lines = [];
    for (const [code, months] of Object.entries(cells)) {
      for (const [m, val] of Object.entries(months)) {
        const amount = parseFloat(val) || 0;
        if (amount !== 0) {
          lines.push({ account_code: code, month: parseInt(m), amount });
        }
      }
    }
    try {
      await api.put(`/api/accounting/budgets/${selected.id}/lines`, lines);
      toast.success("Budget saved");
      await load();
    } catch (e: unknown) { toast.error(e instanceof Error ? e.message : "Failed"); }
  };

  const handleApprove = async () => {
    if (!selected) return;
    try {
      await api.post(`/api/accounting/budgets/${selected.id}/approve`, {});
      toast.success("Budget approved");
      await load();
      const updated = budgets.find(b => b.id === selected.id);
      if (updated) setSelected({ ...updated, status: "APPROVED" });
    } catch (e: unknown) { toast.error(e instanceof Error ? e.message : "Failed"); }
  };

  const handleVsActual = async () => {
    if (!selected) return;
    setVsLoading(true);
    try {
      const data = await api.get<VsActualLine[]>(
        `/api/accounting/budgets/${selected.id}/vs-actual?year=${vsYear}&month=${vsMonth}`
      );
      setVsData(data);
    } catch (e: unknown) {
      toast.error(e instanceof Error ? e.message : "Failed");
    } finally { setVsLoading(false); }
  };

  if (planBlocked) return <PlanGateBlock module={planBlocked.module} currentPlan={planBlocked.currentPlan} featureName="Budget" />;

  return (
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <PiggyBank className="w-6 h-6 text-indigo-400" />
          <div>
            <h1 className="text-xl font-bold vf-text-1">Budget vs Actual</h1>
            <p className="text-xs vf-text-m mt-0.5">Plan fiscal-year budgets and compare against ledger actuals</p>
          </div>
        </div>
        <div className="flex gap-2">
          <button onClick={load} className="vf-btn-ghost text-xs px-3 py-1.5">
            <RefreshCw className="w-3.5 h-3.5 mr-1.5 inline" />Refresh
          </button>
          <button onClick={() => setShowCreate(true)} className="vf-btn text-xs px-3 py-1.5">
            <Plus className="w-3.5 h-3.5 mr-1.5 inline" />New Budget
          </button>
        </div>
      </div>

      {showCreate && (
        <div className="vf-section p-5 space-y-4">
          <p className="font-semibold vf-text-1">New Budget</p>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="text-xs vf-text-m block mb-1">Name</label>
              <input type="text" value={createForm.name}
                onChange={e => setCreateForm(p => ({ ...p, name: e.target.value }))}
                className="vf-input text-sm w-full" />
            </div>
            <div>
              <label className="text-xs vf-text-m block mb-1">Fiscal Year</label>
              <input type="number" value={createForm.fiscal_year}
                onChange={e => setCreateForm(p => ({ ...p, fiscal_year: e.target.value }))}
                className="vf-input text-sm w-full" />
            </div>
          </div>
          <div className="flex justify-end gap-2">
            <button onClick={() => setShowCreate(false)} className="vf-btn-ghost text-xs px-3 py-1.5">Cancel</button>
            <button onClick={handleCreate} className="vf-btn text-xs px-3 py-1.5">Create</button>
          </div>
        </div>
      )}

      <div className="grid grid-cols-4 gap-4">
        {/* Budget list */}
        <div className="col-span-1 space-y-2">
          {loading ? (
            <div className="flex justify-center py-8"><Loader2 className="w-5 h-5 animate-spin vf-text-m" /></div>
          ) : budgets.length === 0 ? (
            <div className="vf-section p-6 text-center vf-text-m text-sm">No budgets yet.</div>
          ) : (
            budgets.map(b => (
              <div
                key={b.id}
                className={`vf-section p-3 cursor-pointer hover:ring-1 hover:ring-indigo-500/40 transition-all ${
                  selected?.id === b.id ? "ring-1 ring-indigo-500/60" : ""
                }`}
                onClick={() => selectBudget(b)}
              >
                <p className="font-semibold vf-text-1 text-sm">{b.name}</p>
                <div className="flex items-center justify-between mt-1">
                  <span className="text-xs vf-text-m">FY{b.fiscal_year}</span>
                  <span className={styles[STATUS_MODULE[b.status] ?? "statusDraft"]}>
                    {b.status}
                  </span>
                </div>
              </div>
            ))
          )}
        </div>

        {/* Detail panel */}
        <div className="col-span-3">
          {selected ? (
            <div className="space-y-4">
              {/* Tabs + actions */}
              <div className="flex items-center justify-between">
                <div className="flex gap-1">
                  {(["edit", "vs-actual"] as const).map(t => (
                    <button key={t} onClick={() => setTab(t)}
                      className={`text-xs px-3 py-1.5 rounded-md transition-colors ${
                        tab === t ? "vf-btn" : "vf-btn-ghost"
                      }`}>
                      {t === "edit" ? "Edit Budget" : "Vs. Actual"}
                    </button>
                  ))}
                </div>
                <div className="flex gap-2">
                  {selected.status === "DRAFT" && tab === "edit" && (
                    <>
                      <button onClick={handleSaveLines} className="vf-btn-ghost text-xs px-3 py-1.5">Save</button>
                      <button onClick={handleApprove} className="vf-btn text-xs px-3 py-1.5">
                        <CheckCircle className="w-3.5 h-3.5 mr-1 inline" />Approve
                      </button>
                    </>
                  )}
                </div>
              </div>

              {/* Edit tab: spreadsheet grid */}
              {tab === "edit" && (
                <div className="vf-section overflow-x-auto">
                  <table className="w-full text-xs">
                    <thead>
                      <tr className="border-b border-white/10">
                        <th className="text-left py-2 px-3 vf-text-m font-medium w-32">Account</th>
                        {MONTHS.map(m => (
                          <th key={m} className="text-right py-2 px-2 vf-text-m font-medium">{m}</th>
                        ))}
                        <th className="text-right py-2 px-3 vf-text-m font-medium">Total</th>
                      </tr>
                    </thead>
                    <tbody>
                      {BAS_ACCOUNTS.map(acc => {
                        const row = cells[acc.code] ?? {};
                        const total = Object.values(row).reduce((s, v) => s + (parseFloat(v) || 0), 0);
                        return (
                          <tr key={acc.code} className="border-b border-white/5">
                            <td className="py-1.5 px-3 vf-text-1">
                              <p className="font-mono">{acc.code}</p>
                              <p className="vf-text-m text-xs">{acc.name}</p>
                            </td>
                            {Array.from({ length: 12 }, (_, i) => i + 1).map(m => (
                              <td key={m} className="py-1 px-1">
                                <input
                                  type="number"
                                  disabled={selected.status !== "DRAFT"}
                                  value={row[m] ?? "0"}
                                  onChange={e => setCells(prev => ({
                                    ...prev,
                                    [acc.code]: { ...prev[acc.code], [m]: e.target.value },
                                  }))}
                                  className="vf-input text-xs w-16 text-right disabled:opacity-50"
                                />
                              </td>
                            ))}
                            <td className="py-1.5 px-3 font-mono font-bold vf-text-1 text-right">
                              {fmt(total)}
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              )}

              {/* Vs Actual tab */}
              {tab === "vs-actual" && (
                <div className="space-y-4">
                  <div className="flex items-center gap-3">
                    <select value={vsYear} onChange={e => setVsYear(parseInt(e.target.value))}
                      className="vf-input text-xs">
                      {[currentYear - 1, currentYear, currentYear + 1].map(y => (
                        <option key={y} value={y}>{y}</option>
                      ))}
                    </select>
                    <select value={vsMonth} onChange={e => setVsMonth(parseInt(e.target.value))}
                      className="vf-input text-xs">
                      {MONTHS.map((m, i) => <option key={i} value={i + 1}>{m}</option>)}
                    </select>
                    <button onClick={handleVsActual} className="vf-btn text-xs px-3 py-1.5">
                      {vsLoading ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : "Compare"}
                    </button>
                  </div>

                  {vsData && (
                    <div className="vf-section overflow-hidden">
                      <table className="w-full text-xs">
                        <thead>
                          <tr className="border-b border-white/10">
                            {["Account", "Budget", "Actual", "Variance", "%"].map(h => (
                              <th key={h} className="text-left py-2 px-3 vf-text-m font-medium">{h}</th>
                            ))}
                          </tr>
                        </thead>
                        <tbody>
                          {vsData.map((line, i) => {
                            const positive = Number(line.variance) >= 0;
                            return (
                              <tr key={i} className="border-b border-white/5">
                                <td className="py-2 px-3 font-mono vf-text-1">{line.account_code}</td>
                                <td className="py-2 px-3 font-mono vf-text-m">{fmt(line.budget)}</td>
                                <td className="py-2 px-3 font-mono vf-text-1">{fmt(line.actual)}</td>
                                <td className={`py-2 px-3 font-mono font-medium ${positive ? "text-emerald-400" : "text-rose-400"}`}>
                                  {positive ? "+" : ""}{fmt(line.variance)}
                                </td>
                                <td className={`py-2 px-3 font-mono ${positive ? "text-emerald-400" : "text-rose-400"}`}>
                                  {line.variance_pct != null ? `${Number(line.variance_pct).toFixed(1)}%` : "—"}
                                </td>
                              </tr>
                            );
                          })}
                        </tbody>
                      </table>
                    </div>
                  )}
                </div>
              )}
            </div>
          ) : (
            <div className="vf-section p-8 text-center vf-text-m text-sm">
              Select a budget to view and edit.
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
