#!/usr/bin/env node
// File: frontend/scripts/test_marketing.mjs
// Purpose: Zero-dependency smoke tests for the full marketing site build.
// Validates routes, metadata, CTAs, pricing, hreflang, and conversion infra.
//
// Invocation: `node frontend/scripts/test_marketing.mjs`
// Strategy: read .tsx/.ts source files as text and pattern-match expected tokens.

import { readFileSync, existsSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, resolve } from "node:path";
import test from "node:test";
import assert from "node:assert/strict";

const HERE = dirname(fileURLToPath(import.meta.url));
const ROOT = resolve(HERE, "..");
const MARKETING = resolve(ROOT, "src/app/[locale]/(marketing)");
const COMPONENTS = resolve(ROOT, "src/components/marketing");

// ─── helpers ──────────────────────────────────────────────────────────────────

function src(relPath) {
  return readFileSync(resolve(ROOT, relPath), "utf8");
}

function marketingSrc(relPath) {
  return readFileSync(resolve(MARKETING, relPath), "utf8");
}

function componentSrc(name) {
  return readFileSync(resolve(COMPONENTS, name), "utf8");
}

function fileExists(relPath) {
  return existsSync(resolve(ROOT, relPath));
}

// ─── 1. Static page files exist ───────────────────────────────────────────────

const STATIC_PAGES = [
  "pricing/page.tsx",
  "features/page.tsx",
  "compliance/page.tsx",
  "security/page.tsx",
  "trial/page.tsx",
  "demo/page.tsx",
  "partners/page.tsx",
  "press/page.tsx",
  "about/page.tsx",
  "contact/page.tsx",
];

test("all static marketing page files exist", () => {
  for (const page of STATIC_PAGES) {
    const path = `src/app/[locale]/(marketing)/${page}`;
    assert.ok(fileExists(path), `Missing: ${path}`);
  }
});

// ─── 2. Dynamic route page files exist ────────────────────────────────────────

test("dynamic route page files exist", () => {
  const dynamic = [
    "src/app/[locale]/(marketing)/verticals/[vertical]/page.tsx",
    "src/app/[locale]/(marketing)/vs/[competitor]/page.tsx",
    "src/app/[locale]/(marketing)/regions/[region]/page.tsx",
  ];
  for (const path of dynamic) {
    assert.ok(fileExists(path), `Missing: ${path}`);
  }
});

// ─── 3. Client form components exist ──────────────────────────────────────────

test("ContactForm client component exists", () => {
  assert.ok(fileExists("src/app/[locale]/(marketing)/contact/ContactForm.tsx"));
});

test("DemoForm client component exists", () => {
  assert.ok(fileExists("src/app/[locale]/(marketing)/demo/DemoForm.tsx"));
});

// ─── 4. Data files export required slugs ──────────────────────────────────────

test("verticals.ts exports all 4 vertical slugs", () => {
  const s = marketingSrc("verticals/[vertical]/verticals.ts");
  for (const slug of ["salons", "retail", "b2b", "restaurants"]) {
    assert.ok(s.includes(`"${slug}"`), `verticals.ts missing slug: ${slug}`);
  }
  assert.ok(s.includes("VERTICAL_SLUGS"), "Missing VERTICAL_SLUGS export");
  assert.ok(s.includes("getVertical"), "Missing getVertical export");
});

test("vscompetitors.ts exports all 4 competitor slugs", () => {
  const s = marketingSrc("vs/[competitor]/vscompetitors.ts");
  for (const slug of ["fortnox", "odoo", "visma", "bokio"]) {
    assert.ok(s.includes(`"${slug}"`), `vscompetitors.ts missing slug: ${slug}`);
  }
  assert.ok(s.includes("VS_SLUGS"), "Missing VS_SLUGS export");
  assert.ok(s.includes("getVsData"), "Missing getVsData export");
});

test("regions.ts exports all 4 region slugs", () => {
  const s = marketingSrc("regions/[region]/regions.ts");
  for (const slug of ["se", "sa", "ae", "ma"]) {
    assert.ok(s.includes(`"${slug}"`), `regions.ts missing slug: ${slug}`);
  }
  assert.ok(s.includes("REGION_SLUGS"), "Missing REGION_SLUGS export");
  assert.ok(s.includes("getRegion"), "Missing getRegion export");
});

// ─── 5. All pages have metadata ───────────────────────────────────────────────

test("static pages export metadata", () => {
  const pagesWithMeta = [
    "pricing/page.tsx",
    "features/page.tsx",
    "compliance/page.tsx",
    "security/page.tsx",
    "trial/page.tsx",
    "about/page.tsx",
    "contact/page.tsx",
    "partners/page.tsx",
    "press/page.tsx",
  ];
  for (const page of pagesWithMeta) {
    const s = marketingSrc(page);
    assert.ok(
      s.includes("export const metadata") || s.includes("export async function generateMetadata"),
      `${page} is missing metadata export`,
    );
  }
});

test("dynamic pages use generateMetadata", () => {
  for (const page of [
    "verticals/[vertical]/page.tsx",
    "vs/[competitor]/page.tsx",
    "regions/[region]/page.tsx",
  ]) {
    const s = marketingSrc(page);
    assert.ok(s.includes("generateMetadata"), `${page} missing generateMetadata`);
    assert.ok(s.includes("generateStaticParams"), `${page} missing generateStaticParams`);
  }
});

// ─── 6. All pages contain an h1 ───────────────────────────────────────────────

test("all static pages render an h1", () => {
  for (const page of STATIC_PAGES) {
    const s = marketingSrc(page);
    assert.ok(s.includes("<h1") || s.includes("<HeroSection"), `${page} has no h1 or HeroSection`);
  }
});

// ─── 7. CTAs link to correct destinations ─────────────────────────────────────

test("trial page CTA links to /trial endpoint", () => {
  const s = marketingSrc("trial/page.tsx");
  assert.ok(s.includes('href="/trial"') || s.includes("TrialSignupForm"), "trial page missing /trial CTA");
});

test("pricing page links to /trial or /auth/signup", () => {
  const s = marketingSrc("pricing/page.tsx");
  assert.ok(
    s.includes('href="/trial"') || s.includes('href="/auth/signup"') || s.includes("PricingTable"),
    "pricing page missing CTA link",
  );
});

test("about page CTA links to /trial", () => {
  const s = marketingSrc("about/page.tsx");
  assert.ok(
    s.includes('href="/trial"') || s.includes('href: "/trial"'),
    "about page missing /trial CTA",
  );
});

test("vs pages CTA links to /trial", () => {
  const s = marketingSrc("vs/[competitor]/page.tsx");
  assert.ok(s.includes('href="/trial"'), "vs page missing /trial CTA");
});

// ─── 8. Pricing correctness ───────────────────────────────────────────────────

test("PricingTable component exists and has Pro tier at 599 SEK", () => {
  const s = componentSrc("PricingTable.tsx");
  assert.ok(s.includes("599"), "PricingTable missing 599 (Pro price SEK)");
  assert.ok(s.includes("SEK") || s.includes("kr"), "PricingTable missing SEK currency indicator");
  assert.ok(s.includes("Starter") || s.includes("starter"), "PricingTable missing Starter tier");
  assert.ok(s.includes("Pro") || s.includes("pro"), "PricingTable missing Pro tier");
});

test("regions.ts has pricingFrom for all regions", () => {
  const s = marketingSrc("regions/[region]/regions.ts");
  assert.ok(s.includes("pricingFrom"), "regions.ts missing pricingFrom field");
  // SE should have SEK pricing
  assert.ok(s.includes("SEK") || s.includes("kr"), "regions.ts missing SEK pricing for SE");
  // MENA regions should have SAR or AED
  assert.ok(s.includes("SAR") || s.includes("AED"), "regions.ts missing MENA pricing");
});

// ─── 9. Hreflang / canonical alternates ──────────────────────────────────────

test("about page has hreflang alternates", () => {
  const s = marketingSrc("about/page.tsx");
  assert.ok(s.includes("languages"), "about/page.tsx missing languages (hreflang) in alternates");
  assert.ok(s.includes('"x-default"'), 'about/page.tsx missing x-default hreflang');
});

test("contact page has hreflang alternates", () => {
  const s = marketingSrc("contact/page.tsx");
  assert.ok(s.includes("languages"), "contact/page.tsx missing hreflang alternates");
});

test("dynamic pages have canonical alternates", () => {
  for (const page of [
    "verticals/[vertical]/page.tsx",
    "vs/[competitor]/page.tsx",
    "regions/[region]/page.tsx",
  ]) {
    const s = marketingSrc(page);
    assert.ok(s.includes("canonical"), `${page} missing canonical URL in metadata`);
  }
});

// ─── 10. JSON-LD structured data ─────────────────────────────────────────────

test("JsonLd component exists and exports organization schema", () => {
  const s = componentSrc("JsonLd.tsx");
  assert.ok(s.includes("organizationSchema"), "JsonLd.tsx missing organizationSchema");
  assert.ok(s.includes("softwareApplicationSchema"), "JsonLd.tsx missing softwareApplicationSchema");
  assert.ok(s.includes("application/ld+json"), "JsonLd.tsx missing ld+json script type");
});

test("pricing page uses pricingOfferSchema", () => {
  const s = marketingSrc("pricing/page.tsx");
  assert.ok(s.includes("pricingOfferSchema") || s.includes("JsonLd"), "pricing page missing JSON-LD");
});

test("FAQ component exports buildFAQSchema", () => {
  const s = componentSrc("FAQ.tsx");
  assert.ok(s.includes("buildFAQSchema"), "FAQ.tsx missing buildFAQSchema export");
  assert.ok(s.includes("FAQPage"), "FAQ.tsx JSON-LD missing FAQPage @type");
});

// ─── 11. SEO components exist ────────────────────────────────────────────────

const EXPECTED_COMPONENTS = [
  "HeroSection.tsx",
  "PricingTable.tsx",
  "ComparisonTable.tsx",
  "FeatureCard.tsx",
  "TestimonialCarousel.tsx",
  "LogoCloud.tsx",
  "StatBar.tsx",
  "TrialSignupForm.tsx",
  "CTABanner.tsx",
  "FAQ.tsx",
  "JsonLd.tsx",
  "ExitIntentModal.tsx",
  "CrispChat.tsx",
  "NewsletterSignup.tsx",
];

test("all 14 marketing components exist", () => {
  for (const comp of EXPECTED_COMPONENTS) {
    assert.ok(
      existsSync(resolve(COMPONENTS, comp)),
      `Missing marketing component: ${comp}`,
    );
  }
});

// ─── 12. Conversion infrastructure ───────────────────────────────────────────

test("layout.tsx includes CrispChat", () => {
  const s = marketingSrc("layout.tsx");
  assert.ok(s.includes("CrispChat"), "layout.tsx missing CrispChat");
});

test("layout.tsx includes ExitIntentModal", () => {
  const s = marketingSrc("layout.tsx");
  assert.ok(s.includes("ExitIntentModal"), "layout.tsx missing ExitIntentModal");
});

test("layout.tsx includes NewsletterSignup in footer", () => {
  const s = marketingSrc("layout.tsx");
  assert.ok(s.includes("NewsletterSignup"), "layout.tsx footer missing NewsletterSignup");
});

test("ExitIntentModal fires on mouseleave at top of page", () => {
  const s = componentSrc("ExitIntentModal.tsx");
  assert.ok(s.includes("mouseleave"), "ExitIntentModal missing mouseleave event");
  assert.ok(s.includes("clientY"), "ExitIntentModal missing clientY check");
});

test("CrispChat uses NEXT_PUBLIC_CRISP_WEBSITE_ID env var", () => {
  const s = componentSrc("CrispChat.tsx");
  assert.ok(
    s.includes("NEXT_PUBLIC_CRISP_WEBSITE_ID"),
    "CrispChat.tsx must use NEXT_PUBLIC_CRISP_WEBSITE_ID",
  );
});

// ─── 13. HeaderNav links ─────────────────────────────────────────────────────

test("HeaderNav includes Features, Pricing, Compliance, About links", () => {
  const s = marketingSrc("HeaderNav.tsx");
  assert.ok(s.includes("/features"), "HeaderNav missing /features link");
  assert.ok(s.includes("/pricing"), "HeaderNav missing /pricing link");
  assert.ok(s.includes("/compliance"), "HeaderNav missing /compliance link");
  assert.ok(s.includes("/about"), "HeaderNav missing /about link");
});

// ─── 14. Sitemap completeness ────────────────────────────────────────────────

test("sitemap.ts imports new data exports", () => {
  const s = src("src/app/sitemap.ts");
  assert.ok(s.includes("VERTICAL_SLUGS"), "sitemap.ts missing VERTICAL_SLUGS import");
  assert.ok(s.includes("VS_SLUGS"), "sitemap.ts missing VS_SLUGS import");
  assert.ok(s.includes("REGION_SLUGS"), "sitemap.ts missing REGION_SLUGS import");
});

test("sitemap.ts includes all new marketing static paths", () => {
  const s = src("src/app/sitemap.ts");
  for (const path of ["/features", "/compliance", "/security", "/trial", "/demo", "/about", "/contact"]) {
    assert.ok(s.includes(`"${path}"`), `sitemap.ts missing PUBLIC_PATH: ${path}`);
  }
});

test("sitemap.ts generates vertical, vs, and region entries", () => {
  const s = src("src/app/sitemap.ts");
  assert.ok(s.includes("verticalEntries"), "sitemap.ts missing verticalEntries");
  assert.ok(s.includes("vsEntries"), "sitemap.ts missing vsEntries");
  assert.ok(s.includes("regionEntries"), "sitemap.ts missing regionEntries");
});

// ─── 15. RTL support in region pages ─────────────────────────────────────────

test("region page applies dir attribute for RTL support", () => {
  const s = marketingSrc("regions/[region]/page.tsx");
  assert.ok(s.includes("data.dir") || s.includes("dir={"), "regions page missing dir attribute for RTL");
});

test("regions.ts has rtl direction for MENA regions", () => {
  const s = marketingSrc("regions/[region]/regions.ts");
  assert.ok(s.includes('"rtl"'), "regions.ts missing rtl direction for MENA");
  assert.ok(s.includes('"ltr"'), "regions.ts missing ltr direction for SE");
});

// ─── 16. Contact/Demo forms are client components ────────────────────────────

test("ContactForm is a client component", () => {
  const s = marketingSrc("contact/ContactForm.tsx");
  assert.ok(s.startsWith('"use client"') || s.includes('"use client"'), "ContactForm must be a client component");
});

test("DemoForm is a client component", () => {
  const s = marketingSrc("demo/DemoForm.tsx");
  assert.ok(s.startsWith('"use client"') || s.includes('"use client"'), "DemoForm must be a client component");
});

test("contact/page.tsx is NOT a client component (needs metadata)", () => {
  const s = marketingSrc("contact/page.tsx");
  assert.ok(!s.startsWith('"use client"'), "contact/page.tsx must not be a client component — it exports metadata");
});

// ─── 17. TrialSignupForm redirects to trial ──────────────────────────────────

test("TrialSignupForm redirects to /auth/signup with trial param", () => {
  const s = componentSrc("TrialSignupForm.tsx");
  assert.ok(
    s.includes("trial") && (s.includes("/auth/signup") || s.includes("signup")),
    "TrialSignupForm must redirect to signup with trial param",
  );
});

// ─── 18. ComparisonTable handles Yes/No/string rows ──────────────────────────

test("ComparisonTable renders check for Yes and dash for No", () => {
  const s = componentSrc("ComparisonTable.tsx");
  assert.ok(s.includes("CheckCircle") || s.includes("Check"), "ComparisonTable missing Yes check icon");
  assert.ok(s.includes("Minus") || s.includes("minus") || s.includes("✗"), "ComparisonTable missing No indicator");
});

// ─── 19. TestimonialCarousel is a client component ───────────────────────────

test("TestimonialCarousel is a client component with navigation", () => {
  const s = componentSrc("TestimonialCarousel.tsx");
  assert.ok(s.includes('"use client"'), "TestimonialCarousel must be a client component");
  assert.ok(s.includes("useState"), "TestimonialCarousel needs useState for navigation");
});

// ─── 20. No hardcoded production URLs in marketing components ─────────────────

test("no hardcoded production Railway URLs in marketing components", () => {
  for (const comp of EXPECTED_COMPONENTS) {
    const path = resolve(COMPONENTS, comp);
    if (!existsSync(path)) continue;
    const s = readFileSync(path, "utf8");
    assert.ok(
      !s.includes("varuflow-production.up.railway.app"),
      `${comp} must not hardcode the Railway URL — use NEXT_PUBLIC_API_URL`,
    );
  }
});
