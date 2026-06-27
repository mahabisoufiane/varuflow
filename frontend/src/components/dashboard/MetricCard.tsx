"use client";

// File: src/components/dashboard/MetricCard.tsx
// Purpose: Mobile-first metric tile used on the dashboard. Full width
// by default (stacks vertically when siblings render in a `grid-cols-1`
// container). Layout is horizontal inside the card:
//
//   ┌──────────────────────────────────────────────┐
//   │ [icon]                 123 456 kr            │
//   │ Label                  ↑12%                  │
//   └──────────────────────────────────────────────┘
//
// Desktop dashboards still use the existing `KpiCard` — this component
// is for the mobile stack only.

import Link from "next/link";
import { type LucideIcon, ArrowUpRight, ArrowDownRight, Minus } from "lucide-react";
import { cn } from "@/lib/utils";

export type DeltaType = "up" | "down" | "zero";

export interface MetricCardProps {
  icon: LucideIcon;
  label: string;
  value: string;
  /** Rendered after the delta icon, e.g. "12% vs yesterday". */
  delta?: string;
  deltaType?: DeltaType;
  /** Tailwind classes for the icon tile background + text colour. */
  colorClass?: string;
  href?: string;
  onClick?: () => void;
}

const DELTA_STYLES: Record<DeltaType, { text: string; bg: string; icon: LucideIcon }> = {
  up:   { text: "text-emerald-600", bg: "bg-emerald-50 dark:bg-emerald-500/10", icon: ArrowUpRight   },
  down: { text: "text-red-600",     bg: "bg-red-50 dark:bg-red-500/10",         icon: ArrowDownRight },
  zero: { text: "text-gray-500",    bg: "bg-gray-100 dark:bg-white/5",          icon: Minus          },
};

export default function MetricCard({
  icon: Icon,
  label,
  value,
  delta,
  deltaType = "zero",
  colorClass = "bg-indigo-100 text-indigo-700",
  href,
  onClick,
}: MetricCardProps) {
  const d = DELTA_STYLES[deltaType];
  const DeltaIcon = d.icon;

  const body = (
    <div
      data-testid="metric-card"
      className="flex min-h-[80px] w-full items-center gap-4 rounded-2xl border border-gray-200 bg-white p-4 shadow-sm transition-transform active:scale-[0.98] dark:border-white/10 dark:bg-white/5"
    >
      <div className="flex flex-col items-center gap-1">
        <span className={cn("flex h-10 w-10 items-center justify-center rounded-full", colorClass)}>
          <Icon className="h-5 w-5" />
        </span>
        <span className="max-w-[68px] text-center text-[10px] font-medium leading-tight text-gray-500 dark:text-gray-400">
          {label}
        </span>
      </div>
      <div className="ml-auto flex flex-col items-end gap-1">
        <span className="text-3xl font-bold tabular-nums leading-none text-gray-900 dark:text-white">
          {value}
        </span>
        {delta && (
          <span
            className={cn(
              "inline-flex items-center gap-0.5 rounded-full px-2 py-0.5 text-[11px] font-semibold",
              d.text,
              d.bg,
            )}
          >
            <DeltaIcon className="h-3 w-3" />
            {delta}
          </span>
        )}
      </div>
    </div>
  );

  if (href) {
    return <Link href={href} className="block">{body}</Link>;
  }
  if (onClick) {
    return (
      <button type="button" onClick={onClick} className="block w-full text-left">
        {body}
      </button>
    );
  }
  return body;
}
