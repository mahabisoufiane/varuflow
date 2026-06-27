"use client";

import { useState, useEffect } from "react";
import { toast } from "sonner";

interface RetentionPoint { month_offset: number; retained: number; rate: number }
interface Cohort { cohort_month: string; cohort_size: number; retention: RetentionPoint[] }
interface CohortsData { cohorts: Cohort[]; max_offset: number }

function heatColor(rate: number): string {
  if (rate === 0) return "bg-gray-100 text-gray-400";
  if (rate >= 80) return "bg-emerald-600 text-white";
  if (rate >= 60) return "bg-emerald-500 text-white";
  if (rate >= 40) return "bg-emerald-400 text-white";
  if (rate >= 25) return "bg-amber-300 text-amber-900";
  if (rate >= 10) return "bg-amber-200 text-amber-800";
  return "bg-red-100 text-red-600";
}

export default function CohortsPage() {
  const apiBase = process.env.NEXT_PUBLIC_API_URL!;
  const [data, setData] = useState<CohortsData | null>(null);
  const [months, setMonths] = useState(12);
  const [loading, setLoading] = useState(false);

  const f = (url: string) => fetch(`${apiBase}${url}`, { credentials: "include" });

  async function load(m: number) {
    setLoading(true);
    try {
      const res = await f(`/api/bi/cohorts?months=${m}`);
      if (res.ok) setData(await res.json());
      else { const e = await res.json(); toast.error(e.detail || "Failed"); }
    } finally { setLoading(false); }
  }

  useEffect(() => { load(months); }, [months]);

  const maxOffset = data?.max_offset ?? 0;
  const offsets = Array.from({ length: Math.min(maxOffset + 1, 13) }, (_, i) => i);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-gray-900">Cohort Analysis</h1>
          <p className="mt-1 text-sm text-gray-500">Customer retention by acquisition month — see who keeps coming back.</p>
        </div>
        <select className="input text-sm" value={months} onChange={e => setMonths(Number(e.target.value))}>
          {[6, 12, 18, 24].map(m => <option key={m} value={m}>Last {m} months</option>)}
        </select>
      </div>

      {/* Legend */}
      <div className="flex items-center gap-3 text-xs text-gray-500">
        <span>Retention rate:</span>
        {[
          { label: "≥80%", color: "bg-emerald-600" },
          { label: "60–79%", color: "bg-emerald-500" },
          { label: "40–59%", color: "bg-emerald-400" },
          { label: "25–39%", color: "bg-amber-300" },
          { label: "10–24%", color: "bg-amber-200" },
          { label: "<10%", color: "bg-red-100" },
        ].map(l => (
          <span key={l.label} className="flex items-center gap-1">
            <span className={`w-3 h-3 rounded-sm ${l.color}`} />
            {l.label}
          </span>
        ))}
      </div>

      {loading ? (
        <div className="animate-pulse h-64 bg-gray-100 rounded-xl" />
      ) : !data || data.cohorts.length === 0 ? (
        <div className="rounded-xl border border-dashed border-gray-300 p-12 text-center text-sm text-gray-400">
          Not enough invoice data to generate cohorts. You need customers with invoices spanning multiple months.
        </div>
      ) : (
        <div className="rounded-xl border border-gray-200 bg-white overflow-auto">
          <table className="text-xs border-collapse">
            <thead>
              <tr className="border-b border-gray-200">
                <th className="sticky left-0 bg-gray-50 px-4 py-3 text-left font-medium text-gray-500 min-w-[120px] z-10">Cohort</th>
                <th className="px-3 py-3 text-center font-medium text-gray-500 min-w-[60px]">Size</th>
                {offsets.map(n => (
                  <th key={n} className="px-3 py-3 text-center font-medium text-gray-500 min-w-[52px]">
                    M+{n}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {data.cohorts.map(cohort => (
                <tr key={cohort.cohort_month} className="hover:bg-gray-50/50">
                  <td className="sticky left-0 bg-white px-4 py-2 font-medium text-gray-900 z-10">{cohort.cohort_month}</td>
                  <td className="px-3 py-2 text-center text-gray-600">{cohort.cohort_size}</td>
                  {offsets.map(n => {
                    const point = cohort.retention.find(r => r.month_offset === n);
                    if (!point) return <td key={n} className="px-3 py-2 text-center text-gray-200">—</td>;
                    return (
                      <td key={n} className="px-1 py-1">
                        <div className={`rounded text-center py-1.5 font-medium tabular-nums ${heatColor(point.rate)}`}
                          title={`${point.retained} customers (${point.rate}%)`}>
                          {point.rate > 0 ? `${point.rate}%` : "0%"}
                        </div>
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <div className="rounded-xl border border-gray-200 bg-gray-50 p-4 text-xs text-gray-500 space-y-1">
        <p className="font-medium text-gray-700">How to read this table</p>
        <p>Each row is a cohort of customers whose first invoice was in that month. M+0 = the acquisition month (always 100%). M+1 = % who purchased again in the following month, etc.</p>
        <p>A healthy SaaS/recurring business should see ≥40% retention at M+3. Below 20% at M+1 suggests one-time buyers dominating.</p>
      </div>
    </div>
  );
}
