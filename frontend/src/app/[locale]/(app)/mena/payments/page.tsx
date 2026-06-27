"use client";

import { api } from "@/lib/api-client";
import { useEffect, useState } from "react";
import { CreditCard, ExternalLink, RefreshCw, X } from "lucide-react";
import { toast } from "sonner";
import { useRouter } from "@/i18n/navigation";
import { useLocale } from "next-intl";

interface Provider {
  name: string;
  display_name: string;
  country: string;
  currency: string;
  docs: string;
  configured: boolean;
}

interface PaymentSession {
  id: string;
  invoice_id: string;
  provider: string;
  provider_session_id: string | null;
  amount: string;
  currency: string;
  status: string;
  created_at: string;
}

const STATUS_COLORS: Record<string, string> = {
  initiated: "bg-blue-100 text-blue-700",
  paid:      "bg-green-100 text-green-700",
  failed:    "bg-red-100 text-red-700",
  expired:   "bg-gray-100 text-gray-500",
};

const FLAG: Record<string, string> = { SA: "🇸🇦", KW: "🇰🇼", BH: "🇧🇭", EG: "🇪🇬" };

export default function GccPaymentsPage() {
  const locale = useLocale();
  const router = useRouter();
  const [providers, setProviders] = useState<Provider[]>([]);
  const [sessions, setSessions] = useState<PaymentSession[]>([]);
  const [loadingProviders, setLoadingProviders] = useState(true);
  const [loadingSessions, setLoadingSessions] = useState(true);
  const [modal, setModal] = useState(false);
  const [form, setForm] = useState({ invoice_id: "", provider: "mada", currency: "SAR" });
  const [initiating, setInitiating] = useState(false);
  const [checkoutUrl, setCheckoutUrl] = useState<string | null>(null);

  async function loadData() {
    setLoadingProviders(true);
    setLoadingSessions(true);
    try {
      const [pData, sData] = await Promise.all([
        api.get("/api/mena/payments/providers"),
        api.get("/api/mena/payments/sessions?limit=50"),
      ]);
      setProviders((pData as { providers: Provider[] }).providers);
      setSessions((sData as { sessions: PaymentSession[] }).sessions);
    } catch (e: unknown) {
      const err = e as { status?: number };
      if (err.status === 401) router.push(`/${locale}/auth/login`);
      else toast.error("Failed to load payment data.");
    } finally {
      setLoadingProviders(false);
      setLoadingSessions(false);
    }
  }

  useEffect(() => { loadData(); }, []); // eslint-disable-line react-hooks/exhaustive-deps

  async function initiate() {
    if (!form.invoice_id.trim()) { toast.error("Enter an invoice ID."); return; }
    setInitiating(true);
    try {
      const d = await api.post("/api/mena/payments/initiate", form);
      const r = d as { checkout_url: string; session_id: string };
      setCheckoutUrl(r.checkout_url);
      toast.success("Payment session initiated (stub).");
      loadData();
    } catch (e: unknown) {
      const err = e as { status?: number; detail?: string };
      if (err.status === 404) toast.error("Invoice not found.");
      else toast.error("Failed to initiate payment.");
    } finally {
      setInitiating(false);
    }
  }

  return (
    <div className="max-w-5xl mx-auto p-6 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold flex items-center gap-2">
            <CreditCard className="w-6 h-6 text-indigo-600" />
            GCC Payment Rails
          </h1>
          <p className="text-sm text-gray-500 mt-1">
            mada (Saudi), KNET (Kuwait), Benefit (Bahrain), Fawry (Egypt)
          </p>
        </div>
        <div className="flex gap-2">
          <button onClick={loadData} className="flex items-center gap-1 text-xs px-3 py-1.5 border rounded hover:bg-gray-50">
            <RefreshCw className="w-3 h-3" /> Refresh
          </button>
          <button onClick={() => { setModal(true); setCheckoutUrl(null); }}
            className="flex items-center gap-2 px-4 py-2 bg-indigo-600 text-white text-sm rounded-lg hover:bg-indigo-700">
            + Test Payment
          </button>
        </div>
      </div>

      {/* Provider grid */}
      <div className="grid grid-cols-2 gap-4">
        {loadingProviders && <p className="col-span-2 text-sm text-gray-400 animate-pulse">Loading…</p>}
        {providers.map(p => (
          <div key={p.name} className="p-5 border rounded-lg space-y-3">
            <div className="flex items-center gap-3">
              <span className="text-2xl">{FLAG[p.country] ?? "🌍"}</span>
              <div>
                <p className="font-semibold">{p.display_name}</p>
                <p className="text-xs text-gray-500">{p.currency} · {p.country}</p>
              </div>
              <span className="ml-auto text-xs px-2 py-0.5 rounded-full bg-gray-100 text-gray-500">
                Not configured
              </span>
            </div>
            <a href={p.docs} target="_blank" rel="noopener noreferrer"
              className="flex items-center gap-1 text-xs text-indigo-600 hover:underline">
              <ExternalLink className="w-3 h-3" /> Merchant API docs
            </a>
          </div>
        ))}
      </div>

      {/* Sessions table */}
      <div className="space-y-2">
        <h2 className="font-semibold text-sm">Payment Sessions</h2>
        {loadingSessions && <p className="text-xs text-gray-400 animate-pulse">Loading…</p>}
        {!loadingSessions && sessions.length === 0 && (
          <p className="text-sm text-gray-400 text-center py-6">No payment sessions yet.</p>
        )}
        {sessions.length > 0 && (
          <div className="border rounded-lg overflow-hidden">
            <table className="w-full text-sm">
              <thead className="bg-gray-50 border-b">
                <tr>
                  {["Invoice", "Provider", "Amount", "Currency", "Status", "Date"].map(h => (
                    <th key={h} className="text-left px-3 py-2 text-xs font-medium text-gray-600">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y">
                {sessions.map(s => (
                  <tr key={s.id} className="hover:bg-gray-50/50">
                    <td className="px-3 py-2 font-mono text-xs text-gray-500">{s.invoice_id.slice(0, 8)}…</td>
                    <td className="px-3 py-2 capitalize">{s.provider}</td>
                    <td className="px-3 py-2">{parseFloat(s.amount).toLocaleString()}</td>
                    <td className="px-3 py-2 text-xs">{s.currency}</td>
                    <td className="px-3 py-2">
                      <span className={`text-xs px-2 py-0.5 rounded-full ${STATUS_COLORS[s.status] ?? "bg-gray-100"}`}>
                        {s.status}
                      </span>
                    </td>
                    <td className="px-3 py-2 text-xs text-gray-400">
                      {new Date(s.created_at).toLocaleDateString()}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Initiate modal */}
      {modal && (
        <div className="fixed inset-0 z-40 flex items-center justify-center">
          <div className="absolute inset-0 bg-black/30" onClick={() => setModal(false)} />
          <div className="relative bg-white rounded-xl shadow-xl p-6 w-full max-w-sm space-y-4 z-50">
            <div className="flex items-center justify-between">
              <h2 className="font-bold text-lg">Initiate Test Payment</h2>
              <button onClick={() => setModal(false)}><X className="w-5 h-5" /></button>
            </div>
            <div className="space-y-3">
              <div>
                <label className="text-sm font-medium">Invoice ID</label>
                <input value={form.invoice_id} onChange={e => setForm(f => ({ ...f, invoice_id: e.target.value }))}
                  className="mt-1 w-full border rounded px-3 py-2 text-sm font-mono"
                  placeholder="UUID" />
              </div>
              <div>
                <label className="text-sm font-medium">Provider</label>
                <select value={form.provider} onChange={e => setForm(f => ({ ...f, provider: e.target.value }))}
                  className="mt-1 w-full border rounded px-3 py-2 text-sm">
                  {["mada", "knet", "benefit", "fawry"].map(p => (
                    <option key={p} value={p}>{p}</option>
                  ))}
                </select>
              </div>
              <div>
                <label className="text-sm font-medium">Currency</label>
                <select value={form.currency} onChange={e => setForm(f => ({ ...f, currency: e.target.value }))}
                  className="mt-1 w-full border rounded px-3 py-2 text-sm">
                  {["SAR", "KWD", "BHD", "EGP", "AED"].map(c => (
                    <option key={c}>{c}</option>
                  ))}
                </select>
              </div>
            </div>
            {checkoutUrl && (
              <div className="p-3 bg-indigo-50 rounded border border-indigo-200 text-xs">
                <p className="font-medium text-indigo-700 mb-1">Stub checkout URL:</p>
                <p className="font-mono break-all text-indigo-600">{checkoutUrl}</p>
              </div>
            )}
            <button onClick={initiate} disabled={initiating}
              className="w-full py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 disabled:opacity-50 text-sm">
              {initiating ? "Initiating…" : "Initiate Payment"}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
