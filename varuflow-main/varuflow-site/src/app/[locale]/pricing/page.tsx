import type { Metadata } from "next";
import { Check, Minus } from "lucide-react";
import { getTranslations, setRequestLocale } from "next-intl/server";
import { PricingTiers } from "@/components/site/PricingTiers";
import { Container } from "@/components/ui/Container";
import { Section } from "@/components/ui/Section";
import { MODULES } from "@/content/modules";
import { tierIncludesModule } from "@/lib/plan-modules";
import { TIERS, type Tier, type TierId } from "@/lib/pricing";
import { JsonLd } from "@/components/site/JsonLd";
import { pageMetadata, SITE_URL } from "@/lib/seo";

type AppLocale = "sv" | "en";

function fmtCount(n: number, loc: AppLocale): string {
  return new Intl.NumberFormat(loc === "sv" ? "sv-SE" : "en-IE").format(n);
}

export async function generateMetadata({
  params,
}: {
  params: Promise<{ locale: string }>;
}): Promise<Metadata> {
  const { locale } = await params;
  const t = await getTranslations({ locale, namespace: "pricingPage" });
  return pageMetadata({
    locale,
    path: "/pricing",
    title: t("title"),
    description: t("sub"),
  });
}

export default async function PricingPage({
  params,
}: {
  params: Promise<{ locale: string }>;
}) {
  const { locale } = await params;
  setRequestLocale(locale);
  const t = await getTranslations("pricingPage");
  const loc: AppLocale = locale === "en" ? "en" : "sv";

  // A limit cell: real number from lib/pricing.ts, or the "Unlimited" word —
  // never a bare checkmark for unlimited (per spec).
  const limitCell = (n: number | null) =>
    n == null ? t("table.unlimited") : fmtCount(n, loc);

  const included = (yes: boolean) =>
    yes ? (
      <Check aria-label={t("table.included")} className="mx-auto h-4 w-4 text-accent" strokeWidth={2.5} />
    ) : (
      <Minus aria-label={t("table.notIncluded")} className="mx-auto h-4 w-4 text-line" strokeWidth={2} />
    );

  const LIMIT_ROWS: { key: string; value: (tier: Tier) => string }[] = [
    { key: "products", value: (x) => limitCell(x.limits.maxProducts) },
    { key: "seats", value: (x) => limitCell(x.limits.maxSeats) },
    { key: "invoices", value: (x) => limitCell(x.limits.maxInvoicesPerMonth) },
    { key: "customers", value: (x) => limitCell(x.limits.maxCustomers) },
  ];

  const FLAG_ROWS = [
    "fortnoxIntegration",
    "mobileApp",
    "advancedAnalytics",
    "prioritySupport",
    "apiAccess",
    "customIntegrations",
  ] as const;

  const groupHeader = (label: string) => (
    <tr key={label} className="bg-paper-shade">
      <th
        colSpan={4}
        scope="colgroup"
        className="px-4 py-3 text-left text-small font-semibold uppercase tracking-wide text-ink"
      >
        {label}
      </th>
    </tr>
  );

  return (
    <>
      <JsonLd
        data={{
          "@context": "https://schema.org",
          "@type": "Product",
          name: "Varuflow",
          description: t("sub"),
          url: `${SITE_URL}/${locale}/pricing`,
          offers: TIERS.map((tier) => ({
            "@type": "Offer",
            name: tier.id.charAt(0).toUpperCase() + tier.id.slice(1),
            price: loc === "sv" ? tier.monthly.sek : tier.monthly.eur,
            priceCurrency: loc === "sv" ? "SEK" : "EUR",
            url: `${SITE_URL}/${locale}/pricing`,
          })),
        }}
      />
      <Section className="pt-16 sm:pt-20">
        <Container>
          <div className="mx-auto max-w-2xl text-center">
            <h1 className="font-display text-4xl font-bold tracking-tight text-ink sm:text-display">
              {t("title")}
            </h1>
            <p className="mt-4 text-body text-mist">{t("sub")}</p>
          </div>

          {/* Tier cards — client island with monthly/yearly toggle */}
          <div className="mt-14">
            <PricingTiers locale={loc} />
          </div>
          <p className="mt-4 text-center text-small text-mist">{t("trialNote")}</p>
        </Container>
      </Section>

      {/* Comparison table — every value derived from lib/pricing.ts,
          content/modules and lib/plan-modules at render time. */}
      <Section shaded>
        <Container>
          <p className="mb-8 max-w-2xl text-body text-mist">{t("allModulesNote")}</p>
          <div className="overflow-x-auto rounded-card border border-line bg-paper">
            <table className="w-full min-w-[640px] border-collapse text-small">
              <thead>
                <tr className="border-b border-line">
                  <th scope="col" className="px-4 py-4 text-left font-semibold text-mist">
                    {t("table.feature")}
                  </th>
                  {TIERS.map((tier) => (
                    <th
                      key={tier.id}
                      scope="col"
                      className={`px-4 py-4 text-center font-semibold ${
                        tier.id === "professional" ? "text-brand" : "text-ink"
                      }`}
                    >
                      {tier.id.charAt(0).toUpperCase() + tier.id.slice(1)}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {groupHeader(t("table.usage"))}
                {LIMIT_ROWS.map(({ key, value }) => (
                  <tr key={key} className="border-b border-line last:border-0">
                    <th scope="row" className="px-4 py-3 text-left font-normal text-ink-soft">
                      {t(`table.${key}`)}
                    </th>
                    {TIERS.map((tier) => (
                      <td key={tier.id} className="px-4 py-3 text-center text-ink">
                        {value(tier)}
                      </td>
                    ))}
                  </tr>
                ))}

                {groupHeader(t("table.modules"))}
                {MODULES.map((m) => (
                  <tr key={m.slug} className="border-b border-line">
                    <th scope="row" className="px-4 py-3 text-left font-normal text-ink-soft">
                      {m.name[loc]}
                    </th>
                    {TIERS.map((tier) => (
                      <td key={tier.id} className="px-4 py-3 text-center">
                        {included(tierIncludesModule(tier.id as TierId, m.gate))}
                      </td>
                    ))}
                  </tr>
                ))}

                {groupHeader(t("table.platform"))}
                {FLAG_ROWS.map((flag) => (
                  <tr key={flag} className="border-b border-line last:border-0">
                    <th scope="row" className="px-4 py-3 text-left font-normal text-ink-soft">
                      {t(`table.${flag}`)}
                    </th>
                    {TIERS.map((tier) => (
                      <td key={tier.id} className="px-4 py-3 text-center">
                        {included(tier.flags[flag])}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Container>
      </Section>

      {/* FAQ — five items, native <details>, no JS needed */}
      <Section>
        <Container>
          <h2 className="font-display text-headline font-bold text-ink">{t("faq.title")}</h2>
          <div className="mt-8 max-w-3xl divide-y divide-line border-y border-line">
            {([1, 2, 3, 4, 5] as const).map((i) => (
              <details key={i} className="group py-5">
                <summary className="flex cursor-pointer list-none items-center justify-between text-body font-semibold text-ink [&::-webkit-details-marker]:hidden">
                  {t(`faq.q${i}`)}
                  <span aria-hidden className="ml-4 text-mist transition-transform group-open:rotate-45">
                    +
                  </span>
                </summary>
                <p className="mt-3 max-w-2xl text-body text-mist">{t(`faq.a${i}`)}</p>
              </details>
            ))}
          </div>
        </Container>
      </Section>
    </>
  );
}
