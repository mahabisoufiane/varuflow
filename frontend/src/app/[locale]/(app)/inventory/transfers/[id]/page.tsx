"use client";

import { api } from "@/lib/api-client";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { useParams, useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";
import { Truck, ArrowLeft, Send, PackageCheck, Ban } from "lucide-react";

interface TransferItem {
  id: string;
  product_id: string;
  batch_id: string | null;
  qty_requested: number;
  qty_shipped: number;
  qty_received: number;
}

interface Transfer {
  id: string;
  from_warehouse_id: string;
  to_warehouse_id: string;
  status: "DRAFT" | "IN_TRANSIT" | "PARTIAL" | "RECEIVED" | "CANCELLED";
  notes: string | null;
  created_at: string;
  shipped_at: string | null;
  received_at: string | null;
  cancelled_at: string | null;
  items: TransferItem[];
}

const STATUS_COLORS: Record<Transfer["status"], string> = {
  DRAFT: "bg-gray-100 text-gray-700",
  IN_TRANSIT: "bg-blue-100 text-blue-700",
  PARTIAL: "bg-amber-100 text-amber-700",
  RECEIVED: "bg-green-100 text-green-700",
  CANCELLED: "bg-red-100 text-red-700",
};

export default function TransferDetailPage() {
  const params = useParams();
  const router = useRouter();
  const id = String(params?.id ?? "");
  const [t, setT] = useState<Transfer | null>(null);
  const [busy, setBusy] = useState<"ship" | "receive" | "cancel" | null>(null);

  const load = useCallback(async () => {
    try {
      const row = await api.get<Transfer>(`/api/stock-transfers/${id}`);
      setT(row);
    } catch (e: any) {
      toast.error(e.message);
    }
  }, [id]);

  useEffect(() => {
    if (id) load();
  }, [id, load]);

  async function runAction(
    action: "ship" | "receive" | "cancel",
    body: object = {},
  ) {
    setBusy(action);
    try {
      await api.post(`/api/stock-transfers/${id}/${action}`, body);
      toast.success(`Transfer ${action}ed`);
      await load();
    } catch (e: any) {
      toast.error(e.message);
    } finally {
      setBusy(null);
    }
  }

  if (!t) {
    return <div className="text-sm text-gray-500">Loading…</div>;
  }

  const canShip = t.status === "DRAFT";
  const canReceive = t.status === "IN_TRANSIT" || t.status === "PARTIAL";
  const canCancel = t.status === "DRAFT";

  const totalRequested = t.items.reduce((n, i) => n + i.qty_requested, 0);
  const totalShipped = t.items.reduce((n, i) => n + i.qty_shipped, 0);
  const totalReceived = t.items.reduce((n, i) => n + i.qty_received, 0);

  return (
    <div className="space-y-6 max-w-4xl">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Button variant="ghost" size="sm" onClick={() => router.back()}>
            <ArrowLeft className="h-4 w-4" />
          </Button>
          <div>
            <h1 className="text-2xl font-bold text-[#1a2332] flex items-center gap-2">
              <Truck className="h-5 w-5" /> Stock transfer
            </h1>
            <p className="text-xs text-gray-500 font-mono">{t.id}</p>
          </div>
        </div>
        <Badge className={STATUS_COLORS[t.status]}>{t.status}</Badge>
      </div>

      <div className="rounded-xl border bg-white p-4 space-y-3">
        <div className="grid grid-cols-2 gap-4 text-sm">
          <div>
            <div className="text-xs uppercase text-gray-500">From</div>
            <div className="font-mono">{t.from_warehouse_id}</div>
          </div>
          <div>
            <div className="text-xs uppercase text-gray-500">To</div>
            <div className="font-mono">{t.to_warehouse_id}</div>
          </div>
          <div>
            <div className="text-xs uppercase text-gray-500">Created</div>
            <div>{new Date(t.created_at).toLocaleString()}</div>
          </div>
          <div>
            <div className="text-xs uppercase text-gray-500">Shipped</div>
            <div>{t.shipped_at ? new Date(t.shipped_at).toLocaleString() : "—"}</div>
          </div>
          <div>
            <div className="text-xs uppercase text-gray-500">Received</div>
            <div>
              {t.received_at ? new Date(t.received_at).toLocaleString() : "—"}
            </div>
          </div>
          <div>
            <div className="text-xs uppercase text-gray-500">Cancelled</div>
            <div>
              {t.cancelled_at ? new Date(t.cancelled_at).toLocaleString() : "—"}
            </div>
          </div>
        </div>
        {t.notes && (
          <div className="border-t pt-2 text-sm">
            <div className="text-xs uppercase text-gray-500 mb-1">Notes</div>
            <div>{t.notes}</div>
          </div>
        )}
      </div>

      <div className="rounded-xl border bg-white overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-gray-50 text-xs uppercase text-gray-500">
            <tr>
              <th className="px-4 py-2 text-left">Product</th>
              <th className="px-4 py-2 text-left">Batch</th>
              <th className="px-4 py-2 text-right">Requested</th>
              <th className="px-4 py-2 text-right">Shipped</th>
              <th className="px-4 py-2 text-right">Received</th>
            </tr>
          </thead>
          <tbody>
            {t.items.map((i) => (
              <tr key={i.id} className="border-t">
                <td className="px-4 py-2 font-mono text-xs">
                  {i.product_id.slice(0, 8)}…
                </td>
                <td className="px-4 py-2 font-mono text-xs">
                  {i.batch_id ? i.batch_id.slice(0, 8) + "…" : "—"}
                </td>
                <td className="px-4 py-2 text-right tabular-nums">
                  {i.qty_requested}
                </td>
                <td className="px-4 py-2 text-right tabular-nums">
                  {i.qty_shipped}
                </td>
                <td className="px-4 py-2 text-right tabular-nums">
                  {i.qty_received}
                </td>
              </tr>
            ))}
            <tr className="border-t bg-gray-50 font-medium">
              <td colSpan={2} className="px-4 py-2 text-right">
                Totals
              </td>
              <td className="px-4 py-2 text-right tabular-nums">
                {totalRequested}
              </td>
              <td className="px-4 py-2 text-right tabular-nums">
                {totalShipped}
              </td>
              <td className="px-4 py-2 text-right tabular-nums">
                {totalReceived}
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      <div className="flex gap-2">
        {canShip && (
          <Button
            onClick={() => runAction("ship")}
            disabled={busy !== null}
            className="bg-[#1a2332] hover:bg-[#2a3342] text-white"
          >
            <Send className="mr-1.5 h-3.5 w-3.5" />
            {busy === "ship" ? "Shipping…" : "Ship"}
          </Button>
        )}
        {canReceive && (
          <Button
            onClick={() => runAction("receive")}
            disabled={busy !== null}
            className="bg-green-600 hover:bg-green-700 text-white"
          >
            <PackageCheck className="mr-1.5 h-3.5 w-3.5" />
            {busy === "receive" ? "Receiving…" : "Receive all"}
          </Button>
        )}
        {canCancel && (
          <Button
            variant="outline"
            onClick={() => runAction("cancel")}
            disabled={busy !== null}
          >
            <Ban className="mr-1.5 h-3.5 w-3.5" />
            {busy === "cancel" ? "Cancelling…" : "Cancel"}
          </Button>
        )}
      </div>
    </div>
  );
}
