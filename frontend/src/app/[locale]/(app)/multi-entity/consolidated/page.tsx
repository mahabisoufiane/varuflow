"use client";

import { useState, useEffect } from "react";
import { toast } from "sonner";
import { BarChart3, MinusCircle } from "lucide-react";

interface EntityRow { id: string; name: string; revenue: number }
interface ConsolidatedData {
  period: string;
  entities: EntityRow[];
  consolidated: {
    gross_revenue: number;
    intercompany_eliminations: number;
    net_group_revenue: number;
  };
}

export default function ConsolidatedReportsPage() {
  const apiBase = process.env.NEXT_PUBLIC_API_URL!;
  const now = new Date();
  const [period, setPeriod] = useState(`${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}`);
  const [data, setData] = useState<ConsolidatedData | null>(null);
  const [loading, setLoading] = useState(false);

  const fetch_ = (url: string) => fetch(`${apiBase}${url}`, { credentials: "include" });

  async function load() {
    setLoading(true);
    try {
      const res = await fetch_(`/api/multi-entity/consolidated/${period}`);
      if (res.ok) setData(await res.json());
      else toast.error("Failed to load report");
    } catch { toast.error("Network error"); }
    setLoading(false);
  }

  useEffect(() => { load(); }, [period]);

  const fmt = (n: number) => new Intl.NumberFormat("sv-SE", { style: "currency", currency: "SEK", maximumFractionDigits: 0 }).format(n);

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold text-gray-900">Consolidated Reports</h1>
          <p className="mt-1 text-sm text-gray-500">Group P&L across all entities, net of intercompany eliminations.</p>
        </div>
        <input
          type="month"
          className="input w-44"
          value={period}
          onChange={e => setPeriod(e.target.value)}
        />
      </div>

      {loading && <div className="text-sm text-gray-400 animate-pulse">Loading…</div>}

      {data && !loading && (
        <>
          {/* Entity breakdown */}
          <div>
            <h2 className="text-sm font-semibold text-gray-500 uppercase tracking-wider mb-3">Revenue by Entity</h2>
            {data.entities.length === 0 ? (
              <p className="text-sm text-gray-400">No revenue data for this period.</p>
            ) : (
              <div className="space-y-2">
                {data.entities.map(e => (
                  <div key={e.id} className="flex items-center justify-between rounded-xl border border-gray-200 bg-white p-4">
                    <div className="flex items-center gap-3">
                      <BarChart3 className="h-4 w-4 text-gray-400" />
                      <p className="text-sm font-medium text-gray-900">{e.name}</p>
                    </div>
                    <p className="text-sm font-medium text-gray-900">{fmt(e.revenue)}</p>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Consolidated summary */}
          <div className="rounded-2xl border border-gray-200 bg-white p-6 space-y-4">
            <h2 className="text-sm font-semibold text-gray-700 uppercase tracking-wider">Group Summary</h2>

            <div className="space-y-2">
              <div className="flex justify-between text-sm">
                <span className="text-gray-600">Gross Group Revenue</span>
                <span className="font-medium text-gray-900">{fmt(data.consolidated.gross_revenue)}</span>
              </div>
              <div className="flex justify-between text-sm text-red-600">
                <span className="flex items-center gap-1"><MinusCircle className="h-3.5 w-3.5" /> Intercompany Eliminations</span>
                <span className="font-medium">({fmt(data.consolidated.intercompany_eliminations)})</span>
              </div>
              <div className="h-px bg-gray-200" />
              <div className="flex justify-between text-base font-semibold">
                <span className="text-gray-900">Net Group Revenue</span>
                <span className="text-blue-700">{fmt(data.consolidated.net_group_revenue)}</span>
              </div>
            </div>
          </div>

          <p className="text-xs text-gray-400">
            Eliminations are generated automatically when intercompany transfers are posted.
            Navigate to <strong>Intercompany Transfers</strong> to post and eliminate transactions.
          </p>
        </>
      )}
    </div>
  );
}
