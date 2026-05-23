"use client";

import { useCallback, useEffect, useState } from "react";
import { TrendingUp, Loader2 } from "lucide-react";
import { toast } from "sonner";
import { api } from "@/lib/api-client";

interface MonthData {
  deals: number;
  total_value: number;
  weighted_value: number;
  by_stage: Record<string, number>;
}

interface ForecastData {
  months: Record<string, MonthData>;
  total_pipeline: number;
}

export default function CrmForecastPage() {
  const [data, setData] = useState<ForecastData | null>(null);
  const [loading, setLoading] = useState(true);
  const [months, setMonths] = useState(3);

  const load = useCallback(async (m: number) => {
    setLoading(true);
    try {
      const d = await api.get<ForecastData>(`/api/crm/forecast?months=${m}`);
      setData(d);
    } catch {
      toast.error("Failed to load forecast");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(months); }, [months, load]);

  const monthEntries = Object.entries(data?.months ?? {});
  const totalWeighted = monthEntries.reduce((s, [, m]) => s + m.weighted_value, 0);
  const closingThisMonth = (() => {
    const key = new Date().toISOString().slice(0, 7);
    return data?.months[key]?.deals ?? 0;
  })();

  return (
    <div className="space-y-5">
      <div className="flex items-center gap-3">
        <TrendingUp className="h-5 w-5 vf-text-m" />
        <h1 className="text-[15px] font-semibold vf-text-1">Sales Forecast</h1>
      </div>

      {/* KPI strip */}
      <div className="grid grid-cols-3 gap-4">
        {[
          { label: "Total pipeline", value: `${(data?.total_pipeline ?? 0).toLocaleString()} SEK` },
          { label: "Weighted forecast", value: `${totalWeighted.toLocaleString(undefined, { maximumFractionDigits: 0 })} SEK` },
          { label: "Closing this month", value: `${closingThisMonth} deals` },
        ].map((kpi) => (
          <div key={kpi.label} className="vf-card p-4">
            <p className="text-xs vf-text-m">{kpi.label}</p>
            <p className="text-xl font-bold vf-text-1 mt-1">{kpi.value}</p>
          </div>
        ))}
      </div>

      {/* Month range selector */}
      <div className="flex gap-2">
        {[3, 6, 12].map((m) => (
          <button
            key={m}
            onClick={() => setMonths(m)}
            className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${
              months === m ? "bg-indigo-600 text-white" : "vf-btn-ghost vf-text-m"
            }`}
          >
            {m} months
          </button>
        ))}
      </div>

      {loading ? (
        <div className="flex justify-center py-12">
          <Loader2 className="h-6 w-6 animate-spin text-gray-400" />
        </div>
      ) : monthEntries.length === 0 ? (
        <div className="vf-card p-8 text-center text-sm vf-text-m">
          No deals with close dates in this range.
        </div>
      ) : (
        <div className="vf-card overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-[var(--vf-border)]">
                <th className="px-4 py-3 text-left text-xs font-semibold vf-text-m">Month</th>
                <th className="px-4 py-3 text-right text-xs font-semibold vf-text-m">Deals</th>
                <th className="px-4 py-3 text-right text-xs font-semibold vf-text-m">Pipeline</th>
                <th className="px-4 py-3 text-right text-xs font-semibold vf-text-m">Weighted</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[var(--vf-border)]">
              {monthEntries.map(([month, m]) => (
                <tr key={month} className="hover:bg-[var(--vf-hover)]">
                  <td className="px-4 py-3 font-medium vf-text-1">{month}</td>
                  <td className="px-4 py-3 text-right vf-text-m">{m.deals}</td>
                  <td className="px-4 py-3 text-right vf-text-m">{m.total_value.toLocaleString()} SEK</td>
                  <td className="px-4 py-3 text-right font-semibold text-indigo-500">
                    {m.weighted_value.toLocaleString(undefined, { maximumFractionDigits: 0 })} SEK
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
