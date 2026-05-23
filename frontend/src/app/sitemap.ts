import type { MetadataRoute } from "next";
import { INDUSTRY_SLUGS } from "./[locale]/(marketing)/bransch/[slug]/industries";
import { COMPETITOR_SLUGS } from "./[locale]/(marketing)/jämför/[competitor]/competitors";
import { VERTICAL_SLUGS } from "./[locale]/(marketing)/verticals/[vertical]/verticals";
import { VS_SLUGS } from "./[locale]/(marketing)/vs/[competitor]/vscompetitors";
import { REGION_SLUGS } from "./[locale]/(marketing)/regions/[region]/regions";
import { getSitemapPosts, SEED_CATEGORIES } from "@/lib/sanity/getPosts";

const BASE_URL =
  process.env.NEXT_PUBLIC_SITE_URL ?? "https://varuflow.vercel.app";

// Marketing / public pages only — the authenticated app is excluded by
// robots.txt and must never appear in a sitemap.
const PUBLIC_PATHS = [
  "",
  "/pricing",
  "/features",
  "/compliance",
  "/security",
  "/trial",
  "/demo",
  "/partners",
  "/press",
  "/about",
  "/contact",
  "/privacy",
  "/terms",
  "/blog",
];
const LOCALES = ["en", "sv", "no", "da", "fi"];

// "jämför" must be URL-encoded in sitemap entries so crawlers that
// don't normalise IRIs still reach the right canonical URL.
const COMPARE_SEGMENT = "j%C3%A4mf%C3%B6r";

export default async function sitemap(): Promise<MetadataRoute.Sitemap> {
  const now = new Date();

  const staticEntries = LOCALES.flatMap((locale) =>
    PUBLIC_PATHS.map((path) => ({
      url: `${BASE_URL}/${locale}${path}`,
      lastModified: now,
      changeFrequency: "weekly" as const,
      priority: path === "" ? 1.0 : path === "/pricing" || path === "/trial" ? 0.9 : path === "/blog" ? 0.8 : 0.7,
    })),
  );

  // Swedish-only industry + compare landing pages — high lead-gen value.
  const industryEntries = INDUSTRY_SLUGS.map((slug) => ({
    url: `${BASE_URL}/sv/bransch/${slug}`,
    lastModified: now,
    changeFrequency: "monthly" as const,
    priority: 0.8,
  }));

  const compareEntries = COMPETITOR_SLUGS.map((slug) => ({
    url: `${BASE_URL}/sv/${COMPARE_SEGMENT}/${slug}`,
    lastModified: now,
    changeFrequency: "monthly" as const,
    priority: 0.8,
  }));

  // Multi-locale vertical landings (salons, retail, b2b, restaurants)
  const verticalEntries = LOCALES.flatMap((locale) =>
    VERTICAL_SLUGS.map((slug) => ({
      url: `${BASE_URL}/${locale}/verticals/${slug}`,
      lastModified: now,
      changeFrequency: "monthly" as const,
      priority: 0.8,
    })),
  );

  // Competitor comparison pages — English canonical, high SEO value
  const vsEntries = VS_SLUGS.map((slug) => ({
    url: `${BASE_URL}/en/vs/${slug}`,
    lastModified: now,
    changeFrequency: "monthly" as const,
    priority: 0.85,
  }));

  // Region-specific landing pages
  const regionEntries = REGION_SLUGS.map((slug) => ({
    url: `${BASE_URL}/en/regions/${slug}`,
    lastModified: now,
    changeFrequency: "monthly" as const,
    priority: 0.75,
  }));

  // Blog category archive pages
  const blogCategoryEntries = LOCALES.flatMap((locale) =>
    SEED_CATEGORIES.map((cat) => ({
      url: `${BASE_URL}/${locale}/blog/category/${cat.slug}`,
      lastModified: now,
      changeFrequency: "weekly" as const,
      priority: 0.65,
    })),
  );

  // Individual blog articles — served per locale from Sanity/seed
  const sitemapPosts = await getSitemapPosts();
  const blogPostEntries = sitemapPosts.flatMap((post) => {
    const entries = [
      {
        url: `${BASE_URL}/${post.locale}/blog/${post.slug}`,
        lastModified: new Date(post.updatedAt ?? post.publishedAt),
        changeFrequency: "monthly" as const,
        priority: 0.75,
      },
    ];
    // Add translation URL if present
    if (post.translations) {
      for (const t of post.translations) {
        entries.push({
          url: `${BASE_URL}/${t.locale}/blog/${t.slug}`,
          lastModified: new Date(post.updatedAt ?? post.publishedAt),
          changeFrequency: "monthly" as const,
          priority: 0.75,
        });
      }
    }
    return entries;
  });

  return [
    ...staticEntries,
    ...industryEntries,
    ...compareEntries,
    ...verticalEntries,
    ...vsEntries,
    ...regionEntries,
    ...blogCategoryEntries,
    ...blogPostEntries,
  ];
}
