"use client";

import { api } from "@/lib/api-client";
import { Button } from "@/components/ui/button";
import Link from "next/link";
import { useEffect, useState } from "react";
import { toast } from "sonner";
import { FileText, Plus, AlertTriangle } from "lucide-react";

interface Invoice {
  id: string;
  invoice_number: string;
  customer: { id: string; company_name: string };
  issue_date: string;
  due_date: string;
  status: "DRAFT" | "SENT" | "PAID" | "OVERDUE";
  total_sek: string;
  created_at: string;
}

const STATUS_STYLES: Record<string, string> = {
  DRAFT: "bg-gray-100 text-gray-600 border border-gray-200",
  SENT: "bg-blue-50 text-blue-700 border border-blue-200",
  PAID: "bg-emerald-50 text-emerald-700 border border-emerald-200",
  OVERDUE: "bg-red-50 text-red-700 border border-red-200",
};

const NEXT_STATUS: Record<string, string | null> = { DRAFT: "SENT", SENT: "PAID", OVERDUE: "PAID", PAID: null };
const NEXT_LABEL: Record<string, string> = { DRAFT: "Mark Sent", SENT: "Mark Paid", OVERDUE: "Mark Paid" };

export default function InvoicesPage() {
  const [invoices, setInvoices] = useState<Invoice[]>([]);
  const [loading, setLoading] = useState(true);
  const [updating, setUpdating] = useState<string | null>(null);
  const [markingOverdue, setMarkingOverdue] = useState(false);

  async function load() {
    try { setInvoices(await api.get<Invoice[]>("/api/invoicing/invoices")); }
    catch (e: any) { toast.error(e.message); }
    finally { setLoading(false); }
  }

  useEffect(() => { load(); }, []);

  async function advanceStatus(inv: Invoice) {
    const next = NEXT_STATUS[inv.status];
    if (!next) return;
    setUpdating(inv.id);
    try {
      await api.patch(`/api/invoicing/invoices/${inv.id}/status`, { status: next });
      toast.success(`${inv.invoice_number} marked as ${next.toLowerCase()}`);
      await load();
    } catch (e: any) { toast.error(e.message); }
    finally { setUpdating(null); }
  }

  async function handleMarkOverdue() {
    setMarkingOverdue(true);
    try {
      const res = await api.post<{ marked: number }>("/api/recurring/mark-overdue", {});
      toast.success(res.marked > 0 ? `${res.marked} invoices marked overdue` : "No invoices to mark overdue");
      if (res.marked > 0) await load();
    } catch (e: any) { toast.error(e.message); }
    finally { setMarkingOverdue(false); }
  }

  const outstanding = invoices.filter(i => i.status === "SENT" || i.status === "OVERDUE").reduce((s, i) => s + Number(i.total_sek), 0);
  const overdue = invoices.filter(i => i.status === "OVERDUE").reduce((s, i) => s + Number(i.total_sek), 0);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Invoices</h1>
          <p className="text-sm text-gray-400">{invoices.length} total</p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" size="sm" disabled={markingOverdue} onClick={handleMarkOverdue}>
            <AlertTriangle className="mr-1.5 h-3.5 w-3.5 text-red-500" />{markingOverdue ? "Checking…" : "Mark overdue"}
          </Button>
          <Button asChild size="sm" className="bg-[#0f1724] hover:bg-[#1a2840] text-white">
            <Link href="/invoices/new"><Plus className="mr-1.5 h-3.5 w-3.5" />New invoice</Link>
          </Button>
        </div>
      </div>

      {invoices.length > 0 && (
        <div className="grid grid-cols-2 gap-4">
          <div className="rounded-xl border border-gray-200 bg-white p-4 shadow-sm">
            <p className="text-xs font-medium text-gray-400 uppercase tracking-wide">Outstanding</p>
            <p className="mt-1 text-2xl font-bold text-gray-900">
              {outstanding.toLocaleString("sv-SE", { minimumFractionDigits: 0 })} <span className="text-base font-normal text-gray-400">SEK</span>
            </p>
          </div>
          <div className="rounded-xl border border-gray-200 bg-white p-4 shadow-sm">
            <p className="text-xs font-medium text-gray-400 uppercase tracking-wide">Overdue</p>
            <p className={`mt-1 text-2xl font-bold ${overdue > 0 ? "text-red-600" : "text-gray-300"}`}>
              {overdue.toLocaleString("sv-SE", { minimumFractionDigits: 0 })} <span className="text-base font-normal">SEK</span>
            </p>
          </div>
        </div>
      )}

      {loading ? (
        <div className="space-y-2">{[1,2,3].map(i => <div key={i} className="h-14 animate-pulse rounded-xl bg-gray-100" />)}</div>
      ) : invoices.length === 0 ? (
        <div className="rounded-xl border border-gray-200 bg-white px-6 py-16 text-center shadow-sm">
          <FileText className="mx-auto h-10 w-10 text-gray-200" />
          <h3 className="mt-3 font-semibold text-gray-900">No invoices yet</h3>
          <p className="mt-1 text-sm text-gray-400">Create your first invoice to get paid.</p>
          <Button asChild size="sm" className="mt-4 bg-[#0f1724] hover:bg-[#1a2840] text-white">
            <Link href="/invoices/new"><Plus className="mr-1.5 h-3.5 w-3.5" />New invoice</Link>
          </Button>
        </div>
      ) : (
        <div className="rounded-xl border border-gray-200 bg-white shadow-sm overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-100 bg-gray-50/80">
                <th className="px-5 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wide">Invoice #</th>
                <th className="px-5 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wide">Customer</th>
                <th className="px-5 py-3 text-center text-xs font-semibold text-gray-500 uppercase tracking-wide">Status</th>
                <th className="px-5 py-3 text-right text-xs font-semibold text-gray-500 uppercase tracking-wide">Amount</th>
                <th className="px-5 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wide">Due</th>
                <th className="px-5 py-3" />
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {invoices.map((inv) => (
                <tr key={inv.id} className="hover:bg-gray-50/70 transition-colors">
                  <td className="px-5 py-3.5">
                    <Link href={`/invoices/${inv.id}`} className="font-mono text-xs font-semibold text-[#0f1724] hover:text-blue-600 transition-colors">
                      {inv.invoice_number}
                    </Link>
                  </td>
                  <td className="px-5 py-3.5 font-medium text-gray-900">{inv.customer.company_name}</td>
                  <td className="px-5 py-3.5 text-center">
                    <span className={`inline-flex rounded-full px-2.5 py-0.5 text-[11px] font-semibold ${STATUS_STYLES[inv.status]}`}>
                      {inv.status}
                    </span>
                  </td>
                  <td className="px-5 py-3.5 text-right font-mono font-semibold text-gray-900">
                    {Number(inv.total_sek).toLocaleString("sv-SE", { minimumFractionDigits: 2 })}
                  </td>
                  <td className="px-5 py-3.5 text-xs text-gray-400">{inv.due_date}</td>
                  <td className="px-5 py-3.5">
                    <div className="flex justify-end gap-1.5">
                      <Button variant="ghost" size="sm" className="h-7 px-2 text-xs text-gray-400"
                        onClick={() => window.open(api.downloadUrl(`/api/invoicing/invoices/${inv.id}/pdf`), "_blank")}>
                        PDF
                      </Button>
                      {NEXT_STATUS[inv.status] && (
                        <Button variant="outline" size="sm" className="h-7 px-2.5 text-xs"
                          disabled={updating === inv.id} onClick={() => advanceStatus(inv)}>
                          {updating === inv.id ? "…" : NEXT_LABEL[inv.status]}
                        </Button>
                      )}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
