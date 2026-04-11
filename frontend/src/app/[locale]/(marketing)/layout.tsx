// File: src/app/[locale]/(marketing)/layout.tsx
// Purpose: Marketing layout — header nav + footer for public-facing pages
// Used by: Landing page, pricing page

import { Link } from "@/i18n/navigation";

export default function MarketingLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <div className="min-h-screen flex flex-col" style={{ background: "var(--vf-bg-primary)" }}>
      <MarketingHeader />
      <main className="flex-1">{children}</main>
      <MarketingFooter />
    </div>
  );
}

function MarketingHeader() {
  return (
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
        {/* Logo */}
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

        {/* Nav links */}
        <nav className="flex items-center gap-1">
          <Link
            href="/pricing"
            className="rounded-lg px-3 py-1.5 text-sm font-medium text-slate-400 transition-colors hover:bg-white/[0.05] hover:text-slate-200"
          >
            Pricing
          </Link>
          <div className="mx-2 h-4 w-px bg-white/[0.10]" />
          <Link href="/" locale="sv" className="rounded px-2 py-1 text-xs font-semibold text-slate-600 hover:text-slate-300 transition-colors">
            SV
          </Link>
          <Link href="/" locale="en" className="rounded px-2 py-1 text-xs font-semibold text-slate-600 hover:text-slate-300 transition-colors">
            EN
          </Link>
          <div className="mx-2 h-4 w-px bg-white/[0.10]" />
          <Link
            href="/auth/login"
            className="rounded-lg px-3 py-1.5 text-sm font-medium text-slate-400 transition-colors hover:text-slate-200"
          >
            Log in
          </Link>
          <Link
            href="/auth/signup"
            className="ml-1 rounded-xl bg-gradient-to-br from-[#6366F1] to-[#4F46E5] px-4 py-1.5 text-sm font-semibold text-white transition-all duration-200 hover:scale-[1.02] hover:shadow-[0_0_16px_rgba(99,102,241,0.3)]"
          >
            Get started
          </Link>
        </nav>
      </div>
    </header>
  );
}

function MarketingFooter() {
  return (
    <footer
      className="border-t"
      style={{ borderColor: "rgba(255,255,255,0.07)", background: "#090C12" }}
    >
      <div className="mx-auto max-w-6xl px-4 py-12">
        <div className="flex flex-col gap-8 md:flex-row md:items-start md:justify-between">
          {/* Brand */}
          <div className="max-w-xs">
            <div className="flex items-center gap-2 mb-3">
              <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-gradient-to-br from-indigo-500 to-violet-600">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                  <polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2" />
                </svg>
              </div>
              <span className="text-[15px] font-bold tracking-tight text-white">Varuflow</span>
            </div>
            <p className="text-sm text-slate-500">
              Inventory and invoicing for Swedish wholesalers. Simple. Compliant. Fast.
            </p>
          </div>

          {/* Links */}
          <div className="flex gap-12 text-sm text-slate-500">
            <div className="space-y-3">
              <p className="text-xs font-semibold uppercase tracking-widest text-slate-400">Product</p>
              <Link href="/pricing" className="block hover:text-slate-200 transition-colors">Pricing</Link>
              <Link href="/auth/signup" className="block hover:text-slate-200 transition-colors">Get started</Link>
              <Link href="/auth/login" className="block hover:text-slate-200 transition-colors">Log in</Link>
            </div>
            <div className="space-y-3">
              <p className="text-xs font-semibold uppercase tracking-widest text-slate-400">Legal</p>
              <p className="text-slate-600">GDPR-compliant</p>
              <p className="text-slate-600">EU data residency</p>
              <p className="text-slate-600">Bokföringslagen</p>
            </div>
          </div>
        </div>

        <div className="mt-10 border-t border-white/[0.06] pt-6 flex flex-col sm:flex-row items-center justify-between gap-2 text-xs text-slate-600">
          <p>&copy; {new Date().getFullYear()} Varuflow AB. Made for Swedish wholesalers.</p>
          <p>Swedish VAT ready · SE-compliant</p>
        </div>
      </div>
    </footer>
  );
}
