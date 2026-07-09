import type { Metadata } from "next";
import { ArrowRight, Check } from "lucide-react";
import { getTranslations, setRequestLocale } from "next-intl/server";
import { notFound } from "next/navigation";
import { Link } from "@/i18n/navigation";
import { Card } from "@/components/ui/Card";
import { Container } from "@/components/ui/Container";
import { Section } from "@/components/ui/Section";
import { MODULES } from "@/content/modules";
import { JsonLd } from "@/components/site/JsonLd";
import { pageMetadata, SITE_URL } from "@/lib/seo";

const APP_URL = process.env.NEXT_PUBLIC_APP_URL ?? "https://varuflow.vercel.app";

type AppLocale = "sv" | "en";
type Params = Promise<{ locale: string; slug: string }>;

export function generateStaticParams() {
  // Slugs only — the [locale] layout's generateStaticParams provides the
  // locales, and Next multiplies the two segments (6 slugs × 2 locales).
  return MODULES.map((m) => ({ slug: m.slug }));
}

export async function generateMetadata({ params }: { params: Params }): Promise<Metadata> {
  const { locale, slug } = await params;
  const m = MODULES.find((x) => x.slug === slug);
  if (!m) return {};
  const loc: AppLocale = locale === "en" ? "en" : "sv";
  return pageMetadata({
    locale,
    path: `/modules/${slug}`,
    title: m.name[loc],
    description: m.description[loc],
  });
}

export default async function ModulePage({ params }: { params: Params }) {
  const { locale, slug } = await params;
  setRequestLocale(locale);
  const m = MODULES.find((x) => x.slug === slug);
  if (!m) notFound();
  const t = await getTranslations("moduleTemplate");
  const loc: AppLocale = locale === "en" ? "en" : "sv";

  const related = m.related
    .map((r) => MODULES.find((x) => x.slug === r))
    .filter((x): x is NonNullable<typeof x> => Boolean(x));

  const crumbs = [
    { name: loc === "sv" ? "Hem" : "Home", path: "" },
    { name: loc === "sv" ? "Moduler" : "Modules", path: "/modules" },
    { name: m.name[loc], path: `/modules/${m.slug}` },
  ];

  return (
    <>
      <JsonLd
        data={{
          "@context": "https://schema.org",
          "@type": "BreadcrumbList",
          itemListElement: crumbs.map((c, i) => ({
            "@type": "ListItem",
            position: i + 1,
            name: c.name,
            item: `${SITE_URL}/${locale}${c.path}`,
          })),
        }}
      />
      {/* Hero */}
      <Section className="pt-16 sm:pt-24">
        <Container>
          <div className="max-w-3xl">
            <h1 className="[overflow-wrap:anywhere] hyphens-auto font-display text-3xl font-bold tracking-tight text-ink sm:text-display">
              {m.name[loc]}
            </h1>
            <p className="mt-6 text-body text-mist">{m.valueProp[loc]}</p>
          </div>
        </Container>
      </Section>

      {/* Capabilities + screenshot placeholder */}
      <Section shaded>
        <Container>
          <h2 className="font-display text-headline font-bold text-ink">{t("capabilities")}</h2>
          <div className="mt-10 grid gap-6 lg:grid-cols-3">
            {m.capabilities.map((cap) => (
              <Card key={cap.title.en}>
                <Check className="h-5 w-5 text-accent" strokeWidth={2.5} />
                <h3 className="mt-3 text-title font-semibold text-ink">{cap.title[loc]}</h3>
                <p className="mt-2 text-small text-mist">{cap.description[loc]}</p>
              </Card>
            ))}
          </div>

          {/* Flat CSS screenshot placeholder — replaced with a real capture later */}
          <div
            aria-label={t("screenshotAlt")}
            role="img"
            className="mt-12 rounded-card border border-line bg-paper p-3"
          >
            <div className="flex items-center gap-1.5 px-2 pb-3">
              <span className="h-2.5 w-2.5 rounded-full bg-line" />
              <span className="h-2.5 w-2.5 rounded-full bg-line" />
              <span className="h-2.5 w-2.5 rounded-full bg-line" />
            </div>
            <div className="grid gap-3 rounded-lg bg-paper-shade p-6 sm:grid-cols-4">
              <div className="h-24 rounded-lg border border-line bg-paper" />
              <div className="h-24 rounded-lg border border-line bg-paper" />
              <div className="h-24 rounded-lg border border-line bg-paper" />
              <div className="h-24 rounded-lg border border-line bg-paper" />
              <div className="h-40 rounded-lg border border-line bg-paper sm:col-span-3" />
              <div className="h-40 rounded-lg border border-line bg-paper" />
            </div>
          </div>
        </Container>
      </Section>

      {/* Works well with */}
      <Section>
        <Container>
          <h2 className="font-display text-headline font-bold text-ink">{t("worksWith")}</h2>
          <div className="mt-8 grid gap-6 sm:grid-cols-2">
            {related.map((r) => (
              <Link key={r.slug} href={`/modules/${r.slug}`} className="group">
                <Card className="h-full transition-colors group-hover:border-brand">
                  <h3 className="text-title font-semibold text-ink">{r.name[loc]}</h3>
                  <p className="mt-2 text-small text-mist">{r.description[loc]}</p>
                  <span className="mt-4 inline-flex items-center gap-1 text-small font-semibold text-brand">
                    <ArrowRight className="h-4 w-4 transition-transform group-hover:translate-x-0.5" />
                  </span>
                </Card>
              </Link>
            ))}
          </div>
        </Container>
      </Section>

      {/* CTA band */}
      <section className="bg-ink py-20 text-center">
        <Container>
          <h2 className="[overflow-wrap:anywhere] hyphens-auto font-display text-title font-bold text-white sm:text-headline">
            {t("ctaTitle", { module: m.name[loc] })}
          </h2>
          <p className="mx-auto mt-4 max-w-xl text-body text-white/70">{t("ctaSub")}</p>
          <a
            href={`${APP_URL}/sv/auth/signup`}
            className="mt-8 inline-flex items-center justify-center rounded-full bg-white px-8 py-3.5 text-body font-semibold text-ink transition-colors hover:bg-paper-shade"
          >
            {t("cta")}
          </a>
        </Container>
      </section>
    </>
  );
}
