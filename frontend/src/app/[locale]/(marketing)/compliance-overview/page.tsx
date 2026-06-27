import type { Metadata } from "next";
import { ShieldCheck, FileCheck, Globe, Lock } from "lucide-react";
import CTABanner from "@/components/marketing/CTABanner";
import JsonLd, { organizationSchema } from "@/components/marketing/JsonLd";

const BASE = process.env.NEXT_PUBLIC_SITE_URL ?? "https://varuflow.vercel.app";

export const metadata: Metadata = {
  title: "Compliance — Bokföringslagen, ZATCA, GDPR, Peppol | Varuflow",
  description:
    "Varuflow is compliant with Bokföringslagen (Sweden), ZATCA (Saudi Arabia), GDPR, and Peppol. Built for regulated markets from day one.",
  openGraph: {
    title: "Varuflow Compliance — Bokföringslagen, ZATCA, GDPR, Peppol",
    description: "Regulatory compliance built into the core — not bolted on.",
    type: "website",
    url: `${BASE}/en/compliance`,
  },
  twitter: { card: "summary_large_image", title: "Varuflow Compliance" },
  alternates: {
    canonical: `${BASE}/en/compliance`,
    languages: {
      en: `${BASE}/en/compliance`,
      sv: `${BASE}/sv/compliance`,
      ar: `${BASE}/ar/compliance`,
      "x-default": `${BASE}/en/compliance`,
    },
  },
};

const SECTIONS = [
  {
    id: "bokforingslagen",
    icon: <FileCheck className="h-6 w-6" />,
    badge: "Sweden",
    title: "Bokföringslagen (SBL)",
    subtitle: "Swedish Bookkeeping Act compliance",
    points: [
      "SIE-file export (SIE4T format) for direct import into certified accounting systems (Fortnox, Visma, etc.)",
      "Immutable, cryptographically chained audit log for every transaction",
      "7-year record retention policy — data cannot be deleted within the statutory period",
      "Sequential invoice numbering — no gaps allowed, immutable once issued",
      "PDF/A invoice archival with digital signature",
      "All monetary calculations in SEK with full precision (no rounding errors in VAT)",
    ],
  },
  {
    id: "zatca",
    icon: <Globe className="h-6 w-6" />,
    badge: "Saudi Arabia",
    title: "ZATCA E-Invoicing",
    subtitle: "Fatoorah Phase 1 & Phase 2",
    points: [
      "Phase 1 (December 2021): all invoices generated as structured XML with mandatory fields",
      "Phase 2 (Integration): invoices submitted to Fatoorah platform in real time via API",
      "QR code on every B2C invoice — TLV-encoded with seller name, VAT number, date, total, and VAT amount",
      "Credit and debit notes linked to the original invoice reference",
      "Clearance for B2B invoices with Fatoorah before delivery to buyer",
      "VAT at 15% — automatic on every line item with correct treatment for exempt categories",
    ],
  },
  {
    id: "gdpr",
    icon: <Lock className="h-6 w-6" />,
    badge: "EU",
    title: "GDPR & Data Privacy",
    subtitle: "EU General Data Protection Regulation",
    points: [
      "All data stored in EU (Frankfurt, AWS eu-central-1) — never leaves the EU by default",
      "Customer data export: full JSON/CSV download on request, fulfilled in < 72 hours",
      "Right to erasure: personal data anonymised on deletion whilst preserving accounting records",
      "Consent log: timestamped record of when each customer accepted your terms",
      "Data processing agreement (DPA) available for all paid plans",
      "Annual penetration testing; results available under NDA for Enterprise customers",
    ],
  },
  {
    id: "peppol",
    icon: <Globe className="h-6 w-6" />,
    badge: "EU / Nordic",
    title: "Peppol & PINT",
    subtitle: "Pan-European Public Procurement Online",
    points: [
      "Peppol BIS Billing 3.0 (UBL 2.1) for invoices, credit notes, and reminders",
      "Norwegian EHF (Elektronisk Handelsformat) support for NO market",
      "Denmark OIOUBL and Finnish Finvoice via Peppol gateway",
      "PINT (Peppol International) for cross-border invoicing outside the EU",
      "Automatic SMP lookup — find any buyer's Peppol endpoint from their organisation number",
      "Delivery confirmation receipts with PEPPOL MDN acknowledgement",
    ],
  },
];

export default function CompliancePage() {
  return (
    <>
      <JsonLd data={organizationSchema()} />

      {/* Hero */}
      <section className="px-4 pb-8 pt-20 text-center">
        <p className="mb-4 inline-block rounded-full border border-green-500/30 bg-green-500/10 px-4 py-1 text-xs font-semibold uppercase tracking-widest text-green-400">
          Regulatory compliance
        </p>
        <h1 className="vf-text-1 text-4xl font-extrabold tracking-tight sm:text-5xl">
          Compliance built in, not bolted on
        </h1>
        <p className="vf-text-2 mx-auto mt-4 max-w-xl text-lg">
          Varuflow was designed for regulated markets. Bokföringslagen, ZATCA, GDPR, and Peppol are core features — not paid add-ons.
        </p>
        <div className="mt-6 flex flex-wrap justify-center gap-2">
          {["Bokföringslagen", "ZATCA", "GDPR", "Peppol", "EU data residency"].map((badge) => (
            <span key={badge} className="rounded-full border border-white/15 px-3 py-1 text-xs font-medium text-slate-400">
              {badge}
            </span>
          ))}
        </div>
      </section>

      {/* Compliance sections */}
      <div className="mx-auto max-w-4xl px-4 py-8 space-y-16">
        {SECTIONS.map((sec) => (
          <section key={sec.id} id={sec.id} className="scroll-mt-20">
            <div className="mb-6 flex items-start gap-4">
              <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-xl bg-indigo-500/15 text-indigo-400">
                {sec.icon}
              </div>
              <div>
                <div className="flex items-center gap-2">
                  <h2 className="vf-text-1 text-xl font-bold">{sec.title}</h2>
                  <span className="rounded-full bg-indigo-500/15 px-2.5 py-0.5 text-xs font-semibold text-indigo-300">
                    {sec.badge}
                  </span>
                </div>
                <p className="vf-text-m text-sm">{sec.subtitle}</p>
              </div>
            </div>

            <ul className="space-y-3 border-l-2 border-indigo-500/20 pl-6">
              {sec.points.map((point, i) => (
                <li key={i} className="vf-text-2 text-sm leading-relaxed">
                  {point}
                </li>
              ))}
            </ul>
          </section>
        ))}
      </div>

      <CTABanner
        headline="Need compliance documentation?"
        subheadline="Enterprise customers receive a compliance pack: DPA, audit log export, and pen-test report on request."
        ctaPrimary={{ href: "/demo", label: "Talk to our team" }}
        ctaSecondary={{ href: "/trial", label: "Start free trial" }}
      />
    </>
  );
}
