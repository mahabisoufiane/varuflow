"use client";

import { useState, useEffect, useCallback } from "react";
import { toast } from "sonner";
import { Building2, Download } from "lucide-react";
import { api } from "@/lib/api-client";

interface Institution { id: string; name: string; countries: string[]; logo?: string }
interface Account { id: string; iban?: string; name?: string; currency?: string }
type ConnectStatus = { connected: boolean; institution_id?: string }

export default function BankingIntegrationPage() {
  const [institutions, setInstitutions] = useState<Institution[]>([]);
  const [country, setCountry] = useState("SE");
  const [selected, setSelected] = useState("");
  const [status, setStatus] = useState<ConnectStatus>({ connected: false });
  const [accounts, setAccounts] = useState<Account[]>([]);
  const [importing, setImporting] = useState<string | null>(null);
  const [connecting, setConnecting] = useState(false);

  const loadAccounts = useCallback(async () => {
    try {
      const data = await api.get<{ accounts?: Account[] }>("/api/integrations/open-banking/accounts");
      setAccounts(data.accounts || []);
      setStatus({ connected: (data.accounts?.length ?? 0) > 0 });
    } catch {}
  }, []);

  useEffect(() => {
    async function loadInstitutions() {
      try {
        const data = await api.get<{ institutions?: Institution[] }>(`/api/integrations/open-banking/providers?country=${country}`);
        setInstitutions(data.institutions ?? []);
      } catch {}
    }
    loadInstitutions();
  }, [country]);

  useEffect(() => { loadAccounts(); }, [loadAccounts]);

  // Check URL params for callback status
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    if (params.get("status") === "connected") {
      toast.success("Bank connected! Loading accounts…");
      loadAccounts();
    }
  }, [loadAccounts]);

  async function connectBank() {
    if (!selected) { toast.error("Select a bank first"); return; }
    setConnecting(true);
    try {
      const data = await api.post<{ redirect_url?: string }>("/api/integrations/open-banking/connect", { institution_id: selected, country });
      if (data.redirect_url) {
        window.open(data.redirect_url, "_blank", "noopener");
        toast.info("Complete the bank authorisation in the new tab, then return here.");
      }
    } catch (err: any) {
      toast.error(err.message || "Connection failed");
    }
    setConnecting(false);
  }

  async function importTransactions(accountId: string) {
    setImporting(accountId);
    try {
      const data = await api.post<{ message?: string; imported?: number }>(`/api/integrations/open-banking/accounts/${accountId}/import`, {});
      toast.success(data.message || `Imported ${data.imported} transactions`);
    } catch (err: any) {
      toast.error(err.message || "Import failed");
    }
    setImporting(null);
  }

  async function disconnect() {
    await api.delete("/api/integrations/open-banking/disconnect").catch(() => {});
    toast.success("Disconnected");
    setAccounts([]);
    setStatus({ connected: false });
  }

  return (
    <div className="max-w-2xl space-y-6">
      <div>
        <h1 className="text-2xl font-semibold text-gray-900">Open Banking</h1>
        <p className="mt-1 text-sm text-gray-500">Import bank transactions from European banks via GoCardless (Nordigen).</p>
      </div>

      {/* Bank search */}
      {!status.connected ? (
        <div className="space-y-4">
          <div className="flex gap-3">
            <select className="input" value={country} onChange={e => setCountry(e.target.value)}>
              <option value="SE">Sweden</option>
              <option value="NO">Norway</option>
              <option value="DK">Denmark</option>
              <option value="FI">Finland</option>
            </select>
          </div>

          <div className="grid grid-cols-2 gap-3">
            {institutions.map(inst => (
              <label key={inst.id} className={`flex items-center gap-3 rounded-xl border p-3 cursor-pointer transition-colors ${
                selected === inst.id ? "border-blue-500 bg-blue-50" : "border-gray-200 hover:border-gray-300"
              }`}>
                <input type="radio" name="bank" value={inst.id} checked={selected === inst.id} onChange={e => setSelected(e.target.value)} className="sr-only" />
                <Building2 className="h-5 w-5 text-gray-400 flex-shrink-0" />
                <span className="text-sm font-medium text-gray-900">{inst.name}</span>
              </label>
            ))}
          </div>

          <button onClick={connectBank} disabled={connecting || !selected} className="btn-primary">
            {connecting ? "Opening bank portal…" : "Connect Bank"}
          </button>

          <p className="text-xs text-gray-400">
            After clicking Connect, you will be redirected to your bank to authorise read-only access. No payment data is stored — Varuflow only imports transaction history.
          </p>
        </div>
      ) : (
        <div className="space-y-4">
          <div className="rounded-lg bg-green-50 px-4 py-3 text-sm text-green-700 font-medium">
            Bank connected — {accounts.length} account{accounts.length !== 1 ? "s" : ""} linked
          </div>

          {accounts.map(acc => (
            <div key={acc.id} className="flex items-center justify-between rounded-xl border border-gray-200 bg-white p-4">
              <div>
                <p className="text-sm font-medium text-gray-900">{acc.name || "Bank Account"}</p>
                <p className="text-xs text-gray-500">{acc.iban || acc.id} · {acc.currency}</p>
              </div>
              <button
                onClick={() => importTransactions(acc.id)}
                disabled={importing === acc.id}
                className="btn-secondary flex items-center gap-1.5"
              >
                <Download className="h-3.5 w-3.5" />
                {importing === acc.id ? "Importing…" : "Import Transactions"}
              </button>
            </div>
          ))}

          <button onClick={disconnect} className="btn-danger-outline text-sm">Disconnect Bank</button>
        </div>
      )}
    </div>
  );
}
