import type { Metadata } from "next";
import { Link } from "@/i18n/navigation";
import { getAllPosts, SEED_CATEGORIES, getCategoryTitle } from "@/lib/sanity/getPosts";
import { ArrowRight, Clock, Tag } from "lucide-react";
import JsonLd, { organizationSchema } from "@/components/marketing/JsonLd";

// ISR: revalidate every 60 minutes
export const revalidate = 3600;

const BASE = process.env.NEXT_PUBLIC_SITE_URL ?? "https://varuflow.vercel.app";

export const metadata: Metadata = {
  title: "Blog — Varuflow",
  description:
    "Compliance guides, product comparisons, and vertical playbooks for Nordic and MENA wholesale businesses.",
  openGraph: {
    title: "Varuflow Blog",
    description: "Compliance guides, product comparisons, and vertical playbooks.",
    type: "website",
    url: `${BASE}/en/blog`,
  },
  twitter: { card: "summary_large_image", title: "Varuflow Blog" },
  alternates: {
    canonical: `${BASE}/en/blog`,
    languages: {
      en: `${BASE}/en/blog`,
      sv: `${BASE}/sv/blog`,
      "x-default": `${BASE}/en/blog`,
    },
  },
};

interface Props {
  searchParams: Promise<{ category?: string; page?: string }>;
}

const POSTS_PER_PAGE = 9;

function PostCard({ post }: { post: Awaited<ReturnType<typeof getAllPosts>>[0] }) {
  const date = new Date(post.publishedAt).toLocaleDateString("en-GB", {
    day: "numeric",
    month: "long",
    year: "numeric",
  });

  return (
    <article className="group flex flex-col rounded-2xl border border-white/8 bg-white/4 p-6 transition-colors hover:border-[var(--vf-brand-border)] hover:bg-white/6">
      <div className="mb-3 flex items-center gap-2">
        <span className="inline-block rounded-full border border-[var(--vf-brand-border)] bg-[var(--vf-brand-primary-subtle)] px-2.5 py-0.5 text-xs font-semibold text-[var(--vf-brand-primary-light)]">
          {getCategoryTitle(post.category)}
        </span>
        <span className="flex items-center gap-1 text-xs text-slate-500">
          <Clock className="h-3 w-3" />
          {post.readingTimeMinutes} min read
        </span>
      </div>

      <h2 className="vf-text-1 mb-3 text-base font-bold leading-snug group-hover:text-white transition-colors">
        <Link href={`/blog/${post.slug}`}>{post.title}</Link>
      </h2>

      <p className="vf-text-2 mb-4 flex-1 text-sm leading-relaxed line-clamp-3">{post.excerpt}</p>

      <div className="mt-auto flex items-center justify-between">
        <div className="flex items-center gap-2">
          <div className="flex h-6 w-6 items-center justify-center rounded-full bg-[var(--vf-brand-primary)] text-[10px] font-bold text-white">
            {post.author.initials}
          </div>
          <span className="text-xs text-slate-500">{post.author.name} · {date}</span>
        </div>
        <Link
          href={`/blog/${post.slug}`}
          className="text-xs font-medium text-[var(--vf-brand-primary-light)] hover:text-white flex items-center gap-1"
        >
          Read <ArrowRight className="h-3 w-3" />
        </Link>
      </div>
    </article>
  );
}

export default async function BlogIndexPage({ searchParams }: Props) {
  const { category, page: pageStr } = await searchParams;
  const page = Math.max(1, parseInt(pageStr ?? "1", 10));

  const allPosts = await getAllPosts();
  const filtered = category ? allPosts.filter((p) => p.category === category) : allPosts;
  const totalPages = Math.max(1, Math.ceil(filtered.length / POSTS_PER_PAGE));
  const posts = filtered.slice((page - 1) * POSTS_PER_PAGE, page * POSTS_PER_PAGE);

  const blogListingSchema = {
    "@context": "https://schema.org",
    "@type": "Blog",
    name: "Varuflow Blog",
    url: `${BASE}/en/blog`,
    description: "Compliance guides, product comparisons, and vertical playbooks.",
    blogPost: posts.map((p) => ({
      "@type": "BlogPosting",
      headline: p.title,
      url: `${BASE}/en/blog/${p.slug}`,
      datePublished: p.publishedAt,
      author: { "@type": "Person", name: p.author.name },
    })),
  };

  return (
    <>
      <JsonLd data={organizationSchema()} />
      <JsonLd data={blogListingSchema} />

      <div className="mx-auto max-w-6xl px-4 py-16">
        {/* Header */}
        <div className="mb-10 text-center">
          <p className="mb-3 inline-block rounded-full border border-[var(--vf-brand-border)] bg-[var(--vf-brand-primary-subtle)] px-4 py-1 text-xs font-semibold uppercase tracking-widest text-[var(--vf-brand-primary-light)]">
            Resources
          </p>
          <h1 className="vf-text-1 text-3xl font-extrabold tracking-tight sm:text-4xl">
            Compliance guides & playbooks
          </h1>
          <p className="vf-text-2 mx-auto mt-4 max-w-xl text-base">
            Deep dives for Nordic and MENA wholesale businesses — from Bokföringslagen to ZATCA.
          </p>
        </div>

        {/* Category filter */}
        <div className="mb-8 flex flex-wrap gap-2">
          <Link
            href="/blog"
            className={`rounded-full border px-3.5 py-1.5 text-xs font-medium transition-colors ${
              !category
                ? "border-[var(--vf-brand-border)] bg-[var(--vf-brand-primary-soft)] text-[var(--vf-brand-primary-light)]"
                : "border-white/8 text-slate-400 hover:border-white/20 hover:text-white"
            }`}
          >
            All
          </Link>
          {SEED_CATEGORIES.map((cat) => (
            <Link
              key={cat.slug}
              href={`/blog?category=${cat.slug}`}
              className={`rounded-full border px-3.5 py-1.5 text-xs font-medium transition-colors ${
                category === cat.slug
                  ? "border-[var(--vf-brand-border)] bg-[var(--vf-brand-primary-soft)] text-[var(--vf-brand-primary-light)]"
                  : "border-white/8 text-slate-400 hover:border-white/20 hover:text-white"
              }`}
            >
              {cat.title}
            </Link>
          ))}
        </div>

        {/* Posts grid */}
        {posts.length === 0 ? (
          <p className="vf-text-2 py-16 text-center">No posts in this category yet.</p>
        ) : (
          <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
            {posts.map((post) => (
              <PostCard key={post._id} post={post} />
            ))}
          </div>
        )}

        {/* Pagination */}
        {totalPages > 1 && (
          <div className="mt-10 flex justify-center gap-2">
            {Array.from({ length: totalPages }, (_, i) => i + 1).map((p) => (
              <Link
                key={p}
                href={`/blog?${category ? `category=${category}&` : ""}page=${p}`}
                className={`flex h-9 w-9 items-center justify-center rounded-lg border text-sm font-medium transition-colors ${
                  p === page
                    ? "border-[var(--vf-brand-border)] bg-[var(--vf-brand-primary-soft)] text-[var(--vf-brand-primary-light)]"
                    : "border-white/8 text-slate-400 hover:border-white/20 hover:text-white"
                }`}
              >
                {p}
              </Link>
            ))}
          </div>
        )}

        {/* Tags cloud */}
        <div className="mt-16 border-t border-white/8 pt-8">
          <p className="vf-text-m mb-4 flex items-center gap-1 text-xs">
            <Tag className="h-3 w-3" /> Browse by tag
          </p>
          <div className="flex flex-wrap gap-2">
            {[...new Set(allPosts.flatMap((p) => p.tags))].map((tag) => (
              <Link
                key={tag}
                href={`/blog/tag/${tag.toLowerCase().replace(/\s+/g, "-")}`}
                className="rounded-full border border-white/8 px-3 py-1 text-xs text-slate-400 transition-colors hover:border-white/20 hover:text-white"
              >
                {tag}
              </Link>
            ))}
          </div>
        </div>
      </div>
    </>
  );
}
