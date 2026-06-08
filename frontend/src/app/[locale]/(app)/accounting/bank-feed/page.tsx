"use client";

/**
 * Bank Feed — Manual CSV Import
 *
 * Wires:
 *   GET    /api/accounting/bank-accounts
 *   POST   /api/accounting/bank-accounts
 *   DELETE /api/accounting/bank-accounts/{id}
 *   POST   /api/accounting/bank-accounts/{id}/import-csv
 *   GET    /api/accounting/bank-accounts/{id}/transactions
 *   POST   /api/accounting/bank-transactions/{id}/match
 *   POST   /api/accounting/bank-transactions/{id}/exclude
 *   GET    /api/accounting/bank-accounts/{id}/reconciliation
 */
import { useCallback, useEffect, useRef, useState } from "react";
import { Building2, Loader2, Plus, RefreshCw, Upload, CheckCircle2, X, Link } from "lucide-react";
import { toast } from "sonner";
import { api } from "@/lib/api-client";
import styles from "./page.module.scss";
import { isPlanGateError, PlanGateBlock } from "@/components/ui/PlanGate";

// ─── Types ──────────────────────────────────────────────────────────────────

interface BankAccount {
  id: string;
  name: string;
  iban: string | null;
  currency: string;
  last_synced_at: string | null;
  created_at: string;
}

interface BankTransaction {
  id: string;
  transaction_date: string;
  value_date: string | null;
  amount: string;
  description: string;
  reference: string | null;
  status: string;
  matched_type: string | null;
  matched_id: string | null;
  imported_at: string;
}

interface Reconciliation {
  total_transactions: number;
  unmatched_count: number;
  matched_count: number;
  excluded_count: number;
  unmatched_total: string;
  period_balance: string;
}

// ─── Helpers ────────────────────────────────────────────────────────────────

const fmt = (n: string | number) =>
  Number(n).toLocaleString("sv-SE", { minimumFractionDigits: 2, maximumFractionDigits: 2 });

const STATUS_CHIP: Record<string, string> = {
  UNMATCHED: "text-amber-400 bg-amber-400/10",
  MATCHED: "text-emerald-400 bg-emerald-400/10",
  EXCLUDED: "text-zinc-400 bg-zinc-400/10",
};

const STATUS_CHIP_MODULE: Record<string, keyof typeof styles> = {
  UNMATCHED: "chipUnmatched",
  MATCHED:   "chipMatched",
  EXCLUDED:  "chipExcluded",
};

// ─── Component ──────────────────────────────────────────────────────────────

export default function BankFeedPage() {
  const [accounts, setAccounts]   = useState<BankAccount[]>([]);
  const [loading, setLoading]     = useState(true);
  const [selected, setSelected]   = useState<BankAccount | null>(null);
  const [txns, setTxns]           = useState<BankTransaction[]>([]);
  const [txLoading, setTxLoading] = useState(false);
  const [recon, setRecon]         = useState<Reconciliation | null>(null);
  const [showCreate, setShowCreate] = useState(false);
  const [statusFilter, setStatusFilter] = useState<string>("");
  const [page, setPage]           = useState(1);

  const fileRef = useRef<HTMLInputElement>(null);
  const [uploading, setUploading] = useState(false);

  const [createForm, setCreateForm] = useState({ name: "", iban: "", currency: "SEK" });

  const [planBlocked, setPlanBlocked] = useState<{ module: string; currentPlan: string } | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const data = await api.get<BankAccount[]>("/api/accounting/bank-accounts");
      setAccounts(data);
    } catch (err) {
      if (isPlanGateError(err)) {
        setPlanBlocked({ module: (err as any).module ?? "finance", currentPlan: (err as any).currentPlan ?? "FREE" });
        return;
      }
      toast.error(err instanceof Error ? err.message : "Failed to load accounts");
    } finally { setLoading(false); }
  }, []);

  useEffect(() => { load(); }, [load]);

  const loadTransactions = async (acct: BankAccount, pageNum = 1, filter = "") => {
    setTxLoading(true);
    try {
      const params = new URLSearchParams({ page: String(pageNum), per_page: "50" });
      if (filter) params.set("status", filter);
      const data = await api.get<BankTransaction[]>(
        `/api/accounting/bank-accounts/${acct.id}/transactions?${params}`
      );
      setTxns(data);
      const r = await api.get<Reconciliation>(`/api/accounting/bank-accounts/${acct.id}/reconciliation`);
      setRecon(r);
    } catch (e: unknown) {
      toast.error(e instanceof Error ? e.message : "Failed to load transactions");
    } finally { setTxLoading(false); }
  };

  const selectAccount = (a: BankAccount) => {
    setSelected(a);
    setPage(1);
    setStatusFilter("");
    loadTransactions(a, 1, "");
  };

  const handleCreate = async () => {
    if (!createForm.name) { toast.error("Account name required"); return; }
    try {
      await api.post("/api/accounting/bank-accounts", {
        name: createForm.name,
        iban: createForm.iban || null,
        currency: createForm.currency,
      });
      toast.success("Account added");
      setShowCreate(false);
      setCreateForm({ name: "", iban: "", currency: "SEK" });
      await load();
    } catch (e: unknown) { toast.error(e instanceof Error ? e.message : "Failed"); }
  };

  const handleDelete = async (id: string) => {
    try {
      await api.delete(`/api/accounting/bank-accounts/${id}`);
      toast.success("Account removed");
      if (selected?.id === id) { setSelected(null); setTxns([]); setRecon(null); }
      await load();
    } catch (e: unknown) { toast.error(e instanceof Error ? e.message : "Failed"); }
  };

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file || !selected) return;
    setUploading(true);
    try {
      const form = new FormData();
      form.append("file", file);
      const result = await api.post<{ imported: number; skipped: number }>(
        `/api/accounting/bank-accounts/${selected.id}/import-csv`,
        form
      );
      toast.success(`Imported ${result.imported} transactions (${result.skipped} skipped)`);
      await loadTransactions(selected, page, statusFilter);
    } catch (e: unknown) {
      toast.error(e instanceof Error ? e.message : "Import failed");
    } finally {
      setUploading(false);
      if (fileRef.current) fileRef.current.value = "";
    }
  };

  const handleExclude = async (txId: string) => {
    try {
      await api.post(`/api/accounting/bank-transactions/${txId}/exclude`, {});
      toast.success("Transaction excluded");
      if (selected) await loadTransactions(selected, page, statusFilter);
    } catch (e: unknown) { toast.error(e instanceof Error ? e.message : "Failed"); }
  };

  const applyFilter = (f: string) => {
    setStatusFilter(f);
    setPage(1);
    if (selected) loadTransactions(selected, 1, f);
  };

  if (planBlocked) return <PlanGateBlock module={planBlocked.module} currentPlan={planBlocked.currentPlan} featureName="Bank Feed" />;

  return (
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Building2 className="w-6 h-6 text-indigo-400" />
          <div>
            <h1 className="text-xl font-bold vf-text-1">Bank Feed</h1>
            <p className="text-xs vf-text-m mt-0.5">Import Nordic bank CSV exports (SEB, Handelsbanken, Nordea)</p>
          </div>
        </div>
        <div className="flex gap-2">
          <button onClick={load} className="vf-btn-ghost text-xs px-3 py-1.5">
            <RefreshCw className="w-3.5 h-3.5 mr-1.5 inline" />Refresh
          </button>
          <button onClick={() => setShowCreate(true)} className="vf-btn text-xs px-3 py-1.5">
            <Plus className="w-3.5 h-3.5 mr-1.5 inline" />Add Account
          </button>
        </div>
      </div>

      {showCreate && (
        <div className="vf-section p-5 space-y-4">
          <p className="font-semibold vf-text-1">New Bank Account</p>
          <div className="grid grid-cols-3 gap-3">
            <div>
              <label className="text-xs vf-text-m block mb-1">Account Name</label>
              <input type="text" placeholder="SEB Business" value={createForm.name}
                onChange={e => setCreateForm(p => ({ ...p, name: e.target.value }))}
                className="vf-input text-sm w-full" />
            </div>
            <div>
              <label className="text-xs vf-text-m block mb-1">IBAN (optional)</label>
              <input type="text" placeholder="SE35 5000 0000 0549 1000 0003" value={createForm.iban}
                onChange={e => setCreateForm(p => ({ ...p, iban: e.target.value }))}
                className="vf-input text-sm w-full" />
            </div>
            <div>
              <label className="text-xs vf-text-m block mb-1">Currency</label>
              <select value={createForm.currency} onChange={e => setCreateForm(p => ({ ...p, currency: e.target.value }))}
                className="vf-input text-sm w-full">
                {["SEK","NOK","DKK","EUR","USD"].map(c => <option key={c} value={c}>{c}</option>)}
              </select>
            </div>
          </div>
          <div className="flex justify-end gap-2">
            <button onClick={() => setShowCreate(false)} className="vf-btn-ghost text-xs px-3 py-1.5">Cancel</button>
            <button onClick={handleCreate} className="vf-btn text-xs px-3 py-1.5">Add</button>
          </div>
        </div>
      )}

      <div className="grid grid-cols-3 gap-4">
        {/* Account list */}
        <div className="col-span-1 space-y-2">
          {loading ? (
            <div className="flex justify-center py-8"><Loader2 className="w-5 h-5 animate-spin vf-text-m" /></div>
          ) : accounts.length === 0 ? (
            <div className="vf-section p-6 text-center vf-text-m text-sm">No bank accounts. Add one to get started.</div>
          ) : (
            accounts.map(a => (
              <div
                key={a.id}
                className={`vf-section p-4 cursor-pointer hover:ring-1 hover:ring-indigo-500/40 transition-all ${
                  selected?.id === a.id ? "ring-1 ring-indigo-500/60" : ""
                }`}
                onClick={() => selectAccount(a)}
              >
                <div className="flex items-start justify-between">
                  <div>
                    <p className="font-semibold vf-text-1 text-sm">{a.name}</p>
                    {a.iban && <p className="text-xs vf-text-m font-mono mt-0.5">{a.iban}</p>}
                    <p className="text-xs vf-text-m mt-0.5">{a.currency}</p>
                  </div>
                  <button onClick={e => { e.stopPropagation(); handleDelete(a.id); }}
                    className="vf-text-m hover:text-rose-400 transition-colors p-0.5">
                    <X className="w-3.5 h-3.5" />
                  </button>
                </div>
                {a.last_synced_at && (
                  <p className="text-xs vf-text-m mt-2">
                    Last import: {new Date(a.last_synced_at).toLocaleDateString("sv-SE")}
                  </p>
                )}
              </div>
            ))
          )}
        </div>

        {/* Transactions panel */}
        <div className="col-span-2 space-y-4">
          {selected ? (
            <>
              {/* Import + reconciliation */}
              <div className="vf-section p-4 flex items-center justify-between gap-4">
                <div className="flex gap-4 text-xs">
                  {recon && (
                    <>
                      <div className="text-center">
                        <p className="vf-text-m">Total</p>
                        <p className="font-bold vf-text-1">{recon.total_transactions}</p>
                      </div>
                      <div className="text-center">
                        <p className="vf-text-m">Unmatched</p>
                        <p className="font-bold text-amber-400">{recon.unmatched_count}</p>
                      </div>
                      <div className="text-center">
                        <p className="vf-text-m">Matched</p>
                        <p className="font-bold text-emerald-400">{recon.matched_count}</p>
                      </div>
                      <div className="text-center">
                        <p className="vf-text-m">Balance</p>
                        <p className="font-mono font-bold vf-text-1">{fmt(recon.period_balance)}</p>
                      </div>
                    </>
                  )}
                </div>
                <div>
                  <input type="file" ref={fileRef} accept=".csv" onChange={handleFileUpload} className="hidden" />
                  <button
                    onClick={() => fileRef.current?.click()}
                    disabled={uploading}
                    className="vf-btn text-xs px-3 py-1.5"
                  >
                    {uploading
                      ? <Loader2 className="w-3.5 h-3.5 animate-spin" />
                      : <><Upload className="w-3.5 h-3.5 mr-1.5 inline" />Import CSV</>
                    }
                  </button>
                </div>
              </div>

              {/* Filter tabs */}
              <div className="flex gap-1">
                {["", "UNMATCHED", "MATCHED", "EXCLUDED"].map(f => (
                  <button key={f} onClick={() => applyFilter(f)}
                    className={`text-xs px-3 py-1 rounded-md transition-colors ${
                      statusFilter === f ? "vf-btn" : "vf-btn-ghost"
                    }`}>
                    {f || "All"}
                  </button>
                ))}
              </div>

              {/* Transactions table */}
              {txLoading ? (
                <div className="flex justify-center py-8"><Loader2 className="w-5 h-5 animate-spin vf-text-m" /></div>
              ) : txns.length === 0 ? (
                <div className="vf-section p-8 text-center vf-text-m text-sm">
                  No transactions. Import a CSV file to get started.
                </div>
              ) : (
                <div className="vf-section overflow-hidden">
                  <table className="w-full text-xs">
                    <thead>
                      <tr className="border-b border-white/10">
                        {["Date", "Description", "Amount", "Status", ""].map(h => (
                          <th key={h} className="text-left py-2 px-3 vf-text-m font-medium">{h}</th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {txns.map(tx => (
                        <tr key={tx.id} className="border-b border-white/5 hover:bg-white/5">
                          <td className="py-2 px-3 vf-text-m font-mono whitespace-nowrap">{tx.transaction_date}</td>
                          <td className="py-2 px-3 vf-text-1 max-w-xs truncate">{tx.description}</td>
                          <td className={`py-2 px-3 font-mono font-medium whitespace-nowrap ${
                            Number(tx.amount) >= 0 ? "text-emerald-400" : "text-rose-400"
                          }`}>
                            {Number(tx.amount) >= 0 ? "+" : ""}{fmt(tx.amount)}
                          </td>
                          <td className="py-2 px-3">
                            <span className={styles[STATUS_CHIP_MODULE[tx.status] ?? "chipUnmatched"]}>
                              {tx.status}
                            </span>
                            {tx.matched_type && (
                              <span className="ml-1 vf-text-m text-xs">{tx.matched_type}</span>
                            )}
                          </td>
                          <td className="py-2 px-3">
                            {tx.status === "UNMATCHED" && (
                              <button onClick={() => handleExclude(tx.id)}
                                className="vf-text-m hover:text-rose-400 transition-colors"
                                title="Exclude">
                                <X className="w-3.5 h-3.5" />
                              </button>
                            )}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>

                  {/* Pagination */}
                  <div className="flex items-center justify-between px-3 py-2 border-t border-white/10">
                    <button disabled={page === 1} onClick={() => {
                      const p = page - 1;
                      setPage(p);
                      if (selected) loadTransactions(selected, p, statusFilter);
                    }} className="vf-btn-ghost text-xs px-2 py-1 disabled:opacity-40">← Prev</button>
                    <span className="text-xs vf-text-m">Page {page}</span>
                    <button disabled={txns.length < 50} onClick={() => {
                      const p = page + 1;
                      setPage(p);
                      if (selected) loadTransactions(selected, p, statusFilter);
                    }} className="vf-btn-ghost text-xs px-2 py-1 disabled:opacity-40">Next →</button>
                  </div>
                </div>
              )}
            </>
          ) : (
            <div className="vf-section p-8 text-center vf-text-m text-sm">
              Select a bank account to view transactions.
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
