import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { Link } from "@/i18n/navigation";
import { CheckCircle2, ArrowRight } from "lucide-react";
import { VERTICAL_SLUGS, getVertical, type VerticalSlug } from "./verticals";
import TestimonialCarousel from "@/components/marketing/TestimonialCarousel";
import CTABanner from "@/components/marketing/CTABanner";
import JsonLd, { softwareApplicationSchema } from "@/components/marketing/JsonLd";
import FeatureCard from "@/components/marketing/FeatureCard";
import { Package } from "lucide-react";

interface Params {
  locale: string;
  vertical: string;
}

export function generateStaticParams(): { vertical: VerticalSlug }[] {
  return VERTICAL_SLUGS.map((vertical) => ({ vertical }));
}

export async function generateMetadata(
  { params }: { params: Promise<Params> },
): Promise<Metadata> {
  const { vertical: slug } = await params;
  const data = getVertical(slug);
  if (!data) return { title: "Varuflow" };
  const BASE = process.env.NEXT_PUBLIC_SITE_URL ?? "https://varuflow.vercel.app";
  return {
    title: data.metaTitle,
    description: data.metaDescription,
    openGraph: { title: data.metaTitle, description: data.metaDescription, type: "website" },
    twitter: { card: "summary_large_image", title: data.metaTitle },
    alternates: { canonical: `${BASE}/en/verticals/${slug}` },
  };
}

export default async function VerticalPage(
  { params }: { params: Promise<Params> },
) {
  const { vertical: slug } = await params;
  const data = getVertical(slug);
  if (!data) notFound();

  return (
    <>
      <JsonLd data={softwareApplicationSchema(data.subheadline)} />

      {/* Hero */}
      <section className="relative overflow-hidden px-4 py-24 text-center">
        <div aria-hidden className="pointer-events-none absolute inset-0" style={{ background: "radial-gradient(ellipse 80% 60% at 50% -10%, rgba(99,102,241,0.18) 0%, transparent 70%)" }} />
        <div className="relative mx-auto max-w-3xl">
          <p className="mb-4 inline-block rounded-full border border-indigo-500/30 bg-indigo-500/10 px-4 py-1 text-xs font-semibold uppercase tracking-widest text-indigo-400">
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

      {/* Features */}
      <section className="px-4 py-16">
        <div className="mx-auto max-w-5xl">
          <h2 className="vf-text-1 mb-8 text-center text-2xl font-bold">Built for your workflow</h2>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {data.features.map((f) => (
              <FeatureCard key={f.title} icon={<Package className="h-5 w-5" />} title={f.title} description={f.description} />
            ))}
          </div>
        </div>
      </section>

      {/* Testimonials */}
      {data.testimonials.length > 0 && (
        <section className="px-4 py-16" style={{ background: "rgba(255,255,255,0.03)" }}>
          <TestimonialCarousel testimonials={data.testimonials} />
        </section>
      )}

      <CTABanner
        headline={`Start your free ${data.slug} trial today`}
        subheadline="14-day Pro trial, no credit card required."
        ctaPrimary={{ href: "/trial", label: "Start free trial" }}
        ctaSecondary={{ href: "/pricing", label: "See pricing" }}
      />
    </>
  );
}
