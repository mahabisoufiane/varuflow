#!/usr/bin/env node
// File: frontend/scripts/test_seo_pages.mjs
// Purpose: Zero-dependency smoke test for the Swedish SEO landing
// pages. Validates that:
//   • /bransch/[slug] exports the five required slugs
//   • /jämför/[competitor] exports the four required competitors
//   • Each metaTitle/metaDescription contains the expected Swedish
//     keywords (catching accidental English-only copy).
//
// Invocation: `node frontend/scripts/test_seo_pages.mjs`. Intentionally
// a plain Node script — the frontend has no unit-test harness yet and
// pulling in Jest / Vitest just for this single module is not worth it.
//
// Strategy: read the .ts source files as text and regex-match expected
// tokens. This avoids a TS runtime dependency while still catching
// the regressions we care about (renamed / removed slugs, missing
// Swedish keywords, broken metadata shape).

import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, resolve } from "node:path";
import test from "node:test";
import assert from "node:assert/strict";

const HERE = dirname(fileURLToPath(import.meta.url));
const ROOT = resolve(HERE, "..");

const INDUSTRIES_PATH = resolve(
  ROOT,
  "src/app/[locale]/(marketing)/bransch/[slug]/industries.ts",
);
const COMPETITORS_PATH = resolve(
  ROOT,
  "src/app/[locale]/(marketing)/jämför/[competitor]/competitors.ts",
);
const SITEMAP_PATH = resolve(ROOT, "src/app/sitemap.ts");

const EXPECTED_INDUSTRIES = [
  "grossist",
  "livsmedel",
  "byggmaterial",
  "klaeder",
  "elektronik",
];
const EXPECTED_COMPETITORS = ["fortnox", "visma", "excel", "specter"];

test("industries.ts exports all five required slugs", () => {
  const src = readFileSync(INDUSTRIES_PATH, "utf8");
  for (const slug of EXPECTED_INDUSTRIES) {
    assert.match(
      src,
      new RegExp(`slug:\\s*"${slug}"`),
      `missing industry slug: ${slug}`,
    );
  }
});

test("competitors.ts exports all four required slugs", () => {
  const src = readFileSync(COMPETITORS_PATH, "utf8");
  for (const slug of EXPECTED_COMPETITORS) {
    assert.match(
      src,
      new RegExp(`slug:\\s*"${slug}"`),
      `missing competitor slug: ${slug}`,
    );
  }
});

test("each competitor metadata title follows the Swedish SEO pattern", () => {
  const src = readFileSync(COMPETITORS_PATH, "utf8");
  // Must contain "Sveriges bästa alternativ 2026" in every metaTitle.
  const occurrences =
    src.match(/metaTitle:\s*"[^"]*Sveriges bästa alternativ 2026"/g) ?? [];
  assert.equal(
    occurrences.length,
    EXPECTED_COMPETITORS.length,
    `expected ${EXPECTED_COMPETITORS.length} metaTitle entries, found ${occurrences.length}`,
  );
});

test("industries metadata uses Swedish keywords (Fortnox, moms)", () => {
  const src = readFileSync(INDUSTRIES_PATH, "utf8");
  // Catches a regression where the copy reverted to English-only.
  assert.match(src, /moms|Fortnox/);
  assert.match(src, /Varuflow/);
});

test("sitemap references both bransch/ and jämför/ url segments", () => {
  const src = readFileSync(SITEMAP_PATH, "utf8");
  assert.match(src, /\/sv\/bransch\//, "sitemap missing /sv/bransch/ entries");
  // jämför is URL-encoded as j%C3%A4mf%C3%B6r in the sitemap.
  assert.match(
    src,
    /j%C3%A4mf%C3%B6r/,
    "sitemap missing URL-encoded jämför entries",
  );
});

test("each page exports generateStaticParams and generateMetadata", () => {
  const industryPage = readFileSync(
    resolve(
      ROOT,
      "src/app/[locale]/(marketing)/bransch/[slug]/page.tsx",
    ),
    "utf8",
  );
  const comparePage = readFileSync(
    resolve(
      ROOT,
      "src/app/[locale]/(marketing)/jämför/[competitor]/page.tsx",
    ),
    "utf8",
  );
  for (const src of [industryPage, comparePage]) {
    assert.match(src, /export function generateStaticParams/);
    assert.match(src, /export async function generateMetadata/);
    // Schema.org JSON-LD injection must be present.
    assert.match(src, /application\/ld\+json/);
    assert.match(src, /SoftwareApplication/);
  }
});
