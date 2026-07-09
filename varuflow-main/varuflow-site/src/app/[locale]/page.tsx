import {
  ArrowRight,
  BarChart3,
  Check,
  Database,
  FileText,
  Lock,
  Package,
  ScanLine,
  ShieldCheck,
  Sparkles,
  TrendingUp,
  type LucideIcon,
} from "lucide-react";
import { getTranslations, setRequestLocale } from "next-intl/server";
import { Link } from "@/i18n/navigation";
import { BookDemoButton } from "@/components/site/BookDemoButton";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { Container } from "@/components/ui/Container";
import { Section } from "@/components/ui/Section";
import { JsonLd } from "@/components/site/JsonLd";
import { MODULES } from "@/content/modules";
import { SOLUTIONS } from "@/content/solutions";
import { TIERS, type Tier } from "@/lib/pricing";
import { pageMetadata, SITE_URL } from "@/lib/seo";
import type { Metadata } from "next";

const APP_URL = process.env.NEXT_PUBLIC_APP_URL ?? "https://varuflow.vercel.app";

const MODULE_ICONS: Record<string, LucideIcon> = {
  inventory: Package,
  invoicing: FileText,
  finance: TrendingUp,
  pos: ScanLine,
  ai: Sparkles,
  analytics: BarChart3,
};

type AppLocale = "sv" | "en";

// SEK on /sv, EUR on /en — figures come straight from lib/pricing.ts.
function price(tier: Tier, locale: AppLocale): string {
  return locale === "sv"
    ? new Intl.NumberFormat("sv-SE", { style: "currency", currency: "SEK", maximumFractionDigits: 0 }).format(tier.monthly.sek)
    : new Intl.NumberFormat("en-IE", { style: "currency", currency: "EUR", maximumFractionDigits: 0 }).format(tier.monthly.eur);
}

export async function generateMetadata({
  params,
}: {
  params: Promise<{ locale: string }>;
}): Promise<Metadata> {
  const { locale } = await params;
  const t = await getTranslations({ locale, namespace: "home" });
  return pageMetadata({
    locale,
    path: "",
    title: t("meta.title"),
    description: t("meta.description"),
  });
}

export default async function HomePage({
  params,
}: {
  params: Promise<{ locale: string }>;
}) {
  const { locale } = await params;
  setRequestLocale(locale);
  const t = await getTranslations("home");
  const loc: AppLocale = locale === "en" ? "en" : "sv";

  // Top-4 feature lines per tier, derived from real limits/flags in
  // lib/pricing.ts — numbers are never hardcoded here (AGENTS.md rule).
  const tierFeatures = (tier: Tier): string[] => {
    const limit = (k: "products" | "seats" | "invoices", n: number | null) =>
      n == null
        ? t(`pricing.features.${k}Unlimited`)
        : t(`pricing.features.${k}`, { n });
    const highlight = tier.flags.apiAccess
      ? t("pricing.features.apiAccess")
      : tier.flags.mobileApp
        ? t("pricing.features.mobileApp")
        : t("pricing.features.fortnox");
    return [
      limit("products", tier.limits.maxProducts),
      limit("seats", tier.limits.maxSeats),
      limit("invoices", tier.limits.maxInvoicesPerMonth),
      highlight,
    ];
  };

  const trustItems = [
    { icon: ShieldCheck, title: t("trust.gdpr"), desc: t("trust.gdprDesc") },
    { icon: Database, title: t("trust.hosting"), desc: t("trust.hostingDesc") },
    { icon: Lock, title: t("trust.encryption"), desc: t("trust.encryptionDesc") },
    { icon: ArrowRight, title: t("trust.export"), desc: t("trust.exportDesc") },
  ] as const;

  const journey = ([1, 2, 3, 4] as const).map((i) => ({
    n: i,
    title: t(`journey.s${i}t`),
    desc: t(`journey.s${i}d`),
  }));

  const currency = loc === "sv" ? "SEK" : "EUR";
  const prices = TIERS.map((x) => (loc === "sv" ? x.monthly.sek : x.monthly.eur));

  return (
    <>
      <JsonLd
        data={{
          "@context": "https://schema.org",
          "@type": "Organization",
          name: "Varuflow",
          url: SITE_URL,
        }}
      />
      <JsonLd
        data={{
          "@context": "https://schema.org",
          "@type": "SoftwareApplication",
          name: "Varuflow",
          applicationCategory: "BusinessApplication",
          operatingSystem: "Web",
          offers: {
            "@type": "AggregateOffer",
            priceCurrency: currency,
            lowPrice: Math.min(...prices),
            highPrice: Math.max(...prices),
            offerCount: TIERS.length,
          },
        }}
      />
      {/* ── 1. Hero ─────────────────────────────────────────────────── */}
      <Section className="pt-16 sm:pt-24">
        <Container>
          <div className="mx-auto max-w-3xl text-center">
            <h1 className="font-display text-4xl font-bold tracking-tight text-ink sm:text-display">
              {t("hero.h1")}
            </h1>
            <p className="mx-auto mt-6 max-w-2xl text-body text-mist">{t("hero.sub")}</p>
            <div className="mt-10 flex flex-col items-center justify-center gap-4 sm:flex-row">
              <a
                href={`${APP_URL}/sv/auth/signup`}
                className="inline-flex w-full items-center justify-center rounded-full bg-brand px-8 py-3.5 text-body font-semibold text-white transition-colors hover:bg-brand-strong sm:w-auto"
              >
                {t("hero.ctaPrimary")}
              </a>
              <BookDemoButton
                label={t("hero.ctaSecondary")}
                className="inline-flex w-full items-center justify-center rounded-full border border-line bg-paper px-6 py-3 text-small font-semibold text-ink transition-colors hover:border-ink sm:w-auto"
              />
            </div>
            <p className="mt-4 text-small text-mist">{t("hero.trialNote")}</p>
          </div>

          {/* CSS-only product sketch — flat, tokenized, no images */}
          <div
            aria-hidden
            className="mx-auto mt-16 max-w-4xl rounded-card border border-line bg-paper-shade p-3 shadow-sm"
          >
            <div className="flex items-center gap-1.5 px-2 pb-3">
              <span className="h-2.5 w-2.5 rounded-full bg-line" />
              <span className="h-2.5 w-2.5 rounded-full bg-line" />
              <span className="h-2.5 w-2.5 rounded-full bg-line" />
            </div>
            <div className="grid gap-3 rounded-lg bg-paper p-4 sm:grid-cols-3">
              {[
                { label: t("mockup.revenue"), bar: "w-3/4" },
                { label: t("mockup.stock"), bar: "w-1/2" },
                { label: t("mockup.orders"), bar: "w-2/3" },
              ].map(({ label, bar }) => (
                <div key={label} className="rounded-lg border border-line p-4">
                  <p className="text-small text-mist">{label}</p>
                  <div className="mt-3 h-2 w-full rounded-full bg-paper-shade">
                    <div className={`h-2 rounded-full bg-brand ${bar}`} />
                  </div>
                  <div className="mt-2 h-2 w-1/3 rounded-full bg-paper-shade" />
                </div>
              ))}
            </div>
          </div>
        </Container>
      </Section>

      {/* ── 2. Modules grid ─────────────────────────────────────────── */}
      <Section shaded>
        <Container>
          <div className="max-w-2xl">
            <h2 className="font-display text-headline font-bold text-ink">{t("modules.title")}</h2>
            <p className="mt-3 text-body text-mist">{t("modules.sub")}</p>
          </div>
          <div className="mt-12 grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
            {MODULES.map((m) => {
              const Icon = MODULE_ICONS[m.slug] ?? Package;
              return (
                <Link key={m.slug} href={`/modules/${m.slug}`} className="group">
                  <Card className="h-full transition-colors group-hover:border-brand">
                    <Icon className="h-6 w-6 text-brand" strokeWidth={1.75} />
                    <h3 className="mt-4 text-title font-semibold text-ink">{m.name[loc]}</h3>
                    <p className="mt-2 line-clamp-2 text-small text-mist">{m.description[loc]}</p>
                  </Card>
                </Link>
              );
            })}
          </div>
        </Container>
      </Section>

      {/* ── 3. Trust band ───────────────────────────────────────────── */}
      <Section className="border-y border-line !py-14">
        <Container>
          <div className="grid gap-8 sm:grid-cols-2 lg:grid-cols-4">
            {trustItems.map(({ icon: Icon, title, desc }) => (
              <div key={title} className="flex gap-3">
                <Icon className="mt-0.5 h-5 w-5 shrink-0 text-accent" strokeWidth={2} />
                <div>
                  <p className="text-small font-semibold text-ink">{title}</p>
                  <p className="mt-1 text-small text-mist">{desc}</p>
                </div>
              </div>
            ))}
          </div>
        </Container>
      </Section>

      {/* ── 4. Verticals ────────────────────────────────────────────── */}
      <Section>
        <Container>
          <div className="max-w-2xl">
            <h2 className="font-display text-headline font-bold text-ink">{t("verticals.title")}</h2>
            <p className="mt-3 text-body text-mist">{t("verticals.sub")}</p>
          </div>
          <div className="mt-12 grid gap-6 lg:grid-cols-3">
            {SOLUTIONS.map((s) => (
              <Link key={s.slug} href={`/solutions/${s.slug}`} className="group">
                <Card className="h-full transition-colors group-hover:border-brand">
                  <p className="text-small font-semibold uppercase tracking-wide text-brand">
                    {s.eyebrow[loc]}
                  </p>
                  <h3 className="mt-3 text-title font-semibold text-ink">{s.headline[loc]}</h3>
                  <p className="mt-3 text-small text-mist">{s.subheadline[loc]}</p>
                  <span className="mt-5 inline-flex items-center gap-1 text-small font-semibold text-brand">
                    {t("verticals.cta")}
                    <ArrowRight className="h-4 w-4 transition-transform group-hover:translate-x-0.5" />
                  </span>
                </Card>
              </Link>
            ))}
          </div>
        </Container>
      </Section>

      {/* ── 5. Pricing preview ──────────────────────────────────────── */}
      <Section shaded>
        <Container>
          <div className="mx-auto max-w-2xl text-center">
            <h2 className="font-display text-headline font-bold text-ink">{t("pricing.title")}</h2>
            <p className="mt-3 text-body text-mist">{t("pricing.sub")}</p>
          </div>
          <div className="mx-auto mt-12 grid max-w-5xl gap-6 lg:grid-cols-3">
            {TIERS.map((tier) => {
              const featured = tier.id === "professional";
              return (
                <Card
                  key={tier.id}
                  className={featured ? "relative border-2 border-brand" : ""}
                >
                  {featured && (
                    <span className="absolute -top-3 left-1/2 -translate-x-1/2 rounded-full bg-brand px-3 py-1 text-xs font-semibold text-white">
                      {t("pricing.highlight")}
                    </span>
                  )}
                  <h3 className="text-title font-semibold text-ink">
                    {t(`pricing.tierNames.${tier.id}`)}
                  </h3>
                  <p className="mt-4">
                    <span className="font-display text-headline font-bold text-ink">
                      {price(tier, loc)}
                    </span>
                    <span className="text-small text-mist"> {t("pricing.perMonth")}</span>
                  </p>
                  <p className="text-small text-mist">{t("pricing.billedMonthly")}</p>
                  <ul className="mt-6 space-y-2.5">
                    {tierFeatures(tier).map((line) => (
                      <li key={line} className="flex items-start gap-2 text-small text-ink-soft">
                        <Check className="mt-0.5 h-4 w-4 shrink-0 text-accent" strokeWidth={2.5} />
                        {line}
                      </li>
                    ))}
                  </ul>
                </Card>
              );
            })}
          </div>
          <div className="mt-10 text-center">
            <Button href="/pricing" variant="ghost">
              {t("pricing.cta")} <ArrowRight className="h-4 w-4" />
            </Button>
          </div>
        </Container>
      </Section>

      {/* ── 6. Onboarding journey ───────────────────────────────────── */}
      <Section>
        <Container>
          <h2 className="font-display text-headline font-bold text-ink">{t("journey.title")}</h2>
          <ol className="mt-12 flex flex-col gap-10 md:flex-row md:gap-6">
            {journey.map((step, i) => (
              <li key={step.n} className="relative flex flex-1 gap-4 md:flex-col">
                {/* connector: vertical on mobile, horizontal on desktop */}
                {i < journey.length - 1 && (
                  <span
                    aria-hidden
                    className="absolute left-4 top-10 h-[calc(100%+1rem)] w-px bg-line md:left-10 md:top-4 md:h-px md:w-[calc(100%-2rem)]"
                  />
                )}
                <span className="relative z-10 flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-brand text-small font-bold text-white">
                  {step.n}
                </span>
                <div>
                  <h3 className="text-body font-semibold text-ink md:mt-4">{step.title}</h3>
                  <p className="mt-1 text-small text-mist">{step.desc}</p>
                </div>
              </li>
            ))}
          </ol>
        </Container>
      </Section>

      {/* ── 7. Final CTA band ───────────────────────────────────────── */}
      <section className="bg-ink py-20 text-center sm:py-24">
        <Container>
          <h2 className="hyphens-auto break-words font-display text-title font-bold text-white sm:text-headline">{t("finalCta.h")}</h2>
          <p className="mx-auto mt-4 max-w-xl text-body text-white/70">{t("finalCta.sub")}</p>
          <a
            href={`${APP_URL}/sv/auth/signup`}
            className="mt-8 inline-flex items-center justify-center rounded-full bg-white px-8 py-3.5 text-body font-semibold text-ink transition-colors hover:bg-paper-shade"
          >
            {t("finalCta.cta")}
          </a>
        </Container>
      </section>
    </>
  );
}
