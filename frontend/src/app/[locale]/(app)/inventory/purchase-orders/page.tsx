"use client";

import { api } from "@/lib/api-client";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import Link from "next/link";
import { useEffect, useState } from "react";
import { FileText, Plus } from "lucide-react";

interface PurchaseOrder {
  id: string; status: "DRAFT" | "SENT" | "RECEIVED"; total: string; notes: string | null;
  created_at: string; supplier: { name: string };
  items: { id: string; quantity: number; unit_price: string; line_total: string; product_id: string }[];
}

const STATUS_COLORS: Record<string, string> = {
  DRAFT: "bg-gray-100 text-gray-700",
  SENT: "bg-blue-100 text-blue-700",
  RECEIVED: "bg-green-100 text-green-700",
};

export default function PurchaseOrdersPage() {
  const [orders, setOrders] = useState<PurchaseOrder[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [updating, setUpdating] = useState<string | null>(null);

  async function load() {
    try { setOrders(await api.get<PurchaseOrder[]>("/api/inventory/purchase-orders")); }
    catch (e: any) { setError(e.message); }
    finally { setLoading(false); }
  }

  useEffect(() => { load(); }, []);

  async function advanceStatus(po: PurchaseOrder) {
    const next = po.status === "DRAFT" ? "SENT" : po.status === "SENT" ? "RECEIVED" : null;
    if (!next) return;
    setUpdating(po.id);
    try {
      await api.patch(`/api/inventory/purchase-orders/${po.id}/status`, { status: next });
      await load();
    } catch (e: any) { setError(e.message); } finally { setUpdating(null); }
  }

  function downloadPDF(id: string) {
    window.open(api.downloadUrl(`/api/inventory/purchase-orders/${id}/pdf`), "_blank");
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-[#1a2332]">Purchase Orders</h1>
          <p className="text-sm text-muted-foreground">{orders.length} orders</p>
        </div>
        <Button asChild size="sm" className="bg-[#1a2332] hover:bg-[#2a3342] text-white">
          <Link href="/inventory/purchase-orders/new">
            <Plus className="mr-1.5 h-3.5 w-3.5" />New order
          </Link>
        </Button>
      </div>

      {error && <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-2 text-sm text-red-700">{error}</div>}

      {loading ? (
        <div className="space-y-2 animate-pulse">{[1, 2, 3].map((i) => <div key={i} className="h-16 rounded-xl bg-gray-100" />)}</div>
      ) : orders.length === 0 ? (
        <div className="rounded-xl border bg-white px-6 py-12 text-center">
          <FileText className="mx-auto h-10 w-10 text-gray-300" />
          <h3 className="mt-3 font-medium text-gray-900">No purchase orders yet</h3>
          <p className="mt-1 text-sm text-muted-foreground">Create a PO to restock from a supplier.</p>
          <Button asChild size="sm" className="mt-4 bg-[#1a2332] hover:bg-[#2a3342] text-white">
            <Link href="/inventory/purchase-orders/new"><Plus className="mr-1.5 h-3.5 w-3.5" />New order</Link>
          </Button>
        </div>
      ) : (
        <div className="rounded-xl border bg-white overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-gray-50 text-xs text-gray-500 uppercase">
              <tr>
                <th className="px-4 py-3 text-left">PO #</th>
                <th className="px-4 py-3 text-left">Supplier</th>
                <th className="px-4 py-3 text-center">Status</th>
                <th className="px-4 py-3 text-right">Total (SEK)</th>
                <th className="px-4 py-3 text-left">Date</th>
                <th className="px-4 py-3 text-right" />
              </tr>
            </thead>
            <tbody className="divide-y">
              {orders.map((po) => (
                <tr key={po.id} className="hover:bg-gray-50">
                  <td className="px-4 py-3 font-mono text-xs">{po.id.slice(0, 8).toUpperCase()}</td>
                  <td className="px-4 py-3 font-medium">{po.supplier.name}</td>
                  <td className="px-4 py-3 text-center">
                    <span className={`rounded px-2 py-0.5 text-xs font-medium ${STATUS_COLORS[po.status]}`}>{po.status}</span>
                  </td>
                  <td className="px-4 py-3 text-right font-mono">{Number(po.total).toLocaleString("sv-SE", { minimumFractionDigits: 2 })}</td>
                  <td className="px-4 py-3 text-muted-foreground text-xs">{new Date(po.created_at).toLocaleDateString("sv-SE")}</td>
                  <td className="px-4 py-3">
                    <div className="flex justify-end gap-2">
                      <Button variant="ghost" size="sm" className="h-7 text-xs" onClick={() => downloadPDF(po.id)}>PDF</Button>
                      {po.status !== "RECEIVED" && (
                        <Button variant="outline" size="sm" className="h-7 text-xs" disabled={updating === po.id} onClick={() => advanceStatus(po)}>
                          {po.status === "DRAFT" ? "Mark Sent" : "Mark Received"}
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
