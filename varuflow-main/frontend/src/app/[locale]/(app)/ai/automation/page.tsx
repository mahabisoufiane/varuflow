"use client";

import { api } from "@/lib/api-client";
import { useEffect, useState } from "react";
import { AlertTriangle, ArrowRight, CheckCircle, RefreshCw, TrendingUp, XCircle } from "lucide-react";
import { toast } from "sonner";
import { useRouter } from "@/i18n/navigation";
import { useLocale } from "next-intl";

/* ── Types ─────────────────────────────────────────────────────────────────── */
interface CashBucket {
  label: string;
  incoming: number;
  outgoing: number;
  net: number;
  currency: string;
}
interface CashFlowResponse {
  current_balance: number;
  currency: string;
  buckets: CashBucket[];
}

interface AnomalyItem {
  type: string;
  severity: "HIGH" | "MEDIUM" | "LOW";
  title: string;
  detail: string;
  meta: Record<string, unknown>;
}
interface AnomalyResponse {
  anomalies: AnomalyItem[];
  checked_at: string;
}

interface MatchCandidate {
  invoice_id: string;
  invoice_number: string;
  customer_name: string;
  invoice_amount: number;
  due_date: string;
  score: number;
}
interface BankMatchItem {
  transaction_id: string;
  description: string;
  amount: number;
  date: string;
  status: string;
  candidates: MatchCandidate[];
}
interface BankMatchResponse {
  matches: BankMatchItem[];
}

type Tab = "cashflow" | "anomalies" | "bankmatch";

/* ── Page ───────────────────────────────────────────────────────────────────── */
export default function AutomationPage() {
  const locale = useLocale();
  const router = useRouter();
  const [tab, setTab] = useState<Tab>("cashflow");

  const [cashflow, setCashflow] = useState<CashFlowResponse | null>(null);
  const [anomalies, setAnomalies] = useState<AnomalyResponse | null>(null);
  const [matches, setMatches] = useState<BankMatchResponse | null>(null);
  const [loading, setLoading] = useState(false);

  async function load(t: Tab) {
    setLoading(true);
    try {
      if (t === "cashflow" && !cashflow) {
        const d = await api.get("/api/ai/cashflow");
        setCashflow(d as CashFlowResponse);
      } else if (t === "anomalies" && !anomalies) {
        const d = await api.get("/api/ai/anomalies");
        setAnomalies(d as AnomalyResponse);
      } else if (t === "bankmatch" && !matches) {
        const d = await api.get("/api/ai/bank-match");
        setMatches(d as BankMatchResponse);
      }
    } catch (e: unknown) {
      const err = e as { status?: number };
      if (err.status === 401) router.push(`/${locale}/auth/login`);
      else toast.error("Failed to load data.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { load(tab); }, [tab]); // eslint-disable-line react-hooks/exhaustive-deps

  async function refresh() {
    setCashflow(null); setAnomalies(null); setMatches(null);
    await load(tab);
  }

  async function confirmMatch(txId: string, invoiceId: string) {
    try {
      await api.post(`/api/ai/bank-match/${txId}/confirm`, { invoice_id: invoiceId });
      toast.success("Match confirmed.");
      setMatches(null);
      load("bankmatch");
    } catch {
      toast.error("Failed to confirm match.");
    }
  }

  const TABS: { id: Tab; label: string }[] = [
    { id: "cashflow",  label: "Cash Flow Forecast" },
    { id: "anomalies", label: "Anomalies"           },
    { id: "bankmatch", label: "Bank Match"           },
  ];

  const sevColor: Record<string, string> = {
    HIGH: "bg-red-100 text-red-700",
    MEDIUM: "bg-amber-100 text-amber-700",
    LOW: "bg-gray-100 text-gray-600",
  };

  return (
    <div className="max-w-5xl mx-auto p-6 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold flex items-center gap-2">
            <TrendingUp className="w-6 h-6 text-blue-500" />
            AI Automation
          </h1>
          <p className="text-sm text-gray-500 mt-1">Cash flow forecasts, anomaly detection and bank reconciliation</p>
        </div>
        <button onClick={refresh} className="flex items-center gap-2 px-3 py-1.5 text-sm border rounded hover:bg-gray-50">
          <RefreshCw className="w-4 h-4" /> Refresh
        </button>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 border-b">
        {TABS.map(t => (
          <button
            key={t.id}
            onClick={() => setTab(t.id)}
            className={`px-4 py-2 text-sm font-medium -mb-px border-b-2 transition-colors ${
              tab === t.id ? "border-blue-500 text-blue-600" : "border-transparent text-gray-500 hover:text-gray-700"
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      {loading && <p className="text-sm text-gray-400 animate-pulse">Loading…</p>}

      {/* Cash Flow */}
      {tab === "cashflow" && cashflow && (
        <div className="space-y-4">
          <div className="p-4 bg-blue-50 border border-blue-200 rounded-lg">
            <p className="text-sm text-blue-700">Current bank balance</p>
            <p className="text-3xl font-bold text-blue-800 mt-1">
              {cashflow.current_balance.toLocaleString("sv-SE", { style: "currency", currency: cashflow.currency })}
            </p>
          </div>
          <div className="grid grid-cols-3 gap-4">
            {cashflow.buckets.map((b) => (
              <div key={b.label} className="p-4 border rounded-lg space-y-2">
                <p className="font-semibold text-gray-700">{b.label}</p>
                <div className="space-y-1 text-sm">
                  <div className="flex justify-between">
                    <span className="text-green-600">Incoming</span>
                    <span className="font-medium">{b.incoming.toLocaleString("sv-SE")}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-red-600">Outgoing</span>
                    <span className="font-medium">{b.outgoing.toLocaleString("sv-SE")}</span>
                  </div>
                  <div className="flex justify-between border-t pt-1 mt-1">
                    <span className="font-medium">Net</span>
                    <span className={`font-bold ${b.net >= 0 ? "text-green-700" : "text-red-700"}`}>
                      {b.net.toLocaleString("sv-SE")}
                    </span>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Anomalies */}
      {tab === "anomalies" && anomalies && (
        <div className="space-y-3">
          {anomalies.anomalies.length === 0 && (
            <div className="flex items-center gap-2 p-4 bg-green-50 border border-green-200 rounded-lg text-green-700">
              <CheckCircle className="w-5 h-5" />
              <span className="text-sm">No anomalies detected.</span>
            </div>
          )}
          {anomalies.anomalies.map((a, i) => (
            <div key={i} className="p-4 border rounded-lg space-y-1">
              <div className="flex items-center gap-2">
                <AlertTriangle className="w-4 h-4 text-amber-500" />
                <span className="font-medium">{a.title}</span>
                <span className={`ml-auto text-xs px-2 py-0.5 rounded-full font-medium ${sevColor[a.severity]}`}>
                  {a.severity}
                </span>
              </div>
              <p className="text-sm text-gray-600">{a.detail}</p>
            </div>
          ))}
        </div>
      )}

      {/* Bank Match */}
      {tab === "bankmatch" && matches && (
        <div className="space-y-4">
          {matches.matches.length === 0 && (
            <p className="text-sm text-gray-500">No unmatched transactions to suggest.</p>
          )}
          {matches.matches.map((tx) => (
            <div key={tx.transaction_id} className="border rounded-lg overflow-hidden">
              <div className="p-3 bg-gray-50 flex items-center justify-between text-sm">
                <div>
                  <span className="font-medium">{tx.description}</span>
                  <span className="ml-2 text-gray-400">{tx.date}</span>
                </div>
                <span className={`font-bold ${tx.amount >= 0 ? "text-green-700" : "text-red-700"}`}>
                  {tx.amount.toLocaleString("sv-SE")} SEK
                </span>
              </div>
              {tx.candidates.length === 0 ? (
                <p className="px-3 py-2 text-xs text-gray-400">No matching invoices found.</p>
              ) : (
                <div className="divide-y">
                  {tx.candidates.map((c) => (
                    <div key={c.invoice_id} className="px-3 py-2 flex items-center gap-3 text-sm">
                      <XCircle className="w-4 h-4 text-gray-300" />
                      <div className="flex-1">
                        <span className="font-medium">{c.invoice_number}</span>
                        <span className="ml-2 text-gray-500">{c.customer_name}</span>
                      </div>
                      <span className="text-gray-600">{c.invoice_amount.toLocaleString("sv-SE")} SEK</span>
                      <span className="text-xs bg-blue-50 text-blue-700 px-2 py-0.5 rounded">
                        {c.score}% match
                      </span>
                      <button
                        onClick={() => confirmMatch(tx.transaction_id, c.invoice_id)}
                        className="flex items-center gap-1 text-xs px-2 py-1 bg-blue-600 text-white rounded hover:bg-blue-700"
                      >
                        Confirm <ArrowRight className="w-3 h-3" />
                      </button>
                    </div>
                  ))}
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
