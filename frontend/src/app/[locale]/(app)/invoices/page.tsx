"use client";

import { api } from "@/lib/api-client";
import Link from "next/link";
import { useEffect, useState } from "react";
import { toast } from "sonner";
import {
  AlertTriangle, ArrowRight, CheckCircle2, Clock,
  FileText, Plus, Send, TrendingUp,
} from "lucide-react";

interface Invoice {
  id: string;
  invoice_number: string;
  customer: { id: string; company_name: string };
  issue_date: string;
  due_date: string;
  status: "DRAFT" | "SENT" | "PAID" | "OVERDUE";
  total_sek: string;
}

const NEXT_STATUS: Record<string, string | null> = {
  DRAFT: "SENT", SENT: "PAID", OVERDUE: "PAID", PAID: null,
};

function fmt(n: number) {
  return n.toLocaleString("sv-SE", { minimumFractionDigits: 0, maximumFractionDigits: 0 });
}

function StatusBadge({ status }: { status: string }) {
  const cfg: Record<string, { label: string; cls: string; dot: string }> = {
    DRAFT:   { label: "Draft",   cls: "bg-gray-100 text-gray-500 border-gray-200",            dot: "bg-gray-400" },
    SENT:    { label: "Sent",    cls: "bg-blue-50 text-blue-600 border-blue-200",              dot: "bg-blue-500" },
    PAID:    { label: "Paid",    cls: "bg-emerald-50 text-emerald-700 border-emerald-200",     dot: "bg-emerald-500" },
    OVERDUE: { label: "Overdue", cls: "bg-red-50 text-red-600 border-red-200",                 dot: "bg-red-500" },
  };
  const s = cfg[status] ?? cfg.DRAFT;
  return (
    <span className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-[11px] font-semibold ${s.cls}`}>
      <span className={`h-1.5 w-1.5 rounded-full ${s.dot}`} />
      {s.label}
    </span>
  );
}

function KpiTile({ label, value, sub, accent, icon }: {
  label: string; value: string; sub?: string; accent?: string; icon: React.ReactNode;
}) {
  return (
    <div className={`rounded-2xl border bg-white p-5 shadow-sm ${accent ?? "border-gray-200"}`}>
      <div className="flex items-center justify-between mb-3">
        <p className="text-[11px] font-semibold uppercase tracking-widest text-gray-400">{label}</p>
        <span className="text-gray-300">{icon}</span>
      </div>
      <p className="text-3xl font-bold tracking-tight text-gray-900 tabular-nums">{value}</p>
      {sub && <p className="mt-1 text-xs text-gray-400">{sub}</p>}
    </div>
  );
}

type Filter = "ALL" | "DRAFT" | "SENT" | "OVERDUE" | "PAID";

export default function InvoicesPage() {
  const [invoices, setInvoices] = useState<Invoice[]>([]);
  const [filter, setFilter] = useState<Filter>("ALL");
  const [updating, setUpdating] = useState<string | null>(null);
  const [markingOverdue, setMarkingOverdue] = useState(false);

  async function load() {
    try { setInvoices(await api.get<Invoice[]>("/api/invoicing/invoices")); }
    catch (e: unknown) { toast.error((e as Error).message); }
  }

  useEffect(() => { load(); }, []);

  async function advanceStatus(inv: Invoice) {
    const next = NEXT_STATUS[inv.status];
    if (!next) return;
    setUpdating(inv.id);
    try {
      await api.patch(`/api/invoicing/invoices/${inv.id}/status`, { status: next });
      toast.success(`${inv.invoice_number} → ${next.toLowerCase()}`);
      await load();
    } catch (e: unknown) { toast.error((e as Error).message); }
    finally { setUpdating(null); }
  }

  async function handleMarkOverdue() {
    setMarkingOverdue(true);
    try {
      const res = await api.post<{ marked: number }>("/api/recurring/mark-overdue", {});
      toast.success(res.marked > 0 ? `${res.marked} marked overdue` : "Nothing to update");
      if (res.marked > 0) await load();
    } catch (e: unknown) { toast.error((e as Error).message); }
    finally { setMarkingOverdue(false); }
  }

  // Derived
  const outstanding = invoices.filter(i => i.status === "SENT" || i.status === "OVERDUE")
    .reduce((s, i) => s + Number(i.total_sek), 0);
  const overdueAmt  = invoices.filter(i => i.status === "OVERDUE")
    .reduce((s, i) => s + Number(i.total_sek), 0);
  const paidCount   = invoices.filter(i => i.status === "PAID").length;
  const overdueCount = invoices.filter(i => i.status === "OVERDUE").length;

  const FILTERS: { key: Filter; label: string; count: number }[] = [
    { key: "ALL",     label: "All",     count: invoices.length },
    { key: "SENT",    label: "Sent",    count: invoices.filter(i => i.status === "SENT").length },
    { key: "OVERDUE", label: "Overdue", count: overdueCount },
    { key: "DRAFT",   label: "Draft",   count: invoices.filter(i => i.status === "DRAFT").length },
    { key: "PAID",    label: "Paid",    count: paidCount },
  ];

  const visible = filter === "ALL" ? invoices : invoices.filter(i => i.status === filter);

  return (
    <div className="space-y-6">

      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-[22px] font-bold tracking-tight text-gray-900">Invoices</h1>
          <p className="text-xs text-gray-400 mt-0.5">{invoices.length} total invoices</p>
        </div>
        <div className="flex gap-2">
          <button
            onClick={handleMarkOverdue}
            disabled={markingOverdue}
            className="inline-flex items-center gap-1.5 rounded-lg border border-gray-200 bg-white px-3 py-1.5 text-sm font-medium text-gray-600 shadow-sm hover:bg-gray-50 transition-colors disabled:opacity-50"
          >
            <AlertTriangle className="h-3.5 w-3.5 text-amber-500" />
            {markingOverdue ? "Checking…" : "Flag overdue"}
          </button>
          <Link
            href="/invoices/new"
            className="inline-flex items-center gap-1.5 rounded-lg bg-[#0d1117] px-3 py-1.5 text-sm font-medium text-white shadow-sm hover:bg-[#161b22] transition-colors"
          >
            <Plus className="h-3.5 w-3.5" />New invoice
          </Link>
        </div>
      </div>

      {/* KPI tiles */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <KpiTile
          label="Outstanding"
          value={`${fmt(outstanding)} kr`}
          sub={`${invoices.filter(i => i.status === "SENT" || i.status === "OVERDUE").length} invoices`}
          icon={<TrendingUp className="h-5 w-5" />}
          accent="border-gray-200"
        />
        <KpiTile
          label="Overdue"
          value={`${fmt(overdueAmt)} kr`}
          sub={overdueCount > 0 ? `${overdueCount} need action` : "All current"}
          icon={<AlertTriangle className="h-5 w-5" />}
          accent={overdueAmt > 0 ? "border-red-200 bg-red-50/30" : "border-gray-200"}
        />
        <KpiTile
          label="Paid this month"
          value={String(paidCount)}
          sub="invoices collected"
          icon={<CheckCircle2 className="h-5 w-5" />}
          accent="border-gray-200"
        />
        <KpiTile
          label="Draft"
          value={String(invoices.filter(i => i.status === "DRAFT").length)}
          sub="not yet sent"
          icon={<Clock className="h-5 w-5" />}
          accent="border-gray-200"
        />
      </div>

      {/* Filter tabs */}
      <div className="flex items-center gap-1 border-b border-gray-200">
        {FILTERS.map(({ key, label, count }) => (
          <button
            key={key}
            onClick={() => setFilter(key)}
            className={`flex items-center gap-1.5 px-3 py-2 text-sm font-medium transition-colors border-b-2 -mb-px ${
              filter === key
                ? "border-gray-900 text-gray-900"
                : "border-transparent text-gray-400 hover:text-gray-700"
            }`}
          >
            {label}
            <span className={`rounded-full px-1.5 py-0.5 text-[10px] font-bold ${
              filter === key ? "bg-gray-900 text-white" : "bg-gray-100 text-gray-500"
            }`}>{count}</span>
          </button>
        ))}
      </div>

      {/* Invoice list */}
      {visible.length === 0 ? (
        <div className="rounded-2xl border border-dashed border-gray-200 bg-white px-6 py-20 text-center">
          <FileText className="mx-auto h-10 w-10 text-gray-200" />
          <p className="mt-3 text-sm font-semibold text-gray-500">No invoices</p>
          <p className="text-xs text-gray-400 mt-1">
            {filter === "ALL" ? "Create your first invoice to get started." : `No ${filter.toLowerCase()} invoices.`}
          </p>
          {filter === "ALL" && (
            <Link
              href="/invoices/new"
              className="mt-4 inline-flex items-center gap-1.5 rounded-lg bg-[#0d1117] px-4 py-2 text-sm font-medium text-white hover:bg-[#161b22]"
            >
              <Plus className="h-3.5 w-3.5" />New invoice
            </Link>
          )}
        </div>
      ) : (
        <div className="space-y-2">
          {visible.map((inv) => {
            const isOverdue = inv.status === "OVERDUE";
            const isPaid    = inv.status === "PAID";
            const isDraft   = inv.status === "DRAFT";
            const nextStatus = NEXT_STATUS[inv.status];
            const amount = Number(inv.total_sek);

            return (
              <div
                key={inv.id}
                className={`group flex items-center gap-4 rounded-xl border bg-white px-5 py-4 shadow-sm transition-all hover:shadow-md ${
                  isOverdue ? "border-red-200 hover:border-red-300" :
                  isPaid    ? "border-emerald-100 hover:border-emerald-200" :
                              "border-gray-200 hover:border-gray-300"
                }`}
              >
                {/* Left accent bar */}
                <div className={`h-10 w-1 shrink-0 rounded-full ${
                  isOverdue ? "bg-red-400" :
                  isPaid    ? "bg-emerald-400" :
                  isDraft   ? "bg-gray-200" : "bg-blue-400"
                }`} />

                {/* Invoice number + customer */}
                <div className="w-28 shrink-0">
                  <Link
                    href={`/invoices/${inv.id}`}
                    className="font-mono text-sm font-bold text-gray-900 hover:text-blue-600 transition-colors"
                  >
                    {inv.invoice_number}
                  </Link>
                  <p className="text-[11px] text-gray-400 mt-0.5">{inv.issue_date}</p>
                </div>

                {/* Customer */}
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-semibold text-gray-900 truncate">{inv.customer.company_name}</p>
                  <p className="text-xs text-gray-400">Due {inv.due_date}</p>
                </div>

                {/* Status */}
                <div className="shrink-0">
                  <StatusBadge status={inv.status} />
                </div>

                {/* Amount */}
                <div className="w-32 shrink-0 text-right">
                  <p className={`tabular-nums text-base font-bold ${isOverdue ? "text-red-600" : isPaid ? "text-emerald-600" : "text-gray-900"}`}>
                    {fmt(amount)}
                  </p>
                  <p className="text-[11px] text-gray-400">SEK</p>
                </div>

                {/* Actions */}
                <div className="flex shrink-0 items-center gap-1.5">
                  <button
                    onClick={() => window.open(api.downloadUrl(`/api/invoicing/invoices/${inv.id}/pdf`), "_blank")}
                    className="rounded-lg px-2.5 py-1.5 text-[11px] font-semibold text-gray-400 hover:bg-gray-100 hover:text-gray-700 transition-colors"
                  >
                    PDF
                  </button>
                  {nextStatus && (
                    <button
                      onClick={() => advanceStatus(inv)}
                      disabled={updating === inv.id}
                      className={`inline-flex items-center gap-1 rounded-lg px-2.5 py-1.5 text-[11px] font-semibold transition-colors disabled:opacity-50 ${
                        isOverdue
                          ? "bg-red-50 text-red-600 hover:bg-red-100 border border-red-200"
                          : isDraft
                          ? "bg-gray-900 text-white hover:bg-gray-700"
                          : "bg-blue-50 text-blue-600 hover:bg-blue-100 border border-blue-200"
                      }`}
                    >
                      {updating === inv.id ? "…" : (
                        <>
                          {isDraft ? <Send className="h-3 w-3" /> : <CheckCircle2 className="h-3 w-3" />}
                          {isDraft ? "Send" : "Mark paid"}
                        </>
                      )}
                    </button>
                  )}
                  <Link
                    href={`/invoices/${inv.id}`}
                    className="rounded-lg p-1.5 text-gray-300 hover:bg-gray-100 hover:text-gray-600 transition-colors"
                  >
                    <ArrowRight className="h-4 w-4" />
                  </Link>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
