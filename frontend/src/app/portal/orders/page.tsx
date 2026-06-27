"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import {
  portalApi,
  PORTAL_TOKEN_KEY,
  PORTAL_CUSTOMER_KEY,
} from "@/lib/portal-client";

interface OrderHistoryItem {
  order_number: string;
  invoice_id: string;
  status: string;
  total_sek: string;
  created_at: string;
}

const STATUS_COLORS: Record<string, string> = {
  pending: "bg-amber-100 text-amber-800",
  confirmed: "bg-blue-100 text-blue-800",
  shipped: "bg-indigo-100 text-indigo-800",
  invoiced: "bg-green-100 text-green-800",
};

const STATUS_LABEL: Record<string, string> = {
  pending: "Väntar på bekräftelse",
  confirmed: "Bekräftad",
  shipped: "Skickad",
  invoiced: "Fakturerad",
};

export default function PortalOrdersPage() {
  const router = useRouter();
  const [orders, setOrders] = useState<OrderHistoryItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const token =
      typeof window !== "undefined" ? localStorage.getItem(PORTAL_TOKEN_KEY) : null;
    if (!token) {
      router.replace("/portal/login");
      return;
    }
    portalApi
      .get<OrderHistoryItem[]>("/api/portal/orders")
      .then(setOrders)
      .catch((e: Error) => setError(e.message))
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
        <h1 className="text-xl font-bold text-[#1a2332]">Orderhistorik</h1>
        <div className="flex gap-3 text-xs">
          <Link href="/portal/catalogue" className="underline text-muted-foreground">
            Katalog
          </Link>
          <Link href="/portal/invoices" className="underline text-muted-foreground">
            Fakturor
          </Link>
          <button
            onClick={handleSignOut}
            className="underline text-muted-foreground hover:text-gray-900"
          >
            Logga ut
          </button>
        </div>
      </div>

      {error && (
        <div className="rounded-xl border border-red-300 bg-red-50 p-3 text-sm text-red-700">
          {error}
        </div>
      )}

      {orders.length === 0 ? (
        <div className="rounded-xl border bg-white p-8 text-center text-sm text-muted-foreground">
          Inga ordrar ännu.{" "}
          <Link href="/portal/catalogue" className="underline">
            Gå till katalogen
          </Link>
          .
        </div>
      ) : (
        <div className="rounded-xl border bg-white overflow-hidden divide-y">
          {orders.map((o) => (
            <Link
              key={o.invoice_id}
              href={`/portal/invoices/${o.invoice_id}`}
              className="flex items-center justify-between px-5 py-4 hover:bg-gray-50 transition-colors"
            >
              <div className="space-y-0.5">
                <p className="text-sm font-semibold text-gray-900">{o.order_number}</p>
                <p className="text-xs text-muted-foreground">
                  {new Date(o.created_at).toLocaleDateString("sv-SE")}
                </p>
              </div>
              <div className="flex items-center gap-3">
                <span className="font-mono text-sm font-medium">
                  {Number(o.total_sek).toLocaleString("sv-SE", {
                    minimumFractionDigits: 2,
                  })}{" "}
                  SEK
                </span>
                <span
                  className={`rounded px-2 py-0.5 text-xs font-medium ${
                    STATUS_COLORS[o.status] ?? "bg-gray-100 text-gray-700"
                  }`}
                >
                  {STATUS_LABEL[o.status] ?? o.status}
                </span>
              </div>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
