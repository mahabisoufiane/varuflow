import type { Metadata } from "next";
import { CheckCircle2, ArrowRight } from "lucide-react";
import TrialSignupForm from "@/components/marketing/TrialSignupForm";
import FAQ from "@/components/marketing/FAQ";
import Link from "next/link";

function buildFAQSchema(items: { question: string; answer: string }[]) {
  return {
    "@context": "https://schema.org",
    "@type": "FAQPage",
    mainEntity: items.map((item) => ({
      "@type": "Question",
      name: item.question,
      acceptedAnswer: { "@type": "Answer", text: item.answer },
    })),
  };
}
import JsonLd, { softwareApplicationSchema } from "@/components/marketing/JsonLd";

const BASE = process.env.NEXT_PUBLIC_SITE_URL ?? "https://varuflow.vercel.app";

export const metadata: Metadata = {
  title: "Try Varuflow Free for 14 Days | Varuflow",
  description:
    "Start your 14-day free trial of Varuflow. No credit card required. Full access to all Starter features. Upgrade to Professional when you're ready.",
  openGraph: {
    title: "14-Day Free Trial — Varuflow",
    description: "Full Starter access for 14 days. No credit card required.",
    type: "website",
    url: `${BASE}/en/trial`,
  },
  twitter: { card: "summary_large_image", title: "Try Varuflow Free for 14 Days" },
  alternates: {
    canonical: `${BASE}/en/trial`,
    languages: {
      en: `${BASE}/en/trial`,
      sv: `${BASE}/sv/trial`,
      ar: `${BASE}/ar/trial`,
      "x-default": `${BASE}/en/trial`,
    },
  },
};

const TRIAL_INCLUDES = [
  "Up to 500 products",
  "Up to 150 customers",
  "Up to 200 invoices/month",
  "5 team members",
  "Inventory & stock management",
  "PDF & email invoicing",
  "Fortnox integration",
  "Bulk import",
  "Email support"
];

const PRO_FEATURES = [
  "Up to 10,000 products",
  "Unlimited customers & invoices",
  "20 team members",
  "Mobile app (Android & iOS)",
  "Advanced analytics & forecasting",
  "Automated dunning & reminders",
  "B2B customer portal",
  "Priority support (4h response)",
  "Low stock alerts & reorder rules",
];

const FAQS = [
  {
    question: "Do I need a credit card to start?",
    answer:
      "No. Your 14-day trial starts immediately with no credit card required. You only add payment details when you choose to upgrade.",
  },
  {
    question: "What happens when my trial ends?",
    answer:
      "Your account stays active — you keep all your data. You can continue on the Starter plan (499 kr/month) or upgrade to Professional for more capacity.",
  },
  {
    question: "How much does Professional cost?",
    answer:
      "Professional is 1,490 kr/month (billed monthly) or 1,190 kr/month (billed annually). Starter is 499 kr/month. See the pricing page for full details.",
  },
  {
    question: "Can I upgrade or downgrade anytime?",
    answer:
      "Yes. Upgrade instantly and changes apply immediately. Downgrades apply at the next billing cycle. Cancel anytime from your billing settings.",
  },
  {
    question: "Is my data secure?",
    answer:
      "All data is encrypted and stored on EU servers. We are fully GDPR compliant and follow Bokföringslagen requirements for Swedish businesses.",
  },
];

export default function TrialPage() {
  return (
    <>
      <JsonLd id="jsonld-software" data={softwareApplicationSchema()} />
      <JsonLd id="jsonld-faq" data={buildFAQSchema(FAQS)} />

      <div className="mx-auto max-w-5xl px-4 py-20">
        <div className="grid gap-16 lg:grid-cols-2 lg:items-start">
          {/* Left: form */}
          <div>
            <p className="mb-4 inline-block rounded-full border border-indigo-500/30 bg-indigo-500/10 px-4 py-1 text-xs font-semibold uppercase tracking-widest text-indigo-400">
              14-day trial — no credit card required
            </p>
            <h1 className="vf-text-1 text-3xl font-extrabold tracking-tight sm:text-4xl">
              Try Varuflow free<br />for 14 days.
            </h1>
            <p className="vf-text-2 mt-4 text-base leading-relaxed">
              Full Starter access from day one. Set up in under 5 minutes. Upgrade to Professional when you need more power.
            </p>

            <div className="mt-8">
              <TrialSignupForm />
            </div>

            <p className="mt-4 text-center text-xs vf-text-m">
              Already know you need Pro?{" "}
              <Link href="/pricing" className="text-indigo-400 underline underline-offset-2 hover:text-indigo-300">
                See Pro pricing →
              </Link>
            </p>
          </div>

          {/* Right: what's free vs locked */}
          <div className="space-y-6">
            {/* Starter trial */}
            <div className="rounded-xl border vf-border vf-bg-card p-5">
              <h2 className="vf-text-1 mb-4 text-sm font-bold uppercase tracking-widest text-green-500">
                ✓ Starter — included in your trial
              </h2>
              <ul className="space-y-2">
                {TRIAL_INCLUDES.map((item) => (
                  <li key={item} className="flex items-start gap-2.5">
                    <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-green-500" />
                    <span className="vf-text-2 text-sm">{item}</span>
                  </li>
                ))}
              </ul>
            </div>

            {/* Professional upgrade */}
            <div className="rounded-xl border border-dashed vf-border vf-bg-card p-5">
              <div className="mb-4 flex items-center justify-between">
                <h2 className="text-sm font-bold uppercase tracking-widest text-indigo-400">
                  ⚡ Professional — 1,490 kr/mo
                </h2>
                <Link
                  href="/pricing"
                  className="flex items-center gap-1 rounded-full bg-indigo-600 px-3 py-1 text-xs font-semibold text-white hover:bg-indigo-500 transition-colors"
                >
                  See plans <ArrowRight className="h-3 w-3" />
                </Link>
              </div>
              <ul className="space-y-2">
                {PRO_FEATURES.map((item) => (
                  <li key={item} className="flex items-start gap-2.5">
                    <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-indigo-400" />
                    <span className="vf-text-2 text-sm">{item}</span>
                  </li>
                ))}
              </ul>
            </div>
          </div>
        </div>

        {/* FAQ */}
        <div className="mt-20">
          <h2 className="vf-text-1 mb-8 text-center text-xl font-bold">Frequently asked questions</h2>
          <FAQ items={FAQS} />
        </div>
      </div>
    </>
  );
}

