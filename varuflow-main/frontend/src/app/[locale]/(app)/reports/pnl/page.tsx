"use client";
import { useEffect, useState, useCallback } from "react";
import { BarChart3, Download, FileText, TrendingUp, TrendingDown, Minus } from "lucide-react";
import { api } from "@/lib/api-client";
import { toast } from "sonner";

// ── Types ─────────────────────────────────────────────────────────────────────

interface PeriodSlice {
  from_date: string; to_date: string; label: string;
  revenue: number; cogs: number; gross_profit: number; gross_margin_pct: number;
  operating_expenses: number; staff_costs: number; ebitda: number; net_profit: number;
}
interface MonthPoint { month: string; revenue: number; expenses: number; profit: number; }
interface PnLData { current: PeriodSlice; previous: PeriodSlice | null; monthly_series: MonthPoint[]; }

type PeriodType = "month" | "quarter" | "year" | "custom";
const MONTHS = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"];
const CUR_YEAR = new Date().getFullYear();
const YEARS = Array.from({ length: 5 }, (_, i) => CUR_YEAR - i);

// ── Helpers ───────────────────────────────────────────────────────────────────

function fmt(n: number) {
  return n.toLocaleString("sv-SE", { minimumFractionDigits: 0, maximumFractionDigits: 0 });
}
function fmtK(n: number) {
  if (Math.abs(n) >= 1_000_000) return `${(n/1_000_000).toFixed(1)}M`;
  if (Math.abs(n) >= 1_000) return `${(n/1_000).toFixed(1)}k`;
  return String(Math.round(n));
}
function delta(cur: number, prev: number) {
  if (!prev) return null;
  return ((cur - prev) / Math.abs(prev)) * 100;
}
function DeltaBadge({ cur, prev }: { cur: number; prev: number | undefined }) {
  if (prev === undefined) return null;
  const d = delta(cur, prev);
  if (d === null) return null;
  const pos = cur >= prev;
  const Icon = Math.abs(d) < 0.05 ? Minus : pos ? TrendingUp : TrendingDown;
  return (
    <span className={`inline-flex items-center gap-0.5 text-xs font-medium ${pos ? "text-green-600" : "text-red-500"}`}>
      <Icon size={11} />
      {Math.abs(d).toFixed(1)}%
    </span>
  );
}

// ── Chart ─────────────────────────────────────────────────────────────────────

function MonthlyChart({ series }: { series: MonthPoint[] }) {
  const maxVal = Math.max(...series.flatMap(p => [p.revenue, p.expenses]), 1);
  return (
    <div className="space-y-1">
      <div className="flex items-end gap-1.5 h-40">
        {series.map((p) => {
          const revH = Math.max((p.revenue / maxVal) * 140, 2);
          const expH = Math.max((p.expenses / maxVal) * 140, 2);
          const profitPositive = p.profit >= 0;
          return (
            <div key={p.month} className="flex-1 flex items-end gap-0.5 group relative">
              {/* Tooltip */}
              <div className="absolute bottom-full left-1/2 -translate-x-1/2 mb-1 hidden group-hover:block z-10 bg-gray-900 text-white text-[10px] rounded px-2 py-1 whitespace-nowrap shadow">
                <div>{p.month}</div>
                <div className="text-blue-300">Rev {fmtK(p.revenue)}</div>
                <div className="text-red-300">Exp {fmtK(p.expenses)}</div>
                <div className={profitPositive ? "text-green-300" : "text-orange-300"}>
                  {profitPositive ? "+" : ""}{fmtK(p.profit)}
                </div>
              </div>
              <div className="flex-1 bg-blue-400 rounded-t" style={{ height: revH }} />
              <div className="flex-1 bg-red-300 rounded-t" style={{ height: expH }} />
            </div>
          );
        })}
      </div>
      <div className="flex gap-1.5">
        {series.map((p) => (
          <div key={p.month} className="flex-1 text-center text-[9px] text-gray-400">
            {p.month.slice(5)}
          </div>
        ))}
      </div>
      <div className="flex items-center gap-4 pt-1 text-xs text-gray-500">
        <span className="flex items-center gap-1.5"><span className="inline-block w-3 h-2.5 rounded-sm bg-blue-400" />Revenue</span>
        <span className="flex items-center gap-1.5"><span className="inline-block w-3 h-2.5 rounded-sm bg-red-300" />Expenses</span>
      </div>
    </div>
  );
}

// ── KPI Card ──────────────────────────────────────────────────────────────────

function KpiCard({ label, value, prev, sub, highlight }: {
  label: string; value: number; prev?: number; sub?: string; highlight?: "green" | "red" | "neutral";
}) {
  const color = highlight === "green" ? "text-green-600" : highlight === "red" ? "text-red-500" : "text-[#1a2332]";
  return (
    <div className="bg-white border rounded-xl p-4 space-y-1">
      <p className="text-xs font-medium text-gray-400 uppercase tracking-wide">{label}</p>
      <p className={`text-2xl font-bold ${color}`}>{fmt(value)}</p>
      {sub && <p className="text-xs text-gray-400">{sub}</p>}
      {prev !== undefined && <DeltaBadge cur={value} prev={prev} />}
    </div>
  );
}

// ── Waterfall row ─────────────────────────────────────────────────────────────

function WfRow({ label, value, indent, bold, separator, color }: {
  label: string; value: number; indent?: boolean; bold?: boolean; separator?: boolean; color?: string;
}) {
  return (
    <tr className={separator ? "border-t-2 border-[#1a2332]" : ""}>
      <td className={`py-2 text-sm ${bold ? "font-semibold" : "text-gray-600"} ${indent ? "pl-6" : ""}`}>{label}</td>
      <td className={`py-2 text-right font-mono text-sm ${bold ? "font-semibold" : ""} ${color || (value < 0 ? "text-red-500" : "")}`}>
        {value < 0 ? `(${fmt(Math.abs(value))})` : fmt(value)} SEK
      </td>
    </tr>
  );
}

// ── Page ──────────────────────────────────────────────────────────────────────

export default function PnLPage() {
  const [data, setData] = useState<PnLData | null>(null);
  const [loading, setLoading] = useState(true);
  const [periodType, setPeriodType] = useState<PeriodType>("month");
  const [year, setYear] = useState(CUR_YEAR);
  const [month, setMonth] = useState(new Date().getMonth() + 1);
  const [quarter, setQuarter] = useState(Math.ceil((new Date().getMonth() + 1) / 3));
  const [fromDate, setFromDate] = useState("");
  const [toDate, setToDate] = useState("");

  const buildParams = useCallback(() => {
    const p = new URLSearchParams({ period: periodType, year: String(year) });
    if (periodType === "month") p.set("month", String(month));
    if (periodType === "quarter") p.set("quarter", String(quarter));
    if (periodType === "custom") { p.set("from_date", fromDate); p.set("to_date", toDate); }
    return p.toString();
  }, [periodType, year, month, quarter, fromDate, toDate]);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const d = await api.get<PnLData>(`/api/reports/pnl?${buildParams()}`);
      setData(d);
    } catch { toast.error("Failed to load P&L data"); }
    finally { setLoading(false); }
  }, [buildParams]);

  useEffect(() => { load(); }, [load]);

  function exportPdf() {
    window.open(api.downloadUrl(`/api/reports/pnl/pdf?${buildParams()}`), "_blank");
  }
  function exportCsv() {
    window.open(api.downloadUrl(`/api/reports/pnl/csv?${buildParams()}`), "_blank");
  }

  const cur = data?.current;
  const prev = data?.previous;

  return (
    <div className="p-6 space-y-6 max-w-5xl">
      {/* Header */}
      <div className="flex items-start justify-between gap-4 flex-wrap">
        <div className="flex items-center gap-3">
          <BarChart3 size={22} className="text-[#1a2332]" />
          <div>
            <h1 className="text-xl font-bold text-[#1a2332]">Profit &amp; Loss</h1>
            {cur && <p className="text-sm text-gray-400 mt-0.5">{cur.label}</p>}
          </div>
        </div>
        <div className="flex gap-2">
          <button onClick={exportCsv} className="flex items-center gap-1.5 px-3 py-1.5 border rounded text-sm hover:bg-gray-50">
            <FileText size={13} /> CSV
          </button>
          <button onClick={exportPdf} className="flex items-center gap-1.5 px-3 py-1.5 border rounded text-sm hover:bg-gray-50">
            <Download size={13} /> PDF
          </button>
        </div>
      </div>

      {/* Period selector */}
      <div className="bg-white border rounded-xl p-4 space-y-3">
        <div className="flex gap-1">
          {(["month","quarter","year","custom"] as PeriodType[]).map((t) => (
            <button key={t} onClick={() => setPeriodType(t)}
              className={`px-3 py-1.5 rounded text-sm font-medium capitalize transition-colors ${periodType === t ? "bg-[#1a2332] text-white" : "text-gray-600 hover:bg-gray-100"}`}>
              {t}
            </button>
          ))}
        </div>

        <div className="flex flex-wrap gap-3 items-end">
          {periodType !== "custom" && (
            <div>
              <label className="block text-xs text-gray-400 mb-1">Year</label>
              <select value={year} onChange={e => setYear(Number(e.target.value))}
                className="border rounded px-2 py-1.5 text-sm focus:outline-none">
                {YEARS.map(y => <option key={y} value={y}>{y}</option>)}
              </select>
            </div>
          )}
          {periodType === "month" && (
            <div>
              <label className="block text-xs text-gray-400 mb-1">Month</label>
              <select value={month} onChange={e => setMonth(Number(e.target.value))}
                className="border rounded px-2 py-1.5 text-sm focus:outline-none">
                {MONTHS.map((m, i) => <option key={i+1} value={i+1}>{m}</option>)}
              </select>
            </div>
          )}
          {periodType === "quarter" && (
            <div>
              <label className="block text-xs text-gray-400 mb-1">Quarter</label>
              <select value={quarter} onChange={e => setQuarter(Number(e.target.value))}
                className="border rounded px-2 py-1.5 text-sm focus:outline-none">
                {[1,2,3,4].map(q => <option key={q} value={q}>Q{q}</option>)}
              </select>
            </div>
          )}
          {periodType === "custom" && (
            <>
              <div>
                <label className="block text-xs text-gray-400 mb-1">From</label>
                <input type="date" value={fromDate} onChange={e => setFromDate(e.target.value)}
                  className="border rounded px-2 py-1.5 text-sm focus:outline-none" />
              </div>
              <div>
                <label className="block text-xs text-gray-400 mb-1">To</label>
                <input type="date" value={toDate} onChange={e => setToDate(e.target.value)}
                  className="border rounded px-2 py-1.5 text-sm focus:outline-none" />
              </div>
            </>
          )}
          <button onClick={load} className="px-4 py-1.5 bg-[#1a2332] text-white rounded text-sm hover:opacity-90">
            {loading ? "Loading…" : "Apply"}
          </button>
        </div>
      </div>

      {loading && !data && (
        <div className="grid grid-cols-3 gap-4">
          {[1,2,3,4,5,6].map(i => <div key={i} className="h-24 rounded-xl bg-gray-100 animate-pulse" />)}
        </div>
      )}

      {cur && (
        <>
          {/* KPI grid */}
          <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
            <KpiCard label="Revenue" value={cur.revenue} prev={prev?.revenue} />
            <KpiCard label="Cost of Goods Sold" value={cur.cogs} prev={prev?.cogs} />
            <KpiCard
              label="Gross Profit"
              value={cur.gross_profit}
              prev={prev?.gross_profit}
              sub={`${cur.gross_margin_pct}% margin`}
              highlight={cur.gross_profit >= 0 ? "green" : "red"}
            />
            <KpiCard label="Operating Expenses" value={cur.operating_expenses} prev={prev?.operating_expenses} />
            <KpiCard label="Staff Costs" value={cur.staff_costs} prev={prev?.staff_costs} />
            <KpiCard
              label="EBITDA / Net Profit"
              value={cur.net_profit}
              prev={prev?.net_profit}
              highlight={cur.net_profit >= 0 ? "green" : "red"}
            />
          </div>

          {/* Comparison banner */}
          {prev && (
            <div className="bg-gray-50 border rounded-xl p-4">
              <p className="text-xs font-semibold text-gray-400 uppercase tracking-wide mb-3">
                vs previous period ({prev.label})
              </p>
              <div className="grid grid-cols-3 md:grid-cols-6 gap-4 text-center text-sm">
                {[
                  { l: "Revenue", c: cur.revenue, p: prev.revenue },
                  { l: "COGS", c: cur.cogs, p: prev.cogs },
                  { l: "Gross Profit", c: cur.gross_profit, p: prev.gross_profit },
                  { l: "Op Exp", c: cur.operating_expenses, p: prev.operating_expenses },
                  { l: "Staff", c: cur.staff_costs, p: prev.staff_costs },
                  { l: "Net Profit", c: cur.net_profit, p: prev.net_profit },
                ].map(({ l, c, p }) => {
                  const d = delta(c, p);
                  const pos = c >= p;
                  return (
                    <div key={l}>
                      <p className="text-xs text-gray-400">{l}</p>
                      <p className="font-semibold">{fmtK(c)}</p>
                      <p className={`text-xs ${pos ? "text-green-600" : "text-red-500"}`}>
                        {d !== null ? `${pos ? "+" : ""}${d.toFixed(1)}%` : "—"}
                      </p>
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          {/* P&L detail table */}
          <div className="bg-white border rounded-xl p-5">
            <p className="text-sm font-semibold text-gray-700 mb-4">Statement Detail</p>
            <table className="w-full">
              <tbody>
                <WfRow label="Revenue" value={cur.revenue} bold />
                <WfRow label="Cost of Goods Sold (COGS)" value={-cur.cogs} indent />
                <WfRow label="Gross Profit" value={cur.gross_profit} bold separator
                  color={cur.gross_profit >= 0 ? "text-green-600" : "text-red-500"} />
                <WfRow label={`Gross Margin: ${cur.gross_margin_pct}%`} value={0} indent
                  color="text-gray-400" />
                <WfRow label="Operating Expenses" value={-cur.operating_expenses} indent />
                <WfRow label="Staff Costs (Employer)" value={-cur.staff_costs} indent />
                <WfRow label="EBITDA" value={cur.ebitda} bold separator
                  color={cur.ebitda >= 0 ? "text-green-600" : "text-red-500"} />
                <WfRow label="Net Profit" value={cur.net_profit} bold separator
                  color={cur.net_profit >= 0 ? "text-green-600" : "text-red-500"} />
              </tbody>
            </table>
          </div>

          {/* 12-month chart */}
          {data.monthly_series.length > 0 && (
            <div className="bg-white border rounded-xl p-5">
              <p className="text-sm font-semibold text-gray-700 mb-4">Revenue vs Expenses — trailing 12 months</p>
              <MonthlyChart series={data.monthly_series} />
            </div>
          )}
        </>
      )}
    </div>
  );
}
