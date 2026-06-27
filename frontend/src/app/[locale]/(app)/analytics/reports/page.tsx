"use client";

import { useState, useEffect } from "react";
import { toast } from "sonner";
import { Plus, Play, Trash2, ChevronRight, Table2, Filter, Layers } from "lucide-react";

const SOURCES = ["invoices", "customers", "expenses", "products"] as const;
const FIELDS: Record<string, { text: string[]; numeric: string[] }> = {
  invoices:  { text: ["status", "currency"], numeric: ["total_amount", "subtotal", "tax_amount", "paid_amount", "outstanding_amount"] },
  customers: { text: ["country", "currency"], numeric: ["credit_limit"] },
  expenses:  { text: ["category", "currency", "status"], numeric: ["amount"] },
  products:  { text: ["category", "unit"], numeric: ["unit_price", "cost_price"] },
};
const AGG_FNS = ["sum", "avg", "count", "min", "max"] as const;
const OPS = ["=", "!=", ">", ">=", "<", "<="] as const;

interface Filter { field: string; op: string; value: string }
interface Aggregate { fn: string; field: string; alias: string }
interface ReportConfig {
  source: string;
  filters: Filter[];
  group_by: string[];
  aggregates: Aggregate[];
  sort_by: string;
  sort_dir: "asc" | "desc";
}
interface SavedReport { id: string; name: string; description?: string; source: string; last_run_at?: string; last_run_row_count?: number; updated_at: string }
interface RunResult { columns: string[]; rows: Record<string, unknown>[]; total: number }

const defaultConfig = (source = "invoices"): ReportConfig => ({
  source,
  filters: [],
  group_by: ["status"],
  aggregates: [{ fn: "sum", field: "total_amount", alias: "revenue" }, { fn: "count", field: "*", alias: "count" }],
  sort_by: "revenue",
  sort_dir: "desc",
});

export default function ReportBuilderPage() {
  const apiBase = process.env.NEXT_PUBLIC_API_URL!;
  const [saved, setSaved] = useState<SavedReport[]>([]);
  const [config, setConfig] = useState<ReportConfig>(defaultConfig());
  const [result, setResult] = useState<RunResult | null>(null);
  const [running, setRunning] = useState(false);
  const [saveName, setSaveName] = useState("");
  const [showSave, setShowSave] = useState(false);

  const f = (url: string, opts?: RequestInit) =>
    fetch(`${apiBase}${url}`, { credentials: "include", ...opts });

  useEffect(() => {
    f("/api/bi/reports").then(r => r.ok ? r.json() : { reports: [] }).then(d => setSaved(d.reports));
  }, []);

  const fieldOptions = FIELDS[config.source] || { text: [], numeric: [] };
  const allFields = [...fieldOptions.text, ...fieldOptions.numeric];

  async function preview() {
    setRunning(true);
    try {
      const res = await f("/api/bi/reports/preview", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name: "preview", config }),
      });
      if (res.ok) setResult(await res.json());
      else { const e = await res.json(); toast.error(e.detail || "Error"); }
    } finally { setRunning(false); }
  }

  async function saveReport() {
    if (!saveName.trim()) { toast.error("Enter a name"); return; }
    const res = await f("/api/bi/reports", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name: saveName, config }),
    });
    if (res.ok) {
      toast.success("Report saved");
      setShowSave(false);
      setSaveName("");
      f("/api/bi/reports").then(r => r.ok ? r.json() : { reports: [] }).then(d => setSaved(d.reports));
    } else toast.error("Save failed");
  }

  async function runSaved(id: string) {
    setRunning(true);
    try {
      const res = await f(`/api/bi/reports/${id}/run`, { method: "POST" });
      if (res.ok) setResult(await res.json());
      else toast.error("Run failed");
    } finally { setRunning(false); }
  }

  async function deleteSaved(id: string) {
    await f(`/api/bi/reports/${id}`, { method: "DELETE" });
    setSaved(r => r.filter(x => x.id !== id));
    toast.success("Deleted");
  }

  function addFilter() {
    setConfig(c => ({ ...c, filters: [...c.filters, { field: allFields[0] || "", op: "=", value: "" }] }));
  }
  function removeFilter(i: number) {
    setConfig(c => ({ ...c, filters: c.filters.filter((_, idx) => idx !== i) }));
  }
  function updateFilter(i: number, patch: Partial<Filter>) {
    setConfig(c => ({ ...c, filters: c.filters.map((f, idx) => idx === i ? { ...f, ...patch } : f) }));
  }

  function toggleGroupBy(field: string) {
    setConfig(c => ({
      ...c,
      group_by: c.group_by.includes(field)
        ? c.group_by.filter(f => f !== field)
        : [...c.group_by, field],
    }));
  }

  function addAggregate() {
    setConfig(c => ({
      ...c,
      aggregates: [...c.aggregates, { fn: "sum", field: fieldOptions.numeric[0] || "amount", alias: "value" }],
    }));
  }
  function removeAggregate(i: number) {
    setConfig(c => ({ ...c, aggregates: c.aggregates.filter((_, idx) => idx !== i) }));
  }
  function updateAggregate(i: number, patch: Partial<Aggregate>) {
    setConfig(c => ({ ...c, aggregates: c.aggregates.map((a, idx) => idx === i ? { ...a, ...patch } : a) }));
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-gray-900">Custom Report Builder</h1>
          <p className="mt-1 text-sm text-gray-500">Filter, group, and aggregate any data without engineering.</p>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Builder panel */}
        <div className="lg:col-span-2 space-y-4">
          {/* Source */}
          <div className="rounded-xl border border-gray-200 bg-white p-4 space-y-3">
            <p className="text-sm font-semibold text-gray-700">1. Data Source</p>
            <div className="flex gap-2 flex-wrap">
              {SOURCES.map(s => (
                <button key={s} onClick={() => setConfig(defaultConfig(s))}
                  className={`px-3 py-1.5 rounded-lg text-sm font-medium capitalize transition-all ${
                    config.source === s ? "bg-blue-500 text-white" : "bg-gray-100 text-gray-700 hover:bg-gray-200"
                  }`}>{s}</button>
              ))}
            </div>
          </div>

          {/* Filters */}
          <div className="rounded-xl border border-gray-200 bg-white p-4 space-y-3">
            <div className="flex items-center justify-between">
              <p className="text-sm font-semibold text-gray-700 flex items-center gap-1.5"><Filter className="h-3.5 w-3.5" /> Filters</p>
              <button onClick={addFilter} className="btn-secondary text-xs flex items-center gap-1"><Plus className="h-3 w-3" /> Add</button>
            </div>
            {config.filters.length === 0 && <p className="text-xs text-gray-400">No filters — returning all rows.</p>}
            {config.filters.map((fil, i) => (
              <div key={i} className="flex gap-2 items-center">
                <select className="input text-sm" value={fil.field} onChange={e => updateFilter(i, { field: e.target.value })}>
                  {allFields.map(f => <option key={f} value={f}>{f}</option>)}
                </select>
                <select className="input text-sm w-20" value={fil.op} onChange={e => updateFilter(i, { op: e.target.value })}>
                  {OPS.map(op => <option key={op} value={op}>{op}</option>)}
                </select>
                <input className="input text-sm flex-1" value={fil.value} onChange={e => updateFilter(i, { value: e.target.value })} placeholder="Value" />
                <button onClick={() => removeFilter(i)} className="text-gray-400 hover:text-red-500"><Trash2 className="h-3.5 w-3.5" /></button>
              </div>
            ))}
          </div>

          {/* Group by */}
          <div className="rounded-xl border border-gray-200 bg-white p-4 space-y-3">
            <p className="text-sm font-semibold text-gray-700 flex items-center gap-1.5">
              <Layers className="h-3.5 w-3.5" /> Group By
            </p>
            <div className="flex flex-wrap gap-2">
              {fieldOptions.text.map(f => (
                <button key={f} onClick={() => toggleGroupBy(f)}
                  className={`px-2.5 py-1 rounded-lg text-xs font-medium transition-all ${
                    config.group_by.includes(f) ? "bg-blue-500 text-white" : "bg-gray-100 text-gray-700 hover:bg-gray-200"
                  }`}>{f}</button>
              ))}
            </div>
          </div>

          {/* Aggregates */}
          <div className="rounded-xl border border-gray-200 bg-white p-4 space-y-3">
            <div className="flex items-center justify-between">
              <p className="text-sm font-semibold text-gray-700 flex items-center gap-1.5"><Table2 className="h-3.5 w-3.5" /> Aggregates</p>
              <button onClick={addAggregate} className="btn-secondary text-xs flex items-center gap-1"><Plus className="h-3 w-3" /> Add</button>
            </div>
            {config.aggregates.map((agg, i) => (
              <div key={i} className="flex gap-2 items-center">
                <select className="input text-sm w-24" value={agg.fn} onChange={e => updateAggregate(i, { fn: e.target.value })}>
                  {AGG_FNS.map(fn => <option key={fn} value={fn}>{fn.toUpperCase()}</option>)}
                </select>
                <select className="input text-sm" value={agg.field} onChange={e => updateAggregate(i, { field: e.target.value })}>
                  {agg.fn === "count" && <option value="*">* (all rows)</option>}
                  {fieldOptions.numeric.map(f => <option key={f} value={f}>{f}</option>)}
                </select>
                <span className="text-gray-400 text-sm">AS</span>
                <input className="input text-sm w-28" value={agg.alias} onChange={e => updateAggregate(i, { alias: e.target.value })} />
                <button onClick={() => removeAggregate(i)} className="text-gray-400 hover:text-red-500"><Trash2 className="h-3.5 w-3.5" /></button>
              </div>
            ))}
          </div>

          {/* Sort */}
          <div className="rounded-xl border border-gray-200 bg-white p-4 flex gap-3 items-center">
            <p className="text-sm font-semibold text-gray-700 shrink-0">Sort by</p>
            <input className="input text-sm" value={config.sort_by} onChange={e => setConfig(c => ({ ...c, sort_by: e.target.value }))} placeholder="column alias" />
            <select className="input text-sm w-24" value={config.sort_dir} onChange={e => setConfig(c => ({ ...c, sort_dir: e.target.value as "asc" | "desc" }))}>
              <option value="desc">DESC</option>
              <option value="asc">ASC</option>
            </select>
          </div>

          {/* Actions */}
          <div className="flex gap-3">
            <button onClick={preview} disabled={running} className="btn-primary flex items-center gap-1.5">
              <Play className="h-3.5 w-3.5" /> {running ? "Running…" : "Run Preview"}
            </button>
            <button onClick={() => setShowSave(true)} className="btn-secondary">Save Report</button>
          </div>

          {showSave && (
            <div className="rounded-xl border border-blue-200 bg-blue-50 p-3 flex gap-2">
              <input className="input flex-1 text-sm" placeholder="Report name" value={saveName} onChange={e => setSaveName(e.target.value)} autoFocus />
              <button onClick={saveReport} className="btn-primary text-sm">Save</button>
              <button onClick={() => setShowSave(false)} className="btn-secondary text-sm">Cancel</button>
            </div>
          )}

          {/* Results */}
          {result && (
            <div className="rounded-xl border border-gray-200 bg-white overflow-hidden">
              <div className="px-4 py-2 bg-gray-50 border-b border-gray-200 flex items-center justify-between">
                <span className="text-xs font-medium text-gray-600">{result.total} rows</span>
              </div>
              <div className="overflow-x-auto">
                <table className="w-full text-xs">
                  <thead className="bg-gray-50">
                    <tr>{result.columns.map(c => <th key={c} className="text-left px-3 py-2 font-medium text-gray-500 capitalize">{c}</th>)}</tr>
                  </thead>
                  <tbody className="divide-y divide-gray-100">
                    {result.rows.map((row, i) => (
                      <tr key={i} className="hover:bg-gray-50">
                        {result.columns.map(c => <td key={c} className="px-3 py-2 text-gray-700">{String(row[c] ?? "")}</td>)}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </div>

        {/* Saved reports */}
        <div className="space-y-2">
          <p className="text-sm font-semibold text-gray-700">Saved Reports</p>
          {saved.length === 0 && <p className="text-xs text-gray-400">No saved reports yet.</p>}
          {saved.map(r => (
            <div key={r.id} className="rounded-xl border border-gray-200 bg-white p-3 space-y-2">
              <div className="flex items-start justify-between">
                <div>
                  <p className="text-sm font-medium text-gray-900">{r.name}</p>
                  <p className="text-[10px] text-gray-400 capitalize">{r.source} · {r.last_run_row_count != null ? `${r.last_run_row_count} rows` : "not run"}</p>
                </div>
                <button onClick={() => deleteSaved(r.id)} className="text-gray-300 hover:text-red-500"><Trash2 className="h-3.5 w-3.5" /></button>
              </div>
              <button onClick={() => runSaved(r.id)} className="btn-sm-outline w-full flex items-center justify-center gap-1">
                <Play className="h-3 w-3" /> Run <ChevronRight className="h-3 w-3" />
              </button>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
