import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { Link } from "@/i18n/navigation";
import { ArrowRight } from "lucide-react";
import { VS_SLUGS, getVsData, type VsSlug } from "./vscompetitors";
import ComparisonTable from "@/components/marketing/ComparisonTable";
import CTABanner from "@/components/marketing/CTABanner";
import JsonLd, { organizationSchema } from "@/components/marketing/JsonLd";

interface Params {
  locale: string;
  competitor: string;
}

export function generateStaticParams(): { competitor: VsSlug }[] {
  return VS_SLUGS.map((competitor) => ({ competitor }));
}

export async function generateMetadata(
  { params }: { params: Promise<Params> },
): Promise<Metadata> {
  const { competitor: slug } = await params;
  const data = getVsData(slug);
  if (!data) return { title: "Varuflow" };
  const BASE = process.env.NEXT_PUBLIC_SITE_URL ?? "https://varuflow.vercel.app";
  return {
    title: data.metaTitle,
    description: data.metaDescription,
    openGraph: { title: data.metaTitle, description: data.metaDescription, type: "website" },
    twitter: { card: "summary_large_image", title: data.metaTitle },
    alternates: { canonical: `${BASE}/en/vs/${slug}` },
  };
}

export default async function VsPage(
  { params }: { params: Promise<Params> },
) {
  const { competitor: slug } = await params;
  const data = getVsData(slug);
  if (!data) notFound();

  const displaySlug = slug.charAt(0).toUpperCase() + slug.slice(1);

  return (
    <>
      <JsonLd data={organizationSchema()} />

      {/* Hero */}
      <section className="px-4 py-20 text-center">
        <p className="mb-4 inline-block rounded-full border border-[var(--vf-brand-border)] bg-[var(--vf-brand-primary-subtle)] px-4 py-1 text-xs font-semibold uppercase tracking-widest text-[var(--vf-brand-primary-light)]">
          {data.angle}
        </p>
        <h1 className="vf-text-1 text-4xl font-extrabold tracking-tight sm:text-5xl">
          {data.headline}
        </h1>
        <p className="vf-text-2 mx-auto mt-4 max-w-xl text-lg leading-relaxed">
          {data.tagline}
        </p>
        <div className="mt-8 flex flex-col items-center justify-center gap-3 sm:flex-row">
          <Link href="/trial" className="vf-btn inline-flex items-center gap-2 rounded-xl px-7 py-3 text-base font-semibold">
            Start free trial <ArrowRight className="h-4 w-4" />
          </Link>
          <Link href="/pricing" className="vf-btn-ghost rounded-xl px-7 py-3 text-base font-semibold">
            See pricing
          </Link>
        </div>
      </section>

      {/* Comparison table */}
      <section className="px-4 py-8">
        <h2 className="vf-text-1 mb-8 text-center text-xl font-bold">
          Varuflow vs {displaySlug} — feature comparison
        </h2>
        <ComparisonTable
          competitorName={displaySlug}
          rows={data.rows}
        />
      </section>

      {/* Customer quote */}
      <section className="mx-auto max-w-2xl px-4 py-16 text-center">
        <blockquote className="vf-text-1 text-lg font-medium leading-relaxed">
          &ldquo;{data.customerQuote.quote}&rdquo;
        </blockquote>
        <div className="mt-4 flex items-center justify-center gap-3">
          <div className="flex h-8 w-8 items-center justify-center rounded-full bg-[var(--vf-brand-primary)] text-xs font-bold text-white">
            {data.customerQuote.initials}
          </div>
          <p className="vf-text-2 text-sm">
            {data.customerQuote.author} · {data.customerQuote.company}
          </p>
        </div>
      </section>

      <CTABanner
        headline={data.migrationCta}
        subheadline="14-day Pro trial — full access, no credit card."
        ctaPrimary={{ href: "/trial", label: `Switch from ${displaySlug} free` }}
        ctaSecondary={{ href: "/demo", label: "Book a migration walkthrough" }}
      />
    </>
  );
}
