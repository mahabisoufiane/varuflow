"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { portalApi, PORTAL_TOKEN_KEY, PORTAL_CUSTOMER_KEY } from "@/lib/portal-client";

interface InvoiceSummary {
  id: string;
  invoice_number: string;
  issue_date: string;
  due_date: string;
  status: string;
  total_sek: string;
  customer: { company_name: string };
}

const STATUS_COLORS: Record<string, string> = {
  SENT: "bg-blue-100 text-blue-700",
  PAID: "bg-green-100 text-green-700",
  OVERDUE: "bg-red-100 text-red-700",
};

export default function PortalInvoicesPage() {
  const router = useRouter();
  const [invoices, setInvoices] = useState<InvoiceSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [customerName, setCustomerName] = useState("");
  const [orgName, setOrgName] = useState("");

  useEffect(() => {
    const token = localStorage.getItem(PORTAL_TOKEN_KEY);
    if (!token) { router.replace("/portal/login"); return; }

    const info = localStorage.getItem(PORTAL_CUSTOMER_KEY);
    if (info) {
      const parsed = JSON.parse(info);
      setCustomerName(parsed.customer_name ?? "");
      setOrgName(parsed.org_name ?? "");
    }

    portalApi
      .get<InvoiceSummary[]>("/api/portal/invoices")
      .then(setInvoices)
      .catch(() => router.replace("/portal/login"))
      .finally(() => setLoading(false));
  }, [router]);

  function handleSignOut() {
    localStorage.removeItem(PORTAL_TOKEN_KEY);
    localStorage.removeItem(PORTAL_CUSTOMER_KEY);
    router.push("/portal/login");
  }

  if (loading) {
    return (
      <div className="space-y-3">
        {[1, 2, 3].map((i) => (
          <div key={i} className="h-16 rounded-xl bg-gray-100 animate-pulse" />
        ))}
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-xl font-bold text-[#1a2332]">Your invoices</h1>
          {customerName && (
            <p className="mt-0.5 text-sm text-muted-foreground">
              {customerName}{orgName ? ` · ${orgName}` : ""}
            </p>
          )}
        </div>
        <button
          onClick={handleSignOut}
          className="text-xs text-muted-foreground hover:text-gray-900 underline"
        >
          Sign out
        </button>
      </div>

      {invoices.length === 0 ? (
        <div className="rounded-xl border bg-white p-8 text-center text-sm text-muted-foreground">
          No invoices found.
        </div>
      ) : (
        <div className="rounded-xl border bg-white overflow-hidden divide-y">
          {invoices.map((inv) => (
            <Link
              key={inv.id}
              href={`/portal/invoices/${inv.id}`}
              className="flex items-center justify-between px-5 py-4 hover:bg-gray-50 transition-colors"
            >
              <div className="space-y-0.5">
                <p className="text-sm font-semibold text-gray-900">{inv.invoice_number}</p>
                <p className="text-xs text-muted-foreground">Due {inv.due_date}</p>
              </div>
              <div className="flex items-center gap-3">
                <span className="font-mono text-sm font-medium">
                  {Number(inv.total_sek).toLocaleString("sv-SE", { minimumFractionDigits: 2 })} SEK
                </span>
                <span className={`rounded px-2 py-0.5 text-xs font-medium ${STATUS_COLORS[inv.status] ?? "bg-gray-100 text-gray-700"}`}>
                  {inv.status}
                </span>
              </div>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
