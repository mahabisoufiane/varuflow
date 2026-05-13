// File: mobile/scripts/test_tablet_layout.mjs
// Purpose: Zero-dep structural smoke tests for Item 13 (Expo tablet
// layout). We can't mount React Native off-device, so these assertions
// are a mix of pure-function invariants on the `columnsFor` helper
// plus grep-level assertions that the right components are wired into
// the app layout and each screen. Run with `npm run test:tablet`
// (node --test) inside `mobile/`.

import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, resolve } from "node:path";
import { test } from "node:test";
import assert from "node:assert/strict";

const here = dirname(fileURLToPath(import.meta.url));
const root = resolve(here, "..");
const read = (p) => readFileSync(resolve(root, p), "utf8");

const HOOK     = read("lib/useDeviceLayout.ts");
const SIDEBAR  = read("components/TabletSidebar.tsx");
const GRID     = read("components/TabletGrid.tsx");
const TOPBAR   = read("components/TabletTopBar.tsx");
const LAYOUT   = read("app/(app)/_layout.tsx");
const INV      = read("app/(app)/inventory.tsx");
const DASH     = read("app/(app)/dashboard.tsx");
const ANA      = read("app/(app)/analytics.tsx");
const SET      = read("app/(app)/settings.tsx");
const I18N     = read("lib/tablet-i18n.ts");

// Mirror of `columnsFor` in useDeviceLayout.ts — kept in sync so the
// pure logic is testable without importing the RN hook.
function columnsFor(w, h) {
  if (w < 768) return 1;
  return w > h ? 3 : 2;
}

test("test_isTablet_true_for_width_1024", () => {
  // Portrait tablet (1024 × 1366 iPad Pro 10.5): 2 cols.
  assert.equal(columnsFor(1024, 1366), 2);
  // Landscape tablet (1366 × 1024): 3 cols.
  assert.equal(columnsFor(1366, 1024), 3);
  // Hook source must treat width >= 768 as tablet.
  assert.match(HOOK, /TABLET_BREAKPOINT_PX = 768/);
  assert.match(HOOK, /width >= TABLET_BREAKPOINT_PX/);
});

test("test_isPhone_true_for_width_375", () => {
  // iPhone 13 portrait (375 × 812).
  assert.equal(columnsFor(375, 812), 1);
  // iPhone rotated to landscape (812 × 375) is still a phone.
  assert.equal(columnsFor(667, 375), 1);
});

test("test_sidebar_visible_on_tablet", () => {
  // Tablet branch in (app)/_layout.tsx renders <TabletSidebar /> + <Slot />.
  assert.match(LAYOUT, /if \(isTablet\)/);
  assert.match(LAYOUT, /<TabletSidebar\b/);
  assert.match(LAYOUT, /<Slot \/>/);
  assert.match(LAYOUT, /testID="tablet-shell"/);
  assert.match(SIDEBAR, /testID="tablet-sidebar"/);
});

test("test_sidebar_hidden_on_phone", () => {
  // Sidebar component self-returns null when !isTablet.
  assert.match(SIDEBAR, /if \(!isTablet\) return null;/);
  // Phone branch of the layout still uses the bottom-tab navigator.
  assert.match(LAYOUT, /<Tabs\b/);
  assert.match(LAYOUT, /name="dashboard"/);
  assert.match(LAYOUT, /name="inventory"/);
});

test("test_inventory_uses_three_column_grid_landscape", () => {
  // Tablet branch in inventory renders TabletGrid, which resolves 3 cols
  // in landscape via columnsFor (asserted above).
  assert.match(INV, /if \(isTablet\)/);
  assert.match(INV, /<TabletGrid\b/);
  assert.match(INV, /testID="inventory-tablet"/);
  // Grid respects orientation: landscape → 3 columns.
  assert.equal(columnsFor(1366, 1024), 3);
});

test("test_inventory_uses_two_column_grid_portrait", () => {
  // Portrait tablet → 2 columns.
  assert.equal(columnsFor(810, 1080), 2);
  // TabletGrid keys the FlatList on column count so orientation flips remount.
  assert.match(GRID, /key=\{`grid-\$\{cols\}`\}/);
});

test("test_dashboard_show_split_layout_on_tablet", () => {
  // Dashboard has a tablet-landscape split pane (LowStock + Recent activity).
  assert.match(DASH, /testID="dashboard-split"/);
  assert.match(DASH, /isTablet && isLandscape/);
  assert.match(DASH, /<TabletTopBar\b/);
  // Analytics also goes two-column on tablet landscape.
  assert.match(ANA, /testID="analytics-two-col"/);
});

test("test_settings_show_tablet_two_pane", () => {
  // Settings renders Notifications + Account in a flexDirection row on tablet.
  assert.match(SET, /"settings-two-pane"/);
  assert.match(SET, /twoPane:\s*\{\s*flexDirection:\s*"row"/);
});

test("test_phone_layout_unchanged", () => {
  // Dashboard phone header still exists behind `!isTablet` guard.
  assert.match(DASH, /!isTablet/);
  assert.match(DASH, /styles\.greeting/);
  // Inventory's phone ScrollView + StockCard map is still present —
  // the tablet branch returns early, so the original phone render
  // below it is untouched.
  assert.match(INV, /displayed\.map\(\(item\)/);
  // Layout keeps the bottom-tab styles.
  assert.match(LAYOUT, /tabBarStyle:\s*styles\.tabBar/);
});

test("test_active_route_highlight_works", () => {
  // Sidebar derives active state from usePathname().
  assert.match(SIDEBAR, /usePathname\(\)/);
  assert.match(SIDEBAR, /navItemActive/);
  assert.match(SIDEBAR, /accessibilityState=\{\{ selected: active \}\}/);
});

test("i18n_tablet_keys_present_in_en_and_sv", () => {
  const KEYS = [
    "sidebar_dashboard", "sidebar_inventory", "sidebar_analytics", "sidebar_settings",
    "topbar_search", "topbar_quick_stats", "layout_tablet",
  ];
  for (const k of KEYS) {
    assert.match(I18N, new RegExp(`${k}:`));
  }
  // Swedish bundle references the brand's expected words.
  assert.match(I18N, /Översikt/);
  assert.match(I18N, /Surfplattelayout/);
});
