"use client";

import { Link } from "@/i18n/navigation";
import {
  ArrowRight, BarChart3, CheckCircle2, ChevronRight, FileText,
  Package, RefreshCw, ShoppingCart, TrendingUp, Users, Zap,
  Shield, Globe, Bot, Star,
} from "lucide-react";

/* ── Data ────────────────────────────────────────────────────────────────── */
const FEATURES = [
  {
    icon: Package,
    title: "Real-time inventory",
    body: "Live stock across every warehouse. Low-stock alerts fire before customers notice. Goods-in and adjustment records in seconds.",
    color: "from-blue-500 to-cyan-500",
  },
  {
    icon: FileText,
    title: "SE-compliant invoicing",
    body: "25 / 12 / 6 % VAT baked in. PDF export, payment tracking, automatic overdue detection — no Fortnox copy-paste ever again.",
    color: "from-violet-500 to-indigo-500",
  },
  {
    icon: TrendingUp,
    title: "Cash flow visibility",
    body: "Aging reports show 30 / 60 / 90+ day buckets at a glance. Always know what's outstanding and what's overdue.",
    color: "from-emerald-500 to-teal-500",
  },
  {
    icon: ShoppingCart,
    title: "Point of sale",
    body: "Fast checkout with barcode scanning, split payments, and automatic stock deduction. Works offline, syncs when you reconnect.",
    color: "from-orange-500 to-amber-500",
  },
  {
    icon: Bot,
    title: "AI advisor",
    body: "Flags cash-flow risks, suggests reorder quantities, and drafts purchase orders — before you even think to ask.",
    color: "from-pink-500 to-rose-500",
  },
  {
    icon: BarChart3,
    title: "Demand forecasting",
    body: "See your fastest movers and seasonal patterns. Auto-generated POs based on real historical movement data.",
    color: "from-indigo-500 to-purple-500",
  },
];

const STEPS = [
  { n: "1", title: "Create your account", body: "Sign up in 60 seconds. No credit card required." },
  { n: "2", title: "Import your data", body: "Upload products, customers, and opening stock from CSV or Excel." },
  { n: "3", title: "Start selling", body: "Issue invoices, manage inventory, and accept payments — all in one tab." },
];

const TRUST_ITEMS = [
  { icon: Shield, label: "GDPR-compliant" },
  { icon: Globe, label: "EU data residency" },
  { icon: CheckCircle2, label: "Bokföringslagen ready" },
  { icon: RefreshCw, label: "99.9 % uptime SLA" },
];

const TESTIMONIALS = [
  {
    quote: "Finally an alternative for those of us who've outgrown Excel but don't want an ERP.",
    name: "Mattias L.",
    role: "Food wholesale · Gothenburg",
  },
  {
    quote: "We cut invoice processing time by 70 %. The Fortnox sync alone paid for itself in week one.",
    name: "Sara K.",
    role: "Building supplies · Stockholm",
  },
  {
    quote: "The AI advisor flagged a stockout three weeks before our busiest season. That saved us.",
    name: "Johan A.",
    role: "Electronics distributor · Malmö",
  },
];

/* ── Reusable badge ───────────────────────────────────────────────────────── */
function Badge({ children }: { children: React.ReactNode }) {
  return (
    <span className="inline-flex items-center gap-1.5 rounded-full border border-indigo-500/30 bg-indigo-500/10 px-3 py-1 text-xs font-semibold tracking-wide text-indigo-400">
      {children}
    </span>
  );
}

/* ── Page ─────────────────────────────────────────────────────────────────── */
export default function HomePage() {
  return (
    <div className="flex flex-col text-white" style={{ background: "#070B12" }}>

      {/* ═══════════════════════════════════════════════════════════════════
          HERO
      ═══════════════════════════════════════════════════════════════════ */}
      <section className="relative overflow-hidden px-4 pt-24 pb-32">
        {/* Background orbs */}
        <div className="pointer-events-none absolute inset-0">
          <div className="absolute -top-40 left-1/2 -translate-x-1/2 h-[600px] w-[900px] rounded-full opacity-20"
            style={{ background: "radial-gradient(ellipse,#4A6CF7 0%,transparent 70%)" }} />
          <div className="absolute top-1/2 -left-32 h-[400px] w-[400px] rounded-full opacity-10"
            style={{ background: "radial-gradient(circle,#3B5CE6 0%,transparent 70%)" }} />
          <div className="absolute bottom-0 right-0 h-[300px] w-[400px] rounded-full opacity-10"
            style={{ background: "radial-gradient(circle,#7C3AED 0%,transparent 70%)" }} />
          {/* Grid overlay */}
          <div className="absolute inset-0 opacity-[0.03]"
            style={{ backgroundImage: "linear-gradient(#fff 1px,transparent 1px),linear-gradient(90deg,#fff 1px,transparent 1px)", backgroundSize: "48px 48px" }} />
        </div>

        <div className="relative mx-auto max-w-4xl text-center">
          <Badge>
            <Zap className="h-3 w-3" />
            Built for Nordic wholesalers
          </Badge>

          <h1 className="mt-6 text-5xl font-extrabold leading-tight tracking-tight sm:text-6xl lg:text-7xl">
            The backoffice
            <br />
            <span className="bg-gradient-to-r from-indigo-400 via-violet-400 to-purple-400 bg-clip-text text-transparent">
              Nordic wholesalers
            </span>
            <br />
            actually want to use.
          </h1>

          <p className="mx-auto mt-6 max-w-2xl text-lg text-slate-400 leading-relaxed">
            Inventory, invoicing, POS, and AI-driven insights — all in one platform.
            Replace Excel, Fortnox copy-paste, and guesswork with one tab that does everything.
          </p>

          <div className="mt-10 flex flex-col sm:flex-row items-center justify-center gap-4">
            <Link
              href="/auth/signup"
              className="group flex items-center gap-2 rounded-xl bg-gradient-to-r from-indigo-500 to-violet-600 px-7 py-3.5 text-sm font-bold text-white shadow-lg shadow-indigo-500/25 transition-all hover:shadow-indigo-500/40 hover:scale-[1.02] active:scale-[0.98]"
            >
              Start free trial
              <ArrowRight className="h-4 w-4 transition-transform group-hover:translate-x-0.5" />
            </Link>
            <Link
              href="/demo"
              className="flex items-center gap-2 rounded-xl border border-white/20 bg-[#1a2234] px-7 py-3.5 text-sm font-semibold text-slate-300 transition-all hover:bg-[#1e2740] hover:text-white"
            >
              Book a demo
              <ChevronRight className="h-4 w-4 opacity-50" />
            </Link>
          </div>

          <p className="mt-4 text-xs text-slate-500">
            14-day free trial · No credit card required · Cancel any time
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
                  <div key={s} className={`flex items-center gap-2 rounded-lg px-3 py-2 text-[11px] font-medium ${i === 0 ? "bg-indigo-500/15 text-indigo-400" : "text-slate-500"}`}>
                    <div className={`h-2 w-2 rounded-sm ${i === 0 ? "bg-indigo-400" : "bg-slate-700"}`} />
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
                          <div className="h-2 rounded-full bg-indigo-500/50" style={{ width: `${w}%` }} />
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
            style={{ background: "radial-gradient(ellipse,#4A6CF7,transparent)" }} />
        </div>
      </section>

      {/* ═══════════════════════════════════════════════════════════════════
          TRUST STRIP
      ═══════════════════════════════════════════════════════════════════ */}
      <section className="border-y border-white/[0.06] bg-white/[0.015] px-4 py-5">
        <div className="mx-auto max-w-4xl flex flex-wrap items-center justify-center gap-8">
          {TRUST_ITEMS.map(({ icon: Icon, label }) => (
            <div key={label} className="flex items-center gap-2 text-sm text-slate-400">
              <Icon className="h-4 w-4 text-emerald-500 shrink-0" />
              {label}
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
            <Badge>Features</Badge>
            <h2 className="mt-4 text-3xl font-bold tracking-tight sm:text-4xl">
              Everything in one platform.
              <br />
              <span className="text-slate-400">Nothing you don't need.</span>
            </h2>
            <p className="mt-4 text-slate-400 max-w-xl mx-auto">
              No add-ons to install, no integrations to babysit, no consultants to call.
              One product that does the whole job.
            </p>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-5">
            {FEATURES.map(({ icon: Icon, title, body, color }) => (
              <div
                key={title}
                className="group relative rounded-2xl border border-white/[0.07] bg-white/[0.03] p-6 space-y-4 transition-all hover:border-white/[0.15] hover:bg-white/[0.05]"
              >
                <div className={`flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-br ${color} shadow-lg`}>
                  <Icon className="h-5 w-5 text-white" />
                </div>
                <h3 className="font-semibold text-white text-base">{title}</h3>
                <p className="text-sm text-slate-400 leading-relaxed">{body}</p>
              </div>
            ))}
          </div>

          <div className="mt-10 text-center">
            <Link href="/features" className="inline-flex items-center gap-1.5 text-sm font-medium text-indigo-400 hover:text-indigo-300 transition-colors">
              See all features <ChevronRight className="h-4 w-4" />
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
            <Badge>How it works</Badge>
            <h2 className="mt-4 text-3xl font-bold tracking-tight">Up and running in one afternoon.</h2>
          </div>
          <div className="relative flex flex-col gap-8">
            <div className="absolute left-5 top-10 bottom-10 w-px bg-gradient-to-b from-indigo-500/60 via-violet-500/40 to-transparent hidden sm:block" />
            {STEPS.map(({ n, title, body }) => (
              <div key={n} className="flex gap-5">
                <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-gradient-to-br from-indigo-500 to-violet-600 text-sm font-bold text-white shadow-lg shadow-indigo-500/30 z-10">
                  {n}
                </div>
                <div className="pt-1.5">
                  <h3 className="font-semibold text-white text-base">{title}</h3>
                  <p className="mt-1 text-sm text-slate-400">{body}</p>
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
            <Badge>Testimonials</Badge>
            <h2 className="mt-4 text-3xl font-bold tracking-tight">What early users say.</h2>
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-5">
            {TESTIMONIALS.map(({ quote, name, role }) => (
              <div key={name} className="rounded-2xl border border-white/[0.07] bg-white/[0.03] p-6 space-y-4">
                <div className="flex gap-0.5">
                  {[...Array(5)].map((_, i) => (
                    <Star key={i} className="h-4 w-4 fill-amber-400 text-amber-400" />
                  ))}
                </div>
                <p className="text-sm text-slate-300 leading-relaxed">"{quote}"</p>
                <div>
                  <p className="text-sm font-semibold text-white">{name}</p>
                  <p className="text-xs text-slate-500 mt-0.5">{role}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ═══════════════════════════════════════════════════════════════════
          PRICING TEASER
      ═══════════════════════════════════════════════════════════════════ */}
      <section className="px-4 py-24 border-t border-white/[0.06]" style={{ background: "rgba(255,255,255,0.01)" }}>
        <div className="mx-auto max-w-xl text-center">
          <Badge>Pricing</Badge>
          <h2 className="mt-4 text-3xl font-bold tracking-tight">Simple pricing. No surprises.</h2>
          <p className="mt-4 text-slate-400">
            From <span className="text-indigo-400 font-semibold">299 kr/month</span>. No per-user fees. No transaction cuts. Cancel any time.
          </p>
          <div className="mt-8 flex flex-col sm:flex-row items-center justify-center gap-4">
            <Link
              href="/auth/signup"
              className="group flex items-center gap-2 rounded-xl bg-gradient-to-r from-indigo-500 to-violet-600 px-7 py-3.5 text-sm font-bold text-white shadow-lg shadow-indigo-500/25 transition-all hover:shadow-indigo-500/40 hover:scale-[1.02]"
            >
              Start free trial <ArrowRight className="h-4 w-4 transition-transform group-hover:translate-x-0.5" />
            </Link>
            <Link
              href="/pricing"
              className="text-sm font-medium text-indigo-400 hover:text-indigo-300 transition-colors flex items-center gap-1"
            >
              See all plans <ChevronRight className="h-4 w-4" />
            </Link>
          </div>
          <p className="mt-4 text-xs text-slate-500">14-day free trial · No credit card required</p>
        </div>
      </section>

      {/* ═══════════════════════════════════════════════════════════════════
          FINAL CTA
      ═══════════════════════════════════════════════════════════════════ */}
      <section className="relative overflow-hidden px-4 py-28 border-t border-white/[0.06]">
        <div className="pointer-events-none absolute inset-0">
          <div className="absolute inset-0 opacity-20"
            style={{ background: "radial-gradient(ellipse at center,#4A6CF7 0%,transparent 70%)" }} />
        </div>
        <div className="relative mx-auto max-w-2xl text-center">
          <h2 className="text-4xl font-extrabold tracking-tight sm:text-5xl">
            Ready to replace Excel?
          </h2>
          <p className="mt-4 text-lg text-slate-400">
            Join hundreds of Nordic wholesalers who've moved their operations to Varuflow.
          </p>
          <div className="mt-10 flex flex-col sm:flex-row items-center justify-center gap-4">
            <Link
              href="/auth/signup"
              className="group flex items-center gap-2 rounded-xl bg-gradient-to-r from-indigo-500 to-violet-600 px-8 py-4 text-sm font-bold text-white shadow-xl shadow-indigo-500/30 transition-all hover:scale-[1.02] hover:shadow-indigo-500/50 active:scale-[0.98]"
            >
              Start free — no card needed
              <ArrowRight className="h-4 w-4 transition-transform group-hover:translate-x-0.5" />
            </Link>
            <Link
              href="/demo"
              className="flex items-center gap-2 rounded-xl border border-white/20 bg-[#1a2234] px-8 py-4 text-sm font-semibold text-slate-300 transition-all hover:bg-[#1e2740] hover:text-white"
            >
              Book a 20-min demo
            </Link>
          </div>
          <div className="mt-8 flex flex-wrap items-center justify-center gap-6 text-sm text-slate-500">
            {["14-day free trial", "No credit card", "EU data residency", "Cancel any time"].map(t => (
              <span key={t} className="flex items-center gap-1.5">
                <CheckCircle2 className="h-3.5 w-3.5 text-emerald-500" /> {t}
              </span>
            ))}
          </div>
        </div>
      </section>
    </div>
  );
}
