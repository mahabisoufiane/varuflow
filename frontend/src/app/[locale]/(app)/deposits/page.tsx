"use client";
import { useEffect, useState } from "react";
import { api } from "@/lib/api-client";
import { toast } from "sonner";

interface Deposit {
  id: string;
  customer_id: string;
  invoice_id: string | null;
  quote_id: string | null;
  amount: number;
  currency: string;
  status: string;
  payment_method: string | null;
  paid_at: string | null;
  created_at: string;
}

const STATUS_COLORS: Record<string, string> = {
  pending: "bg-yellow-100 text-yellow-800",
  paid: "bg-green-100 text-green-800",
  cancelled: "bg-gray-100 text-gray-500",
};

export default function DepositsPage() {
  const [deposits, setDeposits] = useState<Deposit[]>([]);
  const [loading, setLoading] = useState(true);

  const load = () => {
    api.get<Deposit[]>("/api/payment-options/deposits")
      .then(setDeposits)
      .catch(() => toast.error("Failed to load deposits"))
      .finally(() => setLoading(false));
  };

  useEffect(() => { load(); }, []);

  const markPaid = async (id: string) => {
    try {
      await api.patch(`/api/payment-options/deposits/${id}`, { status: "paid" });
      toast.success("Deposit marked as paid");
      load();
    } catch {
      toast.error("Failed to update deposit");
    }
  };

  return (
    <div className="space-y-6 p-6">
      <h1 className="text-2xl font-bold">Deposit Requests</h1>
      {loading && <p className="text-sm text-gray-500">Loading…</p>}
      {!loading && deposits.length === 0 && <p className="text-sm text-gray-500">No deposit requests.</p>}
      <div className="overflow-x-auto">
        <table className="w-full text-sm border rounded bg-white">
          <thead className="bg-gray-50 text-xs text-gray-500 uppercase">
            <tr>
              <th className="text-left px-4 py-2">Customer</th>
              <th className="text-left px-4 py-2">Amount</th>
              <th className="text-left px-4 py-2">Status</th>
              <th className="text-left px-4 py-2">Created</th>
              <th className="text-left px-4 py-2">Paid</th>
              <th />
            </tr>
          </thead>
          <tbody className="divide-y">
            {deposits.map(d => (
              <tr key={d.id} className="hover:bg-gray-50">
                <td className="px-4 py-2 text-xs text-gray-500">{d.customer_id.slice(0, 8)}…</td>
                <td className="px-4 py-2 font-medium">{d.amount.toLocaleString()} {d.currency}</td>
                <td className="px-4 py-2">
                  <span className={`px-2 py-0.5 rounded text-xs font-medium ${STATUS_COLORS[d.status] || "bg-gray-100"}`}>{d.status}</span>
                </td>
                <td className="px-4 py-2 text-xs">{new Date(d.created_at).toLocaleDateString()}</td>
                <td className="px-4 py-2 text-xs">{d.paid_at ? new Date(d.paid_at).toLocaleDateString() : "—"}</td>
                <td className="px-4 py-2">
                  {d.status === "pending" && (
                    <button onClick={() => markPaid(d.id)} className="text-xs text-blue-600 hover:underline">
                      Mark paid
                    </button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
