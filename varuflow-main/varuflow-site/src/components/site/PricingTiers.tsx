"use client";

// The one interactive island on /pricing: monthly ⇄ yearly toggle.
// All figures come from lib/pricing.ts — this component only chooses
// which real number to display.
import { useState } from "react";
import { useTranslations } from "next-intl";
import { Card } from "@/components/ui/Card";
import { TIERS, type Tier } from "@/lib/pricing";

const APP_URL = process.env.NEXT_PUBLIC_APP_URL ?? "https://varuflow.vercel.app";

type AppLocale = "sv" | "en";
type Cycle = "monthly" | "yearly";

function fmtPrice(value: number, loc: AppLocale): string {
  return loc === "sv"
    ? new Intl.NumberFormat("sv-SE", { style: "currency", currency: "SEK", maximumFractionDigits: 0 }).format(value)
    : new Intl.NumberFormat("en-IE", { style: "currency", currency: "EUR", maximumFractionDigits: 0 }).format(value);
}

export function PricingTiers({ locale }: { locale: AppLocale }) {
  const t = useTranslations("pricingPage");
  const [cycle, setCycle] = useState<Cycle>("monthly");

  const shown = (tier: Tier) => {
    const p = cycle === "monthly" ? tier.monthly : tier.yearlyPerMonth;
    return locale === "sv" ? p.sek : p.eur;
  };
  const annualTotal = (tier: Tier) =>
    locale === "sv" ? tier.annual.sek : tier.annual.eur;

  return (
    <div>
      {/* Billing-cycle toggle */}
      <div className="flex justify-center">
        <div
          role="group"
          aria-label={`${t("billing.monthly")} / ${t("billing.yearly")}`}
          className="inline-flex rounded-full border border-line bg-paper p-1"
        >
          {(["monthly", "yearly"] as const).map((c) => (
            <button
              key={c}
              type="button"
              aria-pressed={cycle === c}
              onClick={() => setCycle(c)}
              className={`rounded-full px-5 py-2 text-small font-semibold transition-colors ${
                cycle === c ? "bg-ink text-white" : "text-mist hover:text-ink"
              }`}
            >
              {t(`billing.${c}`)}
            </button>
          ))}
        </div>
      </div>

      <div className="mx-auto mt-10 grid max-w-5xl gap-6 lg:grid-cols-3">
        {TIERS.map((tier) => (
          <Card key={tier.id} className={tier.id === "professional" ? "border-2 border-brand" : ""}>
            <h2 className="text-title font-semibold text-ink">
              {tier.id.charAt(0).toUpperCase() + tier.id.slice(1)}
            </h2>
            <p className="mt-3">
              <span className="font-display text-headline font-bold text-ink">
                {fmtPrice(shown(tier), locale)}
              </span>
              <span className="text-small text-mist"> {t("perMonth")}</span>
            </p>
            <p className="mt-1 min-h-10 text-small text-mist">
              {cycle === "monthly"
                ? t("billing.billedMonthly")
                : `${t("billing.billedYearly")} · ${t("billing.annualTotal", {
                    price: fmtPrice(annualTotal(tier), locale),
                  })}`}
            </p>
            <a
              href={`${APP_URL}/sv/auth/signup?plan=${tier.id}`}
              className="mt-6 inline-flex w-full items-center justify-center rounded-full bg-brand px-6 py-3 text-small font-semibold text-white transition-colors hover:bg-brand-strong"
            >
              {t("cta")}
            </a>
          </Card>
        ))}
      </div>
    </div>
  );
}
