"use client";
import { useEffect, useState, useCallback } from "react";
import { Scale, Download, AlertCircle, CheckCircle2 } from "lucide-react";
import { api } from "@/lib/api-client";
import { toast } from "sonner";

// ── Types ─────────────────────────────────────────────────────────────────────

interface LineItem { label: string; amount: string; note: string | null; }
interface Section  { title: string; lines: LineItem[]; total: string; }

interface BalanceSheetData {
  as_of: string;
  generated_at: string;
  assets: Section;
  liabilities: Section;
  equity: Section;
  total_assets: string;
  total_liabilities_and_equity: string;
  balanced: boolean;
  disclaimer: string;
}

// ── Helpers ───────────────────────────────────────────────────────────────────

function fmt(s: string | number) {
  const n = typeof s === "string" ? parseFloat(s) : s;
  if (isNaN(n)) return "—";
  const abs = Math.abs(n);
  const str = abs.toLocaleString("sv-SE", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  return n < 0 ? `(${str})` : str;
}

function numOf(s: string) { return parseFloat(s) || 0; }

// ── Section Table ─────────────────────────────────────────────────────────────

function SectionTable({
  section,
  totalLabel,
  totalColor,
}: {
  section: Section;
  totalLabel: string;
  totalColor: string;
}) {
  return (
    <div>
      <div className="flex items-center justify-between px-4 py-2.5 bg-[#f8f9fb] border-b">
        <span className="text-sm font-bold text-[#1a2332] uppercase tracking-wide">{section.title}</span>
        <span className="text-xs text-gray-400 font-medium">SEK</span>
      </div>
      {section.lines.map((line, i) => {
        const n = numOf(line.amount);
        const isSubtraction = line.label.startsWith("Less:");
        return (
          <div
            key={i}
            className={`flex items-start justify-between px-4 py-2 border-b last:border-b-0 ${isSubtraction ? "bg-red-50/40" : ""}`}
          >
            <div className="flex-1 min-w-0">
              <p className={`text-sm ${isSubtraction ? "text-gray-400 italic" : "text-gray-700"}`}>{line.label}</p>
              {line.note && <p className="text-[10px] text-gray-400 mt-0.5">{line.note}</p>}
            </div>
            <span
              className={`ml-4 font-mono text-sm font-medium tabular-nums ${n < 0 ? "text-red-500" : n === 0 ? "text-gray-400" : "text-gray-700"}`}
            >
              {fmt(line.amount)}
            </span>
          </div>
        );
      })}
      {/* Total row */}
      <div className="flex items-center justify-between px-4 py-3 border-t-2 border-[#1a2332] bg-[#f8f9fb]">
        <span className="text-sm font-bold text-[#1a2332]">{totalLabel}</span>
        <span className={`font-mono text-sm font-bold tabular-nums ${totalColor}`}>
          {fmt(section.total)}
        </span>
      </div>
    </div>
  );
}

// ── Page ──────────────────────────────────────────────────────────────────────

export default function BalanceSheetPage() {
  const [data, setData] = useState<BalanceSheetData | null>(null);
  const [loading, setLoading] = useState(true);
  const [asOf, setAsOf] = useState(() => new Date().toISOString().slice(0, 10));
  const [inputDate, setInputDate] = useState(asOf);

  const load = useCallback(async (d: string) => {
    setLoading(true);
    try {
      const res = await api.get<BalanceSheetData>(`/api/reports/balance-sheet?as_of=${d}`);
      setData(res);
    } catch {
      toast.error("Failed to load balance sheet");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(asOf); }, [load, asOf]);

  function apply() { setAsOf(inputDate); }

  function exportPdf() {
    window.open(api.downloadUrl(`/api/reports/balance-sheet/pdf?as_of=${asOf}`), "_blank");
  }

  const totalAssets = data ? numOf(data.total_assets) : 0;
  const totalLE     = data ? numOf(data.total_liabilities_and_equity) : 0;
  const totalLiab   = data ? numOf(data.liabilities.total) : 0;
  const totalEquity = data ? numOf(data.equity.total) : 0;

  return (
    <div className="p-6 space-y-6 max-w-4xl">
      {/* Header */}
      <div className="flex items-start justify-between gap-4 flex-wrap">
        <div className="flex items-center gap-3">
          <Scale size={22} className="text-[#1a2332]" />
          <div>
            <h1 className="text-xl font-bold text-[#1a2332]">Balance Sheet</h1>
            {data && (
              <p className="text-sm text-gray-400 mt-0.5">
                As at {data.as_of}
              </p>
            )}
          </div>
        </div>
        <div className="flex gap-2 items-end flex-wrap">
          <div>
            <label className="block text-xs text-gray-400 mb-1">As at date</label>
            <input
              type="date"
              value={inputDate}
              onChange={(e) => setInputDate(e.target.value)}
              className="border rounded px-2 py-1.5 text-sm focus:outline-none"
            />
          </div>
          <button
            onClick={apply}
            className="px-4 py-1.5 bg-[#1a2332] text-white rounded text-sm hover:opacity-90"
          >
            {loading ? "Loading…" : "Apply"}
          </button>
          <button
            onClick={exportPdf}
            className="flex items-center gap-1.5 px-3 py-1.5 border rounded text-sm hover:bg-gray-50"
          >
            <Download size={13} /> PDF
          </button>
        </div>
      </div>

      {/* Disclaimer */}
      <div className="flex items-start gap-3 bg-amber-50 border border-amber-200 rounded-xl p-4">
        <AlertCircle size={17} className="text-amber-500 mt-0.5 flex-shrink-0" />
        <p className="text-xs text-amber-800 leading-relaxed">
          {data?.disclaimer ?? "This is a management approximation generated from operational data. It does not constitute a certified audit statement."}
        </p>
      </div>

      {loading && !data && (
        <div className="space-y-4">
          {[1, 2, 3].map((i) => <div key={i} className="h-40 rounded-xl bg-gray-100 animate-pulse" />)}
        </div>
      )}

      {data && (
        <>
          {/* Balance check banner */}
          <div className={`flex items-center gap-3 rounded-xl px-4 py-3 border ${
            data.balanced
              ? "bg-green-50 border-green-200"
              : "bg-red-50 border-red-200"
          }`}>
            {data.balanced ? (
              <CheckCircle2 size={17} className="text-green-600 flex-shrink-0" />
            ) : (
              <AlertCircle size={17} className="text-red-500 flex-shrink-0" />
            )}
            <p className={`text-xs font-medium ${data.balanced ? "text-green-800" : "text-red-700"}`}>
              {data.balanced
                ? "Sheet balances — Assets equal Liabilities + Equity"
                : "Sheet does not balance — rounding or data gap; check the detailed lines below"}
            </p>
          </div>

          {/* Summary tiles */}
          <div className="grid grid-cols-3 gap-4">
            <div className="bg-white border rounded-xl p-4 space-y-1">
              <p className="text-xs font-medium text-gray-400 uppercase tracking-wide">Total Assets</p>
              <p className={`text-2xl font-bold ${totalAssets >= 0 ? "text-[#1a2332]" : "text-red-500"}`}>
                {fmt(data.total_assets)}
              </p>
              <p className="text-[10px] text-gray-400">SEK</p>
            </div>
            <div className="bg-white border rounded-xl p-4 space-y-1">
              <p className="text-xs font-medium text-gray-400 uppercase tracking-wide">Total Liabilities</p>
              <p className={`text-2xl font-bold ${totalLiab > 0 ? "text-red-500" : "text-green-600"}`}>
                {fmt(data.liabilities.total)}
              </p>
              <p className="text-[10px] text-gray-400">SEK</p>
            </div>
            <div className="bg-white border rounded-xl p-4 space-y-1">
              <p className="text-xs font-medium text-gray-400 uppercase tracking-wide">Net Equity</p>
              <p className={`text-2xl font-bold ${totalEquity >= 0 ? "text-green-600" : "text-red-500"}`}>
                {fmt(data.equity.total)}
              </p>
              <p className="text-[10px] text-gray-400">SEK</p>
            </div>
          </div>

          {/* Assets section */}
          <div className="bg-white border rounded-xl overflow-hidden">
            <SectionTable
              section={data.assets}
              totalLabel="Total Assets"
              totalColor={totalAssets >= 0 ? "text-green-600" : "text-red-500"}
            />
          </div>

          {/* Liabilities section */}
          <div className="bg-white border rounded-xl overflow-hidden">
            <SectionTable
              section={data.liabilities}
              totalLabel="Total Liabilities"
              totalColor={totalLiab > 0 ? "text-red-500" : "text-green-600"}
            />
          </div>

          {/* Equity section */}
          <div className="bg-white border rounded-xl overflow-hidden">
            <SectionTable
              section={data.equity}
              totalLabel="Total Equity"
              totalColor={totalEquity >= 0 ? "text-green-600" : "text-red-500"}
            />
          </div>

          {/* Final reconciliation */}
          <div className="bg-white border-2 border-[#1a2332] rounded-xl overflow-hidden">
            <div className="px-4 py-3 flex items-center justify-between bg-[#f8f9fb] border-b">
              <span className="text-sm font-bold text-[#1a2332]">Reconciliation</span>
            </div>
            <div className="divide-y">
              <div className="flex items-center justify-between px-4 py-3">
                <span className="text-sm text-gray-600">Total Assets</span>
                <span className="font-mono text-sm font-semibold">{fmt(data.total_assets)} SEK</span>
              </div>
              <div className="flex items-center justify-between px-4 py-3">
                <span className="text-sm text-gray-600">Total Liabilities + Equity</span>
                <span className="font-mono text-sm font-semibold">{fmt(data.total_liabilities_and_equity)} SEK</span>
              </div>
              <div className="flex items-center justify-between px-4 py-3 bg-gray-50">
                <span className="text-sm font-bold text-[#1a2332]">Difference</span>
                <span className={`font-mono text-sm font-bold ${
                  Math.abs(totalAssets - totalLE) < 1 ? "text-green-600" : "text-red-500"
                }`}>
                  {fmt(String(totalAssets - totalLE))} SEK
                </span>
              </div>
            </div>
          </div>

          {/* Generated timestamp */}
          <p className="text-[10px] text-gray-400 text-right">
            Generated {new Date(data.generated_at).toLocaleString("en-GB")} UTC
          </p>
        </>
      )}
    </div>
  );
}
