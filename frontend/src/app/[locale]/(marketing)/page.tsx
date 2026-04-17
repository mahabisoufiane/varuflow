"use client";

import { Button } from "@/components/ui/button";
import { Link } from "@/i18n/navigation";
import { useState } from "react";
import { useLocale } from "next-intl";
import {
  BarChart3,
  CheckCircle2,
  FileText,
  Package,
  TrendingUp,
  Zap,
} from "lucide-react";

const FEATURES = [
  {
    icon: Package,
    title: "Real-time inventory",
    body: "Track stock across multiple warehouses. Get alerts before you run out. Record goods in, out, and adjustments in seconds.",
  },
  {
    icon: FileText,
    title: "Swedish invoicing",
    body: "Generate SE-compliant invoices with 25/12/6% VAT in one click. PDF export, payment tracking, and automatic overdue detection.",
  },
  {
    icon: TrendingUp,
    title: "Cash flow visibility",
    body: "Know exactly what's outstanding and overdue. Aging reports show your receivables bucketed by 30/60/90+ days.",
  },
  {
    icon: BarChart3,
    title: "Demand forecasting",
    body: "See which products are moving fastest. Auto-generated purchase orders based on historical movement data.",
  },
  {
    icon: Zap,
    title: "Purchase orders",
    body: "Create POs from your supplier list, track status from draft to received, and download PDFs to send directly.",
  },
  {
    icon: CheckCircle2,
    title: "GDPR & Bokföringslagen",
    body: "Data hosted in the EU. Built from the ground up for Swedish compliance — no plugins, no workarounds.",
  },
];

const PAIN_POINTS = [
  { before: "Inventory in three Excel files", after: "One live view across all warehouses" },
  { before: "Manually copy invoice numbers into Fortnox", after: "Generate & send from the same screen" },
  { before: "Discover stockouts when a customer calls", after: "Low-stock alerts before it happens" },
  { before: "Month-end cash flow guess", after: "Real-time aging report, always up to date" },
];

export default function HomePage() {
  const [email, setEmail] = useState("");
  const [company, setCompany] = useState("");
  const [submitted, setSubmitted] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const locale = useLocale();
  const priceLabel =
    locale === "sv" ? "299 kr" :
    locale === "no" ? "299 kr" :
    locale === "da" ? "299 kr" :
    "€29";

  async function handleWaitlist(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError(null);
    try {
      const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
      const res = await fetch(`${apiUrl}/api/waitlist`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, company_name: company || null }),
      });
      if (!res.ok) throw new Error("Something went wrong. Try again.");
      setSubmitted(true);
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="flex flex-col">
      {/* ── Hero ── */}
      <section className="relative overflow-hidden bg-[#1a2332] px-4 py-24 text-center text-white">
        <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_top,_rgba(255,255,255,0.05)_0%,_transparent_70%)]" />
        <div className="relative mx-auto max-w-3xl">
          <span className="mb-4 inline-block rounded-full border border-white/20 bg-white/10 px-3 py-1 text-xs font-medium tracking-wide text-white/80">
            Built for Swedish wholesalers
          </span>
          <h1 className="mt-4 text-4xl font-bold tracking-tight sm:text-5xl lg:text-6xl">
            Inventory + invoicing,
            <br />
            <span className="text-white/70">finally in one place</span>
          </h1>
          <p className="mt-6 text-lg text-white/70 max-w-2xl mx-auto">
            Stop juggling Excel and Fortnox. Varuflow gives 10–50 person Swedish wholesale businesses real-time stock control, SE-compliant invoicing, and cash flow clarity.
          </p>
          <div className="mt-10 flex flex-col sm:flex-row gap-3 justify-center">
            <Button asChild size="lg" className="bg-white text-[#1a2332] hover:bg-gray-100 font-semibold">
              <a href="#waitlist">Join the waitlist</a>
            </Button>
            <Button asChild size="lg" variant="outline" className="border-white/30 text-white hover:bg-white/10">
              <Link href="/auth/login">Log in</Link>
            </Button>
          </div>
        </div>
      </section>

      {/* ── Before / After ── */}
      <section className="bg-gray-50 px-4 py-16">
        <div className="mx-auto max-w-4xl">
          <h2 className="text-center text-2xl font-bold text-[#1a2332] mb-10">
            Sound familiar?
          </h2>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            {PAIN_POINTS.map(({ before, after }, i) => (
              <div key={i} className="rounded-xl border bg-white p-5 space-y-3">
                <p className="flex items-start gap-2 text-sm text-red-600">
                  <span className="mt-0.5 shrink-0 text-red-400">✕</span>
                  {before}
                </p>
                <p className="flex items-start gap-2 text-sm text-green-700 font-medium">
                  <span className="mt-0.5 shrink-0">✓</span>
                  {after}
                </p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── Features ── */}
      <section className="px-4 py-20">
        <div className="mx-auto max-w-5xl">
          <h2 className="text-center text-2xl font-bold text-[#1a2332] mb-2">
            Everything a wholesaler needs
          </h2>
          <p className="text-center text-muted-foreground mb-12 text-sm">
            No add-ons. No integrations to babysit. One product that does the job.
          </p>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6">
            {FEATURES.map(({ icon: Icon, title, body }) => (
              <div key={title} className="rounded-xl border bg-white p-6 space-y-3">
                <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-[#1a2332]/8">
                  <Icon className="h-5 w-5 text-[#1a2332]" />
                </div>
                <h3 className="font-semibold text-gray-900">{title}</h3>
                <p className="text-sm text-muted-foreground leading-relaxed">{body}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── Social proof / trust ── */}
      <section className="bg-[#1a2332] px-4 py-16 text-white text-center">
        <div className="mx-auto max-w-2xl space-y-4">
          <p className="text-2xl font-bold">"Finally an alternative for those of us who've outgrown Excel but don't want an ERP."</p>
          <p className="text-white/60 text-sm">— Beta user, food wholesale, Gothenburg</p>
        </div>
      </section>

      {/* ── Pricing teaser ── */}
      <section className="bg-gray-50 px-4 py-16">
        <div className="mx-auto max-w-xl text-center">
          <h2 className="text-2xl font-bold text-[#1a2332]">Simple, transparent pricing</h2>
          <p className="mt-3 text-muted-foreground text-sm">
            From {priceLabel}/month. No per-user fees. No transaction cuts.
            14-day free trial on every plan.
          </p>
          <div className="mt-6 flex flex-col sm:flex-row items-center justify-center gap-3">
            <Link
              href="/pricing"
              className="inline-flex items-center gap-2 rounded-xl bg-[#1a2332] px-6 py-3 text-sm font-semibold text-white hover:bg-[#2a3342] transition-colors"
            >
              View pricing
            </Link>
            <div className="inline-flex items-center gap-2 rounded-full bg-green-50 border border-green-200 px-4 py-2 text-sm text-green-700 font-medium">
              <CheckCircle2 className="h-4 w-4" />
              14-day free trial
            </div>
          </div>
        </div>
      </section>

      {/* ── Waitlist ── */}
      <section id="waitlist" className="px-4 py-20">
        <div className="mx-auto max-w-md">
          <div className="rounded-2xl border bg-white p-8 shadow-sm">
            {submitted ? (
              <div className="text-center space-y-3 py-4">
                <CheckCircle2 className="mx-auto h-12 w-12 text-green-500" />
                <h3 className="text-xl font-bold text-[#1a2332]">You're on the list!</h3>
                <p className="text-sm text-muted-foreground">
                  We'll email you when Varuflow is ready for early access. Expect to hear from us soon.
                </p>
              </div>
            ) : (
              <>
                <h2 className="text-xl font-bold text-[#1a2332] mb-1">Join the waitlist</h2>
                <p className="text-sm text-muted-foreground mb-6">
                  Be first in line. Waitlist members get 3 months free at launch.
                </p>
                <form onSubmit={handleWaitlist} className="space-y-4">
                  <div className="space-y-1.5">
                    <label className="text-sm font-medium text-gray-700">Work email *</label>
                    <input
                      type="email"
                      required
                      value={email}
                      onChange={(e) => setEmail(e.target.value)}
                      placeholder="you@company.se"
                      className="block w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-[#1a2332] focus:outline-none focus:ring-1 focus:ring-[#1a2332]"
                    />
                  </div>
                  <div className="space-y-1.5">
                    <label className="text-sm font-medium text-gray-700">Company name</label>
                    <input
                      type="text"
                      value={company}
                      onChange={(e) => setCompany(e.target.value)}
                      placeholder="Nordisk Handel AB"
                      className="block w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-[#1a2332] focus:outline-none focus:ring-1 focus:ring-[#1a2332]"
                    />
                  </div>
                  {error && <p className="text-sm text-red-600">{error}</p>}
                  <Button type="submit" disabled={loading} className="w-full bg-[#1a2332] hover:bg-[#2a3342] text-white">
                    {loading ? "Sending…" : "Join waitlist — it's free"}
                  </Button>
                </form>
                <p className="mt-4 text-center text-xs text-muted-foreground">
                  No spam. Unsubscribe any time. GDPR-compliant.
                </p>
              </>
            )}
          </div>
        </div>
      </section>
    </div>
  );
}
