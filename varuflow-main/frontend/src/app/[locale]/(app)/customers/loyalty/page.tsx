"use client";

/**
 * Customers → Loyalty (Item 35).
 *
 * Admin-side loyalty control panel. Three tabs worth of content on
 * one page:
 *   1. Program config (earn rate, redemption rate, expiry window)
 *   2. Customer account lookup (by UUID) → live card + ledger
 *   3. Manual adjustment + redemption form for the selected customer
 *   4. CSV export link
 *
 * Wires:
 *   GET  /api/loyalty/program
 *   PUT  /api/loyalty/program
 *   GET  /api/loyalty/accounts/{id}
 *   GET  /api/loyalty/accounts/{id}/transactions
 *   POST /api/loyalty/accounts/{id}/adjust
 *   POST /api/loyalty/accounts/{id}/redeem
 *   GET  /api/loyalty/export/{id}
 */
import { useCallback, useEffect, useState } from "react";
import { useTranslations } from "next-intl";
import { toast } from "sonner";
import { Award, Download, Loader2, Save } from "lucide-react";

import { api } from "@/lib/api-client";
import { LoyaltyCard } from "@/components/loyalty/LoyaltyCard";

interface Program {
  id?: string | null;
  name: string;
  points_per_currency_unit: string;
  redemption_rate: string;
  expiry_days: number;
  is_active: boolean;
}

interface Transaction {
  id: string;
  points: number;
  type: string;
  source_type: string | null;
  source_id: string | null;
  reason: string | null;
  expires_at: string | null;
  created_at: string;
}

export default function LoyaltyPage() {
  const t = useTranslations("loyalty");
  const [program, setProgram] = useState<Program | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [customerId, setCustomerId] = useState("");
  const [txs, setTxs] = useState<Transaction[]>([]);
  const [fetchingLedger, setFetchingLedger] = useState(false);
  const [adjustDelta, setAdjustDelta] = useState("");
  const [adjustReason, setAdjustReason] = useState("");
  const [adjusting, setAdjusting] = useState(false);

  const loadProgram = useCallback(async () => {
    setLoading(true);
    try {
      const p = await api.get<Program>("/api/loyalty/program");
      setProgram(p);
    } catch {
      toast.error(t("load_failed"));
    } finally {
      setLoading(false);
    }
  }, [t]);

  useEffect(() => {
    loadProgram();
  }, [loadProgram]);

  const saveProgram = async () => {
    if (!program) return;
    setSaving(true);
    try {
      const saved = await api.put<Program>("/api/loyalty/program", {
        name: program.name,
        points_per_currency_unit: program.points_per_currency_unit,
        redemption_rate: program.redemption_rate,
        expiry_days: program.expiry_days,
        is_active: program.is_active,
      });
      setProgram(saved);
      toast.success(t("program_saved"));
    } catch {
      toast.error(t("save_failed"));
    } finally {
      setSaving(false);
    }
  };

  const loadLedger = async () => {
    if (!customerId) return;
    setFetchingLedger(true);
    try {
      const rows = await api.get<Transaction[]>(
        `/api/loyalty/accounts/${customerId}/transactions`
      );
      setTxs(rows);
    } catch {
      toast.error(t("ledger_failed"));
      setTxs([]);
    } finally {
      setFetchingLedger(false);
    }
  };

  const submitAdjust = async () => {
    const delta = parseInt(adjustDelta, 10);
    if (!customerId || Number.isNaN(delta) || delta === 0 || !adjustReason.trim()) {
      toast.error(t("adjust_invalid"));
      return;
    }
    setAdjusting(true);
    try {
      await api.post(
        `/api/loyalty/accounts/${customerId}/adjust`,
        { delta, reason: adjustReason.trim() }
      );
      toast.success(t("adjust_done"));
      setAdjustDelta("");
      setAdjustReason("");
      await loadLedger();
    } catch {
      toast.error(t("adjust_failed"));
    } finally {
      setAdjusting(false);
    }
  };

  const exportCsv = () => {
    if (!customerId) return;
    api.downloadBlob(
      `/api/loyalty/export/${customerId}`,
      `loyalty_${customerId}.csv`
    );
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center p-12">
        <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
      </div>
    );
  }

  return (
    <div className="space-y-8 p-6">
      <div className="flex items-center gap-3">
        <Award className="h-6 w-6 text-primary" />
        <div>
          <h1 className="text-2xl font-semibold">{t("title")}</h1>
          <p className="text-sm text-muted-foreground">{t("subtitle")}</p>
        </div>
      </div>

      {/* Program config */}
      <section className="rounded-lg border bg-card p-5">
        <h2 className="mb-2 text-base font-medium">{t("program")}</h2>
        <p className="mb-4 text-sm text-muted-foreground">{t("program_hint")}</p>
        {program && (
          <div className="grid gap-3 md:grid-cols-2">
            <label className="text-sm">
              <span className="mb-1 block text-xs text-muted-foreground">
                {t("points_per_unit")}
              </span>
              <input
                type="number"
                step="0.0001"
                min="0"
                value={program.points_per_currency_unit}
                onChange={(e) =>
                  setProgram({ ...program, points_per_currency_unit: e.target.value })
                }
                className="w-full rounded-md border bg-background px-3 py-2"
              />
            </label>
            <label className="text-sm">
              <span className="mb-1 block text-xs text-muted-foreground">
                {t("redemption_rate")}
              </span>
              <input
                type="number"
                step="0.000001"
                min="0"
                value={program.redemption_rate}
                onChange={(e) =>
                  setProgram({ ...program, redemption_rate: e.target.value })
                }
                className="w-full rounded-md border bg-background px-3 py-2"
              />
            </label>
            <label className="text-sm">
              <span className="mb-1 block text-xs text-muted-foreground">
                {t("expiry_days")}
              </span>
              <input
                type="number"
                min="0"
                max="3650"
                value={program.expiry_days}
                onChange={(e) =>
                  setProgram({ ...program, expiry_days: parseInt(e.target.value || "0", 10) })
                }
                className="w-full rounded-md border bg-background px-3 py-2"
              />
            </label>
            <label className="flex items-center gap-2 text-sm">
              <input
                type="checkbox"
                checked={program.is_active}
                onChange={(e) =>
                  setProgram({ ...program, is_active: e.target.checked })
                }
              />
              {t("is_active")}
            </label>
          </div>
        )}
        <button
          type="button"
          onClick={saveProgram}
          disabled={saving}
          className="mt-4 inline-flex items-center gap-2 rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground disabled:opacity-50"
        >
          {saving ? <Loader2 className="h-4 w-4 animate-spin" /> : <Save className="h-4 w-4" />}
          {t("save")}
        </button>
      </section>

      {/* Customer lookup */}
      <section className="rounded-lg border bg-card p-5">
        <h2 className="mb-2 text-base font-medium">{t("customer_lookup")}</h2>
        <p className="mb-4 text-sm text-muted-foreground">{t("customer_hint")}</p>
        <div className="flex flex-wrap items-center gap-3">
          <input
            type="text"
            value={customerId}
            onChange={(e) => setCustomerId(e.target.value.trim())}
            placeholder={t("customer_id_placeholder")}
            className="flex-1 rounded-md border bg-background px-3 py-2 text-sm font-mono"
          />
          <button
            type="button"
            onClick={loadLedger}
            disabled={!customerId || fetchingLedger}
            className="inline-flex items-center gap-2 rounded-md border px-3 py-2 text-sm font-medium disabled:opacity-50"
          >
            {fetchingLedger && <Loader2 className="h-4 w-4 animate-spin" />}
            {t("load")}
          </button>
          <button
            type="button"
            onClick={exportCsv}
            disabled={!customerId}
            className="inline-flex items-center gap-2 rounded-md border px-3 py-2 text-sm font-medium disabled:opacity-50"
          >
            <Download className="h-4 w-4" />
            {t("export_csv")}
          </button>
        </div>

        {customerId && (
          <div className="mt-5 space-y-5">
            <LoyaltyCard customerId={customerId} />

            {/* Manual adjustment */}
            <div className="rounded-md border bg-muted/30 p-4">
              <h3 className="mb-2 text-sm font-medium">{t("manual_adjust")}</h3>
              <div className="flex flex-wrap gap-3">
                <input
                  type="number"
                  value={adjustDelta}
                  onChange={(e) => setAdjustDelta(e.target.value)}
                  placeholder={t("adjust_delta")}
                  className="w-36 rounded-md border bg-background px-3 py-2 text-sm"
                />
                <input
                  type="text"
                  value={adjustReason}
                  onChange={(e) => setAdjustReason(e.target.value)}
                  placeholder={t("adjust_reason")}
                  className="flex-1 rounded-md border bg-background px-3 py-2 text-sm"
                />
                <button
                  type="button"
                  onClick={submitAdjust}
                  disabled={adjusting}
                  className="inline-flex items-center gap-2 rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground disabled:opacity-50"
                >
                  {adjusting ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
                  {t("apply")}
                </button>
              </div>
            </div>

            {/* Ledger */}
            <div>
              <h3 className="mb-2 text-sm font-medium">{t("ledger")}</h3>
              {txs.length === 0 ? (
                <p className="text-sm text-muted-foreground">{t("no_ledger_rows")}</p>
              ) : (
                <table className="w-full text-sm">
                  <thead className="text-left text-xs uppercase text-muted-foreground">
                    <tr>
                      <th className="pb-2">{t("date")}</th>
                      <th className="pb-2">{t("type")}</th>
                      <th className="pb-2 text-right">{t("points")}</th>
                      <th className="pb-2">{t("source")}</th>
                      <th className="pb-2">{t("reason")}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {txs.map((row) => (
                      <tr key={row.id} className="border-t">
                        <td className="py-2 text-muted-foreground">
                          {new Date(row.created_at).toLocaleString()}
                        </td>
                        <td className="py-2">
                          {t(`type.${row.type}` as "type.earn")}
                        </td>
                        <td
                          className={`py-2 text-right font-mono ${
                            row.points < 0 ? "text-red-500" : "text-emerald-600"
                          }`}
                        >
                          {row.points > 0 ? `+${row.points}` : row.points}
                        </td>
                        <td className="py-2 text-xs text-muted-foreground">
                          {row.source_type || ""}
                        </td>
                        <td className="py-2 text-xs text-muted-foreground">
                          {row.reason || ""}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>
          </div>
        )}
      </section>
    </div>
  );
}
