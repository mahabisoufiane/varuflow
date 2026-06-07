"use client";

import { useEffect, useState } from "react";
import { useTranslations } from "next-intl";
import { api } from "@/lib/api-client";
import { toast } from "sonner";
import { Receipt, Download, Calculator, AlertTriangle } from "lucide-react";

interface PosSession {
  id: string;
  opened_at: string;
  closed_at: string;
  opening_cash: number;
  closing_cash: number;
  total_sales: number;
  total_card: number;
  total_cash_sales: number;
  total_refunds: number;
  transaction_count: number;
  currency: string;
}

export default function ZReportPage() {
  const t = useTranslations("pos");
  const [sessions, setSessions] = useState<PosSession[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [countedCash, setCountedCash] = useState("");

  useEffect(() => {
    (async () => {
      try {
        const data = await api.get<PosSession[]>("/api/pos/sessions?status=closed");
        setSessions(data || []);
      } catch {
        toast.error(t("loadError"));
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  const selected = sessions.find((s) => s.id === selectedId);
  const counted = parseFloat(countedCash) || 0;
  const expectedCash = selected
    ? selected.opening_cash + selected.total_cash_sales - selected.total_refunds
    : 0;
  const variance = selected ? counted - expectedCash : 0;

  async function handleDownload(sessionId: string) {
    try {
      const blob = await api.get<Blob>(`/api/pos/sessions/${sessionId}/zreport`);
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `z-report-${sessionId}.pdf`;
      a.click();
      URL.revokeObjectURL(url);
    } catch {
      toast.error(t("downloadError"));
    }
  }

  async function handleSubmitCount() {
    if (!selectedId) return;
    try {
      await api.post(`/api/pos/sessions/${selectedId}/reconcile`, {
        counted_cash: counted,
      });
      toast.success(t("reconciled"));
    } catch {
      toast.error(t("reconcileError"));
    }
  }

  function fmt(amount: number, currency: string) {
    return new Intl.NumberFormat(undefined, {
      style: "currency",
      currency,
    }).format(amount);
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin h-8 w-8 border-4 border-current border-t-transparent rounded-full" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-2">
        <Receipt className="h-6 w-6 vf-text-1" />
        <h1 className="vf-text-1 text-2xl font-bold">{t("zReport")}</h1>
      </div>

      {sessions.length === 0 ? (
        <p className="vf-text-m text-center py-12">{t("noClosedSessions")}</p>
      ) : (
        <div className="grid gap-4 lg:grid-cols-2">
          {/* Session list */}
          <div className="space-y-3">
            <h2 className="vf-text-1 font-semibold">{t("closedSessions")}</h2>
            {sessions.map((s) => (
              <button
                key={s.id}
                onClick={() => {
                  setSelectedId(s.id);
                  setCountedCash("");
                }}
                className={`w-full text-left vf-bg-card vf-border rounded-lg p-4 hover:ring-2 hover:ring-primary/30 transition ${
                  selectedId === s.id ? "ring-2 ring-primary" : ""
                }`}
              >
                <div className="flex items-center justify-between">
                  <p className="vf-text-1 font-medium">
                    {new Date(s.closed_at).toLocaleDateString()}
                  </p>
                  <span className="vf-text-m text-sm">
                    {s.transaction_count} txns
                  </span>
                </div>
                <p className="vf-text-m text-sm mt-1">
                  {t("totalSales")}: {fmt(s.total_sales, s.currency)}
                </p>
              </button>
            ))}
          </div>

          {/* Detail / reconciliation */}
          {selected && (
            <div className="space-y-4">
              <div className="vf-bg-card vf-border rounded-lg p-5 space-y-3">
                <h2 className="vf-text-1 font-semibold">{t("sessionSummary")}</h2>
                <dl className="grid grid-cols-2 gap-2 text-sm">
                  <dt className="vf-text-m">{t("opened")}</dt>
                  <dd className="vf-text-1">
                    {new Date(selected.opened_at).toLocaleString()}
                  </dd>
                  <dt className="vf-text-m">{t("closed")}</dt>
                  <dd className="vf-text-1">
                    {new Date(selected.closed_at).toLocaleString()}
                  </dd>
                  <dt className="vf-text-m">{t("openingCash")}</dt>
                  <dd className="vf-text-1">
                    {fmt(selected.opening_cash, selected.currency)}
                  </dd>
                  <dt className="vf-text-m">{t("totalSales")}</dt>
                  <dd className="vf-text-1">
                    {fmt(selected.total_sales, selected.currency)}
                  </dd>
                  <dt className="vf-text-m">{t("cardPayments")}</dt>
                  <dd className="vf-text-1">
                    {fmt(selected.total_card, selected.currency)}
                  </dd>
                  <dt className="vf-text-m">{t("cashSales")}</dt>
                  <dd className="vf-text-1">
                    {fmt(selected.total_cash_sales, selected.currency)}
                  </dd>
                  <dt className="vf-text-m">{t("refunds")}</dt>
                  <dd className="vf-text-1">
                    {fmt(selected.total_refunds, selected.currency)}
                  </dd>
                </dl>
              </div>

              {/* Cash count form */}
              <div className="vf-bg-card vf-border rounded-lg p-5 space-y-3">
                <div className="flex items-center gap-2">
                  <Calculator className="h-5 w-5 vf-text-1" />
                  <h2 className="vf-text-1 font-semibold">{t("cashCount")}</h2>
                </div>
                <div className="flex gap-3 items-end">
                  <div className="flex-1">
                    <label className="block text-sm vf-text-m mb-1">
                      {t("countedCash")}
                    </label>
                    <input
                      type="number"
                      step="0.01"
                      value={countedCash}
                      onChange={(e) => setCountedCash(e.target.value)}
                      className="w-full rounded-md border px-3 py-2 text-sm vf-border"
                    />
                  </div>
                  <button
                    onClick={handleSubmitCount}
                    disabled={!countedCash}
                    className="rounded-lg bg-primary px-4 py-2 text-sm font-medium text-white hover:bg-primary/90 disabled:opacity-50"
                  >
                    {t("submit")}
                  </button>
                </div>
                <p className="text-sm vf-text-m">
                  {t("expectedCash")}: {fmt(expectedCash, selected.currency)}
                </p>
                {countedCash && (
                  <div
                    className={`flex items-center gap-2 rounded-md p-3 text-sm ${
                      Math.abs(variance) < 0.01
                        ? "bg-green-50 text-green-800"
                        : "bg-yellow-50 text-yellow-800"
                    }`}
                  >
                    {Math.abs(variance) >= 0.01 && (
                      <AlertTriangle className="h-4 w-4" />
                    )}
                    {t("variance")}: {fmt(variance, selected.currency)}
                  </div>
                )}
              </div>

              <button
                onClick={() => handleDownload(selected.id)}
                className="inline-flex items-center gap-2 rounded-lg border px-4 py-2 text-sm font-medium vf-border hover:bg-accent"
              >
                <Download className="h-4 w-4" />
                {t("downloadZReport")}
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
