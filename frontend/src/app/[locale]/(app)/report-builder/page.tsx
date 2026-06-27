"use client";

import { api } from "@/lib/api-client";
import { useEffect, useState } from "react";
import { useRouter, useParams } from "next/navigation";
import { toast } from "sonner";
import {
  FileBarChart2, Play, Save, Trash2, Plus, X, RefreshCw, ChevronDown,
  BarChart3, TrendingUp, PieChart, Download, Share2, Clock
} from "lucide-react";

interface EntityMeta {
  entity: string;
  fields: string[];
}

interface Filter {
  field: string;
  operator: string;
  value: string;
}

interface Aggregate {
  func: string;
  column: string;
}

interface SavedReportItem {
  id: string;
  name: string;
  entity: string;
  chart_type?: string;
  is_shared: boolean;
  created_at: string;
}

const OPERATORS = [
  { value: "eq", label: "equals" },
  { value: "ne", label: "not equals" },
  { value: "gt", label: "greater than" },
  { value: "gte", label: "≥" },
  { value: "lt", label: "less than" },
  { value: "lte", label: "≤" },
  { value: "like", label: "contains" },
];

const AGG_FUNCS = ["count", "sum", "avg", "min", "max"];

const CHART_TYPES = [
  { value: "bar", label: "Bar", icon: BarChart3 },
  { value: "line", label: "Line", icon: TrendingUp },
  { value: "pie", label: "Pie", icon: PieChart },
];

export default function ReportBuilderPage() {
  const router = useRouter();
  const params = useParams();
  const locale = params.locale as string;

  const [entities, setEntities] = useState<EntityMeta[]>([]);
  const [savedReports, setSavedReports] = useState<SavedReportItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [running, setRunning] = useState(false);
  const [saving, setSaving] = useState(false);

  // Report config state
  const [entity, setEntity] = useState("");
  const [filters, setFilters] = useState<Filter[]>([]);
  const [groupBy, setGroupBy] = useState<string[]>([]);
  const [aggregates, setAggregates] = useState<Aggregate[]>([]);
  const [sortBy, setSortBy] = useState("");
  const [sortDir, setSortDir] = useState<"asc" | "desc">("asc");
  const [chartType, setChartType] = useState<string | null>(null);
  const [reportName, setReportName] = useState("Untitled Report");
  const [isShared, setIsShared] = useState(false);

  // Results
  const [rows, setRows] = useState<Record<string, any>[]>([]);
  const [ran, setRan] = useState(false);
  const [activeReportId, setActiveReportId] = useState<string | null>(null);

  const availableFields = entities.find(e => e.entity === entity)?.fields ?? [];

  async function loadMeta() {
    try {
      const [entData, repData] = await Promise.all([
        api.get("/api/reports-builder/entities"),
        api.get("/api/reports-builder"),
      ]);
      setEntities(entData.entities ?? []);
      setSavedReports(repData.items ?? repData);
    } catch (err: any) {
      if (err?.status === 401) router.push(`/${locale}/auth/login`);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { loadMeta(); }, []);

  // When entity changes, reset filters/groupBy/aggregates
  function changeEntity(newEntity: string) {
    setEntity(newEntity);
    setFilters([]);
    setGroupBy([]);
    setAggregates([]);
    setSortBy("");
    setRows([]);
    setRan(false);
    setActiveReportId(null);
  }

  function addFilter() {
    if (!availableFields.length) return;
    setFilters(prev => [...prev, { field: availableFields[0], operator: "eq", value: "" }]);
  }

  function updateFilter(i: number, key: keyof Filter, value: string) {
    setFilters(prev => prev.map((f, j) => j === i ? { ...f, [key]: value } : f));
  }

  function removeFilter(i: number) {
    setFilters(prev => prev.filter((_, j) => j !== i));
  }

  function toggleGroupBy(field: string) {
    setGroupBy(prev => prev.includes(field) ? prev.filter(f => f !== field) : [...prev, field]);
  }

  function addAggregate() {
    if (!availableFields.length) return;
    setAggregates(prev => [...prev, { func: "count", column: availableFields[0] }]);
  }

  function updateAggregate(i: number, key: keyof Aggregate, value: string) {
    setAggregates(prev => prev.map((a, j) => j === i ? { ...a, [key]: value } : a));
  }

  function removeAggregate(i: number) {
    setAggregates(prev => prev.filter((_, j) => j !== i));
  }

  async function runReport() {
    if (!entity) {
      toast.error("Choose an entity first");
      return;
    }
    setRunning(true);
    try {
      if (activeReportId) {
        // Run saved report
        const data = await api.post(`/api/reports-builder/${activeReportId}/run`, {});
        setRows(data.rows ?? []);
      } else {
        // Save-then-run
        const created = await api.post("/api/reports-builder", {
          name: reportName,
          entity, filters, group_by: groupBy, aggregates,
          columns: [], sort_by: sortBy || undefined,
          sort_dir: sortDir, chart_type: chartType,
          is_shared: isShared,
        });
        const data = await api.post(`/api/reports-builder/${created.id}/run`, {});
        setRows(data.rows ?? []);
        setActiveReportId(created.id);
        setSavedReports(prev => [...prev, { id: created.id, name: reportName, entity, chart_type: chartType ?? undefined, is_shared: isShared, created_at: new Date().toISOString() }]);
        toast.success("Report saved & run");
      }
      setRan(true);
    } catch {
      toast.error("Failed to run report");
    } finally {
      setRunning(false);
    }
  }

  async function saveReport() {
    if (!entity) { toast.error("Choose an entity first"); return; }
    setSaving(true);
    try {
      if (activeReportId) {
        await api.patch(`/api/reports-builder/${activeReportId}`, {
          name: reportName, filters, group_by: groupBy, aggregates,
          sort_by: sortBy || undefined, sort_dir: sortDir,
          chart_type: chartType, is_shared: isShared,
        });
        toast.success("Report saved");
      } else {
        const created = await api.post("/api/reports-builder", {
          name: reportName, entity, filters, group_by: groupBy, aggregates,
          columns: [], sort_by: sortBy || undefined, sort_dir: sortDir,
          chart_type: chartType, is_shared: isShared,
        });
        setActiveReportId(created.id);
        setSavedReports(prev => [...prev, { id: created.id, name: reportName, entity, chart_type: chartType ?? undefined, is_shared: isShared, created_at: new Date().toISOString() }]);
        toast.success("Report created");
      }
    } catch {
      toast.error("Failed to save");
    } finally {
      setSaving(false);
    }
  }

  function loadSavedReport(report: SavedReportItem) {
    setActiveReportId(report.id);
    setEntity(report.entity);
    setReportName(report.name);
    setChartType(report.chart_type ?? null);
    setIsShared(report.is_shared);
    setFilters([]);
    setGroupBy([]);
    setAggregates([]);
    setRows([]);
    setRan(false);
  }

  function exportCsv() {
    if (!rows.length) return;
    const cols = Object.keys(rows[0]);
    const csv = [cols.join(","), ...rows.map(r => cols.map(c => JSON.stringify(r[c] ?? "")).join(","))].join("\n");
    const blob = new Blob([csv], { type: "text/csv" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `${reportName}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  }

  const columns = rows.length > 0 ? Object.keys(rows[0]) : [];

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <RefreshCw className="h-6 w-6 animate-spin text-muted-foreground" />
      </div>
    );
  }

  return (
    <div className="flex h-full overflow-hidden">
      {/* Left sidebar: saved reports */}
      <div className="w-60 border-r flex flex-col bg-background flex-shrink-0">
        <div className="p-3 border-b">
          <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">Saved Reports</p>
        </div>
        <div className="flex-1 overflow-y-auto">
          {savedReports.length === 0 ? (
            <p className="text-xs text-muted-foreground p-3">No saved reports yet</p>
          ) : (
            savedReports.map(r => (
              <button
                key={r.id}
                onClick={() => loadSavedReport(r)}
                className={`w-full text-left px-3 py-2 text-sm hover:bg-muted/40 border-b transition-colors
                  ${activeReportId === r.id ? "bg-primary/5 text-primary font-medium" : ""}`}
              >
                <p className="truncate">{r.name}</p>
                <p className="text-xs text-muted-foreground">{r.entity}</p>
              </button>
            ))
          )}
        </div>
        <div className="p-3 border-t">
          <button
            className="w-full text-xs text-primary hover:underline text-left"
            onClick={() => {
              setActiveReportId(null);
              setEntity("");
              setFilters([]);
              setGroupBy([]);
              setAggregates([]);
              setRows([]);
              setRan(false);
              setReportName("Untitled Report");
            }}
          >
            + New Report
          </button>
        </div>
      </div>

      {/* Main builder */}
      <div className="flex-1 flex flex-col overflow-hidden">
        {/* Toolbar */}
        <div className="border-b px-4 py-3 flex items-center gap-3 bg-background">
          <FileBarChart2 className="h-5 w-5 text-primary" />
          <input
            className="text-sm font-medium bg-transparent border-none outline-none focus:ring-0 w-48"
            value={reportName}
            onChange={e => setReportName(e.target.value)}
          />
          <div className="ml-auto flex items-center gap-2">
            {/* Chart type toggle */}
            {CHART_TYPES.map(ct => {
              const Icon = ct.icon;
              return (
                <button
                  key={ct.value}
                  title={ct.label}
                  onClick={() => setChartType(chartType === ct.value ? null : ct.value)}
                  className={`p-1.5 rounded-lg ${chartType === ct.value ? "bg-primary text-primary-foreground" : "hover:bg-muted text-muted-foreground"}`}
                >
                  <Icon className="h-4 w-4" />
                </button>
              );
            })}
            <div className="w-px h-5 bg-border" />
            {ran && (
              <button className="btn-secondary text-xs flex items-center gap-1.5 h-8 px-3" onClick={exportCsv}>
                <Download className="h-3.5 w-3.5" /> CSV
              </button>
            )}
            <button className="btn-secondary text-xs flex items-center gap-1.5 h-8 px-3" onClick={saveReport} disabled={saving || !entity}>
              {saving ? <RefreshCw className="h-3.5 w-3.5 animate-spin" /> : <Save className="h-3.5 w-3.5" />}
              Save
            </button>
            <button className="btn-primary text-xs flex items-center gap-1.5 h-8 px-3" onClick={runReport} disabled={running || !entity}>
              {running ? <RefreshCw className="h-3.5 w-3.5 animate-spin" /> : <Play className="h-3.5 w-3.5" />}
              Run
            </button>
          </div>
        </div>

        <div className="flex-1 flex overflow-hidden">
          {/* Config panel */}
          <div className="w-72 border-r overflow-y-auto p-4 space-y-5 flex-shrink-0">
            {/* Entity */}
            <div>
              <label className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">Entity</label>
              <select className="input mt-1.5 w-full text-sm" value={entity} onChange={e => changeEntity(e.target.value)}>
                <option value="">— choose entity —</option>
                {entities.map(e => <option key={e.entity} value={e.entity}>{e.entity}</option>)}
              </select>
            </div>

            {entity && (
              <>
                {/* Filters */}
                <div>
                  <div className="flex items-center justify-between mb-2">
                    <label className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">Filters</label>
                    <button className="text-xs text-primary hover:underline" onClick={addFilter}>+ Add</button>
                  </div>
                  <div className="space-y-2">
                    {filters.map((f, i) => (
                      <div key={i} className="space-y-1 p-2 rounded-lg border bg-muted/30">
                        <div className="flex items-center gap-1">
                          <select className="input flex-1 text-xs py-0.5" value={f.field} onChange={e => updateFilter(i, "field", e.target.value)}>
                            {availableFields.map(field => <option key={field} value={field}>{field}</option>)}
                          </select>
                          <button onClick={() => removeFilter(i)} className="text-red-500"><X className="h-3 w-3" /></button>
                        </div>
                        <select className="input w-full text-xs py-0.5" value={f.operator} onChange={e => updateFilter(i, "operator", e.target.value)}>
                          {OPERATORS.map(op => <option key={op.value} value={op.value}>{op.label}</option>)}
                        </select>
                        <input className="input w-full text-xs py-0.5" placeholder="value" value={f.value} onChange={e => updateFilter(i, "value", e.target.value)} />
                      </div>
                    ))}
                  </div>
                </div>

                {/* Group by */}
                <div>
                  <label className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">Group By</label>
                  <div className="mt-1.5 flex flex-wrap gap-1.5">
                    {availableFields.map(field => (
                      <button
                        key={field}
                        onClick={() => toggleGroupBy(field)}
                        className={`text-xs px-2 py-0.5 rounded-full border transition-colors ${
                          groupBy.includes(field) ? "bg-primary text-primary-foreground border-primary" : "hover:bg-muted border-border"
                        }`}
                      >
                        {field}
                      </button>
                    ))}
                  </div>
                </div>

                {/* Aggregates */}
                <div>
                  <div className="flex items-center justify-between mb-2">
                    <label className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">Aggregates</label>
                    <button className="text-xs text-primary hover:underline" onClick={addAggregate}>+ Add</button>
                  </div>
                  <div className="space-y-1">
                    {aggregates.map((a, i) => (
                      <div key={i} className="flex items-center gap-1">
                        <select className="input flex-shrink-0 w-16 text-xs py-0.5" value={a.func} onChange={e => updateAggregate(i, "func", e.target.value)}>
                          {AGG_FUNCS.map(f => <option key={f} value={f}>{f}</option>)}
                        </select>
                        <select className="input flex-1 text-xs py-0.5" value={a.column} onChange={e => updateAggregate(i, "column", e.target.value)}>
                          {availableFields.map(field => <option key={field} value={field}>{field}</option>)}
                        </select>
                        <button onClick={() => removeAggregate(i)} className="text-red-500"><X className="h-3 w-3" /></button>
                      </div>
                    ))}
                  </div>
                </div>

                {/* Sort */}
                <div>
                  <label className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">Sort</label>
                  <div className="flex gap-2 mt-1.5">
                    <select className="input flex-1 text-xs py-0.5" value={sortBy} onChange={e => setSortBy(e.target.value)}>
                      <option value="">— none —</option>
                      {availableFields.map(f => <option key={f} value={f}>{f}</option>)}
                    </select>
                    <select className="input w-16 text-xs py-0.5" value={sortDir} onChange={e => setSortDir(e.target.value as "asc" | "desc")}>
                      <option value="asc">ASC</option>
                      <option value="desc">DESC</option>
                    </select>
                  </div>
                </div>
              </>
            )}
          </div>

          {/* Results area */}
          <div className="flex-1 overflow-auto p-4">
            {!ran ? (
              <div className="flex flex-col items-center justify-center h-full text-center">
                <FileBarChart2 className="h-12 w-12 text-muted-foreground mb-4" />
                {!entity ? (
                  <p className="text-muted-foreground">Select an entity to build your report</p>
                ) : (
                  <>
                    <p className="font-medium">Ready to run</p>
                    <p className="text-sm text-muted-foreground mt-1">Configure filters and click Run</p>
                    <button className="btn-primary mt-4 flex items-center gap-2" onClick={runReport} disabled={running}>
                      {running ? <RefreshCw className="h-4 w-4 animate-spin" /> : <Play className="h-4 w-4" />}
                      Run Report
                    </button>
                  </>
                )}
              </div>
            ) : rows.length === 0 ? (
              <div className="flex items-center justify-center h-48">
                <p className="text-muted-foreground">No results match your filters</p>
              </div>
            ) : (
              <div className="space-y-3">
                <div className="flex items-center justify-between">
                  <p className="text-sm text-muted-foreground">{rows.length} rows returned</p>
                  <button className="text-xs text-primary hover:underline flex items-center gap-1" onClick={exportCsv}>
                    <Download className="h-3 w-3" /> Export CSV
                  </button>
                </div>
                <div className="overflow-x-auto rounded-xl border">
                  <table className="w-full text-sm">
                    <thead className="bg-muted/50">
                      <tr>
                        {columns.map(col => (
                          <th key={col} className="text-left px-4 py-2 font-medium text-xs uppercase tracking-wide">{col}</th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {rows.slice(0, 500).map((row, i) => (
                        <tr key={i} className="border-t hover:bg-muted/30">
                          {columns.map(col => (
                            <td key={col} className="px-4 py-2 text-muted-foreground max-w-xs truncate">
                              {row[col] == null ? "—" : String(row[col])}
                            </td>
                          ))}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                  {rows.length > 500 && (
                    <p className="text-xs text-muted-foreground text-center py-2 border-t">
                      Showing first 500 of {rows.length} rows
                    </p>
                  )}
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
