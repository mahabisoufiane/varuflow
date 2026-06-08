"use client";

import { useEffect, useState } from "react";
import { useRouter, useParams } from "next/navigation";
import { useLocale } from "next-intl";
import { toast } from "sonner";
import { api } from "@/lib/api-client";
import {
  ArrowLeft,
  Loader2,
  CheckCircle,
  XCircle,
  RefreshCw,
  Trash2,
  FileText,
} from "lucide-react";
import { isPlanGateError, PlanGateBlock } from "@/components/ui/PlanGate";

interface Category {
  id: string;
  name: string;
  color: string;
}

interface Expense {
  id: string;
  amount: string;
  currency: string;
  description: string | null;
  expense_date: string;
  category_id: string | null;
  supplier_id: string | null;
  receipt_url: string | null;
  receipt_mime: string | null;
  receipt_size: number | null;
  status: string;
  review_note: string | null;
  created_at: string;
}

const STATUS_COLORS: Record<string, string> = {
  DRAFT: "bg-yellow-100 text-yellow-800",
  APPROVED: "bg-green-100 text-green-800",
  REJECTED: "bg-red-100 text-red-800",
};

export default function ExpenseDetailPage() {
  const router = useRouter();
  const locale = useLocale();
  const params = useParams();
  const expenseId = params.id as string;

  const [expense, setExpense] = useState<Expense | null>(null);
  const [categories, setCategories] = useState<Category[]>([]);
  const [loading, setLoading] = useState(true);
  const [editing, setEditing] = useState(false);
  const [saving, setSaving] = useState(false);
  const [rejectNote, setRejectNote] = useState("");
  const [showRejectDialog, setShowRejectDialog] = useState(false);

  const [planBlocked, setPlanBlocked] = useState<{ module: string; currentPlan: string } | null>(null);

  const [form, setForm] = useState({
    amount: "",
    currency: "SEK",
    category_id: "",
    description: "",
    expense_date: "",
  });

  useEffect(() => {
    Promise.all([
      api.get<Expense>(`/api/expenses/${expenseId}`),
      api.get<Category[]>("/api/expenses/categories"),
    ])
      .then(([exp, cats]) => {
        setExpense(exp);
        setCategories(cats);
        setForm({
          amount: exp.amount,
          currency: exp.currency,
          category_id: exp.category_id ?? "",
          description: exp.description ?? "",
          expense_date: exp.expense_date,
        });
      })
      .catch((err) => {
        if (isPlanGateError(err)) {
          setPlanBlocked({ module: (err as any).module ?? "finance", currentPlan: (err as any).currentPlan ?? "FREE" });
          return;
        }
        toast.error("Failed to load expense");
      })
      .finally(() => setLoading(false));
  }, [expenseId]);

  function update(field: string, value: string) {
    setForm((f) => ({ ...f, [field]: value }));
  }

  async function handleSave(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    try {
      const updated = await api.patch<Expense>(`/api/expenses/${expenseId}`, {
        amount: parseFloat(form.amount),
        currency: form.currency,
        category_id: form.category_id || null,
        description: form.description || null,
        expense_date: form.expense_date,
      });
      setExpense(updated);
      setEditing(false);
      toast.success("Expense updated");
    } catch {
      toast.error("Failed to update expense");
    } finally {
      setSaving(false);
    }
  }

  async function handleApprove() {
    try {
      const updated = await api.post<Expense>(`/api/expenses/${expenseId}/approve`, {});
      setExpense(updated);
      toast.success("Expense approved");
    } catch {
      toast.error("Failed to approve expense");
    }
  }

  async function handleReject() {
    if (!rejectNote.trim()) {
      toast.error("Rejection note is required");
      return;
    }
    try {
      const updated = await api.post<Expense>(`/api/expenses/${expenseId}/reject`, {
        note: rejectNote,
      });
      setExpense(updated);
      setShowRejectDialog(false);
      setRejectNote("");
      toast.success("Expense rejected");
    } catch {
      toast.error("Failed to reject expense");
    }
  }

  async function handleResubmit() {
    try {
      const updated = await api.post<Expense>(`/api/expenses/${expenseId}/resubmit`, {});
      setExpense(updated);
      toast.success("Expense resubmitted for review");
    } catch {
      toast.error("Failed to resubmit expense");
    }
  }

  async function handleDelete() {
    if (!confirm("Delete this expense? This cannot be undone.")) return;
    try {
      await api.delete(`/api/expenses/${expenseId}`);
      toast.success("Expense deleted");
      router.push(`/${locale}/expenses`);
    } catch {
      toast.error("Failed to delete expense");
    }
  }

  const categoryName = categories.find((c) => c.id === expense?.category_id)?.name;

  if (loading) {
    return (
      <div className="flex items-center justify-center p-12">
        <Loader2 className="h-6 w-6 animate-spin text-gray-400" />
      </div>
    );
  }

  if (!expense) {
    return (
      <div className="p-6 text-center text-gray-500">
        Expense not found.{" "}
        <button onClick={() => router.back()} className="text-blue-600 hover:underline">
          Go back
        </button>
      </div>
    );
  }

  const canEdit = expense.status === "DRAFT" || expense.status === "REJECTED";
  const canApprove = expense.status === "DRAFT";
  const canResubmit = expense.status === "REJECTED";
  const isImage = expense.receipt_mime?.startsWith("image/");

  if (planBlocked) return <PlanGateBlock module={planBlocked.module} currentPlan={planBlocked.currentPlan} featureName="Expenses" />;

  return (
    <div className="mx-auto max-w-2xl space-y-6 p-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <button
            onClick={() => router.back()}
            className="h-8 w-8 rounded-lg border border-gray-200 flex items-center justify-center hover:bg-gray-50"
          >
            <ArrowLeft className="h-4 w-4" />
          </button>
          <div>
            <h1 className="text-xl font-semibold text-gray-900">
              {expense.description || `Expense — ${expense.expense_date}`}
            </h1>
            <p className="text-sm text-gray-500">
              {new Date(expense.created_at).toLocaleDateString("sv-SE")}
              {categoryName ? ` · ${categoryName}` : ""}
            </p>
          </div>
        </div>
        <span
          className={`px-3 py-1 rounded-full text-xs font-semibold uppercase tracking-wide ${STATUS_COLORS[expense.status] ?? "bg-gray-100 text-gray-700"}`}
        >
          {expense.status}
        </span>
      </div>

      {/* Review note (rejection reason) */}
      {expense.review_note && (
        <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
          <strong>Rejection note:</strong> {expense.review_note}
        </div>
      )}

      {/* Detail / Edit form */}
      <form onSubmit={handleSave} className="rounded-xl border bg-white shadow-sm p-6 space-y-5">
        <div className="flex items-center justify-between">
          <h2 className="text-sm font-semibold text-gray-700 uppercase tracking-wide">Details</h2>
          {canEdit && !editing && (
            <button
              type="button"
              onClick={() => setEditing(true)}
              className="text-sm text-blue-600 hover:underline"
            >
              Edit
            </button>
          )}
        </div>

        <div className="grid grid-cols-3 gap-3">
          <div className="col-span-2 space-y-1.5">
            <label className="text-sm font-medium text-gray-700">Amount</label>
            {editing ? (
              <input
                type="number"
                step="0.01"
                min="0"
                value={form.amount}
                onChange={(e) => update("amount", e.target.value)}
                className="w-full rounded-lg border border-gray-300 px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-[#1a2332]/20 focus:border-[#1a2332]"
                required
              />
            ) : (
              <p className="py-2.5 text-sm font-semibold text-gray-900">
                {Number(expense.amount).toFixed(2)} {expense.currency}
              </p>
            )}
          </div>
          <div className="space-y-1.5">
            <label className="text-sm font-medium text-gray-700">Currency</label>
            {editing ? (
              <select
                value={form.currency}
                onChange={(e) => update("currency", e.target.value)}
                className="w-full rounded-lg border border-gray-300 px-3 py-2.5 text-sm"
              >
                {["SEK", "NOK", "DKK", "EUR"].map((c) => (
                  <option key={c}>{c}</option>
                ))}
              </select>
            ) : null}
          </div>
        </div>

        <div className="space-y-1.5">
          <label className="text-sm font-medium text-gray-700">Category</label>
          {editing ? (
            <select
              value={form.category_id}
              onChange={(e) => update("category_id", e.target.value)}
              className="w-full rounded-lg border border-gray-300 px-3 py-2.5 text-sm"
            >
              <option value="">No category</option>
              {categories.map((c) => (
                <option key={c.id} value={c.id}>{c.name}</option>
              ))}
            </select>
          ) : (
            <p className="py-2.5 text-sm text-gray-700">{categoryName ?? "—"}</p>
          )}
        </div>

        <div className="space-y-1.5">
          <label className="text-sm font-medium text-gray-700">Date</label>
          {editing ? (
            <input
              type="date"
              value={form.expense_date}
              onChange={(e) => update("expense_date", e.target.value)}
              className="w-full rounded-lg border border-gray-300 px-3 py-2.5 text-sm"
              required
            />
          ) : (
            <p className="py-2.5 text-sm text-gray-700">{expense.expense_date}</p>
          )}
        </div>

        <div className="space-y-1.5">
          <label className="text-sm font-medium text-gray-700">Description</label>
          {editing ? (
            <textarea
              value={form.description}
              onChange={(e) => update("description", e.target.value)}
              rows={3}
              placeholder="What was this expense for?"
              className="w-full rounded-lg border border-gray-300 px-3 py-2.5 text-sm resize-none"
            />
          ) : (
            <p className="py-2.5 text-sm text-gray-700">{expense.description || "—"}</p>
          )}
        </div>

        {editing && (
          <div className="flex gap-3 pt-2">
            <button
              type="button"
              onClick={() => setEditing(false)}
              className="px-4 py-2.5 rounded-lg border border-gray-300 text-sm font-medium text-gray-700 hover:bg-gray-50"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={saving}
              className="flex-1 flex items-center justify-center gap-2 px-4 py-2.5 rounded-lg bg-[#1a2332] text-white text-sm font-medium hover:bg-[#2a3342] disabled:opacity-50"
            >
              {saving ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
              {saving ? "Saving…" : "Save Changes"}
            </button>
          </div>
        )}
      </form>

      {/* Receipt */}
      {expense.receipt_url && (
        <div className="rounded-xl border bg-white shadow-sm p-6 space-y-3">
          <h2 className="text-sm font-semibold text-gray-700 uppercase tracking-wide">Receipt</h2>
          {isImage ? (
            <img
              src={expense.receipt_url}
              alt="Receipt"
              className="max-h-64 rounded-lg object-contain border border-gray-100"
            />
          ) : (
            <a
              href={expense.receipt_url}
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center gap-2 text-sm text-blue-600 hover:underline"
            >
              <FileText className="h-4 w-4" />
              View receipt PDF
            </a>
          )}
          {expense.receipt_size && (
            <p className="text-xs text-gray-400">
              {(expense.receipt_size / 1024).toFixed(0)} KB
            </p>
          )}
        </div>
      )}

      {/* Actions */}
      <div className="flex flex-wrap gap-3">
        {canApprove && (
          <>
            <button
              onClick={handleApprove}
              className="flex items-center gap-2 px-4 py-2.5 rounded-lg bg-green-600 text-white text-sm font-medium hover:bg-green-700"
            >
              <CheckCircle className="h-4 w-4" />
              Approve
            </button>
            <button
              onClick={() => setShowRejectDialog(true)}
              className="flex items-center gap-2 px-4 py-2.5 rounded-lg border border-red-300 text-red-600 text-sm font-medium hover:bg-red-50"
            >
              <XCircle className="h-4 w-4" />
              Reject
            </button>
          </>
        )}
        {canResubmit && (
          <button
            onClick={handleResubmit}
            className="flex items-center gap-2 px-4 py-2.5 rounded-lg border border-blue-300 text-blue-600 text-sm font-medium hover:bg-blue-50"
          >
            <RefreshCw className="h-4 w-4" />
            Resubmit
          </button>
        )}
        <button
          onClick={handleDelete}
          className="flex items-center gap-2 px-4 py-2.5 rounded-lg border border-gray-300 text-gray-600 text-sm font-medium hover:bg-gray-50 ml-auto"
        >
          <Trash2 className="h-4 w-4" />
          Delete
        </button>
      </div>

      {/* Reject dialog */}
      {showRejectDialog && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
          <div className="w-full max-w-md rounded-xl bg-white p-6 shadow-2xl space-y-4">
            <h3 className="text-lg font-semibold text-gray-900">Reject Expense</h3>
            <p className="text-sm text-gray-500">
              Provide a reason so the submitter knows what to fix.
            </p>
            <textarea
              value={rejectNote}
              onChange={(e) => setRejectNote(e.target.value)}
              rows={3}
              placeholder="Reason for rejection…"
              className="w-full rounded-lg border border-gray-300 px-3 py-2.5 text-sm resize-none focus:outline-none focus:ring-2 focus:ring-red-300"
              autoFocus
            />
            <div className="flex gap-3">
              <button
                onClick={() => setShowRejectDialog(false)}
                className="px-4 py-2.5 rounded-lg border border-gray-300 text-sm font-medium text-gray-700 hover:bg-gray-50"
              >
                Cancel
              </button>
              <button
                onClick={handleReject}
                className="flex-1 px-4 py-2.5 rounded-lg bg-red-600 text-white text-sm font-medium hover:bg-red-700"
              >
                Confirm Rejection
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
