"use client";

import { api } from "@/lib/api-client";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Link } from "@/i18n/navigation";
import { useEffect, useState } from "react";
import { toast } from "sonner";
import { cn } from "@/lib/utils";
import {
  Plus, RefreshCw, Pause, Play, AlertCircle, Calendar, Users, Repeat,
} from "lucide-react";

interface Customer { id: string; company_name: string; }
interface Invoice  { id: string; invoice_number: string; }
interface Recurring {
  id: string; customer_id: string; customer_name: string;
  frequency: "WEEKLY" | "MONTHLY"; next_run_date: string;
  is_active: boolean; template_invoice_id: string | null;
}

const FREQ_LABEL: Record<string, string> = { WEEKLY: "Weekly", MONTHLY: "Monthly" };

export default function RecurringPage() {
  const [items, setItems]       = useState<Recurring[]>([]);
  const [customers, setCustomers] = useState<Customer[]>([]);
  const [invoices, setInvoices] = useState<Invoice[]>([]);
  const [loading, setLoading]   = useState(true);
  const [open, setOpen]         = useState(false);
  const [form, setForm]         = useState({
    customer_id: "", frequency: "MONTHLY", next_run_date: "", template_invoice_id: "",
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

  function setF(k: string, v: string) { setForm(s => ({ ...s, [k]: v })); }

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault(); setSaving(true); setError(null);
    try {
      await api.post("/api/recurring", {
        customer_id:          form.customer_id,
        frequency:            form.frequency,
        next_run_date:        form.next_run_date,
        template_invoice_id:  form.template_invoice_id,
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
            <div key={label} className="vf-section p-4" style={{ borderRadius: 14 }}>
              <div className={cn("inline-flex h-8 w-8 items-center justify-center rounded-lg mb-2", col)}>{icon}</div>
              <p className="text-[10px] font-semibold vf-text-m uppercase tracking-wide">{label}</p>
              <p className="text-xl font-bold tabular-nums vf-text-1">{value}</p>
            </div>
          ))}
        </div>
      )}

      {/* ── Error ──────────────────────────────────────────────────── */}
      {error && (
        <div className="flex items-start gap-2.5 rounded-xl px-4 py-3 text-sm text-red-400"
          style={{ background: "rgba(239,68,68,0.08)", border: "1px solid rgba(239,68,68,0.2)" }}>
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
        <div className="rounded-xl px-6 py-20 text-center"
          style={{ border: "1px dashed var(--vf-border-strong)", background: "var(--vf-bg-surface)" }}>
          <div className="mx-auto mb-3 flex h-12 w-12 items-center justify-center rounded-2xl"
            style={{ background: "var(--vf-bg-elevated)" }}>
            <RefreshCw className="h-6 w-6 vf-text-m" />
          </div>
          <p className="text-sm font-semibold vf-text-2">No recurring invoices</p>
          <p className="text-xs vf-text-m mt-1">Set up a recurring invoice from an existing invoice template.</p>
          {invoices.length === 0 && (
            <p className="text-xs vf-text-m mt-2">
              You need at least one invoice first.{" "}
              <Link href="/invoices/new" className="text-indigo-500 hover:underline">Create one</Link>.
            </p>
          )}
        </div>
      ) : (
        <div className="vf-section overflow-hidden" style={{ borderRadius: 14 }}>
          <table className="w-full text-sm">
            <thead>
              <tr style={{ borderBottom: "1px solid var(--vf-border)", background: "var(--vf-bg-elevated)" }}>
                <th className="px-5 py-3 text-left text-[11px] font-semibold uppercase tracking-wide vf-text-m">Customer</th>
                <th className="px-5 py-3 text-left text-[11px] font-semibold uppercase tracking-wide vf-text-m hidden sm:table-cell">Frequency</th>
                <th className="px-5 py-3 text-left text-[11px] font-semibold uppercase tracking-wide vf-text-m hidden md:table-cell">Next run</th>
                <th className="px-5 py-3 text-center text-[11px] font-semibold uppercase tracking-wide vf-text-m">Status</th>
                <th className="px-5 py-3 text-right text-[11px] font-semibold uppercase tracking-wide vf-text-m">Actions</th>
              </tr>
            </thead>
            <tbody>
              {items.map((r, i) => (
                <tr key={r.id} className={cn("vf-row", !r.is_active && "opacity-50")}
                  style={{ borderBottom: i < items.length - 1 ? "1px solid var(--vf-divider)" : undefined }}>
                  <td className="px-5 py-3.5">
                    <div className="flex items-center gap-2">
                      <div className="flex h-7 w-7 items-center justify-center rounded-lg shrink-0"
                        style={{ background: "var(--vf-bg-elevated)" }}>
                        <Users className="h-3.5 w-3.5 vf-text-m" />
                      </div>
                      <span className="font-medium vf-text-1 text-[13px]">{r.customer_name}</span>
                    </div>
                  </td>
                  <td className="px-5 py-3.5 hidden sm:table-cell">
                    <div className="flex items-center gap-1.5">
                      <Calendar className="h-3 w-3 vf-text-m" />
                      <span className="text-[13px] vf-text-2">{FREQ_LABEL[r.frequency]}</span>
                    </div>
                  </td>
                  <td className="px-5 py-3.5 text-[13px] vf-text-m font-mono hidden md:table-cell">
                    {r.next_run_date}
                  </td>
                  <td className="px-5 py-3.5 text-center">
                    {r.is_active ? (
                      <span className="inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-xs font-semibold text-emerald-400"
                        style={{ background: "rgba(16,185,129,0.1)", border: "1px solid rgba(16,185,129,0.2)" }}>
                        <span className="h-1.5 w-1.5 rounded-full bg-emerald-400" />Active
                      </span>
                    ) : (
                      <span className="inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-xs font-semibold vf-text-m"
                        style={{ background: "var(--vf-bg-elevated)", border: "1px solid var(--vf-border-strong)" }}>
                        <Pause className="h-3 w-3" />Paused
                      </span>
                    )}
                  </td>
                  <td className="px-5 py-3.5">
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
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* ── Create modal ───────────────────────────────────────────── */}
      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent
          className="sm:max-w-sm"
          style={{ background: "var(--vf-bg-surface)", borderColor: "var(--vf-border)", borderRadius: 16 }}
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

            {error && (
              <p className="text-xs text-red-400 rounded-lg px-3 py-2"
                style={{ background: "rgba(239,68,68,0.08)", border: "1px solid rgba(239,68,68,0.2)" }}>
                {error}
              </p>
            )}

            <div className="flex justify-end gap-2 pt-2" style={{ borderTop: "1px solid var(--vf-divider)" }}>
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
