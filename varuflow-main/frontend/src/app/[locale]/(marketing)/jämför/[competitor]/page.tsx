// File: src/app/[locale]/(marketing)/jämför/[competitor]/page.tsx
// Purpose: SEO comparison pages — "Varuflow vs X" for the Swedish market.

import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { Link } from "@/i18n/navigation";
import { ArrowRight, Check, Minus } from "lucide-react";
import JsonLd from "@/components/marketing/JsonLd";
import {
  COMPARE_DIMENSIONS,
  COMPETITOR_SLUGS,
  COMPETITORS,
  getCompetitor,
  type CompetitorSlug,
} from "./competitors";

interface Params {
  locale: string;
  competitor: string;
}

export function generateStaticParams(): { competitor: CompetitorSlug }[] {
  return COMPETITOR_SLUGS.map((competitor) => ({ competitor }));
}

export async function generateMetadata(
  { params }: { params: Promise<Params> },
): Promise<Metadata> {
  const { competitor } = await params;
  const data = getCompetitor(competitor);
  if (!data) return { title: "Varuflow" };
  return {
    title: data.metaTitle,
    description: data.metaDescription,
    openGraph: {
      title: data.metaTitle,
      description: data.metaDescription,
      type: "website",
      locale: "sv_SE",
    },
    alternates: {
      // Use the URL-encoded form of "jämför" so canonical links resolve
      // identically whether the crawler is ä-aware or not.
      canonical: `/sv/j%C3%A4mf%C3%B6r/${data.slug}`,
    },
  };
}

function softwareApplicationJsonLd(title: string) {
  return {
    "@context": "https://schema.org",
    "@type": "SoftwareApplication",
    name: "Varuflow",
    applicationCategory: "BusinessApplication",
    operatingSystem: "Web, iOS, Android",
    description: title,
    offers: { "@type": "Offer", price: "0", priceCurrency: "SEK" },
    url: "https://varuflow.se",
  };
}

function Cell({ value }: { value: string }) {
  // Render "Ja" as a check, "Nej" as a dash, everything else as the raw text.
  if (value === "Ja") return <Check className="h-4 w-4 text-emerald-400 inline" />;
  if (value === "Nej") return <Minus className="h-4 w-4 vf-text-m inline" />;
  return <span className="text-xs vf-text-2">{value}</span>;
}

export default async function ComparePage(
  { params }: { params: Promise<Params> },
) {
  const { competitor } = await params;
  const data = getCompetitor(competitor);
  if (!data) notFound();

  return (
    <div className="mx-auto max-w-5xl px-4 py-16">
      <JsonLd id="jsonld-software" data={softwareApplicationJsonLd(data.metaTitle)} />

      <section className="space-y-6 text-center">
        <p className="text-xs font-semibold uppercase tracking-widest text-[var(--vf-brand-primary-light)]">
          Jämförelse 2026
        </p>
        <h1 className="text-3xl md:text-5xl font-bold tracking-tight vf-text-1">
          Varuflow vs {data.displayName}
        </h1>
        <p className="mx-auto max-w-2xl text-base md:text-lg vf-text-2">
          {data.tagline}
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

      <section
        className="mt-16 vf-section overflow-hidden"
        style={{ borderRadius: 14 }}
      >
        <div className="grid grid-cols-[1.4fr_1fr_1fr] text-xs">
          <div
            className="px-4 py-3 font-semibold uppercase tracking-widest vf-text-m"
            style={{ borderBottom: "1px solid var(--vf-divider)" }}
          >
            Funktion
          </div>
          <div
            className="px-4 py-3 font-semibold text-[var(--vf-brand-primary-light)] text-center"
            style={{ borderBottom: "1px solid var(--vf-divider)" }}
          >
            Varuflow
          </div>
          <div
            className="px-4 py-3 font-semibold vf-text-m text-center"
            style={{ borderBottom: "1px solid var(--vf-divider)" }}
          >
            {data.displayName}
          </div>
          {COMPARE_DIMENSIONS.map((dim, i) => (
            <div key={dim} className="contents">
              <div
                className="px-4 py-3 text-sm vf-text-1"
                style={{
                  borderBottom:
                    i === COMPARE_DIMENSIONS.length - 1
                      ? "none"
                      : "1px solid var(--vf-divider)",
                }}
              >
                {dim}
              </div>
              <div
                className="px-4 py-3 text-center"
                style={{
                  borderBottom:
                    i === COMPARE_DIMENSIONS.length - 1
                      ? "none"
                      : "1px solid var(--vf-divider)",
                  background: "rgba(37,99,235,0.04)",
                }}
              >
                <Cell value={data.varuflow[dim]} />
              </div>
              <div
                className="px-4 py-3 text-center"
                style={{
                  borderBottom:
                    i === COMPARE_DIMENSIONS.length - 1
                      ? "none"
                      : "1px solid var(--vf-divider)",
                }}
              >
                <Cell value={data.competitor[dim]} />
              </div>
            </div>
          ))}
        </div>
      </section>

      <section className="mt-12 text-center space-y-4">
        <h2 className="text-xl md:text-2xl font-semibold vf-text-1">
          Redo att byta?
        </h2>
        <p className="mx-auto max-w-xl text-sm vf-text-2">
          Skapa ett gratis konto och importera din data idag. Ingen
          kreditkort krävs — betala först när du är redo att växa.
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
