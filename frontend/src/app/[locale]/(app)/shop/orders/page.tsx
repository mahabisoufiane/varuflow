"use client";

import { useCallback, useEffect, useState } from "react";
import { ShoppingBag, Loader2, Package, CheckCircle, XCircle, Truck } from "lucide-react";
import { toast } from "sonner";
import { api } from "@/lib/api-client";

interface OrderItem {
  id: string;
  description: string;
  quantity: number;
  unit_price: string;
  line_total: string;
}

interface Order {
  id: string;
  order_number: string;
  status: string;
  customer_name: string;
  customer_email: string;
  total: string;
  shipping_carrier: string | null;
  tracking_number: string | null;
  tracking_url: string | null;
  confirmed_at: string | null;
  shipped_at: string | null;
  cancelled_at: string | null;
  created_at: string;
  items: OrderItem[];
}

const STATUS_COLORS: Record<string, string> = {
  PENDING: "bg-yellow-100 text-yellow-800",
  CONFIRMED: "bg-blue-100 text-blue-800",
  SHIPPED: "bg-purple-100 text-purple-800",
  DELIVERED: "bg-green-100 text-green-800",
  CANCELLED: "bg-gray-100 text-gray-600",
  REFUNDED: "bg-red-100 text-red-800",
};

const STATUSES = ["ALL", "PENDING", "CONFIRMED", "SHIPPED", "DELIVERED", "CANCELLED"];

export default function OnlineOrdersPage() {
  const [orders, setOrders] = useState<Order[]>([]);
  const [loading, setLoading] = useState(true);
  const [statusFilter, setStatusFilter] = useState("ALL");
  const [selected, setSelected] = useState<Order | null>(null);
  const [actionLoading, setActionLoading] = useState<string | null>(null);
  const [carrier, setCarrier] = useState("POSTNORD");

  const load = useCallback(async (status?: string) => {
    setLoading(true);
    try {
      const params = status && status !== "ALL" ? `?status=${status}&per_page=100` : "?per_page=100";
      const data = await api.get(`/api/shop/orders${params}`);
      setOrders(data.items ?? []);
    } catch {
      toast.error("Failed to load orders");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load(statusFilter);
  }, [statusFilter, load]);

  const handleConfirm = async (order: Order) => {
    setActionLoading("confirm");
    try {
      const updated = await api.post(`/api/shop/orders/${order.id}/confirm`, {});
      setOrders((prev) => prev.map((o) => (o.id === updated.id ? updated : o)));
      setSelected(updated);
      toast.success(`Order ${order.order_number} confirmed`);
    } catch {
      toast.error("Failed to confirm order");
    } finally {
      setActionLoading(null);
    }
  };

  const handleShip = async (order: Order) => {
    setActionLoading("ship");
    try {
      const updated = await api.post(`/api/shop/orders/${order.id}/ship`, { carrier });
      setOrders((prev) => prev.map((o) => (o.id === updated.id ? updated : o)));
      setSelected(updated);
      toast.success(`Order ${order.order_number} marked as shipped`);
      if (updated.label_pdf_base64) {
        const link = document.createElement("a");
        link.href = `data:application/pdf;base64,${updated.label_pdf_base64}`;
        link.download = `label-${order.order_number}.pdf`;
        link.click();
      }
    } catch {
      toast.error("Failed to ship order");
    } finally {
      setActionLoading(null);
    }
  };

  const handleCancel = async (order: Order) => {
    if (!confirm(`Cancel order ${order.order_number}? This will issue a Stripe refund if applicable.`)) return;
    setActionLoading("cancel");
    try {
      const updated = await api.post(`/api/shop/orders/${order.id}/cancel`, {});
      setOrders((prev) => prev.map((o) => (o.id === updated.id ? updated : o)));
      setSelected(updated);
      toast.success(`Order ${order.order_number} cancelled`);
    } catch {
      toast.error("Failed to cancel order");
    } finally {
      setActionLoading(null);
    }
  };

  // KPI bar
  const todayStr = new Date().toISOString().slice(0, 10);
  const ordersToday = orders.filter((o) => o.created_at.startsWith(todayStr)).length;
  const revenueToday = orders
    .filter((o) => o.created_at.startsWith(todayStr) && !["CANCELLED", "REFUNDED"].includes(o.status))
    .reduce((s, o) => s + parseFloat(o.total), 0);
  const pendingCount = orders.filter((o) => o.status === "PENDING").length;

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center gap-3">
        <ShoppingBag className="h-6 w-6 text-gray-600" />
        <h1 className="text-2xl font-semibold">Online Orders</h1>
      </div>

      {/* KPI bar */}
      <div className="grid grid-cols-3 gap-4">
        {[
          { label: "Orders today", value: ordersToday },
          { label: "Revenue today", value: `${revenueToday.toFixed(0)} kr` },
          { label: "Pending", value: pendingCount },
        ].map((kpi) => (
          <div key={kpi.label} className="border rounded-xl bg-white p-4">
            <p className="text-xs text-gray-500">{kpi.label}</p>
            <p className="text-2xl font-bold mt-1">{kpi.value}</p>
          </div>
        ))}
      </div>

      {/* Status tabs */}
      <div className="flex gap-2 flex-wrap">
        {STATUSES.map((s) => (
          <button
            key={s}
            onClick={() => setStatusFilter(s)}
            className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-colors ${
              statusFilter === s
                ? "bg-gray-900 text-white"
                : "bg-gray-100 text-gray-600 hover:bg-gray-200"
            }`}
          >
            {s}
          </button>
        ))}
      </div>

      {/* Table */}
      <div className="border rounded-xl overflow-hidden bg-white">
        {loading ? (
          <div className="flex items-center justify-center py-16">
            <Loader2 className="h-6 w-6 animate-spin text-gray-400" />
          </div>
        ) : orders.length === 0 ? (
          <div className="text-center py-16 text-gray-400 text-sm">No orders found</div>
        ) : (
          <table className="w-full text-sm">
            <thead className="border-b bg-gray-50">
              <tr>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500">Order</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500">Customer</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500">Total</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500">Status</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500">Date</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y">
              {orders.map((o) => (
                <tr
                  key={o.id}
                  className={`hover:bg-gray-50 cursor-pointer ${selected?.id === o.id ? "bg-blue-50" : ""}`}
                  onClick={() => setSelected(o)}
                >
                  <td className="px-4 py-3 font-mono text-xs">{o.order_number}</td>
                  <td className="px-4 py-3">
                    <p className="font-medium">{o.customer_name}</p>
                    <p className="text-xs text-gray-400">{o.customer_email}</p>
                  </td>
                  <td className="px-4 py-3 font-medium">{parseFloat(o.total).toFixed(2)}</td>
                  <td className="px-4 py-3">
                    <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${STATUS_COLORS[o.status] ?? "bg-gray-100"}`}>
                      {o.status}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-xs text-gray-500">
                    {new Date(o.created_at).toLocaleDateString()}
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex gap-1" onClick={(e) => e.stopPropagation()}>
                      {o.status === "PENDING" && (
                        <button
                          onClick={() => handleConfirm(o)}
                          disabled={!!actionLoading}
                          title="Confirm"
                          className="p-1.5 rounded hover:bg-green-50 text-green-600 disabled:opacity-50"
                        >
                          <CheckCircle className="h-4 w-4" />
                        </button>
                      )}
                      {(o.status === "CONFIRMED" || o.status === "PENDING") && (
                        <button
                          onClick={() => { setSelected(o); }}
                          title="Ship"
                          className="p-1.5 rounded hover:bg-purple-50 text-purple-600"
                        >
                          <Truck className="h-4 w-4" />
                        </button>
                      )}
                      {!["CANCELLED", "REFUNDED", "DELIVERED"].includes(o.status) && (
                        <button
                          onClick={() => handleCancel(o)}
                          disabled={!!actionLoading}
                          title="Cancel"
                          className="p-1.5 rounded hover:bg-red-50 text-red-600 disabled:opacity-50"
                        >
                          <XCircle className="h-4 w-4" />
                        </button>
                      )}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {/* Order detail panel */}
      {selected && (
        <div className="border rounded-xl bg-white p-6 space-y-4">
          <div className="flex items-start justify-between">
            <div>
              <h2 className="font-semibold text-lg">{selected.order_number}</h2>
              <p className="text-sm text-gray-500">{selected.customer_name} · {selected.customer_email}</p>
            </div>
            <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${STATUS_COLORS[selected.status] ?? "bg-gray-100"}`}>
              {selected.status}
            </span>
          </div>

          {/* Line items */}
          <table className="w-full text-sm">
            <thead className="text-xs text-gray-500 border-b">
              <tr>
                <th className="text-left pb-2">Item</th>
                <th className="text-right pb-2">Qty</th>
                <th className="text-right pb-2">Price</th>
                <th className="text-right pb-2">Total</th>
              </tr>
            </thead>
            <tbody>
              {(selected.items ?? []).map((it) => (
                <tr key={it.id} className="border-b last:border-0">
                  <td className="py-2">{it.description}</td>
                  <td className="text-right py-2">{it.quantity}</td>
                  <td className="text-right py-2">{parseFloat(it.unit_price).toFixed(2)}</td>
                  <td className="text-right py-2 font-medium">{parseFloat(it.line_total).toFixed(2)}</td>
                </tr>
              ))}
            </tbody>
          </table>

          {/* Ship action */}
          {(selected.status === "CONFIRMED" || selected.status === "PENDING") && (
            <div className="border rounded-lg p-4 space-y-3 bg-gray-50">
              <h3 className="text-sm font-medium">Ship this order</h3>
              <div className="flex gap-3 items-center">
                <select
                  value={carrier}
                  onChange={(e) => setCarrier(e.target.value)}
                  className="border rounded-lg px-3 py-2 text-sm"
                >
                  <option value="POSTNORD">PostNord</option>
                  <option value="DHL">DHL</option>
                  <option value="UPS">UPS</option>
                </select>
                <button
                  onClick={() => handleShip(selected)}
                  disabled={!!actionLoading}
                  className="flex items-center gap-2 px-4 py-2 rounded-lg bg-gray-900 text-white text-sm font-medium hover:bg-gray-700 disabled:opacity-50 transition-colors"
                >
                  {actionLoading === "ship" ? (
                    <Loader2 className="h-4 w-4 animate-spin" />
                  ) : (
                    <Truck className="h-4 w-4" />
                  )}
                  Ship & generate label
                </button>
              </div>
            </div>
          )}

          {/* Tracking info */}
          {selected.tracking_number && (
            <div className="text-sm space-y-1">
              <p><span className="text-gray-500">Carrier:</span> {selected.shipping_carrier}</p>
              <p><span className="text-gray-500">Tracking:</span>{" "}
                {selected.tracking_url ? (
                  <a href={selected.tracking_url} target="_blank" rel="noopener noreferrer" className="text-blue-600 underline">
                    {selected.tracking_number}
                  </a>
                ) : selected.tracking_number}
              </p>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
