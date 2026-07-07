import type { Metadata } from "next";
import { ShieldCheck, Lock, Eye, Key, Network } from "lucide-react";
import CTABanner from "@/components/marketing/CTABanner";
import JsonLd, { organizationSchema } from "@/components/marketing/JsonLd";

const BASE = process.env.NEXT_PUBLIC_SITE_URL ?? "https://varuflow.vercel.app";

export const metadata: Metadata = {
  title: "Security — Varuflow",
  description:
    "Varuflow security overview: SOC 2 Type II (in progress), AES-256 encryption, MFA, IP allowlist, EU data residency, and annual pen testing.",
  openGraph: {
    title: "Varuflow Security — SOC 2, MFA, Encryption, EU Residency",
    description: "Enterprise-grade security for every plan. Your data never leaves the EU.",
    type: "website",
    url: `${BASE}/en/security`,
  },
  twitter: { card: "summary_large_image", title: "Varuflow Security" },
  alternates: {
    canonical: `${BASE}/en/security`,
    languages: {
      en: `${BASE}/en/security`,
      sv: `${BASE}/sv/security`,
      "x-default": `${BASE}/en/security`,
    },
  },
};

const PILLARS = [
  {
    icon: <ShieldCheck className="h-6 w-6" />,
    title: "SOC 2 Type II",
    status: "In progress",
    statusColor: "text-yellow-400 bg-yellow-400/10 border-yellow-400/30",
    description:
      "We are currently completing our SOC 2 Type II audit (security and availability trust service criteria). Expected certification: Q3 2026. Interim: penetration test report available to Enterprise customers under NDA.",
  },
  {
    icon: <Lock className="h-6 w-6" />,
    title: "Encryption at rest & in transit",
    status: "Live",
    statusColor: "text-green-400 bg-green-400/10 border-green-400/30",
    description:
      "All data encrypted at rest with AES-256. All data in transit protected with TLS 1.3 minimum. Encryption keys managed via AWS KMS with automatic rotation every 90 days.",
  },
  {
    icon: <Key className="h-6 w-6" />,
    title: "Multi-factor authentication (MFA)",
    status: "Live",
    statusColor: "text-green-400 bg-green-400/10 border-green-400/30",
    description:
      "TOTP MFA available for all users. Enterprise can enforce MFA organisation-wide. Supabase Auth with JWT RS256 signing — tokens expire in 1 hour with silent refresh.",
  },
  {
    icon: <Network className="h-6 w-6" />,
    title: "IP allowlist",
    status: "Enterprise",
    statusColor: "text-[var(--vf-brand-primary-light)] bg-[var(--vf-brand-primary-light)]/10 border-[var(--vf-brand-primary-light)]/30",
    description:
      "Enterprise organisations can restrict API and portal access to a list of approved IP ranges. Useful for office-only access policies. Configurable per organisation.",
  },
  {
    icon: <Eye className="h-6 w-6" />,
    title: "Audit log",
    status: "Live",
    statusColor: "text-green-400 bg-green-400/10 border-green-400/30",
    description:
      "Every create, update, and delete action is logged with timestamp, user ID, org ID, IP address, and before/after state. Logs are immutable — not editable by anyone, including admins. Exportable for compliance.",
  },
  {
    icon: <ShieldCheck className="h-6 w-6" />,
    title: "Annual pen testing",
    status: "Live",
    statusColor: "text-green-400 bg-green-400/10 border-green-400/30",
    description:
      "Annual black-box and grey-box penetration test by an independent certified tester. Results shared with Enterprise customers under NDA. Last test: March 2026.",
  },
];

export default function SecurityPage() {
  return (
    <>
      <JsonLd data={organizationSchema()} />

      {/* Hero */}
      <section className="px-4 pb-8 pt-20 text-center">
        <p className="mb-4 inline-block rounded-full border border-green-500/30 bg-green-500/10 px-4 py-1 text-xs font-semibold uppercase tracking-widest text-green-400">
          Security
        </p>
        <h1 className="vf-text-1 text-4xl font-extrabold tracking-tight sm:text-5xl">
          Enterprise security for every plan
        </h1>
        <p className="vf-text-2 mx-auto mt-4 max-w-xl text-lg">
          Your data stays in the EU. We encrypt everything, log every action, and test our security every year.
        </p>
      </section>

      {/* Security pillars */}
      <div className="mx-auto max-w-4xl px-4 py-12 space-y-6">
        {PILLARS.map((pillar) => (
          <div
            key={pillar.title}
            className="flex flex-col gap-4 rounded-2xl border border-white/8 bg-white/4 p-6 sm:flex-row sm:items-start"
          >
            <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-xl bg-[var(--vf-brand-primary-soft)] text-[var(--vf-brand-primary-light)]">
              {pillar.icon}
            </div>
            <div className="flex-1">
              <div className="mb-1 flex flex-wrap items-center gap-2">
                <h2 className="vf-text-1 text-base font-semibold">{pillar.title}</h2>
                <span className={`rounded-full border px-2.5 py-0.5 text-xs font-semibold ${pillar.statusColor}`}>
                  {pillar.status}
                </span>
              </div>
              <p className="vf-text-2 text-sm leading-relaxed">{pillar.description}</p>
            </div>
          </div>
        ))}
      </div>

      {/* Responsible disclosure */}
      <div className="mx-auto max-w-4xl px-4 pb-12">
        <div className="rounded-2xl border border-white/8 bg-white/4 p-6">
          <h2 className="vf-text-1 mb-2 text-base font-semibold">Responsible disclosure</h2>
          <p className="vf-text-2 text-sm leading-relaxed">
            Found a vulnerability? Please email{" "}
            <a href="mailto:security@varuflow.se" className="text-[var(--vf-brand-primary-light)] hover:underline">
              security@varuflow.se
            </a>{" "}
            with a description and proof-of-concept. We aim to respond within 48 hours and patch critical issues within 7 days. We do not take legal action against researchers who follow responsible disclosure.
          </p>
        </div>
      </div>

      <CTABanner
        headline="Security documentation for your procurement team?"
        subheadline="Enterprise plans include the full security pack: pen test report, DPA, data flow diagram, and SOC 2 roadmap."
        ctaPrimary={{ href: "/demo", label: "Talk to our team" }}
        ctaSecondary={{ href: "/compliance-overview", label: "See compliance details" }}
      />
    </>
  );
}
