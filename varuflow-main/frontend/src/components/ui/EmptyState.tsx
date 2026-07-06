// File: src/components/ui/EmptyState.tsx
// Purpose: Reusable empty-state block — pairs an on-brand SVG illustration with
//   a title, description, and an optional call-to-action. Replaces the bare
//   icon-in-a-circle empty states so screens feel designed when there's no data.

import * as React from "react";
import { cn } from "@/lib/utils";

export interface EmptyStateProps {
  /** One of the components from @/components/illustrations. */
  illustration: React.ReactNode;
  title: string;
  description?: string;
  /** Optional CTA (button/link). Falsy values render nothing. */
  action?: React.ReactNode;
  className?: string;
}

export function EmptyState({
  illustration,
  title,
  description,
  action,
  className,
}: EmptyStateProps) {
  return (
    <div
      className={cn(
        "flex flex-col items-center justify-center px-6 py-14 text-center",
        className,
      )}
    >
      <div className="mb-6 w-[190px] max-w-full">{illustration}</div>
      <h3 className="text-base font-semibold vf-text-1">{title}</h3>
      {description && (
        <p className="mt-1.5 max-w-sm text-sm vf-text-m">{description}</p>
      )}
      {action ? <div className="mt-5">{action}</div> : null}
    </div>
  );
}
