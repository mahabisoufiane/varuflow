import type { Metadata } from "next";
import CTABanner from "@/components/marketing/CTABanner";
import JsonLd, { organizationSchema } from "@/components/marketing/JsonLd";

const BASE = process.env.NEXT_PUBLIC_SITE_URL ?? "https://varuflow.vercel.app";

export const metadata: Metadata = {
  title: "About Varuflow — Our Story",
  description: "Varuflow was built by operators who were frustrated by legacy wholesale software. We're building the operating system for Nordic commerce.",
  openGraph: { title: "About Varuflow", description: "Built by operators, for operators.", type: "website", url: `${BASE}/en/about` },
  twitter: { card: "summary_large_image", title: "About Varuflow" },
  alternates: { canonical: `${BASE}/en/about`, languages: { en: `${BASE}/en/about`, sv: `${BASE}/sv/about`, "x-default": `${BASE}/en/about` } },
};

const VALUES = [
  { title: "Operators first", description: "We build for the person using the software every day — not for the IT team buying it once. Every feature has to earn its place." },
  { title: "Compliance by default", description: "Nordic businesses work in highly regulated markets. Compliance isn't a premium feature — it's table stakes." },
  { title: "Boring is good", description: "Business software should be reliable and predictable. We'd rather be boring and trusted than flashy and brittle." },
  { title: "Transparent pricing", description: "No per-user charges. No hidden fees. No sales calls required to get a price. Just a plan that grows with your business." },
];

export default function AboutPage() {
  return (
    <>
      <JsonLd data={organizationSchema()} />
      <div className="mx-auto max-w-3xl px-4 py-20">
        <h1 className="vf-text-1 text-4xl font-extrabold tracking-tight">Our story</h1>

        <div className="vf-text-2 mt-8 space-y-5 text-base leading-relaxed">
          <p>
            Varuflow started with a frustration. We were running a small wholesale operation and using three different tools for inventory, invoicing, and customer management — none of which talked to each other properly. The software was either too simple (Excel, Bokio) or too heavy to implement (Odoo, SAP Business One).
          </p>
          <p>
            We built Varuflow to bridge that gap: a product modern enough that a one-person business can be live in an afternoon, but capable enough that a 50-person operation still finds it useful on day 1, 000.
          </p>
          <p>
            We started with the Swedish market because we know it deeply: Bokföringslagen, Peppol, BankID, Kivra, and the specific VAT rules that trip up every imported product. We&apos;ve since expanded to MENA (ZATCA for Saudi Arabia, FTA for UAE) and are building for the full Nordic region.
          </p>
          <p>
            Stockholm, 2024.
          </p>
        </div>

        <div className="mt-16">
          <h2 className="vf-text-1 mb-8 text-2xl font-bold">What we believe</h2>
          <div className="grid gap-6 sm:grid-cols-2">
            {VALUES.map((v) => (
              <div key={v.title} className="rounded-2xl border border-white/8 bg-white/4 p-6">
                <h3 className="vf-text-1 mb-2 text-base font-semibold">{v.title}</h3>
                <p className="vf-text-2 text-sm leading-relaxed">{v.description}</p>
              </div>
            ))}
          </div>
        </div>
      </div>

      <CTABanner
        headline="Sound like something you need?"
        subheadline="Start with the free plan — no strings attached."
        ctaPrimary={{ href: "/trial", label: "Start free trial" }}
        ctaSecondary={{ href: "/demo", label: "Talk to the team" }}
      />
    </>
  );
}
