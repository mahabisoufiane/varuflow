"use client";

import { api } from "@/lib/api-client";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { DataTable, type Column } from "@/components/ui/DataTable";
import { Link } from "@/i18n/navigation";
import { EmptyState } from "@/components/ui/EmptyState";
import { EmptyInvoices } from "@/components/illustrations";
import { useEffect, useState } from "react";
import { toast } from "sonner";
import { cn } from "@/lib/utils";
import { cx } from "@/lib/cx";
import styles from "./page.module.scss";
import {
  Plus, RefreshCw, Pause, Play, AlertCircle, Calendar, Users, Repeat, Send,
} from "lucide-react";

interface Customer { id: string; company_name: string; }
interface Invoice  { id: string; invoice_number: string; }
interface Recurring {
  id: string; customer_id: string; customer_name: string;
  frequency: "WEEKLY" | "MONTHLY"; next_run_date: string;
  is_active: boolean; template_invoice_id: string | null;
  auto_send: boolean; auto_send_method: string;
}

const FREQ_LABEL: Record<string, string> = { WEEKLY: "Weekly", MONTHLY: "Monthly" };
const METHOD_LABEL: Record<string, string> = {
  email: "Email",
  peppol: "Peppol",
  "email,peppol": "Email + Peppol",
};

export default function RecurringPage() {
  const [items, setItems]       = useState<Recurring[]>([]);
  const [customers, setCustomers] = useState<Customer[]>([]);
  const [invoices, setInvoices] = useState<Invoice[]>([]);
  const [loading, setLoading]   = useState(true);
  const [open, setOpen]         = useState(false);
  const [form, setForm]         = useState({
    customer_id: "", frequency: "MONTHLY", next_run_date: "", template_invoice_id: "",
    auto_send: false, auto_send_method: "email",
  });
  const [saving, setSaving]     = useState(false);
  const [running, setRunning]   = useState<string | null>(null);
  const [error, setError]       = useState<string | null>(null);

  async function load() {
    try {
      const [rec, cust, inv] = await Promise.all([
        api.get<Recurring[]>("/api/recurring"),
        api.get<Customer[]>("/api/invoicing/customers?is_active=true"),
        api.get<Invoice[]>("/api/invoicing/invoices"),
      ]);
      setItems(rec); setCustomers(cust); setInvoices(inv);
    } catch (e: unknown) { setError((e as Error).message); }
    finally { setLoading(false); }
  }

  useEffect(() => { load(); }, []);

  function setF(k: string, v: string | boolean) { setForm(s => ({ ...s, [k]: v })); }

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault(); setSaving(true); setError(null);
    try {
      await api.post("/api/recurring", {
        customer_id:          form.customer_id,
        frequency:            form.frequency,
        next_run_date:        form.next_run_date,
        template_invoice_id:  form.template_invoice_id,
        auto_send:            form.auto_send,
        auto_send_method:     form.auto_send_method,
      });
      setOpen(false); await load();
      toast.success("Recurring invoice created");
    } catch (e: unknown) { setError((e as Error).message); }
    finally { setSaving(false); }
  }

  async function toggle(id: string) {
    try {
      await api.patch(`/api/recurring/${id}/toggle`, {});
      await load();
    } catch (e: unknown) { toast.error((e as Error).message); }
  }

  async function runNow(id: string) {
    setRunning(id); setError(null);
    try {
      const res = await api.post<{ invoice_number: string }>(`/api/recurring/${id}/run`, {});
      await load();
      toast.success(`Created invoice ${res.invoice_number}`);
    } catch (e: unknown) { toast.error((e as Error).message); }
    finally { setRunning(null); }
  }

  const active = items.filter(r => r.is_active).length;
  const paused = items.length - active;

  return (
    <div className="space-y-6">

      {/* ── Header ─────────────────────────────────────────────────── */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold tracking-tight vf-text-1">Recurring Invoices</h1>
          <p className="text-xs vf-text-m mt-0.5">Auto-generate invoices on a schedule</p>
        </div>
        <button onClick={() => { setError(null); setOpen(true); }} className="vf-btn text-xs">
          <Plus className="h-3.5 w-3.5" />New recurring
        </button>
      </div>

      {/* ── KPI strip ───────────────────────────────────────────────── */}
      {!loading && items.length > 0 && (
        <div className="grid grid-cols-3 gap-3">
          {[
            { label: "Total",  value: items.length, icon: <Repeat className="h-4 w-4" />,   col: "text-indigo-400 bg-indigo-500/10"  },
            { label: "Active", value: active,        icon: <Play className="h-4 w-4" />,     col: "text-emerald-400 bg-emerald-500/10" },
            { label: "Paused", value: paused,        icon: <Pause className="h-4 w-4" />,    col: "text-slate-400 bg-slate-500/10"    },
          ].map(({ label, value, icon, col }) => (
            <div key={label} className={cx("vf-section", styles.kpiCard)}>
              <div className={cn("inline-flex h-8 w-8 items-center justify-center rounded-lg mb-2", col)}>{icon}</div>
              <p className="text-[10px] font-semibold vf-text-m uppercase tracking-wide">{label}</p>
              <p className="text-xl font-bold tabular-nums vf-text-1">{value}</p>
            </div>
          ))}
        </div>
      )}

      {/* ── Error ──────────────────────────────────────────────────── */}
      {error && (
        <div className={styles.errorBanner}>
          <AlertCircle className="h-4 w-4 mt-0.5 shrink-0" />
          {error}
        </div>
      )}

      {/* ── Content ────────────────────────────────────────────────── */}
      {loading ? (
        <div className="space-y-2">
          {[1, 2, 3].map(i => <div key={i} className="h-16 skeleton rounded-xl" />)}
        </div>
      ) : items.length === 0 ? (
        <EmptyState
          illustration={<EmptyInvoices />}
          title="No recurring invoices"
          description="Set up a recurring invoice from an existing invoice template."
          action={invoices.length === 0 ? (
            <p className="text-xs vf-text-m">
              You need at least one invoice first.{" "}
              <Link href="/invoices/new" className="text-indigo-500 hover:underline">Create one</Link>.
            </p>
          ) : undefined}
        />
      ) : (
        <DataTable<Recurring>
          columns={[
            {
              key: "customer",
              header: "Customer",
              render: (r) => (
                <div className="flex items-center gap-2">
                  <div className={styles.customerIcon}>
                    <Users className="h-3.5 w-3.5 vf-text-m" />
                  </div>
                  <span className="font-medium vf-text-1 text-[13px]">{r.customer_name}</span>
                </div>
              ),
            },
            {
              key: "frequency",
              header: "Frequency",
              hideBelow: "sm",
              render: (r) => (
                <div className="flex items-center gap-1.5">
                  <Calendar className="h-3 w-3 vf-text-m" />
                  <span className="text-[13px] vf-text-2">{FREQ_LABEL[r.frequency]}</span>
                </div>
              ),
            },
            {
              key: "next_run",
              header: "Next run",
              hideBelow: "md",
              render: (r) => (
                <span className="text-[13px] vf-text-m font-mono">{r.next_run_date}</span>
              ),
            },
            {
              key: "status",
              header: "Status",
              className: "text-center",
              render: (r) => (
                <div className="text-center">
                  {r.is_active ? (
                    <span className={styles.statusActive}>
                      <span className="h-1.5 w-1.5 rounded-full bg-emerald-400" />Active
                    </span>
                  ) : (
                    <span className={styles.statusPaused}>
                      <Pause className="h-3 w-3" />Paused
                    </span>
                  )}
                  {r.auto_send && (
                    <div className={styles.autoSendBadge}>
                      <Send className="h-2.5 w-2.5" />
                      Auto {METHOD_LABEL[r.auto_send_method] ?? r.auto_send_method}
                    </div>
                  )}
                </div>
              ),
            },
            {
              key: "actions",
              header: "Actions",
              className: "text-right",
              render: (r) => (
                <div className="flex justify-end gap-1.5">
                  <button
                    disabled={!r.is_active || running === r.id}
                    onClick={() => runNow(r.id)}
                    className="vf-btn-ghost h-7 px-2.5 text-[11px] font-semibold disabled:opacity-40">
                    <RefreshCw className={cn("h-3 w-3", running === r.id ? "animate-spin" : "")} />
                    {running === r.id ? "Running…" : "Run now"}
                  </button>
                  <button
                    onClick={() => toggle(r.id)}
                    className="vf-btn-ghost h-7 w-7 p-0 flex items-center justify-center">
                    {r.is_active
                      ? <Pause className="h-3.5 w-3.5 text-amber-400" />
                      : <Play className="h-3.5 w-3.5 text-emerald-400" />
                    }
                  </button>
                </div>
              ),
            },
          ]}
          data={items}
          keyExtractor={(r) => r.id}
        />
      )}

      {/* ── Create modal ───────────────────────────────────────────── */}
      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent
          className="sm:max-w-sm rounded-2xl border-[var(--vf-border)] bg-[var(--vf-bg-surface)]"
        >
          <DialogHeader>
            <DialogTitle className="vf-text-1 text-base font-semibold">New recurring invoice</DialogTitle>
          </DialogHeader>

          <form onSubmit={handleCreate} className="space-y-4 pt-1">
            <div className="space-y-1.5">
              <label className="text-xs font-medium vf-text-2">Customer *</label>
              <select required value={form.customer_id} onChange={e => setF("customer_id", e.target.value)}
                className="vf-input w-full">
                <option value="">Select…</option>
                {customers.map(c => <option key={c.id} value={c.id}>{c.company_name}</option>)}
              </select>
            </div>

            <div className="space-y-1.5">
              <label className="text-xs font-medium vf-text-2">Template invoice *</label>
              <select required value={form.template_invoice_id} onChange={e => setF("template_invoice_id", e.target.value)}
                className="vf-input w-full">
                <option value="">Select invoice…</option>
                {invoices.map(i => <option key={i.id} value={i.id}>{i.invoice_number}</option>)}
              </select>
            </div>

            <div className="space-y-1.5">
              <label className="text-xs font-medium vf-text-2">Frequency *</label>
              <select required value={form.frequency} onChange={e => setF("frequency", e.target.value)}
                className="vf-input w-full">
                <option value="MONTHLY">Monthly</option>
                <option value="WEEKLY">Weekly</option>
              </select>
            </div>

            <div className="space-y-1.5">
              <label className="text-xs font-medium vf-text-2">First run date *</label>
              <input type="date" required value={form.next_run_date}
                onChange={e => setF("next_run_date", e.target.value)}
                className="vf-input w-full" />
            </div>

            <div className={cx("space-y-2 pt-2", styles.divider)}>
              <label className="flex items-center gap-2 text-xs font-medium vf-text-2 cursor-pointer select-none">
                <input
                  type="checkbox"
                  checked={form.auto_send}
                  onChange={e => setF("auto_send", e.target.checked)}
                  className="h-3.5 w-3.5 rounded border-[var(--vf-border-strong)]"
                />
                <Send className="h-3.5 w-3.5" />
                Auto-send invoice on schedule
              </label>
              <p className="text-[11px] vf-text-m pl-5">
                When on, every generated invoice is delivered automatically through the channels below.
                Leave off to keep invoices in Draft for manual review.
              </p>
              {form.auto_send && (
                <div className="pl-5 space-y-1.5">
                  <label className="text-[11px] font-medium vf-text-2">Delivery channel</label>
                  <select
                    value={form.auto_send_method}
                    onChange={e => setF("auto_send_method", e.target.value)}
                    className="vf-input w-full"
                  >
                    <option value="email">Email only</option>
                    <option value="peppol">Peppol only (requires Peppol ID on customer)</option>
                    <option value="email,peppol">Email + Peppol</option>
                  </select>
                </div>
              )}
            </div>

            {error && (
              <p className={cx("text-xs text-red-400 rounded-lg px-3 py-2", styles.errorBanner)}>
                {error}
              </p>
            )}

            <div className={cx("flex justify-end gap-2 pt-2", styles.divider)}>
              <button type="button" onClick={() => setOpen(false)} className="vf-btn-ghost text-xs px-4">
                Cancel
              </button>
              <button type="submit" disabled={saving} className="vf-btn text-xs px-4 disabled:opacity-50">
                {saving ? "Creating…" : "Create"}
              </button>
            </div>
          </form>
        </DialogContent>
      </Dialog>
    </div>
  );
}
