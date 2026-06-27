// Auto-reorder smoke tests (Item 16)
// Zero-dep node --test — asserts that the settings page, badge, and
// inventory integration carry the expected shape and testids without
// booting a browser.
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { test } from "node:test";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const root = resolve(here, "..");
const read = (p) => readFileSync(resolve(root, p), "utf8");

const SETTINGS = read("src/app/[locale]/(app)/settings/auto-reorder/page.tsx");
const BADGE = read("src/components/inventory/AutoReorderBadge.tsx");
const INVENTORY = read("src/app/[locale]/(app)/inventory/page.tsx");
const EN = JSON.parse(read("messages/en.json"));
const SV = JSON.parse(read("messages/sv.json"));

test("test_settings_page_renders", () => {
  assert.match(SETTINGS, /data-testid="auto-reorder-settings-page"/);
  assert.match(SETTINGS, /useTranslations\("autoReorder"\)/);
});

test("test_enable_toggle_visible", () => {
  assert.match(SETTINGS, /data-testid="auto-reorder-enable-toggle"/);
  assert.match(SETTINGS, /enabled_label/);
});

test("test_schedule_days_selectable", () => {
  // Day buttons use a templated testid `auto-reorder-day-${d.code}`
  assert.match(SETTINGS, /auto-reorder-day-\$\{d\.code\}/);
  for (const code of ["MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN"]) {
    assert.ok(SETTINGS.includes(code), `day code ${code} missing`);
  }
  assert.match(SETTINGS, /data-testid="auto-reorder-time-input"/);
});

test("test_preview_table_renders", () => {
  assert.match(SETTINGS, /data-testid="auto-reorder-preview-button"/);
  assert.match(SETTINGS, /data-testid="auto-reorder-preview-(table|empty)"/);
  assert.match(SETTINGS, /\/api\/auto-reorder\/preview/);
});

test("test_run_now_button_visible", () => {
  assert.match(SETTINGS, /data-testid="auto-reorder-run-now-button"/);
  assert.match(SETTINGS, /\/api\/auto-reorder\/run/);
});

test("test_run_history_table_renders", () => {
  assert.match(SETTINGS, /data-testid="auto-reorder-history-table"/);
  assert.match(SETTINGS, /\/api\/auto-reorder\/runs/);
});

test("test_per_product_supplier_field_translated", () => {
  // We have i18n keys ready; per-product UI migration will consume them.
  assert.ok(EN.autoReorder.product_supplier_label);
  assert.ok(SV.autoReorder.product_supplier_label);
  assert.ok(EN.autoReorder.product_include_label);
  assert.ok(EN.autoReorder.product_qty_override_label);
  assert.ok(EN.autoReorder.product_buffer_label);
});

test("test_auto_badge_shown_when_enabled", () => {
  assert.match(BADGE, /data-testid="auto-reorder-badge-auto"/);
  // Must check preferred supplier presence before rendering "Auto"
  assert.match(BADGE, /preferredSupplierId/);
  assert.match(BADGE, /badge_auto/);
});

test("test_no_supplier_badge_shown", () => {
  assert.match(BADGE, /data-testid="auto-reorder-badge-no-supplier"/);
  assert.match(BADGE, /badge_no_supplier/);
  // Badge must NOT render at all when auto-reorder is disabled
  assert.match(BADGE, /if \(!autoReorderEnabled\) \{[\s\S]*return null;/);
});

test("test_nothing_to_reorder_empty_state", () => {
  assert.match(SETTINGS, /data-testid="auto-reorder-preview-empty"/);
  assert.ok(EN.autoReorder.nothing_to_reorder);
  assert.ok(SV.autoReorder.nothing_to_reorder);
});

test("test_inventory_page_uses_badge", () => {
  assert.match(
    INVENTORY,
    /import \{ AutoReorderBadge \} from "@\/components\/inventory\/AutoReorderBadge"/,
  );
  assert.match(INVENTORY, /<AutoReorderBadge/);
});

test("test_i18n_forms_and_autoreorder_parity", () => {
  const enKeys = Object.keys(EN.autoReorder).sort();
  const svKeys = Object.keys(SV.autoReorder).sort();
  assert.deepEqual(
    enKeys,
    svKeys,
    "en.json and sv.json must have the same autoReorder keys",
  );
  // Must have translations for every spec'd key
  for (const k of [
    "title",
    "description",
    "enabled_label",
    "schedule_label",
    "notify_email_label",
    "notify_email_hint",
    "preview_button",
    "run_now_button",
    "run_history_title",
    "badge_auto",
    "badge_no_supplier",
    "nothing_to_reorder",
    "run_success",
    "run_empty",
    "run_failed",
  ]) {
    assert.ok(EN.autoReorder[k], `en missing autoReorder.${k}`);
    assert.ok(SV.autoReorder[k], `sv missing autoReorder.${k}`);
  }
});
