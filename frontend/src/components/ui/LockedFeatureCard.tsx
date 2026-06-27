"use client";

// File: src/components/ui/LockedFeatureCard.tsx
// Purpose: Greyed-out card with upgrade CTA for features not available on the current plan.
// Used by: feature sections that require PRO / ENTERPRISE (webhooks, white-label, etc.)

import Link from "next/link";
import { Lock } from "lucide-react";

interface LockedFeatureCardProps {
  featureName: string;
  requiredPlan: "PRO" | "ENTERPRISE";
  description?: string;
  upgradeUrl?: string;
  children?: React.ReactNode;
}

export function LockedFeatureCard({
  featureName,
  requiredPlan,
  description,
  upgradeUrl = "/en/settings/billing",
  children,
}: LockedFeatureCardProps) {
  return (
    <div className="relative overflow-hidden rounded-lg border border-gray-200 bg-gray-50 dark:border-gray-700 dark:bg-gray-900/40">
      {/* Greyed overlay */}
      <div className="pointer-events-none absolute inset-0 z-10 bg-gray-100/60 dark:bg-gray-900/60" />

      {/* Blurred preview content */}
      <div className="pointer-events-none select-none blur-[2px]" aria-hidden>
        {children ?? (
          <div className="flex h-32 items-center justify-center text-gray-400 text-sm">
            Feature preview
          </div>
        )}
      </div>

      {/* Lock overlay CTA */}
      <div className="absolute inset-0 z-20 flex flex-col items-center justify-center gap-2 p-4 text-center">
        <Lock className="h-6 w-6 text-gray-500 dark:text-gray-400" />
        <p className="text-sm font-semibold text-gray-700 dark:text-gray-200">{featureName}</p>
        {description && (
          <p className="text-xs text-gray-500 dark:text-gray-400 max-w-xs">{description}</p>
        )}
        <Link
          href={upgradeUrl}
          className="mt-1 inline-flex items-center rounded-md bg-indigo-600 px-3 py-1.5 text-xs font-medium text-white shadow-sm hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:ring-offset-2"
        >
          Upgrade to {requiredPlan}
        </Link>
      </div>
    </div>
  );
}
