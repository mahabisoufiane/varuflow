"use client";

import { api } from "@/lib/api-client";
import { useEffect, useState } from "react";
import { useRouter, useParams } from "next/navigation";
import { toast } from "sonner";
import { RefreshCw, Download, Star, TrendingUp } from "lucide-react";
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer
} from "recharts";

interface CohortMatrix {
  cohorts: string[];
  columns: number[];
  matrix: Record<string, Record<number, number>>;
  cohort_sizes: Record<string, number>;
  avg_ltv_curve: Array<{ month_offset: number; value: number }>;
  best_cohort: string | null;
  best_cohort_total: number;
}

interface LtvSummary {
  ltv_3m: number;
  ltv_6m: number;
  ltv_12m: number;
  best_cohort: string | null;
}

const METRICS = [
  { value: "revenue", label: "Revenue" },
  { value: "invoice_count", label: "Invoice Count" },
  { value: "retention_rate", label: "Retention Rate" },
];

const MONTH_OPTIONS = [6, 12, 18, 24];

function cellColor(value: number, max: number, metric: string): string {
  if (max === 0 || value === 0) return "bg-muted/20";
  const ratio = Math.min(value / max, 1);
  if (metric === "retention_rate") {
    if (ratio > 0.75) return "bg-green-600 text-white";
    if (ratio > 0.5) return "bg-green-400 text-white";
    if (ratio > 0.25) return "bg-green-200 text-green-900";
    return "bg-green-50 text-green-700";
  }
  if (ratio > 0.75) return "bg-blue-600 text-white";
  if (ratio > 0.5) return "bg-blue-400 text-white";
  if (ratio > 0.25) return "bg-blue-200 text-blue-900";
  return "bg-blue-50 text-blue-700";
}

function fmt(value: number, metric: string): string {
  if (metric === "retention_rate") return `${(value * 100).toFixed(0)}%`;
  if (metric === "revenue") return value.toLocaleString("sv-SE", { maximumFractionDigits: 0 });
  return String(Math.round(value));
}

export default function CohortAnalysisPage() {
  const router = useRouter();
  const params = useParams();
  const locale = params.locale as string;

  const [metric, setMetric] = useState("revenue");
  const [months, setMonths] = useState(12);
  const [data, setData] = useState<CohortMatrix | null>(null);
  const [ltv, setLtv] = useState<LtvSummary | null>(null);
  const [loading, setLoading] = useState(true);

  async function load() {
    setLoading(true);
    try {
      const [cData, lData] = await Promise.all([
        api.get(`/api/cohort-analysis?metric=${metric}&months=${months}`),
        api.get("/api/cohort-analysis/ltv-summary"),
      ]);
      setData(cData);
      setLtv(lData);
    } catch (err: any) {
      if (err?.status === 401) router.push(`/${locale}/auth/login`);
      else toast.error("Failed to load cohort data");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { load(); }, [metric, months]);

  function exportCsv() {
    if (!data) return;
    const header = ["Cohort", "Size", ...data.columns.map(c => `M+${c}`)].join(",");
    const rows = data.cohorts.map(cohort => {
      const size = data.cohort_sizes[cohort] ?? 0;
      const cells = data.columns.map(col => data.matrix[cohort]?.[col] ?? "");
      return [cohort, size, ...cells].join(",");
    });
    const csv = [header, ...rows].join("\n");
    const blob = new Blob([csv], { type: "text/csv" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `cohort-${metric}-${new Date().toISOString().slice(0, 10)}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  }

  // Find max value for color scaling (exclude M+0)
  const maxVal = data
    ? Math.max(...data.cohorts.flatMap(c => data.columns.filter(col => col > 0).map(col => data.matrix[c]?.[col] ?? 0)))
    : 0;

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Cohort Analysis</h1>
          <p className="text-sm text-muted-foreground mt-1">
            Customer acquisition cohorts — track retention, revenue, and lifetime value over time
          </p>
        </div>
        <div className="flex items-center gap-3">
          <div className="flex gap-1 rounded-xl border p-1 bg-background">
            {METRICS.map(m => (
              <button
                key={m.value}
                onClick={() => setMetric(m.value)}
                className={`px-3 py-1 text-sm rounded-lg transition-colors font-medium
                  ${metric === m.value ? "bg-primary text-primary-foreground" : "hover:bg-muted text-muted-foreground"}`}
              >
                {m.label}
              </button>
            ))}
          </div>
          <select
            className="input text-sm py-1.5 h-9 w-32"
            value={months}
            onChange={e => setMonths(Number(e.target.value))}
          >
            {MONTH_OPTIONS.map(m => (
              <option key={m} value={m}>{m} months</option>
            ))}
          </select>
          <button className="btn-secondary flex items-center gap-2 text-sm" onClick={exportCsv} disabled={!data}>
            <Download className="h-4 w-4" /> CSV
          </button>
          {loading && <RefreshCw className="h-4 w-4 animate-spin text-muted-foreground" />}
        </div>
      </div>

      {/* LTV summary cards */}
      {ltv && (
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
          <div className="rounded-2xl border bg-card p-4">
            <p className="text-xs text-muted-foreground">Avg LTV — 3 Month</p>
            <p className="text-2xl font-bold mt-1">{ltv.ltv_3m.toLocaleString("sv-SE", { maximumFractionDigits: 0 })}</p>
          </div>
          <div className="rounded-2xl border bg-card p-4">
            <p className="text-xs text-muted-foreground">Avg LTV — 6 Month</p>
            <p className="text-2xl font-bold mt-1">{ltv.ltv_6m.toLocaleString("sv-SE", { maximumFractionDigits: 0 })}</p>
          </div>
          <div className="rounded-2xl border bg-card p-4">
            <p className="text-xs text-muted-foreground">Avg LTV — 12 Month</p>
            <p className="text-2xl font-bold mt-1">{ltv.ltv_12m.toLocaleString("sv-SE", { maximumFractionDigits: 0 })}</p>
          </div>
          {ltv.best_cohort && (
            <div className="rounded-2xl border bg-card p-4 flex items-start gap-3">
              <Star className="h-5 w-5 text-amber-500 flex-shrink-0 mt-0.5" />
              <div>
                <p className="text-xs text-muted-foreground">Best Cohort</p>
                <p className="text-lg font-bold mt-0.5">{ltv.best_cohort}</p>
              </div>
            </div>
          )}
        </div>
      )}

      {loading ? (
        <div className="flex justify-center py-16">
          <RefreshCw className="h-6 w-6 animate-spin text-muted-foreground" />
        </div>
      ) : !data || data.cohorts.length === 0 ? (
        <div className="rounded-2xl border bg-card flex flex-col items-center justify-center py-20 text-center">
          <TrendingUp className="h-12 w-12 text-muted-foreground mb-4" />
          <p className="font-medium">No cohort data yet</p>
          <p className="text-sm text-muted-foreground mt-1">Data appears once customers have invoices across multiple months</p>
        </div>
      ) : (
        <>
          {/* Cohort heatmap grid */}
          <div className="rounded-2xl border bg-card p-5 overflow-x-auto">
            <h3 className="font-semibold mb-4">
              Cohort Heatmap — {METRICS.find(m => m.value === metric)?.label}
            </h3>
            <table className="text-xs border-collapse w-max min-w-full">
              <thead>
                <tr>
                  <th className="text-left p-2 text-muted-foreground font-medium whitespace-nowrap pr-4">Cohort</th>
                  <th className="p-2 text-muted-foreground font-medium text-center whitespace-nowrap">Size</th>
                  {data.columns.map(col => (
                    <th key={col} className="p-2 text-muted-foreground font-medium text-center whitespace-nowrap">
                      M+{col}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {data.cohorts.map(cohort => (
                  <tr key={cohort} className={data.best_cohort === cohort ? "ring-1 ring-amber-400 ring-inset" : ""}>
                    <td className="p-2 font-medium whitespace-nowrap pr-4 flex items-center gap-1.5">
                      {data.best_cohort === cohort && <Star className="h-3 w-3 text-amber-500 flex-shrink-0" />}
                      {cohort}
                    </td>
                    <td className="p-2 text-center text-muted-foreground">
                      {data.cohort_sizes[cohort] ?? 0}
                    </td>
                    {data.columns.map(col => {
                      const val = data.matrix[cohort]?.[col];
                      const color = val != null ? cellColor(val, maxVal, metric) : "bg-transparent";
                      return (
                        <td key={col} className={`p-0`}>
                          <div className={`m-0.5 rounded px-2 py-1 text-center font-mono tabular-nums ${color}`}
                            title={val != null ? fmt(val, metric) : "–"}>
                            {val != null ? fmt(val, metric) : "–"}
                          </div>
                        </td>
                      );
                    })}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* LTV Curve */}
          {data.avg_ltv_curve.length > 0 && (
            <div className="rounded-2xl border bg-card p-5">
              <h3 className="font-semibold mb-4">Average LTV Curve — Cumulative by Month Offset</h3>
              <ResponsiveContainer width="100%" height={220}>
                <BarChart data={data.avg_ltv_curve} margin={{ top: 5, right: 20, left: 0, bottom: 5 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                  <XAxis dataKey="month_offset" tickFormatter={v => `M+${v}`} tick={{ fontSize: 11 }} />
                  <YAxis
                    tick={{ fontSize: 11 }}
                    tickFormatter={v =>
                      metric === "retention_rate"
                        ? `${(v * 100).toFixed(0)}%`
                        : v.toLocaleString("sv-SE", { maximumFractionDigits: 0 })
                    }
                  />
                  <Tooltip
                    formatter={(v) =>
                      metric === "retention_rate"
                        ? `${((v as number) * 100).toFixed(1)}%`
                        : (v as number).toLocaleString("sv-SE", { maximumFractionDigits: 0 })
                    }
                    labelFormatter={l => `Month +${l}`}
                  />
                  <Bar dataKey="value" name={METRICS.find(m => m.value === metric)?.label} fill="#3b82f6" radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          )}
        </>
      )}
    </div>
  );
}
