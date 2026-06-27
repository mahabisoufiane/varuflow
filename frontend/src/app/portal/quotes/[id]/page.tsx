"use client";
import { useEffect, useState } from "react";
import { useRouter, useParams } from "next/navigation";
import { portalApi, PORTAL_TOKEN_KEY } from "@/lib/portal-client";

interface LineItem { description: string; quantity: number; unit_price: number; tax_rate: number; line_total: number; }
interface QuoteDetail { id: string; title: string; quote_number: string | null; revision: number; status: string; cover_text: string | null; scope: string | null; terms: string | null; subtotal: number; vat_amount: number; total: number; currency: string; valid_until: string | null; decline_reason: string | null; line_items: LineItem[]; }

const STATUS_BADGE: Record<string, string> = {
  draft:    "bg-gray-100 text-gray-600",
  sent:     "bg-blue-100 text-blue-800",
  viewed:   "bg-yellow-100 text-yellow-700",
  accepted: "bg-green-100 text-green-800",
  rejected: "bg-red-100 text-red-700",
  expired:  "bg-gray-200 text-gray-500",
  invoiced: "bg-purple-100 text-purple-700",
};

export default function PortalQuoteDetailPage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const [quote, setQuote] = useState<QuoteDetail | null>(null);
  const [showDecline, setShowDecline] = useState(false);
  const [declineReason, setDeclineReason] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const load = () => portalApi.get<QuoteDetail>(`/api/portal/quotes/${params.id}`).then(setQuote).catch(() => {});

  useEffect(() => {
    if (!localStorage.getItem(PORTAL_TOKEN_KEY)) { router.replace("/portal/login"); return; }
    load();
  }, [params.id]);

  const accept = async () => {
    setSubmitting(true);
    try { await portalApi.post(`/api/portal/quotes/${params.id}/accept`, {}); await load(); }
    finally { setSubmitting(false); }
  };

  const reject = async () => {
    setSubmitting(true);
    try { await portalApi.post(`/api/portal/quotes/${params.id}/reject`, { reason: declineReason }); await load(); setShowDecline(false); }
    finally { setSubmitting(false); }
  };

  if (!quote) return <div className="p-4">Loading...</div>;

  const canAct = ["sent", "viewed"].includes(quote.status);

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-bold">{quote.title}</h1>
        <span className={`px-2 py-0.5 rounded text-xs font-medium ${STATUS_BADGE[quote.status] ?? "bg-gray-100"}`}>{quote.status}</span>
      </div>
      <div className="text-sm text-gray-500 flex gap-2 flex-wrap">
        {quote.quote_number && <span>#{quote.quote_number} v{quote.revision}</span>}
        {quote.valid_until && <span>Valid until {quote.valid_until}</span>}
      </div>

      {quote.cover_text && <div className="bg-white border rounded p-4"><h3 className="font-medium mb-1">Cover</h3><p className="text-sm text-gray-700 whitespace-pre-wrap">{quote.cover_text}</p></div>}
      {quote.scope && <div className="bg-white border rounded p-4"><h3 className="font-medium mb-1">Scope</h3><p className="text-sm text-gray-700 whitespace-pre-wrap">{quote.scope}</p></div>}

      <table className="w-full text-sm border bg-white">
        <thead className="bg-gray-50">
          <tr><th className="px-4 py-2 text-left">Description</th><th className="px-4 py-2 text-right">Qty</th><th className="px-4 py-2 text-right">Price</th><th className="px-4 py-2 text-right">Total</th></tr>
        </thead>
        <tbody>
          {quote.line_items.map((li, i) => (
            <tr key={i} className="border-t"><td className="px-4 py-2">{li.description}</td><td className="px-4 py-2 text-right">{li.quantity}</td><td className="px-4 py-2 text-right">{li.unit_price.toLocaleString()}</td><td className="px-4 py-2 text-right">{li.line_total.toLocaleString()}</td></tr>
          ))}
        </tbody>
        <tfoot className="bg-gray-50">
          <tr><td colSpan={3} className="px-4 py-2 text-right font-medium">Subtotal</td><td className="px-4 py-2 text-right">{quote.subtotal.toLocaleString()}</td></tr>
          <tr><td colSpan={3} className="px-4 py-2 text-right font-medium">VAT</td><td className="px-4 py-2 text-right">{quote.vat_amount.toLocaleString()}</td></tr>
          <tr><td colSpan={3} className="px-4 py-2 text-right font-bold">Total</td><td className="px-4 py-2 text-right font-bold">{quote.total.toLocaleString()} {quote.currency}</td></tr>
        </tfoot>
      </table>

      {quote.terms && <div className="bg-white border rounded p-4"><h3 className="font-medium mb-1">Terms & Conditions</h3><p className="text-sm text-gray-700 whitespace-pre-wrap">{quote.terms}</p></div>}

      {quote.status === "rejected" && quote.decline_reason && (
        <div className="bg-red-50 border border-red-200 rounded p-4 text-sm text-red-700">
          <span className="font-medium">Decline reason: </span>{quote.decline_reason}
        </div>
      )}

      {canAct && (
        <div className="space-y-3">
          <div className="flex gap-3">
            <button onClick={accept} disabled={submitting} className="px-6 py-2 bg-green-600 text-white rounded hover:bg-green-700 disabled:opacity-50">Accept Quote</button>
            <button onClick={() => setShowDecline(s => !s)} disabled={submitting} className="px-6 py-2 bg-red-100 text-red-700 rounded hover:bg-red-200 disabled:opacity-50">Decline</button>
          </div>
          {showDecline && (
            <div className="space-y-2">
              <textarea rows={3} value={declineReason} onChange={e => setDeclineReason(e.target.value)} placeholder="Optional: reason for declining…" className="w-full border rounded px-3 py-2 text-sm resize-none focus:outline-none focus:ring-1" />
              <button onClick={reject} disabled={submitting} className="px-5 py-2 bg-red-600 text-white rounded text-sm hover:bg-red-700 disabled:opacity-50">Confirm Decline</button>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
