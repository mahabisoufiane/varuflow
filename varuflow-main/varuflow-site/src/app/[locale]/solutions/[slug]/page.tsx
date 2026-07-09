import type { Metadata } from "next";
import { ArrowRight, ShieldCheck } from "lucide-react";
import { getTranslations, setRequestLocale } from "next-intl/server";
import { notFound } from "next/navigation";
import { Link } from "@/i18n/navigation";
import { BookDemoButton } from "@/components/site/BookDemoButton";
import { Card } from "@/components/ui/Card";
import { Container } from "@/components/ui/Container";
import { Section } from "@/components/ui/Section";
import { MODULES } from "@/content/modules";
import { SOLUTIONS } from "@/content/solutions";
import { JsonLd } from "@/components/site/JsonLd";
import { pageMetadata, SITE_URL } from "@/lib/seo";

const APP_URL = process.env.NEXT_PUBLIC_APP_URL ?? "https://varuflow.vercel.app";

type AppLocale = "sv" | "en";
type Params = Promise<{ locale: string; slug: string }>;

export function generateStaticParams() {
  // Slugs only — locales come from the [locale] layout (3 slugs × 2 locales).
  return SOLUTIONS.map((s) => ({ slug: s.slug }));
}

export async function generateMetadata({ params }: { params: Params }): Promise<Metadata> {
  const { locale, slug } = await params;
  const s = SOLUTIONS.find((x) => x.slug === slug);
  if (!s) return {};
  const loc: AppLocale = locale === "en" ? "en" : "sv";
  // Title <60 / description <155: eyebrow is short; subheadlines exceed
  // 155, so meta description uses "eyebrow — headline" instead.
  return pageMetadata({
    locale,
    path: `/solutions/${slug}`,
    title: s.eyebrow[loc],
    description: `${s.eyebrow[loc]} — ${s.headline[loc]}`,
  });
}

export default async function SolutionPage({ params }: { params: Params }) {
  const { locale, slug } = await params;
  setRequestLocale(locale);
  const s = SOLUTIONS.find((x) => x.slug === slug);
  if (!s) notFound();
  const t = await getTranslations("solutionTemplate");
  const loc: AppLocale = locale === "en" ? "en" : "sv";

  const crumbs = [
    { name: loc === "sv" ? "Hem" : "Home", path: "" },
    { name: loc === "sv" ? "Lösningar" : "Solutions", path: "/solutions" },
    { name: s.eyebrow[loc], path: `/solutions/${s.slug}` },
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
            <p className="text-small font-semibold uppercase tracking-wide text-brand">
              {s.eyebrow[loc]}
            </p>
            <h1 className="mt-3 font-display text-4xl font-bold tracking-tight text-ink sm:text-display">
              {s.headline[loc]}
            </h1>
            <p className="mt-6 text-body text-mist">{s.subheadline[loc]}</p>
          </div>
        </Container>
      </Section>

      {/* Pain points → module-mapped solutions */}
      <Section shaded>
        <Container>
          <h2 className="font-display text-headline font-bold text-ink">{t("painsTitle")}</h2>
          <div className="mt-10 space-y-6">
            {s.painPoints.map((p) => {
              const mod = MODULES.find((m) => m.slug === p.moduleSlug);
              return (
                <Card key={p.pain.en} className="grid gap-6 lg:grid-cols-2">
                  <div>
                    <h3 className="text-title font-semibold text-ink">{p.pain[loc]}</h3>
                    <p className="mt-2 text-small text-mist">{p.detail[loc]}</p>
                  </div>
                  <div className="border-line lg:border-l lg:pl-6">
                    <p className="text-small text-ink-soft">{p.solution[loc]}</p>
                    {mod && (
                      <Link
                        href={`/modules/${mod.slug}`}
                        className="mt-3 inline-flex items-center gap-1.5 text-small font-semibold text-brand hover:text-brand-strong"
                      >
                        {t("solvedWith")}: {mod.name[loc]}
                        <ArrowRight className="h-4 w-4" />
                      </Link>
                    )}
                  </div>
                </Card>
              );
            })}
          </div>

          {/* Compliance note */}
          <div className="mt-10 flex items-start gap-3 rounded-card border border-line bg-paper p-6">
            <ShieldCheck className="mt-0.5 h-5 w-5 shrink-0 text-accent" strokeWidth={2} />
            <p className="text-small text-ink-soft">{s.compliance[loc]}</p>
          </div>
        </Container>
      </Section>

      {/* First-customers band — honest early-stage pitch, no fake case studies */}
      <section className="bg-ink py-20 text-center">
        <Container>
          <h2 className="mx-auto max-w-2xl hyphens-auto break-words font-display text-title font-bold text-white sm:text-headline">
            {t("firstCustomer", { vertical: t(`verticalNames.${s.slug}`) })}
          </h2>
          <p className="mx-auto mt-4 max-w-xl text-body text-white/70">{t("firstCustomerSub")}</p>
          <div className="mt-8 flex flex-col items-center justify-center gap-4 sm:flex-row">
            <a
              href={`${APP_URL}/sv/auth/signup`}
              className="inline-flex items-center justify-center rounded-full bg-white px-8 py-3.5 text-body font-semibold text-ink transition-colors hover:bg-paper-shade"
            >
              {t("cta")}
            </a>
            <BookDemoButton
              label={t("ctaSecondary")}
              className="inline-flex items-center justify-center rounded-full px-6 py-3 text-body font-semibold text-white/90 transition-colors hover:text-white"
            />
          </div>
        </Container>
      </section>
    </>
  );
}
