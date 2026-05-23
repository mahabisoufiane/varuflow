"use client";

/**
 * Analytics → Forecasting (Item 41)
 *
 * Inventory forecasting dashboard for PRO+ tenants. Shows projected
 * stock at 30/60/90 day horizons, days-until-stockout, seasonal
 * trend, and a red-highlighted "at risk" list. Read-only except for
 * the CSV export (which audits as forecast.exported).
 *
 * Wires: GET /api/analytics/forecasting, /at-risk, /export.csv.
 */
import { useCallback, useEffect, useState } from "react";
import { useTranslations } from "next-intl";
import { toast } from "sonner";
import { Download, Loader2, TrendingDown, TrendingUp, Minus, AlertTriangle } from "lucide-react";

import { api } from "@/lib/api-client";

interface ForecastRow {
  product_id: string;
  name: string;
  sku: string;
  on_hand: number;
  reorder_level: number;
  avg_daily_demand: number;
  days_until_stockout: number | null;
  forecast_30: number;
  forecast_60: number;
  forecast_90: number;
  trend: "up" | "down" | "stable";
  at_risk: boolean;
}

interface ForecastReport {
  generated_at: string;
  horizon_days: number[];
  at_risk_days: number;
  lookback_days: number;
  rows: ForecastRow[];
  at_risk_count: number;
}

function TrendIcon({ trend }: { trend: ForecastRow["trend"] }) {
  if (trend === "up") return <TrendingUp className="h-4 w-4 text-emerald-600" />;
  if (trend === "down") return <TrendingDown className="h-4 w-4 text-amber-600" />;
  return <Minus className="h-4 w-4 text-muted-foreground" />;
}

function formatDays(d: number | null): string {
  if (d === null) return "∞";
  return d.toFixed(1);
}

export default function ForecastingPage() {
  const t = useTranslations("forecasting");
  const [report, setReport] = useState<ForecastReport | null>(null);
  const [loading, setLoading] = useState(true);
  const [denied, setDenied] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const data = await api.get<ForecastReport>("/api/analytics/forecasting");
      setReport(data);
    } catch (err: any) {
      if (err?.status === 403) {
        setDenied(true);
      } else {
        toast.error(t("load_failed"));
      }
    } finally {
      setLoading(false);
    }
  }, [t]);

  useEffect(() => {
    load();
  }, [load]);

  const exportCsv = () => {
    window.open("/api/analytics/forecasting/export.csv", "_blank");
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center p-12">
        <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
      </div>
    );
  }

  if (denied) {
    return (
      <div className="container mx-auto p-6">
        <div className="rounded-lg border p-6 text-center space-y-2">
          <h1 className="text-xl font-semibold">{t("title")}</h1>
          <p className="text-muted-foreground">{t("plan_required")}</p>
        </div>
      </div>
    );
  }

  if (!report) return null;

  const atRiskRows = report.rows.filter((r) => r.at_risk);
  const healthyRows = report.rows.filter((r) => !r.at_risk);

  return (
    <div className="container mx-auto p-6 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold">{t("title")}</h1>
          <p className="text-sm text-muted-foreground">
            {t("subtitle", { days: report.at_risk_days })}
          </p>
        </div>
        <button
          onClick={exportCsv}
          className="inline-flex items-center gap-1 rounded bg-primary text-primary-foreground px-3 py-1.5 text-sm"
        >
          <Download className="h-4 w-4" />
          {t("export_csv")}
        </button>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="rounded-lg border p-4">
          <div className="text-xs text-muted-foreground">{t("tile_total")}</div>
          <div className="text-2xl font-semibold">{report.rows.length}</div>
        </div>
        <div className="rounded-lg border p-4">
          <div className="text-xs text-muted-foreground">{t("tile_at_risk")}</div>
          <div className="text-2xl font-semibold text-red-600 flex items-center gap-2">
            <AlertTriangle className="h-5 w-5" />
            {report.at_risk_count}
          </div>
        </div>
        <div className="rounded-lg border p-4">
          <div className="text-xs text-muted-foreground">{t("tile_lookback")}</div>
          <div className="text-2xl font-semibold">{report.lookback_days}d</div>
        </div>
      </div>

      {atRiskRows.length > 0 && (
        <section className="space-y-2">
          <h2 className="text-lg font-semibold text-red-600 flex items-center gap-2">
            <AlertTriangle className="h-5 w-5" />
            {t("at_risk_heading")}
          </h2>
          <ForecastTable rows={atRiskRows} t={t} highlight />
        </section>
      )}

      <section className="space-y-2">
        <h2 className="text-lg font-semibold">{t("all_products_heading")}</h2>
        <ForecastTable rows={healthyRows} t={t} />
      </section>
    </div>
  );
}

function ForecastTable({
  rows,
  t,
  highlight = false,
}: {
  rows: ForecastRow[];
  t: ReturnType<typeof useTranslations>;
  highlight?: boolean;
}) {
  if (rows.length === 0) {
    return (
      <div className="rounded-lg border p-4 text-center text-sm text-muted-foreground">
        {t("empty")}
      </div>
    );
  }
  return (
    <div className="rounded-lg border overflow-x-auto">
      <table className="w-full text-sm">
        <thead className="bg-muted">
          <tr>
            <th className="text-left p-2">{t("col_product")}</th>
            <th className="text-left p-2">{t("col_sku")}</th>
            <th className="text-right p-2">{t("col_on_hand")}</th>
            <th className="text-right p-2">{t("col_avg_demand")}</th>
            <th className="text-right p-2">{t("col_days_until")}</th>
            <th className="text-right p-2">{t("col_forecast_30")}</th>
            <th className="text-right p-2">{t("col_forecast_60")}</th>
            <th className="text-right p-2">{t("col_forecast_90")}</th>
            <th className="p-2">{t("col_trend")}</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr
              key={r.product_id}
              className={highlight ? "bg-red-50 dark:bg-red-950/20" : ""}
            >
              <td className="p-2">{r.name}</td>
              <td className="p-2 font-mono text-xs">{r.sku}</td>
              <td className="p-2 text-right">{r.on_hand}</td>
              <td className="p-2 text-right">{r.avg_daily_demand.toFixed(2)}</td>
              <td className="p-2 text-right">{formatDays(r.days_until_stockout)}</td>
              <td className="p-2 text-right">{r.forecast_30}</td>
              <td className="p-2 text-right">{r.forecast_60}</td>
              <td className="p-2 text-right">{r.forecast_90}</td>
              <td className="p-2 text-center">
                <TrendIcon trend={r.trend} />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
