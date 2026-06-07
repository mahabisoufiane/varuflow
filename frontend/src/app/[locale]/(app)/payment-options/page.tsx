"use client";
import { useEffect, useState } from "react";
import { useTranslations } from "next-intl";
import { api } from "@/lib/api-client";
import styles from "./page.module.scss";
import { toast } from "sonner";

interface Plan {
  id: string;
  invoice_id: string;
  customer_id: string;
  total_amount: number;
  currency: string;
  num_instalments: number;
  status: string;
  created_at: string;
  instalments: { id: string; instalment_number: number; amount: number; due_date: string; status: string; paid_at: string | null }[];
}

export default function PaymentOptionsPage() {
  const [plans, setPlans] = useState<Plan[]>([]);
  const [loading, setLoading] = useState(true);

  const load = () => {
    api.get<Plan[]>("/api/payment-options/plans")
      .then(setPlans)
      .catch(() => toast.error("Failed to load payment plans"))
      .finally(() => setLoading(false));
  };

  useEffect(() => { load(); }, []);

  const markPaid = async (planId: string, instId: string) => {
    try {
      await api.patch(`/api/payment-options/plans/${planId}/instalments/${instId}`, {});
      toast.success("Instalment marked as paid");
      load();
    } catch {
      toast.error("Failed to update instalment");
    }
  };

  return (
    <div className="space-y-6 p-6">
      <h1 className="text-2xl font-bold">Payment Plans</h1>
      {loading && <p className="text-sm text-gray-500">Loading…</p>}
      {!loading && plans.length === 0 && <p className="text-sm text-gray-500">No payment plans yet.</p>}
      <div className="space-y-4">
        {plans.map(plan => (
          <div key={plan.id} className="border rounded p-4 space-y-2 bg-white">
            <div className="flex justify-between items-start">
              <div>
                <p className="font-medium text-sm">{plan.num_instalments} instalments — {plan.total_amount.toLocaleString()} {plan.currency}</p>
                <p className="text-xs text-gray-400">Invoice {plan.invoice_id.slice(0, 8)}… · Created {new Date(plan.created_at).toLocaleDateString()}</p>
              </div>
              <span className={styles[plan.status === "active" ? "planActive" : "planInactive"]}>{plan.status}</span>
            </div>
            <table className="w-full text-xs border-t pt-2">
              <thead>
                <tr className="text-gray-500">
                  <th className="text-left py-1">#</th>
                  <th className="text-left py-1">Amount</th>
                  <th className="text-left py-1">Due</th>
                  <th className="text-left py-1">Status</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {plan.instalments.map(inst => (
                  <tr key={inst.id} className="border-t">
                    <td className="py-1">{inst.instalment_number}</td>
                    <td className="py-1">{inst.amount.toLocaleString()} {plan.currency}</td>
                    <td className="py-1">{inst.due_date}</td>
                    <td className="py-1">
                      <span className={styles[inst.status === "paid" ? "installPaid" : "installPending"]}>{inst.status}</span>
                    </td>
                    <td className="py-1">
                      {inst.status !== "paid" && (
                        <button
                          onClick={() => markPaid(plan.id, inst.id)}
                          className="text-xs text-blue-600 hover:underline"
                        >
                          Mark paid
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ))}
      </div>
    </div>
  );
}
