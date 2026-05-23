"use client";

// File: src/components/dashboard/RecentActivity.tsx
// Purpose: Compact unified activity feed rendered under the metric
// cards on the mobile dashboard (and inside a card on desktop). Pulls
// from GET /api/analytics/activity which requires STARTER+ plan.

import { useEffect, useState } from "react";
import Link from "next/link";
import { useLocale, useTranslations } from "next-intl";
import {
  FileText, ArrowDownRight, ArrowUpRight, Package, Truck, UserPlus,
  type LucideIcon,
} from "lucide-react";
import { api } from "@/lib/api-client";
import { cn } from "@/lib/utils";

type ActivityType =
  | "invoice_created"
  | "invoice_paid"
  | "stock_movement"
  | "purchase_order_received"
  | "new_customer";

interface ActivityItem {
  type: ActivityType;
  description: string;
  amount_sek: number | null;
  created_at: string;
  icon_hint: string;
}

const ICONS: Record<ActivityType, LucideIcon> = {
  invoice_created:         FileText,
  invoice_paid:            ArrowDownRight,
  stock_movement:          Package,
  purchase_order_received: Truck,
  new_customer:            UserPlus,
};

function timeAgo(iso: string): string {
  const delta = Math.max(0, (Date.now() - new Date(iso).getTime()) / 1000);
  if (delta < 60)      return `${Math.floor(delta)}s`;
  if (delta < 3600)    return `${Math.floor(delta / 60)}m`;
  if (delta < 86_400)  return `${Math.floor(delta / 3600)}h`;
  return `${Math.floor(delta / 86_400)}d`;
}

export default function RecentActivity() {
  const t = useTranslations();
  const locale = useLocale();
  const [items, setItems] = useState<ActivityItem[] | null>(null);
  const [denied, setDenied] = useState(false);

  useEffect(() => {
    (async () => {
      try {
        const list = await api.get<ActivityItem[]>("/api/analytics/activity?limit=5");
        setItems(list);
      } catch (e) {
        const msg = (e as Error).message ?? "";
        if (msg.includes("403") || msg.toLowerCase().includes("plan")) setDenied(true);
        else setItems([]);
      }
    })();
  }, []);

  if (denied) return null;

  return (
    <section data-testid="recent-activity" className="rounded-2xl border border-gray-200 bg-white p-4 dark:border-white/10 dark:bg-white/5">
      <div className="mb-3 flex items-center justify-between">
        <h2 className="text-sm font-semibold">{t("dashboard.recent_activity")}</h2>
        <Link href={`/${locale}/analytics`} className="text-xs text-emerald-600">
          {t("dashboard.view_all")}
        </Link>
      </div>
      {items === null ? (
        <ul className="space-y-3">
          {[0, 1, 2].map((i) => (
            <li key={i} className="flex items-center gap-3">
              <div className="h-8 w-8 animate-pulse rounded-full bg-gray-200 dark:bg-white/10" />
              <div className="h-4 flex-1 animate-pulse rounded bg-gray-200 dark:bg-white/10" />
              <div className="h-4 w-16 animate-pulse rounded bg-gray-200 dark:bg-white/10" />
            </li>
          ))}
        </ul>
      ) : items.length === 0 ? (
        <p className="py-4 text-center text-xs text-gray-400">—</p>
      ) : (
        <ul className="divide-y divide-gray-100 dark:divide-white/5">
          {items.map((a, i) => {
            const Icon = ICONS[a.type] ?? FileText;
            const isRevenue = a.type === "invoice_paid" || a.type === "invoice_created";
            return (
              <li key={i} className="flex items-center gap-3 py-2.5">
                <span className="flex h-8 w-8 items-center justify-center rounded-full bg-gray-100 text-gray-600 dark:bg-white/10 dark:text-gray-300">
                  <Icon className="h-4 w-4" />
                </span>
                <div className="min-w-0 flex-1">
                  <p className="truncate text-sm">{a.description}</p>
                  <p className="text-[11px] text-gray-400">{timeAgo(a.created_at)}</p>
                </div>
                {a.amount_sek != null && (
                  <span
                    className={cn(
                      "shrink-0 text-sm font-semibold tabular-nums",
                      isRevenue ? "text-emerald-600" : "text-gray-900 dark:text-white",
                    )}
                  >
                    {Number(a.amount_sek).toLocaleString("sv-SE")} kr
                  </span>
                )}
              </li>
            );
          })}
        </ul>
      )}
    </section>
  );
}
