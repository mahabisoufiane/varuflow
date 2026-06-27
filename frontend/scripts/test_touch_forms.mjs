// File: frontend/scripts/test_touch_forms.mjs
// Purpose: Item 15 smoke tests — touch-friendly form primitives.
// Run with: `npm run test:touch-forms` (from frontend/)
//
// Zero-dep node --test pattern matching test_dashboard_mobile.mjs.
// Grep-asserts structural guarantees against the shared component
// source files; no React render or jsdom involved.

import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { test } from "node:test";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const root = resolve(here, "..");
const read = (p) => readFileSync(resolve(root, p), "utf8");

const FIELD   = read("src/components/forms/FormField.tsx");
const SECTION = read("src/components/forms/FormSection.tsx");
const ACTIONS = read("src/components/forms/MobileFormActions.tsx");
const HOOK    = read("src/hooks/useMobileForm.ts");
const EN      = read("messages/en.json");
const SV      = read("messages/sv.json");

// 44 px touch target is min-h-11 in Tailwind (11 × 4 = 44px).
test("test_input_height_meets_minimum", () => {
  assert.match(FIELD, /min-h-11/);
  // Primary action on mobile is 56px (min-h-14) — see MobileFormActions.
  assert.match(ACTIONS, /min-h-14/);
});

test("test_label_above_input", () => {
  // The LabelEl block is rendered BEFORE the input element inside the
  // wrapper div, never as a placeholder-only control.
  // We assert the presence of an <label htmlFor={resolvedId}> ahead of
  // the <input id={resolvedId} ...> block.
  const labelIdx = FIELD.indexOf("<label");
  const inputIdx = FIELD.indexOf("<input");
  assert.ok(labelIdx !== -1 && inputIdx !== -1);
  assert.ok(labelIdx < inputIdx, "label must be declared above input in source");
});

test("test_numeric_keyboard_applied", () => {
  // The hook maps kind='number' → inputMode='numeric' and 'decimal' → 'decimal'.
  assert.match(HOOK, /case "number":\s*return "numeric"/);
  assert.match(HOOK, /case "decimal":\s*return "decimal"/);
  // And FormField actually passes inputMode through to the <input>.
  assert.match(FIELD, /inputMode=\{props\.inputMode \?\? inputModeFor\(/);
  // Number kind also applies pattern="[0-9]*" by default.
  assert.match(FIELD, /pattern={\s*pattern \?\? \(kind === "number" \? "\[0-9\]\*"/);
});

test("test_date_picker_mobile_mode", () => {
  // FormField renders native type="date" for kind="date"; mobile
  // browsers open a native date picker for this type, which is the
  // recommended lightweight path (no custom picker dep).
  assert.match(FIELD, /kind === "date"\s*\?\s*"date"/);
});

test("test_inline_errors_visible", () => {
  // Errors render in a role="alert" paragraph immediately after the
  // control, with data-testid suffix "-error" and red text.
  assert.match(FIELD, /role="alert"/);
  assert.match(FIELD, /text-vf-danger/);
  assert.match(FIELD, /-error`/);
  assert.match(FIELD, /aria-invalid=\{hasError \|\| undefined\}/);
  assert.match(FIELD, /aria-describedby=\{describedBy\}/);
});

test("test_first_error_scrolled_into_view", () => {
  // The hook exposes scrollToFirstError + the submit wrapper calls it
  // on native form invalidity. Both branches are asserted.
  assert.match(HOOK, /export function scrollToFirstError/);
  assert.match(HOOK, /scrollIntoView\(\{ behavior: "smooth", block: "center" \}\)/);
  assert.match(HOOK, /form\.checkValidity\(\)/);
});

test("test_sticky_mobile_action_bar", () => {
  // MobileFormActions is fixed to the viewport bottom on phone, with
  // safe-area bottom padding, and un-fixes on md: screens.
  assert.match(ACTIONS, /fixed inset-x-0 bottom-0/);
  assert.match(ACTIONS, /env\(safe-area-inset-bottom\)/);
  assert.match(ACTIONS, /md:static/);
  assert.match(ACTIONS, /data-testid={rest\["data-testid"\] \?\? "mobile-form-actions"}/);
});

test("test_checkbox_label_clickable", () => {
  // Checkbox / toggle renders the <label> as the full-row clickable
  // target with min-h-11 so the label area — not just the tiny icon —
  // is tappable.
  assert.match(FIELD, /props\.kind === "checkbox" \|\| props\.kind === "toggle"/);
  const checkboxBlock = FIELD.slice(
    FIELD.indexOf('props.kind === "checkbox" || props.kind === "toggle"'),
    FIELD.indexOf("// ── Textarea"),
  );
  assert.match(checkboxBlock, /<label/);
  assert.match(checkboxBlock, /htmlFor=\{resolvedId\}/);
  assert.match(checkboxBlock, /min-h-11/);
  assert.match(checkboxBlock, /cursor-pointer/);
});

test("test_required_field_missing_shows_message", () => {
  // The required marker is rendered when props.required is true, and
  // the error text renders in a role="alert" when props.error is set.
  // Native `required` flag is also forwarded on every input type.
  assert.match(FIELD, /props\.required && <span aria-hidden className="text-vf-danger">\*/);
  assert.match(FIELD, /required=\{props\.required\}/);
});

test("test_form_values_preserved_after_validation_failure", () => {
  // The hook's handleSubmit calls e.preventDefault() on invalid forms,
  // which keeps React-controlled state intact rather than resetting.
  // `value` / `defaultValue` are pass-through props — FormField never
  // clears them on error.
  assert.match(HOOK, /e\.preventDefault\(\);/);
  // No setState that wipes the value exists in FormField — assert
  // there's no call that resets the input value programmatically.
  assert.doesNotMatch(FIELD, /\.value\s*=\s*""/);
  assert.doesNotMatch(FIELD, /setValue\(""\)/);
});

// ── i18n parity ───────────────────────────────────────────────────────

test("i18n_forms_keys_en_sv_parity", () => {
  const en = JSON.parse(EN);
  const sv = JSON.parse(SV);
  assert.ok(en.forms, "en.forms must exist");
  assert.ok(sv.forms, "sv.forms must exist");
  const required = [
    "save", "cancel", "delete", "required", "invalid", "search",
    "optional", "loading", "clear", "choose_date", "select_option",
    "next", "previous", "done",
  ];
  for (const k of required) {
    assert.ok(en.forms[k], `en.forms.${k} missing`);
    assert.ok(sv.forms[k], `sv.forms.${k} missing`);
  }
});

test("section_card_renders_on_desktop_stacks_on_mobile", () => {
  // FormSection is edge-to-edge on phone, bordered card on ≥md — the
  // Tailwind class set is the source of truth.
  assert.match(SECTION, /md:rounded-2xl md:border/);
  assert.match(SECTION, /md:grid md:grid-cols-2/);
});
