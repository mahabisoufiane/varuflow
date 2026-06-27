"use client";

import { api } from "@/lib/api-client";
import { Link } from "@/i18n/navigation";
import { useEffect, useState } from "react";
import { toast } from "sonner";
import { cn } from "@/lib/utils";
import { cx } from "@/lib/cx";
import styles from "./page.module.scss";
import {
  AlertTriangle, ArrowRight, CheckCircle2, Clock,
  FileDown, FileText, Plus, Send, TrendingUp,
} from "lucide-react";
import { Stagger, StaggerItem } from "@/components/motion";
import { EmptyState } from "@/components/ui/EmptyState";
import { EmptyInvoices } from "@/components/illustrations";

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
  const cfg: Record<string, { label: string; cls: string }> = {
    DRAFT:   { label: "Draft",   cls: "pill-draft"   },
    SENT:    { label: "Sent",    cls: "pill-sent"    },
    PAID:    { label: "Paid",    cls: "pill-paid"    },
    OVERDUE: { label: "Overdue", cls: "pill-overdue" },
  };
  const s = cfg[status] ?? cfg.DRAFT;
  return <span className={s.cls}>{s.label}</span>;
}

type Filter = "ALL" | "DRAFT" | "SENT" | "OVERDUE" | "PAID";

export default function InvoicesPage() {
  const [invoices, setInvoices] = useState<Invoice[]>([]);
  const [filter, setFilter] = useState<Filter>("ALL");
  const [updating, setUpdating] = useState<string | null>(null);
  const [markingOverdue, setMarkingOverdue] = useState(false);
  const [exporting, setExporting] = useState(false);

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

  async function handleExportExcel() {
    setExporting(true);
    try {
      const today = new Date().toISOString().slice(0, 10).replace(/-/g, "");
      await api.downloadBlob("/api/reports/excel/invoices", `invoices_${today}.xlsx`);
    } catch (e: unknown) { toast.error((e as Error).message); }
    finally { setExporting(false); }
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
  const draftCount   = invoices.filter(i => i.status === "DRAFT").length;

  const FILTERS: { key: Filter; label: string; count: number }[] = [
    { key: "ALL",     label: "All",     count: invoices.length },
    { key: "SENT",    label: "Sent",    count: invoices.filter(i => i.status === "SENT").length },
    { key: "OVERDUE", label: "Overdue", count: overdueCount },
    { key: "DRAFT",   label: "Draft",   count: draftCount },
    { key: "PAID",    label: "Paid",    count: paidCount },
  ];

  const visible = filter === "ALL" ? invoices : invoices.filter(i => i.status === filter);

  return (
    <div className="space-y-6">

      {/* ── Header ─────────────────────────────────────────────────────── */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold tracking-tight vf-text-1">Invoices</h1>
          <p className="text-xs vf-text-m mt-0.5">{invoices.length} total invoices</p>
        </div>
        <div className="flex gap-2">
          <button
            onClick={handleExportExcel}
            disabled={exporting}
            className="vf-btn-ghost text-xs disabled:opacity-50"
            title="Download as Excel"
          >
            <FileDown className="h-3.5 w-3.5" />
            {exporting ? "Exporting…" : "Excel"}
          </button>
          <button
            onClick={handleMarkOverdue}
            disabled={markingOverdue}
            className="vf-btn-ghost text-xs disabled:opacity-50"
          >
            <AlertTriangle className="h-3.5 w-3.5 text-amber-400" />
            {markingOverdue ? "Checking…" : "Flag overdue"}
          </button>
          <Link href="/invoices/new" className="vf-btn text-xs">
            <Plus className="h-3.5 w-3.5" />New invoice
          </Link>
        </div>
      </div>

      {/* ── KPI strip ───────────────────────────────────────────────────── */}
      <Stagger className="grid grid-cols-2 md:grid-cols-4 gap-3">
        {[
          {
            label: "Outstanding", value: `${fmt(outstanding)} kr`,
            sub: `${invoices.filter(i => i.status === "SENT" || i.status === "OVERDUE").length} invoices`,
            icon: <TrendingUp className="h-4 w-4" />, col: "text-indigo-400 bg-indigo-500/10",
          },
          {
            label: "Overdue", value: `${fmt(overdueAmt)} kr`,
            sub: overdueCount > 0 ? `${overdueCount} need action` : "All current",
            icon: <AlertTriangle className="h-4 w-4" />,
            col: overdueAmt > 0 ? "text-red-400 bg-red-500/10" : "text-emerald-400 bg-emerald-500/10",
          },
          {
            label: "Paid", value: String(paidCount),
            sub: "invoices collected",
            icon: <CheckCircle2 className="h-4 w-4" />, col: "text-emerald-400 bg-emerald-500/10",
          },
          {
            label: "Draft", value: String(draftCount),
            sub: "not yet sent",
            icon: <Clock className="h-4 w-4" />, col: "text-slate-400 bg-slate-500/10",
          },
        ].map(({ label, value, sub, icon, col }) => (
          <StaggerItem key={label} className={cx("vf-section", styles.kpiCard)}>
            <div className={cn("inline-flex h-9 w-9 items-center justify-center rounded-xl mb-3", col)}>{icon}</div>
            <p className="text-[10px] font-semibold vf-text-m uppercase tracking-wide mb-1">{label}</p>
            <p className="text-xl font-bold tabular-nums vf-text-1">{value}</p>
            {sub && <p className="text-[11px] vf-text-m mt-0.5">{sub}</p>}
          </StaggerItem>
        ))}
      </Stagger>

      {/* ── Filter tabs ──────────────────────────────────────────────────── */}
      <div className={styles.filterBar}>
        {FILTERS.map(({ key, label, count }) => (
          <button
            key={key}
            onClick={() => setFilter(key)}
            className={cx(styles.filterTab, filter === key && styles.filterTabActive)}
          >
            {label}
            <span className={cx(styles.filterCount, filter === key && styles.filterCountActive)}>{count}</span>
          </button>
        ))}
      </div>

      {/* ── Invoice list ─────────────────────────────────────────────────── */}
      {visible.length === 0 ? (
        <EmptyState
          illustration={<EmptyInvoices />}
          title={filter === "ALL" ? "No invoices yet" : `No ${filter.toLowerCase()} invoices`}
          description={filter === "ALL" ? "Create your first invoice to get started." : "Try a different filter."}
          action={filter === "ALL" ? (
            <Link href="/invoices/new" className="inline-flex vf-btn text-xs">
              <Plus className="h-3.5 w-3.5" />New invoice
            </Link>
          ) : undefined}
        />
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
                className={cx(
                  styles.invoiceRow,
                  isOverdue && styles.invoiceRowOverdue,
                  "group"
                )}
              >
                {/* Accent bar */}
                <div className={cn(
                  "h-10 w-[3px] shrink-0 rounded-full",
                  isOverdue ? "bg-red-500" : isPaid ? "bg-emerald-500" : isDraft ? "bg-slate-400" : "bg-indigo-500"
                )} />

                {/* Invoice # + date */}
                <div className="w-28 shrink-0">
                  <Link href={`/invoices/${inv.id}`}
                    className="font-mono text-[13px] font-bold vf-text-1 hover:text-indigo-500 transition-colors">
                    {inv.invoice_number}
                  </Link>
                  <p className="text-[11px] vf-text-m mt-0.5">{inv.issue_date}</p>
                </div>

                {/* Customer */}
                <div className="flex-1 min-w-0">
                  <p className="text-[13px] font-semibold vf-text-1 truncate">{inv.customer.company_name}</p>
                  <p className="text-xs vf-text-m">Due {inv.due_date}</p>
                </div>

                {/* Status */}
                <div className="shrink-0 hidden sm:block">
                  <StatusBadge status={inv.status} />
                </div>

                {/* Amount */}
                <div className="w-28 shrink-0 text-right">
                  <p className={cn(
                    "tabular-nums text-[15px] font-bold",
                    isOverdue ? "text-red-400" : isPaid ? "text-emerald-500" : "vf-text-1"
                  )}>
                    {fmt(Number(inv.total_sek))}
                  </p>
                  <p className="text-[11px] vf-text-m">SEK</p>
                </div>

                {/* Actions */}
                <div className="flex shrink-0 items-center gap-1.5">
                  <button
                    onClick={() => window.open(api.downloadUrl(`/api/invoicing/invoices/${inv.id}/pdf`), "_blank")}
                    className="vf-btn-ghost h-8 px-2.5 text-[11px] font-semibold"
                  >
                    PDF
                  </button>
                  {nextStatus && (
                    <button
                      onClick={() => advanceStatus(inv)}
                      disabled={updating === inv.id}
                      className={cn(
                        "inline-flex items-center gap-1 rounded-lg px-2.5 text-[11px] font-semibold transition-colors disabled:opacity-50 h-8",
                        isOverdue
                          ? "bg-red-500/10 text-red-400 hover:bg-red-500/20 border border-red-500/20"
                          : isDraft
                          ? "bg-indigo-600 text-white hover:bg-indigo-500"
                          : "bg-indigo-500/10 text-indigo-500 hover:bg-indigo-500/20 border border-indigo-500/20"
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
                    className="vf-btn-ghost h-8 w-8 p-0 flex items-center justify-center">
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
