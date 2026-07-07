import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { Link } from "@/i18n/navigation";
import { getPostsByTag, getAllSeedTags, tagToSlug } from "@/lib/sanity/getPosts";
import { ArrowRight, Clock } from "lucide-react";
import JsonLd, { organizationSchema } from "@/components/marketing/JsonLd";

export const revalidate = 3600;

const BASE = process.env.NEXT_PUBLIC_SITE_URL ?? "https://varuflow.vercel.app";

interface Params { locale: string; slug: string }

export async function generateStaticParams(): Promise<{ slug: string }[]> {
  return getAllSeedTags().map((tag) => ({ slug: tagToSlug(tag) }));
}

export async function generateMetadata({
  params,
}: {
  params: Promise<Params>;
}): Promise<Metadata> {
  const { slug } = await params;
  const display = slug.replace(/-/g, " ");
  return {
    title: `#${display} — Varuflow Blog`,
    description: `Articles tagged "${display}" on the Varuflow blog.`,
    alternates: { canonical: `${BASE}/en/blog/tag/${slug}` },
    openGraph: {
      title: `#${display} — Varuflow Blog`,
      description: `Articles tagged "${display}" on the Varuflow blog.`,
      type: "website",
      url: `${BASE}/en/blog/tag/${slug}`,
    },
    twitter: { card: "summary_large_image", title: `#${display} — Varuflow Blog` },
  };
}

export default async function TagPage({ params }: { params: Promise<Params> }) {
  const { slug } = await params;
  const posts = await getPostsByTag(slug);
  if (!posts.length && !getAllSeedTags().map(tagToSlug).includes(slug)) notFound();

  const display = slug.replace(/-/g, " ");

  return (
    <>
      <JsonLd data={organizationSchema()} />

      <div className="mx-auto max-w-5xl px-4 py-16">
        <nav className="mb-6 flex items-center gap-2 text-xs text-slate-500">
          <Link href="/blog" className="hover:text-slate-300">Blog</Link>
          <span>/</span>
          <span className="text-slate-300">#{display}</span>
        </nav>

        <h1 className="vf-text-1 mb-2 text-3xl font-extrabold">#{display}</h1>
        <p className="vf-text-2 mb-10 text-sm">{posts.length} article{posts.length !== 1 ? "s" : ""}</p>

        {posts.length === 0 ? (
          <p className="vf-text-2 py-12 text-center">No articles with this tag yet.</p>
        ) : (
          <div className="space-y-4">
            {posts.map((post) => (
              <article
                key={post._id}
                className="flex flex-col gap-1 rounded-2xl border border-white/8 bg-white/4 p-5 hover:border-[var(--vf-brand-border)] transition-colors sm:flex-row sm:items-start sm:gap-6"
              >
                <div className="flex-1">
                  <p className="mb-1 text-xs text-slate-500">
                    <Clock className="inline h-3 w-3 mr-1" />{post.readingTimeMinutes} min ·{" "}
                    {new Date(post.publishedAt).toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric" })}
                  </p>
                  <h2 className="vf-text-1 mb-1.5 text-sm font-bold">
                    <Link href={`/blog/${post.slug}`} className="hover:text-white">{post.title}</Link>
                  </h2>
                  <p className="vf-text-2 text-xs leading-relaxed line-clamp-2">{post.excerpt}</p>
                </div>
                <Link
                  href={`/blog/${post.slug}`}
                  className="flex shrink-0 items-center gap-1 self-end text-xs font-medium text-[var(--vf-brand-primary-light)] hover:text-white"
                >
                  Read <ArrowRight className="h-3 w-3" />
                </Link>
              </article>
            ))}
          </div>
        )}
      </div>
    </>
  );
}
