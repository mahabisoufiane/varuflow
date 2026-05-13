"use client";

/**
 * Financial Reports — P&L, Balance Sheet, Cash Flow
 *
 * Wires:
 *   GET /api/accounting/reports/pnl?from=&to=
 *   GET /api/accounting/reports/balance-sheet?as_of=
 *   GET /api/accounting/reports/cash-flow?from=&to=
 *
 * PRO+ plan required (backend enforces; frontend shows plan gate).
 */
import { useCallback, useState } from "react";
import { BarChart3, Download, Loader2, TrendingDown, TrendingUp } from "lucide-react";
import { toast } from "sonner";
import { api } from "@/lib/api-client";

// ─── Types ─────────────────────────────────────────────────────────────────

interface ReportLine {
  code: string;
  name: string;
  account_type: string;
  account_subtype: string | null;
  amount: string;
}

interface PnLReport {
  from_date: string;
  to_date: string;
  revenue_lines: ReportLine[];
  expense_lines: ReportLine[];
  total_revenue: string;
  total_expenses: string;
  net_income: string;
}

interface BalanceSheetReport {
  as_of: string;
  asset_lines: ReportLine[];
  liability_lines: ReportLine[];
  equity_lines: ReportLine[];
  total_assets: string;
  total_liabilities: string;
  total_equity: string;
  is_balanced: boolean;
}

interface CashFlowLine {
  source_type: string;
  amount: string;
  count: number;
}

interface CashFlowReport {
  from_date: string;
  to_date: string;
  cash_in: CashFlowLine[];
  cash_out: CashFlowLine[];
  net_cash_flow: string;
}

// ─── Helpers ────────────────────────────────────────────────────────────────

const fmt = (n: string | number) =>
  Number(n).toLocaleString("sv-SE", { minimumFractionDigits: 2, maximumFractionDigits: 2 });

const thisYear = new Date().getFullYear();
const defaultFrom = `${thisYear}-01-01`;
const defaultTo   = new Date().toISOString().slice(0, 10);

// ─── Component ──────────────────────────────────────────────────────────────

export default function ReportsPage() {
  const [tab, setTab] = useState<"pnl" | "balance" | "cashflow">("pnl");

  const [fromDate, setFromDate] = useState(defaultFrom);
  const [toDate,   setToDate]   = useState(defaultTo);
  const [asOf,     setAsOf]     = useState(defaultTo);

  const [pnl,      setPnl]      = useState<PnLReport | null>(null);
  const [balance,  setBalance]  = useState<BalanceSheetReport | null>(null);
  const [cashFlow, setCashFlow] = useState<CashFlowReport | null>(null);
  const [loading,  setLoading]  = useState(false);

  const loadPnL = useCallback(async () => {
    setLoading(true);
    try {
      const data = await api.get<PnLReport>(`/api/accounting/reports/pnl?from=${fromDate}&to=${toDate}`);
      setPnl(data);
    } catch (e: unknown) {
      toast.error(e instanceof Error ? e.message : "Failed to load P&L");
    } finally { setLoading(false); }
  }, [fromDate, toDate]);

  const loadBalance = useCallback(async () => {
    setLoading(true);
    try {
      const data = await api.get<BalanceSheetReport>(`/api/accounting/reports/balance-sheet?as_of=${asOf}`);
      setBalance(data);
    } catch (e: unknown) {
      toast.error(e instanceof Error ? e.message : "Failed to load Balance Sheet");
    } finally { setLoading(false); }
  }, [asOf]);

  const loadCashFlow = useCallback(async () => {
    setLoading(true);
    try {
      const data = await api.get<CashFlowReport>(`/api/accounting/reports/cash-flow?from=${fromDate}&to=${toDate}`);
      setCashFlow(data);
    } catch (e: unknown) {
      toast.error(e instanceof Error ? e.message : "Failed to load Cash Flow");
    } finally { setLoading(false); }
  }, [fromDate, toDate]);

  const tabs = [
    { id: "pnl" as const,      label: "Profit & Loss" },
    { id: "balance" as const,  label: "Balance Sheet" },
    { id: "cashflow" as const, label: "Cash Flow" },
  ];

  return (
    <div className="max-w-5xl mx-auto px-4 py-6 space-y-6">
      <div className="flex items-center gap-3">
        <BarChart3 className="w-6 h-6 text-indigo-400" />
        <div>
          <h1 className="text-xl font-bold vf-text-1">Financial Reports</h1>
          <p className="text-xs vf-text-m mt-0.5">P&L, Balance Sheet, and Cash Flow derived from the ledger</p>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 border-b border-white/10">
        {tabs.map(t => (
          <button key={t.id} onClick={() => setTab(t.id)}
            className={`px-4 py-2 text-sm font-medium rounded-t-lg transition-colors ${
              tab === t.id
                ? "bg-indigo-500/20 text-indigo-300 border-b-2 border-indigo-400"
                : "vf-text-m hover:text-white"
            }`}>
            {t.label}
          </button>
        ))}
      </div>

      {/* ── Profit & Loss ─────────────────────────────────────────────────── */}
      {tab === "pnl" && (
        <div className="space-y-4">
          <div className="flex items-end gap-3">
            <div>
              <label className="text-xs vf-text-m block mb-1">From</label>
              <input type="date" value={fromDate} onChange={e => setFromDate(e.target.value)}
                className="vf-input text-sm" />
            </div>
            <div>
              <label className="text-xs vf-text-m block mb-1">To</label>
              <input type="date" value={toDate} onChange={e => setToDate(e.target.value)}
                className="vf-input text-sm" />
            </div>
            <button onClick={loadPnL} className="vf-btn text-xs px-5 py-2">Run</button>
          </div>

          {loading ? (
            <div className="flex justify-center py-12"><Loader2 className="w-5 h-5 animate-spin vf-text-m" /></div>
          ) : pnl ? (
            <div className="space-y-4">
              {/* Net income banner */}
              <div className={`flex items-center justify-between rounded-xl px-5 py-4 ${
                Number(pnl.net_income) >= 0 ? "bg-emerald-500/15" : "bg-rose-500/15"
              }`}>
                <div>
                  <p className="text-xs vf-text-m">{pnl.from_date} – {pnl.to_date}</p>
                  <p className="text-lg font-bold mt-0.5 vf-text-1">Net Income</p>
                </div>
                <div className="text-right">
                  {Number(pnl.net_income) >= 0
                    ? <TrendingUp className="w-5 h-5 text-emerald-400 inline mr-2" />
                    : <TrendingDown className="w-5 h-5 text-rose-400 inline mr-2" />}
                  <span className={`text-2xl font-bold ${Number(pnl.net_income) >= 0 ? "text-emerald-400" : "text-rose-400"}`}>
                    {fmt(pnl.net_income)} SEK
                  </span>
                </div>
              </div>

              <div className="grid grid-cols-2 gap-4">
                {/* Revenue */}
                <div className="vf-section p-4">
                  <h3 className="text-sm font-semibold vf-text-1 mb-3">Revenue</h3>
                  <div className="space-y-2">
                    {pnl.revenue_lines.map(l => (
                      <div key={l.code} className="flex justify-between text-sm">
                        <span className="vf-text-m">{l.code} {l.name}</span>
                        <span className="font-mono text-emerald-400">{fmt(l.amount)}</span>
                      </div>
                    ))}
                    {pnl.revenue_lines.length === 0 && <p className="text-xs vf-text-m">No revenue entries</p>}
                  </div>
                  <div className="border-t border-white/10 mt-3 pt-3 flex justify-between font-semibold text-sm">
                    <span className="vf-text-1">Total Revenue</span>
                    <span className="font-mono text-emerald-400">{fmt(pnl.total_revenue)}</span>
                  </div>
                </div>

                {/* Expenses */}
                <div className="vf-section p-4">
                  <h3 className="text-sm font-semibold vf-text-1 mb-3">Expenses</h3>
                  <div className="space-y-2">
                    {pnl.expense_lines.map(l => (
                      <div key={l.code} className="flex justify-between text-sm">
                        <span className="vf-text-m">{l.code} {l.name}</span>
                        <span className="font-mono text-rose-400">{fmt(l.amount)}</span>
                      </div>
                    ))}
                    {pnl.expense_lines.length === 0 && <p className="text-xs vf-text-m">No expense entries</p>}
                  </div>
                  <div className="border-t border-white/10 mt-3 pt-3 flex justify-between font-semibold text-sm">
                    <span className="vf-text-1">Total Expenses</span>
                    <span className="font-mono text-rose-400">{fmt(pnl.total_expenses)}</span>
                  </div>
                </div>
              </div>
            </div>
          ) : (
            <div className="vf-section p-8 text-center vf-text-m text-sm">
              Select a date range and click Run to generate the P&L report.
            </div>
          )}
        </div>
      )}

      {/* ── Balance Sheet ──────────────────────────────────────────────────── */}
      {tab === "balance" && (
        <div className="space-y-4">
          <div className="flex items-end gap-3">
            <div>
              <label className="text-xs vf-text-m block mb-1">As of date</label>
              <input type="date" value={asOf} onChange={e => setAsOf(e.target.value)}
                className="vf-input text-sm" />
            </div>
            <button onClick={loadBalance} className="vf-btn text-xs px-5 py-2">Run</button>
          </div>

          {loading ? (
            <div className="flex justify-center py-12"><Loader2 className="w-5 h-5 animate-spin vf-text-m" /></div>
          ) : balance ? (
            <div className="space-y-4">
              <div className={`px-4 py-3 rounded-xl text-sm font-medium ${
                balance.is_balanced ? "bg-emerald-500/15 text-emerald-300" : "bg-rose-500/15 text-rose-300"
              }`}>
                {balance.is_balanced ? "✓ Balance sheet balances" : "⚠ Balance sheet does not balance"} — as of {balance.as_of}
              </div>

              <div className="grid grid-cols-2 gap-4">
                {/* Assets */}
                <div className="vf-section p-4">
                  <h3 className="text-sm font-bold vf-text-1 mb-3 uppercase tracking-wider text-xs">Assets</h3>
                  {balance.asset_lines.map(l => (
                    <div key={l.code} className="flex justify-between text-sm py-1">
                      <span className="vf-text-m">{l.code} {l.name}</span>
                      <span className="font-mono vf-text-1">{fmt(l.amount)}</span>
                    </div>
                  ))}
                  <div className="border-t border-white/10 mt-2 pt-2 flex justify-between font-semibold text-sm">
                    <span className="vf-text-1">Total Assets</span>
                    <span className="font-mono text-blue-400">{fmt(balance.total_assets)}</span>
                  </div>
                </div>

                <div className="space-y-4">
                  {/* Liabilities */}
                  <div className="vf-section p-4">
                    <h3 className="text-sm font-bold vf-text-1 mb-3 uppercase tracking-wider text-xs">Liabilities</h3>
                    {balance.liability_lines.map(l => (
                      <div key={l.code} className="flex justify-between text-sm py-1">
                        <span className="vf-text-m">{l.code} {l.name}</span>
                        <span className="font-mono vf-text-1">{fmt(l.amount)}</span>
                      </div>
                    ))}
                    <div className="border-t border-white/10 mt-2 pt-2 flex justify-between font-semibold text-sm">
                      <span className="vf-text-1">Total Liabilities</span>
                      <span className="font-mono text-rose-400">{fmt(balance.total_liabilities)}</span>
                    </div>
                  </div>

                  {/* Equity */}
                  <div className="vf-section p-4">
                    <h3 className="text-sm font-bold vf-text-1 mb-3 uppercase tracking-wider text-xs">Equity</h3>
                    {balance.equity_lines.map(l => (
                      <div key={l.code} className="flex justify-between text-sm py-1">
                        <span className="vf-text-m">{l.code} {l.name}</span>
                        <span className="font-mono vf-text-1">{fmt(l.amount)}</span>
                      </div>
                    ))}
                    <div className="border-t border-white/10 mt-2 pt-2 flex justify-between font-semibold text-sm">
                      <span className="vf-text-1">Total Equity</span>
                      <span className="font-mono text-purple-400">{fmt(balance.total_equity)}</span>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          ) : (
            <div className="vf-section p-8 text-center vf-text-m text-sm">
              Select a date and click Run.
            </div>
          )}
        </div>
      )}

      {/* ── Cash Flow ──────────────────────────────────────────────────────── */}
      {tab === "cashflow" && (
        <div className="space-y-4">
          <div className="flex items-end gap-3">
            <div>
              <label className="text-xs vf-text-m block mb-1">From</label>
              <input type="date" value={fromDate} onChange={e => setFromDate(e.target.value)}
                className="vf-input text-sm" />
            </div>
            <div>
              <label className="text-xs vf-text-m block mb-1">To</label>
              <input type="date" value={toDate} onChange={e => setToDate(e.target.value)}
                className="vf-input text-sm" />
            </div>
            <button onClick={loadCashFlow} className="vf-btn text-xs px-5 py-2">Run</button>
          </div>

          {loading ? (
            <div className="flex justify-center py-12"><Loader2 className="w-5 h-5 animate-spin vf-text-m" /></div>
          ) : cashFlow ? (
            <div className="space-y-4">
              {/* Net cash flow */}
              <div className={`flex items-center justify-between rounded-xl px-5 py-4 ${
                Number(cashFlow.net_cash_flow) >= 0 ? "bg-emerald-500/15" : "bg-rose-500/15"
              }`}>
                <p className="text-sm font-semibold vf-text-1">Net Cash Flow</p>
                <span className={`text-xl font-bold font-mono ${
                  Number(cashFlow.net_cash_flow) >= 0 ? "text-emerald-400" : "text-rose-400"
                }`}>
                  {Number(cashFlow.net_cash_flow) >= 0 ? "+" : ""}{fmt(cashFlow.net_cash_flow)} SEK
                </span>
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div className="vf-section p-4">
                  <h3 className="text-sm font-semibold vf-text-1 mb-3">Cash In</h3>
                  {cashFlow.cash_in.length === 0 && <p className="text-xs vf-text-m">None</p>}
                  {cashFlow.cash_in.map(l => (
                    <div key={l.source_type} className="flex justify-between text-sm py-1">
                      <span className="vf-text-m">{l.source_type} <span className="text-xs">({l.count}×)</span></span>
                      <span className="font-mono text-emerald-400">+{fmt(l.amount)}</span>
                    </div>
                  ))}
                </div>
                <div className="vf-section p-4">
                  <h3 className="text-sm font-semibold vf-text-1 mb-3">Cash Out</h3>
                  {cashFlow.cash_out.length === 0 && <p className="text-xs vf-text-m">None</p>}
                  {cashFlow.cash_out.map(l => (
                    <div key={l.source_type} className="flex justify-between text-sm py-1">
                      <span className="vf-text-m">{l.source_type} <span className="text-xs">({l.count}×)</span></span>
                      <span className="font-mono text-rose-400">-{fmt(l.amount)}</span>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          ) : (
            <div className="vf-section p-8 text-center vf-text-m text-sm">
              Select a date range and click Run.
            </div>
          )}
        </div>
      )}
    </div>
  );
}
