"use client";

import { api } from "@/lib/api-client";
import { useState } from "react";
import { AlertCircle, Calculator, TrendingDown } from "lucide-react";
import { toast } from "sonner";
import { useRouter } from "@/i18n/navigation";
import { useLocale } from "next-intl";

interface ZakatEstimate {
  as_of_date: string;
  inventory_value: string;
  receivables: string;
  payables: string;
  zakatable_base: string;
  nisab_threshold_sar: string;
  above_nisab: boolean;
  zakat_due: string;
  currency: string;
  note: string;
}

export default function ZakatPage() {
  const locale = useLocale();
  const router = useRouter();
  const [asOfDate, setAsOfDate] = useState(() => new Date().toISOString().slice(0, 10));
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<ZakatEstimate | null>(null);

  async function compute() {
    setLoading(true);
    try {
      const d = await api.get(`/api/mena/zakat/estimate?as_of_date=${asOfDate}`);
      setResult(d as ZakatEstimate);
    } catch (e: unknown) {
      const err = e as { status?: number };
      if (err.status === 401) router.push("/auth/login");
      else toast.error("Failed to compute Zakat estimate.");
    } finally {
      setLoading(false);
    }
  }

  const fmt = (v: string) =>
    parseFloat(v).toLocaleString("en-SA", { minimumFractionDigits: 2 });

  const nisabPct = result
    ? Math.min(100, (parseFloat(result.zakatable_base) / parseFloat(result.nisab_threshold_sar)) * 100)
    : 0;

  return (
    <div className="max-w-3xl mx-auto p-6 space-y-6">
      <div>
        <h1 className="text-2xl font-bold flex items-center gap-2">
          <Calculator className="w-6 h-6 text-amber-600" />
          Zakat Estimation
        </h1>
        <p className="text-sm text-gray-500 mt-1">
          Estimate Islamic tax obligation for Saudi entities. 2.5% of zakatable assets above nisab.
        </p>
      </div>

      {/* Controls */}
      <div className="p-5 border rounded-lg flex items-end gap-4">
        <div className="flex-1">
          <label className="text-sm font-medium">As-of date</label>
          <input type="date" value={asOfDate} onChange={e => setAsOfDate(e.target.value)}
            className="mt-1 w-full border rounded px-3 py-2 text-sm" />
        </div>
        <button onClick={compute} disabled={loading}
          className="px-5 py-2 bg-amber-600 text-white text-sm rounded-lg hover:bg-amber-700 disabled:opacity-50 flex items-center gap-2">
          <Calculator className="w-4 h-4" />
          {loading ? "Computing…" : "Estimate Zakat"}
        </button>
      </div>

      {/* Results */}
      {result && (
        <div className="space-y-4">
          {/* KPI cards */}
          <div className="grid grid-cols-2 gap-4">
            {[
              { label: "Inventory Value", value: result.inventory_value, color: "text-blue-700" },
              { label: "Receivables (>354d)", value: result.receivables, color: "text-green-700" },
              { label: "Payables", value: result.payables, color: "text-red-600" },
              { label: "Zakatable Base", value: result.zakatable_base, color: "text-gray-800", bold: true },
            ].map(card => (
              <div key={card.label} className="p-4 border rounded-lg">
                <p className="text-xs text-gray-500">{card.label}</p>
                <p className={`text-xl font-${card.bold ? "bold" : "semibold"} mt-1 ${card.color}`}>
                  {result.currency} {fmt(card.value)}
                </p>
              </div>
            ))}
          </div>

          {/* Nisab progress */}
          <div className="p-4 border rounded-lg space-y-2">
            <div className="flex justify-between text-sm">
              <span>Nisab threshold: <strong>{result.currency} {fmt(result.nisab_threshold_sar)}</strong></span>
              <span className={result.above_nisab ? "text-amber-600 font-medium" : "text-green-600 font-medium"}>
                {result.above_nisab ? "Above nisab" : "Below nisab"}
              </span>
            </div>
            <div className="h-2 bg-gray-100 rounded-full overflow-hidden">
              <div
                className={`h-full rounded-full transition-all ${result.above_nisab ? "bg-amber-500" : "bg-green-500"}`}
                style={{ width: `${nisabPct}%` }}
              />
            </div>
          </div>

          {/* Zakat due */}
          <div className={`p-5 rounded-lg border ${result.above_nisab ? "bg-amber-50 border-amber-300" : "bg-green-50 border-green-300"}`}>
            <p className="text-sm font-medium text-gray-700">Estimated Zakat Due</p>
            <p className={`text-4xl font-bold mt-2 ${result.above_nisab ? "text-amber-700" : "text-green-700"}`}>
              {result.currency} {fmt(result.zakat_due)}
            </p>
            {!result.above_nisab && (
              <p className="text-sm text-green-600 mt-1 flex items-center gap-1">
                <TrendingDown className="w-4 h-4" />
                Zakatable base is below nisab — no Zakat due.
              </p>
            )}
          </div>

          {/* Disclaimer */}
          <div className="p-4 bg-gray-50 border rounded-lg flex items-start gap-3">
            <AlertCircle className="w-5 h-5 text-gray-400 flex-shrink-0 mt-0.5" />
            <p className="text-xs text-gray-500">{result.note}</p>
          </div>
        </div>
      )}
    </div>
  );
}
