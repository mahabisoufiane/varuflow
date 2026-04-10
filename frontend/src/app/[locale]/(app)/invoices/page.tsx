"use client";

import { api } from "@/lib/api-client";
import { Link } from "@/i18n/navigation";
import { useEffect, useState } from "react";
import { toast } from "sonner";
import { cn } from "@/lib/utils";
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
    DRAFT:   { label: "Draft",   cls: "bg-white/5 text-slate-400 border-white/10",             dot: "bg-slate-500"    },
    SENT:    { label: "Sent",    cls: "bg-indigo-500/10 text-indigo-400 border-indigo-500/20", dot: "bg-indigo-400"   },
    PAID:    { label: "Paid",    cls: "bg-emerald-500/10 text-emerald-400 border-emerald-500/20", dot: "bg-emerald-400" },
    OVERDUE: { label: "Overdue", cls: "bg-red-500/10 text-red-400 border-red-500/20",           dot: "bg-red-400"     },
  };
  const s = cfg[status] ?? cfg.DRAFT;
  return (
    <span className={cn("inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-[11px] font-semibold", s.cls)}>
      <span className={cn("h-1.5 w-1.5 rounded-full", s.dot)} />
      {s.label}
    </span>
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

  const outstanding  = invoices.filter(i => i.status === "SENT" || i.status === "OVERDUE").reduce((s, i) => s + Number(i.total_sek), 0);
  const overdueAmt   = invoices.filter(i => i.status === "OVERDUE").reduce((s, i) => s + Number(i.total_sek), 0);
  const paidCount    = invoices.filter(i => i.status === "PAID").length;
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
          <h1 className="text-xl font-bold tracking-tight text-slate-100">Invoices</h1>
          <p className="text-xs text-slate-600 mt-0.5">{invoices.length} total invoices</p>
        </div>
        <div className="flex gap-2">
          <button
            onClick={handleMarkOverdue}
            disabled={markingOverdue}
            className="vf-btn-ghost text-xs px-3 py-1.5 h-auto disabled:opacity-50"
          >
            <AlertTriangle className="h-3.5 w-3.5 text-amber-400" />
            {markingOverdue ? "Checking…" : "Flag overdue"}
          </button>
          <Link href="/invoices/new" className="vf-btn text-xs px-3 py-1.5 h-auto">
            <Plus className="h-3.5 w-3.5" />New invoice
          </Link>
        </div>
      </div>

      {/* KPI strip */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        {[
          { label: "Outstanding",  value: `${fmt(outstanding)} kr`,  sub: `${invoices.filter(i => i.status === "SENT" || i.status === "OVERDUE").length} invoices`, icon: <TrendingUp className="h-4 w-4" />, col: "text-indigo-400 bg-indigo-500/10" },
          { label: "Overdue",      value: `${fmt(overdueAmt)} kr`,   sub: overdueCount > 0 ? `${overdueCount} need action` : "All current", icon: <AlertTriangle className="h-4 w-4" />, col: overdueAmt > 0 ? "text-red-400 bg-red-500/10" : "text-slate-500 bg-white/5" },
          { label: "Paid",         value: String(paidCount),          sub: "invoices collected",   icon: <CheckCircle2 className="h-4 w-4" />, col: "text-emerald-400 bg-emerald-500/10" },
          { label: "Draft",        value: String(invoices.filter(i => i.status === "DRAFT").length), sub: "not yet sent", icon: <Clock className="h-4 w-4" />, col: "text-slate-400 bg-white/5" },
        ].map(({ label, value, sub, icon, col }) => (
          <div key={label} className="rounded-xl border border-white/[0.06] bg-vf-surface p-4">
            <div className={cn("inline-flex h-8 w-8 items-center justify-center rounded-lg mb-3", col)}>{icon}</div>
            <p className="text-2xl font-bold tabular-nums text-slate-100">{value}</p>
            <p className="text-xs text-slate-600 mt-0.5">{label}</p>
            {sub && <p className="text-[11px] text-slate-700 mt-0.5">{sub}</p>}
          </div>
        ))}
      </div>

      {/* Filter tabs */}
      <div className="flex items-center gap-1 border-b border-white/[0.06]">
        {FILTERS.map(({ key, label, count }) => (
          <button
            key={key}
            onClick={() => setFilter(key)}
            className={cn(
              "flex items-center gap-1.5 px-3 py-2 text-[13px] font-medium transition-colors border-b-2 -mb-px",
              filter === key
                ? "border-indigo-500 text-slate-100"
                : "border-transparent text-slate-600 hover:text-slate-300"
            )}
          >
            {label}
            <span className={cn(
              "rounded-full px-1.5 py-0.5 text-[10px] font-bold",
              filter === key ? "bg-indigo-500/20 text-indigo-400" : "bg-white/5 text-slate-600"
            )}>{count}</span>
          </button>
        ))}
      </div>

      {/* Invoice list */}
      {visible.length === 0 ? (
        <div className="rounded-xl border border-dashed border-white/[0.08] bg-vf-surface px-6 py-20 text-center">
          <FileText className="mx-auto h-10 w-10 text-slate-700 mb-3" />
          <p className="text-sm font-semibold text-slate-500">No invoices</p>
          <p className="text-xs text-slate-700 mt-1">
            {filter === "ALL" ? "Create your first invoice to get started." : `No ${filter.toLowerCase()} invoices.`}
          </p>
          {filter === "ALL" && (
            <Link href="/invoices/new" className="mt-4 inline-flex vf-btn text-xs px-4 py-2">
              <Plus className="h-3.5 w-3.5" />New invoice
            </Link>
          )}
        </div>
      ) : (
        <div className="space-y-[3px]">
          {visible.map((inv) => {
            const isOverdue = inv.status === "OVERDUE";
            const isPaid    = inv.status === "PAID";
            const isDraft   = inv.status === "DRAFT";
            const nextStatus = NEXT_STATUS[inv.status];

            return (
              <div
                key={inv.id}
                className={cn(
                  "group flex items-center gap-4 rounded-xl border px-5 py-4 transition-all hover:bg-vf-elevated",
                  isOverdue ? "border-red-500/15 bg-red-500/5" :
                  isPaid    ? "border-emerald-500/10 bg-vf-surface" :
                              "border-white/[0.06] bg-vf-surface"
                )}
              >
                {/* Accent bar */}
                <div className={cn("h-10 w-[3px] shrink-0 rounded-full", isOverdue ? "bg-red-500" : isPaid ? "bg-emerald-500" : isDraft ? "bg-slate-700" : "bg-indigo-500")} />

                {/* Invoice # + date */}
                <div className="w-28 shrink-0">
                  <Link href={`/invoices/${inv.id}`}
                    className="font-mono text-[13px] font-bold text-slate-200 hover:text-indigo-400 transition-colors">
                    {inv.invoice_number}
                  </Link>
                  <p className="text-[11px] text-slate-600 mt-0.5">{inv.issue_date}</p>
                </div>

                {/* Customer */}
                <div className="flex-1 min-w-0">
                  <p className="text-[13px] font-semibold text-slate-200 truncate">{inv.customer.company_name}</p>
                  <p className="text-xs text-slate-600">Due {inv.due_date}</p>
                </div>

                {/* Status */}
                <div className="shrink-0">
                  <StatusBadge status={inv.status} />
                </div>

                {/* Amount */}
                <div className="w-32 shrink-0 text-right">
                  <p className={cn("tabular-nums text-[15px] font-bold", isOverdue ? "text-red-400" : isPaid ? "text-emerald-400" : "text-slate-100")}>
                    {fmt(Number(inv.total_sek))}
                  </p>
                  <p className="text-[11px] text-slate-600">SEK</p>
                </div>

                {/* Actions */}
                <div className="flex shrink-0 items-center gap-1.5">
                  <button
                    onClick={() => window.open(api.downloadUrl(`/api/invoicing/invoices/${inv.id}/pdf`), "_blank")}
                    className="rounded-lg px-2.5 py-1.5 text-[11px] font-semibold text-slate-600 hover:bg-white/5 hover:text-slate-300 transition-colors"
                  >
                    PDF
                  </button>
                  {nextStatus && (
                    <button
                      onClick={() => advanceStatus(inv)}
                      disabled={updating === inv.id}
                      className={cn(
                        "inline-flex items-center gap-1 rounded-lg px-2.5 py-1.5 text-[11px] font-semibold transition-colors disabled:opacity-50",
                        isOverdue
                          ? "bg-red-500/10 text-red-400 hover:bg-red-500/20 border border-red-500/20"
                          : isDraft
                          ? "bg-indigo-600 text-white hover:bg-indigo-500"
                          : "bg-indigo-500/10 text-indigo-400 hover:bg-indigo-500/20 border border-indigo-500/20"
                      )}
                    >
                      {updating === inv.id ? "…" : (
                        <>
                          {isDraft ? <Send className="h-3 w-3" /> : <CheckCircle2 className="h-3 w-3" />}
                          {isDraft ? "Send" : "Mark paid"}
                        </>
                      )}
                    </button>
                  )}
                  <Link href={`/invoices/${inv.id}`}
                    className="rounded-lg p-1.5 text-slate-700 hover:bg-white/5 hover:text-slate-400 transition-colors">
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
