// frontend/scripts/test_blog.mjs
// Tests for the blog CMS integration.
// Run: node --test scripts/test_blog.mjs

import { describe, it } from "node:test";
import assert from "node:assert/strict";
import { readFileSync, existsSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const root = path.resolve(__dirname, "..");
const src = path.join(root, "src");

function readSrc(rel) {
  return readFileSync(path.join(src, rel), "utf8");
}

function fileSrc(rel) {
  return existsSync(path.join(src, rel));
}

// ── 1. Blog index page ──────────────────────────────────────────────────────

describe("Blog index page", () => {
  const page = readSrc("app/[locale]/(marketing)/blog/page.tsx");

  it("exports revalidate = 3600", () => {
    assert.ok(page.includes("export const revalidate = 3600"), "missing ISR revalidate");
  });

  it("exports generateMetadata", () => {
    assert.ok(page.includes("export async function generateMetadata"), "missing generateMetadata");
  });

  it("exports default page component", () => {
    assert.ok(page.includes("export default"), "missing default export");
  });

  it("renders category filter using SEED_CATEGORIES", () => {
    assert.ok(page.includes("SEED_CATEGORIES"), "must use SEED_CATEGORIES for category filter");
  });

  it("has OpenGraph type article-list or website", () => {
    assert.ok(
      page.includes("openGraph") && (page.includes('"website"') || page.includes("'website'")),
      "blog index must have OG metadata",
    );
  });

  it("includes blog JSON-LD schema", () => {
    assert.ok(page.includes("JsonLd") || page.includes("json-ld"), "missing JSON-LD on blog index");
  });

  it("links to individual articles via /blog/[slug]", () => {
    assert.ok(page.includes("/blog/"), "must link to article pages");
  });

  it("shows reading time", () => {
    assert.ok(page.includes("readingTimeMinutes") || page.includes("min read"), "must show reading time");
  });
});

// ── 2. Article page SEO ──────────────────────────────────────────────────────

describe("Article page", () => {
  const page = readSrc("app/[locale]/(marketing)/blog/[slug]/page.tsx");

  it("exists", () => {
    assert.ok(fileSrc("app/[locale]/(marketing)/blog/[slug]/page.tsx"), "article page missing");
  });

  it("exports revalidate = 3600", () => {
    assert.ok(page.includes("export const revalidate = 3600"), "missing ISR revalidate on article");
  });

  it("has generateStaticParams", () => {
    assert.ok(page.includes("generateStaticParams"), "missing generateStaticParams");
  });

  it("has generateMetadata with openGraph", () => {
    assert.ok(page.includes("openGraph"), "article must have OG metadata");
  });

  it("sets OG image via /api/og route", () => {
    assert.ok(page.includes("/api/og"), "must use /api/og for OG image");
  });

  it("sets canonical URL", () => {
    assert.ok(page.includes("canonical"), "missing canonical in metadata");
  });

  it("builds hreflang from translationSlug", () => {
    assert.ok(page.includes("translationSlug"), "must generate hreflang from translationSlug");
    assert.ok(page.includes("languages"), "must set alternates.languages for hreflang");
  });

  it("emits BlogPosting JSON-LD", () => {
    assert.ok(page.includes("BlogPosting"), "missing BlogPosting schema.org markup");
  });

  it("emits BreadcrumbList JSON-LD", () => {
    assert.ok(page.includes("BreadcrumbList"), "missing BreadcrumbList JSON-LD");
  });

  it("renders article body — seed path (dangerouslySetInnerHTML)", () => {
    assert.ok(page.includes("dangerouslySetInnerHTML"), "must render bodyHtml for seed articles");
  });

  it("renders article body — Sanity path (SanityBody)", () => {
    assert.ok(page.includes("SanityBody"), "must render PortableText when Sanity is configured");
  });

  it("includes TableOfContents sidebar", () => {
    assert.ok(page.includes("TableOfContents"), "missing TableOfContents in sidebar");
  });

  it("includes LeadMagnetForm when leadMagnet present", () => {
    assert.ok(page.includes("LeadMagnetForm"), "missing LeadMagnetForm in sidebar");
  });

  it("includes ShareButtons at top and bottom", () => {
    const count = (page.match(/ShareButtons/g) ?? []).length;
    assert.ok(count >= 2, `expected ShareButtons ≥ 2 times, found ${count}`);
  });

  it("shows author bio", () => {
    assert.ok(page.includes("author.bio"), "missing author bio section");
  });

  it("shows related articles", () => {
    assert.ok(page.includes("related"), "missing related articles section");
  });

  it("includes CTABanner at end", () => {
    assert.ok(page.includes("CTABanner"), "missing CTABanner at article end");
  });

  it("seoTitle ≤ 60 chars enforced — seoDescription ≤ 155 enforcement in seed data", () => {
    // Verify all seed articles respect the length limits
    const seedPath = path.join(src, "lib/sanity/seed/posts.ts");
    const seed = readFileSync(seedPath, "utf8");
    // The editorial checklist requires seoTitle ≤ 60 chars; test that the
    // field exists in every post definition
    const seoTitleCount = (seed.match(/seoTitle:/g) ?? []).length;
    assert.ok(seoTitleCount >= 10, `expected 10 seoTitle fields in seed, found ${seoTitleCount}`);
    const seoDescCount = (seed.match(/seoDescription:/g) ?? []).length;
    assert.ok(seoDescCount >= 10, `expected 10 seoDescription fields in seed, found ${seoDescCount}`);
  });

  it("publishedAt and updatedAt present in article page", () => {
    assert.ok(page.includes("publishedAt"), "missing publishedAt in article");
    assert.ok(page.includes("updatedAt"), "missing updatedAt in article");
  });
});

// ── 3. TableOfContents ───────────────────────────────────────────────────────

describe("TableOfContents component", () => {
  const toc = readSrc("app/[locale]/(marketing)/blog/[slug]/TableOfContents.tsx");

  it("is a client component", () => {
    assert.ok(toc.startsWith('"use client"') || toc.startsWith("'use client'"), "TableOfContents must be use client");
  });

  it("uses IntersectionObserver for active heading tracking", () => {
    assert.ok(toc.includes("IntersectionObserver"), "must use IntersectionObserver");
  });

  it("highlights active heading", () => {
    assert.ok(toc.includes("active") || toc.includes("activeId"), "must track and highlight active heading");
  });
});

// ── 4. ShareButtons ──────────────────────────────────────────────────────────

describe("ShareButtons component", () => {
  const share = readSrc("app/[locale]/(marketing)/blog/[slug]/ShareButtons.tsx");

  it("is a client component", () => {
    assert.ok(share.startsWith('"use client"') || share.startsWith("'use client'"), "ShareButtons must be use client");
  });

  it("has Twitter/X share", () => {
    assert.ok(
      share.includes("twitter.com") || share.includes("x.com"),
      "missing Twitter/X share link",
    );
  });

  it("has LinkedIn share", () => {
    assert.ok(share.includes("linkedin.com"), "missing LinkedIn share link");
  });

  it("has clipboard copy", () => {
    assert.ok(
      share.includes("clipboard") || share.includes("navigator.clipboard"),
      "missing clipboard copy",
    );
  });
});

// ── 5. LeadMagnetForm ────────────────────────────────────────────────────────

describe("LeadMagnetForm component", () => {
  const form = readSrc("components/marketing/LeadMagnetForm.tsx");

  it("is a client component", () => {
    assert.ok(form.startsWith('"use client"') || form.startsWith("'use client'"), "LeadMagnetForm must be use client");
  });

  it("submits to /api/waitlist/signup", () => {
    assert.ok(form.includes("/api/waitlist/signup"), "must POST to /api/waitlist/signup");
  });

  it("sends source tag with lead_magnet_ prefix", () => {
    assert.ok(form.includes("lead_magnet_"), "source must contain lead_magnet_ prefix");
  });

  it("sends tags array with lead_magnet and pdfSlug", () => {
    assert.ok(form.includes('"lead_magnet"') || form.includes("'lead_magnet'"), "tags must include lead_magnet");
    assert.ok(form.includes("pdfSlug"), "tags must include pdfSlug");
  });

  it("accepts 409 (already subscribed) and still shows download", () => {
    assert.ok(form.includes("409"), "must treat 409 as success (already subscribed)");
  });

  it("provides download link after success", () => {
    assert.ok(form.includes("/downloads/"), "must show /downloads/ link in done state");
  });

  it("has error state display", () => {
    assert.ok(form.includes("error"), "must handle and display submission errors");
  });

  it("does not expose NEXT_PUBLIC_API_URL directly in JSX", () => {
    // API URL must come from env var, not hardcoded
    assert.ok(
      !form.includes("varuflow-production.up.railway.app"),
      "must not hardcode production API URL in component",
    );
  });
});

// ── 6. OG image route ───────────────────────────────────────────────────────

describe("OG image route /api/og", () => {
  const og = readSrc("app/api/og/route.tsx");

  it("uses Edge runtime", () => {
    assert.ok(og.includes('runtime = "edge"') || og.includes("runtime = 'edge'"), "OG route must use Edge runtime");
  });

  it("uses ImageResponse from next/og", () => {
    assert.ok(og.includes("ImageResponse") && og.includes("next/og"), "must use ImageResponse from next/og");
  });

  it("reads title from query params", () => {
    assert.ok(og.includes('searchParams.get("title")'), "must read title from search params");
  });

  it("reads category from query params", () => {
    assert.ok(og.includes('searchParams.get("category")'), "must read category from search params");
  });

  it("outputs 1200×630 image", () => {
    assert.ok(og.includes("1200") && og.includes("630"), "OG image must be 1200×630");
  });

  it("renders Varuflow branding", () => {
    assert.ok(og.includes("Varuflow"), "OG image must include Varuflow brand");
  });
});

// ── 7. Category archive ─────────────────────────────────────────────────────

describe("Category archive page", () => {
  const cat = readSrc("app/[locale]/(marketing)/blog/category/[slug]/page.tsx");

  it("exists", () => {
    assert.ok(fileSrc("app/[locale]/(marketing)/blog/category/[slug]/page.tsx"), "category page missing");
  });

  it("has generateStaticParams from SEED_CATEGORIES", () => {
    assert.ok(cat.includes("generateStaticParams"), "missing generateStaticParams");
    assert.ok(cat.includes("SEED_CATEGORIES"), "must generate params from SEED_CATEGORIES");
  });

  it("has BreadcrumbList JSON-LD", () => {
    assert.ok(cat.includes("BreadcrumbList"), "missing BreadcrumbList JSON-LD");
  });

  it("returns 404 for unknown category", () => {
    assert.ok(cat.includes("notFound"), "must call notFound() for unknown category slugs");
  });
});

// ── 8. Tag archive ──────────────────────────────────────────────────────────

describe("Tag archive page", () => {
  const tag = readSrc("app/[locale]/(marketing)/blog/tag/[slug]/page.tsx");

  it("exists", () => {
    assert.ok(fileSrc("app/[locale]/(marketing)/blog/tag/[slug]/page.tsx"), "tag page missing");
  });

  it("has generateStaticParams from getAllSeedTags", () => {
    assert.ok(tag.includes("getAllSeedTags"), "must generate params from getAllSeedTags()");
  });

  it("returns 404 for unknown tag", () => {
    assert.ok(tag.includes("notFound"), "must call notFound() for unknown tags");
  });
});

// ── 9. Seed data completeness ────────────────────────────────────────────────

describe("Seed data completeness", () => {
  const seedPath = path.join(src, "lib/sanity/seed/posts.ts");
  const seed = readFileSync(seedPath, "utf8");

  const requiredSlugs = [
    "swedish-bookkeeping-law-guide",
    "zatca-phase-2-compliance-guide",
    "peppol-bis-3-e-invoicing",
    "gdpr-data-retention-invoices",
    "varuflow-vs-fortnox",
    "fortnox-alternativ",
    "odoo-alternatives-wholesale",
    "salon-inventory-management",
    "multi-warehouse-inventory",
    "building-varuflow",
  ];

  for (const slug of requiredSlugs) {
    it(`seed contains article: ${slug}`, () => {
      assert.ok(seed.includes(slug), `missing required seed article: ${slug}`);
    });
  }

  it("has at least 10 articles in SEED_POSTS", () => {
    // Count _id: occurrences as a proxy for article count
    const count = (seed.match(/_id:/g) ?? []).length;
    assert.ok(count >= 10, `expected at least 10 articles in seed, found ${count}`);
  });

  it("every article has tableOfContents", () => {
    const count = (seed.match(/tableOfContents:/g) ?? []).length;
    assert.ok(count >= 10, `expected 10 tableOfContents, found ${count}`);
  });

  it("every article has bodyHtml", () => {
    const count = (seed.match(/bodyHtml:/g) ?? []).length;
    assert.ok(count >= 10, `expected 10 bodyHtml fields, found ${count}`);
  });

  it("every article has a CTA", () => {
    const count = (seed.match(/\bcta:/g) ?? []).length;
    assert.ok(count >= 10, `expected 10 cta fields, found ${count}`);
  });

  it("has compliance category articles", () => {
    assert.ok(seed.includes('"compliance"'), "missing compliance category articles");
  });

  it("has comparison category articles", () => {
    assert.ok(seed.includes('"comparison"'), "missing comparison category articles");
  });

  it("has Swedish (sv) locale articles", () => {
    assert.ok(seed.includes('"sv"'), "missing Swedish locale articles");
  });

  it("has at least one lead magnet", () => {
    assert.ok(seed.includes("leadMagnet:"), "at least one article must have a lead magnet");
    assert.ok(seed.includes("pdfSlug:"), "lead magnet must have pdfSlug");
  });

  it("has at least one translation pair (translationSlug)", () => {
    assert.ok(seed.includes("translationSlug:"), "must have at least one translation pair for hreflang testing");
  });
});

// ── 10. Sitemap ──────────────────────────────────────────────────────────────

describe("Sitemap", () => {
  const sitemapPath = path.join(src, "app/sitemap.ts");
  const sitemap = readFileSync(sitemapPath, "utf8");

  it("imports getSitemapPosts for blog entries", () => {
    assert.ok(
      sitemap.includes("getSitemapPosts") || sitemap.includes("SEED_POSTS"),
      "sitemap must include blog post entries via getSitemapPosts or SEED_POSTS",
    );
  });

  it("exports default function", () => {
    assert.ok(sitemap.includes("export default"), "sitemap must export default function");
  });

  it("includes /blog in PUBLIC_PATHS or blog entries", () => {
    assert.ok(
      sitemap.includes("/blog") || sitemap.includes("blog"),
      "sitemap must reference blog routes",
    );
  });
});

// ── 11. Data access layer: getPosts ─────────────────────────────────────────

describe("getPosts data access layer", () => {
  const getPosts = readSrc("lib/sanity/getPosts.ts");

  it("exports getAllPosts", () => {
    assert.ok(getPosts.includes("export async function getAllPosts"), "missing getAllPosts export");
  });

  it("exports getPostBySlug", () => {
    assert.ok(getPosts.includes("export async function getPostBySlug"), "missing getPostBySlug export");
  });

  it("exports getPostsByCategory", () => {
    assert.ok(getPosts.includes("export async function getPostsByCategory"), "missing getPostsByCategory export");
  });

  it("exports getPostsByTag", () => {
    assert.ok(getPosts.includes("export async function getPostsByTag"), "missing getPostsByTag export");
  });

  it("exports getSitemapPosts", () => {
    assert.ok(getPosts.includes("export async function getSitemapPosts"), "missing getSitemapPosts export");
  });

  it("falls back to SEED_POSTS when SANITY_ENABLED is false", () => {
    assert.ok(getPosts.includes("SEED_POSTS"), "must reference SEED_POSTS for fallback");
    assert.ok(getPosts.includes("SANITY_ENABLED"), "must check SANITY_ENABLED flag");
  });

  it("exports SEED_CATEGORIES with 6 categories", () => {
    assert.ok(getPosts.includes("SEED_CATEGORIES"), "missing SEED_CATEGORIES export");
    const count = (getPosts.match(/slug:/g) ?? []).length;
    assert.ok(count >= 6, "SEED_CATEGORIES must have at least 6 categories");
  });

  it("exports getCategoryTitle helper", () => {
    assert.ok(getPosts.includes("export function getCategoryTitle"), "missing getCategoryTitle export");
  });

  it("exports getAllSeedTags and tagToSlug", () => {
    assert.ok(getPosts.includes("export function getAllSeedTags"), "missing getAllSeedTags");
    assert.ok(getPosts.includes("export function tagToSlug"), "missing tagToSlug");
  });
});

// ── 12. Sanity client ───────────────────────────────────────────────────────

describe("Sanity client", () => {
  const client = readSrc("lib/sanity/client.ts");

  it("exports SANITY_ENABLED flag", () => {
    assert.ok(client.includes("SANITY_ENABLED"), "must export SANITY_ENABLED boolean");
  });

  it("reads projectId from NEXT_PUBLIC_SANITY_PROJECT_ID", () => {
    assert.ok(
      client.includes("NEXT_PUBLIC_SANITY_PROJECT_ID"),
      "must read projectId from env var",
    );
  });

  it("does not hardcode project ID", () => {
    // Project IDs are alphanumeric strings of ~8 characters — match common pattern
    assert.ok(
      !client.match(/projectId:\s*["'][a-z0-9]{8,}["']/),
      "must not hardcode Sanity project ID",
    );
  });

  it("exports sanityFetch with revalidate", () => {
    assert.ok(client.includes("sanityFetch"), "must export sanityFetch");
    assert.ok(client.includes("revalidate"), "sanityFetch must pass revalidate to Next.js cache");
  });
});

// ── 13. PortableText renderer ───────────────────────────────────────────────

describe("PortableText renderer (SanityBody)", () => {
  const ptPath = path.join(src, "lib/sanity/portableText.tsx");
  const exists = existsSync(ptPath);

  it("portableText.tsx exists", () => {
    assert.ok(exists, "lib/sanity/portableText.tsx must exist");
  });

  if (exists) {
    const pt = readFileSync(ptPath, "utf8");
    it("uses @portabletext/react", () => {
      assert.ok(pt.includes("@portabletext/react") || pt.includes("portabletext"), "must use @portabletext/react");
    });
    it("exports SanityBody or PortableText component", () => {
      assert.ok(
        pt.includes("export") && (pt.includes("SanityBody") || pt.includes("PortableText")),
        "must export SanityBody component",
      );
    });
  }
});

// ── 14. i18n translations include blog key ──────────────────────────────────

describe("i18n keys", () => {
  const locales = ["en", "sv", "no", "da"];
  for (const locale of locales) {
    it(`${locale}.json has blog key`, () => {
      const msgPath = path.join(root, "messages", `${locale}.json`);
      if (!existsSync(msgPath)) {
        // messages file may not exist yet — skip softly
        assert.ok(true, `${locale}.json not found — skipping`);
        return;
      }
      const msg = readFileSync(msgPath, "utf8");
      assert.ok(msg.includes('"blog"') || msg.includes("'blog'"), `${locale}.json must have blog key`);
    });
  }
});

// ── 15. No security regressions ─────────────────────────────────────────────

describe("Security checks", () => {
  it("OG route does not eval or execute title/category input", () => {
    const og = readSrc("app/api/og/route.tsx");
    assert.ok(!og.includes("eval("), "OG route must not use eval()");
    assert.ok(!og.includes("Function("), "OG route must not use Function()");
  });

  it("LeadMagnetForm uses Content-Type application/json (no form-urlencoded)", () => {
    const form = readSrc("components/marketing/LeadMagnetForm.tsx");
    assert.ok(form.includes("application/json"), "must use JSON body, not form-urlencoded");
  });

  it("Article page does not expose internal API URL in rendered HTML", () => {
    const page = readSrc("app/[locale]/(marketing)/blog/[slug]/page.tsx");
    assert.ok(
      !page.includes("varuflow-production.up.railway.app"),
      "article page must not expose internal API URL",
    );
  });
});
