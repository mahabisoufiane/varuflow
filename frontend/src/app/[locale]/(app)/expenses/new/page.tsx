"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useLocale } from "next-intl";
import { toast } from "sonner";
import { api } from "@/lib/api-client";
import { ArrowLeft, Upload, Receipt, Loader2 } from "lucide-react";

interface Category {
  id: string;
  name: string;
  color: string;
}

export default function NewExpensePage() {
  const router = useRouter();
  const locale = useLocale();

  const [categories, setCategories] = useState<Category[]>([]);
  const [submitting, setSubmitting] = useState(false);

  const [form, setForm] = useState({
    amount: "",
    currency: "SEK",
    category_id: "",
    description: "",
    expense_date: new Date().toISOString().slice(0, 10),
    supplier_id: "",
  });
  const [receipt, setReceipt] = useState<File | null>(null);

  useEffect(() => {
    api.get<Category[]>("/api/expenses/categories")
      .then(setCategories)
      .catch(() => {});
  }, []);

  function update(field: string, value: string) {
    setForm((f) => ({ ...f, [field]: value }));
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!form.amount || parseFloat(form.amount) <= 0) {
      toast.error("Enter a valid amount");
      return;
    }

    setSubmitting(true);
    try {
      const expense = await api.post<{ id: string }>("/api/expenses", {
        amount: parseFloat(form.amount),
        currency: form.currency,
        category_id: form.category_id || null,
        description: form.description || null,
        expense_date: form.expense_date,
        supplier_id: form.supplier_id || null,
      });

      if (receipt && expense.id) {
        await api.upload(`/api/expenses/${expense.id}/receipt`, receipt, "file").catch(() => {
          toast.error("Expense saved but receipt upload failed");
        });
      }

      toast.success("Expense submitted");
      router.push(`/${locale}/expenses`);
    } catch {
      toast.error("Failed to submit expense");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="mx-auto max-w-2xl space-y-6 p-6">
      <div className="flex items-center gap-3">
        <button
          onClick={() => router.back()}
          className="h-8 w-8 rounded-lg border border-gray-200 flex items-center justify-center hover:bg-gray-50"
        >
          <ArrowLeft className="h-4 w-4" />
        </button>
        <div>
          <h1 className="text-xl font-semibold text-gray-900">New Expense</h1>
          <p className="text-sm text-gray-500">Submit a business expense for approval</p>
        </div>
      </div>

      <form onSubmit={handleSubmit} className="rounded-xl border bg-white shadow-sm p-6 space-y-5">
        {/* Amount + Currency */}
        <div className="grid grid-cols-3 gap-3">
          <div className="col-span-2 space-y-1.5">
            <label className="text-sm font-medium text-gray-700">Amount *</label>
            <input
              type="number"
              step="0.01"
              min="0"
              value={form.amount}
              onChange={(e) => update("amount", e.target.value)}
              placeholder="0.00"
              className="w-full rounded-lg border border-gray-300 px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-[#1a2332]/20 focus:border-[#1a2332]"
              required
            />
          </div>
          <div className="space-y-1.5">
            <label className="text-sm font-medium text-gray-700">Currency</label>
            <select
              value={form.currency}
              onChange={(e) => update("currency", e.target.value)}
              className="w-full rounded-lg border border-gray-300 px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-[#1a2332]/20 focus:border-[#1a2332]"
            >
              <option value="SEK">SEK</option>
              <option value="NOK">NOK</option>
              <option value="DKK">DKK</option>
              <option value="EUR">EUR</option>
            </select>
          </div>
        </div>

        {/* Category */}
        <div className="space-y-1.5">
          <label className="text-sm font-medium text-gray-700">Category</label>
          <select
            value={form.category_id}
            onChange={(e) => update("category_id", e.target.value)}
            className="w-full rounded-lg border border-gray-300 px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-[#1a2332]/20 focus:border-[#1a2332]"
          >
            <option value="">Select category…</option>
            {categories.map((c) => (
              <option key={c.id} value={c.id}>{c.name}</option>
            ))}
          </select>
        </div>

        {/* Date */}
        <div className="space-y-1.5">
          <label className="text-sm font-medium text-gray-700">Expense Date *</label>
          <input
            type="date"
            value={form.expense_date}
            onChange={(e) => update("expense_date", e.target.value)}
            className="w-full rounded-lg border border-gray-300 px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-[#1a2332]/20 focus:border-[#1a2332]"
            required
          />
        </div>

        {/* Description */}
        <div className="space-y-1.5">
          <label className="text-sm font-medium text-gray-700">Description</label>
          <textarea
            value={form.description}
            onChange={(e) => update("description", e.target.value)}
            rows={3}
            placeholder="What was this expense for?"
            className="w-full rounded-lg border border-gray-300 px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-[#1a2332]/20 focus:border-[#1a2332] resize-none"
          />
        </div>

        {/* Receipt upload */}
        <div className="space-y-1.5">
          <label className="text-sm font-medium text-gray-700">Receipt</label>
          <div className="border-2 border-dashed border-gray-200 rounded-lg p-4 text-center hover:border-gray-300 transition-colors">
            {receipt ? (
              <div className="flex items-center justify-center gap-2">
                <Receipt className="h-4 w-4 text-green-600" />
                <span className="text-sm text-gray-700">{receipt.name}</span>
                <button type="button" onClick={() => setReceipt(null)} className="text-xs text-red-500 hover:underline">
                  Remove
                </button>
              </div>
            ) : (
              <label className="cursor-pointer">
                <Upload className="h-6 w-6 text-gray-400 mx-auto mb-1" />
                <p className="text-sm text-gray-500">Click to upload receipt</p>
                <p className="text-xs text-gray-400 mt-0.5">PDF, JPG, or PNG up to 10 MB</p>
                <input
                  type="file"
                  accept="image/*,.pdf"
                  onChange={(e) => setReceipt(e.target.files?.[0] ?? null)}
                  className="hidden"
                />
              </label>
            )}
          </div>
        </div>

        {/* Actions */}
        <div className="flex gap-3 pt-2">
          <button
            type="button"
            onClick={() => router.back()}
            className="px-4 py-2.5 rounded-lg border border-gray-300 text-sm font-medium text-gray-700 hover:bg-gray-50"
          >
            Cancel
          </button>
          <button
            type="submit"
            disabled={submitting}
            className="flex-1 flex items-center justify-center gap-2 px-4 py-2.5 rounded-lg bg-[#1a2332] text-white text-sm font-medium hover:bg-[#2a3342] disabled:opacity-50 transition-colors"
          >
            {submitting ? <Loader2 className="h-4 w-4 animate-spin" /> : <Receipt className="h-4 w-4" />}
            {submitting ? "Submitting…" : "Submit Expense"}
          </button>
        </div>
      </form>
    </div>
  );
}
