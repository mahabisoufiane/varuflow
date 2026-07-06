"use client";

import { api } from "@/lib/api-client";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { useRouter } from "@/i18n/navigation";
import { useEffect, useState } from "react";
import { Link } from "@/i18n/navigation";
import { ArrowLeft, Plus, Trash2 } from "lucide-react";

interface Customer { id: string; company_name: string; payment_terms_days: number; }
interface Product { id: string; name: string; sku: string; sell_price: string; tax_rate: string; }
interface LineItem { description: string; product_id: string; quantity: string; unit_price: string; tax_rate: string; }
interface ExistingInvoice { id: string; invoice_number: string; total_sek: string; invoice_type: string; deposit_amount: string | null; }

type InvoiceType = "standard" | "deposit" | "final";

const TYPE_LABELS: Record<InvoiceType, { label: string; desc: string }> = {
  standard: { label: "Standard Invoice", desc: "Regular invoice for goods or services" },
  deposit:  { label: "Deposit Invoice",  desc: "Advance/deposit before work begins" },
  final:    { label: "Final Invoice",    desc: "Balance due — deposit auto-offset in PDF" },
};

function todayStr() { return new Date().toISOString().slice(0, 10); }
function addDays(d: string, n: number) {
  const dt = new Date(d); dt.setDate(dt.getDate() + n); return dt.toISOString().slice(0, 10);
}

export default function NewInvoicePage() {
  const router = useRouter();
  const [customers, setCustomers] = useState<Customer[]>([]);
  const [products, setProducts] = useState<Product[]>([]);
  const [customerId, setCustomerId] = useState("");
  const [issueDate, setIssueDate] = useState("");
  const [dueDate, setDueDate] = useState("");
  const [notes, setNotes] = useState("");
  const [items, setItems] = useState<LineItem[]>([{ description: "", product_id: "", quantity: "1", unit_price: "", tax_rate: "25" }]);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [invoiceType, setInvoiceType] = useState<InvoiceType>("standard");
  const [parentInvoiceId, setParentInvoiceId] = useState("");
  const [customerInvoices, setCustomerInvoices] = useState<ExistingInvoice[]>([]);

  useEffect(() => {
    const t = todayStr();
    setIssueDate(t);
    setDueDate(addDays(t, 30));
  }, []);

  const [loadingRefs, setLoadingRefs] = useState(true);
  useEffect(() => {
    Promise.all([
      api.get<Customer[]>("/api/invoicing/customers?is_active=true"),
      api.get<{ items: Product[] }>("/api/inventory/products?limit=200&is_active=true"),
    ]).then(([c, p]) => { setCustomers(c); setProducts(p.items); })
      .catch((e) => setError(e.message))
      .finally(() => setLoadingRefs(false));
  }, []);

  async function loadCustomerDepositInvoices(cid: string) {
    if (!cid) { setCustomerInvoices([]); return; }
    try {
      const data = await api.get<ExistingInvoice[] | { invoices: ExistingInvoice[] }>(`/api/invoicing/invoices?customer_id=${cid}&limit=100`);
      const list: ExistingInvoice[] = Array.isArray(data) ? data : (data as any).invoices ?? [];
      setCustomerInvoices(list.filter((i) => i.invoice_type === "deposit"));
    } catch { setCustomerInvoices([]); }
  }

  function handleCustomerChange(id: string) {
    setCustomerId(id);
    const c = customers.find((c) => c.id === id);
    if (c) setDueDate(addDays(issueDate, c.payment_terms_days));
    setParentInvoiceId("");
    if (invoiceType === "final") loadCustomerDepositInvoices(id);
  }

  function handleTypeChange(t: InvoiceType) {
    setInvoiceType(t);
    setParentInvoiceId("");
    if (t === "final") loadCustomerDepositInvoices(customerId);
  }

  function setItem(i: number, field: keyof LineItem, value: string) {
    setItems((prev) => prev.map((item, idx) => {
      if (idx !== i) return item;
      const updated = { ...item, [field]: value };
      if (field === "product_id") {
        const p = products.find((pr) => pr.id === value);
        if (p) { updated.description = p.name; updated.unit_price = p.sell_price; updated.tax_rate = p.tax_rate; }
      }
      return updated;
    }));
  }

  function addLine() { setItems((prev) => [...prev, { description: "", product_id: "", quantity: "1", unit_price: "", tax_rate: "25" }]); }
  function removeLine(i: number) { setItems((prev) => prev.filter((_, idx) => idx !== i)); }

  const subtotal = items.reduce((s, it) => s + (Number(it.unit_price) * Number(it.quantity) || 0), 0);
  const vat = items.reduce((s, it) => s + (Number(it.unit_price) * Number(it.quantity) * Number(it.tax_rate) / 100 || 0), 0);
  const selectedParent = customerInvoices.find((i) => i.id === parentInvoiceId);
  const depositOffset = selectedParent?.deposit_amount ? Number(selectedParent.deposit_amount) : 0;

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (invoiceType === "final" && !parentInvoiceId) {
      setError("Select the deposit invoice to offset for a Final Invoice");
      return;
    }
    setSaving(true); setError(null);
    try {
      const inv = await api.post<{ id: string }>("/api/invoicing/invoices", {
        customer_id: customerId,
        issue_date: issueDate,
        due_date: dueDate,
        notes: notes || null,
        invoice_type: invoiceType,
        parent_invoice_id: parentInvoiceId || null,
        items: items.map((it) => ({
          product_id: it.product_id || null,
          description: it.description,
          quantity: Number(it.quantity),
          unit_price: it.unit_price,
          tax_rate: it.tax_rate,
        })),
      });
      router.push(`/invoices/${inv.id}`);
    } catch (e: any) { setError(e.message); } finally { setSaving(false); }
  }

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <div>
        <Button asChild variant="ghost" size="sm" className="mb-2 -ml-2 text-muted-foreground">
          <Link href="/invoices"><ArrowLeft className="mr-1 h-3.5 w-3.5" />Invoices</Link>
        </Button>
        <h1 className="text-2xl font-bold text-[#1a2332]">New Invoice</h1>
      </div>

      <form onSubmit={handleSubmit} className="space-y-6">
        {/* Invoice type selector */}
        <div className="rounded-xl border bg-white p-6 space-y-3">
          <h2 className="font-semibold text-gray-900">Invoice type</h2>
          <div className="grid grid-cols-3 gap-3">
            {(Object.entries(TYPE_LABELS) as [InvoiceType, { label: string; desc: string }][]).map(([t, { label, desc }]) => (
              <button key={t} type="button" onClick={() => handleTypeChange(t)}
                className={`rounded-lg border p-3 text-left transition-colors ${invoiceType === t ? "border-[#1a2332] bg-[#1a2332]/5 ring-1 ring-[#1a2332]/20" : "hover:border-gray-300"}`}>
                <p className={`text-sm font-medium ${invoiceType === t ? "text-[#1a2332]" : "text-gray-700"}`}>{label}</p>
                <p className="text-xs text-gray-400 mt-0.5">{desc}</p>
              </button>
            ))}
          </div>

          {invoiceType === "final" && (
            <div className="space-y-1.5 pt-1 border-t mt-3">
              <Label>Deposit invoice to offset *</Label>
              {customerInvoices.length === 0 ? (
                <p className="text-xs text-amber-600">
                  {customerId ? "No deposit invoices found for this customer." : "Select a customer first to load their deposit invoices."}
                </p>
              ) : (
                <select required value={parentInvoiceId} onChange={(e) => setParentInvoiceId(e.target.value)}
                  className="block w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-[#1a2332] focus:outline-none focus:ring-1 focus:ring-[#1a2332]">
                  <option value="">Select deposit invoice…</option>
                  {customerInvoices.map((inv) => (
                    <option key={inv.id} value={inv.id}>
                      {inv.invoice_number} — {Number(inv.total_sek).toLocaleString("sv-SE", { minimumFractionDigits: 2 })} SEK
                    </option>
                  ))}
                </select>
              )}
              {selectedParent && (
                <p className="text-xs text-gray-500">
                  Deposit paid: <span className="font-medium text-green-600">{depositOffset.toLocaleString("sv-SE", { minimumFractionDigits: 2 })} SEK</span> — will appear as a deduction on the PDF
                </p>
              )}
            </div>
          )}
        </div>

        <div className="rounded-xl border bg-white p-6 space-y-4">
          <h2 className="font-semibold text-gray-900">Invoice details</h2>
          <div className="space-y-1.5">
            <Label>Customer *</Label>
            <select required disabled={loadingRefs} value={customerId} onChange={(e) => handleCustomerChange(e.target.value)} data-testid="customer-select"
              className="block w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-[#1a2332] focus:outline-none focus:ring-1 focus:ring-[#1a2332]">
              <option value="">{loadingRefs ? "Loading customers…" : "Select customer…"}</option>
              {customers.map((c) => <option key={c.id} value={c.id}>{c.company_name}</option>)}
            </select>
            {!loadingRefs && customers.length === 0 && (
              <p className="text-xs text-muted-foreground">
                No customers yet. <Link href="/customers" className="text-[#1a2332] underline">Add one first.</Link>
              </p>
            )}
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-1.5">
              <Label>Issue date *</Label>
              <input type="date" required value={issueDate} onChange={(e) => setIssueDate(e.target.value)}
                className="block w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-[#1a2332] focus:outline-none focus:ring-1 focus:ring-[#1a2332]" />
            </div>
            <div className="space-y-1.5">
              <Label>Due date *</Label>
              <input type="date" required value={dueDate} onChange={(e) => setDueDate(e.target.value)}
                className="block w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-[#1a2332] focus:outline-none focus:ring-1 focus:ring-[#1a2332]" />
            </div>
          </div>
          <div className="space-y-1.5">
            <Label>Notes</Label>
            <textarea rows={2} value={notes} onChange={(e) => setNotes(e.target.value)} placeholder="Payment instructions, bank details…"
              className="block w-full resize-none rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-[#1a2332] focus:outline-none focus:ring-1 focus:ring-[#1a2332]" />
          </div>
        </div>

        <div className="rounded-xl border bg-white p-6 space-y-4">
          <h2 className="font-semibold text-gray-900">Line items</h2>
          <div className="space-y-3">
            {items.map((item, i) => (
              <div key={i} className="grid grid-cols-12 gap-2 items-end">
                <div className="col-span-4 space-y-1.5">
                  {i === 0 && <Label>Product (optional)</Label>}
                  <select value={item.product_id} onChange={(e) => setItem(i, "product_id", e.target.value)}
                    className="block w-full rounded-md border border-gray-300 px-2 py-2 text-sm focus:border-[#1a2332] focus:outline-none focus:ring-1 focus:ring-[#1a2332]">
                    <option value="">Custom…</option>
                    {products.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
                  </select>
                </div>
                <div className="col-span-3 space-y-1.5">
                  {i === 0 && <Label>Description *</Label>}
                  <input required value={item.description} onChange={(e) => setItem(i, "description", e.target.value)}
                    placeholder="Service or item…"
                    className="block w-full rounded-md border border-gray-300 px-2 py-2 text-sm focus:border-[#1a2332] focus:outline-none focus:ring-1 focus:ring-[#1a2332]" />
                </div>
                <div className="col-span-1 space-y-1.5">
                  {i === 0 && <Label>Qty</Label>}
                  <input type="number" min="0.001" step="0.001" required value={item.quantity}
                    onChange={(e) => setItem(i, "quantity", e.target.value)}
                    className="block w-full rounded-md border border-gray-300 px-2 py-2 text-sm focus:border-[#1a2332] focus:outline-none focus:ring-1 focus:ring-[#1a2332]" />
                </div>
                <div className="col-span-2 space-y-1.5">
                  {i === 0 && <Label>Price (SEK)</Label>}
                  <input type="number" step="0.01" min="0" required value={item.unit_price}
                    onChange={(e) => setItem(i, "unit_price", e.target.value)}
                    className="block w-full rounded-md border border-gray-300 px-2 py-2 text-sm focus:border-[#1a2332] focus:outline-none focus:ring-1 focus:ring-[#1a2332]" />
                </div>
                <div className="col-span-1 space-y-1.5">
                  {i === 0 && <Label>VAT%</Label>}
                  <select value={item.tax_rate} onChange={(e) => setItem(i, "tax_rate", e.target.value)}
                    className="block w-full rounded-md border border-gray-300 px-1 py-2 text-sm focus:border-[#1a2332] focus:outline-none focus:ring-1 focus:ring-[#1a2332]">
                    <option value="25">25%</option>
                    <option value="12">12%</option>
                    <option value="6">6%</option>
                    <option value="0">0%</option>
                  </select>
                </div>
                <div className={`col-span-1 ${i === 0 ? "pb-0.5" : ""}`}>
                  {items.length > 1 && (
                    <Button type="button" variant="ghost" size="sm" className="h-9 w-9 p-0 text-red-400 hover:text-red-600" onClick={() => removeLine(i)}>
                      <Trash2 className="h-4 w-4" />
                    </Button>
                  )}
                </div>
              </div>
            ))}
          </div>
          <Button type="button" variant="outline" size="sm" onClick={addLine} data-testid="add-line-item">
            <Plus className="mr-1.5 h-3.5 w-3.5" />Add line
          </Button>

          <div className="flex justify-end border-t pt-3">
            <div className="text-right space-y-1 min-w-[220px]">
              <div className="flex justify-between gap-8 text-sm text-muted-foreground">
                <span>Subtotal</span>
                <span className="font-mono">{subtotal.toLocaleString("sv-SE", { minimumFractionDigits: 2 })} SEK</span>
              </div>
              <div className="flex justify-between gap-8 text-sm text-muted-foreground">
                <span>VAT</span>
                <span className="font-mono">{vat.toLocaleString("sv-SE", { minimumFractionDigits: 2 })} SEK</span>
              </div>
              {invoiceType === "final" && depositOffset > 0 && (
                <div className="flex justify-between gap-8 text-sm text-green-600">
                  <span>Less deposit paid</span>
                  <span className="font-mono">-{depositOffset.toLocaleString("sv-SE", { minimumFractionDigits: 2 })} SEK</span>
                </div>
              )}
              <div className="flex justify-between gap-8 text-base font-bold text-[#1a2332]">
                <span>{invoiceType === "final" && depositOffset > 0 ? "Total due" : "Total"}</span>
                <span className="font-mono">
                  {(invoiceType === "final" && depositOffset > 0
                    ? Math.max(0, subtotal + vat - depositOffset)
                    : subtotal + vat
                  ).toLocaleString("sv-SE", { minimumFractionDigits: 2 })} SEK
                </span>
              </div>
            </div>
          </div>
        </div>

        {error && <p className="rounded-md bg-red-50 px-3 py-2 text-sm text-red-600">{error}</p>}

        <div className="flex justify-end gap-3">
          <Button type="button" variant="outline" onClick={() => router.back()} data-testid="cancel-invoice">Cancel</Button>
          <Button type="submit" disabled={saving} className="bg-[#1a2332] hover:bg-[#2a3342] text-white" data-testid="save-draft">
            {saving ? "Creating…" : "Create invoice"}
          </Button>
        </div>
      </form>
    </div>
  );
}
