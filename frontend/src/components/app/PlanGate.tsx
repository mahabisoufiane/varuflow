// File: src/components/app/PlanGate.tsx
// Purpose: Show feature preview to all plans, block non-qualifying plans with lock overlay
// Used by: Mobile app section, advanced analytics, API access, bulk import
// RULE: Features are always VISIBLE — never hidden. Lock overlay creates upgrade desire.

"use client";

import { Lock } from "lucide-react";
import { Link } from "@/i18n/navigation";
import type { Plan } from "@/lib/plan";
import { hasAccess } from "@/lib/plan";

interface PlanGateProps {
  requiredPlan: Plan;
  userPlan: Plan;
  children: React.ReactNode;
  featureName: string;
  /** Optional custom upgrade CTA label */
  ctaLabel?: string;
}

export function PlanGate({
  requiredPlan,
  userPlan,
  children,
  featureName,
  ctaLabel = "Upgrade Plan",
}: PlanGateProps) {
  if (hasAccess(userPlan, requiredPlan)) return <>{children}</>;

  return (
    <div className="relative">
      {/* Blurred preview — pointer events disabled so user cannot interact */}
      <div className="pointer-events-none select-none opacity-30 blur-[2px] grayscale">
        {children}
      </div>

      {/* Lock overlay */}
      <div className="absolute inset-0 flex flex-col items-center justify-center rounded-xl z-10 gap-3 p-4"
        style={{ background: "rgba(0,0,0,0.55)", backdropFilter: "blur(4px)" }}>
        <div className="flex h-12 w-12 items-center justify-center rounded-full border border-indigo-500/30 bg-indigo-500/20">
          <Lock className="h-5 w-5 text-indigo-400" />
        </div>
        <p className="text-sm font-semibold text-white text-center">{featureName}</p>
        <p className="text-xs text-slate-400 text-center max-w-[220px]">
          Available on the{" "}
          <span className="capitalize font-medium text-indigo-300">{requiredPlan}</span>{" "}
          plan and above.
        </p>
        <Link
          href="/pricing"
          className="mt-1 rounded-xl bg-indigo-600 px-4 py-2 text-sm font-semibold text-white transition-all duration-200 hover:bg-indigo-500 hover:scale-[1.02]"
        >
          {ctaLabel}
        </Link>
      </div>
    </div>
  );
}
