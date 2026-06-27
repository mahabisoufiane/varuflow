#!/usr/bin/env node
// File: frontend/scripts/test_pos_tablet.mjs
// Purpose: Smoke-test for the tablet-optimized POS (Item 10).
//
// Why structural assertions instead of Vitest + RTL: the frontend has
// no Jest / Vitest / jsdom dependency chain yet; every other test in
// this repo is a zero-dep `node --test` script that regex-matches
// known tokens in the source (see test_offline_queue.mjs, test_seo_pages.mjs).
// This module follows the same pattern so a developer clone needs
// nothing beyond Node 20 to run it. When the team picks a real
// front-end test harness we'll replace this file with component
// tests, but the invariants below still catch the regressions listed
// in the Item 10 spec:
//
//   * Two-column tablet layout present (md:grid-cols-[60%_40%])
//   * Single-column mobile layout present (grid-cols-1)
//   * Product-card click dispatches addToCart
//   * Barcode Enter handler calls the lookup endpoint
//   * +/- controls call updateQty; hitting 0 removes the item
//   * Complete-sale button disabled on empty cart
//   * Cash-change formula is `max(0, cashTendered - total)`
//   * Receipt modal rendered via `{lastSale && <PosReceiptModal />}`
//   * "/" keyboard shortcut focuses the search input
//   * Z-report modal download uses `/api/pos/sessions/*/z-report?format=pdf`

import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import test from "node:test";
import assert from "node:assert/strict";

const HERE = dirname(fileURLToPath(import.meta.url));
const ROOT = resolve(HERE, "..");

const POS_PAGE = readFileSync(resolve(ROOT, "src/app/[locale]/(app)/pos/page.tsx"), "utf8");
const POS_STORE = readFileSync(resolve(ROOT, "src/lib/pos-store.tsx"), "utf8");
const GRID = readFileSync(resolve(ROOT, "src/components/pos/PosProductGrid.tsx"), "utf8");
const CART = readFileSync(resolve(ROOT, "src/components/pos/PosCartPanel.tsx"), "utf8");
const RECEIPT = readFileSync(resolve(ROOT, "src/components/pos/PosReceiptModal.tsx"), "utf8");
const SESSION = readFileSync(resolve(ROOT, "src/components/pos/PosSessionControls.tsx"), "utf8");
const KB = readFileSync(resolve(ROOT, "src/components/pos/usePosKeyboard.ts"), "utf8");

test("two_column_layout_on_tablet — md breakpoint 60/40 grid present", () => {
  assert.match(POS_PAGE, /md:grid-cols-\[60%_40%\]/);
  assert.match(POS_PAGE, /data-testid="pos-left-column"/);
  assert.match(POS_PAGE, /data-testid="pos-right-column"/);
});

test("single_column_on_mobile — default grid-cols-1, cart hidden until md", () => {
  assert.match(POS_PAGE, /grid-cols-1/);
  // Cart panel is gated behind md:block; mobile sees the bottom-sheet toggle.
  assert.match(POS_PAGE, /hidden[^"]*md:block/);
  assert.match(POS_PAGE, /data-testid="pos-mobile-cart-toggle"/);
});

test("add_product_to_cart — grid onClick calls addToCart via store", () => {
  assert.match(GRID, /addToCart\(p,\s*1\)/);
  assert.match(POS_STORE, /export function PosProvider/);
  assert.match(POS_STORE, /addToCart:/);
});

test("barcode_input_adds_product — Enter triggers lookup + addToCart", () => {
  assert.match(GRID, /handleBarcode\(query\)/);
  assert.match(GRID, /\/api\/pos\/lookup\?barcode=/);
});

test("quantity_increment_decrement — +/− buttons call updateQty; qty<=0 removes", () => {
  assert.match(CART, /updateQty\(it\.product\.id,\s*it\.qty\s*\+\s*1\)/);
  assert.match(CART, /updateQty\(it\.product\.id,\s*it\.qty\s*-\s*1\)/);
  assert.match(POS_STORE, /if \(qty <= 0\) \{\s*removeFromCart\(productId\);/);
});

test("complete_sale_disabled_when_empty — button `disabled={cart.length === 0 || submitting || !session}`", () => {
  assert.match(CART, /disabled=\{cart\.length === 0/);
  assert.match(CART, /!session/);
});

test("cash_change_calculation — changeDue = max(0, cashTendered - total)", () => {
  assert.match(CART, /Math\.max\(0,\s*cashTendered\s*-\s*totals\.total\)/);
});

test("receipt_modal_appears_after_sale — rendered when lastSale set", () => {
  assert.match(POS_PAGE, /lastSale\s*&&\s*<PosReceiptModal \/>/);
  assert.match(RECEIPT, /data-testid="pos-receipt-modal"/);
  assert.match(RECEIPT, /dismissLastSale/);
});

test("keyboard_shortcut_focus_search — '/' or F1 focuses search ref", () => {
  assert.match(KB, /e\.key === ['"]\/['"]/);
  assert.match(KB, /e\.key === ['"]F1['"]/);
  assert.match(KB, /searchRef\.current\?\.focus\(\)/);
});

test("z_report_download — session modal POSTs PDF via ?format=pdf", () => {
  assert.match(SESSION, /\/api\/pos\/sessions\/\$\{session\.id\}\/z-report\?format=pdf/);
  assert.match(SESSION, /data-testid="pos-zreport-download"/);
});
