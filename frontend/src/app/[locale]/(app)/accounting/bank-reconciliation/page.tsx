"use client";
import { useEffect, useState, useCallback } from "react";
import {
  RefreshCw, CheckCircle2, AlertCircle, ArrowRight, Link2, X,
  FileText, Zap, MinusCircle, RotateCcw, BarChart3,
} from "lucide-react";
import { api } from "@/lib/api-client";
import { toast } from "sonner";
import styles from "./page.module.scss";
import { isPlanGateError, PlanGateBlock } from "@/components/ui/PlanGate";

// ── Types ─────────────────────────────────────────────────────────────────────

interface BankAccount { id: string; name: string; iban: string | null; currency: string; last_synced_at: string | null; }
interface Tx {
  id: string; transaction_date: string; amount: string; description: string;
  reference: string | null; status: string; matched_type: string | null; matched_id: string | null;
  matched_label?: string | null;
}
interface RecSummary {
  total_transactions: number; unmatched_count: number; matched_count: number;
  excluded_count: number; unmatched_total: string; period_balance: string;
}
interface ReportLine {
  id: string; transaction_date: string; amount: string; description: string;
  status: string; matched_type: string | null; matched_label: string | null;
}
interface RecReport {
  account_name: string; month: string; from_date: string; to_date: string;
  opening_balance: string; closing_balance: string; total_credits: string; total_debits: string;
  matched_count: number; unmatched_count: number; excluded_count: number;
  unmatched_items: ReportLine[]; matched_items: ReportLine[];
}
interface InvoiceSuggestion { id: string; invoice_number: string; total_sek: string; due_date: string; status: string; }

type Tab = "UNMATCHED" | "MATCHED" | "EXCLUDED";

// ── Helpers ───────────────────────────────────────────────────────────────────

function fmt(s: string | number) {
  const n = Number(s);
  return n.toLocaleString("sv-SE", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

const MONTHS = Array.from({ length: 12 }, (_, i) => {
  const d = new Date();
  d.setDate(1);
  d.setMonth(d.getMonth() - i);
  return d.toISOString().slice(0, 7);
});

// ── Transaction row ───────────────────────────────────────────────────────────

function TxRow({
  tx,
  onMatch,
  onUnmatch,
  onExclude,
  onCreateExpense,
}: {
  tx: Tx;
  onMatch: (tx: Tx) => void;
  onUnmatch: (id: string) => void;
  onExclude: (id: string) => void;
  onCreateExpense: (tx: Tx) => void;
}) {
  const amount = Number(tx.amount);
  const isCredit = amount >= 0;

  return (
    <div className={styles.txRow}>
      <div className={`w-1.5 h-10 rounded-full flex-shrink-0 ${isCredit ? "bg-green-400" : "bg-red-400"}`} />
      <div className="flex-1 min-w-0">
        <p className="text-sm text-gray-800 truncate">{tx.description}</p>
        <p className="text-xs text-gray-400">
          {tx.transaction_date}
          {tx.reference && ` · Ref: ${tx.reference}`}
          {tx.matched_label && <span className="text-blue-500 ml-1">→ {tx.matched_label}</span>}
          {tx.matched_type && !tx.matched_label && (
            <span className="text-blue-500 ml-1">→ {tx.matched_type}</span>
          )}
        </p>
      </div>
      <span className={`w-28 text-right flex-shrink-0 ${isCredit ? styles.amountCredit : styles.amountDebit}`}>
        {isCredit ? "+" : ""}{fmt(tx.amount)} SEK
      </span>
      {tx.status === "UNMATCHED" && (
        <div className="hidden group-hover:flex items-center gap-1 flex-shrink-0">
          {isCredit && (
            <button
              onClick={() => onMatch(tx)}
              title="Match to invoice"
              className="p-1.5 rounded hover:bg-blue-100 text-gray-400 hover:text-blue-600"
            >
              <Link2 size={14} />
            </button>
          )}
          {!isCredit && (
            <button
              onClick={() => onCreateExpense(tx)}
              title="Create expense"
              className="p-1.5 rounded hover:bg-orange-100 text-gray-400 hover:text-orange-600"
            >
              <FileText size={14} />
            </button>
          )}
          <button
            onClick={() => onExclude(tx.id)}
            title="Exclude / personal"
            className="p-1.5 rounded hover:bg-gray-200 text-gray-400 hover:text-gray-600"
          >
            <MinusCircle size={14} />
          </button>
        </div>
      )}
      {(tx.status === "MATCHED" || tx.status === "EXCLUDED") && (
        <button
          onClick={() => onUnmatch(tx.id)}
          title="Undo"
          className="opacity-0 group-hover:opacity-100 p-1.5 rounded hover:bg-gray-200 text-gray-400 flex-shrink-0"
        >
          <RotateCcw size={13} />
        </button>
      )}
    </div>
  );
}

// ── Match modal ───────────────────────────────────────────────────────────────

function MatchModal({
  tx,
  onClose,
  onMatched,
}: {
  tx: Tx;
  onClose: () => void;
  onMatched: () => void;
}) {
  const [search, setSearch] = useState("");
  const [results, setResults] = useState<InvoiceSuggestion[]>([]);
  const [loading, setLoading] = useState(false);

  const doSearch = useCallback(async (q: string) => {
    if (!q.trim() && !tx) return;
    setLoading(true);
    try {
      const data = await api.get<{ invoices: InvoiceSuggestion[] }>(
        `/api/invoicing/invoices?status=SENT&status=OVERDUE&search=${encodeURIComponent(q)}&limit=20`
      );
      setResults(data.invoices ?? []);
    } catch {
      setResults([]);
    } finally {
      setLoading(false);
    }
  }, [tx]);

  useEffect(() => {
    // Pre-load with amount-based suggestions
    doSearch("");
  }, [doSearch]);

  async function match(inv: InvoiceSuggestion) {
    try {
      await api.post(`/api/accounting/bank-transactions/${tx.id}/match`, {
        matched_type: "INVOICE",
        matched_id: inv.id,
      });
      toast.success(`Matched to ${inv.invoice_number}`);
      onMatched();
      onClose();
    } catch {
      toast.error("Match failed");
    }
  }

  return (
    <div className="fixed inset-0 bg-black/30 z-50 flex items-center justify-center p-4">
      <div className="bg-white rounded-2xl shadow-xl w-full max-w-md">
        <div className="flex items-center justify-between p-4 border-b">
          <div>
            <p className="text-sm font-semibold text-[#1a2332]">Match transaction to invoice</p>
            <p className="text-xs text-gray-400">{tx.description} · +{fmt(tx.amount)} SEK</p>
          </div>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600"><X size={16} /></button>
        </div>
        <div className="p-4 space-y-3">
          <input
            autoFocus
            type="text"
            placeholder="Search invoice number or customer…"
            value={search}
            onChange={(e) => { setSearch(e.target.value); doSearch(e.target.value); }}
            className="w-full border rounded px-3 py-2 text-sm focus:outline-none"
          />
          {loading && <p className="text-xs text-gray-400 text-center py-2">Searching…</p>}
          {!loading && results.length === 0 && (
            <p className="text-xs text-gray-400 text-center py-2">No matching invoices found</p>
          )}
          <div className="divide-y max-h-64 overflow-y-auto rounded border">
            {results.map((inv) => (
              <button
                key={inv.id}
                onClick={() => match(inv)}
                className="w-full flex items-center justify-between px-3 py-2.5 hover:bg-gray-50 text-left"
              >
                <div>
                  <p className="text-sm font-medium text-[#1a2332]">{inv.invoice_number}</p>
                  <p className="text-xs text-gray-400">Due {inv.due_date} · {inv.status}</p>
                </div>
                <span className="font-mono text-sm font-semibold text-green-600">{fmt(inv.total_sek)} SEK</span>
              </button>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

// ── Month-end Report ──────────────────────────────────────────────────────────

function ReportModal({ accountId, onClose }: { accountId: string; onClose: () => void }) {
  const [month, setMonth] = useState(MONTHS[0]);
  const [report, setReport] = useState<RecReport | null>(null);
  const [loading, setLoading] = useState(false);

  async function load() {
    setLoading(true);
    try {
      const d = await api.get<RecReport>(
        `/api/accounting/bank-accounts/${accountId}/reconciliation-report?month=${month}`
      );
      setReport(d);
    } catch {
      toast.error("Failed to load report");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { load(); }, [month]);

  return (
    <div className="fixed inset-0 bg-black/30 z-50 flex items-center justify-center p-4">
      <div className="bg-white rounded-2xl shadow-xl w-full max-w-2xl max-h-[90vh] flex flex-col">
        <div className="flex items-center justify-between p-4 border-b flex-shrink-0">
          <div>
            <p className="text-sm font-semibold text-[#1a2332]">Month-end Reconciliation Report</p>
            {report && <p className="text-xs text-gray-400">{report.account_name}</p>}
          </div>
          <div className="flex items-center gap-2">
            <select
              value={month}
              onChange={(e) => setMonth(e.target.value)}
              className="border rounded px-2 py-1 text-sm focus:outline-none"
            >
              {MONTHS.map((m) => <option key={m} value={m}>{m}</option>)}
            </select>
            <button onClick={onClose} className="text-gray-400 hover:text-gray-600"><X size={16} /></button>
          </div>
        </div>

        <div className="flex-1 overflow-y-auto p-4 space-y-4">
          {loading && <div className="h-32 rounded-xl bg-gray-100 animate-pulse" />}
          {report && !loading && (
            <>
              {/* Summary grid */}
              <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                {[
                  { label: "Opening Balance", value: report.opening_balance },
                  { label: "Total Credits", value: report.total_credits },
                  { label: "Total Debits", value: report.total_debits },
                  { label: "Closing Balance", value: report.closing_balance },
                ].map(({ label, value }) => (
                  <div key={label} className="bg-gray-50 rounded-lg p-3">
                    <p className="text-[10px] text-gray-400 uppercase tracking-wide mb-1">{label}</p>
                    <p className="font-mono text-sm font-semibold text-[#1a2332]">{fmt(value)}</p>
                  </div>
                ))}
              </div>

              {/* Status pills */}
              <div className="flex gap-2">
                <span className="text-xs px-2 py-1 rounded bg-green-100 text-green-700">{report.matched_count} matched</span>
                <span className="text-xs px-2 py-1 rounded bg-red-100 text-red-700">{report.unmatched_count} unmatched</span>
                <span className="text-xs px-2 py-1 rounded bg-gray-100 text-gray-600">{report.excluded_count} excluded</span>
              </div>

              {/* Unmatched items — the "difference explanation" */}
              {report.unmatched_items.length > 0 && (
                <div>
                  <p className="text-xs font-semibold text-red-600 uppercase tracking-wide mb-2">
                    Unmatched items — {report.unmatched_items.length} requiring attention
                  </p>
                  <div className="border rounded-lg divide-y">
                    {report.unmatched_items.map((line) => (
                      <div key={line.id} className="flex items-center justify-between px-3 py-2">
                        <div>
                          <p className="text-xs text-gray-700">{line.description}</p>
                          <p className="text-[10px] text-gray-400">{line.transaction_date}</p>
                        </div>
                        <span className={`font-mono text-xs font-semibold ${Number(line.amount) >= 0 ? "text-green-600" : "text-red-500"}`}>
                          {fmt(line.amount)} SEK
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Matched items summary */}
              {report.matched_items.length > 0 && (
                <div>
                  <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">
                    Matched transactions ({report.matched_items.length})
                  </p>
                  <div className="border rounded-lg divide-y max-h-64 overflow-y-auto">
                    {report.matched_items.map((line) => (
                      <div key={line.id} className="flex items-center justify-between px-3 py-2">
                        <div>
                          <p className="text-xs text-gray-700">{line.description}</p>
                          <p className="text-[10px] text-blue-400">
                            {line.transaction_date}
                            {line.matched_label && ` → ${line.matched_label}`}
                          </p>
                        </div>
                        <span className={`font-mono text-xs font-semibold ${Number(line.amount) >= 0 ? "text-green-600" : "text-red-500"}`}>
                          {fmt(line.amount)} SEK
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  );
}

// ── Page ──────────────────────────────────────────────────────────────────────

export default function BankReconciliationPage() {
  const [accounts, setAccounts] = useState<BankAccount[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [summary, setSummary] = useState<RecSummary | null>(null);
  const [txs, setTxs] = useState<Tx[]>([]);
  const [tab, setTab] = useState<Tab>("UNMATCHED");
  const [loading, setLoading] = useState(false);
  const [autoMatchLoading, setAutoMatchLoading] = useState(false);
  const [matchTx, setMatchTx] = useState<Tx | null>(null);
  const [createExpTx, setCreateExpTx] = useState<Tx | null>(null);
  const [showReport, setShowReport] = useState(false);

  // Expense creation input
  const [expDesc, setExpDesc] = useState("");
  const [expSaving, setExpSaving] = useState(false);

  const [planBlocked, setPlanBlocked] = useState<{ module: string; currentPlan: string } | null>(null);

  useEffect(() => {
    api.get<BankAccount[]>("/api/accounting/bank-accounts")
      .then((r) => {
        setAccounts(r);
        if (r.length > 0) setSelectedId(r[0].id);
      })
      .catch((err) => {
        if (isPlanGateError(err)) {
          setPlanBlocked({ module: (err as any).module ?? "finance", currentPlan: (err as any).currentPlan ?? "FREE" });
          return;
        }
        toast.error("Failed to load bank accounts");
      });
  }, []);

  const loadData = useCallback(async (id: string) => {
    setLoading(true);
    try {
      const [sum, txList] = await Promise.all([
        api.get<RecSummary>(`/api/accounting/bank-accounts/${id}/reconciliation`),
        api.get<Tx[]>(`/api/accounting/bank-accounts/${id}/transactions?per_page=200`),
      ]);
      setSummary(sum);
      setTxs(txList);
    } catch {
      toast.error("Failed to load transactions");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (selectedId) loadData(selectedId);
  }, [selectedId, loadData]);

  async function runAutoMatch() {
    if (!selectedId) return;
    setAutoMatchLoading(true);
    try {
      const res = await api.post<{ matched: number; unmatched_remaining: number }>(
        `/api/accounting/bank-accounts/${selectedId}/auto-match`, {}
      );
      toast.success(`Auto-matched ${res.matched} transaction${res.matched !== 1 ? "s" : ""}. ${res.unmatched_remaining} remaining.`);
      await loadData(selectedId);
    } catch {
      toast.error("Auto-match failed");
    } finally {
      setAutoMatchLoading(false);
    }
  }

  async function exclude(txId: string) {
    try {
      await api.post(`/api/accounting/bank-transactions/${txId}/exclude`, {});
      setTxs((prev) => prev.map((t) => t.id === txId ? { ...t, status: "EXCLUDED" } : t));
      setSummary((s) => s ? { ...s, unmatched_count: s.unmatched_count - 1, excluded_count: s.excluded_count + 1 } : s);
    } catch {
      toast.error("Failed to exclude");
    }
  }

  async function unmatch(txId: string) {
    try {
      const updated = await api.post<Tx>(`/api/accounting/bank-transactions/${txId}/unmatch`, {});
      setTxs((prev) => prev.map((t) => t.id === txId ? updated : t));
      if (selectedId) await loadData(selectedId);
    } catch {
      toast.error("Failed to undo");
    }
  }

  async function createExpense() {
    if (!createExpTx) return;
    setExpSaving(true);
    try {
      await api.post(`/api/accounting/bank-transactions/${createExpTx.id}/create-expense`, {
        description: expDesc || createExpTx.description,
      });
      toast.success("Expense created and transaction matched");
      setCreateExpTx(null);
      setExpDesc("");
      if (selectedId) await loadData(selectedId);
    } catch {
      toast.error("Failed to create expense");
    } finally {
      setExpSaving(false);
    }
  }

  const selected = accounts.find((a) => a.id === selectedId);
  const filteredTxs = txs.filter((t) => t.status === tab);
  const balanced = summary ? summary.unmatched_count === 0 : false;

  if (planBlocked) return <PlanGateBlock module={planBlocked.module} currentPlan={planBlocked.currentPlan} featureName="Bank Reconciliation" />;

  return (
      {/* Header */}
      <div className="flex items-start justify-between gap-4 flex-wrap">
        <div className="flex items-center gap-3">
          <RefreshCw size={20} className="text-[#1a2332]" />
          <div>
            <h1 className="text-xl font-bold text-[#1a2332]">Bank Reconciliation</h1>
            {selected && <p className="text-sm text-gray-400 mt-0.5">{selected.name}{selected.iban ? ` · ${selected.iban}` : ""}</p>}
          </div>
        </div>
        <div className="flex gap-2 flex-wrap">
          {/* Account selector */}
          {accounts.length > 1 && (
            <select
              value={selectedId ?? ""}
              onChange={(e) => setSelectedId(e.target.value)}
              className="border rounded px-2 py-1.5 text-sm focus:outline-none"
            >
              {accounts.map((a) => <option key={a.id} value={a.id}>{a.name}</option>)}
            </select>
          )}
          <button
            onClick={runAutoMatch}
            disabled={autoMatchLoading || !selectedId}
            className="flex items-center gap-1.5 px-3 py-1.5 bg-[#1a2332] text-white rounded text-sm hover:opacity-90 disabled:opacity-50"
          >
            <Zap size={13} />
            {autoMatchLoading ? "Matching…" : "Auto-match"}
          </button>
          {selectedId && (
            <button
              onClick={() => setShowReport(true)}
              className="flex items-center gap-1.5 px-3 py-1.5 border rounded text-sm hover:bg-gray-50"
            >
              <BarChart3 size={13} /> Month-end report
            </button>
          )}
        </div>
      </div>

      {/* Status banner */}
      {summary && (
        <div className={`flex items-center gap-3 rounded-xl px-4 py-3 border ${
          balanced ? "bg-green-50 border-green-200" : "bg-amber-50 border-amber-200"
        }`}>
          {balanced
            ? <CheckCircle2 size={17} className="text-green-600 flex-shrink-0" />
            : <AlertCircle size={17} className="text-amber-500 flex-shrink-0" />
          }
          <div className="flex-1">
            <p className={`text-xs font-semibold ${balanced ? "text-green-800" : "text-amber-800"}`}>
              {balanced ? "Fully reconciled" : `${summary.unmatched_count} unmatched transaction${summary.unmatched_count !== 1 ? "s" : ""}`}
            </p>
            {!balanced && (
              <p className="text-xs text-amber-700">
                Unmatched total: {fmt(summary.unmatched_total)} SEK · Run auto-match or categorise manually
              </p>
            )}
          </div>
          <div className="flex items-center gap-4 text-xs text-gray-500 flex-shrink-0">
            <span><span className="font-semibold text-green-600">{summary.matched_count}</span> matched</span>
            <span><span className="font-semibold text-amber-600">{summary.unmatched_count}</span> unmatched</span>
            <span><span className="font-semibold text-gray-500">{summary.excluded_count}</span> excluded</span>
          </div>
        </div>
      )}

      {/* Tab bar */}
      <div className="flex gap-1 border-b">
        {(["UNMATCHED", "MATCHED", "EXCLUDED"] as Tab[]).map((t) => {
          const count = txs.filter((tx) => tx.status === t).length;
          return (
            <button
              key={t}
              onClick={() => setTab(t)}
              className={`px-4 py-2 text-sm font-medium capitalize border-b-2 -mb-px transition-colors ${
                tab === t
                  ? "border-[#1a2332] text-[#1a2332]"
                  : "border-transparent text-gray-500 hover:text-gray-700"
              }`}
            >
              {t.charAt(0) + t.slice(1).toLowerCase()} {count > 0 && <span className="ml-1 text-[10px] bg-gray-200 rounded-full px-1.5">{count}</span>}
            </button>
          );
        })}
      </div>

      {/* Transaction list */}
      <div className="bg-white border rounded-xl overflow-hidden">
        {loading && (
          <div className="p-4 space-y-2">
            {[1, 2, 3].map((i) => <div key={i} className="h-12 rounded bg-gray-100 animate-pulse" />)}
          </div>
        )}
        {!loading && filteredTxs.length === 0 && (
          <p className="text-sm text-gray-400 text-center py-12">
            {tab === "UNMATCHED" ? "No unmatched transactions — all clear!" :
             tab === "MATCHED" ? "No matched transactions yet." :
             "No excluded transactions."}
          </p>
        )}
        {!loading && filteredTxs.map((tx) => (
          <TxRow
            key={tx.id}
            tx={tx}
            onMatch={setMatchTx}
            onUnmatch={unmatch}
            onExclude={exclude}
            onCreateExpense={setCreateExpTx}
          />
        ))}
      </div>

      {/* Match modal */}
      {matchTx && (
        <MatchModal
          tx={matchTx}
          onClose={() => setMatchTx(null)}
          onMatched={() => selectedId && loadData(selectedId)}
        />
      )}

      {/* Create expense modal */}
      {createExpTx && (
        <div className="fixed inset-0 bg-black/30 z-50 flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl shadow-xl w-full max-w-sm">
            <div className="flex items-center justify-between p-4 border-b">
              <p className="text-sm font-semibold text-[#1a2332]">Create expense from transaction</p>
              <button onClick={() => { setCreateExpTx(null); setExpDesc(""); }} className="text-gray-400">
                <X size={16} />
              </button>
            </div>
            <div className="p-4 space-y-3">
              <div className="bg-gray-50 rounded-lg px-3 py-2">
                <p className="text-xs text-gray-500">{createExpTx.description}</p>
                <p className="font-mono font-semibold text-red-500 text-sm">{fmt(createExpTx.amount)} SEK</p>
                <p className="text-xs text-gray-400">{createExpTx.transaction_date}</p>
              </div>
              <div>
                <label className="block text-xs text-gray-400 mb-1">Description (optional)</label>
                <input
                  type="text"
                  value={expDesc}
                  onChange={(e) => setExpDesc(e.target.value)}
                  placeholder={createExpTx.description}
                  className="w-full border rounded px-2 py-1.5 text-sm focus:outline-none"
                />
              </div>
              <div className="flex gap-2 justify-end">
                <button onClick={() => { setCreateExpTx(null); setExpDesc(""); }} className="px-3 py-1.5 border rounded text-sm">
                  Cancel
                </button>
                <button
                  onClick={createExpense}
                  disabled={expSaving}
                  className="px-4 py-1.5 bg-[#1a2332] text-white rounded text-sm disabled:opacity-50"
                >
                  {expSaving ? "Creating…" : "Create expense"}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Month-end report modal */}
      {showReport && selectedId && (
        <ReportModal accountId={selectedId} onClose={() => setShowReport(false)} />
      )}

      {/* Empty accounts state */}
      {!loading && accounts.length === 0 && (
        <div className="text-center py-16 space-y-2">
          <RefreshCw size={32} className="mx-auto text-gray-300" />
          <p className="text-sm text-gray-500 font-medium">No bank accounts connected</p>
          <p className="text-xs text-gray-400">
            Go to <span className="text-blue-500">Settings → Bank Feed</span> to connect a bank account or import a CSV statement.
          </p>
        </div>
      )}
    </div>
  );
}
