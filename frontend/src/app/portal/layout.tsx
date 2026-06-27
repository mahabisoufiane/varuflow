import type { Metadata } from "next";
import "../globals.css";
import Link from "next/link";

export const metadata: Metadata = {
  title: "Customer Portal — Varuflow",
  description: "View and pay your invoices",
};

export default function PortalLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="min-h-screen bg-gray-50 antialiased">
        <header className="border-b bg-white">
          <div className="mx-auto max-w-3xl px-4 py-4 flex items-center gap-2">
            <div className="h-6 w-6 rounded bg-[#1a2332]" />
            <span className="font-semibold text-[#1a2332]">Varuflow</span>
            <span className="ml-2 text-xs text-muted-foreground rounded px-1.5 py-0.5 bg-gray-100">
              Customer Portal
            </span>
            <nav className="ml-auto flex gap-4 text-sm">
              <Link href="/portal/invoices" className="text-gray-600 hover:text-gray-900">Invoices</Link>
              <Link href="/portal/deposits" className="text-gray-600 hover:text-gray-900">Deposits</Link>
              <Link href="/portal/orders" className="text-gray-600 hover:text-gray-900">Orders</Link>
              <Link href="/portal/quotes" className="text-gray-600 hover:text-gray-900">Quotes</Link>
              <Link href="/portal/timeline" className="text-gray-600 hover:text-gray-900">Timeline</Link>
              <Link href="/portal/bookings" className="text-gray-600 hover:text-gray-900">Bookings</Link>
              <Link href="/portal/loyalty" className="text-gray-600 hover:text-gray-900">Loyalty</Link>
              <Link href="/portal/statements" className="text-gray-600 hover:text-gray-900">Statements</Link>
              <Link href="/portal/tickets" className="text-gray-600 hover:text-gray-900">Support</Link>
              <Link href="/portal/contracts" className="text-gray-600 hover:text-gray-900">Contracts</Link>
              <Link href="/portal/returns" className="text-gray-600 hover:text-gray-900">Returns</Link>
              <Link href="/portal/warranties" className="text-gray-600 hover:text-gray-900">Warranty</Link>
              <Link href="/portal/suggestions" className="text-gray-600 hover:text-gray-900">For You</Link>
              <Link href="/portal/chat" className="text-gray-600 hover:text-gray-900">Chat</Link>
              <Link href="/portal/credit-notes" className="text-gray-600 hover:text-gray-900">Credit Notes</Link>
              <Link href="/portal/notification-preferences" className="text-gray-600 hover:text-gray-900">Notifications</Link>
              <Link href="/portal/profile" className="text-gray-600 hover:text-gray-900">Profile</Link>
            </nav>
          </div>
        </header>
        <main className="mx-auto max-w-3xl px-4 py-8">{children}</main>
      </body>
    </html>
  );
}
