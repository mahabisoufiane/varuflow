"use client";

/**
 * AutoReorderBadge (Item 16)
 *
 * Visual signal on the inventory list for whether a product participates
 * in the auto-reorder sweep:
 *
 *   • "Auto"        — enabled AND has a preferred supplier set.
 *   • "No supplier" — enabled AND reorder_level > 0 AND stock is low but
 *                     no preferred supplier is set. This is the failure
 *                     state the owner most wants to see, so it renders
 *                     as a warning badge the eye catches first.
 *   • nothing       — auto-reorder disabled on the product.
 *
 * Kept deliberately dependency-light (no shadcn Badge import) so the
 * component works on any page that lists products, including ones that
 * haven't adopted the shared Badge wrapper yet.
 */
import { useTranslations } from "next-intl";
import { Repeat2, AlertTriangle } from "lucide-react";

export interface AutoReorderBadgeProps {
  autoReorderEnabled: boolean | null | undefined;
  preferredSupplierId?: string | null;
  reorderLevel?: number | null;
  currentStock?: number | null;
  className?: string;
}

export function AutoReorderBadge({
  autoReorderEnabled,
  preferredSupplierId,
  reorderLevel,
  currentStock,
  className,
}: AutoReorderBadgeProps) {
  const t = useTranslations("autoReorder");

  if (!autoReorderEnabled) {
    return null;
  }

  if (preferredSupplierId) {
    return (
      <span
        data-testid="auto-reorder-badge-auto"
        className={
          "inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[10px] font-semibold " +
          "bg-indigo-500/10 text-indigo-300 border border-indigo-500/30 " +
          (className ?? "")
        }
      >
        <Repeat2 className="h-3 w-3" />
        {t("badge_auto")}
      </span>
    );
  }

  // Enabled but no supplier AND stock is low → warn.
  const level = Number(reorderLevel ?? 0);
  const stock = Number(currentStock ?? 0);
  const isLow = level > 0 && stock <= level;
  if (!isLow) {
    return null;
  }

  return (
    <span
      data-testid="auto-reorder-badge-no-supplier"
      className={
        "inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[10px] font-semibold " +
        "bg-amber-500/10 text-amber-300 border border-amber-500/30 " +
        (className ?? "")
      }
    >
      <AlertTriangle className="h-3 w-3" />
      {t("badge_no_supplier")}
    </span>
  );
}

export default AutoReorderBadge;
