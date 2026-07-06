"use client";

import { useEffect, useState } from "react";
// next-intl navigation (not next/navigation + next/link): keeps the locale prefix
// so /quotes/{id} resolves to the app route, not the public /quotes/[token] page.
import { Link, useRouter } from "@/i18n/navigation";
import { api } from "@/lib/api-client";
import { toast } from "sonner";
import { Plus, Trash2, ArrowLeft } from "lucide-react";

interface Customer { id: string; company_name: string; }
interface LineItem { description: string; quantity: string; unit_price: string; }

const inputCls =
  "block w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-[var(--vf-brand-primary)] focus:outline-none focus:ring-1 focus:ring-[var(--vf-brand-primary)]";

const labelCls = "block text-xs font-medium text-gray-600 mb-1";

export default function NewQuotePage() {
  const router = useRouter();
  const [customers, setCustomers] = useState<Customer[]>([]);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);

  const [form, setForm] = useState({
    customer_id: "",
    title: "",
    quote_number: "",
    cover_text: "",
    scope: "",
    terms: "",
    valid_until: "",
    currency: "SEK",
  });

  const [items, setItems] = useState<LineItem[]>([
    { description: "", quantity: "1", unit_price: "" },
  ]);

  useEffect(() => {
    api.get<Customer[]>("/api/invoicing/customers?is_active=true&limit=500")
      .then(setCustomers)
      .catch(() => toast.error("Failed to load customers"))
      .finally(() => setLoading(false));
  }, []);

  function addItem() {
    setItems((prev) => [...prev, { description: "", quantity: "1", unit_price: "" }]);
  }

  function removeItem(i: number) {
    setItems((prev) => prev.filter((_, idx) => idx !== i));
  }

  function updateItem(i: number, field: keyof LineItem, val: string) {
    setItems((prev) => prev.map((item, idx) => idx === i ? { ...item, [field]: val } : item));
  }

  function lineTotal(item: LineItem) {
    return (parseFloat(item.quantity) || 0) * (parseFloat(item.unit_price) || 0);
  }

  const grandTotal = items.reduce((sum, i) => sum + lineTotal(i), 0);

  async function submit() {
    if (!form.customer_id) { toast.error("Select a customer"); return; }
    if (!form.title.trim()) { toast.error("Enter a title"); return; }
    const validItems = items.filter((i) => i.description.trim());
    if (validItems.length === 0) { toast.error("Add at least one line item"); return; }

    setSubmitting(true);
    try {
      const data = await api.post<{ id: string }>("/api/quotes", {
        ...form,
        valid_until: form.valid_until || null,
        quote_number: form.quote_number || null,
        items: validItems.map((i) => ({
          description: i.description,
          quantity: parseFloat(i.quantity) || 1,
          unit_price: parseFloat(i.unit_price) || 0,
        })),
      });
      toast.success("Quote created");
      router.push(`/quotes/${data.id}`);
    } catch {
      // api client shows toast
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="max-w-3xl space-y-6 pb-12">
      <div className="flex items-center gap-3">
        <Link href="/quotes" className="text-gray-400 hover:text-gray-700 transition-colors">
          <ArrowLeft className="h-4 w-4" />
        </Link>
        <h1 className="text-xl font-bold text-[var(--vf-text-primary)]">New Quote</h1>
      </div>

      {/* Header */}
      <div className="rounded-xl border bg-white p-5 space-y-4">
        <h2 className="text-sm font-semibold text-gray-700">Quote details</h2>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <div>
            <label className={labelCls}>Customer *</label>
            <select
              required
              disabled={loading}
              value={form.customer_id}
              onChange={(e) => setForm({ ...form, customer_id: e.target.value })}
              className={inputCls}
            >
              <option value="">{loading ? "Loading…" : "Select customer…"}</option>
              {customers.map((c) => (
                <option key={c.id} value={c.id}>{c.company_name}</option>
              ))}
            </select>
          </div>
          <div>
            <label className={labelCls}>Title *</label>
            <input
              placeholder="e.g. Web design project"
              value={form.title}
              onChange={(e) => setForm({ ...form, title: e.target.value })}
              className={inputCls}
            />
          </div>
          <div>
            <label className={labelCls}>Quote number (optional)</label>
            <input
              placeholder="Auto-generated if blank"
              value={form.quote_number}
              onChange={(e) => setForm({ ...form, quote_number: e.target.value })}
              className={inputCls}
            />
          </div>
          <div>
            <label className={labelCls}>Valid until</label>
            <input
              type="date"
              value={form.valid_until}
              onChange={(e) => setForm({ ...form, valid_until: e.target.value })}
              className={inputCls}
            />
          </div>
          <div>
            <label className={labelCls}>Currency</label>
            <select
              value={form.currency}
              onChange={(e) => setForm({ ...form, currency: e.target.value })}
              className={inputCls}
            >
              <option value="SEK">SEK</option>
              <option value="NOK">NOK</option>
              <option value="DKK">DKK</option>
              <option value="EUR">EUR</option>
              <option value="USD">USD</option>
            </select>
          </div>
        </div>
        <div>
          <label className={labelCls}>Cover text</label>
          <textarea
            placeholder="Introduction for the client…"
            value={form.cover_text}
            onChange={(e) => setForm({ ...form, cover_text: e.target.value })}
            rows={3}
            className={inputCls}
          />
        </div>
        <div>
          <label className={labelCls}>Scope of work</label>
          <textarea
            placeholder="What is included…"
            value={form.scope}
            onChange={(e) => setForm({ ...form, scope: e.target.value })}
            rows={3}
            className={inputCls}
          />
        </div>
        <div>
          <label className={labelCls}>Terms & conditions</label>
          <textarea
            placeholder="Payment terms, deadlines, exclusions…"
            value={form.terms}
            onChange={(e) => setForm({ ...form, terms: e.target.value })}
            rows={3}
            className={inputCls}
          />
        </div>
      </div>

      {/* Line items */}
      <div className="rounded-xl border bg-white p-5 space-y-3">
        <h2 className="text-sm font-semibold text-gray-700">Line items</h2>

        <div className="hidden sm:grid grid-cols-[1fr_80px_110px_32px] gap-2 text-xs font-medium text-gray-500 px-1">
          <span>Description</span>
          <span>Qty</span>
          <span>Unit price ({form.currency})</span>
          <span />
        </div>

        {items.map((item, i) => (
          <div key={i} className="grid grid-cols-[1fr_80px_110px_32px] gap-2 items-center">
            <input
              placeholder="Description"
              value={item.description}
              onChange={(e) => updateItem(i, "description", e.target.value)}
              className={inputCls}
            />
            <input
              type="number"
              min="0"
              placeholder="1"
              value={item.quantity}
              onChange={(e) => updateItem(i, "quantity", e.target.value)}
              className={inputCls}
            />
            <input
              type="number"
              min="0"
              step="0.01"
              placeholder="0.00"
              value={item.unit_price}
              onChange={(e) => updateItem(i, "unit_price", e.target.value)}
              className={inputCls}
            />
            <button
              onClick={() => removeItem(i)}
              disabled={items.length === 1}
              className="flex items-center justify-center h-9 w-8 rounded-md text-gray-400 hover:text-red-500 disabled:opacity-30 transition-colors"
            >
              <Trash2 className="h-4 w-4" />
            </button>
          </div>
        ))}

        <button
          onClick={addItem}
          className="flex items-center gap-1.5 text-sm text-[var(--vf-text-primary)] hover:text-[var(--vf-brand-primary)] font-medium"
        >
          <Plus className="h-4 w-4" />
          Add line
        </button>

        <div className="border-t pt-3 text-right">
          <p className="text-xs text-gray-500">Total (ex. VAT)</p>
          <p className="text-lg font-bold text-[var(--vf-text-primary)]">
            {grandTotal.toLocaleString("sv-SE", { minimumFractionDigits: 2 })} {form.currency}
          </p>
        </div>
      </div>

      {/* Actions */}
      <div className="flex gap-3">
        <button
          onClick={submit}
          disabled={submitting}
          className="rounded-md bg-[var(--vf-brand-primary)] px-6 py-2.5 text-sm font-semibold text-white disabled:opacity-60 hover:bg-[#243249] transition-colors"
        >
          {submitting ? "Creating…" : "Create Quote"}
        </button>
        <Link
          href="/quotes"
          className="rounded-md border px-6 py-2.5 text-sm font-medium text-gray-700 hover:bg-gray-50"
        >
          Cancel
        </Link>
      </div>
    </div>
  );
}
