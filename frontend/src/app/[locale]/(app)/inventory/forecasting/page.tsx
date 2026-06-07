"use client";

import { useState, useEffect } from "react";
import { useTranslations } from "next-intl";
import { api } from "@/lib/api-client";
import { toast } from "sonner";
import {
  TrendingUp,
  AlertTriangle,
  CheckCircle2,
  RefreshCw,
  Package,
} from "lucide-react";
import styles from "./page.module.scss";

interface ForecastItem {
  product_id: string;
  product_name: string;
  sku: string;
  current_stock: number;
  predicted_demand: number;
  days_until_stockout: number | null;
  risk_level: "low" | "medium" | "high" | "critical";
  recommended_order_qty: number;
}

const RANGE_OPTIONS = [30, 60, 90] as const;

function riskColor(level: ForecastItem["risk_level"]): keyof typeof styles {
  switch (level) {
    case "critical":
      return "riskCritical";
    case "high":
      return "riskHigh";
    case "medium":
      return "riskMedium";
    default:
      return "riskLow";
  }
}

function riskIcon(level: ForecastItem["risk_level"]) {
  if (level === "critical" || level === "high") {
    return <AlertTriangle className="h-4 w-4" />;
  }
  return <CheckCircle2 className="h-4 w-4" />;
}

export default function ForecastingPage() {
  const t = useTranslations("inventory");
  const [days, setDays] = useState<number>(30);
  const [items, setItems] = useState<ForecastItem[]>([]);
  const [loading, setLoading] = useState(true);

  const fetchForecast = async (d: number) => {
    try {
      setLoading(true);
      const data = await api.get<ForecastItem[]>(
        `/api/inventory/forecasting?days=${d}`
      );
      setItems(data);
    } catch {
      toast.error("Failed to load forecast data.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchForecast(days);
  }, [days]);

  return (
    <div className="space-y-6 p-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="vf-text-1 text-2xl font-semibold">
            Inventory Forecasting
          </h1>
          <p className="vf-text-m mt-1">
            Predict stock needs and identify stockout risks.
          </p>
        </div>
        <div className="inline-flex items-center rounded-lg vf-border border overflow-hidden">
          {RANGE_OPTIONS.map((option) => (
            <button
              key={option}
              onClick={() => setDays(option)}
              className={`px-4 py-2 text-sm font-medium transition ${
                days === option
                  ? "bg-blue-600 text-white"
                  : "vf-text-m hover:bg-gray-100 dark:hover:bg-gray-800"
              }`}
            >
              {option}d
            </button>
          ))}
        </div>
      </div>

      {loading ? (
        <div className="flex items-center justify-center py-20">
          <RefreshCw className="h-6 w-6 animate-spin vf-text-m" />
        </div>
      ) : items.length === 0 ? (
        <div className="vf-bg-card vf-border flex flex-col items-center justify-center rounded-lg border py-16">
          <Package className="h-12 w-12 vf-text-m mb-4" />
          <p className="vf-text-1 font-medium">No forecast data available</p>
          <p className="vf-text-m mt-1 text-sm">
            Forecasts require historical sales data to generate predictions.
          </p>
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {items.map((item) => (
            <div
              key={item.product_id}
              className="vf-bg-card vf-border rounded-lg border p-5 space-y-3"
            >
              <div className="flex items-start justify-between">
                <div>
                  <p className="vf-text-1 font-medium">{item.product_name}</p>
                  <p className="vf-text-m text-xs">{item.sku}</p>
                </div>
                <span
                  className={styles[riskColor(item.risk_level)]}
                >
                  {riskIcon(item.risk_level)}
                  {item.risk_level}
                </span>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <p className="vf-text-m text-xs">Current Stock</p>
                  <p className="vf-text-1 text-lg font-semibold">
                    {item.current_stock}
                  </p>
                </div>
                <div>
                  <p className="vf-text-m text-xs">Predicted Demand</p>
                  <p className="vf-text-1 text-lg font-semibold">
                    {item.predicted_demand}
                  </p>
                </div>
                <div>
                  <p className="vf-text-m text-xs">Days to Stockout</p>
                  <p
                    className={`text-lg font-semibold ${
                      item.days_until_stockout !== null &&
                      item.days_until_stockout < 14
                        ? "text-red-500"
                        : "vf-text-1"
                    }`}
                  >
                    {item.days_until_stockout ?? "N/A"}
                  </p>
                </div>
                <div>
                  <p className="vf-text-m text-xs">Recommended Order</p>
                  <p className="vf-text-1 text-lg font-semibold">
                    {item.recommended_order_qty}
                  </p>
                </div>
              </div>

              {(item.risk_level === "critical" ||
                item.risk_level === "high") && (
                <div className="flex items-center gap-2 rounded-md bg-red-50 dark:bg-red-900/20 px-3 py-2">
                  <TrendingUp className="h-4 w-4 text-red-500" />
                  <span className="text-xs text-red-700 dark:text-red-400">
                    {item.risk_level === "critical"
                      ? "Immediate reorder recommended"
                      : "Consider reordering soon"}
                  </span>
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
