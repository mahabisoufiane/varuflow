"use client";

import { api } from "@/lib/api-client";
import { Button } from "@/components/ui/button";
import Link from "next/link";
import { useEffect, useState } from "react";
import { FileText, Plus } from "lucide-react";

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

const STATUS_COLORS: Record<string, string> = {
  DRAFT: "bg-gray-100 text-gray-700",
  SENT: "bg-blue-100 text-blue-700",
  PAID: "bg-green-100 text-green-700",
  OVERDUE: "bg-red-100 text-red-700",
};

const NEXT_STATUS: Record<string, string | null> = {
  DRAFT: "SENT",
  SENT: "PAID",
  OVERDUE: "PAID",
  PAID: null,
};

const NEXT_LABEL: Record<string, string> = {
  DRAFT: "Mark Sent",
  SENT: "Mark Paid",
  OVERDUE: "Mark Paid",
};

export default function InvoicesPage() {
  const [invoices, setInvoices] = useState<Invoice[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [updating, setUpdating] = useState<string | null>(null);

  async function load() {
    try { setInvoices(await api.get<Invoice[]>("/api/invoicing/invoices")); }
    catch (e: any) { setError(e.message); }
    finally { setLoading(false); }
  }

  useEffect(() => { load(); }, []);

  async function advanceStatus(inv: Invoice) {
    const next = NEXT_STATUS[inv.status];
    if (!next) return;
    setUpdating(inv.id);
    try {
      await api.patch(`/api/invoicing/invoices/${inv.id}/status`, { status: next });
      await load();
    } catch (e: any) { setError(e.message); } finally { setUpdating(null); }
  }

  function downloadPDF(id: string) {
    window.open(api.downloadUrl(`/api/invoicing/invoices/${id}/pdf`), "_blank");
  }

  const outstanding = invoices
    .filter((i) => i.status === "SENT" || i.status === "OVERDUE")
    .reduce((s, i) => s + Number(i.total_sek), 0);
  const overdue = invoices
    .filter((i) => i.status === "OVERDUE")
    .reduce((s, i) => s + Number(i.total_sek), 0);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-[#1a2332]">Invoices</h1>
          <p className="text-sm text-muted-foreground">{invoices.length} invoices</p>
        </div>
        <Button asChild size="sm" className="bg-[#1a2332] hover:bg-[#2a3342] text-white">
          <Link href="/invoices/new"><Plus className="mr-1.5 h-3.5 w-3.5" />New invoice</Link>
        </Button>
      </div>

      {invoices.length > 0 && (
        <div className="grid grid-cols-2 gap-4">
          <div className="rounded-xl border bg-white p-4">
            <p className="text-xs text-muted-foreground">Outstanding</p>
            <p className="text-xl font-bold text-[#1a2332] mt-0.5">
              {outstanding.toLocaleString("sv-SE", { minimumFractionDigits: 2 })} SEK
            </p>
          </div>
          <div className="rounded-xl border bg-white p-4">
            <p className="text-xs text-muted-foreground">Overdue</p>
            <p className={`text-xl font-bold mt-0.5 ${overdue > 0 ? "text-red-600" : "text-gray-400"}`}>
              {overdue.toLocaleString("sv-SE", { minimumFractionDigits: 2 })} SEK
            </p>
          </div>
        </div>
      )}

      {error && <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-2 text-sm text-red-700">{error}</div>}

      {loading ? (
        <div className="space-y-2 animate-pulse">{[1, 2, 3].map((i) => <div key={i} className="h-16 rounded-xl bg-gray-100" />)}</div>
      ) : invoices.length === 0 ? (
        <div className="rounded-xl border bg-white px-6 py-12 text-center">
          <FileText className="mx-auto h-10 w-10 text-gray-300" />
          <h3 className="mt-3 font-medium text-gray-900">No invoices yet</h3>
          <p className="mt-1 text-sm text-muted-foreground">Create your first invoice to get paid.</p>
          <Button asChild size="sm" className="mt-4 bg-[#1a2332] hover:bg-[#2a3342] text-white">
            <Link href="/invoices/new"><Plus className="mr-1.5 h-3.5 w-3.5" />New invoice</Link>
          </Button>
        </div>
      ) : (
        <div className="rounded-xl border bg-white overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-gray-50 text-xs text-gray-500 uppercase">
              <tr>
                <th className="px-4 py-3 text-left">Invoice #</th>
                <th className="px-4 py-3 text-left">Customer</th>
                <th className="px-4 py-3 text-center">Status</th>
                <th className="px-4 py-3 text-right">Total (SEK)</th>
                <th className="px-4 py-3 text-left">Due</th>
                <th className="px-4 py-3 text-right" />
              </tr>
            </thead>
            <tbody className="divide-y">
              {invoices.map((inv) => (
                <tr key={inv.id} className="hover:bg-gray-50">
                  <td className="px-4 py-3 font-mono text-xs">
                    <Link href={`/invoices/${inv.id}`} className="text-[#1a2332] hover:underline font-medium">
                      {inv.invoice_number}
                    </Link>
                  </td>
                  <td className="px-4 py-3 font-medium">{inv.customer.company_name}</td>
                  <td className="px-4 py-3 text-center">
                    <span className={`rounded px-2 py-0.5 text-xs font-medium ${STATUS_COLORS[inv.status]}`}>{inv.status}</span>
                  </td>
                  <td className="px-4 py-3 text-right font-mono">
                    {Number(inv.total_sek).toLocaleString("sv-SE", { minimumFractionDigits: 2 })}
                  </td>
                  <td className="px-4 py-3 text-muted-foreground text-xs">{inv.due_date}</td>
                  <td className="px-4 py-3">
                    <div className="flex justify-end gap-2">
                      <Button variant="ghost" size="sm" className="h-7 text-xs" onClick={() => downloadPDF(inv.id)}>PDF</Button>
                      {NEXT_STATUS[inv.status] && (
                        <Button variant="outline" size="sm" className="h-7 text-xs"
                          disabled={updating === inv.id} onClick={() => advanceStatus(inv)}>
                          {NEXT_LABEL[inv.status]}
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
