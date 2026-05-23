"use client";

// Supplier Portal — Purchase Orders list (Item 37).

import Link from "next/link";
import { useEffect, useState } from "react";
import { supplierPortalApi, SUPPLIER_PORTAL_ME_KEY } from "@/lib/supplier-portal-client";

interface POLine {
  id: string;
  product_id: string;
  quantity: number;
  unit_price: string;
  line_total: string;
}

interface PurchaseOrder {
  id: string;
  status: string;
  total: string;
  notes: string | null;
  created_at: string;
  confirmed_at: string | null;
  items: POLine[];
}

export default function PurchaseOrdersPage() {
  const [orders, setOrders] = useState<PurchaseOrder[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [supplierName, setSupplierName] = useState<string>("");

  useEffect(() => {
    try {
      const me = localStorage.getItem(SUPPLIER_PORTAL_ME_KEY);
      if (me) setSupplierName(JSON.parse(me).supplier_name ?? "");
    } catch {
      // Ignore; header just shows "Supplier".
    }
    supplierPortalApi
      .get<PurchaseOrder[]>("/api/supplier-portal/purchase-orders")
      .then(setOrders)
      .catch((e) => setError(e.message));
  }, []);

  if (error) {
    return (
      <div className="rounded-xl border bg-white p-6 text-center space-y-2">
        <h2 className="text-lg font-semibold text-gray-900">Could not load orders</h2>
        <p className="text-sm text-muted-foreground">{error}</p>
      </div>
    );
  }

  if (orders === null) {
    return <div className="text-sm text-muted-foreground">Loading…</div>;
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-semibold text-gray-900">Purchase orders</h1>
        <p className="text-xs text-muted-foreground mt-0.5">
          {supplierName || "Supplier"} — read-only view
        </p>
      </div>

      {orders.length === 0 ? (
        <div className="rounded-xl border bg-white p-8 text-center">
          <p className="text-sm text-muted-foreground">No purchase orders yet.</p>
        </div>
      ) : (
        <ul className="space-y-3">
          {orders.map((po) => (
            <li
              key={po.id}
              className="rounded-xl border bg-white p-4 flex items-center justify-between gap-3"
            >
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2">
                  <span className="font-semibold text-gray-900">
                    PO · {po.id.slice(0, 8)}
                  </span>
                  <StatusBadge status={po.status} confirmed={po.confirmed_at !== null} />
                </div>
                <p className="text-xs text-muted-foreground mt-0.5">
                  {new Date(po.created_at).toLocaleDateString()} · {po.items.length} line(s) ·{" "}
                  {po.total}
                </p>
              </div>
              <Link
                href={`/supplier-portal/purchase-orders/${po.id}`}
                className="rounded-lg bg-[#1a2332] px-3 py-1.5 text-xs font-semibold text-white hover:bg-[#2a3342]"
              >
                View
              </Link>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function StatusBadge({ status, confirmed }: { status: string; confirmed: boolean }) {
  if (confirmed) {
    return (
      <span className="rounded-full bg-emerald-100 px-2 py-0.5 text-[10px] font-semibold text-emerald-700">
        Confirmed
      </span>
    );
  }
  if (status === "SENT") {
    return (
      <span className="rounded-full bg-amber-100 px-2 py-0.5 text-[10px] font-semibold text-amber-700">
        Awaiting confirmation
      </span>
    );
  }
  return (
    <span className="rounded-full bg-gray-100 px-2 py-0.5 text-[10px] font-semibold text-gray-700">
      {status}
    </span>
  );
}
