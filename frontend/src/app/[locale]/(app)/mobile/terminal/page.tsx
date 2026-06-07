"use client";

import { useState, useEffect } from "react";
import { toast } from "sonner";
import { api } from "@/lib/api-client";
import {
  CreditCard, Wifi, CheckCircle2, XCircle, RefreshCw,
  Smartphone, Receipt, RotateCcw, Info,
} from "lucide-react";

interface Reader { id: string; label: string; device_type: string; status: string }
interface Session {
  id: string; reader_id?: string; payment_intent_id?: string; invoice_id?: string;
  amount: string; currency: string; status: string; created_at: string;
}

const STATUS_COLORS: Record<string, string> = {
  succeeded: "text-green-600 bg-green-50",
  failed: "text-red-500 bg-red-50",
  canceled: "text-gray-400 bg-gray-50",
  initiated: "text-blue-600 bg-blue-50",
  processing: "text-amber-600 bg-amber-50",
};

const CURRENCIES = ["SEK", "EUR", "NOK", "DKK", "USD"];

export default function TerminalPage() {
  const [readers, setReaders] = useState<Reader[]>([]);
  const [sessions, setSessions] = useState<Session[]>([]);
  const [amount, setAmount] = useState("");
  const [currency, setCurrency] = useState("SEK");
  const [selectedReader, setSelectedReader] = useState("");
  const [description, setDescription] = useState("");
  const [receiptEmail, setReceiptEmail] = useState("");
  const [loading, setLoading] = useState(false);
  const [loadingReaders, setLoadingReaders] = useState(false);

  // Refund modal
  const [refundSess, setRefundSess] = useState<Session | null>(null);
  const [refundAmount, setRefundAmount] = useState("");
  const [refunding, setRefunding] = useState(false);

  async function loadData() {
    setLoadingReaders(true);
    try {
      const [readersData, sessionsData] = await Promise.all([
        api.get<{ readers?: Reader[] }>("/api/mobile/terminal/readers").catch(() => null),
        api.get<{ sessions?: Session[] }>("/api/mobile/terminal/sessions?limit=25").catch(() => null),
      ]);
      if (readersData) setReaders(readersData.readers ?? []);
      if (sessionsData) setSessions(sessionsData.sessions ?? []);
    } catch { /* offline */ }
    finally { setLoadingReaders(false); }
  }

  useEffect(() => { loadData(); }, []);

  async function createPayment() {
    const amt = parseFloat(amount);
    if (!amount || isNaN(amt) || amt <= 0) { toast.error("Enter a valid amount"); return; }
    if (!selectedReader) { toast.error("Select a reader first"); return; }
    setLoading(true);
    try {
      const sess = await api.post<Session>("/api/mobile/terminal/create-payment", {
        amount: amt,
        currency: currency.toLowerCase(),
        reader_id: selectedReader,
        description: description || undefined,
      });
      setSessions(s => [sess, ...s]);
      toast.success("Payment initiated — present card to reader");
      setAmount(""); setDescription("");
    } catch (err: any) {
      toast.error(err.message || "Failed to create payment");
    }
    setLoading(false);
  }

  async function capture(piId: string, sessId: string) {
    try {
      const updated = await api.post<Session>(`/api/mobile/terminal/capture/${piId}`, {});
      setSessions(s => s.map(x => x.id === sessId ? updated : x));
      toast.success("Payment captured");
      if (receiptEmail && updated.payment_intent_id) {
        toast.info(`Receipt: set receipt_email on PaymentIntent for automated delivery`);
      }
    } catch {
      toast.error("Capture failed");
    }
  }

  async function cancelPayment(piId: string, sessId: string) {
    try {
      await api.post(`/api/mobile/terminal/cancel/${piId}`, {});
      setSessions(s => s.map(x => x.id === sessId ? { ...x, status: "canceled" } : x));
      toast.success("Payment cancelled");
    } catch {
      toast.error("Cancel failed");
    }
  }

  async function submitRefund() {
    if (!refundSess?.payment_intent_id) return;
    const amt = parseFloat(refundAmount);
    if (!refundAmount || isNaN(amt) || amt <= 0) { toast.error("Enter refund amount"); return; }
    setRefunding(true);
    try {
      await api.post("/api/invoicing/refund", {
        payment_intent_id: refundSess.payment_intent_id,
        amount: amt,
        reason: "requested_by_customer",
      });
      toast.success("Refund issued");
      setSessions(s => s.map(x => x.id === refundSess.id ? { ...x, status: "refunded" } : x));
      setRefundSess(null);
      setRefundAmount("");
    } catch (err: any) {
      toast.error(err.message || "Refund failed");
    } finally {
      setRefunding(false);
    }
  }

  function StatusBadge({ status }: { status: string }) {
    return (
      <span className={`text-xs px-2 py-0.5 rounded-full font-medium capitalize ${STATUS_COLORS[status] || "text-gray-500 bg-gray-50"}`}>
        {status}
      </span>
    );
  }

  function StatusIcon({ status }: { status: string }) {
    if (status === "succeeded") return <CheckCircle2 className="h-4 w-4 text-green-500" />;
    if (["failed", "canceled"].includes(status)) return <XCircle className="h-4 w-4 text-red-400" />;
    if (status === "initiated" || status === "processing")
      return <div className="h-4 w-4 rounded-full border-2 border-blue-400 border-t-transparent animate-spin" />;
    return <CreditCard className="h-4 w-4 text-gray-400" />;
  }

  return (
    <div className="max-w-2xl space-y-6">
      <div>
        <h1 className="text-2xl font-semibold text-gray-900">NFC / Tap-to-Pay</h1>
        <p className="mt-1 text-sm text-gray-500">Accept contactless card payments via Stripe Terminal readers.</p>
      </div>

      {/* Tap to Pay on iPhone info */}
      <div className="flex gap-3 rounded-xl border border-indigo-200 bg-indigo-50 p-4">
        <Smartphone className="h-5 w-5 text-indigo-500 flex-shrink-0 mt-0.5" />
        <div className="space-y-1">
          <p className="text-sm font-medium text-indigo-800">Tap to Pay on iPhone / Android</p>
          <p className="text-xs text-indigo-600">
            To use your phone as a contactless reader (no hardware required), use the Stripe Mobile SDK in the
            companion Varuflow mobile app (Expo). This web interface supports registered Stripe Terminal hardware readers below.
            iPhone XS or later required; Bluetooth must be enabled.
          </p>
        </div>
      </div>

      {/* Readers */}
      <div>
        <div className="flex items-center justify-between mb-2">
          <h2 className="text-sm font-semibold text-gray-700">Hardware Readers</h2>
          <button onClick={loadData} disabled={loadingReaders}
            className="flex items-center gap-1 text-xs text-blue-600 hover:underline disabled:opacity-50">
            <RefreshCw className={`h-3 w-3 ${loadingReaders ? "animate-spin" : ""}`} /> Refresh
          </button>
        </div>
        {readers.length === 0 ? (
          <div className="flex items-center gap-2 rounded-xl border border-dashed border-gray-300 p-4 text-sm text-gray-400">
            <Info className="h-4 w-4" />
            No readers found. Register a Stripe Terminal reader in your Stripe dashboard.
          </div>
        ) : (
          <div className="grid grid-cols-2 gap-3">
            {readers.map(r => (
              <label key={r.id} className={`flex items-center gap-2 p-3 rounded-xl border cursor-pointer transition-colors ${
                selectedReader === r.id ? "border-blue-500 bg-blue-50" : "border-gray-200 hover:border-gray-300"
              }`}>
                <input type="radio" name="reader" value={r.id} checked={selectedReader === r.id}
                  onChange={() => setSelectedReader(r.id)} className="sr-only" />
                <Wifi className={`h-4 w-4 ${r.status === "online" ? "text-green-500" : "text-gray-400"}`} />
                <div className="min-w-0">
                  <p className="text-sm font-medium text-gray-900 truncate">{r.label || r.id}</p>
                  <p className="text-xs text-gray-500">{r.device_type} · <span className={r.status === "online" ? "text-green-600" : "text-gray-400"}>{r.status}</span></p>
                </div>
              </label>
            ))}
          </div>
        )}
      </div>

      {/* Charge form */}
      <div className="rounded-xl border border-gray-200 bg-white p-5 space-y-4">
        <h2 className="text-sm font-semibold text-gray-700">Initiate Payment</h2>
        <div className="flex gap-3">
          <input className="input flex-1" type="number" step="0.01" min="0.01"
            placeholder="Amount (e.g. 1200.00)" value={amount} onChange={e => setAmount(e.target.value)} />
          <select className="input w-24" value={currency} onChange={e => setCurrency(e.target.value)}>
            {CURRENCIES.map(c => <option key={c}>{c}</option>)}
          </select>
        </div>
        <input className="input w-full" placeholder="Description (optional)" value={description}
          onChange={e => setDescription(e.target.value)} />
        <div className="flex items-center gap-2">
          <Receipt className="h-4 w-4 text-gray-400 flex-shrink-0" />
          <input className="input flex-1" type="email" placeholder="Receipt email (optional)"
            value={receiptEmail} onChange={e => setReceiptEmail(e.target.value)} />
        </div>
        <div className="rounded-lg bg-amber-50 border border-amber-200 px-3 py-2 text-xs text-amber-700 flex items-center gap-2">
          <Wifi className="h-3.5 w-3.5 flex-shrink-0" />
          Stripe Terminal supports offline card reading — payments queue when disconnected and process on reconnect.
        </div>
        <button onClick={createPayment} disabled={loading || !selectedReader}
          className="btn-primary w-full flex items-center justify-center gap-2 disabled:opacity-50">
          {loading
            ? <RefreshCw className="h-4 w-4 animate-spin" />
            : <CreditCard className="h-4 w-4" />}
          {loading ? "Initiating…" : "Charge Card"}
        </button>
      </div>

      {/* Session history */}
      <div>
        <h2 className="text-sm font-semibold text-gray-700 mb-3">Recent Sessions</h2>
        {sessions.length === 0 ? (
          <p className="text-sm text-gray-400">No payment sessions yet.</p>
        ) : (
          <div className="space-y-2">
            {sessions.map(s => (
              <div key={s.id} className="rounded-xl border border-gray-200 bg-white p-4 flex items-center gap-3">
                <StatusIcon status={s.status} />
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <p className="text-sm font-medium text-gray-900">{s.amount} {s.currency}</p>
                    <StatusBadge status={s.status} />
                  </div>
                  <p className="text-xs text-gray-400">
                    {new Date(s.created_at).toLocaleString()}
                    {s.reader_id && ` · ${s.reader_id.substring(0, 12)}…`}
                  </p>
                </div>
                <div className="flex gap-2 flex-shrink-0">
                  {s.status === "initiated" && s.payment_intent_id && (
                    <>
                      <button onClick={() => capture(s.payment_intent_id!, s.id)}
                        className="rounded-lg border border-green-300 px-2.5 py-1.5 text-xs font-medium text-green-700 hover:bg-green-50">
                        Capture
                      </button>
                      <button onClick={() => cancelPayment(s.payment_intent_id!, s.id)}
                        className="rounded-lg border border-red-200 px-2.5 py-1.5 text-xs font-medium text-red-500 hover:bg-red-50">
                        Cancel
                      </button>
                    </>
                  )}
                  {s.status === "succeeded" && (
                    <button onClick={() => { setRefundSess(s); setRefundAmount(s.amount); }}
                      className="flex items-center gap-1 rounded-lg border border-gray-200 px-2.5 py-1.5 text-xs text-gray-600 hover:bg-gray-50">
                      <RotateCcw className="h-3 w-3" /> Refund
                    </button>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Refund modal */}
      {refundSess && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
          <div className="w-full max-w-sm rounded-2xl bg-white p-5 space-y-4 shadow-xl">
            <h3 className="font-semibold text-gray-900">Issue Refund</h3>
            <p className="text-sm text-gray-600">Original: {refundSess.amount} {refundSess.currency}</p>
            <div>
              <label className="text-xs font-medium text-gray-700 mb-1 block">Refund amount</label>
              <div className="flex gap-2">
                <input className="input flex-1" type="number" step="0.01" value={refundAmount}
                  onChange={e => setRefundAmount(e.target.value)} />
                <span className="flex items-center text-sm text-gray-500">{refundSess.currency}</span>
              </div>
            </div>
            <div className="flex gap-2">
              <button onClick={() => setRefundSess(null)} className="flex-1 btn-secondary">Cancel</button>
              <button onClick={submitRefund} disabled={refunding}
                className="flex-1 flex items-center justify-center gap-1.5 rounded-lg bg-red-600 py-2 text-sm font-medium text-white hover:bg-red-700 disabled:opacity-50">
                {refunding && <RefreshCw className="h-3.5 w-3.5 animate-spin" />}
                Confirm Refund
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
