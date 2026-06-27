"use client";

// File: frontend/src/components/forms/MobileFormActions.tsx
// Purpose: Sticky bottom action bar for long forms on mobile (Item 15).
//
// Renders at the bottom of the viewport below `md:` with safe-area
// padding and a solid backdrop so the CTA never collides with the
// bottom nav. On ≥md we render inline so desktop forms keep their
// usual static submit row.

import * as React from "react";

export interface MobileFormActionsProps {
  primaryLabel: string;
  onPrimary?: React.ButtonHTMLAttributes<HTMLButtonElement>["onClick"];
  primaryType?: "submit" | "button";
  primaryDisabled?: boolean;
  primaryLoading?: boolean;

  secondaryLabel?: string;
  onSecondary?: () => void;

  destructiveLabel?: string;
  onDestructive?: () => void;

  visible?: boolean;
  className?: string;
  "data-testid"?: string;
}

export function MobileFormActions({
  primaryLabel,
  onPrimary,
  primaryType = "submit",
  primaryDisabled,
  primaryLoading,
  secondaryLabel,
  onSecondary,
  destructiveLabel,
  onDestructive,
  visible = true,
  className,
  ...rest
}: MobileFormActionsProps) {
  if (!visible) return null;

  return (
    <div
      data-testid={rest["data-testid"] ?? "mobile-form-actions"}
      className={[
        // Mobile: sticky to bottom of viewport with safe-area padding.
        // Desktop: static inline flex-row with right-aligned actions.
        "fixed inset-x-0 bottom-0 z-30 border-t border-white/10 bg-vf-bg-primary/95 backdrop-blur",
        "px-4 py-3",
        "[padding-bottom:max(env(safe-area-inset-bottom),0.75rem)]",
        "md:static md:inset-auto md:bottom-auto md:border-0 md:bg-transparent md:backdrop-blur-0",
        "md:p-0 md:[padding-bottom:0]",
        "flex items-center gap-2 md:justify-end",
        className,
      ]
        .filter(Boolean)
        .join(" ")}
    >
      {destructiveLabel && (
        <button
          type="button"
          onClick={onDestructive}
          className="
            min-h-11 rounded-xl border border-vf-danger/40 bg-vf-danger/10 px-4 text-sm
            font-medium text-vf-danger hover:bg-vf-danger/20
            focus:outline-none focus:ring-2 focus:ring-vf-danger/40
            md:mr-auto
          "
          data-testid="form-destructive-btn"
        >
          {destructiveLabel}
        </button>
      )}
      {secondaryLabel && (
        <button
          type="button"
          onClick={onSecondary}
          className="
            min-h-11 shrink-0 rounded-xl border border-white/10 bg-vf-bg-elevated px-4
            text-sm font-medium text-vf-text-secondary hover:bg-white/10
            focus:outline-none focus:ring-2 focus:ring-white/20
          "
          data-testid="form-secondary-btn"
        >
          {secondaryLabel}
        </button>
      )}
      <button
        type={primaryType}
        onClick={onPrimary}
        disabled={primaryDisabled || primaryLoading}
        className="
          min-h-14 flex-1 md:flex-none md:min-h-11
          rounded-xl bg-vf-accent px-5 text-sm font-semibold text-white
          shadow-sm hover:bg-vf-accent/90
          focus:outline-none focus:ring-2 focus:ring-vf-accent/50
          disabled:opacity-50 disabled:cursor-not-allowed
        "
        data-testid="form-primary-btn"
      >
        {primaryLoading ? "…" : primaryLabel}
      </button>
    </div>
  );
}

export default MobileFormActions;
