import type { Metadata } from "next";
import { notFound } from "next/navigation";
import Image from "next/image";
import { Link } from "@/i18n/navigation";
import {
  getAllPostSlugs,
  getPostBySlug,
  getAllPosts,
  getCategoryTitle,
} from "@/lib/sanity/getPosts";
import { SanityBody } from "@/lib/sanity/portableText";
import TableOfContents from "./TableOfContents";
import ShareButtons from "./ShareButtons";
import LeadMagnetForm from "@/components/marketing/LeadMagnetForm";
import CTABanner from "@/components/marketing/CTABanner";
import JsonLd, { organizationSchema } from "@/components/marketing/JsonLd";
import { ArrowLeft, Clock, Calendar, ArrowRight } from "lucide-react";

export const revalidate = 3600;

const BASE = process.env.NEXT_PUBLIC_SITE_URL ?? "https://varuflow.vercel.app";

interface Params { locale: string; slug: string }

export async function generateStaticParams(): Promise<{ slug: string }[]> {
  const slugs = await getAllPostSlugs();
  return slugs.map((slug) => ({ slug }));
}

export async function generateMetadata({
  params,
}: {
  params: Promise<Params>;
}): Promise<Metadata> {
  const { slug, locale } = await params;
  const post = await getPostBySlug(slug);
  if (!post) return { title: "Varuflow Blog" };

  const canonical = post.canonicalUrl ?? `${BASE}/${locale}/blog/${slug}`;
  const alternates: Record<string, string> = {};
  if (post.translationSlug) {
    const otherLocale = post.locale === "en" ? "sv" : post.locale === "sv" ? "en" : "ar";
    alternates[otherLocale] = `${BASE}/${otherLocale}/blog/${post.translationSlug}`;
    alternates[post.locale] = canonical;
    alternates["x-default"] = `${BASE}/en/blog/${post.locale === "en" ? slug : post.translationSlug ?? slug}`;
  }

  return {
    title: post.seoTitle || post.title,
    description: post.seoDescription || post.excerpt,
    openGraph: {
      title: post.seoTitle || post.title,
      description: post.seoDescription || post.excerpt,
      type: "article",
      publishedTime: post.publishedAt,
      modifiedTime: post.updatedAt,
      authors: [post.author.name],
      images: [
        {
          url: `${BASE}/api/og?title=${encodeURIComponent(post.seoTitle || post.title)}&category=${encodeURIComponent(getCategoryTitle(post.category))}`,
          width: 1200,
          height: 630,
          alt: post.featuredImageAlt,
        },
      ],
    },
    twitter: {
      card: "summary_large_image",
      title: post.seoTitle || post.title,
      description: post.seoDescription || post.excerpt,
    },
    alternates: {
      canonical,
      languages: Object.keys(alternates).length ? alternates : undefined,
    },
  };
}

export default async function ArticlePage({ params }: { params: Promise<Params> }) {
  const { slug, locale } = await params;
  const post = await getPostBySlug(slug);
  if (!post) notFound();

  const allPosts = await getAllPosts();
  const related = allPosts
    .filter((p) => p.slug !== slug && p.category === post.category)
    .slice(0, 3);

  const publishDate = new Date(post.publishedAt).toLocaleDateString("en-GB", {
    day: "numeric",
    month: "long",
    year: "numeric",
  });
  const updateDate = new Date(post.updatedAt).toLocaleDateString("en-GB", {
    day: "numeric",
    month: "long",
    year: "numeric",
  });

  const articleSchema = {
    "@context": "https://schema.org",
    "@type": "BlogPosting",
    headline: post.seoTitle || post.title,
    description: post.seoDescription || post.excerpt,
    datePublished: post.publishedAt,
    dateModified: post.updatedAt,
    author: {
      "@type": "Person",
      name: post.author.name,
      jobTitle: post.author.role,
    },
    publisher: {
      "@type": "Organization",
      name: "Varuflow",
      url: BASE,
    },
    mainEntityOfPage: { "@type": "WebPage", "@id": `${BASE}/${locale}/blog/${slug}` },
  };

  const breadcrumb = {
    "@context": "https://schema.org",
    "@type": "BreadcrumbList",
    itemListElement: [
      { "@type": "ListItem", position: 1, name: "Blog", item: `${BASE}/en/blog` },
      {
        "@type": "ListItem",
        position: 2,
        name: getCategoryTitle(post.category),
        item: `${BASE}/en/blog/category/${post.category}`,
      },
      { "@type": "ListItem", position: 3, name: post.title, item: `${BASE}/${locale}/blog/${slug}` },
    ],
  };

  return (
    <>
      <JsonLd data={organizationSchema()} />
      <JsonLd data={articleSchema} />
      <JsonLd data={breadcrumb} />

      <div className="mx-auto max-w-6xl px-4 py-12">
        {/* Breadcrumb */}
        <nav className="mb-6 flex items-center gap-2 text-xs text-slate-500">
          <Link href="/blog" className="flex items-center gap-1 hover:text-slate-300">
            <ArrowLeft className="h-3 w-3" /> Blog
          </Link>
          <span>/</span>
          <Link href={`/blog/category/${post.category}`} className="hover:text-slate-300">
            {getCategoryTitle(post.category)}
          </Link>
        </nav>

        <div className="grid gap-10 lg:grid-cols-[1fr_280px]">
          {/* Article */}
          <article>
            {/* Header */}
            <header className="mb-10">
              <div className="mb-4 flex flex-wrap items-center gap-3">
                <span className="rounded-full border border-indigo-500/20 bg-indigo-500/10 px-2.5 py-0.5 text-xs font-semibold text-indigo-400">
                  {getCategoryTitle(post.category)}
                </span>
                <span className="flex items-center gap-1 text-xs text-slate-500">
                  <Clock className="h-3 w-3" /> {post.readingTimeMinutes} min read
                </span>
              </div>

              <h1 className="vf-text-1 text-2xl font-extrabold leading-tight tracking-tight sm:text-3xl">
                {post.title}
              </h1>

              <p className="vf-text-2 mt-4 text-base leading-relaxed">{post.excerpt}</p>

              <div className="mt-6 flex flex-wrap items-center justify-between gap-4 border-t border-b border-white/8 py-4">
                {/* Author */}
                <div className="flex items-center gap-3">
                  <div className="flex h-9 w-9 items-center justify-center rounded-full bg-indigo-600 text-xs font-bold text-white">
                    {post.author.initials}
                  </div>
                  <div>
                    <p className="text-sm font-medium text-white">{post.author.name}</p>
                    <p className="text-xs text-slate-500">{post.author.role}</p>
                  </div>
                </div>
                {/* Dates */}
                <div className="text-right text-xs text-slate-500">
                  <p className="flex items-center gap-1">
                    <Calendar className="h-3 w-3" /> Published {publishDate}
                  </p>
                  {updateDate !== publishDate && (
                    <p className="mt-0.5">Updated {updateDate}</p>
                  )}
                </div>
              </div>

              {/* Share */}
              <div className="mt-4">
                <ShareButtons
                  url={`${BASE}/${locale}/blog/${slug}`}
                  title={post.title}
                />
              </div>
            </header>

            {/* Body */}
            <div className="article-body">
              {post.body && (post.body as unknown[]).length > 0 ? (
                <SanityBody body={post.body as unknown[]} />
              ) : (
                <div
                  className="prose prose-invert prose-sm max-w-none text-slate-300
                    prose-h2:mt-12 prose-h2:mb-4 prose-h2:text-xl prose-h2:font-bold prose-h2:text-white prose-h2:[scroll-margin-top:80px]
                    prose-h3:mt-8 prose-h3:mb-3 prose-h3:text-base prose-h3:font-semibold prose-h3:text-white prose-h3:[scroll-margin-top:80px]
                    prose-p:my-4 prose-p:leading-relaxed
                    prose-ul:my-4 prose-ul:ml-6 prose-li:my-1
                    prose-ol:my-4 prose-ol:ml-6
                    prose-blockquote:my-6 prose-blockquote:border-l-4 prose-blockquote:border-indigo-500 prose-blockquote:pl-5 prose-blockquote:italic prose-blockquote:text-slate-300
                    prose-table:my-6 prose-table:w-full prose-table:border-collapse
                    prose-th:border prose-th:border-white/12 prose-th:px-3 prose-th:py-2 prose-th:text-left prose-th:text-sm prose-th:font-semibold prose-th:text-white prose-th:bg-white/6
                    prose-td:border prose-td:border-white/8 prose-td:px-3 prose-td:py-2 prose-td:text-sm
                    prose-a:text-indigo-400 prose-a:underline hover:prose-a:text-indigo-300
                    prose-strong:text-white prose-code:text-indigo-300 prose-code:bg-white/8 prose-code:rounded prose-code:px-1 prose-code:py-0.5 prose-code:text-xs"
                  dangerouslySetInnerHTML={{ __html: post.bodyHtml }}
                />
              )}
            </div>

            {/* CTA box at article end */}
            <div className="mt-12 rounded-2xl border border-indigo-500/20 bg-indigo-500/8 p-6">
              <h3 className="vf-text-1 mb-2 text-base font-bold">{post.cta.headline}</h3>
              <p className="vf-text-2 mb-4 text-sm">{post.cta.body}</p>
              <Link
                href={post.cta.href}
                className="vf-btn inline-flex items-center gap-2 rounded-xl px-5 py-2.5 text-sm font-semibold"
              >
                {post.cta.buttonLabel} <ArrowRight className="h-4 w-4" />
              </Link>
            </div>

            {/* Author bio */}
            <div className="mt-8 flex items-start gap-4 rounded-2xl border border-white/8 bg-white/4 p-5">
              <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-full bg-indigo-600 text-sm font-bold text-white">
                {post.author.initials}
              </div>
              <div>
                <p className="font-semibold text-white">{post.author.name}</p>
                <p className="text-xs text-slate-400">{post.author.role}</p>
                <p className="vf-text-2 mt-2 text-sm leading-relaxed">{post.author.bio}</p>
              </div>
            </div>

            {/* Tags */}
            <div className="mt-6 flex flex-wrap gap-2">
              {post.tags.map((tag) => (
                <Link
                  key={tag}
                  href={`/blog/tag/${tag.toLowerCase().replace(/\s+/g, "-")}`}
                  className="rounded-full border border-white/8 px-3 py-1 text-xs text-slate-400 hover:border-white/20 hover:text-white transition-colors"
                >
                  #{tag}
                </Link>
              ))}
            </div>

            {/* Share (bottom) */}
            <div className="mt-6 flex justify-end">
              <ShareButtons url={`${BASE}/${locale}/blog/${slug}`} title={post.title} />
            </div>
          </article>

          {/* Sidebar */}
          <aside className="space-y-6">
            <TableOfContents items={post.tableOfContents} />

            {post.leadMagnet && (
              <LeadMagnetForm
                title={post.leadMagnet.title}
                description={post.leadMagnet.description}
                pdfSlug={post.leadMagnet.pdfSlug}
                buttonLabel={post.leadMagnet.buttonLabel}
              />
            )}

            {/* External links */}
            {post.externalLinks.length > 0 && (
              <div className="rounded-xl border border-white/8 bg-white/4 p-4">
                <p className="mb-3 text-xs font-semibold uppercase tracking-wide text-slate-400">
                  Official sources
                </p>
                <ul className="space-y-2">
                  {post.externalLinks.map((link) => (
                    <li key={link.href}>
                      <a
                        href={link.href}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="flex items-center gap-1 text-xs text-indigo-400 hover:text-indigo-300"
                      >
                        <ArrowRight className="h-3 w-3 shrink-0" />
                        {link.label}
                      </a>
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </aside>
        </div>

        {/* Related articles */}
        {related.length > 0 && (
          <section className="mt-16 border-t border-white/8 pt-10">
            <h2 className="vf-text-1 mb-6 text-xl font-bold">Related articles</h2>
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
              {related.map((rel) => (
                <article
                  key={rel._id}
                  className="rounded-2xl border border-white/8 bg-white/4 p-5 hover:border-indigo-500/20 transition-colors"
                >
                  <p className="mb-1.5 text-xs text-slate-500">
                    <Clock className="inline h-3 w-3 mr-1" />{rel.readingTimeMinutes} min
                  </p>
                  <h3 className="vf-text-1 mb-2 text-sm font-bold leading-snug">
                    <Link href={`/blog/${rel.slug}`} className="hover:text-indigo-300">
                      {rel.title}
                    </Link>
                  </h3>
                  <p className="vf-text-2 text-xs line-clamp-2">{rel.excerpt}</p>
                </article>
              ))}
            </div>
          </section>
        )}
      </div>

      <CTABanner
        headline="Ready to simplify your compliance?"
        subheadline="14-day Pro trial — full access, no credit card."
        ctaPrimary={{ href: "/trial", label: "Start free trial" }}
        ctaSecondary={{ href: "/demo", label: "Book a demo" }}
      />
    </>
  );
}
