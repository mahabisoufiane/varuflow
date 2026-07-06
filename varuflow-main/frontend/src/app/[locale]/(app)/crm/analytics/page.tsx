"use client";
import { useEffect, useState } from "react";
import { BarChart2, TrendingUp, Clock, DollarSign, Target, CheckCircle2, XCircle } from "lucide-react";
import { api } from "@/lib/api-client";

interface Analytics {
  total_deals: number;
  win_rate_pct: number;
  avg_sales_cycle_days: number | null;
  won_revenue: number;
  lost_revenue: number;
  pipeline_value: number;
  stage_breakdown: Record<string, number>;
  win_reasons: Record<string, number>;
  loss_reasons: Record<string, number>;
}

function StatCard({ label, value, sub, icon, accent }: { label: string; value: string; sub?: string; icon: React.ReactNode; accent?: string }) {
  return (
    <div className="bg-white border rounded-xl p-5 space-y-2">
      <div className="flex items-center justify-between">
        <p className="text-xs text-gray-400 font-medium uppercase tracking-wide">{label}</p>
        <span className={accent ?? "text-gray-300"}>{icon}</span>
      </div>
      <p className="text-3xl font-bold text-gray-900">{value}</p>
      {sub && <p className="text-xs text-gray-400">{sub}</p>}
    </div>
  );
}

function ReasonList({ reasons, color }: { reasons: Record<string, number>; color: string }) {
  const entries = Object.entries(reasons).sort(([, a], [, b]) => b - a).slice(0, 8);
  if (entries.length === 0) return <p className="text-sm text-gray-300">None recorded yet</p>;
  const max = entries[0][1];
  return (
    <div className="space-y-2">
      {entries.map(([reason, count]) => (
        <div key={reason} className="space-y-0.5">
          <div className="flex justify-between text-xs text-gray-600">
            <span className="truncate">{reason}</span>
            <span className="shrink-0 ml-2">{count}</span>
          </div>
          <div className="h-1.5 bg-gray-100 rounded-full overflow-hidden">
            <div className={`h-full rounded-full ${color}`} style={{ width: `${(count / max) * 100}%` }} />
          </div>
        </div>
      ))}
    </div>
  );
}

export default function CrmAnalyticsPage() {
  const [data, setData] = useState<Analytics | null>(null);
  const [error, setError] = useState(false);

  useEffect(() => {
    api.get<Analytics>("/api/crm/analytics")
      .then(setData)
      .catch(() => setError(true));
  }, []);

  if (error) return <div className="p-6 text-red-500 text-sm">Failed to load analytics.</div>;
  if (!data) return <div className="p-6 text-gray-400 text-sm">Loading…</div>;

  const stageEntries = Object.entries(data.stage_breakdown).sort(([, a], [, b]) => b - a);
  const maxStage = stageEntries[0]?.[1] ?? 1;

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center gap-2">
        <BarChart2 size={22} className="text-[var(--vf-text-primary)]" />
        <h1 className="text-2xl font-bold">CRM Analytics</h1>
      </div>

      {/* KPI strip */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard
          label="Total Deals"
          value={String(data.total_deals)}
          icon={<Target size={18} />}
        />
        <StatCard
          label="Win Rate"
          value={`${data.win_rate_pct}%`}
          sub={`${Object.values(data.win_reasons).reduce((a,b)=>a+b,0)} won`}
          icon={<TrendingUp size={18} />}
          accent="text-green-400"
        />
        <StatCard
          label="Avg Sales Cycle"
          value={data.avg_sales_cycle_days !== null ? `${data.avg_sales_cycle_days}d` : "—"}
          sub="days from lead to close"
          icon={<Clock size={18} />}
        />
        <StatCard
          label="Pipeline Value"
          value={data.pipeline_value.toLocaleString(undefined, { maximumFractionDigits: 0 })}
          sub="open deals"
          icon={<DollarSign size={18} />}
        />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        {/* Stage breakdown */}
        <div className="bg-white border rounded-xl p-5 space-y-4">
          <p className="text-sm font-semibold text-gray-700">Deals by Stage</p>
          {stageEntries.length === 0 ? (
            <p className="text-sm text-gray-300">No data yet</p>
          ) : stageEntries.map(([stage, count]) => (
            <div key={stage} className="space-y-0.5">
              <div className="flex justify-between text-xs text-gray-600">
                <span className="capitalize">{stage.replace("_", " ")}</span>
                <span>{count}</span>
              </div>
              <div className="h-2 bg-gray-100 rounded-full overflow-hidden">
                <div className="h-full bg-[var(--vf-brand-primary)] rounded-full" style={{ width: `${(count / maxStage) * 100}%` }} />
              </div>
            </div>
          ))}
        </div>

        {/* Won vs Lost revenue */}
        <div className="bg-white border rounded-xl p-5 space-y-4">
          <p className="text-sm font-semibold text-gray-700">Revenue Won vs Lost</p>
          {(() => {
            const maxVal = Math.max(data.won_revenue, data.lost_revenue) || 1;
            return (
              <div className="space-y-4">
                <div className="space-y-1">
                  <div className="flex items-center justify-between text-xs text-gray-600">
                    <span className="flex items-center gap-1"><CheckCircle2 size={11} className="text-green-600" /> Won</span>
                    <span className="font-medium text-green-700">{data.won_revenue.toLocaleString(undefined, { maximumFractionDigits: 0 })}</span>
                  </div>
                  <div className="h-3 bg-gray-100 rounded-full overflow-hidden">
                    <div className="h-full bg-green-500 rounded-full" style={{ width: `${(data.won_revenue / maxVal) * 100}%` }} />
                  </div>
                </div>
                <div className="space-y-1">
                  <div className="flex items-center justify-between text-xs text-gray-600">
                    <span className="flex items-center gap-1"><XCircle size={11} className="text-red-500" /> Lost</span>
                    <span className="font-medium text-red-500">{data.lost_revenue.toLocaleString(undefined, { maximumFractionDigits: 0 })}</span>
                  </div>
                  <div className="h-3 bg-gray-100 rounded-full overflow-hidden">
                    <div className="h-full bg-red-400 rounded-full" style={{ width: `${(data.lost_revenue / maxVal) * 100}%` }} />
                  </div>
                </div>
              </div>
            );
          })()}
        </div>

        {/* Win / loss reasons */}
        <div className="space-y-4">
          <div className="bg-white border rounded-xl p-5 space-y-3">
            <p className="text-sm font-semibold text-gray-700 flex items-center gap-1.5">
              <CheckCircle2 size={14} className="text-green-600" /> Top Win Reasons
            </p>
            <ReasonList reasons={data.win_reasons} color="bg-green-400" />
          </div>
          <div className="bg-white border rounded-xl p-5 space-y-3">
            <p className="text-sm font-semibold text-gray-700 flex items-center gap-1.5">
              <XCircle size={14} className="text-red-500" /> Top Loss Reasons
            </p>
            <ReasonList reasons={data.loss_reasons} color="bg-red-400" />
          </div>
        </div>
      </div>
    </div>
  );
}
