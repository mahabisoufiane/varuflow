"use client";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { portalApi, PORTAL_TOKEN_KEY, PORTAL_CUSTOMER_KEY } from "@/lib/portal-client";

interface DepositInvoice {
  id: string;
  invoice_number: string;
  invoice_type: string;
  status: string;
  issue_date: string;
  due_date: string;
  total_sek: string;
  deposit_amount: string | null;
  parent_invoice_id: string | null;
}

const STATUS_COLORS: Record<string, string> = {
  DRAFT:   "bg-gray-100 text-gray-600",
  SENT:    "bg-blue-100 text-blue-700",
  PAID:    "bg-green-100 text-green-700",
  OVERDUE: "bg-red-100 text-red-700",
};

const TYPE_LABELS: Record<string, string> = {
  deposit: "Deposit",
  final:   "Final Invoice",
};

export default function PortalDepositsPage() {
  const router = useRouter();
  const [invoices, setInvoices] = useState<DepositInvoice[]>([]);
  const [loading, setLoading] = useState(true);
  const [customerName, setCustomerName] = useState("");

  useEffect(() => {
    const token = localStorage.getItem(PORTAL_TOKEN_KEY);
    if (!token) { router.replace("/portal/login"); return; }

    const info = localStorage.getItem(PORTAL_CUSTOMER_KEY);
    if (info) {
      try {
        const parsed = JSON.parse(info);
        if (parsed?.customer_name) setCustomerName(parsed.customer_name);
      } catch {
        localStorage.removeItem(PORTAL_CUSTOMER_KEY);
      }
    }

    portalApi
      .get<DepositInvoice[]>("/api/portal/deposits")
      .then(setInvoices)
      .catch(() => router.replace("/portal/login"))
      .finally(() => setLoading(false));
  }, [router]);

  const deposits = invoices.filter((i) => i.invoice_type === "deposit");
  const finalInvoices = invoices.filter((i) => i.invoice_type === "final");
  const totalDeposited = deposits
    .filter((i) => i.status === "PAID")
    .reduce((s, i) => s + Number(i.deposit_amount ?? i.total_sek), 0);

  if (loading) {
    return (
      <div className="space-y-3">
        {[1, 2, 3].map((i) => <div key={i} className="h-16 rounded-xl bg-gray-100 animate-pulse" />)}
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-bold text-[#1a2332]">Deposit history</h1>
        {customerName && <p className="text-sm text-muted-foreground mt-0.5">{customerName}</p>}
      </div>

      {/* Summary */}
      {totalDeposited > 0 && (
        <div className="rounded-xl bg-purple-50 border border-purple-200 p-4 flex items-center justify-between">
          <p className="text-sm font-medium text-purple-800">Total deposits paid</p>
          <p className="text-lg font-bold text-purple-800">
            {totalDeposited.toLocaleString("sv-SE", { minimumFractionDigits: 2 })} SEK
          </p>
        </div>
      )}

      {invoices.length === 0 ? (
        <p className="text-sm text-muted-foreground text-center py-8">No deposit invoices on record.</p>
      ) : (
        <>
          {deposits.length > 0 && (
            <section className="space-y-3">
              <h2 className="text-sm font-semibold text-gray-500 uppercase tracking-wide">Deposit invoices</h2>
              <div className="divide-y rounded-xl border bg-white overflow-hidden">
                {deposits.map((inv) => (
                  <div key={inv.id} className="flex items-center justify-between px-4 py-3">
                    <div>
                      <p className="text-sm font-medium text-[#1a2332]">{inv.invoice_number}</p>
                      <p className="text-xs text-muted-foreground">Issued {inv.issue_date} · Due {inv.due_date}</p>
                    </div>
                    <div className="flex items-center gap-3">
                      <span className={`rounded px-2 py-0.5 text-xs font-medium ${STATUS_COLORS[inv.status] ?? "bg-gray-100 text-gray-600"}`}>
                        {inv.status}
                      </span>
                      <p className="text-sm font-mono font-medium">
                        {Number(inv.total_sek).toLocaleString("sv-SE", { minimumFractionDigits: 2 })} SEK
                      </p>
                    </div>
                  </div>
                ))}
              </div>
            </section>
          )}

          {finalInvoices.length > 0 && (
            <section className="space-y-3">
              <h2 className="text-sm font-semibold text-gray-500 uppercase tracking-wide">Final invoices (deposit offset)</h2>
              <div className="divide-y rounded-xl border bg-white overflow-hidden">
                {finalInvoices.map((inv) => {
                  const dep = Number(inv.deposit_amount ?? 0);
                  const total = Number(inv.total_sek);
                  const due = Math.max(0, total - dep);
                  return (
                    <div key={inv.id} className="px-4 py-3">
                      <div className="flex items-center justify-between">
                        <div>
                          <p className="text-sm font-medium text-[#1a2332]">{inv.invoice_number}</p>
                          <p className="text-xs text-muted-foreground">Issued {inv.issue_date} · Due {inv.due_date}</p>
                        </div>
                        <span className={`rounded px-2 py-0.5 text-xs font-medium ${STATUS_COLORS[inv.status] ?? "bg-gray-100 text-gray-600"}`}>
                          {inv.status}
                        </span>
                      </div>
                      <div className="mt-2 text-xs space-y-0.5">
                        <div className="flex justify-between text-muted-foreground">
                          <span>Invoice total</span>
                          <span className="font-mono">{total.toLocaleString("sv-SE", { minimumFractionDigits: 2 })} SEK</span>
                        </div>
                        {dep > 0 && (
                          <div className="flex justify-between text-green-600">
                            <span>Less deposit paid</span>
                            <span className="font-mono">-{dep.toLocaleString("sv-SE", { minimumFractionDigits: 2 })} SEK</span>
                          </div>
                        )}
                        <div className="flex justify-between font-semibold text-[#1a2332] border-t pt-1">
                          <span>Amount due</span>
                          <span className="font-mono">{due.toLocaleString("sv-SE", { minimumFractionDigits: 2 })} SEK</span>
                        </div>
                      </div>
                      <Link href={`/portal/invoices/${inv.id}`}
                        className="mt-2 inline-block text-xs text-blue-600 hover:underline">
                        View invoice →
                      </Link>
                    </div>
                  );
                })}
              </div>
            </section>
          )}
        </>
      )}
    </div>
  );
}
