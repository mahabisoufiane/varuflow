import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { Link } from "@/i18n/navigation";
import { getPostsByCategory, getAllPosts, getCategoryTitle, SEED_CATEGORIES } from "@/lib/sanity/getPosts";
import { ArrowRight, Clock } from "lucide-react";
import JsonLd, { organizationSchema } from "@/components/marketing/JsonLd";
import CTABanner from "@/components/marketing/CTABanner";

export const revalidate = 3600;

const BASE = process.env.NEXT_PUBLIC_SITE_URL ?? "https://varuflow.vercel.app";

interface Params { locale: string; slug: string }

export async function generateStaticParams(): Promise<{ slug: string }[]> {
  return SEED_CATEGORIES.map((c) => ({ slug: c.slug }));
}

export async function generateMetadata({
  params,
}: {
  params: Promise<Params>;
}): Promise<Metadata> {
  const { slug } = await params;
  const title = getCategoryTitle(slug);
  return {
    title: `${title} — Varuflow Blog`,
    description: `All ${title} articles from Varuflow.`,
    alternates: { canonical: `${BASE}/en/blog/category/${slug}` },
    openGraph: {
      title: `${title} — Varuflow Blog`,
      description: `All ${title} articles from Varuflow.`,
      type: "website",
      url: `${BASE}/en/blog/category/${slug}`,
    },
    twitter: { card: "summary_large_image", title: `${title} — Varuflow Blog` },
  };
}

export default async function CategoryPage({ params }: { params: Promise<Params> }) {
  const { slug } = await params;
  const allPosts = await getAllPosts();
  const posts = await getPostsByCategory(slug);
  if (!posts.length && !SEED_CATEGORIES.find((c) => c.slug === slug)) notFound();

  const title = getCategoryTitle(slug);
  const breadcrumb = {
    "@context": "https://schema.org",
    "@type": "BreadcrumbList",
    itemListElement: [
      { "@type": "ListItem", position: 1, name: "Blog", item: `${BASE}/en/blog` },
      { "@type": "ListItem", position: 2, name: title, item: `${BASE}/en/blog/category/${slug}` },
    ],
  };

  return (
    <>
      <JsonLd data={organizationSchema()} />
      <JsonLd data={breadcrumb} />

      <div className="mx-auto max-w-5xl px-4 py-16">
        <nav className="mb-6 flex items-center gap-2 text-xs text-slate-500">
          <Link href="/blog" className="hover:text-slate-300">Blog</Link>
          <span>/</span>
          <span className="text-slate-300">{title}</span>
        </nav>

        <h1 className="vf-text-1 mb-2 text-3xl font-extrabold">{title}</h1>
        <p className="vf-text-2 mb-10 text-sm">{posts.length} article{posts.length !== 1 ? "s" : ""}</p>

        {posts.length === 0 ? (
          <p className="vf-text-2 py-12 text-center">No articles yet. Check back soon.</p>
        ) : (
          <div className="space-y-4">
            {posts.map((post) => (
              <article
                key={post._id}
                className="flex flex-col gap-1 rounded-2xl border border-white/8 bg-white/4 p-5 hover:border-indigo-500/20 transition-colors sm:flex-row sm:items-start sm:gap-6"
              >
                <div className="flex-1">
                  <div className="mb-1.5 flex items-center gap-2 text-xs text-slate-500">
                    <Clock className="h-3 w-3" />{post.readingTimeMinutes} min ·{" "}
                    {new Date(post.publishedAt).toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric" })}
                  </div>
                  <h2 className="vf-text-1 mb-1.5 text-sm font-bold">
                    <Link href={`/blog/${post.slug}`} className="hover:text-indigo-300">{post.title}</Link>
                  </h2>
                  <p className="vf-text-2 text-xs leading-relaxed line-clamp-2">{post.excerpt}</p>
                </div>
                <Link
                  href={`/blog/${post.slug}`}
                  className="flex shrink-0 items-center gap-1 self-end text-xs font-medium text-indigo-400 hover:text-indigo-300"
                >
                  Read <ArrowRight className="h-3 w-3" />
                </Link>
              </article>
            ))}
          </div>
        )}
      </div>

      <CTABanner
        headline="Need help staying compliant?"
        subheadline="Varuflow handles Bokföringslagen, Peppol, ZATCA, and GDPR — so you don't have to."
        ctaPrimary={{ href: "/trial", label: "Start free trial" }}
        ctaSecondary={{ href: "/compliance-overview", label: "See compliance features" }}
      />
    </>
  );
}
