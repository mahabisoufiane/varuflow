// File: src/app/[locale]/(marketing)/layout.tsx
// Purpose: Marketing layout — header nav + footer for public-facing pages

import type { Metadata } from "next";
import { Link } from "@/i18n/navigation";
import MarketingHeaderNav from "./HeaderNav";
import CrispChat from "@/components/marketing/CrispChat";
import ExitIntentModal from "@/components/marketing/ExitIntentModal";
import NewsletterSignup from "@/components/marketing/NewsletterSignup";

const BASE = process.env.NEXT_PUBLIC_SITE_URL ?? "https://varuflow.vercel.app";

// Base metadata for all marketing pages. Individual pages override as needed.
export const metadata: Metadata = {
  title: "Varuflow — Inventory, Invoicing & POS for Growing Businesses",
  description:
    "Manage inventory, invoices, customers, and point-of-sale in one place. Built for Swedish and European wholesalers, retailers, and service companies.",
  openGraph: {
    title: "Varuflow — Inventory, Invoicing & POS for Growing Businesses",
    description:
      "Manage inventory, invoices, customers, and POS in one place. Built for European SMBs.",
    type: "website",
    url: BASE,
    siteName: "Varuflow",
    images: [{ url: `${BASE}/og-default.png`, width: 1200, height: 630, alt: "Varuflow" }],
  },
  twitter: {
    card: "summary_large_image",
    site: "@varuflow",
    title: "Varuflow — Inventory, Invoicing & POS",
    description: "Manage inventory, invoices, customers, and POS in one place.",
    images: [`${BASE}/og-default.png`],
  },
};

export default function MarketingLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <div className="min-h-screen flex flex-col" style={{ background: "var(--vf-bg-primary)" }}>
      <header
        className="sticky top-0 z-50 border-b"
        style={{
          background: "rgba(15,23,42,0.85)",
          backdropFilter: "blur(12px)",
          WebkitBackdropFilter: "blur(12px)",
          borderColor: "rgba(255,255,255,0.07)",
        }}
      >
        <div className="mx-auto flex h-16 max-w-6xl items-center justify-between px-4">
          {/* Logo — server-rendered, no auth needed */}
          <Link href="/" className="flex items-center gap-2">
            <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-gradient-to-br from-indigo-500 to-violet-600">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                <polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2" />
              </svg>
            </div>
            <span className="text-[15px] font-bold tracking-tight bg-gradient-to-r from-indigo-400 to-violet-400 bg-clip-text text-transparent">
              Varuflow
            </span>
          </Link>

          {/* Client nav: handles locale switch + auth-aware CTA */}
          <MarketingHeaderNav />
        </div>
      </header>

      <main className="flex-1">{children}</main>

      <MarketingFooter />
      <CrispChat />
      <ExitIntentModal
        headline="Wait — get 20% off Pro"
        subheadline="Leave your email and we'll send you a one-time discount code. No spam."
        ctaLabel="Claim 20% off"
      />
    </div>
  );
}

function MarketingFooter() {
  return (
    <footer
      className="border-t"
      style={{ borderColor: "rgba(255,255,255,0.07)", background: "#090C12" }}
    >
      <div className="mx-auto max-w-6xl px-4 py-12">
        <div className="grid gap-10 md:grid-cols-5">
          {/* Brand + newsletter */}
          <div className="md:col-span-2">
            <div className="flex items-center gap-2 mb-3">
              <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-gradient-to-br from-indigo-500 to-violet-600">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                  <polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2" />
                </svg>
              </div>
              <span className="text-[15px] font-bold tracking-tight text-white">Varuflow</span>
            </div>
            <p className="text-sm text-slate-500 mb-6">
              Inventory and invoicing for Nordic wholesalers. Simple. Compliant. Fast.
            </p>
            <p className="text-xs font-semibold uppercase tracking-widest text-slate-400 mb-3">Newsletter</p>
            <NewsletterSignup compact />
          </div>

          {/* Product */}
          <div className="space-y-3 text-sm text-slate-500">
            <p className="text-xs font-semibold uppercase tracking-widest text-slate-400">Product</p>
            <Link href="/features" className="block hover:text-slate-200 transition-colors">Features</Link>
            <Link href="/pricing" className="block hover:text-slate-200 transition-colors">Pricing</Link>
            <Link href="/security" className="block hover:text-slate-200 transition-colors">Security</Link>
            <Link href="/compliance-overview" className="block hover:text-slate-200 transition-colors">Compliance</Link>
            <Link href="/blog" className="block hover:text-slate-200 transition-colors">Blog</Link>
            <Link href="/trial" className="block hover:text-slate-200 transition-colors">Free trial</Link>
            <Link href="/demo" className="block hover:text-slate-200 transition-colors">Book a demo</Link>
          </div>

          {/* Compare */}
          <div className="space-y-3 text-sm text-slate-500">
            <p className="text-xs font-semibold uppercase tracking-widest text-slate-400">Compare</p>
            <Link href="/vs/fortnox" className="block hover:text-slate-200 transition-colors">vs Fortnox</Link>
            <Link href="/vs/visma" className="block hover:text-slate-200 transition-colors">vs Visma</Link>
            <Link href="/vs/odoo" className="block hover:text-slate-200 transition-colors">vs Odoo</Link>
            <Link href="/vs/bokio" className="block hover:text-slate-200 transition-colors">vs Bokio</Link>
          </div>

          {/* Company */}
          <div className="space-y-3 text-sm text-slate-500">
            <p className="text-xs font-semibold uppercase tracking-widest text-slate-400">Company</p>
            <Link href="/about" className="block hover:text-slate-200 transition-colors">About</Link>
            <Link href="/partners" className="block hover:text-slate-200 transition-colors">Partners</Link>
            <Link href="/press" className="block hover:text-slate-200 transition-colors">Press</Link>
            <Link href="/contact" className="block hover:text-slate-200 transition-colors">Contact</Link>
            <p className="text-slate-600">GDPR-compliant</p>
            <p className="text-slate-600">EU data residency</p>
          </div>
        </div>

        <div className="mt-10 border-t border-white/[0.06] pt-6 flex flex-col sm:flex-row items-center justify-between gap-2 text-xs text-slate-600">
          <p>&copy; {new Date().getFullYear()} Varuflow AB. Made for Nordic wholesalers.</p>
          <p>Swedish VAT ready · SE-compliant · Bokföringslagen</p>
        </div>
      </div>
    </footer>
  );
}
