"use client";

import { api } from "@/lib/api-client";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { useRouter, useParams } from "next/navigation";
import { useEffect, useState } from "react";
import Link from "next/link";
import { useLocale } from "next-intl";
import { ArrowLeft, Mail, Link2, CheckCircle2, Clock } from "lucide-react";

interface LineItem { id: string; description: string; quantity: string; unit_price: string; tax_rate: string; line_total: string; }
interface Payment { id: string; amount: string; payment_date: string; method: string; reference: string | null; }
interface Invoice {
  id: string; invoice_number: string; status: string;
  issue_date: string; due_date: string; notes: string | null;
  subtotal: string; vat_amount: string; total_sek: string;
  stripe_payment_link_url: string | null;
  stripe_payment_link_status: string | null;
  customer: { company_name: string; org_number: string | null; vat_number: string | null; email: string | null; address: string | null; };
  line_items: LineItem[];
}

const STATUS_COLORS: Record<string, string> = {
  DRAFT: "bg-gray-100 text-gray-700",
  SENT: "bg-blue-100 text-blue-700",
  PAID: "bg-green-100 text-green-700",
  OVERDUE: "bg-red-100 text-red-700",
};

const NEXT_STATUS: Record<string, string | null> = { DRAFT: "SENT", SENT: "PAID", OVERDUE: "PAID", PAID: null };
const NEXT_LABEL: Record<string, string> = { DRAFT: "Mark Sent", SENT: "Mark Paid", OVERDUE: "Mark Paid" };

export default function InvoiceDetailPage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const locale = useLocale();
  const [invoice, setInvoice] = useState<Invoice | null>(null);
  const [payments, setPayments] = useState<Payment[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [updating, setUpdating] = useState(false);
  const [sending, setSending] = useState(false);
  const [sendMsg, setSendMsg] = useState<string | null>(null);
  const [linkSending, setLinkSending] = useState(false);
  const [payOpen, setPayOpen] = useState(false);
  const [payForm, setPayForm] = useState({ amount: "", payment_date: "", method: "BANK_TRANSFER", reference: "" });
  const [paying, setPaying] = useState(false);

  async function load() {
    try {
      const [inv, pays] = await Promise.all([
        api.get<Invoice>(`/api/invoicing/invoices/${params.id}`),
        api.get<Payment[]>(`/api/invoicing/invoices/${params.id}/payments`),
      ]);
      setInvoice(inv);
      setPayments(pays);
    } catch (e: any) { setError(e.message); } finally { setLoading(false); }
  }

  useEffect(() => { load(); }, [params.id]);

  async function advanceStatus() {
    if (!invoice) return;
    const next = NEXT_STATUS[invoice.status];
    if (!next) return;
    setUpdating(true);
    try {
      await api.patch(`/api/invoicing/invoices/${invoice.id}/status`, { status: next });
      await load();
    } catch (e: any) { setError(e.message); } finally { setUpdating(false); }
  }

  async function handlePayment(e: React.FormEvent) {
    e.preventDefault(); setPaying(true); setError(null);
    try {
      await api.post(`/api/invoicing/invoices/${params.id}/payments`, {
        amount: Number(payForm.amount),
        payment_date: payForm.payment_date,
        method: payForm.method,
        reference: payForm.reference || null,
      });
      setPayOpen(false);
      await load();
    } catch (e: any) { setError(e.message); } finally { setPaying(false); }
  }

  async function handleSendEmail() {
    if (!invoice) return;
    setSending(true); setSendMsg(null); setError(null);
    try {
      const res = await api.post<{ status: string; to?: string; reason?: string }>(
        `/api/invoicing/invoices/${invoice.id}/send`, {}
      );
      setSendMsg(res.status === "sent" ? `Sent to ${res.to}` : res.reason ?? "Skipped");
    } catch (e: any) { setError(e.message); } finally { setSending(false); }
  }

  async function handleSendPaymentLink() {
    if (!invoice) return;
    setLinkSending(true); setError(null);
    try {
      await api.post(`/api/invoicing/invoices/${invoice.id}/payment-link`, {});
      await load();
    } catch (e: any) { setError(e.message); } finally { setLinkSending(false); }
  }

  async function handleDelete() {
    if (!invoice || invoice.status !== "DRAFT") return;
    if (!confirm("Delete this draft invoice?")) return;
    try {
      await api.delete(`/api/invoicing/invoices/${invoice.id}`);
      router.push("/invoices");
    } catch (e: any) { setError(e.message); }
  }

  if (loading) return (
    <div className="space-y-4 animate-pulse">
      <div className="h-8 w-48 rounded bg-gray-100" />
      <div className="h-48 rounded-xl bg-gray-100" />
    </div>
  );
  if (!invoice) return <p className="text-red-600">{error ?? "Invoice not found"}</p>;

  const totalPaid = payments.reduce((s, p) => s + Number(p.amount), 0);
  const balance = Number(invoice.total_sek) - totalPaid;

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <div>
        <Button asChild variant="ghost" size="sm" className="mb-2 -ml-2 text-muted-foreground">
          <Link href="/invoices"><ArrowLeft className="mr-1 h-3.5 w-3.5" />Invoices</Link>
        </Button>
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-[#1a2332]">{invoice.invoice_number}</h1>
            <span className={`mt-1 inline-block rounded px-2 py-0.5 text-xs font-medium ${STATUS_COLORS[invoice.status]}`}>{invoice.status}</span>
          </div>
          <div className="flex flex-wrap gap-2">
            <Button variant="ghost" size="sm" onClick={() => window.open(api.downloadUrl(`/api/invoicing/invoices/${invoice.id}/pdf`), "_blank")}>
              PDF
            </Button>
            <Button variant="ghost" size="sm" onClick={() => window.open(api.downloadUrl(`/api/invoicing/invoices/${invoice.id}/peppol`), "_blank")}>
              Peppol XML
            </Button>
            {locale === "no" && (
              <Button variant="ghost" size="sm" onClick={() => window.open(api.downloadUrl(`/api/invoicing/invoices/${invoice.id}/ehf`), "_blank")}>
                EHF XML
              </Button>
            )}
            {invoice.status !== "DRAFT" && invoice.customer.email && (
              <Button variant="outline" size="sm" disabled={sending} onClick={handleSendEmail}>
                <Mail className="mr-1.5 h-3.5 w-3.5" />{sending ? "Sending…" : "Email to customer"}
              </Button>
            )}
            {(invoice.status === "SENT" || invoice.status === "OVERDUE") && invoice.customer.email && (
              invoice.stripe_payment_link_url && invoice.stripe_payment_link_status !== "expired" ? (
                <div className="flex items-center gap-1.5">
                  {invoice.stripe_payment_link_status === "paid" ? (
                    <span className="inline-flex items-center gap-1 rounded px-2 py-1 text-xs font-medium bg-green-100 text-green-700">
                      <CheckCircle2 className="h-3 w-3" />Paid via link
                    </span>
                  ) : (
                    <>
                      <span className="inline-flex items-center gap-1 rounded px-2 py-1 text-xs font-medium bg-yellow-100 text-yellow-700">
                        <Clock className="h-3 w-3" />Link sent
                      </span>
                      <Button variant="ghost" size="sm" onClick={() => window.open(invoice.stripe_payment_link_url!, "_blank")}>
                        <Link2 className="mr-1 h-3.5 w-3.5" />Open
                      </Button>
                    </>
                  )}
                </div>
              ) : (
                <Button variant="outline" size="sm" disabled={linkSending} onClick={handleSendPaymentLink}>
                  <Link2 className="mr-1.5 h-3.5 w-3.5" />{linkSending ? "Creating…" : "Send payment link"}
                </Button>
              )
            )}
            {NEXT_STATUS[invoice.status] && (
              <Button size="sm" className="bg-[#1a2332] hover:bg-[#2a3342] text-white" disabled={updating} onClick={advanceStatus}>
                {NEXT_LABEL[invoice.status]}
              </Button>
            )}
            {(invoice.status === "SENT" || invoice.status === "OVERDUE") && (
              <Button variant="outline" size="sm" onClick={() => { setPayForm((f) => ({ ...f, amount: String(balance.toFixed(2)), payment_date: new Date().toISOString().slice(0, 10) })); setPayOpen(true); }}>
                Record payment
              </Button>
            )}
            {invoice.status === "DRAFT" && (
              <Button variant="ghost" size="sm" className="text-red-500 hover:text-red-700" onClick={handleDelete}>Delete</Button>
            )}
          </div>
          {sendMsg && <p className="mt-1 text-xs text-green-600">{sendMsg}</p>}
        </div>
      </div>

      {error && <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-2 text-sm text-red-700">{error}</div>}

      {/* Customer + dates */}
      <div className="rounded-xl border bg-white p-6 grid grid-cols-2 gap-6">
        <div>
          <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide mb-2">Bill To</p>
          <p className="font-semibold text-gray-900">{invoice.customer.company_name}</p>
          {invoice.customer.org_number && <p className="text-sm text-muted-foreground">Org: {invoice.customer.org_number}</p>}
          {invoice.customer.vat_number && <p className="text-sm text-muted-foreground">VAT: {invoice.customer.vat_number}</p>}
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
              <td colSpan={4} className="px-4 py-2 text-right text-muted-foreground">VAT</td>
              <td className="px-4 py-2 text-right font-mono">{Number(invoice.vat_amount).toLocaleString("sv-SE", { minimumFractionDigits: 2 })}</td>
            </tr>
            <tr className="font-bold text-[#1a2332]">
              <td colSpan={4} className="px-4 py-3 text-right">Total (SEK)</td>
              <td className="px-4 py-3 text-right font-mono text-base">{Number(invoice.total_sek).toLocaleString("sv-SE", { minimumFractionDigits: 2 })}</td>
            </tr>
          </tfoot>
        </table>
      </div>

      {/* Payments */}
      {payments.length > 0 && (
        <div className="rounded-xl border bg-white p-6 space-y-3">
          <h2 className="font-semibold text-gray-900">Payments received</h2>
          <div className="divide-y">
            {payments.map((p) => (
              <div key={p.id} className="flex items-center justify-between py-2 text-sm">
                <span className="text-muted-foreground">{p.payment_date} · {p.method.replace("_", " ")}{p.reference ? ` · ${p.reference}` : ""}</span>
                <span className="font-mono font-medium">{Number(p.amount).toLocaleString("sv-SE", { minimumFractionDigits: 2 })} SEK</span>
              </div>
            ))}
          </div>
          {balance > 0.005 && (
            <div className="flex justify-between text-sm font-semibold text-red-600 border-t pt-2">
              <span>Balance due</span>
              <span className="font-mono">{balance.toLocaleString("sv-SE", { minimumFractionDigits: 2 })} SEK</span>
            </div>
          )}
        </div>
      )}

      {/* Record payment dialog */}
      <Dialog open={payOpen} onOpenChange={setPayOpen}>
        <DialogContent className="sm:max-w-sm">
          <DialogHeader><DialogTitle>Record payment</DialogTitle></DialogHeader>
          <form onSubmit={handlePayment} className="space-y-4 pt-2">
            <div className="space-y-1.5">
              <Label>Amount (SEK) *</Label>
              <input type="number" step="0.01" min="0.01" required value={payForm.amount}
                onChange={(e) => setPayForm((f) => ({ ...f, amount: e.target.value }))}
                className="block w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-[#1a2332] focus:outline-none focus:ring-1 focus:ring-[#1a2332]" />
            </div>
            <div className="space-y-1.5">
              <Label>Payment date *</Label>
              <input type="date" required value={payForm.payment_date}
                onChange={(e) => setPayForm((f) => ({ ...f, payment_date: e.target.value }))}
                className="block w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-[#1a2332] focus:outline-none focus:ring-1 focus:ring-[#1a2332]" />
            </div>
            <div className="space-y-1.5">
              <Label>Method</Label>
              <select value={payForm.method} onChange={(e) => setPayForm((f) => ({ ...f, method: e.target.value }))}
                className="block w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-[#1a2332] focus:outline-none focus:ring-1 focus:ring-[#1a2332]">
                <option value="BANK_TRANSFER">Bank transfer</option>
                <option value="CARD">Card</option>
                <option value="CASH">Cash</option>
                <option value="OTHER">Other</option>
              </select>
            </div>
            <div className="space-y-1.5">
              <Label>Reference</Label>
              <input value={payForm.reference} onChange={(e) => setPayForm((f) => ({ ...f, reference: e.target.value }))}
                placeholder="Transaction ID, bank ref…"
                className="block w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-[#1a2332] focus:outline-none focus:ring-1 focus:ring-[#1a2332]" />
            </div>
            {error && <p className="text-sm text-red-600">{error}</p>}
            <div className="flex justify-end gap-3 pt-2">
              <Button type="button" variant="outline" onClick={() => setPayOpen(false)}>Cancel</Button>
              <Button type="submit" disabled={paying} className="bg-[#1a2332] hover:bg-[#2a3342] text-white">
                {paying ? "Saving…" : "Record"}
              </Button>
            </div>
          </form>
        </DialogContent>
      </Dialog>
    </div>
  );
}
