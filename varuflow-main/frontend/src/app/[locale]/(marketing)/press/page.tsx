import type { Metadata } from "next";
import JsonLd, { organizationSchema } from "@/components/marketing/JsonLd";

const BASE = process.env.NEXT_PUBLIC_SITE_URL ?? "https://varuflow.vercel.app";

export const metadata: Metadata = {
  title: "Press & Media Kit — Varuflow",
  description: "Varuflow press resources: company boilerplate, brand assets, logo files, founder bios, and media contact.",
  openGraph: { title: "Varuflow Press & Media Kit", description: "Logos, boilerplate, and media contact for Varuflow.", type: "website", url: `${BASE}/en/press` },
  twitter: { card: "summary_large_image", title: "Varuflow Media Kit" },
  alternates: { canonical: `${BASE}/en/press`, languages: { en: `${BASE}/en/press`, "x-default": `${BASE}/en/press` } },
};

const FACTS = [
  { label: "Founded", value: "2024" },
  { label: "Headquarters", value: "Stockholm, Sweden" },
  { label: "Markets", value: "Sweden, Norway, Denmark, KSA, UAE" },
  { label: "Product", value: "Inventory & invoicing SaaS for Nordic wholesalers" },
  { label: "Pricing", value: "Starter 499 SEK/mo · Professional 1,490 SEK/mo · Enterprise custom" },
  { label: "Compliance", value: "Bokföringslagen, ZATCA, GDPR, Peppol" },
];

export default function PressPage() {
  return (
    <>
      <JsonLd data={organizationSchema()} />
      <div className="mx-auto max-w-4xl px-4 py-20">
        <h1 className="vf-text-1 mb-2 text-4xl font-extrabold tracking-tight">Press & Media Kit</h1>
        <p className="vf-text-2 text-lg">
          Resources for journalists, bloggers, and media covering Varuflow.
        </p>

        {/* Boilerplate */}
        <section className="mt-12">
          <h2 className="vf-text-1 mb-4 text-xl font-bold">Company boilerplate</h2>
          <div className="rounded-2xl border border-white/8 bg-white/4 p-6">
            <p className="vf-text-2 text-sm leading-relaxed">
              Varuflow is a cloud-based inventory and invoicing platform built for Nordic wholesalers. It combines real-time inventory management, automated invoicing, a B2B customer portal, and AI-powered demand forecasting in one product. Varuflow is compliant with Bokföringslagen (Sweden), ZATCA (Saudi Arabia), GDPR, and Peppol e-invoicing standards. The platform offers a Starter plan at 499 SEK/month, a Professional plan at 1,490 SEK/month, and an Enterprise plan with custom pricing. All plans include a 14-day free trial. Varuflow was founded in Stockholm in 2024.
            </p>
          </div>
        </section>

        {/* Quick facts */}
        <section className="mt-10">
          <h2 className="vf-text-1 mb-4 text-xl font-bold">Quick facts</h2>
          <dl className="grid gap-3 sm:grid-cols-2">
            {FACTS.map((f) => (
              <div key={f.label} className="rounded-xl border border-white/8 bg-white/4 px-5 py-3">
                <dt className="vf-text-m text-xs font-semibold uppercase tracking-wider">{f.label}</dt>
                <dd className="vf-text-1 mt-1 text-sm font-medium">{f.value}</dd>
              </div>
            ))}
          </dl>
        </section>

        {/* Brand assets */}
        <section className="mt-10">
          <h2 className="vf-text-1 mb-4 text-xl font-bold">Brand assets</h2>
          <p className="vf-text-2 mb-4 text-sm">
            Logo files in SVG, PNG (dark and light backgrounds), and brand colour hex codes.
          </p>
          <div className="grid gap-4 sm:grid-cols-3">
            {["Logo (SVG)", "Logo (PNG dark)", "Logo (PNG light)", "Brand guidelines", "Product screenshots", "Founder photos"].map((asset) => (
              <div key={asset} className="flex items-center justify-between rounded-xl border border-white/8 bg-white/4 px-4 py-3">
                <span className="vf-text-2 text-xs">{asset}</span>
                <span className="vf-text-m text-xs">Contact press</span>
              </div>
            ))}
          </div>
          <p className="vf-text-m mt-3 text-xs">
            Full media kit (ZIP) available on request. Email{" "}
            <a href="mailto:press@varuflow.se" className="text-indigo-400 hover:underline">press@varuflow.se</a>.
          </p>
        </section>

        {/* Contact */}
        <section className="mt-10">
          <h2 className="vf-text-1 mb-3 text-xl font-bold">Press contact</h2>
          <p className="vf-text-2 text-sm">
            For press enquiries, interview requests, and media partnerships:<br />
            <a href="mailto:press@varuflow.se" className="text-indigo-400 hover:underline">press@varuflow.se</a>
          </p>
        </section>
      </div>
    </>
  );
}
