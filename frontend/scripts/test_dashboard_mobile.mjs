// File: frontend/scripts/test_dashboard_mobile.mjs
// Purpose: Zero-dep structural smoke tests for Item 12 (mobile dashboard
// redesign, MobileBottomNav, pull-to-refresh, RecentActivity). Runs via
// `npm run test:dashboard`. These are grep-level assertions against the
// source files — no React runtime.

import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, resolve } from "node:path";
import { test } from "node:test";
import assert from "node:assert/strict";

const here = dirname(fileURLToPath(import.meta.url));
const root = resolve(here, "..");
const read = (p) => readFileSync(resolve(root, p), "utf8");

const DASH    = read("src/app/[locale]/(app)/dashboard/page.tsx");
const METRIC  = read("src/components/dashboard/MetricCard.tsx");
const CAROUS  = read("src/components/dashboard/AiCardCarousel.tsx");
const ACTIV   = read("src/components/dashboard/RecentActivity.tsx");
const NAV     = read("src/components/MobileBottomNav.tsx");
const FAB     = read("src/components/MobileQuickActions.tsx");
const P2R     = read("src/hooks/usePullToRefresh.ts");
const NAV_H   = read("src/hooks/useBottomNavHeight.ts");
const QA      = read("src/lib/quick-actions.ts");
const LAYOUT  = read("src/app/[locale]/(app)/layout.tsx");
const EN      = JSON.parse(read("messages/en.json"));
const SV      = JSON.parse(read("messages/sv.json"));

// ── Metric cards ────────────────────────────────────────────────────────────

test("test_metric_cards_stack_on_mobile", () => {
  // The KPI strip uses grid-cols-1 at mobile width (was grid-cols-2).
  assert.match(DASH, /grid-cols-1 md:grid-cols-4/);
  // The standalone MetricCard component renders full-width cards.
  assert.match(METRIC, /w-full/);
  assert.match(METRIC, /data-testid="metric-card"/);
});

test("test_metric_cards_grid_on_desktop", () => {
  // Desktop branch of the same grid is preserved.
  assert.match(DASH, /md:grid-cols-4/);
  assert.match(DASH, /data-testid="kpi-strip"/);
});

// ── AI carousel ─────────────────────────────────────────────────────────────

test("test_ai_carousel_rendered", () => {
  // Carousel maps over cards, uses scroll-snap.
  assert.match(CAROUS, /cards\.map/);
  assert.match(CAROUS, /scroll-snap-type:x_mandatory/);
  assert.match(CAROUS, /data-testid="ai-carousel"/);
  assert.match(CAROUS, /data-testid="ai-carousel-dots"/);
});

test("test_ai_carousel_empty_state", () => {
  assert.match(CAROUS, /cards\.length === 0/);
  assert.match(CAROUS, /data-testid="ai-carousel-empty"/);
  assert.match(CAROUS, /ai_cards_empty/);
});

// ── Pull to refresh ─────────────────────────────────────────────────────────

test("test_pull_indicator_hidden_initially", () => {
  // Indicator element lives above the viewport (top: -60px).
  assert.match(DASH, /data-testid="dashboard-pull-indicator"/);
  assert.match(DASH, /top: "-60px"/);
  // Hook only arms when window.scrollY === 0.
  assert.match(P2R, /window\.scrollY > 0/);
  // Haptic tick on trigger when available.
  assert.match(P2R, /navigator\.vibrate/);
});

// ── Bottom nav ──────────────────────────────────────────────────────────────

test("test_bottom_nav_visible_mobile", () => {
  // MobileBottomNav is rendered in the app layout, always mounted client-side.
  assert.match(LAYOUT, /<MobileBottomNav \/>/);
  assert.match(LAYOUT, /from "@\/components\/MobileBottomNav"/);
  assert.match(NAV, /data-testid="mobile-bottom-nav"/);
  // Five tabs total (home, inventory, invoices, pos, more).
  assert.match(NAV, /data-testid=\{`nav-\$\{tab\.id\}`\}/);
});

test("test_bottom_nav_hidden_desktop", () => {
  // `md:hidden` keeps the nav off ≥ 768 px. Appears on the <nav>,
  // the backdrop, and the drawer.
  const count = (NAV.match(/md:hidden/g) ?? []).length;
  assert.ok(count >= 3, `expected md:hidden ≥ 3 times, saw ${count}`);
});

test("test_nav_home_active_on_dashboard", () => {
  // Active-tab resolution lives in `getActive(pathname)`.
  assert.match(NAV, /getActive\(pathname\)/);
  assert.match(NAV, /if \(stripped === "\/dashboard"\) return "home"/);
});

test("test_nav_more_opens_drawer", () => {
  // Tapping a tab with id "more" flips `setMoreOpen(true)`.
  assert.match(NAV, /if \(tab\.id === "more"\) \{ setMoreOpen\(true\); return; \}/);
  assert.match(NAV, /data-testid="nav-more-drawer"/);
  // Escape closes the drawer.
  assert.match(NAV, /e\.key === "Escape"/);
});

test("test_nav_hidden_on_pos", () => {
  // Route-gating uses the new `isNavHidden` helper (symmetrical to isFabHidden).
  assert.match(NAV, /isNavHidden\(pathname\)/);
  assert.match(QA, /export function isNavHidden/);
  assert.match(QA, /NAV_HIDDEN_ROUTES = \["\/pos", "\/onboarding", "\/auth"\]/);
});

// ── FAB stacks above nav ────────────────────────────────────────────────────

test("test_fab_position_above_bottom_nav", () => {
  // FAB reads `--bottom-nav-height` so it sits 16 px above the nav.
  assert.match(FAB, /var\(--bottom-nav-height, 64px\) \+ 16px/);
  // The CSS var is published by useBottomNavHeight.
  assert.match(NAV_H, /--bottom-nav-height/);
  // MobileBottomNav invokes the hook.
  assert.match(NAV, /useBottomNavHeight\(\)/);
});

// ── Recent activity + i18n ──────────────────────────────────────────────────

test("recent_activity_fetches_endpoint", () => {
  assert.match(ACTIV, /\/api\/analytics\/activity\?limit=5/);
  assert.match(ACTIV, /data-testid="recent-activity"/);
});

test("i18n_dashboard_keys_present_in_en_and_sv", () => {
  const KEYS = [
    "greeting_morning", "greeting_afternoon", "greeting_evening",
    "pull_to_refresh", "release_to_refresh", "refreshing",
    "metric_revenue", "metric_unpaid", "metric_low_stock", "metric_overdue",
    "ai_cards_title", "ai_cards_empty",
    "recent_activity", "view_all",
    "nav_home", "nav_inventory", "nav_invoices", "nav_pos", "nav_more",
  ];
  for (const k of KEYS) {
    assert.ok(EN.dashboard?.[k], `en.json missing dashboard.${k}`);
    assert.ok(SV.dashboard?.[k], `sv.json missing dashboard.${k}`);
  }
});
