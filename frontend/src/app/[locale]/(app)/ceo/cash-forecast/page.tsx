"use client";

import { useState, useEffect } from "react";
import { AlertTriangle, TrendingDown, CheckCircle2, DollarSign, Calendar } from "lucide-react";
import { api } from "@/lib/api-client";

interface SeriesPoint { day: number; date: string; balance: number; inflow: number; outflow: number }
interface UpcomingInflow { invoice_number: string; customer: string; due_date: string; expected: number }
interface ForecastData {
  current_balance: number;
  balance_30d: number;
  balance_60d: number;
  balance_90d: number;
  daily_burn: number;
  cashout_day: number | null;
  low_balance: number;
  low_day: number;
  series: SeriesPoint[];
  upcoming_inflows: UpcomingInflow[];
  has_bank_data: boolean;
}

function BalanceBar({ value, max }: { value: number; max: number }) {
  const pct = max === 0 ? 0 : Math.max(0, Math.min(100, (value / max) * 100));
  const color = value < 0 ? "bg-red-500" : value < max * 0.2 ? "bg-amber-400" : "bg-emerald-500";
  return (
    <div className="h-2 bg-gray-100 rounded-full overflow-hidden">
      <div className={`h-full rounded-full transition-all ${color}`} style={{ width: `${pct}%` }} />
    </div>
  );
}

export default function CashForecastPage() {
  const [data, setData] = useState<ForecastData | null>(null);
  const [horizon, setHorizon] = useState(90);
  const [loading, setLoading] = useState(false);

  async function load(h: number) {
    setLoading(true);
    try {
      const result = await api.get<ForecastData>(`/api/ceo/cash-forecast?horizon_days=${h}`);
      setData(result);
    } catch {}
    setLoading(false);
  }

  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(() => { load(horizon); }, [horizon]);

  const fmt = (v: number) => v.toLocaleString("sv-SE", { maximumFractionDigits: 0 });
  const fmtDate = (s: string) => new Date(s).toLocaleDateString("sv-SE", { month: "short", day: "numeric" });

  const maxBalance = data ? Math.max(data.current_balance, data.balance_30d, data.balance_60d, data.balance_90d, 1) : 1;

  return (
    <div className="max-w-3xl space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-gray-900">Cash Flow Forecast</h1>
          <p className="mt-1 text-sm text-gray-500">Forward-looking balance — will you have money in 30/60/90 days?</p>
        </div>
        <div className="flex gap-2">
          {[30, 60, 90].map(h => (
            <button key={h} onClick={() => setHorizon(h)}
              className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-all ${
                horizon === h ? "bg-blue-500 text-white" : "bg-gray-100 text-gray-700 hover:bg-gray-200"
              }`}>{h}d</button>
          ))}
        </div>
      </div>

      {loading || !data ? (
        <div className="space-y-4">
          {[1,2,3].map(i => <div key={i} className="animate-pulse h-24 rounded-xl bg-gray-100" />)}
        </div>
      ) : (
        <>
          {/* Cashout alert */}
          {data.cashout_day !== null && (
            <div className="rounded-xl border border-red-300 bg-red-50 p-4 flex items-start gap-3">
              <AlertTriangle className="h-5 w-5 text-red-500 flex-shrink-0 mt-0.5" />
              <div>
                <p className="font-semibold text-red-800">Cashout Risk</p>
                <p className="text-sm text-red-700 mt-0.5">
                  At your current burn rate of <strong>{fmt(data.daily_burn)}/day</strong>, your projected balance
                  goes negative in <strong>day {data.cashout_day}</strong> ({fmtDate(data.series.find(s => s.day >= data.cashout_day!)?.date || "")}).
                  Consider collecting outstanding invoices or reducing costs.
                </p>
              </div>
            </div>
          )}

          {!data.has_bank_data && (
            <div className="rounded-xl border border-amber-200 bg-amber-50 p-3 text-sm text-amber-800">
              No bank account connected. Balance is estimated from paid invoices minus approved expenses.
              Connect a bank account in <strong>Bank Feed</strong> for precise figures.
            </div>
          )}

          {/* Balance at milestones */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
            {[
              { label: "Today", value: data.current_balance },
              { label: "In 30 days", value: data.balance_30d },
              { label: "In 60 days", value: data.balance_60d },
              { label: "In 90 days", value: data.balance_90d },
            ].map(item => (
              <div key={item.label} className={`rounded-xl border p-4 ${item.value < 0 ? "border-red-200 bg-red-50" : "border-gray-200 bg-white"}`}>
                <p className="text-xs font-medium text-gray-500">{item.label}</p>
                <p className={`text-xl font-bold mt-1 tabular-nums ${item.value < 0 ? "text-red-600" : "text-gray-900"}`}>
                  {item.value < 0 ? "−" : ""}{fmt(Math.abs(item.value))}
                </p>
                <BalanceBar value={item.value} max={maxBalance} />
              </div>
            ))}
          </div>

          {/* Daily burn + low point */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div className="rounded-xl border border-gray-200 bg-white p-4 flex items-center gap-4">
              <TrendingDown className="h-8 w-8 text-amber-400" />
              <div>
                <p className="text-xs font-medium text-gray-500">Daily Burn Rate</p>
                <p className="text-xl font-bold text-gray-900">{fmt(data.daily_burn)}</p>
                <p className="text-xs text-gray-400">3-month avg daily expense</p>
              </div>
            </div>
            <div className={`rounded-xl border p-4 flex items-center gap-4 ${data.low_balance < 0 ? "border-red-200 bg-red-50" : "border-gray-200 bg-white"}`}>
              {data.low_balance < 0 ? <AlertTriangle className="h-8 w-8 text-red-400" /> : <CheckCircle2 className="h-8 w-8 text-green-400" />}
              <div>
                <p className="text-xs font-medium text-gray-500">Projected Low Point</p>
                <p className={`text-xl font-bold ${data.low_balance < 0 ? "text-red-600" : "text-gray-900"}`}>{fmt(data.low_balance)}</p>
                <p className="text-xs text-gray-400">at day {data.low_day} ({fmtDate(data.series.find(s => s.day >= data.low_day)?.date || "")})</p>
              </div>
            </div>
          </div>

          {/* Balance chart (SVG sparkline) */}
          {data.series.length > 1 && (
            <div className="rounded-xl border border-gray-200 bg-white p-5">
              <p className="text-sm font-semibold text-gray-700 mb-4">Projected Balance</p>
              <div className="relative h-40">
                <svg viewBox={`0 0 ${data.series.length * 12} 160`} className="w-full h-full" preserveAspectRatio="none">
                  {(() => {
                    const vals = data.series.map(s => s.balance);
                    const min = Math.min(...vals, 0);
                    const max_ = Math.max(...vals, 1);
                    const range = max_ - min || 1;
                    const pts = data.series.map((s, i) => {
                      const x = i * 12 + 6;
                      const y = 160 - ((s.balance - min) / range) * 140 - 10;
                      return `${x},${y}`;
                    }).join(" ");
                    const zeroY = 160 - ((0 - min) / range) * 140 - 10;
                    return (
                      <>
                        {min < 0 && <line x1="0" y1={zeroY} x2={data.series.length * 12} y2={zeroY} stroke="#d1d5db" strokeWidth="1" strokeDasharray="4,4" />}
                        <polyline points={pts} fill="none" stroke="#3b82f6" strokeWidth="2" />
                        {data.series.map((s, i) => {
                          const x = i * 12 + 6;
                          const y = 160 - ((s.balance - min) / range) * 140 - 10;
                          const color = s.balance < 0 ? "#ef4444" : "#3b82f6";
                          return <circle key={i} cx={x} cy={y} r="3" fill={color} />;
                        })}
                      </>
                    );
                  })()}
                </svg>
                <div className="flex justify-between text-[10px] text-gray-400 mt-1">
                  {data.series.filter(s => [0, 30, 60, 90].includes(s.day)).map(s => (
                    <span key={s.day}>D+{s.day}</span>
                  ))}
                </div>
              </div>
            </div>
          )}

          {/* Upcoming inflows */}
          {data.upcoming_inflows.length > 0 && (
            <div className="rounded-xl border border-gray-200 bg-white p-5">
              <p className="text-sm font-semibold text-gray-700 mb-3 flex items-center gap-1.5">
                <Calendar className="h-4 w-4 text-green-500" /> Expected Inflows — Next 7 Days
              </p>
              <div className="space-y-2">
                {data.upcoming_inflows.map((inv, i) => (
                  <div key={i} className="flex items-center justify-between text-sm">
                    <div>
                      <span className="font-medium text-gray-900">{inv.customer || "—"}</span>
                      <span className="text-gray-500 ml-2">#{inv.invoice_number}</span>
                    </div>
                    <div className="text-right">
                      <span className="font-semibold text-green-700">+{fmt(inv.expected)}</span>
                      <span className="text-xs text-gray-400 ml-2">{fmtDate(inv.due_date)}</span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}
