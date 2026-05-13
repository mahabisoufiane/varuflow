// frontend/src/lib/sanity/getPosts.ts
// Unified data access: Sanity when configured, seed data as fallback.

import { sanityFetch, SANITY_ENABLED } from "./client";
import {
  QUERY_ALL_POSTS,
  QUERY_POST_BY_SLUG,
  QUERY_POSTS_BY_CATEGORY,
  QUERY_POSTS_BY_TAG,
  QUERY_ALL_POST_SLUGS,
  QUERY_SITEMAP_POSTS,
} from "./queries";
import { SEED_POSTS, type SeedPost } from "./seed/posts";

// ── Types ─────────────────────────────────────────────────────────────────────

export type Post = SeedPost & {
  // When coming from Sanity, body is PortableText blocks; bodyHtml is for seed fallback
  body?: unknown[];
};

// ── Helpers ───────────────────────────────────────────────────────────────────

function slugify(str: string) {
  return str.toLowerCase().replace(/\s+/g, "-").replace(/[^a-z0-9-]/g, "");
}

// ── Data access ───────────────────────────────────────────────────────────────

export async function getAllPosts(locale?: string): Promise<Post[]> {
  if (SANITY_ENABLED) {
    const data = await sanityFetch<Post[]>(QUERY_ALL_POSTS(locale));
    return data ?? [];
  }
  if (locale) return SEED_POSTS.filter((p) => p.locale === locale) as Post[];
  return SEED_POSTS as Post[];
}

export async function getPostBySlug(slug: string): Promise<Post | null> {
  if (SANITY_ENABLED) {
    return sanityFetch<Post>(QUERY_POST_BY_SLUG, { slug });
  }
  return (SEED_POSTS.find((p) => p.slug === slug) as Post) ?? null;
}

export async function getPostsByCategory(
  categorySlug: string,
  locale?: string,
): Promise<Post[]> {
  if (SANITY_ENABLED) {
    const data = await sanityFetch<Post[]>(QUERY_POSTS_BY_CATEGORY, {
      categorySlug,
      locale: locale ?? null,
    });
    return data ?? [];
  }
  return SEED_POSTS.filter(
    (p) =>
      p.category === categorySlug && (!locale || p.locale === locale),
  ) as Post[];
}

export async function getPostsByTag(
  tagSlug: string,
  locale?: string,
): Promise<Post[]> {
  if (SANITY_ENABLED) {
    const data = await sanityFetch<Post[]>(QUERY_POSTS_BY_TAG, {
      tagSlug,
      locale: locale ?? null,
    });
    return data ?? [];
  }
  return SEED_POSTS.filter(
    (p) =>
      p.tags.map(slugify).includes(tagSlug) && (!locale || p.locale === locale),
  ) as Post[];
}

export async function getAllPostSlugs(): Promise<string[]> {
  if (SANITY_ENABLED) {
    const data = await sanityFetch<Array<{ slug: string }>>(QUERY_ALL_POST_SLUGS);
    return data?.map((d) => d.slug) ?? [];
  }
  return SEED_POSTS.map((p) => p.slug);
}

export async function getSitemapPosts(): Promise<
  Array<{
    slug: string;
    locale: string;
    publishedAt: string;
    updatedAt: string;
    translations?: Array<{ locale: string; slug: string }>;
  }>
> {
  if (SANITY_ENABLED) {
    const data = await sanityFetch<
      Array<{ slug: string; locale: string; publishedAt: string; updatedAt: string }>
    >(QUERY_SITEMAP_POSTS);
    return data ?? [];
  }
  return SEED_POSTS.map((p) => ({
    slug: p.slug,
    locale: p.locale,
    publishedAt: p.publishedAt,
    updatedAt: p.updatedAt,
    translations: p.translationSlug ? [{ locale: p.locale === "en" ? "sv" : "en", slug: p.translationSlug }] : [],
  }));
}

// ── Category/tag lookups ──────────────────────────────────────────────────────

export const SEED_CATEGORIES = [
  { slug: "compliance", title: "Compliance" },
  { slug: "comparison", title: "Comparison" },
  { slug: "vertical", title: "Industry" },
  { slug: "product-update", title: "Product updates" },
  { slug: "founder-story", title: "Founder story" },
  { slug: "customer-story", title: "Customer story" },
] as const;

export type CategorySlug = (typeof SEED_CATEGORIES)[number]["slug"];

export function getCategoryTitle(slug: string) {
  return SEED_CATEGORIES.find((c) => c.slug === slug)?.title ?? slug;
}

export function getAllSeedTags(): string[] {
  const all = SEED_POSTS.flatMap((p) => p.tags);
  return [...new Set(all)];
}

export function tagToSlug(tag: string) {
  return slugify(tag);
}
