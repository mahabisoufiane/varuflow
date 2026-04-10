import { Link } from "@/i18n/navigation";

export default function MarketingLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <div className="min-h-screen flex flex-col">
      <MarketingHeader />
      <main className="flex-1">{children}</main>
      <MarketingFooter />
    </div>
  );
}

function MarketingHeader() {
  return (
    <header className="sticky top-0 z-50 border-b bg-white/95 backdrop-blur">
      <div className="container mx-auto flex h-16 items-center justify-between px-4">
        <Link href="/" className="text-xl font-bold text-[#1a2332]">
          Varuflow
        </Link>
        <nav className="flex items-center gap-3">
          <Link href="/" locale="sv" className="text-xs text-muted-foreground hover:text-foreground px-1">SV</Link>
          <Link href="/" locale="en" className="text-xs text-muted-foreground hover:text-foreground px-1">EN</Link>
          <Link
            href="/auth/login"
            className="text-sm font-medium text-gray-700 hover:text-[#1a2332]"
          >
            Log in
          </Link>
          <a
            href="#waitlist"
            className="rounded-md bg-[#1a2332] px-4 py-2 text-sm font-medium text-white hover:bg-[#2a3342] transition-colors"
          >
            Join waitlist
          </a>
        </nav>
      </div>
    </header>
  );
}

function MarketingFooter() {
  return (
    <footer className="border-t bg-[#1a2332] text-white">
      <div className="container mx-auto px-4 py-10">
        <div className="flex flex-col gap-6 md:flex-row md:items-start md:justify-between">
          <div>
            <p className="text-lg font-bold">Varuflow</p>
            <p className="mt-1 text-sm text-gray-400 max-w-xs">
              Inventory and invoicing for Swedish wholesalers. Simple. Compliant. Fast.
            </p>
          </div>
          <div className="flex gap-8 text-sm text-gray-400">
            <div className="space-y-2">
              <p className="font-medium text-white text-xs uppercase tracking-wide">Product</p>
              <a href="#waitlist" className="block hover:text-white">Early access</a>
              <Link href="/auth/login" className="block hover:text-white">Log in</Link>
            </div>
            <div className="space-y-2">
              <p className="font-medium text-white text-xs uppercase tracking-wide">Legal</p>
              <p className="text-gray-500">GDPR-compliant</p>
              <p className="text-gray-500">EU data residency</p>
            </div>
          </div>
        </div>
        <div className="mt-8 border-t border-white/10 pt-6 flex flex-col sm:flex-row items-center justify-between gap-2 text-xs text-gray-500">
          <p>&copy; {new Date().getFullYear()} Varuflow. Made for Swedish wholesalers.</p>
          <p>Swedish VAT ready · Bokföringslagen compliant</p>
        </div>
      </div>
    </footer>
  );
}
