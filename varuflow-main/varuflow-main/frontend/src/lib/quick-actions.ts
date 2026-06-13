// File: src/lib/quick-actions.ts
// Purpose: Data-driven definitions for the mobile quick-action sheet
// (Item 11). Adding a sixth action means adding a row to the QUICK_ACTIONS
// array below — no component changes required.
//
// Each action either navigates (`to`) or opens a named inline view
// inside the bottom sheet (`view`). We never mix the two: actions that
// set `view` do NOT set `to`, and vice-versa. The rendering component
// (QuickActionSheet) switches on the presence of `view`.

import {
  PackagePlus,
  FilePlus,
  ScanBarcode,
  ShoppingCart,
  Banknote,
  type LucideIcon,
} from "lucide-react";

/** The list of inline-form views the sheet knows how to render.
 *  Keep in sync with the switch in `QuickActionSheet`. */
export type SheetView = "menu" | "stock_movement" | "quick_invoice" | "record_payment";

export interface QuickAction {
  id:
    | "ADD_STOCK_MOVEMENT"
    | "NEW_QUICK_INVOICE"
    | "SCAN_PRODUCT"
    | "QUICK_POS_SALE"
    | "RECORD_PAYMENT";
  icon: LucideIcon;
  labelKey: string;      // i18n key under `quickActions.*`
  colorClass: string;    // Tailwind classes for the icon tile (bg + text)
  /** Open a form view inside the sheet. Mutually exclusive with `to`. */
  view?: Exclude<SheetView, "menu">;
  /** Navigate directly to this path (locale-prefixed at render time).
   *  Mutually exclusive with `view`. */
  to?: string;
  /** Opens the camera scanner overlay above the sheet (SCAN_PRODUCT). */
  scan?: boolean;
}

export const QUICK_ACTIONS: QuickAction[] = [
  {
    id: "ADD_STOCK_MOVEMENT",
    icon: PackagePlus,
    labelKey: "quickActions.add_stock",
    colorClass: "bg-blue-100 text-blue-700",
    view: "stock_movement",
  },
  {
    id: "NEW_QUICK_INVOICE",
    icon: FilePlus,
    labelKey: "quickActions.new_invoice",
    colorClass: "bg-purple-100 text-purple-700",
    view: "quick_invoice",
  },
  {
    id: "SCAN_PRODUCT",
    icon: ScanBarcode,
    labelKey: "quickActions.scan_product",
    colorClass: "bg-amber-100 text-amber-700",
    scan: true,
  },
  {
    id: "QUICK_POS_SALE",
    icon: ShoppingCart,
    labelKey: "quickActions.quick_pos",
    colorClass: "bg-green-100 text-green-700",
    to: "/pos",
  },
  {
    id: "RECORD_PAYMENT",
    icon: Banknote,
    labelKey: "quickActions.record_payment",
    colorClass: "bg-emerald-100 text-emerald-700",
    view: "record_payment",
  },
];

/** Routes where the FAB must never appear. Checked via `usePathname()`
 *  startswith — note the locale prefix is stripped before the check. */
export const FAB_HIDDEN_ROUTES = ["/pos", "/onboarding", "/auth"] as const;

/** Routes where the mobile bottom nav must never appear. POS takes over
 *  the full viewport (Item 10); onboarding is a full-page wizard; auth
 *  doesn't have a nav. */
export const NAV_HIDDEN_ROUTES = ["/pos", "/onboarding", "/auth"] as const;

function stripLocale(pathname: string): string {
  return pathname.replace(/^\/[a-z]{2}(?=\/|$)/i, "") || "/";
}

export function isFabHidden(pathname: string | null): boolean {
  if (!pathname) return false;
  const stripped = stripLocale(pathname);
  return FAB_HIDDEN_ROUTES.some((r) => stripped === r || stripped.startsWith(`${r}/`));
}

export function isNavHidden(pathname: string | null): boolean {
  if (!pathname) return false;
  const stripped = stripLocale(pathname);
  return NAV_HIDDEN_ROUTES.some((r) => stripped === r || stripped.startsWith(`${r}/`));
}
