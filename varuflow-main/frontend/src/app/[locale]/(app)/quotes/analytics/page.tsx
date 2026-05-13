"use client";
import { useEffect, useState } from "react";
import { TrendingUp, DollarSign, Clock, BarChart2 } from "lucide-react";

const API = process.env.NEXT_PUBLIC_API_URL ?? "";

interface Analytics {
  total_quotes: number;
  acceptance_rate_pct: number;
  avg_hours_to_accept: number | null;
  won_revenue: number;
  lost_revenue: number;
  status_breakdown: Record<string, number>;
}

const STATUS_COLOR: Record<string, string> = {
  draft:    "bg-gray-300",
  sent:     "bg-blue-400",
  viewed:   "bg-yellow-400",
  accepted: "bg-green-500",
  rejected: "bg-red-400",
  expired:  "bg-gray-400",
  invoiced: "bg-purple-500",
};

function StatCard({ label, value, sub, icon }: { label: string; value: string; sub?: string; icon: React.ReactNode }) {
  return (
    <div className="bg-white border rounded-xl p-5 space-y-2">
      <div className="flex items-center justify-between">
        <p className="text-xs text-gray-400 font-medium uppercase tracking-wide">{label}</p>
        <span className="text-gray-300">{icon}</span>
      </div>
      <p className="text-3xl font-bold text-gray-900">{value}</p>
      {sub && <p className="text-xs text-gray-400">{sub}</p>}
    </div>
  );
}

export default function QuoteAnalyticsPage() {
  const [data, setData] = useState<Analytics | null>(null);
  const [error, setError] = useState(false);

  useEffect(() => {
    fetch(`${API}/api/quotes/analytics`, { credentials: "include" })
      .then(r => { if (!r.ok) throw new Error(); return r.json(); })
      .then(setData)
      .catch(() => setError(true));
  }, []);

  if (error) return <div className="p-6 text-red-500 text-sm">Failed to load analytics.</div>;
  if (!data) return <div className="p-6 text-gray-400 text-sm">Loading…</div>;

  const total = data.total_quotes;
  const fmtHours = (h: number | null) => h === null ? "—" : h < 24 ? `${h.toFixed(1)}h` : `${(h / 24).toFixed(1)}d`;

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center gap-3">
        <BarChart2 size={22} className="text-[#1a2332]" />
        <h1 className="text-2xl font-bold">Quote Analytics</h1>
      </div>

      {/* KPI cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard
          label="Total Quotes"
          value={String(total)}
          icon={<BarChart2 size={18} />}
        />
        <StatCard
          label="Acceptance Rate"
          value={`${data.acceptance_rate_pct}%`}
          sub={`${data.status_breakdown["accepted"] ?? 0} of ${total} quotes`}
          icon={<TrendingUp size={18} />}
        />
        <StatCard
          label="Avg Time to Accept"
          value={fmtHours(data.avg_hours_to_accept)}
          sub="from sent to accepted"
          icon={<Clock size={18} />}
        />
        <StatCard
          label="Won Revenue"
          value={data.won_revenue.toLocaleString(undefined, { maximumFractionDigits: 0 })}
          sub={`Lost: ${data.lost_revenue.toLocaleString(undefined, { maximumFractionDigits: 0 })}`}
          icon={<DollarSign size={18} />}
        />
      </div>

      {/* Status breakdown */}
      <div className="bg-white border rounded-xl p-5 space-y-4">
        <p className="text-sm font-semibold text-gray-700">Status Breakdown</p>
        {total === 0 ? (
          <p className="text-sm text-gray-400">No quotes yet.</p>
        ) : (
          <div className="space-y-3">
            {Object.entries(data.status_breakdown)
              .sort(([, a], [, b]) => b - a)
              .map(([status, count]) => {
                const pct = total ? Math.round((count / total) * 100) : 0;
                return (
                  <div key={status} className="space-y-1">
                    <div className="flex items-center justify-between text-xs text-gray-600">
                      <span className="capitalize">{status}</span>
                      <span>{count} ({pct}%)</span>
                    </div>
                    <div className="h-2 bg-gray-100 rounded-full overflow-hidden">
                      <div
                        className={`h-full rounded-full ${STATUS_COLOR[status] ?? "bg-gray-400"}`}
                        style={{ width: `${pct}%` }}
                      />
                    </div>
                  </div>
                );
              })}
          </div>
        )}
      </div>

      {/* Won vs Lost revenue comparison */}
      <div className="bg-white border rounded-xl p-5 space-y-4">
        <p className="text-sm font-semibold text-gray-700">Revenue — Won vs Lost</p>
        {data.won_revenue === 0 && data.lost_revenue === 0 ? (
          <p className="text-sm text-gray-400">No revenue data yet.</p>
        ) : (
          (() => {
            const maxVal = Math.max(data.won_revenue, data.lost_revenue);
            return (
              <div className="space-y-3">
                <div className="space-y-1">
                  <div className="flex justify-between text-xs text-gray-600">
                    <span>Won</span>
                    <span className="font-medium text-green-700">{data.won_revenue.toLocaleString(undefined, { maximumFractionDigits: 0 })}</span>
                  </div>
                  <div className="h-3 bg-gray-100 rounded-full overflow-hidden">
                    <div className="h-full bg-green-500 rounded-full" style={{ width: maxVal ? `${(data.won_revenue / maxVal) * 100}%` : "0%" }} />
                  </div>
                </div>
                <div className="space-y-1">
                  <div className="flex justify-between text-xs text-gray-600">
                    <span>Lost</span>
                    <span className="font-medium text-red-600">{data.lost_revenue.toLocaleString(undefined, { maximumFractionDigits: 0 })}</span>
                  </div>
                  <div className="h-3 bg-gray-100 rounded-full overflow-hidden">
                    <div className="h-full bg-red-400 rounded-full" style={{ width: maxVal ? `${(data.lost_revenue / maxVal) * 100}%` : "0%" }} />
                  </div>
                </div>
              </div>
            );
          })()
        )}
      </div>
    </div>
  );
}
