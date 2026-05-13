"use client";

// File: src/components/ui/LimitWarningBanner.tsx
// Purpose: Yellow banner shown when org is approaching (≥80%) a plan limit.
// Used by: any page that creates resources (products, invoices, customers, etc.)

import Link from "next/link";
import { AlertTriangle } from "lucide-react";

interface LimitWarningBannerProps {
  resource: string;
  current: number;
  limit: number;
  upgradeUrl?: string;
}

export function LimitWarningBanner({
  resource,
  current,
  limit,
  upgradeUrl = "/en/settings/billing",
}: LimitWarningBannerProps) {
  const pct = Math.round((current / limit) * 100);
  const label = resource.replace(/_/g, " ");

  return (
    <div className="flex items-start gap-3 rounded-md border border-yellow-300 bg-yellow-50 px-4 py-3 text-sm text-yellow-800 dark:border-yellow-600/50 dark:bg-yellow-900/20 dark:text-yellow-300">
      <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
      <span>
        You have used <strong>{current}</strong> of <strong>{limit}</strong> {label} ({pct}%).{" "}
        <Link href={upgradeUrl} className="font-medium underline underline-offset-2">
          Upgrade your plan
        </Link>{" "}
        to increase your limit.
      </span>
    </div>
  );
}
