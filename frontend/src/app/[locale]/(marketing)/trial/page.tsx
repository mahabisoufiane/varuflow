import type { Metadata } from "next";
import { CheckCircle2, Lock, ArrowRight } from "lucide-react";
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
  title: "Start Free — Try Varuflow | Varuflow",
  description:
    "Try Varuflow free. Add up to 25 products and send 10 invoices. Upgrade anytime to unlock unlimited access, AI features, and full Pro tools.",
  openGraph: {
    title: "Try Varuflow Free — Upgrade When Ready",
    description: "Start free. Upgrade when you need more.",
    type: "website",
    url: `${BASE}/en/trial`,
  },
  twitter: { card: "summary_large_image", title: "Try Varuflow Free" },
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

const FREE_INCLUDES = [
  "Up to 25 products",
  "Up to 10 invoices per month",
  "Up to 3 customers",
  "1 team member (owner only)",
  "Basic inventory overview",
  "Manual stock updates",
  "PDF invoice download",
  "Email support (48h response)",
];

const PRO_LOCKED = [
  "Unlimited products, customers & invoices",
  "B2B customer portal",
  "AI demand forecast & action cards",
  "POS terminal (mobile & tablet)",
  "Peppol e-invoicing & automated dunning",
  "ZATCA, GDPR & Bokföringslagen compliance",
  "Up to 20 team members",
  "Fortnox & Stripe integration",
  "Priority support (2h response)",
  "Data export & API access",
];

const FAQS = [
  {
    question: "Is the free plan really free forever?",
    answer:
      "Yes. The free plan is free forever with the limits shown. No credit card required to sign up. You only pay when you upgrade to Pro.",
  },
  {
    question: "What happens when I hit a limit?",
    answer:
      "You'll see a clear prompt to upgrade. Your existing data is never deleted — you just can't add more until you upgrade or remove old records.",
  },
  {
    question: "How much does Pro cost?",
    answer:
      "Pro starts at 599 SEK/month (billed monthly) or 499 SEK/month (billed annually). See the pricing page for full details.",
  },
  {
    question: "Can I try Pro features before paying?",
    answer:
      "Yes — you get a 14-day Pro trial when you first sign up. After 14 days your account moves to the free plan unless you add a payment method.",
  },
  {
    question: "Can I cancel anytime?",
    answer:
      "Yes. Cancel from your billing settings at any time. You keep Pro access until the end of the billing period, then revert to the free plan.",
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
              Free forever — no card required
            </p>
            <h1 className="vf-text-1 text-3xl font-extrabold tracking-tight sm:text-4xl">
              Start free.<br />Upgrade when you grow.
            </h1>
            <p className="vf-text-2 mt-4 text-base leading-relaxed">
              Get started in under 2 minutes. Free plan is limited — upgrade to Pro to unlock everything.
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
            {/* Free plan */}
            <div className="rounded-xl border vf-border vf-bg-card p-5">
              <h2 className="vf-text-1 mb-4 text-sm font-bold uppercase tracking-widest text-green-500">
                ✓ Free plan includes
              </h2>
              <ul className="space-y-2">
                {FREE_INCLUDES.map((item) => (
                  <li key={item} className="flex items-start gap-2.5">
                    <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-green-500" />
                    <span className="vf-text-2 text-sm">{item}</span>
                  </li>
                ))}
              </ul>
            </div>

            {/* Pro locked */}
            <div className="rounded-xl border border-dashed vf-border vf-bg-card p-5 opacity-80">
              <div className="mb-4 flex items-center justify-between">
                <h2 className="text-sm font-bold uppercase tracking-widest text-indigo-400">
                  🔒 Unlocked with Pro
                </h2>
                <Link
                  href="/pricing"
                  className="flex items-center gap-1 rounded-full bg-indigo-600 px-3 py-1 text-xs font-semibold text-white hover:bg-indigo-500 transition-colors"
                >
                  Upgrade <ArrowRight className="h-3 w-3" />
                </Link>
              </div>
              <ul className="space-y-2">
                {PRO_LOCKED.map((item) => (
                  <li key={item} className="flex items-start gap-2.5">
                    <Lock className="mt-0.5 h-4 w-4 shrink-0 text-indigo-400/60" />
                    <span className="vf-text-m text-sm line-through decoration-indigo-400/40">{item}</span>
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

