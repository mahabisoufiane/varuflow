"use client";

/**
 * Accounting — Ledger & Chart of Accounts
 *
 * Tabs:
 *   Accounts     — chart of accounts (BAS 2024 seeded on first load)
 *   Journal      — paginated journal entries with debit/credit lines
 *   Trial Balance — per-account totals, checks books balance
 *   Backfill     — one-shot import of existing invoices/payments/expenses
 *
 * Wires: GET  /api/accounting/accounts
 *        POST /api/accounting/accounts
 *        PATCH /api/accounting/accounts/{code}
 *        GET  /api/accounting/journal
 *        POST /api/accounting/journal
 *        GET  /api/accounting/trial-balance
 *        POST /api/accounting/backfill
 */
import { useCallback, useEffect, useState } from "react";
import { RoleGuard } from "@/components/app/RoleContext";
import { BookOpen, ChevronDown, ChevronUp, Loader2, Plus, RefreshCw } from "lucide-react";
import { toast } from "sonner";
import { api } from "@/lib/api-client";
import styles from "./page.module.scss";
import { isPlanGateError, PlanGateBlock } from "@/components/ui/PlanGate";

// ─── Types ─────────────────────────────────────────────────────────────────

type AccountType = "ASSET" | "LIABILITY" | "EQUITY" | "REVENUE" | "EXPENSE";

interface Account {
  code: string;
  name: string;
  account_type: AccountType;
  account_subtype: string | null;
  is_system: boolean;
  is_active: boolean;
}

interface JournalLine {
  id: string;
  account_code: string;
  debit: string;
  credit: string;
  memo: string | null;
  currency: string;
}

interface JournalEntry {
  id: string;
  entry_date: string;
  description: string;
  source_type: string | null;
  reference: string | null;
  is_posted: boolean;
  created_at: string;
  lines: JournalLine[];
}

interface JournalPage {
  total: number;
  page: number;
  per_page: number;
  items: JournalEntry[];
}

interface TrialBalanceLine {
  code: string;
  name: string;
  account_type: AccountType;
  debit_total: string;
  credit_total: string;
  balance: string;
}

interface TrialBalance {
  as_of: string;
  lines: TrialBalanceLine[];
  total_debits: string;
  total_credits: string;
  is_balanced: boolean;
}

interface BackfillResult {
  invoices_posted: number;
  payments_posted: number;
  expenses_posted: number;
  skipped: number;
}

// ─── Helpers ────────────────────────────────────────────────────────────────

const TYPE_COLORS: Record<AccountType, string> = {
  ASSET:     "bg-blue-500/15 text-blue-400",
  LIABILITY: "bg-rose-500/15 text-rose-400",
  EQUITY:    "bg-purple-500/15 text-purple-400",
  REVENUE:   "bg-emerald-500/15 text-emerald-400",
  EXPENSE:   "bg-amber-500/15 text-amber-400",
};

const fmt = (n: string | number) =>
  Number(n).toLocaleString("sv-SE", { minimumFractionDigits: 2, maximumFractionDigits: 2 });

// ─── Component ──────────────────────────────────────────────────────────────

function AccountingPageInner() {
  const [tab, setTab] = useState<"accounts" | "journal" | "trial" | "backfill">("accounts");

  // Accounts
  const [accounts, setAccounts] = useState<Account[]>([]);
  const [acctLoading, setAcctLoading] = useState(true);
  const [showAddAccount, setShowAddAccount] = useState(false);
  const [newCode, setNewCode] = useState("");
  const [newName, setNewName] = useState("");
  const [newType, setNewType] = useState<AccountType>("ASSET");

  // Journal
  const [journal, setJournal] = useState<JournalPage | null>(null);
  const [jPage, setJPage] = useState(1);
  const [jLoading, setJLoading] = useState(false);
  const [expandedEntry, setExpandedEntry] = useState<string | null>(null);
  const [showAddEntry, setShowAddEntry] = useState(false);
  const [manualEntry, setManualEntry] = useState({
    entry_date: new Date().toISOString().slice(0, 10),
    description: "",
    lines: [
      { account_code: "", debit: "0", credit: "0", memo: "" },
      { account_code: "", debit: "0", credit: "0", memo: "" },
    ],
  });

  // Trial balance
  const [trial, setTrial] = useState<TrialBalance | null>(null);
  const [trialAsOf, setTrialAsOf] = useState(new Date().toISOString().slice(0, 10));
  const [trialLoading, setTrialLoading] = useState(false);

  // Backfill
  const [backfillLoading, setBackfillLoading] = useState(false);
  const [backfillResult, setBackfillResult] = useState<BackfillResult | null>(null);

  const [planBlocked, setPlanBlocked] = useState<{ module: string; currentPlan: string } | null>(null);

  // ── Data loaders ──────────────────────────────────────────────────────────

  const loadAccounts = useCallback(async () => {
    setAcctLoading(true);
    try {
      const data = await api.get<Account[]>("/api/accounting/accounts");
      setAccounts(data);
    } catch (err) {
      if (isPlanGateError(err)) {
        setPlanBlocked({ module: (err as any).module ?? "finance", currentPlan: (err as any).currentPlan ?? "FREE" });
        return;
      }
      toast.error(err instanceof Error ? err.message : "Failed to load accounts");
    } finally {
      setAcctLoading(false);
    }
  }, []);

  const loadJournal = useCallback(async (page = 1) => {
    setJLoading(true);
    try {
      const data = await api.get<JournalPage>(`/api/accounting/journal?page=${page}&per_page=25`);
      setJournal(data);
      setJPage(page);
    } catch (e: unknown) {
      toast.error(e instanceof Error ? e.message : "Failed to load journal");
    } finally {
      setJLoading(false);
    }
  }, []);

  const loadTrial = useCallback(async (asOf: string) => {
    setTrialLoading(true);
    try {
      const data = await api.get<TrialBalance>(`/api/accounting/trial-balance?as_of=${asOf}`);
      setTrial(data);
    } catch (e: unknown) {
      toast.error(e instanceof Error ? e.message : "Failed to load trial balance");
    } finally {
      setTrialLoading(false);
    }
  }, []);

  useEffect(() => { loadAccounts(); }, [loadAccounts]);

  useEffect(() => {
    if (tab === "journal" && !journal) loadJournal(1);
    if (tab === "trial" && !trial) loadTrial(trialAsOf);
  }, [tab, journal, trial, loadJournal, loadTrial, trialAsOf]);

  // ── Mutations ─────────────────────────────────────────────────────────────

  const handleAddAccount = async () => {
    if (!newCode.trim() || !newName.trim()) { toast.error("Code and name required"); return; }
    try {
      await api.post("/api/accounting/accounts", {
        code: newCode.trim(),
        name: newName.trim(),
        account_type: newType,
      });
      toast.success(`Account ${newCode} added`);
      setShowAddAccount(false);
      setNewCode(""); setNewName(""); setNewType("ASSET");
      await loadAccounts();
    } catch (e: unknown) {
      toast.error(e instanceof Error ? e.message : "Failed to add account");
    }
  };

  const handleToggleActive = async (code: string, current: boolean) => {
    try {
      await api.patch(`/api/accounting/accounts/${code}`, { is_active: !current });
      toast.success(current ? "Account deactivated" : "Account activated");
      await loadAccounts();
    } catch (e: unknown) {
      toast.error(e instanceof Error ? e.message : "Failed to update account");
    }
  };

  const handlePostManual = async () => {
    if (!manualEntry.description.trim()) { toast.error("Description required"); return; }
    const lines = manualEntry.lines.filter(l => l.account_code.trim());
    if (lines.length < 2) { toast.error("At least 2 lines required"); return; }
    try {
      await api.post("/api/accounting/journal", {
        entry_date: manualEntry.entry_date,
        description: manualEntry.description,
        lines: lines.map(l => ({
          account_code: l.account_code.trim(),
          debit: parseFloat(l.debit) || 0,
          credit: parseFloat(l.credit) || 0,
          memo: l.memo || null,
          currency: "SEK",
        })),
      });
      toast.success("Journal entry posted");
      setShowAddEntry(false);
      setManualEntry({
        entry_date: new Date().toISOString().slice(0, 10),
        description: "",
        lines: [
          { account_code: "", debit: "0", credit: "0", memo: "" },
          { account_code: "", debit: "0", credit: "0", memo: "" },
        ],
      });
      await loadJournal(1);
    } catch (e: unknown) {
      toast.error(e instanceof Error ? e.message : "Journal entry must balance and have valid account codes");
    }
  };

  const handleBackfill = async () => {
    if (!confirm("This will import all existing invoices, payments, and approved expenses into the ledger. Continue?")) return;
    setBackfillLoading(true);
    try {
      const result = await api.post<BackfillResult>("/api/accounting/backfill", {});
      setBackfillResult(result);
      toast.success(`Backfill complete — ${result.invoices_posted + result.payments_posted + result.expenses_posted} entries posted`);
    } catch (e: unknown) {
      toast.error(e instanceof Error ? e.message : "Backfill failed");
    } finally {
      setBackfillLoading(false);
    }
  };

  // ── Render ────────────────────────────────────────────────────────────────

  const tabs: Array<{ id: typeof tab; label: string }> = [
    { id: "accounts", label: "Chart of Accounts" },
    { id: "journal",  label: "Journal" },
    { id: "trial",    label: "Trial Balance" },
    { id: "backfill", label: "Backfill" },
  ];

  if (planBlocked) return <PlanGateBlock module={planBlocked.module} currentPlan={planBlocked.currentPlan} featureName="Accounting" />;

  return (
    <div className="max-w-6xl mx-auto px-4 py-6 space-y-6">
      {/* Header */}
      <div className="flex items-center gap-3">
        <BookOpen className="w-6 h-6 text-indigo-400" />
        <div>
          <h1 className="text-xl font-bold vf-text-1">Accounting Ledger</h1>
          <p className="text-xs vf-text-m mt-0.5">Double-entry bookkeeping powered by BAS 2024</p>
        </div>
      </div>

      {/* Tabs */}
      <div className={styles.tabBar}>
        {tabs.map(t => (
          <button
            key={t.id}
            onClick={() => setTab(t.id)}
            className={`${styles.tab} ${tab === t.id ? styles.tabActive : ""}`}
          >
            {t.label}
          </button>
        ))}
      </div>

      {/* ── Accounts tab ───────────────────────────────────────────────────── */}
      {tab === "accounts" && (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <p className="text-sm vf-text-m">{accounts.length} accounts</p>
            <div className="flex gap-2">
              <button onClick={loadAccounts} className="vf-btn-ghost text-xs px-3 py-1.5">
                <RefreshCw className="w-3.5 h-3.5 mr-1.5 inline" />Refresh
              </button>
              <button onClick={() => setShowAddAccount(!showAddAccount)} className="vf-btn text-xs px-3 py-1.5">
                <Plus className="w-3.5 h-3.5 mr-1.5 inline" />Add Account
              </button>
            </div>
          </div>

          {showAddAccount && (
            <div className="vf-section p-4 space-y-3">
              <p className="text-sm font-semibold vf-text-1">New Account</p>
              <div className="grid grid-cols-3 gap-3">
                <div>
                  <label className="text-xs vf-text-m block mb-1">BAS Code</label>
                  <input value={newCode} onChange={e => setNewCode(e.target.value)}
                    placeholder="e.g. 5010" className="vf-input text-sm w-full" />
                </div>
                <div>
                  <label className="text-xs vf-text-m block mb-1">Name</label>
                  <input value={newName} onChange={e => setNewName(e.target.value)}
                    placeholder="Account name" className="vf-input text-sm w-full" />
                </div>
                <div>
                  <label className="text-xs vf-text-m block mb-1">Type</label>
                  <select value={newType} onChange={e => setNewType(e.target.value as AccountType)}
                    className="vf-input text-sm w-full">
                    {(["ASSET","LIABILITY","EQUITY","REVENUE","EXPENSE"] as AccountType[]).map(t => (
                      <option key={t} value={t}>{t}</option>
                    ))}
                  </select>
                </div>
              </div>
              <div className="flex justify-end gap-2">
                <button onClick={() => setShowAddAccount(false)} className="vf-btn-ghost text-xs px-3 py-1.5">Cancel</button>
                <button onClick={handleAddAccount} className="vf-btn text-xs px-3 py-1.5">Save</button>
              </div>
            </div>
          )}

          {acctLoading ? (
            <div className="flex justify-center py-12"><Loader2 className="w-5 h-5 animate-spin vf-text-m" /></div>
          ) : (
            <div className="vf-section overflow-hidden">
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-xs vf-text-m border-b border-white/10">
                    <th className="text-left px-4 py-3 font-medium">Code</th>
                    <th className="text-left px-4 py-3 font-medium">Name</th>
                    <th className="text-left px-4 py-3 font-medium">Type</th>
                    <th className="text-left px-4 py-3 font-medium">Subtype</th>
                    <th className="text-right px-4 py-3 font-medium">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-white/5">
                  {accounts.map(acct => (
                    <tr key={acct.code} className={`hover:bg-white/5 transition-colors ${!acct.is_active ? "opacity-40" : ""}`}>
                      <td className="px-4 py-3 font-mono font-semibold vf-text-1 text-sm">{acct.code}</td>
                      <td className="px-4 py-3 vf-text-1">{acct.name}</td>
                      <td className="px-4 py-3">
                        <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${TYPE_COLORS[acct.account_type]}`}>
                          {acct.account_type}
                        </span>
                      </td>
                      <td className="px-4 py-3 vf-text-m text-xs">{acct.account_subtype ?? "—"}</td>
                      <td className="px-4 py-3 text-right">
                        {!acct.is_system ? (
                          <button
                            onClick={() => handleToggleActive(acct.code, acct.is_active)}
                            className="text-xs vf-text-m hover:text-white transition-colors"
                          >
                            {acct.is_active ? "Deactivate" : "Activate"}
                          </button>
                        ) : (
                          <span className="text-xs vf-text-m">System</span>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {/* ── Journal tab ────────────────────────────────────────────────────── */}
      {tab === "journal" && (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <p className="text-sm vf-text-m">
              {journal ? `${journal.total} entries total` : "Loading..."}
            </p>
            <div className="flex gap-2">
              <button onClick={() => loadJournal(jPage)} className="vf-btn-ghost text-xs px-3 py-1.5">
                <RefreshCw className="w-3.5 h-3.5 mr-1.5 inline" />Refresh
              </button>
              <button onClick={() => setShowAddEntry(!showAddEntry)} className="vf-btn text-xs px-3 py-1.5">
                <Plus className="w-3.5 h-3.5 mr-1.5 inline" />Manual Entry
              </button>
            </div>
          </div>

          {showAddEntry && (
            <div className="vf-section p-4 space-y-4">
              <p className="text-sm font-semibold vf-text-1">Manual Journal Entry</p>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="text-xs vf-text-m block mb-1">Date</label>
                  <input type="date" value={manualEntry.entry_date}
                    onChange={e => setManualEntry(m => ({ ...m, entry_date: e.target.value }))}
                    className="vf-input text-sm w-full" />
                </div>
                <div>
                  <label className="text-xs vf-text-m block mb-1">Description</label>
                  <input value={manualEntry.description}
                    onChange={e => setManualEntry(m => ({ ...m, description: e.target.value }))}
                    placeholder="e.g. Opening entry" className="vf-input text-sm w-full" />
                </div>
              </div>
              <div>
                <p className="text-xs vf-text-m mb-2">Lines (must balance)</p>
                <div className="space-y-2">
                  {manualEntry.lines.map((line, i) => (
                    <div key={i} className="grid grid-cols-4 gap-2">
                      <input value={line.account_code}
                        onChange={e => setManualEntry(m => {
                          const lines = [...m.lines]; lines[i] = { ...lines[i], account_code: e.target.value }; return { ...m, lines };
                        })}
                        placeholder="Account code" className="vf-input text-xs" />
                      <input value={line.debit} type="number" min="0"
                        onChange={e => setManualEntry(m => {
                          const lines = [...m.lines]; lines[i] = { ...lines[i], debit: e.target.value }; return { ...m, lines };
                        })}
                        placeholder="Debit" className="vf-input text-xs" />
                      <input value={line.credit} type="number" min="0"
                        onChange={e => setManualEntry(m => {
                          const lines = [...m.lines]; lines[i] = { ...lines[i], credit: e.target.value }; return { ...m, lines };
                        })}
                        placeholder="Credit" className="vf-input text-xs" />
                      <input value={line.memo}
                        onChange={e => setManualEntry(m => {
                          const lines = [...m.lines]; lines[i] = { ...lines[i], memo: e.target.value }; return { ...m, lines };
                        })}
                        placeholder="Memo (optional)" className="vf-input text-xs" />
                    </div>
                  ))}
                </div>
                <button
                  onClick={() => setManualEntry(m => ({ ...m, lines: [...m.lines, { account_code: "", debit: "0", credit: "0", memo: "" }] }))}
                  className="mt-2 text-xs vf-text-m hover:text-white"
                >
                  + Add line
                </button>
              </div>
              <div className="flex justify-end gap-2">
                <button onClick={() => setShowAddEntry(false)} className="vf-btn-ghost text-xs px-3 py-1.5">Cancel</button>
                <button onClick={handlePostManual} className="vf-btn text-xs px-3 py-1.5">Post Entry</button>
              </div>
            </div>
          )}

          {jLoading ? (
            <div className="flex justify-center py-12"><Loader2 className="w-5 h-5 animate-spin vf-text-m" /></div>
          ) : journal && journal.items.length === 0 ? (
            <div className="vf-section p-8 text-center vf-text-m text-sm">
              No journal entries yet. Use the Backfill tab to import existing data.
            </div>
          ) : (
            <div className="space-y-2">
              {journal?.items.map(entry => (
                <div key={entry.id} className="vf-section overflow-hidden">
                  <div
                    className={styles.entryHeader}
                    onClick={() => setExpandedEntry(expandedEntry === entry.id ? null : entry.id)}
                  >
                    <div className="flex items-center gap-4">
                      <span className="font-mono text-xs vf-text-m w-24 shrink-0">{entry.entry_date}</span>
                      <span className="text-sm vf-text-1 font-medium">{entry.description}</span>
                      {entry.source_type && (
                        <span className={styles.entryBadge}>{entry.source_type}</span>
                      )}
                      {entry.reference && (
                        <span className="text-xs vf-text-m">{entry.reference}</span>
                      )}
                    </div>
                    {expandedEntry === entry.id
                      ? <ChevronUp className="w-4 h-4 vf-text-m" />
                      : <ChevronDown className="w-4 h-4 vf-text-m" />}
                  </div>
                  {expandedEntry === entry.id && (
                    <div className={styles.entryDetail}>
                      <table className={styles.journalTable}>
                        <thead>
                          <tr className="vf-text-m border-b border-white/5">
                            <th className="text-left py-1.5 font-medium">Account</th>
                            <th className="text-right py-1.5 font-medium">Debit</th>
                            <th className="text-right py-1.5 font-medium">Credit</th>
                            <th className="text-left py-1.5 pl-4 font-medium">Memo</th>
                          </tr>
                        </thead>
                        <tbody className="divide-y divide-white/5">
                          {entry.lines.map(line => (
                            <tr key={line.id}>
                              <td className="py-1.5 font-mono vf-text-1 font-semibold">{line.account_code}</td>
                              <td className="py-1.5 text-right font-mono">{Number(line.debit) > 0 ? fmt(line.debit) : "—"}</td>
                              <td className="py-1.5 text-right font-mono">{Number(line.credit) > 0 ? fmt(line.credit) : "—"}</td>
                              <td className="py-1.5 pl-4 vf-text-m">{line.memo ?? "—"}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  )}
                </div>
              ))}

              {journal && journal.total > journal.per_page && (
                <div className="flex justify-center gap-3 pt-2">
                  <button
                    disabled={jPage <= 1}
                    onClick={() => loadJournal(jPage - 1)}
                    className="vf-btn-ghost text-xs px-3 py-1.5 disabled:opacity-40"
                  >← Prev</button>
                  <span className="text-xs vf-text-m self-center">
                    {jPage} / {Math.ceil(journal.total / journal.per_page)}
                  </span>
                  <button
                    disabled={jPage >= Math.ceil(journal.total / journal.per_page)}
                    onClick={() => loadJournal(jPage + 1)}
                    className="vf-btn-ghost text-xs px-3 py-1.5 disabled:opacity-40"
                  >Next →</button>
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {/* ── Trial Balance tab ──────────────────────────────────────────────── */}
      {tab === "trial" && (
        <div className="space-y-4">
          <div className="flex items-center gap-3">
            <div>
              <label className="text-xs vf-text-m block mb-1">As of date</label>
              <input type="date" value={trialAsOf}
                onChange={e => setTrialAsOf(e.target.value)}
                className="vf-input text-sm" />
            </div>
            <button onClick={() => loadTrial(trialAsOf)} className="vf-btn text-xs px-4 py-2 mt-4">
              Run
            </button>
          </div>

          {trialLoading ? (
            <div className="flex justify-center py-12"><Loader2 className="w-5 h-5 animate-spin vf-text-m" /></div>
          ) : trial ? (
            <div className="space-y-4">
              <div className={`flex items-center gap-3 px-4 py-3 rounded-xl text-sm font-medium ${
                trial.is_balanced
                  ? "bg-emerald-500/15 text-emerald-300"
                  : "bg-rose-500/15 text-rose-300"
              }`}>
                {trial.is_balanced ? "✓ Books balance" : "⚠ Books do not balance"} — as of {trial.as_of}
              </div>

              <div className="vf-section overflow-hidden">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="text-xs vf-text-m border-b border-white/10">
                      <th className="text-left px-4 py-3 font-medium">Code</th>
                      <th className="text-left px-4 py-3 font-medium">Account</th>
                      <th className="text-left px-4 py-3 font-medium">Type</th>
                      <th className="text-right px-4 py-3 font-medium">Debit</th>
                      <th className="text-right px-4 py-3 font-medium">Credit</th>
                      <th className="text-right px-4 py-3 font-medium">Balance</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-white/5">
                    {trial.lines.map(line => (
                      <tr key={line.code} className="hover:bg-white/5 transition-colors">
                        <td className="px-4 py-2.5 font-mono font-semibold vf-text-1 text-xs">{line.code}</td>
                        <td className="px-4 py-2.5 vf-text-1 text-sm">{line.name}</td>
                        <td className="px-4 py-2.5">
                          <span className={`text-xs px-2 py-0.5 rounded-full ${TYPE_COLORS[line.account_type]}`}>
                            {line.account_type}
                          </span>
                        </td>
                        <td className="px-4 py-2.5 text-right font-mono text-xs">{fmt(line.debit_total)}</td>
                        <td className="px-4 py-2.5 text-right font-mono text-xs">{fmt(line.credit_total)}</td>
                        <td className={`px-4 py-2.5 text-right font-mono text-xs font-semibold ${
                          Number(line.balance) >= 0 ? "text-emerald-400" : "text-rose-400"
                        }`}>
                          {fmt(Math.abs(Number(line.balance)))}
                          {Number(line.balance) < 0 ? " CR" : " DR"}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                  <tfoot>
                    <tr className="border-t-2 border-white/20 font-semibold vf-text-1">
                      <td colSpan={3} className="px-4 py-3 text-sm">Total</td>
                      <td className="px-4 py-3 text-right font-mono text-sm">{fmt(trial.total_debits)}</td>
                      <td className="px-4 py-3 text-right font-mono text-sm">{fmt(trial.total_credits)}</td>
                      <td />
                    </tr>
                  </tfoot>
                </table>
              </div>
            </div>
          ) : (
            <div className="vf-section p-8 text-center vf-text-m text-sm">
              Select a date and click Run to generate the trial balance.
            </div>
          )}
        </div>
      )}

      {/* ── Backfill tab ───────────────────────────────────────────────────── */}
      {tab === "backfill" && (
        <div className="space-y-4 max-w-xl">
          <div className="vf-section p-5 space-y-4">
            <h2 className="font-semibold vf-text-1">Import Existing Data into Ledger</h2>
            <p className="text-sm vf-text-m leading-relaxed">
              This one-time import will create journal entries for all existing invoices
              (SENT / PAID / OVERDUE), recorded payments, and approved expenses.
            </p>
            <ul className="text-xs vf-text-m space-y-1 list-disc list-inside">
              <li>Safe to run multiple times — already-posted entries are skipped</li>
              <li>Does not modify any existing invoice or expense data</li>
              <li>Required before P&L reports and trial balance show full history</li>
            </ul>
            <button
              onClick={handleBackfill}
              disabled={backfillLoading}
              className="vf-btn text-sm px-5 py-2 disabled:opacity-60"
            >
              {backfillLoading ? (
                <><Loader2 className="w-4 h-4 animate-spin inline mr-2" />Running…</>
              ) : "Run Backfill"}
            </button>
          </div>

          {backfillResult && (
            <div className="vf-section p-5">
              <p className="text-sm font-semibold vf-text-1 mb-3">Last Backfill Result</p>
              <div className="grid grid-cols-2 gap-3 text-sm">
                <div className="bg-emerald-500/10 rounded-lg p-3">
                  <p className="text-xs vf-text-m">Invoices posted</p>
                  <p className="text-lg font-bold text-emerald-400">{backfillResult.invoices_posted}</p>
                </div>
                <div className="bg-emerald-500/10 rounded-lg p-3">
                  <p className="text-xs vf-text-m">Payments posted</p>
                  <p className="text-lg font-bold text-emerald-400">{backfillResult.payments_posted}</p>
                </div>
                <div className="bg-emerald-500/10 rounded-lg p-3">
                  <p className="text-xs vf-text-m">Expenses posted</p>
                  <p className="text-lg font-bold text-emerald-400">{backfillResult.expenses_posted}</p>
                </div>
                <div className="bg-white/5 rounded-lg p-3">
                  <p className="text-xs vf-text-m">Skipped (already posted)</p>
                  <p className="text-lg font-bold vf-text-m">{backfillResult.skipped}</p>
                </div>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export default function AccountingPage() {
  return (
    <RoleGuard minRole="ADMIN">
      <AccountingPageInner />
    </RoleGuard>
  );
}
