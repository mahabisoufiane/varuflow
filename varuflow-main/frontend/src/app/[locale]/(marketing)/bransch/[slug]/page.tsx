// File: src/app/[locale]/(marketing)/bransch/[slug]/page.tsx
// Purpose: Static Swedish-market industry landing pages for SEO/lead-gen.
// Pre-rendered at build via generateStaticParams. Schema.org SoftwareApplication
// JSON-LD is injected so Google can pick it up for rich-results eligibility.

import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { Link } from "@/i18n/navigation";
import { ArrowRight, CheckCircle2 } from "lucide-react";
import JsonLd from "@/components/marketing/JsonLd";
import {
  INDUSTRIES,
  INDUSTRY_SLUGS,
  getIndustry,
  type IndustrySlug,
} from "./industries";

interface Params {
  locale: string;
  slug: string;
}

export function generateStaticParams(): { slug: IndustrySlug }[] {
  return INDUSTRY_SLUGS.map((slug) => ({ slug }));
}

export async function generateMetadata(
  { params }: { params: Promise<Params> },
): Promise<Metadata> {
  const { slug } = await params;
  const industry = getIndustry(slug);
  if (!industry) {
    return { title: "Varuflow" };
  }
  return {
    title: industry.metaTitle,
    description: industry.metaDescription,
    openGraph: {
      title: industry.metaTitle,
      description: industry.metaDescription,
      type: "website",
      locale: "sv_SE",
    },
    alternates: {
      canonical: `/sv/bransch/${industry.slug}`,
    },
  };
}

function softwareApplicationJsonLd(industryHeadline: string) {
  // Schema.org SoftwareApplication — lets Google surface pricing / rating
  // in the SERP once we have customer reviews to populate the fields.
  // Keep this minimal until we have real rating data (otherwise Google
  // Search Console flags the markup as spam).
  return {
    "@context": "https://schema.org",
    "@type": "SoftwareApplication",
    name: "Varuflow",
    applicationCategory: "BusinessApplication",
    operatingSystem: "Web, iOS, Android",
    description: industryHeadline,
    offers: {
      "@type": "Offer",
      price: "0",
      priceCurrency: "SEK",
    },
    url: "https://varuflow.se",
  };
}

export default async function IndustryPage(
  { params }: { params: Promise<Params> },
) {
  const { slug } = await params;
  const industry = getIndustry(slug);
  if (!industry) notFound();

  return (
    <div className="mx-auto max-w-5xl px-4 py-16">
      <JsonLd id="jsonld-software" data={softwareApplicationJsonLd(industry.headline)} />

      <section className="space-y-6 text-center">
        <p className="text-xs font-semibold uppercase tracking-widest text-[var(--vf-brand-primary-light)]">
          För svenska {industry.slug}-företag
        </p>
        <h1 className="text-3xl md:text-5xl font-bold tracking-tight vf-text-1">
          {industry.headline}
        </h1>
        <p className="mx-auto max-w-2xl text-base md:text-lg vf-text-2">
          {industry.subheadline}
        </p>
        <div className="flex items-center justify-center gap-3 pt-2">
          <Link
            href="/onboarding"
            className="vf-btn inline-flex items-center gap-2 px-5 h-11 text-sm"
          >
            Starta gratis
            <ArrowRight className="h-4 w-4" />
          </Link>
          <Link
            href="/pricing"
            className="vf-btn-ghost inline-flex items-center px-5 h-11 text-sm"
          >
            Se priser
          </Link>
        </div>
      </section>

      <section className="mt-16 grid gap-3 md:grid-cols-2">
        {industry.features.map((feat) => (
          <div
            key={feat}
            className="vf-section p-5 flex items-start gap-3"
            style={{ borderRadius: 14 }}
          >
            <CheckCircle2 className="h-5 w-5 text-emerald-400 shrink-0 mt-0.5" />
            <p className="text-sm vf-text-2">{feat}</p>
          </div>
        ))}
      </section>

      <section
        className="mt-16 vf-section p-6 text-center"
        style={{ borderRadius: 14 }}
      >
        <p className="text-sm vf-text-m italic">{industry.socialProof}</p>
      </section>

      <section className="mt-12 text-center space-y-4">
        <h2 className="text-xl md:text-2xl font-semibold vf-text-1">
          Kom igång på mindre än fem minuter
        </h2>
        <p className="mx-auto max-w-xl text-sm vf-text-2">
          Skapa ett gratis konto, importera din produktkatalog och skicka din
          första faktura. Ingen kreditkort krävs.
        </p>
        <Link
          href="/onboarding"
          className="vf-btn inline-flex items-center gap-2 px-5 h-11 text-sm"
        >
          Starta gratis
          <ArrowRight className="h-4 w-4" />
        </Link>
      </section>
    </div>
  );
}
