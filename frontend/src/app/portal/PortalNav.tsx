"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState } from "react";
import { ShoppingBag, FileText, Package, MessageCircle, User, MoreHorizontal, X } from "lucide-react";

const PRIMARY_NAV = [
  { href: "/portal/catalogue", label: "Order", icon: ShoppingBag },
  { href: "/portal/orders", label: "My Orders", icon: Package },
  { href: "/portal/invoices", label: "Invoices", icon: FileText },
  { href: "/portal/tickets", label: "Support", icon: MessageCircle },
  { href: "/portal/profile", label: "Account", icon: User },
];

const MORE_NAV = [
  { href: "/portal/quotes", label: "Quotes" },
  { href: "/portal/statements", label: "Statements" },
  { href: "/portal/loyalty", label: "Loyalty" },
  { href: "/portal/bookings", label: "Bookings" },
  { href: "/portal/returns", label: "Returns" },
  { href: "/portal/chat", label: "Chat" },
  { href: "/portal/timeline", label: "Timeline" },
  { href: "/portal/contracts", label: "Contracts" },
  { href: "/portal/credit-notes", label: "Credit Notes" },
  { href: "/portal/notification-preferences", label: "Notifications" },
];

export function PortalNav() {
  const pathname = usePathname();
  const [moreOpen, setMoreOpen] = useState(false);

  return (
    <nav className="ml-auto flex items-center gap-1">
      {PRIMARY_NAV.map(({ href, label, icon: Icon }) => {
        const active = pathname === href || pathname.startsWith(href + "/");
        return (
          <Link
            key={href}
            href={href}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm font-medium transition-colors ${
              active
                ? "bg-[#1a2332] text-white"
                : "text-gray-600 hover:text-gray-900 hover:bg-gray-100"
            }`}
          >
            <Icon className="h-3.5 w-3.5" />
            <span className="hidden md:inline">{label}</span>
          </Link>
        );
      })}

      {/* More dropdown */}
      <div className="relative">
        <button
          onClick={() => setMoreOpen((v) => !v)}
          className="flex items-center gap-1 px-2.5 py-1.5 rounded-lg text-sm text-gray-500 hover:text-gray-900 hover:bg-gray-100 transition-colors"
        >
          <MoreHorizontal className="h-4 w-4" />
        </button>
        {moreOpen && (
          <>
            <div className="fixed inset-0 z-40" onClick={() => setMoreOpen(false)} />
            <div className="absolute right-0 top-full mt-1 z-50 w-48 rounded-xl border border-gray-200 bg-white shadow-lg py-1">
              <div className="flex items-center justify-between px-3 py-2 border-b border-gray-100">
                <span className="text-xs font-medium text-gray-400">More</span>
                <button onClick={() => setMoreOpen(false)} className="text-gray-400 hover:text-gray-600">
                  <X className="h-3.5 w-3.5" />
                </button>
              </div>
              {MORE_NAV.map(({ href, label }) => (
                <Link
                  key={href}
                  href={href}
                  onClick={() => setMoreOpen(false)}
                  className={`block px-3 py-2 text-sm transition-colors ${
                    pathname === href ? "text-[#1a2332] font-medium bg-gray-50" : "text-gray-600 hover:text-gray-900 hover:bg-gray-50"
                  }`}
                >
                  {label}
                </Link>
              ))}
            </div>
          </>
        )}
      </div>
    </nav>
  );
}
