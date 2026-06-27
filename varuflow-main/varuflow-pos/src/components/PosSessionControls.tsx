/** Session open / close controls.
 *
 * "Öppna session" prompt for opening cash float when no active session.
 * "Stäng session" button opens a Z-report modal which pre-renders the
 * server-computed totals (via GET /api/pos/sessions/:id/zreport) so
 * the cashier never has to compute the variance by hand. */

import { useEffect, useState } from "react";
import { usePosT } from "../lib/i18n";
import { toast } from "sonner";
import { api } from "../lib/api";
import { usePos } from "../lib/pos-store";

interface ZReport {
  session: { id: string; status: string; opened_at: string; closed_at: string | null };
  sales_count: number;
  total_revenue: string;
  by_payment_method: { cash: string; card: string; swish: string };
  opening_float: string;
  expected_cash: string;
  counted_cash: string | null;
  variance: string | null;
  items_sold: { product_name: string; qty: string; total: string }[];
}

export default function PosSessionControls() {
  const t = usePosT();
  const { session, openSession, closeSession, loadOpenSession } = usePos();
  const [openingFloat, setOpeningFloat] = useState(0);
  const [countedCash, setCountedCash] = useState(0);
  const [zReport, setZReport] = useState<ZReport | null>(null);
  const [showZ, setShowZ] = useState(false);

  useEffect(() => {
    loadOpenSession();
  }, [loadOpenSession]);

  async function loadZ(id: string) {
    try {
      const r = await api.get<ZReport>(`/api/pos/sessions/${id}/zreport`);
      setZReport(r);
    } catch (e) {
      toast.error((e as Error).message);
    }
  }

  async function handleDownloadPdf() {
    if (!session) return;
    const base = (import.meta.env.VITE_API_URL ?? "");
    window.open(`${base}/api/pos/sessions/${session.id}/zreport?format=pdf`, "_blank");
  }

  if (!session) {
    return (
      <div className="flex items-center gap-2" data-testid="pos-open-session">
        <input
          type="number"
          inputMode="decimal"
          min={0}
          value={openingFloat || ""}
          onChange={(e) => setOpeningFloat(Number(e.target.value) || 0)}
          placeholder={t("opening_float")}
          className="h-11 w-36 rounded-lg border border-gray-300 px-3 text-sm dark:border-gray-600 dark:bg-gray-800 dark:text-gray-100"
        />
        <button
          type="button"
          onClick={async () => {
            try {
              await openSession(openingFloat);
            } catch (e) {
              toast.error((e as Error).message);
            }
          }}
          className="h-11 rounded-lg bg-emerald-600 px-4 text-sm font-semibold text-white"
        >
          {t("open_session")}
        </button>
      </div>
    );
  }

  return (
    <div className="flex items-center gap-2">
      <button
        type="button"
        onClick={async () => {
          setShowZ(true);
          await loadZ(session.id);
        }}
        data-testid="pos-close-session"
        className="h-11 rounded-lg border border-gray-300 bg-white px-4 text-sm font-medium dark:border-gray-600 dark:bg-gray-800 dark:text-gray-200"
      >
        {t("close_session")}
      </button>

      {showZ && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4"
          role="dialog"
          aria-modal="true"
          data-testid="pos-zreport-modal"
        >
          <div className="w-full max-w-lg rounded-2xl bg-white p-6 shadow-xl dark:bg-gray-800">
            <h3 className="mb-4 text-lg font-semibold">{t("z_report_title")}</h3>

            {!zReport ? (
              <p className="py-6 text-center text-sm text-gray-500 dark:text-gray-400">…</p>
            ) : (
              <>
                <div className="mb-3 grid grid-cols-2 gap-2 text-sm text-gray-700 dark:text-gray-300">
                  <div>Sales</div><div className="text-right tabular-nums">{zReport.sales_count}</div>
                  <div>Total revenue</div><div className="text-right tabular-nums">{Number(zReport.total_revenue).toFixed(2)} SEK</div>
                  <div>{t("payment_cash")}</div><div className="text-right tabular-nums">{Number(zReport.by_payment_method.cash).toFixed(2)}</div>
                  <div>{t("payment_card")}</div><div className="text-right tabular-nums">{Number(zReport.by_payment_method.card).toFixed(2)}</div>
                  <div>{t("payment_swish")}</div><div className="text-right tabular-nums">{Number(zReport.by_payment_method.swish).toFixed(2)}</div>
                  <div>{t("opening_float")}</div><div className="text-right tabular-nums">{Number(zReport.opening_float).toFixed(2)}</div>
                  <div>Expected cash</div><div className="text-right tabular-nums">{Number(zReport.expected_cash).toFixed(2)}</div>
                </div>

                <label className="mb-1 block text-sm text-gray-600 dark:text-gray-400">{t("counted_cash")}</label>
                <input
                  type="number"
                  inputMode="decimal"
                  min={0}
                  value={countedCash || ""}
                  onChange={(e) => setCountedCash(Number(e.target.value) || 0)}
                  className="mb-2 h-11 w-full rounded-lg border border-gray-300 px-3 dark:border-gray-600 dark:bg-gray-700 dark:text-gray-100"
                />
                {countedCash > 0 && (() => {
                  const variance = countedCash - Number(zReport.expected_cash);
                  const ok = Math.abs(variance) < 0.01;
                  return (
                    <p
                      className={`mb-3 text-sm ${ok ? "text-emerald-700" : "text-red-600"}`}
                      data-testid="pos-cash-variance"
                    >
                      {t("cash_variance")}: {variance.toFixed(2)} SEK
                    </p>
                  );
                })()}

                <div className="flex flex-wrap gap-2">
                  <button
                    type="button"
                    onClick={handleDownloadPdf}
                    disabled={session.status !== "CLOSED"}
                    data-testid="pos-zreport-download"
                    className="h-11 rounded-lg border border-gray-300 bg-white px-4 text-sm font-medium disabled:opacity-50 dark:border-gray-600 dark:bg-gray-700 dark:text-gray-200"
                  >
                    {t("z_report_download")}
                  </button>
                  <button
                    type="button"
                    onClick={async () => {
                      try {
                        await closeSession(countedCash);
                        toast.success(t("close_session"));
                        setShowZ(false);
                      } catch (e) {
                        toast.error((e as Error).message);
                      }
                    }}
                    className="h-11 flex-1 rounded-lg bg-emerald-600 px-4 text-sm font-semibold text-white"
                  >
                    {t("confirm_close")}
                  </button>
                  <button
                    type="button"
                    onClick={() => setShowZ(false)}
                    className="h-11 rounded-lg px-3 text-sm text-gray-600 dark:text-gray-400"
                  >
                    ✕
                  </button>
                </div>
              </>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
