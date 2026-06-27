"use client";
import { useEffect, useState } from "react";
import { CheckCircle, XCircle, FileText, ChevronDown } from "lucide-react";

const API = process.env.NEXT_PUBLIC_API_URL ?? "";

interface LineItem {
  id: string;
  description: string;
  quantity: number;
  unit_price: number;
  tax_rate: number;
  line_total: number;
}

interface QuoteData {
  id: string;
  quote_number: string | null;
  revision: number;
  title: string;
  status: string;
  cover_text: string | null;
  scope: string | null;
  terms: string | null;
  subtotal: number;
  vat_amount: number;
  total: number;
  currency: string;
  valid_until: string | null;
  accepted_at: string | null;
  rejected_at: string | null;
  decline_reason: string | null;
  line_items: LineItem[];
}

const STATUS_MAP: Record<string, { label: string; color: string }> = {
  draft:    { label: "Draft",    color: "bg-gray-100 text-gray-600" },
  sent:     { label: "Sent",     color: "bg-blue-100 text-blue-700" },
  viewed:   { label: "Viewed",   color: "bg-yellow-100 text-yellow-700" },
  accepted: { label: "Accepted", color: "bg-green-100 text-green-700" },
  rejected: { label: "Declined", color: "bg-red-100 text-red-700" },
  expired:  { label: "Expired",  color: "bg-gray-200 text-gray-500" },
  invoiced: { label: "Invoiced", color: "bg-purple-100 text-purple-700" },
};

export default function PublicQuotePage({ params }: { params: { token: string } }) {
  const { token } = params;
  const [quote, setQuote] = useState<QuoteData | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [showDecline, setShowDecline] = useState(false);
  const [declineReason, setDeclineReason] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [done, setDone] = useState<"accepted" | "declined" | null>(null);

  useEffect(() => {
    fetch(`${API}/api/quotes/view/${token}`)
      .then(r => {
        if (!r.ok) throw new Error("Quote not found or link has expired.");
        return r.json();
      })
      .then(setQuote)
      .catch(e => setError(e.message))
      .finally(() => setLoading(false));
  }, [token]);

  const accept = async () => {
    setSubmitting(true);
    try {
      const r = await fetch(`${API}/api/quotes/view/${token}/accept`, { method: "POST" });
      if (!r.ok) throw new Error(await r.text());
      setDone("accepted");
      setQuote(q => q ? { ...q, status: "accepted" } : q);
    } catch (e: any) {
      alert(e.message ?? "Something went wrong.");
    } finally {
      setSubmitting(false);
    }
  };

  const decline = async () => {
    setSubmitting(true);
    try {
      const r = await fetch(`${API}/api/quotes/view/${token}/decline`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ reason: declineReason }),
      });
      if (!r.ok) throw new Error(await r.text());
      setDone("declined");
      setQuote(q => q ? { ...q, status: "rejected" } : q);
    } catch (e: any) {
      alert(e.message ?? "Something went wrong.");
    } finally {
      setSubmitting(false);
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50">
        <div className="text-gray-400 text-sm">Loading quote…</div>
      </div>
    );
  }

  if (error || !quote) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50">
        <div className="text-center space-y-2">
          <XCircle className="mx-auto text-red-400" size={40} />
          <p className="text-gray-700 font-medium">{error ?? "Quote not found."}</p>
          <p className="text-gray-400 text-sm">This link may have expired or been revoked.</p>
        </div>
      </div>
    );
  }

  const statusInfo = STATUS_MAP[quote.status] ?? { label: quote.status, color: "bg-gray-100 text-gray-600" };
  const canAct = ["sent", "viewed"].includes(quote.status) && !done;

  return (
    <div className="min-h-screen bg-gray-50 py-10 px-4">
      <div className="max-w-3xl mx-auto space-y-6">
        {/* Header */}
        <div className="bg-white rounded-xl border p-6 flex flex-col sm:flex-row sm:items-start sm:justify-between gap-4">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-lg bg-[#1a2332] flex items-center justify-center shrink-0">
              <FileText size={20} className="text-white" />
            </div>
            <div>
              <h1 className="text-lg font-bold text-gray-900">{quote.title}</h1>
              <p className="text-xs text-gray-400">
                Quote #{quote.quote_number ?? quote.id.slice(0, 8)} · Rev {quote.revision}
                {quote.valid_until && ` · Valid until ${quote.valid_until}`}
              </p>
            </div>
          </div>
          <span className={`px-3 py-1 rounded-full text-xs font-medium shrink-0 ${statusInfo.color}`}>
            {statusInfo.label}
          </span>
        </div>

        {/* Done banners */}
        {done === "accepted" && (
          <div className="bg-green-50 border border-green-200 rounded-xl p-5 flex items-center gap-3">
            <CheckCircle size={24} className="text-green-600 shrink-0" />
            <div>
              <p className="font-semibold text-green-800">Quote accepted — thank you!</p>
              <p className="text-sm text-green-600">We'll be in touch shortly to take the next steps.</p>
            </div>
          </div>
        )}
        {done === "declined" && (
          <div className="bg-red-50 border border-red-200 rounded-xl p-5 flex items-center gap-3">
            <XCircle size={24} className="text-red-500 shrink-0" />
            <div>
              <p className="font-semibold text-red-700">Quote declined.</p>
              <p className="text-sm text-red-500">Thank you for letting us know. We appreciate your feedback.</p>
            </div>
          </div>
        )}

        {/* Cover / scope */}
        {quote.cover_text && (
          <div className="bg-white rounded-xl border p-6 space-y-1">
            <p className="text-xs font-semibold text-gray-400 uppercase tracking-wide">Overview</p>
            <p className="text-sm text-gray-700 whitespace-pre-wrap">{quote.cover_text}</p>
          </div>
        )}
        {quote.scope && (
          <div className="bg-white rounded-xl border p-6 space-y-1">
            <p className="text-xs font-semibold text-gray-400 uppercase tracking-wide">Scope of Work</p>
            <p className="text-sm text-gray-700 whitespace-pre-wrap">{quote.scope}</p>
          </div>
        )}

        {/* Line items */}
        <div className="bg-white rounded-xl border overflow-hidden">
          <div className="px-6 py-4 border-b">
            <p className="text-xs font-semibold text-gray-400 uppercase tracking-wide">Line Items</p>
          </div>
          <table className="w-full text-sm">
            <thead className="bg-gray-50 text-xs text-gray-500">
              <tr>
                <th className="text-left px-6 py-3">Description</th>
                <th className="text-right px-4 py-3">Qty</th>
                <th className="text-right px-4 py-3">Unit Price</th>
                <th className="text-right px-4 py-3">Tax</th>
                <th className="text-right px-6 py-3">Total</th>
              </tr>
            </thead>
            <tbody className="divide-y">
              {quote.line_items.map(item => (
                <tr key={item.id}>
                  <td className="px-6 py-3 text-gray-800">{item.description}</td>
                  <td className="px-4 py-3 text-right text-gray-600">{item.quantity}</td>
                  <td className="px-4 py-3 text-right text-gray-600">{item.unit_price.toFixed(2)}</td>
                  <td className="px-4 py-3 text-right text-gray-600">{item.tax_rate}%</td>
                  <td className="px-6 py-3 text-right font-medium">{item.line_total.toFixed(2)}</td>
                </tr>
              ))}
            </tbody>
            <tfoot className="bg-gray-50 border-t text-sm">
              <tr>
                <td colSpan={4} className="px-6 py-2 text-right text-gray-500">Subtotal</td>
                <td className="px-6 py-2 text-right">{quote.subtotal.toFixed(2)}</td>
              </tr>
              <tr>
                <td colSpan={4} className="px-6 py-2 text-right text-gray-500">VAT</td>
                <td className="px-6 py-2 text-right">{quote.vat_amount.toFixed(2)}</td>
              </tr>
              <tr className="font-bold">
                <td colSpan={4} className="px-6 py-3 text-right">Total</td>
                <td className="px-6 py-3 text-right">{quote.total.toFixed(2)} {quote.currency}</td>
              </tr>
            </tfoot>
          </table>
        </div>

        {/* Terms */}
        {quote.terms && (
          <div className="bg-white rounded-xl border p-6 space-y-1">
            <p className="text-xs font-semibold text-gray-400 uppercase tracking-wide">Terms &amp; Conditions</p>
            <p className="text-sm text-gray-600 whitespace-pre-wrap">{quote.terms}</p>
          </div>
        )}

        {/* Actions */}
        {canAct && (
          <div className="bg-white rounded-xl border p-6 space-y-4">
            <p className="text-sm font-medium text-gray-700">Ready to proceed?</p>
            <div className="flex flex-wrap gap-3">
              <button
                onClick={accept}
                disabled={submitting}
                className="px-5 py-2.5 rounded-lg bg-green-600 text-white text-sm font-medium hover:bg-green-700 disabled:opacity-50 flex items-center gap-2"
              >
                <CheckCircle size={15} />
                Accept Quote
              </button>
              <button
                onClick={() => setShowDecline(s => !s)}
                disabled={submitting}
                className="px-5 py-2.5 rounded-lg border border-red-300 text-red-600 text-sm font-medium hover:bg-red-50 disabled:opacity-50 flex items-center gap-2"
              >
                <ChevronDown size={15} className={showDecline ? "rotate-180 transition-transform" : "transition-transform"} />
                Decline
              </button>
            </div>
            {showDecline && (
              <div className="space-y-3 pt-1">
                <textarea
                  rows={3}
                  value={declineReason}
                  onChange={e => setDeclineReason(e.target.value)}
                  placeholder="Optional: let us know why you're declining…"
                  className="w-full border rounded-lg px-3 py-2 text-sm resize-none focus:outline-none focus:ring-1 focus:ring-red-400"
                />
                <button
                  onClick={decline}
                  disabled={submitting}
                  className="px-5 py-2 rounded-lg bg-red-600 text-white text-sm font-medium hover:bg-red-700 disabled:opacity-50"
                >
                  Confirm Decline
                </button>
              </div>
            )}
          </div>
        )}

        {/* Already actioned */}
        {quote.status === "accepted" && !done && (
          <div className="bg-green-50 border border-green-200 rounded-xl p-5 flex items-center gap-3">
            <CheckCircle size={20} className="text-green-600 shrink-0" />
            <p className="text-sm text-green-700 font-medium">This quote has already been accepted.</p>
          </div>
        )}
        {quote.status === "rejected" && !done && (
          <div className="bg-red-50 border border-red-200 rounded-xl p-5 space-y-1">
            <p className="text-sm text-red-700 font-medium">This quote has been declined.</p>
            {quote.decline_reason && <p className="text-xs text-red-500">{quote.decline_reason}</p>}
          </div>
        )}
        {quote.status === "expired" && (
          <div className="bg-gray-100 border rounded-xl p-5">
            <p className="text-sm text-gray-600 font-medium">This quote has expired. Please contact us for a revised proposal.</p>
          </div>
        )}

        <p className="text-center text-xs text-gray-300 pb-4">Powered by Varuflow</p>
      </div>
    </div>
  );
}
