"use client";

import { Link } from "@/i18n/navigation";
import { PLAN_PRICES } from "@/lib/plan";
import {
  ArrowRight, BarChart3, CheckCircle2, ChevronRight, FileText,
  Package, RefreshCw, ShoppingCart, TrendingUp, Users, Zap,
  Shield, Globe, Bot, Star,
} from "lucide-react";
import { ScrollReveal } from "@/components/marketing/ScrollReveal";
import { useTranslations } from "next-intl";

/* ── Data ────────────────────────────────────────────────────────────────── */
// Copy lives in messages/*.json under home.features.* (sv is the primary market).
const FEATURES = [
  { icon: Package,      k: "f1", color: "from-blue-500 to-cyan-500" },
  { icon: FileText,     k: "f2", color: "from-[var(--vf-brand-primary-light)] to-[var(--vf-brand-primary)]" },
  { icon: TrendingUp,   k: "f3", color: "from-emerald-500 to-teal-500" },
  { icon: ShoppingCart, k: "f4", color: "from-orange-500 to-amber-500" },
  { icon: Bot,          k: "f5", color: "from-pink-500 to-rose-500" },
  { icon: BarChart3,    k: "f6", color: "from-[var(--vf-brand-primary)] to-[var(--vf-brand-primary-hover)]" },
] as const;

const STEPS = [{ n: "1", k: "s1" }, { n: "2", k: "s2" }, { n: "3", k: "s3" }] as const;

const TRUST_ITEMS = [
  { icon: Shield, k: "gdpr" },
  { icon: Globe, k: "eu" },
  { icon: CheckCircle2, k: "bokforing" },
  { icon: RefreshCw, k: "uptime" },
] as const;

const TESTIMONIALS = [
  { name: "Mattias L.", k: 1 },
  { name: "Sara K.", k: 2 },
  { name: "Johan A.", k: 3 },
] as const;

/* ── Reusable badge ───────────────────────────────────────────────────────── */
function Badge({ children }: { children: React.ReactNode }) {
  return (
    <span className="inline-flex items-center gap-1.5 rounded-full border border-[var(--vf-brand-border)] bg-[var(--vf-brand-primary-subtle)] px-3 py-1 text-xs font-semibold tracking-wide text-[var(--vf-brand-primary-light)]">
      {children}
    </span>
  );
}

/* ── Page ─────────────────────────────────────────────────────────────────── */
export default function HomePage() {
  const t = useTranslations("home");
  return (
    <div className="flex flex-col text-white" style={{ background: "#070B12" }}>

      {/* ═══════════════════════════════════════════════════════════════════
          HERO
      ═══════════════════════════════════════════════════════════════════ */}
      <section className="relative overflow-hidden px-4 pt-24 pb-32">
        {/* Background orbs */}
        <div className="pointer-events-none absolute inset-0">
          <div className="absolute -top-40 left-1/2 -translate-x-1/2 h-[600px] w-[900px] rounded-full opacity-20"
            style={{ background: "radial-gradient(ellipse,var(--vf-brand-primary) 0%,transparent 70%)" }} />
          <div className="absolute top-1/2 -left-32 h-[400px] w-[400px] rounded-full opacity-10"
            style={{ background: "radial-gradient(circle,var(--vf-brand-primary-hover) 0%,transparent 70%)" }} />
          <div className="absolute bottom-0 right-0 h-[300px] w-[400px] rounded-full opacity-10"
            style={{ background: "radial-gradient(circle,var(--vf-brand-primary) 0%,transparent 70%)" }} />
          {/* Grid overlay */}
          <div className="absolute inset-0 opacity-[0.03]"
            style={{ backgroundImage: "linear-gradient(#fff 1px,transparent 1px),linear-gradient(90deg,#fff 1px,transparent 1px)", backgroundSize: "48px 48px" }} />
        </div>

        <div className="relative mx-auto max-w-4xl text-center">
          <Badge>
            <Zap className="h-3 w-3" />
            {t("hero.badge")}
          </Badge>

          <h1 className="mt-6 text-5xl font-extrabold leading-tight tracking-tight sm:text-6xl lg:text-7xl">
            {t("hero.h1a")}
            <br />
            <span className="bg-gradient-to-r from-[var(--vf-brand-primary-light)] via-[var(--vf-brand-primary-light)] to-[var(--vf-brand-primary)] bg-clip-text text-transparent">
              {t("hero.h1b")}
            </span>
            <br />
            {t("hero.h1c")}
          </h1>

          <p className="mx-auto mt-6 max-w-2xl text-lg text-slate-400 leading-relaxed">
            {t("hero.sub")}
          </p>

          <div className="mt-10 flex flex-col sm:flex-row items-center justify-center gap-4">
            <Link
              href="/auth/signup"
              className="group flex items-center gap-2 rounded-xl bg-gradient-to-r from-[var(--vf-brand-primary)] to-[var(--vf-brand-primary-hover)] px-7 py-3.5 text-sm font-bold text-white vf-shadow-brand transition-all hover:scale-[1.02] active:scale-[0.98]"
            >
              {t("hero.ctaTrial")}
              <ArrowRight className="h-4 w-4 transition-transform group-hover:translate-x-0.5" />
            </Link>
            <Link
              href="/demo"
              className="flex items-center gap-2 rounded-xl border border-white/20 bg-[#1a2234] px-7 py-3.5 text-sm font-semibold text-slate-300 transition-all hover:bg-[#1e2740] hover:text-white"
            >
              {t("hero.ctaDemo")}
              <ChevronRight className="h-4 w-4 opacity-50" />
            </Link>
          </div>

          <p className="mt-4 text-xs text-slate-500">
            {t("hero.disclaimer")}
          </p>
        </div>

        {/* App preview mockup */}
        <div className="relative mx-auto mt-20 max-w-5xl px-4">
          <div className="rounded-2xl border border-white/10 bg-[#0D1117] shadow-2xl shadow-black/60 overflow-hidden">
            <div className="flex h-10 items-center gap-2 border-b border-white/[0.06] px-4">
              <div className="h-3 w-3 rounded-full bg-red-500/70" />
              <div className="h-3 w-3 rounded-full bg-yellow-500/70" />
              <div className="h-3 w-3 rounded-full bg-green-500/70" />
              <div className="ml-4 h-5 w-48 rounded-md bg-white/[0.04]" />
            </div>
            <div className="flex">
              {/* Fake sidebar */}
              <div className="hidden sm:flex w-[180px] shrink-0 flex-col gap-1 border-r border-white/[0.06] p-3">
                {["Dashboard","Sales","Inventory","Finance","HR & People","Settings"].map((s, i) => (
                  <div key={s} className={`flex items-center gap-2 rounded-lg px-3 py-2 text-[11px] font-medium ${i === 0 ? "bg-[var(--vf-brand-primary-soft)] text-[var(--vf-brand-primary-light)]" : "text-slate-500"}`}>
                    <div className={`h-2 w-2 rounded-sm ${i === 0 ? "bg-[var(--vf-brand-primary-light)]" : "bg-slate-700"}`} />
                    {s}
                  </div>
                ))}
              </div>
              {/* Fake content */}
              <div className="flex-1 p-5 space-y-4">
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                  {["Total Revenue","Open Invoices","Stock Value","Low Stock"].map((label, i) => (
                    <div key={label} className="rounded-xl border border-white/[0.06] bg-white/[0.02] p-3 space-y-2">
                      <p className="text-[10px] text-slate-500 uppercase tracking-wider">{label}</p>
                      <div className="h-5 w-20 rounded bg-white/[0.06]" />
                      <div className={`h-2.5 w-12 rounded text-[8px] flex items-center gap-1 ${i % 2 === 0 ? "text-emerald-500" : "text-slate-500"}`}>
                        <div className={`h-2 w-10 rounded ${i % 2 === 0 ? "bg-emerald-500/30" : "bg-slate-700"}`} />
                      </div>
                    </div>
                  ))}
                </div>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                  <div className="rounded-xl border border-white/[0.06] bg-white/[0.02] p-3 h-28 flex flex-col gap-2">
                    <div className="h-3 w-24 rounded bg-white/[0.06]" />
                    <div className="flex-1 flex items-end gap-1 pt-2">
                      {[40,65,45,80,55,90,70,85,60,95,75,88].map((h, i) => (
                        <div key={i} className="flex-1 rounded-t" style={{ height: `${h}%`, background: `hsl(${240 + i * 3},70%,60%,0.5)` }} />
                      ))}
                    </div>
                  </div>
                  <div className="rounded-xl border border-white/[0.06] bg-white/[0.02] p-3 h-28 space-y-2">
                    <div className="h-3 w-24 rounded bg-white/[0.06]" />
                    {[85,60,40].map((w, i) => (
                      <div key={i} className="flex items-center gap-2">
                        <div className="h-2 flex-1 rounded-full bg-white/[0.04]">
                          <div className="h-2 rounded-full bg-[var(--vf-brand-border)]" style={{ width: `${w}%` }} />
                        </div>
                        <span className="text-[9px] text-slate-600 w-6">{w}%</span>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            </div>
          </div>
          {/* Glow under mockup */}
          <div className="absolute -bottom-8 left-1/2 -translate-x-1/2 h-24 w-3/4 blur-3xl opacity-20"
            style={{ background: "radial-gradient(ellipse,var(--vf-brand-primary),transparent)" }} />
        </div>
      </section>

      {/* ═══════════════════════════════════════════════════════════════════
          TRUST STRIP
      ═══════════════════════════════════════════════════════════════════ */}
      <section className="border-y border-white/[0.06] bg-white/[0.015] px-4 py-5">
        <div className="mx-auto max-w-4xl flex flex-wrap items-center justify-center gap-8">
          {TRUST_ITEMS.map(({ icon: Icon, k }) => (
            <div key={k} className="flex items-center gap-2 text-sm text-slate-400">
              <Icon className="h-4 w-4 text-emerald-500 shrink-0" />
              {t(`trust.${k}`)}
            </div>
          ))}
        </div>
      </section>

      {/* ═══════════════════════════════════════════════════════════════════
          FEATURES
      ═══════════════════════════════════════════════════════════════════ */}
      <section className="px-4 py-24">
        <div className="mx-auto max-w-5xl">
          <div className="text-center mb-16">
            <Badge>{t("features.badge")}</Badge>
            <h2 className="mt-4 text-3xl font-bold tracking-tight sm:text-4xl">
              {t("features.h2a")}
              <br />
              <span className="text-slate-400">{t("features.h2b")}</span>
            </h2>
            <p className="mt-4 text-slate-400 max-w-xl mx-auto">
              {t("features.sub")}
            </p>
          </div>

          <ScrollReveal stagger className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-5">
            {FEATURES.map(({ icon: Icon, k, color }) => (
              <div
                key={k}
                className="group relative rounded-2xl border border-white/[0.07] bg-white/[0.03] p-6 space-y-4 transition-all hover:border-white/[0.15] hover:bg-white/[0.05]"
              >
                <div className={`flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-br ${color} shadow-lg`}>
                  <Icon className="h-5 w-5 text-white" />
                </div>
                <h3 className="font-semibold text-white text-base">{t(`features.${k}t`)}</h3>
                <p className="text-sm text-slate-400 leading-relaxed">{t(`features.${k}b`)}</p>
              </div>
            ))}
          </ScrollReveal>

          <div className="mt-10 text-center">
            <Link href="/features" className="inline-flex items-center gap-1.5 text-sm font-medium text-[var(--vf-brand-primary-light)] hover:text-white transition-colors">
              {t("features.seeAll")} <ChevronRight className="h-4 w-4" />
            </Link>
          </div>
        </div>
      </section>

      {/* ═══════════════════════════════════════════════════════════════════
          HOW IT WORKS
      ═══════════════════════════════════════════════════════════════════ */}
      <section className="px-4 py-24 border-t border-white/[0.06]" style={{ background: "rgba(255,255,255,0.01)" }}>
        <div className="mx-auto max-w-3xl">
          <div className="text-center mb-14">
            <Badge>{t("steps.badge")}</Badge>
            <h2 className="mt-4 text-3xl font-bold tracking-tight">{t("steps.h2")}</h2>
          </div>
          <div className="relative flex flex-col gap-8">
            <div className="absolute left-5 top-10 bottom-10 w-px bg-gradient-to-b from-[var(--vf-brand-primary)]/60 via-[var(--vf-brand-border)] to-transparent hidden sm:block" />
            {STEPS.map(({ n, k }) => (
              <div key={n} className="flex gap-5">
                <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-gradient-to-br from-[var(--vf-brand-primary)] to-[var(--vf-brand-primary-hover)] text-sm font-bold text-white vf-shadow-brand z-10">
                  {n}
                </div>
                <div className="pt-1.5">
                  <h3 className="font-semibold text-white text-base">{t(`steps.${k}t`)}</h3>
                  <p className="mt-1 text-sm text-slate-400">{t(`steps.${k}b`)}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ═══════════════════════════════════════════════════════════════════
          TESTIMONIALS
      ═══════════════════════════════════════════════════════════════════ */}
      <section className="px-4 py-24 border-t border-white/[0.06]">
        <div className="mx-auto max-w-5xl">
          <div className="text-center mb-14">
            <Badge>{t("testimonials.badge")}</Badge>
            <h2 className="mt-4 text-3xl font-bold tracking-tight">{t("testimonials.h2")}</h2>
          </div>
          <ScrollReveal stagger className="grid grid-cols-1 sm:grid-cols-3 gap-5">
            {TESTIMONIALS.map(({ name, k }) => (
              <div key={name} className="rounded-2xl border border-white/[0.07] bg-white/[0.03] p-6 space-y-4">
                <div className="flex gap-0.5">
                  {[...Array(5)].map((_, i) => (
                    <Star key={i} className="h-4 w-4 fill-amber-400 text-amber-400" />
                  ))}
                </div>
                <p className="text-sm text-slate-300 leading-relaxed">"{t(`testimonials.q${k}`)}"</p>
                <div>
                  <p className="text-sm font-semibold text-white">{name}</p>
                  <p className="text-xs text-slate-500 mt-0.5">{t(`testimonials.r${k}`)}</p>
                </div>
              </div>
            ))}
          </ScrollReveal>
        </div>
      </section>

      {/* ═══════════════════════════════════════════════════════════════════
          PRICING TEASER
      ═══════════════════════════════════════════════════════════════════ */}
      <section className="px-4 py-24 border-t border-white/[0.06]" style={{ background: "rgba(255,255,255,0.01)" }}>
        <div className="mx-auto max-w-xl text-center">
          <Badge>{t("pricing.badge")}</Badge>
          <h2 className="mt-4 text-3xl font-bold tracking-tight">{t("pricing.h2")}</h2>
          <p className="mt-4 text-slate-400">
            {t("pricing.from")} <span className="text-[var(--vf-brand-primary-light)] font-semibold">{PLAN_PRICES.starter.monthly.sek} {t("pricing.perMonth")}</span>. {t("pricing.body")}
          </p>
          <div className="mt-8 flex flex-col sm:flex-row items-center justify-center gap-4">
            <Link
              href="/auth/signup"
              className="group flex items-center gap-2 rounded-xl bg-gradient-to-r from-[var(--vf-brand-primary)] to-[var(--vf-brand-primary-hover)] px-7 py-3.5 text-sm font-bold text-white vf-shadow-brand transition-all hover:scale-[1.02]"
            >
              {t("hero.ctaTrial")} <ArrowRight className="h-4 w-4 transition-transform group-hover:translate-x-0.5" />
            </Link>
            <Link
              href="/pricing"
              className="text-sm font-medium text-[var(--vf-brand-primary-light)] hover:text-white transition-colors flex items-center gap-1"
            >
              {t("pricing.seePlans")} <ChevronRight className="h-4 w-4" />
            </Link>
          </div>
          <p className="mt-4 text-xs text-slate-500">{t("pricing.disclaimer")}</p>
        </div>
      </section>

      {/* ═══════════════════════════════════════════════════════════════════
          FINAL CTA
      ═══════════════════════════════════════════════════════════════════ */}
      <section className="relative overflow-hidden px-4 py-28 border-t border-white/[0.06]">
        <div className="pointer-events-none absolute inset-0">
          <div className="absolute inset-0 opacity-20"
            style={{ background: "radial-gradient(ellipse at center,var(--vf-brand-primary) 0%,transparent 70%)" }} />
        </div>
        <div className="relative mx-auto max-w-2xl text-center">
          <h2 className="text-4xl font-extrabold tracking-tight sm:text-5xl">
            {t("cta.h2")}
          </h2>
          <p className="mt-4 text-lg text-slate-400">
            {t("cta.sub")}
          </p>
          <div className="mt-10 flex flex-col sm:flex-row items-center justify-center gap-4">
            <Link
              href="/auth/signup"
              className="group flex items-center gap-2 rounded-xl bg-gradient-to-r from-[var(--vf-brand-primary)] to-[var(--vf-brand-primary-hover)] px-8 py-4 text-sm font-bold text-white vf-shadow-brand transition-all hover:scale-[1.02] active:scale-[0.98]"
            >
              {t("cta.main")}
              <ArrowRight className="h-4 w-4 transition-transform group-hover:translate-x-0.5" />
            </Link>
            <Link
              href="/demo"
              className="flex items-center gap-2 rounded-xl border border-white/20 bg-[#1a2234] px-8 py-4 text-sm font-semibold text-slate-300 transition-all hover:bg-[#1e2740] hover:text-white"
            >
              {t("cta.demo")}
            </Link>
          </div>
          <div className="mt-8 flex flex-wrap items-center justify-center gap-6 text-sm text-slate-500">
            {(["c1", "c2", "c3", "c4"] as const).map((k) => (
              <span key={k} className="flex items-center gap-1.5">
                <CheckCircle2 className="h-3.5 w-3.5 text-emerald-500" /> {t(`cta.${k}`)}
              </span>
            ))}
          </div>
        </div>
      </section>
    </div>
  );
}
