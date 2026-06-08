"use client";

/**
 * Payroll Processing
 *
 * Wires:
 *   GET    /api/accounting/payroll
 *   POST   /api/accounting/payroll
 *   GET    /api/accounting/payroll/{id}
 *   POST   /api/accounting/payroll/{id}/entries
 *   DELETE /api/accounting/payroll/{id}/entries/{eid}
 *   POST   /api/accounting/payroll/{id}/approve
 *   GET    /api/accounting/payroll/{id}/agi-xml
 */
import { useCallback, useEffect, useState } from "react";
import { Wallet, Loader2, Plus, RefreshCw, CheckCircle, Download, Trash2 } from "lucide-react";
import { toast } from "sonner";
import { api } from "@/lib/api-client";
import styles from "./page.module.scss";
import { isPlanGateError, PlanGateBlock } from "@/components/ui/PlanGate";

// ─── Types ──────────────────────────────────────────────────────────────────

interface PayrollEntry {
  id: string;
  employee_name: string;
  staff_id: string | null;
  gross_salary: string;
  income_tax: string;
  social_contribution: string;
  net_salary: string;
  employer_total: string;
  notes: string | null;
  created_at: string;
}

interface PayrollRun {
  id: string;
  period_start: string;
  period_end: string;
  status: string;
  total_gross: string;
  total_employer_cost: string;
  journal_entry_id: string | null;
  approved_at: string | null;
  created_at: string;
  entries: PayrollEntry[];
}

// ─── Helpers ────────────────────────────────────────────────────────────────

const fmt = (n: string | number) =>
  Number(n).toLocaleString("sv-SE", { minimumFractionDigits: 2, maximumFractionDigits: 2 });

const STATUS_COLORS: Record<string, string> = {
  DRAFT: "text-amber-400 bg-amber-400/10",
  APPROVED: "text-emerald-400 bg-emerald-400/10",
  PAID: "text-indigo-400 bg-indigo-400/10",
};

const STATUS_MODULE: Record<string, keyof typeof styles> = {
  DRAFT:    "statusDraft",
  APPROVED: "statusApproved",
  PAID:     "statusPaid",
};

// ─── Component ──────────────────────────────────────────────────────────────

export default function PayrollPage() {
  const [runs, setRuns]           = useState<PayrollRun[]>([]);
  const [loading, setLoading]     = useState(true);
  const [selected, setSelected]   = useState<PayrollRun | null>(null);
  const [showCreate, setShowCreate] = useState(false);
  const [showAddEntry, setShowAddEntry] = useState(false);

  const today = new Date().toISOString().slice(0, 10);
  const firstOfMonth = today.slice(0, 8) + "01";

  const [runForm, setRunForm] = useState({ period_start: firstOfMonth, period_end: today });
  const [entryForm, setEntryForm] = useState({
    employee_name: "", gross_salary: "", income_tax: "0", personal_number: "", notes: "",
  });

  const [planBlocked, setPlanBlocked] = useState<{ module: string; currentPlan: string } | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const data = await api.get<PayrollRun[]>("/api/accounting/payroll");
      setRuns(data);
    } catch (err) {
      if (isPlanGateError(err)) {
        setPlanBlocked({ module: (err as any).module ?? "finance", currentPlan: (err as any).currentPlan ?? "FREE" });
        return;
      }
      toast.error(err instanceof Error ? err.message : "Failed to load payroll runs");
    } finally { setLoading(false); }
  }, []);

  useEffect(() => { load(); }, [load]);

  const loadRun = async (id: string) => {
    try {
      const data = await api.get<PayrollRun>(`/api/accounting/payroll/${id}`);
      setSelected(data);
      setRuns(prev => prev.map(r => r.id === id ? data : r));
    } catch (e: unknown) {
      toast.error(e instanceof Error ? e.message : "Failed to load run");
    }
  };

  const handleCreateRun = async () => {
    try {
      await api.post("/api/accounting/payroll", runForm);
      toast.success("Payroll run created");
      setShowCreate(false);
      await load();
    } catch (e: unknown) { toast.error(e instanceof Error ? e.message : "Failed"); }
  };

  const handleAddEntry = async () => {
    if (!selected) return;
    if (!entryForm.employee_name || !entryForm.gross_salary) {
      toast.error("Employee name and gross salary required");
      return;
    }
    try {
      await api.post(`/api/accounting/payroll/${selected.id}/entries`, {
        employee_name: entryForm.employee_name,
        gross_salary: parseFloat(entryForm.gross_salary),
        income_tax: parseFloat(entryForm.income_tax) || 0,
        personal_number: entryForm.personal_number || null,
        notes: entryForm.notes || null,
      });
      toast.success("Entry added");
      setShowAddEntry(false);
      setEntryForm({ employee_name: "", gross_salary: "", income_tax: "0", personal_number: "", notes: "" });
      await loadRun(selected.id);
    } catch (e: unknown) { toast.error(e instanceof Error ? e.message : "Failed"); }
  };

  const handleDeleteEntry = async (entryId: string) => {
    if (!selected) return;
    try {
      await api.delete(`/api/accounting/payroll/${selected.id}/entries/${entryId}`);
      toast.success("Entry removed");
      await loadRun(selected.id);
    } catch (e: unknown) { toast.error(e instanceof Error ? e.message : "Failed"); }
  };

  const handleApprove = async () => {
    if (!selected) return;
    try {
      await api.post(`/api/accounting/payroll/${selected.id}/approve`, {});
      toast.success("Payroll run approved and posted to ledger");
      await loadRun(selected.id);
    } catch (e: unknown) { toast.error(e instanceof Error ? e.message : "Failed"); }
  };

  const handleAgiXml = () => {
    if (!selected) return;
    window.open(`/api/accounting/payroll/${selected.id}/agi-xml`, "_blank");
  };

  if (planBlocked) return <PlanGateBlock module={planBlocked.module} currentPlan={planBlocked.currentPlan} featureName="Payroll" />;

  return (
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Wallet className="w-6 h-6 text-indigo-400" />
          <div>
            <h1 className="text-xl font-bold vf-text-1">Payroll Processing</h1>
            <p className="text-xs vf-text-m mt-0.5">Manage salary runs, arbetsgivaravgift, and AGI reporting</p>
          </div>
        </div>
        <div className="flex gap-2">
          <button onClick={load} className="vf-btn-ghost text-xs px-3 py-1.5">
            <RefreshCw className="w-3.5 h-3.5 mr-1.5 inline" />Refresh
          </button>
          <button onClick={() => setShowCreate(true)} className="vf-btn text-xs px-3 py-1.5">
            <Plus className="w-3.5 h-3.5 mr-1.5 inline" />New Run
          </button>
        </div>
      </div>

      {/* Create run form */}
      {showCreate && (
        <div className="vf-section p-5 space-y-4">
          <p className="font-semibold vf-text-1">New Payroll Run</p>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="text-xs vf-text-m block mb-1">Period Start</label>
              <input type="date" value={runForm.period_start}
                onChange={e => setRunForm(p => ({ ...p, period_start: e.target.value }))}
                className="vf-input text-sm w-full" />
            </div>
            <div>
              <label className="text-xs vf-text-m block mb-1">Period End</label>
              <input type="date" value={runForm.period_end}
                onChange={e => setRunForm(p => ({ ...p, period_end: e.target.value }))}
                className="vf-input text-sm w-full" />
            </div>
          </div>
          <div className="flex justify-end gap-2">
            <button onClick={() => setShowCreate(false)} className="vf-btn-ghost text-xs px-3 py-1.5">Cancel</button>
            <button onClick={handleCreateRun} className="vf-btn text-xs px-3 py-1.5">Create</button>
          </div>
        </div>
      )}

      <div className="grid grid-cols-3 gap-4">
        {/* Run list */}
        <div className="col-span-1 space-y-2">
          {loading ? (
            <div className="flex justify-center py-12"><Loader2 className="w-5 h-5 animate-spin vf-text-m" /></div>
          ) : runs.length === 0 ? (
            <div className="vf-section p-8 text-center vf-text-m text-sm">No payroll runs yet.</div>
          ) : (
            runs.map(run => (
              <div
                key={run.id}
                className={`vf-section p-4 cursor-pointer hover:ring-1 hover:ring-indigo-500/40 transition-all ${
                  selected?.id === run.id ? "ring-1 ring-indigo-500/60" : ""
                }`}
                onClick={() => loadRun(run.id)}
              >
                <div className="flex items-start justify-between">
                  <div>
                    <p className="font-semibold vf-text-1 text-sm">
                      {run.period_start} – {run.period_end}
                    </p>
                    <p className="text-xs vf-text-m mt-0.5">{run.entries.length} employees</p>
                  </div>
                  <span className={styles[STATUS_MODULE[run.status] ?? "statusDraft"]}>
                    {run.status}
                  </span>
                </div>
                <div className="mt-2 flex justify-between text-xs">
                  <span className="vf-text-m">Gross</span>
                  <span className="font-mono vf-text-1">{fmt(run.total_gross)}</span>
                </div>
                <div className="flex justify-between text-xs">
                  <span className="vf-text-m">Employer cost</span>
                  <span className="font-mono vf-text-1">{fmt(run.total_employer_cost)}</span>
                </div>
              </div>
            ))
          )}
        </div>

        {/* Detail panel */}
        <div className="col-span-2">
          {selected ? (
            <div className="space-y-4">
              {/* Header */}
              <div className="vf-section p-4 flex items-center justify-between">
                <div>
                  <p className="font-semibold vf-text-1">{selected.period_start} – {selected.period_end}</p>
                  <p className="text-xs vf-text-m mt-0.5">
                    Gross: {fmt(selected.total_gross)} · Employer cost: {fmt(selected.total_employer_cost)}
                  </p>
                </div>
                <div className="flex gap-2">
                  {selected.status === "DRAFT" && (
                    <>
                      <button onClick={() => setShowAddEntry(!showAddEntry)} className="vf-btn-ghost text-xs px-3 py-1.5">
                        <Plus className="w-3.5 h-3.5 mr-1 inline" />Add Employee
                      </button>
                      <button onClick={handleApprove} className="vf-btn text-xs px-3 py-1.5">
                        <CheckCircle className="w-3.5 h-3.5 mr-1 inline" />Approve
                      </button>
                    </>
                  )}
                  {selected.status !== "DRAFT" && (
                    <button onClick={handleAgiXml} className="vf-btn-ghost text-xs px-3 py-1.5">
                      <Download className="w-3.5 h-3.5 mr-1 inline" />AGI XML
                    </button>
                  )}
                </div>
              </div>

              {/* Add entry form */}
              {showAddEntry && selected.status === "DRAFT" && (
                <div className="vf-section p-4 space-y-3">
                  <p className="font-medium vf-text-1 text-sm">Add Employee Entry</p>
                  <div className="grid grid-cols-2 gap-3">
                    {[
                      { label: "Employee Name", key: "employee_name", type: "text", placeholder: "Anna Andersson" },
                      { label: "Personnummer", key: "personal_number", type: "text", placeholder: "YYYYMMDD-XXXX" },
                      { label: "Gross Salary (SEK)", key: "gross_salary", type: "number", placeholder: "35000" },
                      { label: "Preliminary Tax", key: "income_tax", type: "number", placeholder: "8000" },
                    ].map(f => (
                      <div key={f.key}>
                        <label className="text-xs vf-text-m block mb-1">{f.label}</label>
                        <input type={f.type} placeholder={f.placeholder}
                          value={(entryForm as Record<string, string>)[f.key]}
                          onChange={e => setEntryForm(p => ({ ...p, [f.key]: e.target.value }))}
                          className="vf-input text-sm w-full" />
                      </div>
                    ))}
                  </div>
                  <div className="flex justify-end gap-2">
                    <button onClick={() => setShowAddEntry(false)} className="vf-btn-ghost text-xs px-3 py-1.5">Cancel</button>
                    <button onClick={handleAddEntry} className="vf-btn text-xs px-3 py-1.5">Add</button>
                  </div>
                </div>
              )}

              {/* Entries table */}
              {selected.entries.length === 0 ? (
                <div className="vf-section p-8 text-center vf-text-m text-sm">No entries yet. Add employees to this run.</div>
              ) : (
                <div className="vf-section overflow-hidden">
                  <table className="w-full text-xs">
                    <thead>
                      <tr className="border-b border-white/10">
                        {["Employee", "Gross", "Tax", "Social (31.42%)", "Net", "Employer Total", ""].map(h => (
                          <th key={h} className="text-left py-2 px-3 vf-text-m font-medium">{h}</th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {selected.entries.map(ent => (
                        <tr key={ent.id} className="border-b border-white/5 hover:bg-white/5">
                          <td className="py-2 px-3 vf-text-1 font-medium">{ent.employee_name}</td>
                          <td className="py-2 px-3 font-mono vf-text-1">{fmt(ent.gross_salary)}</td>
                          <td className="py-2 px-3 font-mono vf-text-m">{fmt(ent.income_tax)}</td>
                          <td className="py-2 px-3 font-mono vf-text-m">{fmt(ent.social_contribution)}</td>
                          <td className="py-2 px-3 font-mono text-emerald-400">{fmt(ent.net_salary)}</td>
                          <td className="py-2 px-3 font-mono vf-text-1">{fmt(ent.employer_total)}</td>
                          <td className="py-2 px-3">
                            {selected.status === "DRAFT" && (
                              <button onClick={() => handleDeleteEntry(ent.id)} className="vf-text-m hover:text-rose-400 transition-colors">
                                <Trash2 className="w-3.5 h-3.5" />
                              </button>
                            )}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}

              {/* Totals summary */}
              {selected.entries.length > 0 && (
                <div className="vf-section p-4">
                  <div className="grid grid-cols-3 gap-4 text-xs">
                    <div className="text-center">
                      <p className="vf-text-m">Total Gross</p>
                      <p className="font-mono font-bold vf-text-1 text-base mt-0.5">{fmt(selected.total_gross)}</p>
                    </div>
                    <div className="text-center">
                      <p className="vf-text-m">Total Social Contributions</p>
                      <p className="font-mono font-bold vf-text-1 text-base mt-0.5">
                        {fmt(selected.entries.reduce((s, e) => s + Number(e.social_contribution), 0))}
                      </p>
                    </div>
                    <div className="text-center">
                      <p className="vf-text-m">Total Employer Cost</p>
                      <p className="font-mono font-bold vf-text-1 text-base mt-0.5">{fmt(selected.total_employer_cost)}</p>
                    </div>
                  </div>
                </div>
              )}
            </div>
          ) : (
            <div className="vf-section p-8 text-center vf-text-m text-sm">
              Select a payroll run to view details.
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
