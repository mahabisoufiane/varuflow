"use client";

import { useState, useEffect } from "react";
import { RoleGuard } from "@/components/app/RoleContext";
import { Link } from "@/i18n/navigation";
import { TrendingUp, Target, FileBarChart2, GitBranch, DollarSign, AlertTriangle, ArrowUpRight, ArrowDownRight, Crosshair } from "lucide-react";
import { api } from "@/lib/api-client";

interface PnlData {
  revenue: { invoiced: number; collected: number };
  expenses: { total: number };
  gross_profit: number;
  gross_margin_pct: number;
  net_income: number;
}
interface CashData {
  current_balance: number;
  balance_30d: number;
  cashout_day: number | null;
  daily_burn: number;
}
interface PipelineData {
  total_pipeline: number;
  months: Record<string, { deals: number; total_value: number; weighted_value: number }>;
}

function StatCard({ label, value, sub, icon: Icon, color = "blue", danger = false }: {
  label: string; value: string; sub?: string;
  icon: React.ComponentType<{className?: string}>;
  color?: string; danger?: boolean;
}) {
  return (
    <div className={`rounded-xl border bg-white p-5 ${danger ? "border-red-200 bg-red-50" : "border-gray-200"}`}>
      <div className="flex items-start justify-between">
        <div>
          <p className="text-xs font-medium text-gray-500 uppercase tracking-wide">{label}</p>
          <p className={`text-2xl font-bold mt-1 ${danger ? "text-red-600" : "text-gray-900"}`}>{value}</p>
          {sub && <p className="text-xs text-gray-500 mt-0.5">{sub}</p>}
        </div>
        <div className={`p-2 rounded-lg ${danger ? "bg-red-100" : `bg-${color}-100`}`}>
          <Icon className={`h-5 w-5 ${danger ? "text-red-500" : `text-${color}-500`}`} />
        </div>
      </div>
    </div>
  );
}

function CeoDashboardPageInner() {
  const [pnl, setPnl] = useState<PnlData | null>(null);
  const [cash, setCash] = useState<CashData | null>(null);
  const [pipeline, setPipeline] = useState<PipelineData | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([
      api.get<PnlData>("/api/ceo/pnl?period=ytd").then(d => setPnl(d)).catch(() => {}),
      api.get<CashData>("/api/ceo/cash-forecast?horizon_days=30").then(d => setCash(d)).catch(() => {}),
      api.get<PipelineData>("/api/crm/forecast?months=3").then(d => setPipeline(d)).catch(() => {}),
    ]).finally(() => setLoading(false));
  }, []);

  const fmt = (v: number) => v.toLocaleString("sv-SE", { maximumFractionDigits: 0 });

  const MODULES = [
    { href: "/ceo/cash-forecast", icon: DollarSign,    title: "Cash Flow Forecast",   desc: "30/60/90-day forward balance — will you have money?" },
    { href: "/crm/forecast",      icon: Crosshair,     title: "Sales Pipeline",        desc: "Weighted deal forecast — how much will we close next month?" },
    { href: "/ceo/kpi-goals",     icon: Target,         title: "KPI Goals",             desc: "Set revenue, margin and customer targets, track progress" },
    { href: "/ceo/board-report",  icon: FileBarChart2,  title: "Board Report",          desc: "Generate investor-ready PDF with P&L + KPIs" },
    { href: "/ceo/scenarios",     icon: GitBranch,      title: "Scenario Planning",     desc: "What if you hire 2 staff? Model cash impact" },
  ];

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold text-gray-900">CEO Dashboard</h1>
        <p className="mt-1 text-sm text-gray-500">Decision-making tools for owners and investors.</p>
      </div>

      {/* Top KPIs */}
      {!loading && (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          {pnl && (
            <>
              <StatCard
                label="Revenue YTD"
                value={`${fmt(pnl.revenue.invoiced)}`}
                sub={`${fmt(pnl.revenue.collected)} collected`}
                icon={TrendingUp} color="blue"
              />
              <StatCard
                label="Net Income YTD"
                value={`${fmt(pnl.net_income)}`}
                sub={`${pnl.gross_margin_pct}% gross margin`}
                icon={pnl.net_income >= 0 ? ArrowUpRight : ArrowDownRight}
                color={pnl.net_income >= 0 ? "green" : "red"}
                danger={pnl.net_income < 0}
              />
              <StatCard
                label="Total Expenses YTD"
                value={`${fmt(pnl.expenses.total)}`}
                icon={TrendingUp} color="amber"
              />
            </>
          )}
          {cash && (
            <StatCard
              label="Cash in 30 days"
              value={`${fmt(cash.balance_30d)}`}
              sub={cash.cashout_day ? `⚠ Cashout risk at day ${cash.cashout_day}` : `Burn: ${fmt(cash.daily_burn)}/day`}
              icon={DollarSign}
              danger={cash.cashout_day !== null && cash.cashout_day <= 30}
            />
          )}
          {pipeline && (
            <StatCard
              label="Sales Pipeline (3 mo)"
              value={`${fmt(pipeline.total_pipeline)}`}
              sub={`Weighted: ${fmt(Object.values(pipeline.months).reduce((a, m) => a + m.weighted_value, 0))}`}
              icon={Crosshair}
              color="purple"
            />
          )}
        </div>
      )}

      {/* Module cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        {MODULES.map(m => (
          <Link key={m.href} href={m.href}
            className="group rounded-xl border border-gray-200 bg-white p-5 hover:border-blue-300 hover:shadow-sm transition-all flex items-start gap-4">
            <div className="p-2.5 rounded-xl bg-blue-50 group-hover:bg-blue-100 transition-colors">
              <m.icon className="h-5 w-5 text-blue-600" />
            </div>
            <div>
              <p className="font-semibold text-gray-900 group-hover:text-blue-700">{m.title}</p>
              <p className="text-sm text-gray-500 mt-0.5">{m.desc}</p>
            </div>
          </Link>
        ))}
      </div>

      {/* Quick P&L period toggle */}
      {pnl && (
        <div className="rounded-xl border border-gray-200 bg-white p-5">
          <p className="text-sm font-semibold text-gray-700 mb-4">P&L Summary — Year to Date</p>
          <div className="space-y-2">
            {[
              { label: "Revenue (invoiced)", value: pnl.revenue.invoiced, positive: true },
              { label: "Less: Expenses", value: -pnl.expenses.total, positive: false },
              { label: "Gross Profit", value: pnl.gross_profit, positive: pnl.gross_profit >= 0 },
              { label: "Net Income", value: pnl.net_income, positive: pnl.net_income >= 0 },
            ].map(row => (
              <div key={row.label} className={`flex justify-between items-center px-3 py-2 rounded-lg ${
                row.label === "Net Income" ? "bg-gray-50 font-semibold" : ""
              }`}>
                <span className="text-sm text-gray-700">{row.label}</span>
                <span className={`text-sm font-medium tabular-nums ${row.positive ? "text-gray-900" : "text-red-600"}`}>
                  {row.value < 0 ? "−" : ""}{fmt(Math.abs(row.value))}
                </span>
              </div>
            ))}
          </div>
          <p className="text-xs text-gray-400 mt-3">
            From invoice + expense data · <Link href="/ceo/board-report" className="text-blue-500 hover:underline">Generate full board report →</Link>
          </p>
        </div>
      )}
    </div>
  );
}

export default function CeoDashboardPage() {
  return (
    <RoleGuard minRole="ADMIN">
      <CeoDashboardPageInner />
    </RoleGuard>
  );
}
