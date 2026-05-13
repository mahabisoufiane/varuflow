"use client";
import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { portalApi, PORTAL_TOKEN_KEY } from "@/lib/portal-client";
import { toast } from "sonner";

interface Instalment { id: string; instalment_number: number; amount: number; due_date: string; status: string; }
interface PaymentPlanSummary { id: string; num_instalments: number; status: string; total_amount: number; }
interface EarlyDiscount { id: string; discount_pct: number; days_threshold: number; discounted_total: number; accepted_at: string | null; }
interface PaymentOptionsData {
  invoice_id: string;
  invoice_total: number;
  currency: string;
  available_payment_methods: string | null;
  payment_plans: PaymentPlanSummary[];
  early_discount: EarlyDiscount | null;
}

export default function PortalPaymentsPage() {
  const { invoice_id } = useParams<{ invoice_id: string }>();
  const router = useRouter();
  const [data, setData] = useState<PaymentOptionsData | null>(null);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [numInstalments, setNumInstalments] = useState(3);

  useEffect(() => {
    if (!localStorage.getItem(PORTAL_TOKEN_KEY)) { router.replace("/portal/login"); return; }
    portalApi.get<PaymentOptionsData>(`/api/portal/payments/${invoice_id}`)
      .then(setData)
      .catch(() => toast.error("Failed to load payment options"))
      .finally(() => setLoading(false));
  }, [invoice_id]);

  const acceptDiscount = async () => {
    if (!data) return;
    setSubmitting(true);
    try {
      const res = await portalApi.post<{ accepted: boolean; discounted_total: number }>(
        `/api/portal/payments/${invoice_id}/accept-discount`, {}
      );
      toast.success(`Discount accepted! New total: ${res.discounted_total.toLocaleString()} ${data.currency}`);
      setData(d => d ? { ...d, early_discount: d.early_discount ? { ...d.early_discount, accepted_at: new Date().toISOString() } : null } : d);
    } catch {
      toast.error("Failed to accept discount");
    } finally {
      setSubmitting(false);
    }
  };

  const requestPlan = async () => {
    if (!data) return;
    setSubmitting(true);
    try {
      const perInstalment = data.invoice_total / numInstalments;
      const today = new Date();
      const amounts = Array(numInstalments).fill(parseFloat(perInstalment.toFixed(2)));
      const dueDates = Array.from({ length: numInstalments }, (_, i) => {
        const d = new Date(today);
        d.setMonth(d.getMonth() + i + 1);
        return d.toISOString().slice(0, 10);
      });
      await portalApi.post(`/api/portal/payments/${invoice_id}/select-plan`, {
        invoice_id,
        num_instalments: numInstalments,
        instalment_amounts: amounts,
        instalment_due_dates: dueDates,
      });
      toast.success("Payment plan created");
      router.back();
    } catch {
      toast.error("Failed to create plan");
    } finally {
      setSubmitting(false);
    }
  };

  if (loading) return <div className="text-sm text-gray-500">Loading…</div>;
  if (!data) return <div className="text-sm text-red-500">Could not load payment options.</div>;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-bold">Payment Options</h1>
        <p className="text-sm text-gray-500">Invoice total: {data.invoice_total.toLocaleString()} {data.currency}</p>
      </div>

      {data.early_discount && (
        <div className="border rounded p-4 bg-green-50 space-y-2">
          <h2 className="font-semibold text-green-800">Early Payment Discount</h2>
          <p className="text-sm text-green-700">
            Pay within {data.early_discount.days_threshold} days and save {data.early_discount.discount_pct}%.
            New total: <strong>{data.early_discount.discounted_total.toLocaleString()} {data.currency}</strong>
          </p>
          {data.early_discount.accepted_at ? (
            <span className="text-xs font-medium text-green-600">✓ Accepted</span>
          ) : (
            <button
              onClick={acceptDiscount}
              disabled={submitting}
              className="px-3 py-1.5 bg-green-600 text-white text-sm rounded hover:bg-green-700 disabled:opacity-50"
            >
              Accept Discount
            </button>
          )}
        </div>
      )}

      {data.available_payment_methods && (
        <div className="border rounded p-4 space-y-1">
          <h2 className="font-semibold">Accepted Payment Methods</h2>
          <p className="text-sm text-gray-600">{data.available_payment_methods}</p>
        </div>
      )}

      <div className="border rounded p-4 space-y-3">
        <h2 className="font-semibold">Pay in Instalments</h2>
        {data.payment_plans.length > 0 ? (
          <div className="space-y-2">
            {data.payment_plans.map(p => (
              <div key={p.id} className="text-sm flex justify-between border-b pb-1">
                <span>{p.num_instalments} instalments — {p.total_amount.toLocaleString()} {data.currency}</span>
                <span className={`text-xs px-2 rounded ${p.status === "active" ? "bg-blue-100 text-blue-800" : "bg-gray-100"}`}>{p.status}</span>
              </div>
            ))}
          </div>
        ) : (
          <div className="space-y-2">
            <p className="text-sm text-gray-500">No plan set up yet. Choose number of instalments:</p>
            <div className="flex items-center gap-3">
              {[2, 3, 4, 6].map(n => (
                <button
                  key={n}
                  onClick={() => setNumInstalments(n)}
                  className={`px-3 py-1 border rounded text-sm ${numInstalments === n ? "bg-gray-900 text-white" : "hover:bg-gray-50"}`}
                >
                  {n}×
                </button>
              ))}
            </div>
            <p className="text-xs text-gray-400">
              ≈ {(data.invoice_total / numInstalments).toLocaleString(undefined, { maximumFractionDigits: 2 })} {data.currency} / month
            </p>
            <button
              onClick={requestPlan}
              disabled={submitting}
              className="px-4 py-2 bg-[#1a2332] text-white text-sm rounded hover:opacity-90 disabled:opacity-50"
            >
              Request Plan
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
