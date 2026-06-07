import type { Metadata } from "next";
import "../globals.css";
import Link from "next/link";
import { PortalNav } from "./PortalNav";

export const metadata: Metadata = {
  title: "Customer Portal — Varuflow",
  description: "Place orders and manage your account",
};

export default function PortalLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="min-h-screen bg-gray-50 antialiased">
        <header className="border-b bg-white sticky top-0 z-40">
          <div className="mx-auto max-w-4xl px-4 py-3 flex items-center gap-3">
            <Link href="/portal" className="flex items-center gap-2">
              <div className="h-7 w-7 rounded-lg bg-[#1a2332] flex items-center justify-center">
                <span className="text-white text-xs font-bold">V</span>
              </div>
              <span className="font-semibold text-[#1a2332] hidden sm:inline">Varuflow</span>
            </Link>
            <PortalNav />
          </div>
        </header>
        <main className="mx-auto max-w-4xl px-4 py-6">{children}</main>
      </body>
    </html>
  );
}
