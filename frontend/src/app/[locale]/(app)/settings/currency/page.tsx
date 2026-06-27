"use client";

/**
 * Settings → Currency (Item 34)
 *
 * Owner/admin UI for managing the organisation's base currency and
 * inspecting the latest cached exchange rates. Rates refresh
 * automatically via the daily scheduler; the "refresh" button here
 * is a manual override (e.g. just before closing a foreign-currency
 * invoice batch).
 *
 * Wires:
 *   GET  /api/currencies           → supported ISO codes
 *   GET  /api/currencies/base      → current org base currency
 *   PUT  /api/currencies/base      → change base (logs audit)
 *   GET  /api/currencies/rates     → latest-per-pair snapshot
 *   POST /api/currencies/rates/refresh → trigger sweep (logs audit)
 */
import { useCallback, useEffect, useState } from "react";
import { useTranslations } from "next-intl";
import { toast } from "sonner";
import { Coins, Loader2, RefreshCw, Save } from "lucide-react";

import { api } from "@/lib/api-client";

interface RateRow {
  id: string;
  base_currency: string;
  target_currency: string;
  rate: string;
  fetched_at: string;
}

interface BaseResponse {
  base_currency: string;
}

export default function CurrencySettingsPage() {
  const t = useTranslations("currency");
  const [supported, setSupported] = useState<string[]>([]);
  const [base, setBase] = useState<string>("SEK");
  const [draftBase, setDraftBase] = useState<string>("SEK");
  const [rates, setRates] = useState<RateRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [refreshing, setRefreshing] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [codes, baseRes, rateRes] = await Promise.all([
        api.get<string[]>("/api/currencies").catch(() => [] as string[]),
        api.get<BaseResponse>("/api/currencies/base").catch(() => ({ base_currency: "SEK" })),
        api.get<RateRow[]>("/api/currencies/rates").catch(() => [] as RateRow[]),
      ]);
      setSupported(codes);
      setBase(baseRes.base_currency);
      setDraftBase(baseRes.base_currency);
      setRates(rateRes);
    } catch {
      toast.error(t("load_failed"));
    } finally {
      setLoading(false);
    }
  }, [t]);

  useEffect(() => {
    load();
  }, [load]);

  const saveBase = async () => {
    if (!draftBase || draftBase === base) return;
    setSaving(true);
    try {
      await api.put("/api/currencies/base", { base_currency: draftBase });
      setBase(draftBase);
      toast.success(t("base_saved"));
    } catch {
      toast.error(t("save_failed"));
    } finally {
      setSaving(false);
    }
  };

  const refresh = async () => {
    setRefreshing(true);
    try {
      await api.post("/api/currencies/rates/refresh", {});
      const fresh = await api.get<RateRow[]>("/api/currencies/rates").catch(() => [] as RateRow[]);
      setRates(fresh);
      toast.success(t("refresh_done"));
    } catch {
      toast.error(t("refresh_failed"));
    } finally {
      setRefreshing(false);
    }
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
        <Coins className="h-6 w-6 text-primary" />
        <div>
          <h1 className="text-2xl font-semibold">{t("title")}</h1>
          <p className="text-sm text-muted-foreground">{t("subtitle")}</p>
        </div>
      </div>

      {/* Base currency picker */}
      <section className="rounded-lg border bg-card p-5">
        <h2 className="mb-2 text-base font-medium">{t("base_currency")}</h2>
        <p className="mb-4 text-sm text-muted-foreground">{t("base_hint")}</p>
        <div className="flex flex-wrap items-center gap-3">
          <select
            value={draftBase}
            onChange={(e) => setDraftBase(e.target.value.toUpperCase())}
            className="rounded-md border bg-background px-3 py-2 text-sm"
            disabled={saving}
          >
            {supported.map((c) => (
              <option key={c} value={c}>
                {c}
              </option>
            ))}
          </select>
          <button
            type="button"
            onClick={saveBase}
            disabled={saving || draftBase === base}
            className="inline-flex items-center gap-2 rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground disabled:opacity-50"
          >
            {saving ? <Loader2 className="h-4 w-4 animate-spin" /> : <Save className="h-4 w-4" />}
            {t("save")}
          </button>
          <span className="text-xs text-muted-foreground">
            {t("current")}: <strong>{base}</strong>
          </span>
        </div>
      </section>

      {/* Rates table */}
      <section className="rounded-lg border bg-card p-5">
        <div className="mb-4 flex items-center justify-between">
          <div>
            <h2 className="text-base font-medium">{t("exchange_rates")}</h2>
            <p className="text-sm text-muted-foreground">{t("rates_hint")}</p>
          </div>
          <button
            type="button"
            onClick={refresh}
            disabled={refreshing}
            className="inline-flex items-center gap-2 rounded-md border px-3 py-2 text-sm font-medium disabled:opacity-50"
          >
            {refreshing ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <RefreshCw className="h-4 w-4" />
            )}
            {t("refresh")}
          </button>
        </div>
        {rates.length === 0 ? (
          <p className="py-8 text-center text-sm text-muted-foreground">{t("no_rates")}</p>
        ) : (
          <table className="w-full text-sm">
            <thead className="text-left text-xs uppercase text-muted-foreground">
              <tr>
                <th className="pb-2">{t("pair")}</th>
                <th className="pb-2">{t("rate_label")}</th>
                <th className="pb-2">{t("last_updated")}</th>
              </tr>
            </thead>
            <tbody>
              {rates.map((r) => (
                <tr key={r.id} className="border-t">
                  <td className="py-2 font-mono">
                    {r.base_currency} → {r.target_currency}
                  </td>
                  <td className="py-2 font-mono">{r.rate}</td>
                  <td className="py-2 text-muted-foreground">
                    {new Date(r.fetched_at).toLocaleString()}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>
    </div>
  );
}
