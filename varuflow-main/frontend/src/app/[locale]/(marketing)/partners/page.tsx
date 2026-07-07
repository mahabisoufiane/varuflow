import type { Metadata } from "next";
import { Link } from "@/i18n/navigation";
import JsonLd, { organizationSchema } from "@/components/marketing/JsonLd";
import CTABanner from "@/components/marketing/CTABanner";
import PartnerApplicationForm from "@/components/marketing/PartnerApplicationForm";
import {
  CheckCircle2,
  TrendingUp,
  Users,
  BarChart3,
  HeadphonesIcon,
  BookOpen,
  BadgeCheck,
} from "lucide-react";

const BASE = process.env.NEXT_PUBLIC_SITE_URL ?? "https://varuflow.vercel.app";

export const metadata: Metadata = {
  title: "Accounting Partner Program — Varuflow",
  description:
    "Earn 25% recurring commission for 12 months on every client you refer to Varuflow. Join 60+ accounting firms already earning with us.",
  openGraph: {
    title: "Partner with Varuflow — 25% recurring commission",
    description:
      "Refer your clients to Varuflow and earn 25% of their monthly subscription for 12 months. Apply in 2 minutes.",
    type: "website",
  },
  alternates: { canonical: `${BASE}/en/partners` },
};

const BENEFITS = [
  {
    icon: TrendingUp,
    title: "25% recurring commission",
    description:
      "Earn 25% of the subscription fee for every client you refer — each month, for 12 months.",
  },
  {
    icon: BarChart3,
    title: "Real-time partner dashboard",
    description:
      "Track referrals, conversions, and commissions from your dedicated partner portal.",
  },
  {
    icon: Users,
    title: "Dedicated partner manager",
    description:
      "A named partner manager is assigned within 2 days of approval. Direct Slack or email access.",
  },
  {
    icon: BookOpen,
    title: "Marketing assets library",
    description:
      "Branded email templates, banners, one-pagers, and social content ready to send to clients.",
  },
  {
    icon: HeadphonesIcon,
    title: "Priority support",
    description:
      "Partners enjoy a 2-hour response SLA — skip the queue and get answers fast.",
  },
  {
    icon: BadgeCheck,
    title: "Partner certification",
    description:
      "Complete training modules and earn a Certified Varuflow Partner badge for your website.",
  },
];

const STEPS = [
  {
    num: "01",
    title: "Apply",
    description: "Submit the form below. We review every application within 1 business day.",
  },
  {
    num: "02",
    title: "Get your link & assets",
    description:
      "Receive your unique referral link, marketing kit, and partner dashboard access.",
  },
  {
    num: "03",
    title: "Share with clients",
    description:
      "Recommend Varuflow to your wholesale SMB clients via email, meetings, or your newsletter.",
  },
  {
    num: "04",
    title: "Earn 25% × 12 months",
    description:
      "For every client who activates a paid plan, you earn 25% of their monthly fee for 12 months.",
  },
];

const TESTIMONIALS = [
  {
    quote:
      "We referred 8 clients in our first quarter. The commission covered half our own Varuflow subscription — and our clients love the product.",
    name: "Britta Svensson",
    role: "CFO, Svensson & Partners",
    initials: "BS",
  },
  {
    quote:
      "Varuflow's partner program is the most transparent I've seen. Real-time dashboard, no payment delays. Highly recommend to any Swedish accounting firm.",
    name: "Jonas Karlsson",
    role: "Founder, Bokföringsbyrån Karlsson",
    initials: "JK",
  },
];

const FAQS = [
  {
    q: "How is commission paid?",
    a: "Commission is paid via monthly bank transfer by the 5th of the following month. You'll receive a statement in your partner dashboard.",
  },
  {
    q: "Is there a minimum number of referrals?",
    a: "No minimum. You can refer one client or one hundred — there's no threshold to unlock payouts.",
  },
  {
    q: "How long does approval take?",
    a: "We review every application within 1 business day. You'll receive an email with dashboard access and your referral link once approved.",
  },
  {
    q: "Can I refer existing Varuflow customers?",
    a: "No, the program is for new accounts only. Referrals that sign up with an existing org email are not eligible for commission.",
  },
  {
    q: "Is there a commission cap?",
    a: "No cap. Refer as many clients as you like — you earn 25% on each for 12 months.",
  },
];

export default function PartnersPage() {
  return (
    <>
      <JsonLd data={organizationSchema()} />

      {/* ── Hero ────────────────────────────────────────────────────────── */}
      <section
        className="relative overflow-hidden px-4 pb-16 pt-20 text-center"
        style={{
          background:
            "radial-gradient(ellipse 100% 70% at 50% -10%, rgba(37,99,235,0.18) 0%, transparent 65%)",
        }}
      >
        {/* Glow blob */}
        <div
          className="pointer-events-none absolute inset-0 -z-10"
          style={{
            background:
              "radial-gradient(ellipse 60% 40% at 50% 0%, rgba(124,58,237,0.12) 0%, transparent 70%)",
          }}
        />
        <p className="mb-5 inline-block rounded-full border border-[var(--vf-brand-border)] bg-[var(--vf-brand-primary-subtle)] px-4 py-1 text-xs font-semibold uppercase tracking-widest text-[var(--vf-brand-primary-light)]">
          For accounting firms
        </p>
        <h1 className="vf-text-1 mx-auto max-w-3xl text-4xl font-extrabold tracking-tight sm:text-5xl lg:text-6xl">
          Partner with Varuflow and{" "}
          <span className="bg-gradient-to-r from-[var(--vf-brand-primary-light)] to-[var(--vf-brand-primary)] bg-clip-text text-transparent">
            grow your practice
          </span>
        </h1>
        <p className="vf-text-2 mx-auto mt-5 max-w-xl text-lg leading-relaxed">
          Earn 25% recurring commission for 12 months on every client you refer.
          Join 60+ accounting firms already earning with us.
        </p>
        <div className="mt-8 flex flex-col items-center justify-center gap-3 sm:flex-row">
          <a
            href="#apply-form"
            className="vf-btn inline-flex items-center gap-2 rounded-xl px-7 py-3 text-base font-semibold"
          >
            Apply now — free &amp; instant
          </a>
          <a
            href="/downloads/partner-pack.pdf"
            download
            className="vf-btn-ghost inline-flex items-center gap-2 rounded-xl px-7 py-3 text-base font-semibold"
          >
            Download Partner Pack
          </a>
        </div>
      </section>

      {/* ── Benefits grid ────────────────────────────────────────────────── */}
      <section className="mx-auto max-w-5xl px-4 py-16">
        <h2 className="vf-text-1 mb-10 text-center text-2xl font-bold tracking-tight sm:text-3xl">
          Everything you need to earn with Varuflow
        </h2>
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {BENEFITS.map(({ icon: Icon, title, description }) => (
            <div
              key={title}
              className="rounded-2xl border border-white/8 bg-white/4 p-6"
            >
              <div className="mb-4 inline-flex h-10 w-10 items-center justify-center rounded-xl bg-[var(--vf-brand-primary-subtle)]">
                <Icon className="h-5 w-5 text-[var(--vf-brand-primary-light)]" />
              </div>
              <h3 className="vf-text-1 mb-2 text-base font-semibold">{title}</h3>
              <p className="vf-text-2 text-sm leading-relaxed">{description}</p>
            </div>
          ))}
        </div>
      </section>

      {/* ── How it works ─────────────────────────────────────────────────── */}
      <section
        className="px-4 py-16"
        style={{
          background:
            "radial-gradient(ellipse 80% 50% at 50% 50%, rgba(37,99,235,0.06) 0%, transparent 70%)",
        }}
      >
        <div className="mx-auto max-w-4xl">
          <h2 className="vf-text-1 mb-12 text-center text-2xl font-bold tracking-tight sm:text-3xl">
            How it works
          </h2>
          <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-4">
            {STEPS.map((step, idx) => (
              <div key={step.num} className="relative flex flex-col">
                {/* Connector line (desktop) */}
                {idx < STEPS.length - 1 && (
                  <div className="absolute right-0 top-5 hidden h-px w-full translate-x-1/2 border-t border-dashed border-[var(--vf-brand-border)] lg:block" />
                )}
                <div className="mb-4 flex h-10 w-10 items-center justify-center rounded-2xl bg-[var(--vf-brand-primary-soft)]">
                  <span className="text-sm font-bold text-[var(--vf-brand-primary-light)]">
                    {step.num}
                  </span>
                </div>
                <h3 className="vf-text-1 mb-2 text-base font-semibold">
                  {step.title}
                </h3>
                <p className="vf-text-2 text-sm leading-relaxed">
                  {step.description}
                </p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── Social proof ─────────────────────────────────────────────────── */}
      <section className="mx-auto max-w-4xl px-4 py-16">
        <h2 className="vf-text-1 mb-10 text-center text-2xl font-bold tracking-tight">
          What our partners say
        </h2>
        <div className="grid gap-6 sm:grid-cols-2">
          {TESTIMONIALS.map(({ quote, name, role, initials }) => (
            <div
              key={name}
              className="rounded-2xl border border-white/8 bg-white/4 p-6"
            >
              <p className="vf-text-2 mb-6 text-sm leading-relaxed">
                &ldquo;{quote}&rdquo;
              </p>
              <div className="flex items-center gap-3">
                <div className="flex h-9 w-9 items-center justify-center rounded-full bg-gradient-to-br from-[var(--vf-brand-primary)] to-[var(--vf-brand-primary-hover)] text-xs font-bold text-white">
                  {initials}
                </div>
                <div>
                  <p className="vf-text-1 text-sm font-semibold">{name}</p>
                  <p className="vf-text-2 text-xs">{role}</p>
                </div>
              </div>
            </div>
          ))}
        </div>
      </section>

      {/* ── Application form ─────────────────────────────────────────────── */}
      <section id="apply-form" className="px-4 py-16">
        <div className="mx-auto max-w-xl">
          <div className="rounded-2xl border border-white/10 bg-white/4 p-8">
            <div className="mb-8 text-center">
              <p className="mb-2 inline-block rounded-full border border-[var(--vf-brand-border)] bg-[var(--vf-brand-primary-subtle)] px-3 py-0.5 text-xs font-semibold uppercase tracking-wider text-[var(--vf-brand-primary-light)]">
                Apply now
              </p>
              <h2 className="vf-text-1 text-2xl font-bold tracking-tight">
                Start earning with Varuflow
              </h2>
              <p className="vf-text-2 mt-2 text-sm">
                Takes 2 minutes. We respond within 1 business day.
              </p>
            </div>
            <PartnerApplicationForm />
          </div>
        </div>
      </section>

      {/* ── FAQ ──────────────────────────────────────────────────────────── */}
      <section className="mx-auto max-w-2xl px-4 py-12">
        <h2 className="vf-text-1 mb-8 text-center text-2xl font-bold tracking-tight">
          Frequently asked questions
        </h2>
        <div className="space-y-3">
          {FAQS.map(({ q, a }) => (
            <details
              key={q}
              className="group rounded-xl border border-white/8 bg-white/4"
            >
              <summary className="vf-text-1 flex cursor-pointer items-center justify-between px-5 py-4 text-sm font-semibold marker:content-none">
                {q}
                <span className="ml-4 shrink-0 text-slate-500 transition-transform group-open:rotate-180">
                  ▾
                </span>
              </summary>
              <div className="px-5 pb-4">
                <p className="vf-text-2 text-sm leading-relaxed">{a}</p>
              </div>
            </details>
          ))}
        </div>
      </section>

      {/* ── CTA Banner ───────────────────────────────────────────────────── */}
      <CTABanner
        headline="Ready to earn with Varuflow?"
        subheadline="Apply in 2 minutes. No commitment required. We approve within 1 business day."
        ctaPrimary={{ href: "#apply-form", label: "Apply now" }}
        ctaSecondary={{ href: "/demo", label: "See the product first" }}
      />
    </>
  );
}
