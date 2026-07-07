import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { Link } from "@/i18n/navigation";
import { CheckCircle2, ArrowRight } from "lucide-react";
import { REGION_SLUGS, getRegion, type RegionSlug } from "./regions";
import CTABanner from "@/components/marketing/CTABanner";
import JsonLd, { organizationSchema } from "@/components/marketing/JsonLd";

interface Params {
  locale: string;
  region: string;
}

export function generateStaticParams(): { region: RegionSlug }[] {
  return REGION_SLUGS.map((region) => ({ region }));
}

export async function generateMetadata(
  { params }: { params: Promise<Params> },
): Promise<Metadata> {
  const { region: slug } = await params;
  const data = getRegion(slug);
  if (!data) return { title: "Varuflow" };
  const BASE = process.env.NEXT_PUBLIC_SITE_URL ?? "https://varuflow.vercel.app";
  return {
    title: data.metaTitle,
    description: data.metaDescription,
    openGraph: { title: data.metaTitle, description: data.metaDescription, type: "website", locale: data.locale },
    twitter: { card: "summary_large_image", title: data.metaTitle },
    alternates: { canonical: `${BASE}/en/regions/${slug}` },
  };
}

export default async function RegionPage(
  { params }: { params: Promise<Params> },
) {
  const { region: slug } = await params;
  const data = getRegion(slug);
  if (!data) notFound();

  return (
    <>
      <JsonLd data={organizationSchema()} />

      {/* Hero */}
      <section
        className="relative overflow-hidden px-4 py-24 text-center"
        dir={data.dir}
      >
        <div aria-hidden className="pointer-events-none absolute inset-0" style={{ background: "radial-gradient(ellipse 80% 60% at 50% -10%, rgba(37,99,235,0.18) 0%, transparent 70%)" }} />
        <div className="relative mx-auto max-w-3xl">
          <p className="mb-4 inline-block rounded-full border border-[var(--vf-brand-border)] bg-[var(--vf-brand-primary-subtle)] px-4 py-1 text-xs font-semibold uppercase tracking-widest text-[var(--vf-brand-primary-light)]">
            {data.eyebrow}
          </p>
          <h1 className="vf-text-1 text-4xl font-extrabold leading-tight tracking-tight sm:text-5xl">
            {data.headline}
          </h1>
          <p className="vf-text-2 mx-auto mt-6 max-w-2xl text-lg leading-relaxed">
            {data.subheadline}
          </p>
          <div className="mt-10 flex flex-col items-center justify-center gap-3 sm:flex-row">
            <Link href="/trial" className="vf-btn inline-flex items-center gap-2 rounded-xl px-7 py-3 text-base font-semibold">
              {data.ctaLabel} <ArrowRight className="h-4 w-4" />
            </Link>
            <Link href="/demo" className="vf-btn-ghost rounded-xl px-7 py-3 text-base font-semibold">
              Book a demo
            </Link>
          </div>
        </div>
      </section>

      {/* Compliance highlights */}
      <section className="px-4 py-12" dir={data.dir}>
        <div className="mx-auto max-w-3xl">
          <h2 className="vf-text-1 mb-6 text-center text-xl font-bold">
            Compliance & localization
          </h2>
          <div className="grid gap-3 sm:grid-cols-2">
            {data.complianceHighlights.map((point) => (
              <div key={point} className="flex items-center gap-3 rounded-xl border border-white/8 bg-white/4 px-4 py-3">
                <CheckCircle2 className="h-4 w-4 shrink-0 text-green-500" />
                <span className="vf-text-2 text-sm">{point}</span>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Region-specific features */}
      <section className="px-4 py-12" dir={data.dir}>
        <div className="mx-auto max-w-4xl">
          <h2 className="vf-text-1 mb-6 text-center text-xl font-bold">
            Built for {data.slug.toUpperCase()}
          </h2>
          <div className="grid gap-4 sm:grid-cols-3">
            {data.features.map((f) => (
              <div key={f.title} className="rounded-2xl border border-white/8 bg-white/4 p-6">
                <h3 className="vf-text-1 mb-2 text-sm font-semibold">{f.title}</h3>
                <p className="vf-text-2 text-sm leading-relaxed">{f.description}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Pricing note */}
      <div className="mx-auto max-w-xl px-4 py-6 text-center">
        <p className="vf-text-m text-sm">
          Local pricing: starting at{" "}
          <span className="vf-text-1 font-semibold">{data.pricingFrom}</span>
        </p>
      </div>

      <CTABanner
        headline={`Start free in ${data.slug.toUpperCase()}`}
        subheadline={`${data.pricingFrom} — 14-day Pro trial included.`}
        ctaPrimary={{ href: "/trial", label: data.ctaLabel }}
        ctaSecondary={{ href: "/pricing", label: "See all plans" }}
      />
    </>
  );
}
