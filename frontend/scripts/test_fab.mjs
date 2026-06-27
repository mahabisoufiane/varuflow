// File: frontend/scripts/test_fab.mjs
// Purpose: Zero-dep structural smoke tests for the Item 11
// Mobile FAB + Bottom Sheet Quick Actions. Runs via `npm run test:fab`.
//
// These are grep-level assertions against the source files — we do not
// run React at this layer. Functional contracts of `isFabHidden()` are
// exercised with an on-the-fly regex reimplementation to keep the test
// file self-contained (no TypeScript import chain).

import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, resolve } from "node:path";
import { test } from "node:test";
import assert from "node:assert/strict";

const here = dirname(fileURLToPath(import.meta.url));
const root = resolve(here, "..");
const read = (p) => readFileSync(resolve(root, p), "utf8");

const FAB    = read("src/components/MobileQuickActions.tsx");
const SHEET  = read("src/components/QuickActionSheet.tsx");
const DATA   = read("src/lib/quick-actions.ts");
const LAYOUT = read("src/app/[locale]/(app)/layout.tsx");
const EN     = JSON.parse(read("messages/en.json"));
const SV     = JSON.parse(read("messages/sv.json"));

/** Mirrors `isFabHidden` from `src/lib/quick-actions.ts`. */
function isFabHidden(pathname) {
  if (!pathname) return false;
  const stripped = pathname.replace(/^\/[a-z]{2}(?=\/|$)/i, "") || "/";
  const HIDDEN = ["/pos", "/onboarding", "/auth"];
  return HIDDEN.some((r) => stripped === r || stripped.startsWith(`${r}/`));
}

test("test_fab_hidden_on_pos_page", () => {
  assert.equal(isFabHidden("/en/pos"), true);
  assert.equal(isFabHidden("/sv/pos"), true);
  assert.equal(isFabHidden("/en/onboarding/step-1"), true);
  assert.equal(isFabHidden("/en/auth/login"), true);
  assert.equal(isFabHidden("/en/dashboard"), false);
  // Guard for the pathname branch in the component.
  assert.match(FAB, /isFabHidden\(pathname\)/);
});

test("test_fab_hidden_on_desktop", () => {
  // Tailwind md: breakpoint hides the FAB at ≥ 768px.
  assert.match(FAB, /md:hidden/);
  // Backdrop and sheet should also carry md:hidden so they never leak.
  assert.ok(
    (FAB.match(/md:hidden/g) ?? []).length >= 3,
    "md:hidden must appear on FAB, backdrop, and sheet",
  );
});

test("test_fab_visible_on_mobile_authenticated", () => {
  // Mounted only inside the authenticated (app) layout.
  assert.match(LAYOUT, /<MobileQuickActions \/>/);
  assert.match(LAYOUT, /from "@\/components\/MobileQuickActions"/);
  // FAB is a fixed-position button (Item 12 moved `bottom` to a CSS
  // custom-property so it stacks above the bottom nav).
  assert.match(FAB, /fixed right-6/);
  assert.match(FAB, /data-testid="mobile-fab"/);
});

test("test_sheet_opens_on_fab_tap", () => {
  // onClick toggles the open state.
  assert.match(FAB, /onClick=\{\(\) => setOpen\(\(v\) => !v\)\}/);
  assert.match(FAB, /aria-expanded=\{open\}/);
  assert.match(FAB, /role="dialog"/);
});

test("test_sheet_closes_on_backdrop_tap", () => {
  // Backdrop has an onClick that calls setOpen(false). Attribute order
  // isn't guaranteed — match either direction around the testid anchor.
  assert.ok(
    /setOpen\(false\)[\s\S]{0,400}?data-testid="mobile-fab-backdrop"|data-testid="mobile-fab-backdrop"[\s\S]{0,400}?setOpen\(false\)/.test(FAB),
    "backdrop must close the sheet via setOpen(false)",
  );
  assert.ok(FAB.includes('data-testid="mobile-fab-backdrop"'));
  // Escape key also closes.
  assert.match(FAB, /e\.key === "Escape"/);
});

test("test_sheet_closes_on_swipe_down", () => {
  assert.match(FAB, /onTouchStart/);
  assert.match(FAB, /onTouchMove/);
  assert.match(FAB, /onTouchEnd/);
  // Threshold — if swipe dy > 80px, close.
  assert.match(FAB, /dy > 80/);
});

test("test_five_actions_rendered", () => {
  const EXPECTED_IDS = [
    "ADD_STOCK_MOVEMENT",
    "NEW_QUICK_INVOICE",
    "SCAN_PRODUCT",
    "QUICK_POS_SALE",
    "RECORD_PAYMENT",
  ];
  for (const id of EXPECTED_IDS) {
    assert.ok(DATA.includes(`"${id}"`), `missing action id ${id}`);
  }
  // Sheet maps over QUICK_ACTIONS to render the 5 tiles.
  assert.match(SHEET, /QUICK_ACTIONS\.map/);
});

test("test_back_navigation_within_sheet", () => {
  // The back button resets the view to "menu".
  assert.match(SHEET, /setView\("menu"\)/);
  assert.match(SHEET, /data-testid="qa-back"/);
  assert.match(SHEET, /quickActions\.back/);
});

test("test_offline_badge_shows_when_pending", () => {
  // Badge is conditional on pendingCount() > 0.
  assert.match(FAB, /pending > 0/);
  assert.match(FAB, /pendingCount\(\)/);
  assert.match(FAB, /data-testid="mobile-fab-badge"/);
  // Poll every 5s, matching OfflineIndicator pattern.
  assert.match(FAB, /setInterval\(refresh, 5000\)/);
});

test("test_offline_toast_on_submit_offline", () => {
  // All three inline forms surface the offline-queued toast when
  // navigator.onLine === false at submit time.
  const offlineChecks = SHEET.match(/navigator\.onLine === false/g) ?? [];
  assert.ok(offlineChecks.length >= 3, "expected 3 offline-aware submit paths");
  assert.match(SHEET, /quickActions\.offline_queued/);
});

test("i18n_keys_present_in_en_and_sv", () => {
  const KEYS = [
    "sheet_title", "add_stock", "new_invoice", "scan_product",
    "quick_pos", "record_payment", "stock_movement_success",
    "invoice_created", "open_invoice", "payment_recorded",
    "product_not_found", "create_new_product", "offline_queued",
    "back", "submit", "pending_sync_badge",
  ];
  for (const k of KEYS) {
    assert.ok(EN.quickActions?.[k], `en.json missing quickActions.${k}`);
    assert.ok(SV.quickActions?.[k], `sv.json missing quickActions.${k}`);
  }
});
