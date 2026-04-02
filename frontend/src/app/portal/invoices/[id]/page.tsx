"use client";

import { useEffect, useState } from "react";
import { useRouter, useParams } from "next/navigation";
import Link from "next/link";
import { portalApi, PORTAL_TOKEN_KEY } from "@/lib/portal-client";

interface LineItem { id: string; description: string; quantity: string; unit_price: string; tax_rate: string; line_total: string; }
interface Invoice {
  id: string;
  invoice_number: string;
  status: string;
  issue_date: string;
  due_date: string;
  notes: string | null;
  subtotal: string;
  vat_amount: string;
  total_sek: string;
  stripe_payment_link_url: string | null;
  stripe_payment_link_status: string | null;
  customer: { company_name: string; org_number: string | null; email: string | null; address: string | null; };
  line_items: LineItem[];
}

const STATUS_COLORS: Record<string, string> = {
  SENT: "bg-blue-100 text-blue-700",
  PAID: "bg-green-100 text-green-700",
  OVERDUE: "bg-red-100 text-red-700",
};

export default function PortalInvoiceDetailPage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const [invoice, setInvoice] = useState<Invoice | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const token = localStorage.getItem(PORTAL_TOKEN_KEY);
    if (!token) { router.replace("/portal/login"); return; }

    portalApi
      .get<Invoice>(`/api/portal/invoices/${params.id}`)
      .then(setInvoice)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [params.id, router]);

  if (loading) {
    return (
      <div className="space-y-4 animate-pulse">
        <div className="h-8 w-48 rounded bg-gray-100" />
        <div className="h-48 rounded-xl bg-gray-100" />
      </div>
    );
  }
  if (!invoice) return <p className="text-red-600">{error ?? "Invoice not found"}</p>;

  const canPay = (invoice.status === "SENT" || invoice.status === "OVERDUE")
    && invoice.stripe_payment_link_url
    && invoice.stripe_payment_link_status !== "paid"
    && invoice.stripe_payment_link_status !== "expired";

  return (
    <div className="space-y-6">
      <div>
        <Link href="/portal/invoices" className="text-sm text-muted-foreground hover:text-gray-900">
          ← Back to invoices
        </Link>
        <div className="mt-3 flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-[#1a2332]">{invoice.invoice_number}</h1>
            <span className={`mt-1 inline-block rounded px-2 py-0.5 text-xs font-medium ${STATUS_COLORS[invoice.status] ?? "bg-gray-100 text-gray-700"}`}>
              {invoice.status}
            </span>
          </div>
          <div className="flex gap-2">
            <a
              href={`${process.env.NEXT_PUBLIC_API_URL}/api/portal/invoices/${invoice.id}/pdf`}
              download
              className="rounded-md border border-gray-300 bg-white px-3 py-1.5 text-sm font-medium hover:bg-gray-50"
              onClick={(e) => {
                // Attach token via fetch instead of direct href — token is in localStorage
                e.preventDefault();
                const token = localStorage.getItem(PORTAL_TOKEN_KEY);
                if (!token) return;
                fetch(`${process.env.NEXT_PUBLIC_API_URL}/api/portal/invoices/${invoice.id}/pdf`, {
                  headers: { Authorization: `Bearer ${token}` },
                })
                  .then((r) => r.blob())
                  .then((blob) => {
                    const url = URL.createObjectURL(blob);
                    const a = document.createElement("a");
                    a.href = url;
                    a.download = `${invoice.invoice_number}.pdf`;
                    a.click();
                    URL.revokeObjectURL(url);
                  });
              }}
            >
              Download PDF
            </a>
            {canPay && (
              <a
                href={invoice.stripe_payment_link_url!}
                target="_blank"
                rel="noreferrer"
                className="rounded-md bg-[#1a2332] px-4 py-1.5 text-sm font-semibold text-white hover:bg-[#2a3342]"
              >
                Pay now
              </a>
            )}
            {invoice.stripe_payment_link_status === "paid" && (
              <span className="inline-flex items-center gap-1.5 rounded-md bg-green-100 px-3 py-1.5 text-sm font-medium text-green-700">
                <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                </svg>
                Paid online
              </span>
            )}
          </div>
        </div>
      </div>

      {/* Customer + dates */}
      <div className="rounded-xl border bg-white p-6 grid grid-cols-2 gap-6">
        <div>
          <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide mb-2">Bill To</p>
          <p className="font-semibold text-gray-900">{invoice.customer.company_name}</p>
          {invoice.customer.org_number && <p className="text-sm text-muted-foreground">Org: {invoice.customer.org_number}</p>}
          {invoice.customer.email && <p className="text-sm text-muted-foreground">{invoice.customer.email}</p>}
          {invoice.customer.address && <p className="text-sm text-muted-foreground">{invoice.customer.address}</p>}
        </div>
        <div className="space-y-2">
          <div>
            <p className="text-xs text-muted-foreground">Issue date</p>
            <p className="text-sm font-medium">{invoice.issue_date}</p>
          </div>
          <div>
            <p className="text-xs text-muted-foreground">Due date</p>
            <p className="text-sm font-medium">{invoice.due_date}</p>
          </div>
          {invoice.notes && (
            <div>
              <p className="text-xs text-muted-foreground">Notes</p>
              <p className="text-sm">{invoice.notes}</p>
            </div>
          )}
        </div>
      </div>

      {/* Line items */}
      <div className="rounded-xl border bg-white overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-gray-50 text-xs text-gray-500 uppercase">
            <tr>
              <th className="px-4 py-3 text-left">Description</th>
              <th className="px-4 py-3 text-right">Qty</th>
              <th className="px-4 py-3 text-right">Unit price</th>
              <th className="px-4 py-3 text-right">VAT</th>
              <th className="px-4 py-3 text-right">Total (SEK)</th>
            </tr>
          </thead>
          <tbody className="divide-y">
            {invoice.line_items.map((li) => (
              <tr key={li.id}>
                <td className="px-4 py-3">{li.description}</td>
                <td className="px-4 py-3 text-right font-mono">{li.quantity}</td>
                <td className="px-4 py-3 text-right font-mono">{Number(li.unit_price).toLocaleString("sv-SE", { minimumFractionDigits: 2 })}</td>
                <td className="px-4 py-3 text-right text-muted-foreground">{li.tax_rate}%</td>
                <td className="px-4 py-3 text-right font-mono">{Number(li.line_total).toLocaleString("sv-SE", { minimumFractionDigits: 2 })}</td>
              </tr>
            ))}
          </tbody>
          <tfoot className="border-t bg-gray-50 text-sm">
            <tr>
              <td colSpan={4} className="px-4 py-2 text-right text-muted-foreground">Subtotal</td>
              <td className="px-4 py-2 text-right font-mono">{Number(invoice.subtotal).toLocaleString("sv-SE", { minimumFractionDigits: 2 })}</td>
            </tr>
            <tr>
              <td colSpan={4} className="px-4 py-2 text-right text-muted-foreground">VAT (25%)</td>
              <td className="px-4 py-2 text-right font-mono">{Number(invoice.vat_amount).toLocaleString("sv-SE", { minimumFractionDigits: 2 })}</td>
            </tr>
            <tr className="font-bold text-[#1a2332]">
              <td colSpan={4} className="px-4 py-3 text-right">Total (SEK)</td>
              <td className="px-4 py-3 text-right font-mono text-base">{Number(invoice.total_sek).toLocaleString("sv-SE", { minimumFractionDigits: 2 })}</td>
            </tr>
          </tfoot>
        </table>
      </div>
    </div>
  );
}
