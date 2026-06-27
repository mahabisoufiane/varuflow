"use client";
import { useEffect, useState } from "react";
import { useParams } from "next/navigation";

interface LineItem {
  id: string;
  description: string;
  quantity: number;
  unit_price: number;
  tax_rate: number;
  line_total: number;
}

interface QuotePublic {
  id: string;
  quote_number: string | null;
  revision: number;
  title: string;
  cover_text: string | null;
  scope: string | null;
  terms: string | null;
  status: string;
  subtotal: number;
  vat_amount: number;
  total: number;
  currency: string;
  valid_until: string | null;
  accepted_at: string | null;
  rejected_at: string | null;
  decline_reason: string | null;
  acceptance_name: string | null;
  line_items: LineItem[];
}

const BASE = process.env.NEXT_PUBLIC_API_URL ?? "";

export default function PublicQuotePage() {
  const params = useParams<{ token: string }>();
  const token = params.token;

  const [quote, setQuote] = useState<QuotePublic | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [acceptName, setAcceptName] = useState("");
  const [declineReason, setDeclineReason] = useState("");
  const [showDeclineForm, setShowDeclineForm] = useState(false);
  const [acting, setActing] = useState(false);
  const [done, setDone] = useState("");

  useEffect(() => {
    fetch(`${BASE}/api/quotes/view/${token}`)
      .then(r => r.ok ? r.json() : Promise.reject(r.status))
      .then(setQuote)
      .catch(() => setError("Quote not found or has expired."))
      .finally(() => setLoading(false));
  }, [token]);

  const isExpired = quote?.valid_until && new Date(quote.valid_until) < new Date();
  const canAct = quote?.status === "sent" || quote?.status === "viewed";

  async function accept() {
    if (!acceptName.trim()) { alert("Please type your name to accept."); return; }
    setActing(true);
    try {
      const r = await fetch(`${BASE}/api/quotes/view/${token}/accept`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ acceptance_name: acceptName }),
      });
      if (!r.ok) throw new Error("Accept failed");
      setDone("accepted");
      setQuote(q => q ? { ...q, status: "accepted", accepted_at: new Date().toISOString() } : q);
    } catch {
      alert("Something went wrong. Please try again.");
    } finally {
      setActing(false);
    }
  }

  async function decline() {
    setActing(true);
    try {
      const r = await fetch(`${BASE}/api/quotes/view/${token}/decline`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ reason: declineReason }),
      });
      if (!r.ok) throw new Error("Decline failed");
      setDone("declined");
      setQuote(q => q ? { ...q, status: "rejected", rejected_at: new Date().toISOString() } : q);
    } catch {
      alert("Something went wrong. Please try again.");
    } finally {
      setActing(false);
    }
  }

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="animate-pulse text-gray-400">Loading quote…</div>
      </div>
    );
  }

  if (error || !quote) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center space-y-2">
          <p className="text-xl font-semibold text-gray-700">{error || "Quote not found."}</p>
          <p className="text-sm text-gray-400">The link may have expired or been deactivated.</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50 py-10 px-4">
      <div className="mx-auto max-w-2xl space-y-6">
        {/* Header */}
        <div className="bg-white border rounded-2xl p-6 shadow-sm">
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-2">
              <div className="h-8 w-8 rounded bg-[#1a2332]" />
              <span className="font-bold text-[#1a2332] text-lg">Varuflow</span>
            </div>
            <span className={`px-3 py-1 rounded-full text-xs font-semibold ${
              quote.status === "accepted" ? "bg-green-100 text-green-700"
              : quote.status === "rejected" ? "bg-red-100 text-red-700"
              : isExpired ? "bg-gray-100 text-gray-500"
              : "bg-blue-100 text-blue-700"
            }`}>
              {quote.status === "accepted" ? "Accepted"
               : quote.status === "rejected" ? "Declined"
               : isExpired ? "Expired"
               : "Awaiting response"}
            </span>
          </div>

          <h1 className="text-2xl font-bold text-gray-900">{quote.title}</h1>
          {quote.quote_number && (
            <p className="text-sm text-gray-500 mt-1">
              Quote {quote.quote_number}{quote.revision > 1 ? ` · Rev. ${quote.revision}` : ""}
            </p>
          )}
          {quote.valid_until && (
            <p className={`text-sm mt-1 ${isExpired ? "text-red-600" : "text-gray-500"}`}>
              Valid until {new Date(quote.valid_until).toLocaleDateString("en-SE", { year: "numeric", month: "long", day: "numeric" })}
              {isExpired ? " — EXPIRED" : ""}
            </p>
          )}
        </div>

        {/* Cover text */}
        {quote.cover_text && (
          <div className="bg-white border rounded-2xl p-6 shadow-sm">
            <p className="text-gray-700 whitespace-pre-wrap">{quote.cover_text}</p>
          </div>
        )}

        {/* Scope */}
        {quote.scope && (
          <div className="bg-white border rounded-2xl p-6 shadow-sm">
            <h2 className="font-semibold text-gray-800 mb-2">Scope of work</h2>
            <p className="text-gray-700 whitespace-pre-wrap text-sm">{quote.scope}</p>
          </div>
        )}

        {/* Line items */}
        <div className="bg-white border rounded-2xl shadow-sm overflow-hidden">
          <div className="px-6 py-4 border-b">
            <h2 className="font-semibold text-gray-800">Pricing</h2>
          </div>
          <table className="w-full text-sm">
            <thead className="bg-gray-50 text-xs text-gray-500 uppercase">
              <tr>
                <th className="px-6 py-3 text-left">Description</th>
                <th className="px-6 py-3 text-right">Qty</th>
                <th className="px-6 py-3 text-right">Unit</th>
                <th className="px-6 py-3 text-right">Total</th>
              </tr>
            </thead>
            <tbody className="divide-y">
              {quote.line_items.map(item => (
                <tr key={item.id}>
                  <td className="px-6 py-3">{item.description}</td>
                  <td className="px-6 py-3 text-right">{item.quantity}</td>
                  <td className="px-6 py-3 text-right font-mono">{item.unit_price.toLocaleString("sv-SE", { minimumFractionDigits: 2 })} {quote.currency}</td>
                  <td className="px-6 py-3 text-right font-mono">{item.line_total.toLocaleString("sv-SE", { minimumFractionDigits: 2 })} {quote.currency}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <div className="px-6 py-4 border-t bg-gray-50 space-y-1 text-sm">
            <div className="flex justify-between text-gray-600">
              <span>Subtotal</span>
              <span className="font-mono">{quote.subtotal.toLocaleString("sv-SE", { minimumFractionDigits: 2 })} {quote.currency}</span>
            </div>
            <div className="flex justify-between text-gray-600">
              <span>VAT</span>
              <span className="font-mono">{quote.vat_amount.toLocaleString("sv-SE", { minimumFractionDigits: 2 })} {quote.currency}</span>
            </div>
            <div className="flex justify-between font-bold text-gray-900 text-base pt-1 border-t">
              <span>Total</span>
              <span className="font-mono">{quote.total.toLocaleString("sv-SE", { minimumFractionDigits: 2 })} {quote.currency}</span>
            </div>
          </div>
        </div>

        {/* Terms */}
        {quote.terms && (
          <div className="bg-white border rounded-2xl p-6 shadow-sm">
            <h2 className="font-semibold text-gray-800 mb-2">Terms & Conditions</h2>
            <p className="text-gray-600 text-sm whitespace-pre-wrap">{quote.terms}</p>
          </div>
        )}

        {/* Action area */}
        {done === "accepted" || quote.status === "accepted" ? (
          <div className="bg-green-50 border border-green-200 rounded-2xl p-6 text-center">
            <p className="text-xl font-bold text-green-700">Quote Accepted</p>
            {quote.acceptance_name && <p className="text-sm text-green-600 mt-1">Signed by: {quote.acceptance_name}</p>}
            {quote.accepted_at && <p className="text-xs text-green-500 mt-0.5">{new Date(quote.accepted_at).toLocaleString()}</p>}
            <p className="text-sm text-gray-600 mt-3">We will be in touch shortly to move forward.</p>
          </div>
        ) : done === "declined" || quote.status === "rejected" ? (
          <div className="bg-gray-50 border rounded-2xl p-6 text-center">
            <p className="text-lg font-semibold text-gray-700">Quote Declined</p>
            <p className="text-sm text-gray-500 mt-1">Thank you for letting us know.</p>
          </div>
        ) : canAct && !isExpired ? (
          <div className="bg-white border rounded-2xl p-6 shadow-sm space-y-4">
            <h2 className="font-semibold text-gray-800">Your response</h2>

            {!showDeclineForm ? (
              <>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Type your full name to accept
                  </label>
                  <input
                    type="text"
                    value={acceptName}
                    onChange={e => setAcceptName(e.target.value)}
                    placeholder="Full name"
                    className="w-full border rounded-lg px-4 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
                  />
                </div>
                <div className="flex gap-3">
                  <button
                    onClick={accept}
                    disabled={acting || !acceptName.trim()}
                    className="flex-1 bg-indigo-600 text-white rounded-lg py-2.5 font-semibold hover:bg-indigo-700 disabled:opacity-50 transition-colors"
                  >
                    {acting ? "Processing…" : "Accept Quote"}
                  </button>
                  <button
                    onClick={() => setShowDeclineForm(true)}
                    className="px-4 py-2.5 border rounded-lg text-sm text-gray-600 hover:bg-gray-50 transition-colors"
                  >
                    Decline
                  </button>
                </div>
              </>
            ) : (
              <>
                <textarea
                  value={declineReason}
                  onChange={e => setDeclineReason(e.target.value)}
                  placeholder="Optional: reason for declining"
                  className="w-full border rounded-lg px-4 py-2 text-sm h-20 focus:outline-none focus:ring-2 focus:ring-red-300"
                />
                <div className="flex gap-3">
                  <button
                    onClick={decline}
                    disabled={acting}
                    className="flex-1 bg-red-600 text-white rounded-lg py-2.5 font-semibold hover:bg-red-700 disabled:opacity-50 transition-colors"
                  >
                    {acting ? "Processing…" : "Confirm Decline"}
                  </button>
                  <button
                    onClick={() => setShowDeclineForm(false)}
                    className="px-4 py-2.5 border rounded-lg text-sm text-gray-600 hover:bg-gray-50 transition-colors"
                  >
                    Back
                  </button>
                </div>
              </>
            )}
          </div>
        ) : null}
      </div>
    </div>
  );
}
