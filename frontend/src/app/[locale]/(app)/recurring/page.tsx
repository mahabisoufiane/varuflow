"use client";

import { api } from "@/lib/api-client";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Label } from "@/components/ui/label";
import Link from "next/link";
import { useEffect, useState } from "react";
import { Plus, RefreshCw, Pause, Play } from "lucide-react";

interface Customer { id: string; company_name: string; }
interface Invoice { id: string; invoice_number: string; }
interface Recurring {
  id: string; customer_id: string; customer_name: string;
  frequency: "WEEKLY" | "MONTHLY"; next_run_date: string;
  is_active: boolean; template_invoice_id: string | null;
}

export default function RecurringPage() {
  const [items, setItems] = useState<Recurring[]>([]);
  const [customers, setCustomers] = useState<Customer[]>([]);
  const [invoices, setInvoices] = useState<Invoice[]>([]);
  const [loading, setLoading] = useState(false);
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState({ customer_id: "", frequency: "MONTHLY", next_run_date: "", template_invoice_id: "" });
  const [saving, setSaving] = useState(false);
  const [running, setRunning] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function load() {
    try {
      const [rec, cust, inv] = await Promise.all([
        api.get<Recurring[]>("/api/recurring"),
        api.get<Customer[]>("/api/invoicing/customers?is_active=true"),
        api.get<Invoice[]>("/api/invoicing/invoices"),
      ]);
      setItems(rec);
      setCustomers(cust);
      setInvoices(inv);
    } catch (e: any) { setError(e.message); } finally { setLoading(false); }
  }

  useEffect(() => { load(); }, []);

  function setF(k: string, v: string) { setForm((s) => ({ ...s, [k]: v })); }

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault(); setSaving(true); setError(null);
    try {
      await api.post("/api/recurring", {
        customer_id: form.customer_id,
        frequency: form.frequency,
        next_run_date: form.next_run_date,
        template_invoice_id: form.template_invoice_id,
      });
      setOpen(false);
      await load();
    } catch (e: any) { setError(e.message); } finally { setSaving(false); }
  }

  async function toggle(id: string) {
    try {
      await api.patch(`/api/recurring/${id}/toggle`, {});
      await load();
    } catch (e: any) { setError(e.message); }
  }

  async function runNow(id: string) {
    setRunning(id); setError(null);
    try {
      const res = await api.post<{ invoice_number: string }>(`/api/recurring/${id}/run`, {});
      await load();
      alert(`Created invoice ${res.invoice_number}`);
    } catch (e: any) { setError(e.message); } finally { setRunning(null); }
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-[#1a2332]">Recurring Invoices</h1>
          <p className="text-sm text-muted-foreground">Auto-generate invoices on a schedule</p>
        </div>
        <Button size="sm" className="bg-[#1a2332] hover:bg-[#2a3342] text-white" onClick={() => { setError(null); setOpen(true); }}>
          <Plus className="mr-1.5 h-3.5 w-3.5" />New recurring
        </Button>
      </div>

      {error && <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-2 text-sm text-red-700">{error}</div>}

      {loading ? (
        <div className="space-y-2 animate-pulse">{[1,2,3].map(i => <div key={i} className="h-16 rounded-xl bg-gray-100" />)}</div>
      ) : items.length === 0 ? (
        <div className="rounded-xl border bg-white px-6 py-12 text-center">
          <RefreshCw className="mx-auto h-10 w-10 text-gray-300" />
          <h3 className="mt-3 font-medium text-gray-900">No recurring invoices</h3>
          <p className="mt-1 text-sm text-muted-foreground">Set up a recurring invoice from an existing invoice template.</p>
          {invoices.length === 0 && (
            <p className="mt-2 text-xs text-muted-foreground">
              You need at least one invoice first. <Link href="/invoices/new" className="text-[#1a2332] underline">Create one</Link>.
            </p>
          )}
        </div>
      ) : (
        <div className="rounded-xl border bg-white overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-gray-50 text-xs text-gray-500 uppercase">
              <tr>
                <th className="px-4 py-3 text-left">Customer</th>
                <th className="px-4 py-3 text-left">Frequency</th>
                <th className="px-4 py-3 text-left">Next run</th>
                <th className="px-4 py-3 text-center">Status</th>
                <th className="px-4 py-3 text-right" />
              </tr>
            </thead>
            <tbody className="divide-y">
              {items.map((r) => (
                <tr key={r.id} className={`hover:bg-gray-50 ${!r.is_active ? "opacity-50" : ""}`}>
                  <td className="px-4 py-3 font-medium">{r.customer_name}</td>
                  <td className="px-4 py-3 capitalize text-muted-foreground">{r.frequency.toLowerCase()}</td>
                  <td className="px-4 py-3 text-muted-foreground text-xs">{r.next_run_date}</td>
                  <td className="px-4 py-3 text-center">
                    <span className={`rounded px-2 py-0.5 text-xs font-medium ${r.is_active ? "bg-green-100 text-green-700" : "bg-gray-100 text-gray-500"}`}>
                      {r.is_active ? "Active" : "Paused"}
                    </span>
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex justify-end gap-2">
                      <Button variant="outline" size="sm" className="h-7 text-xs" disabled={!r.is_active || running === r.id}
                        onClick={() => runNow(r.id)}>
                        <RefreshCw className="mr-1 h-3 w-3" />{running === r.id ? "Running…" : "Run now"}
                      </Button>
                      <Button variant="ghost" size="sm" className="h-7 text-xs" onClick={() => toggle(r.id)}>
                        {r.is_active ? <Pause className="h-3.5 w-3.5" /> : <Play className="h-3.5 w-3.5" />}
                      </Button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="sm:max-w-sm">
          <DialogHeader><DialogTitle>New recurring invoice</DialogTitle></DialogHeader>
          <form onSubmit={handleCreate} className="space-y-4 pt-2">
            <div className="space-y-1.5">
              <Label>Customer *</Label>
              <select required value={form.customer_id} onChange={(e) => setF("customer_id", e.target.value)}
                className="block w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-[#1a2332] focus:outline-none focus:ring-1 focus:ring-[#1a2332]">
                <option value="">Select…</option>
                {customers.map((c) => <option key={c.id} value={c.id}>{c.company_name}</option>)}
              </select>
            </div>
            <div className="space-y-1.5">
              <Label>Template invoice *</Label>
              <select required value={form.template_invoice_id} onChange={(e) => setF("template_invoice_id", e.target.value)}
                className="block w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-[#1a2332] focus:outline-none focus:ring-1 focus:ring-[#1a2332]">
                <option value="">Select invoice…</option>
                {invoices.map((i) => <option key={i.id} value={i.id}>{i.invoice_number}</option>)}
              </select>
            </div>
            <div className="space-y-1.5">
              <Label>Frequency *</Label>
              <select required value={form.frequency} onChange={(e) => setF("frequency", e.target.value)}
                className="block w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-[#1a2332] focus:outline-none focus:ring-1 focus:ring-[#1a2332]">
                <option value="MONTHLY">Monthly</option>
                <option value="WEEKLY">Weekly</option>
              </select>
            </div>
            <div className="space-y-1.5">
              <Label>First run date *</Label>
              <input type="date" required value={form.next_run_date} onChange={(e) => setF("next_run_date", e.target.value)}
                className="block w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-[#1a2332] focus:outline-none focus:ring-1 focus:ring-[#1a2332]" />
            </div>
            {error && <p className="text-sm text-red-600">{error}</p>}
            <div className="flex justify-end gap-3 pt-2">
              <Button type="button" variant="outline" onClick={() => setOpen(false)}>Cancel</Button>
              <Button type="submit" disabled={saving} className="bg-[#1a2332] hover:bg-[#2a3342] text-white">
                {saving ? "Saving…" : "Create"}
              </Button>
            </div>
          </form>
        </DialogContent>
      </Dialog>
    </div>
  );
}
