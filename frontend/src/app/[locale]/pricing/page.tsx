// File: src/app/[locale]/pricing/page.tsx
// Purpose: Pricing page — converts visitors into paying customers
// Used by: Marketing site, linked from header nav, landing page, and PlanGate CTAs

"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
import { Link } from "@/i18n/navigation";
import {
  Check, Lock, X, ChevronDown, Star, Smartphone,
  Zap, Mail, Building2,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { PLAN_PRICES, type Plan } from "@/lib/plan";

/* ── Price display helper ────────────────────────────────────────────────────── */
function fmt(n: number): string {
  return n.toLocaleString("sv-SE");
}

/* ── FAQ item (self-contained accordion row) ─────────────────────────────────── */
function FaqItem({ q, a }: { q: string; a: string }) {
  const [open, setOpen] = useState(false);
  return (
    <div className="border-b" style={{ borderColor: "var(--vf-border)" }}>
      <button
        type="button"
        onClick={() => setOpen(!open)}
        className="flex w-full items-center justify-between gap-4 py-5 text-left"
      >
        <span className="text-[15px] font-semibold" style={{ color: "var(--vf-text-primary)" }}>
          {q}
        </span>
        <ChevronDown
          className={cn(
            "h-4 w-4 shrink-0 transition-transform duration-200 text-indigo-400",
            open && "rotate-180"
          )}
        />
      </button>
      {open && (
        <p className="pb-5 text-sm leading-relaxed" style={{ color: "var(--vf-text-secondary)" }}>
          {a}
        </p>
      )}
    </div>
  );
}

/* ── Contact modal ───────────────────────────────────────────────────────────── */
function ContactModal({ onClose }: { onClose: () => void }) {
  const t = useTranslations("pricing.contact");
  const [name, setName]       = useState("");
  const [email, setEmail]     = useState("");
  const [company, setCompany] = useState("");
  const [msg, setMsg]         = useState("");
  const [sending, setSending] = useState(false);
  const [sent, setSent]       = useState(false);

  async function handleSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setSending(true);
    // Fire-and-forget to backend waitlist endpoint (reuse existing)
    try {
      const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
      await fetch(`${apiUrl}/api/waitlist`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, company_name: company, name, message: msg }),
      });
    } catch {}
    setSending(false);
    setSent(true);
  }

  return (
    /* Backdrop */
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4"
      style={{ background: "rgba(0,0,0,0.7)", backdropFilter: "blur(4px)" }}
      onClick={(e) => e.target === e.currentTarget && onClose()}
    >
      <div
        className="w-full max-w-md rounded-2xl p-8 animate-fade-in relative"
        style={{
          background: "var(--vf-bg-surface)",
          border: "1px solid var(--vf-border)",
        }}
      >
        <button
          type="button"
          onClick={onClose}
          className="absolute right-4 top-4 rounded-lg p-1.5 transition-colors"
          style={{ color: "var(--vf-text-muted)" }}
        >
          <X className="h-4 w-4" />
        </button>

        {sent ? (
          <div className="flex flex-col items-center gap-4 py-6 text-center">
            <div className="flex h-14 w-14 items-center justify-center rounded-full bg-emerald-500/15 border border-emerald-500/20">
              <Check className="h-7 w-7 text-emerald-400" />
            </div>
            <p className="text-lg font-bold" style={{ color: "var(--vf-text-primary)" }}>
              {t("sent")}
            </p>
            <button type="button" onClick={onClose} className="vf-btn-ghost px-6">
              {t("cancel")}
            </button>
          </div>
        ) : (
          <>
            <h2 className="text-xl font-bold mb-1" style={{ color: "var(--vf-text-primary)" }}>
              {t("title")}
            </h2>
            <p className="text-sm mb-6" style={{ color: "var(--vf-text-secondary)" }}>
              {t("subtitle")}
            </p>
            <form onSubmit={handleSubmit} className="space-y-3">
              <input
                required
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder={t("name")}
                className="vf-input"
              />
              <input
                required
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder={t("email")}
                className="vf-input"
              />
              <input
                required
                value={company}
                onChange={(e) => setCompany(e.target.value)}
                placeholder={t("company")}
                className="vf-input"
              />
              <textarea
                rows={3}
                value={msg}
                onChange={(e) => setMsg(e.target.value)}
                placeholder={t("message")}
                className="vf-input h-auto py-3 resize-none"
              />
              <button type="submit" disabled={sending} className="vf-btn w-full disabled:opacity-50">
                {sending ? t("sending") : t("send")}
              </button>
            </form>
          </>
        )}
      </div>
    </div>
  );
}

/* ── Plan card ───────────────────────────────────────────────────────────────── */
interface PlanCardProps {
  plan: Plan;
  yearly: boolean;
  badge?: string;
  badgeStyle?: "indigo" | "amber";
  highlight?: boolean;
  features: string[];
  lockedFeatures?: string[];
  stars?: string[];
  ctaLabel: string;
  ctaStyle: "primary" | "secondary" | "amber";
  onCta: () => void;
}

function PlanCard({
  plan, yearly, badge, badgeStyle = "indigo", highlight = false,
  features, lockedFeatures, stars, ctaLabel, ctaStyle, onCta,
}: PlanCardProps) {
  const t = useTranslations("pricing");
  const prices = PLAN_PRICES[plan];
  const price = yearly ? prices.yearly : prices.monthly;
  const annualSek = yearly && "annualSek" in price ? (price as typeof prices.yearly).annualSek : null;

  return (
    <div
      className={cn(
        "relative flex flex-col rounded-2xl p-8 transition-all duration-200",
        highlight
          ? "scale-[1.02] shadow-[0_0_40px_rgba(99,102,241,0.25)]"
          : "hover:scale-[1.01]"
      )}
      style={{
        background: highlight ? "var(--vf-bg-elevated)" : "var(--vf-bg-surface)",
        border: highlight
          ? "1px solid rgba(99,102,241,0.5)"
          : badgeStyle === "amber"
          ? "1px solid rgba(245,158,11,0.3)"
          : "1px solid var(--vf-border)",
      }}
    >
      {/* Badge */}
      {badge && (
        <div className="absolute -top-3.5 left-1/2 -translate-x-1/2">
          <span
            className="rounded-full px-3 py-1 text-xs font-bold tracking-wide text-white whitespace-nowrap"
            style={{
              background: badgeStyle === "amber"
                ? "linear-gradient(135deg, #F59E0B, #D97706)"
                : "linear-gradient(135deg, #6366F1, #4F46E5)",
            }}
          >
            {badge}
          </span>
        </div>
      )}

      {/* Plan name */}
      <div className="mb-6">
        <p className="text-xs font-semibold uppercase tracking-widest mb-1"
          style={{ color: highlight ? "#818CF8" : badgeStyle === "amber" ? "#F59E0B" : "var(--vf-text-muted)" }}>
          {t(`${plan}.name` as "starter.name" | "professional.name" | "enterprise.name")}
        </p>
        <p className="text-sm" style={{ color: "var(--vf-text-secondary)" }}>
          {t(`${plan}.description` as "starter.description" | "professional.description" | "enterprise.description")}
        </p>
      </div>

      {/* Price */}
      <div className="mb-6">
        <div className="flex items-baseline gap-1">
          <span className="text-5xl font-bold tabular-nums" style={{ color: "var(--vf-text-primary)" }}>
            {fmt(price.sek)}
          </span>
          <span className="text-lg font-semibold" style={{ color: "var(--vf-text-muted)" }}>
            kr{t("perMonth")}
          </span>
        </div>
        <p className="mt-1 text-xs" style={{ color: "var(--vf-text-muted)" }}>
          {yearly && annualSek
            ? t("billedYearly", { amount: fmt(annualSek) })
            : `/ €${price.eur}`}
        </p>
      </div>

      {/* CTA */}
      <button
        type="button"
        onClick={onCta}
        className={cn(
          "mb-8 flex h-11 w-full items-center justify-center rounded-xl text-sm font-semibold transition-all duration-200 hover:scale-[1.01] active:scale-[0.98]",
          ctaStyle === "primary" &&
            "bg-gradient-to-br from-[#6366F1] to-[#4F46E5] text-white shadow-[inset_0_1px_0_rgba(255,255,255,0.1)] hover:shadow-[0_0_16px_rgba(99,102,241,0.4)]",
          ctaStyle === "secondary" &&
            "border text-sm font-semibold",
          ctaStyle === "amber" &&
            "bg-gradient-to-br from-[#F59E0B] to-[#D97706] text-white shadow-[inset_0_1px_0_rgba(255,255,255,0.1)] hover:shadow-[0_0_16px_rgba(245,158,11,0.4)]"
        )}
        style={
          ctaStyle === "secondary"
            ? { borderColor: "var(--vf-border)", color: "var(--vf-text-primary)", background: "var(--vf-glass-bg)" }
            : {}
        }
      >
        {ctaLabel}
      </button>

      {/* Included features */}
      <div className="flex flex-col gap-3">
        <p className="text-[11px] font-semibold uppercase tracking-wider" style={{ color: "var(--vf-text-muted)" }}>
          {t("includes")}
        </p>
        {features.map((f) => (
          <div key={f} className="flex items-start gap-2.5">
            <Check className="mt-0.5 h-4 w-4 shrink-0 text-emerald-400" />
            <span className="text-sm" style={{ color: "var(--vf-text-secondary)" }}>{f}</span>
          </div>
        ))}

        {/* Enterprise star features */}
        {stars && stars.map((f) => (
          <div key={f} className="flex items-start gap-2.5">
            <Star className="mt-0.5 h-4 w-4 shrink-0 text-amber-400 fill-amber-400/30" />
            <span className="text-sm font-medium" style={{ color: "var(--vf-text-primary)" }}>{f}</span>
          </div>
        ))}

        {/* Locked features */}
        {lockedFeatures && lockedFeatures.length > 0 && (
          <>
            <p className="mt-2 text-[11px] font-semibold uppercase tracking-wider" style={{ color: "var(--vf-text-muted)" }}>
              {t("locked")}
            </p>
            {lockedFeatures.map((f) => (
              <div key={f} className="flex items-start gap-2.5 opacity-50">
                <Lock className="mt-0.5 h-4 w-4 shrink-0" style={{ color: "var(--vf-text-muted)" }} />
                <span className="text-sm" style={{ color: "var(--vf-text-muted)" }}>{f}</span>
              </div>
            ))}
          </>
        )}
      </div>
    </div>
  );
}

/* ── Store badge ─────────────────────────────────────────────────────────────── */
function StoreBadge({ label, locked }: { label: string; locked: boolean }) {
  return (
    <div
      className={cn(
        "flex items-center gap-2.5 rounded-xl border px-4 py-3 transition-all",
        locked ? "opacity-40 grayscale" : "hover:scale-[1.02]"
      )}
      style={{ borderColor: "var(--vf-border)", background: "var(--vf-glass-bg)" }}
    >
      <Smartphone className="h-5 w-5 shrink-0 text-indigo-400" />
      <div>
        <p className="text-[10px] uppercase tracking-widest" style={{ color: "var(--vf-text-muted)" }}>
          {locked ? "Coming soon" : "Download on"}
        </p>
        <p className="text-sm font-semibold" style={{ color: "var(--vf-text-primary)" }}>{label}</p>
      </div>
      {locked && <Lock className="ml-auto h-4 w-4 shrink-0" style={{ color: "var(--vf-text-muted)" }} />}
    </div>
  );
}

/* ══════════════════════════════════════════════════════════════════════════════
   PAGE
══════════════════════════════════════════════════════════════════════════════ */
export default function PricingPage() {
  const t = useTranslations("pricing");
  const [yearly, setYearly]           = useState(false);
  const [contactOpen, setContactOpen] = useState(false);

  // Typed feature arrays from translations
  const starterFeatures      = t.raw("starter.features") as string[];
  const starterLocked        = t.raw("starter.locked") as string[];
  const proFeatures          = t.raw("professional.features") as string[];
  const proLocked            = t.raw("professional.locked") as string[];
  const enterpriseFeatures   = t.raw("enterprise.features") as string[];
  const enterpriseStars      = t.raw("enterprise.stars") as string[];
  const faqItems             = t.raw("faq.items") as { q: string; a: string }[];

  function goToSignup(plan: "starter" | "professional") {
    window.location.href = `/auth/signup?plan=${plan}`;
  }

  return (
    <>
      {contactOpen && <ContactModal onClose={() => setContactOpen(false)} />}

      <div className="mx-auto max-w-6xl px-4 py-20 space-y-24">

        {/* ── Header ──────────────────────────────────────────────────────── */}
        <div className="text-center space-y-4">
          <div className="inline-flex items-center gap-2 rounded-full border px-3 py-1 text-xs font-medium mb-2"
            style={{ borderColor: "rgba(99,102,241,0.3)", background: "rgba(99,102,241,0.08)", color: "#818CF8" }}>
            <Zap className="h-3 w-3" />
            14-day free trial on all plans
          </div>
          <h1 className="text-4xl font-bold tracking-tight sm:text-5xl" style={{ color: "var(--vf-text-primary)" }}>
            {t("pageTitle")}
          </h1>
          <p className="mx-auto max-w-xl text-base" style={{ color: "var(--vf-text-secondary)" }}>
            {t("pageSubtitle")}
          </p>

          {/* Monthly / Yearly toggle */}
          <div className="mt-6 inline-flex items-center gap-1 rounded-xl border p-1"
            style={{ borderColor: "var(--vf-border)", background: "var(--vf-glass-bg)" }}>
            <button
              type="button"
              onClick={() => setYearly(false)}
              className={cn(
                "rounded-lg px-5 py-2 text-sm font-semibold transition-all duration-200",
                !yearly
                  ? "bg-gradient-to-br from-[#6366F1] to-[#4F46E5] text-white shadow-sm"
                  : "text-slate-500 hover:text-slate-300"
              )}
            >
              {t("monthly")}
            </button>
            <button
              type="button"
              onClick={() => setYearly(true)}
              className={cn(
                "flex items-center gap-2 rounded-lg px-5 py-2 text-sm font-semibold transition-all duration-200",
                yearly
                  ? "bg-gradient-to-br from-[#6366F1] to-[#4F46E5] text-white shadow-sm"
                  : "text-slate-500 hover:text-slate-300"
              )}
            >
              {t("yearly")}
              <span className={cn(
                "rounded-full px-2 py-0.5 text-[10px] font-bold transition-colors",
                yearly ? "bg-white/20 text-white" : "bg-emerald-500/20 text-emerald-400"
              )}>
                {t("yearlySave")}
              </span>
            </button>
          </div>
        </div>

        {/* ── Plan cards ──────────────────────────────────────────────────── */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6 items-start">
          <PlanCard
            plan="starter"
            yearly={yearly}
            features={starterFeatures}
            lockedFeatures={starterLocked}
            ctaLabel={t("startTrial")}
            ctaStyle="secondary"
            onCta={() => goToSignup("starter")}
          />
          <PlanCard
            plan="professional"
            yearly={yearly}
            badge={t("mostPopular")}
            badgeStyle="indigo"
            highlight
            features={proFeatures}
            lockedFeatures={proLocked}
            ctaLabel={t("startTrial")}
            ctaStyle="primary"
            onCta={() => goToSignup("professional")}
          />
          <PlanCard
            plan="enterprise"
            yearly={yearly}
            badge={t("fullAccess")}
            badgeStyle="amber"
            features={enterpriseFeatures}
            stars={enterpriseStars}
            ctaLabel={t("contactSales")}
            ctaStyle="amber"
            onCta={() => setContactOpen(true)}
          />
        </div>

        {/* Trial note */}
        <p className="text-center text-xs -mt-16" style={{ color: "var(--vf-text-muted)" }}>
          {t("trialNote")}
        </p>

        {/* ── Mobile app teaser ───────────────────────────────────────────── */}
        <div
          className="relative overflow-hidden rounded-2xl p-10 text-center space-y-6"
          style={{ background: "var(--vf-bg-elevated)", border: "1px solid var(--vf-border)" }}
        >
          {/* Background orbs */}
          <div className="pointer-events-none absolute inset-0 overflow-hidden">
            <div className="absolute -top-16 -right-16 h-64 w-64 rounded-full opacity-10 blur-3xl"
              style={{ background: "radial-gradient(circle, #6366F1 0%, transparent 70%)" }} />
            <div className="absolute -bottom-16 -left-16 h-64 w-64 rounded-full opacity-10 blur-3xl"
              style={{ background: "radial-gradient(circle, #F59E0B 0%, transparent 70%)" }} />
          </div>

          <div className="relative">
            <div className="mx-auto mb-4 flex h-14 w-14 items-center justify-center rounded-2xl bg-indigo-500/15 border border-indigo-500/20">
              <Smartphone className="h-7 w-7 text-indigo-400" />
            </div>
            <h2 className="text-2xl font-bold" style={{ color: "var(--vf-text-primary)" }}>
              {t("mobileTeaser.title")}
            </h2>
            <p className="mx-auto mt-3 max-w-lg text-sm" style={{ color: "var(--vf-text-secondary)" }}>
              {t("mobileTeaser.subtitle")}
            </p>

            {/* Store badges — locked for non-enterprise */}
            <div className="mt-8 flex flex-col sm:flex-row items-center justify-center gap-3">
              <StoreBadge label={t("mobileTeaser.android")} locked />
              <StoreBadge label={t("mobileTeaser.ios")} locked />
              <StoreBadge label={t("mobileTeaser.huawei")} locked />
            </div>

            <div className="mt-6 inline-flex items-center gap-2 rounded-full border px-4 py-2 text-xs font-semibold"
              style={{ borderColor: "rgba(245,158,11,0.3)", background: "rgba(245,158,11,0.08)", color: "#F59E0B" }}>
              <Lock className="h-3 w-3" />
              {t("mobileTeaser.badge")}
            </div>

            <div className="mt-4">
              <button
                type="button"
                onClick={() => setContactOpen(true)}
                className="inline-flex items-center gap-2 rounded-xl bg-gradient-to-br from-[#F59E0B] to-[#D97706] px-6 py-3 text-sm font-semibold text-white transition-all duration-200 hover:scale-[1.02] hover:shadow-[0_0_20px_rgba(245,158,11,0.3)]"
              >
                {t("mobileTeaser.cta")}
              </button>
            </div>
          </div>
        </div>

        {/* ── FAQ ─────────────────────────────────────────────────────────── */}
        <div className="mx-auto max-w-2xl">
          <h2 className="mb-8 text-center text-2xl font-bold" style={{ color: "var(--vf-text-primary)" }}>
            {t("faq.title")}
          </h2>
          <div className="rounded-2xl overflow-hidden"
            style={{ background: "var(--vf-bg-surface)", border: "1px solid var(--vf-border)" }}>
            <div className="px-8">
              {faqItems.map((item) => (
                <FaqItem key={item.q} q={item.q} a={item.a} />
              ))}
            </div>
          </div>
        </div>

        {/* ── Bottom CTA ──────────────────────────────────────────────────── */}
        <div
          className="rounded-2xl p-12 text-center space-y-5"
          style={{
            background: "linear-gradient(135deg, rgba(99,102,241,0.12) 0%, rgba(79,70,229,0.06) 100%)",
            border: "1px solid rgba(99,102,241,0.2)",
          }}
        >
          <h2 className="text-2xl font-bold" style={{ color: "var(--vf-text-primary)" }}>
            Ready to replace your spreadsheets?
          </h2>
          <p style={{ color: "var(--vf-text-secondary)" }}>
            Start your free 14-day trial. No credit card required.
          </p>
          <div className="flex flex-col sm:flex-row items-center justify-center gap-3">
            <Link
              href="/auth/signup?plan=professional"
              className="inline-flex h-12 items-center gap-2 rounded-xl bg-gradient-to-br from-[#6366F1] to-[#4F46E5] px-7 text-sm font-semibold text-white transition-all duration-200 hover:scale-[1.02] hover:shadow-[0_0_20px_rgba(99,102,241,0.4)]"
            >
              Start free trial
            </Link>
            <button
              type="button"
              onClick={() => setContactOpen(true)}
              className="inline-flex h-12 items-center gap-2 rounded-xl border px-7 text-sm font-semibold transition-all duration-200 hover:scale-[1.01]"
              style={{ borderColor: "var(--vf-border)", color: "var(--vf-text-secondary)", background: "var(--vf-glass-bg)" }}
            >
              <Mail className="h-4 w-4" />
              Talk to sales
            </button>
          </div>
        </div>

      </div>
    </>
  );
}
