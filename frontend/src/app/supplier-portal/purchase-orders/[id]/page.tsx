"use client";

// Supplier Portal — Purchase Order detail + confirm (Item 37).

import Link from "next/link";
import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { supplierPortalApi } from "@/lib/supplier-portal-client";

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

export default function PurchaseOrderDetailPage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const id = params.id;

  const [po, setPo] = useState<PurchaseOrder | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [confirming, setConfirming] = useState(false);

  useEffect(() => {
    if (!id) return;
    supplierPortalApi
      .get<PurchaseOrder>(`/api/supplier-portal/purchase-orders/${id}`)
      .then(setPo)
      .catch((e) => setError(e.message));
  }, [id]);

  async function handleConfirm() {
    if (!id || !po || po.confirmed_at) return;
    setConfirming(true);
    try {
      await supplierPortalApi.post(`/api/supplier-portal/purchase-orders/${id}/confirm`);
      // Re-fetch so the detail + header update with the stamped
      // timestamp.
      const updated = await supplierPortalApi.get<PurchaseOrder>(
        `/api/supplier-portal/purchase-orders/${id}`,
      );
      setPo(updated);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setConfirming(false);
    }
  }

  if (error) {
    return (
      <div className="rounded-xl border bg-white p-6 text-center space-y-3">
        <h2 className="text-lg font-semibold text-gray-900">Could not load order</h2>
        <p className="text-sm text-muted-foreground">{error}</p>
        <Link
          href="/supplier-portal/purchase-orders"
          className="inline-block text-sm text-[#1a2332] underline"
        >
          Back to list
        </Link>
      </div>
    );
  }

  if (!po) return <div className="text-sm text-muted-foreground">Loading…</div>;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-gray-900">
            PO · {po.id.slice(0, 8)}
          </h1>
          <p className="text-xs text-muted-foreground mt-0.5">
            {new Date(po.created_at).toLocaleDateString()} · Status: {po.status}
          </p>
        </div>
        <Link
          href="/supplier-portal/purchase-orders"
          className="text-xs text-[#1a2332] underline"
        >
          Back
        </Link>
      </div>

      <div className="rounded-xl border bg-white overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-gray-50 border-b">
            <tr>
              <th className="px-4 py-2 text-left text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">
                Product
              </th>
              <th className="px-4 py-2 text-right text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">
                Qty
              </th>
              <th className="px-4 py-2 text-right text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">
                Unit price
              </th>
              <th className="px-4 py-2 text-right text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">
                Line total
              </th>
            </tr>
          </thead>
          <tbody>
            {po.items.map((it) => (
              <tr key={it.id} className="border-b last:border-0">
                <td className="px-4 py-3 font-mono text-xs text-gray-600">
                  {it.product_id.slice(0, 8)}…
                </td>
                <td className="px-4 py-3 text-right tabular-nums">{it.quantity}</td>
                <td className="px-4 py-3 text-right tabular-nums">{it.unit_price}</td>
                <td className="px-4 py-3 text-right tabular-nums font-medium">
                  {it.line_total}
                </td>
              </tr>
            ))}
          </tbody>
          <tfoot className="bg-gray-50 border-t">
            <tr>
              <td colSpan={3} className="px-4 py-2 text-right text-xs font-semibold">
                Total
              </td>
              <td className="px-4 py-2 text-right text-sm font-bold tabular-nums">
                {po.total}
              </td>
            </tr>
          </tfoot>
        </table>
      </div>

      {po.notes && (
        <div className="rounded-xl border bg-white p-4 text-sm">
          <p className="text-[11px] font-semibold uppercase tracking-wide text-muted-foreground mb-1">
            Notes
          </p>
          <p className="text-gray-700 whitespace-pre-line">{po.notes}</p>
        </div>
      )}

      {/* ── Confirmation CTA ─────────────────────────────────────── */}
      <div className="rounded-xl border bg-white p-5 flex items-center justify-between gap-4">
        {po.confirmed_at ? (
          <div>
            <p className="text-sm font-semibold text-emerald-700">
              Confirmed
            </p>
            <p className="text-xs text-muted-foreground">
              {new Date(po.confirmed_at).toLocaleString()}
            </p>
          </div>
        ) : (
          <div>
            <p className="text-sm font-semibold text-gray-900">Accept this order</p>
            <p className="text-xs text-muted-foreground">
              By confirming, you accept the lines and pricing above.
            </p>
          </div>
        )}
        <button
          type="button"
          onClick={handleConfirm}
          disabled={po.confirmed_at !== null || confirming}
          className="rounded-lg bg-[#1a2332] px-4 py-2 text-sm font-semibold text-white hover:bg-[#2a3342] disabled:cursor-not-allowed disabled:bg-gray-300"
        >
          {po.confirmed_at ? "Already confirmed" : confirming ? "Confirming…" : "Confirm order"}
        </button>
      </div>
    </div>
  );
}
