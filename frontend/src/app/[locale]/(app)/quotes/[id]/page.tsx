"use client";
import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { api } from "@/lib/api-client";
import { Copy, Download, Check } from "lucide-react";

interface LineItem { id: string; description: string; quantity: number; unit_price: number; tax_rate: number; line_total: number; }
interface QuoteDetail { id: string; title: string; quote_number: string | null; revision: number; status: string; cover_text: string | null; scope: string | null; terms: string | null; subtotal: number; vat_amount: number; total: number; currency: string; valid_until: string | null; customer_id: string; invoice_id: string | null; parent_quote_id: string | null; decline_reason: string | null; public_token: string | null; line_items: LineItem[]; }

export default function QuoteDetailPage() {
  const params = useParams<{ id: string }>();
  const [quote, setQuote] = useState<QuoteDetail | null>(null);
  const [copied, setCopied] = useState(false);

  const load = () => {
    api.get<QuoteDetail>(`/api/quotes/${params.id}`).then(setQuote).catch(() => {});
  };

  useEffect(() => { load(); }, [params.id]);

  const action = async (path: string) => {
    await api.post(`/api/quotes/${params.id}/${path}`, {}).catch(() => {});
    load();
  };

  const downloadPdf = () => {
    window.open(api.downloadUrl(`/api/quotes/${params.id}/pdf`), "_blank");
  };

  const copyLink = () => {
    if (!quote?.public_token) return;
    const url = `${window.location.origin}/q/${quote.public_token}`;
    navigator.clipboard.writeText(url).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    });
  };

  if (!quote) return <div className="p-6">Loading...</div>;

  const badge = (s: string) => {
    const c: Record<string, string> = { draft: "bg-gray-100", sent: "bg-blue-100 text-blue-800", viewed: "bg-yellow-100 text-yellow-700", accepted: "bg-green-100 text-green-800", rejected: "bg-red-100 text-red-800", expired: "bg-gray-200 text-gray-500", invoiced: "bg-purple-100 text-purple-800" };
    return <span className={`px-2 py-0.5 rounded text-xs font-medium ${c[s] || "bg-gray-100"}`}>{s}</span>;
  };

  return (
    <div className="p-6 max-w-3xl space-y-4">
      <div className="flex items-center justify-between flex-wrap gap-2">
        <div className="flex items-center gap-3">
          <h1 className="text-2xl font-bold">{quote.title}</h1>
          {badge(quote.status)}
        </div>
        <div className="flex gap-2">
          <button onClick={downloadPdf} className="flex items-center gap-1.5 px-3 py-1.5 border rounded text-sm hover:bg-gray-50">
            <Download size={14} /> PDF
          </button>
          {quote.public_token && (
            <button onClick={copyLink} className="flex items-center gap-1.5 px-3 py-1.5 border rounded text-sm hover:bg-gray-50">
              {copied ? <Check size={14} className="text-green-600" /> : <Copy size={14} />}
              {copied ? "Copied!" : "Copy Link"}
            </button>
          )}
        </div>
      </div>
      <div className="text-sm text-gray-500">{quote.quote_number && `#${quote.quote_number} `}v{quote.revision} · {quote.currency} · Valid until: {quote.valid_until || "∞"}</div>

      {quote.cover_text && <div className="bg-white border rounded p-4"><h3 className="font-medium text-sm mb-1">Cover</h3><p className="text-sm whitespace-pre-wrap">{quote.cover_text}</p></div>}
      {quote.scope && <div className="bg-white border rounded p-4"><h3 className="font-medium text-sm mb-1">Scope</h3><p className="text-sm whitespace-pre-wrap">{quote.scope}</p></div>}

      <table className="w-full text-sm border">
        <thead className="bg-gray-50"><tr><th className="px-4 py-2 text-left">Description</th><th className="px-4 py-2 text-right">Qty</th><th className="px-4 py-2 text-right">Price</th><th className="px-4 py-2 text-right">Total</th></tr></thead>
        <tbody>
          {quote.line_items.map(li => (
            <tr key={li.id} className="border-t"><td className="px-4 py-2">{li.description}</td><td className="px-4 py-2 text-right">{li.quantity}</td><td className="px-4 py-2 text-right">{li.unit_price.toLocaleString()}</td><td className="px-4 py-2 text-right">{li.line_total.toLocaleString()}</td></tr>
          ))}
        </tbody>
        <tfoot className="bg-gray-50 font-medium">
          <tr><td colSpan={3} className="px-4 py-2 text-right">Subtotal</td><td className="px-4 py-2 text-right">{quote.subtotal.toLocaleString()}</td></tr>
          <tr><td colSpan={3} className="px-4 py-2 text-right">VAT</td><td className="px-4 py-2 text-right">{quote.vat_amount.toLocaleString()}</td></tr>
          <tr><td colSpan={3} className="px-4 py-2 text-right font-bold">Total</td><td className="px-4 py-2 text-right font-bold">{quote.total.toLocaleString()} {quote.currency}</td></tr>
        </tfoot>
      </table>

      {quote.terms && <div className="bg-white border rounded p-4"><h3 className="font-medium text-sm mb-1">Terms</h3><p className="text-sm whitespace-pre-wrap">{quote.terms}</p></div>}

      {quote.decline_reason && (
        <div className="bg-red-50 border border-red-200 rounded p-3 text-sm text-red-700">
          <span className="font-medium">Decline reason: </span>{quote.decline_reason}
        </div>
      )}

      <div className="flex gap-3 flex-wrap">
        {quote.status === "draft" && <button onClick={() => action("send")} className="px-4 py-2 bg-blue-600 text-white rounded">Send to Client</button>}
        {["sent", "viewed", "accepted", "rejected"].includes(quote.status) && <button onClick={() => action("revise")} className="px-4 py-2 bg-gray-200 rounded">Create Revision</button>}
        {quote.status === "accepted" && !quote.invoice_id && <button onClick={() => action("convert")} className="px-4 py-2 bg-green-600 text-white rounded">Convert to Invoice</button>}
        {quote.invoice_id && <span className="text-sm text-purple-600 self-center">Invoice created</span>}
      </div>
    </div>
  );
}
