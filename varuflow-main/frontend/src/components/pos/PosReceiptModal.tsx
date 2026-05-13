"use client";

/** Receipt modal shown after a sale succeeds. Four big action buttons
 *  (print / email / refund / new-sale) and a 30-second auto-dismiss that
 *  resets the UI for the next customer so the cashier can keep ringing
 *  up even if they don't touch anything. */

import { useEffect, useState } from "react";
import { useTranslations } from "next-intl";
import { toast } from "sonner";
import { api } from "@/lib/api-client";
import { usePos } from "@/lib/pos-store";

export default function PosReceiptModal() {
  const t = useTranslations("pos");
  const { lastSale, dismissLastSale } = usePos();
  const [refunding, setRefunding] = useState(false);

  useEffect(() => {
    if (!lastSale) return;
    const timer = setTimeout(dismissLastSale, 30_000);
    return () => clearTimeout(timer);
  }, [lastSale, dismissLastSale]);

  if (!lastSale) return null;

  async function handlePrint() {
    if (!lastSale) return;
    const base = process.env.NEXT_PUBLIC_API_URL ?? "";
    window.open(`${base}/api/pos/sales/${lastSale.id}/receipt`, "_blank");
  }

  async function handleRefund() {
    if (!lastSale) return;
    if (!window.confirm(t("refund_confirm"))) return;
    setRefunding(true);
    try {
      await api.post<unknown>(`/api/pos/sales/${lastSale.id}/refund`, {});
      toast.success(t("refund_success"));
      dismissLastSale();
    } catch (e) {
      toast.error((e as Error).message);
    } finally {
      setRefunding(false);
    }
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4"
      role="dialog"
      aria-modal="true"
      data-testid="pos-receipt-modal"
    >
      <div className="w-full max-w-md rounded-2xl bg-white p-6 shadow-xl dark:bg-gray-800">
        <div className="mb-4 flex items-center justify-between">
          <h3 className="text-lg font-semibold dark:text-gray-100">#{lastSale.sale_number}</h3>
          <span className="text-lg font-bold text-emerald-700 dark:text-emerald-400">
            {Number(lastSale.total).toFixed(2)} SEK
          </span>
        </div>

        {Number(lastSale.change_due ?? 0) > 0 && (
          <p className="mb-4 rounded-lg bg-emerald-50 px-3 py-2 text-sm text-emerald-900 dark:bg-emerald-900/30 dark:text-emerald-300">
            {t("change_due")}:{" "}
            <span className="font-semibold">
              {Number(lastSale.change_due).toFixed(2)} SEK
            </span>
          </p>
        )}

        <div className="grid grid-cols-2 gap-3">
          <button
            type="button"
            onClick={handlePrint}
            className="flex min-h-[72px] flex-col items-center justify-center rounded-xl border border-gray-200 bg-white text-sm font-medium hover:bg-gray-50 dark:border-gray-600 dark:bg-gray-700 dark:text-gray-200 dark:hover:bg-gray-600"
          >
            <span className="text-xl">🖨️</span>
            {t("receipt_print")}
          </button>
          <button
            type="button"
            onClick={() => toast.message("Email flow TBD")}
            className="flex min-h-[72px] flex-col items-center justify-center rounded-xl border border-gray-200 bg-white text-sm font-medium hover:bg-gray-50 dark:border-gray-600 dark:bg-gray-700 dark:text-gray-200 dark:hover:bg-gray-600"
          >
            <span className="text-xl">📧</span>
            {t("receipt_email")}
          </button>
          <button
            type="button"
            onClick={handleRefund}
            disabled={refunding}
            className="flex min-h-[72px] flex-col items-center justify-center rounded-xl border border-red-200 bg-white text-sm font-medium text-red-600 hover:bg-red-50 disabled:opacity-50 dark:border-red-800/50 dark:bg-gray-700 dark:text-red-400 dark:hover:bg-red-900/20"
          >
            <span className="text-xl">↩️</span>
            {refunding ? "…" : t("refund")}
          </button>
          <button
            type="button"
            onClick={dismissLastSale}
            className="flex min-h-[72px] flex-col items-center justify-center rounded-xl bg-emerald-600 text-sm font-semibold text-white hover:bg-emerald-700"
          >
            <span className="text-xl">➡️</span>
            {t("new_sale")}
          </button>
        </div>
      </div>
    </div>
  );
}
