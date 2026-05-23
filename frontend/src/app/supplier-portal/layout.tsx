import type { Metadata } from "next";
import "../globals.css";

export const metadata: Metadata = {
  title: "Supplier Portal — Varuflow",
  description: "Review and confirm purchase orders",
};

export default function SupplierPortalLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="min-h-screen bg-gray-50 antialiased">
        <header className="border-b bg-white">
          <div className="mx-auto max-w-3xl px-4 py-4 flex items-center gap-2">
            <div className="h-6 w-6 rounded bg-[#1a2332]" />
            <span className="font-semibold text-[#1a2332]">Varuflow</span>
            <span className="ml-2 text-xs text-muted-foreground rounded px-1.5 py-0.5 bg-gray-100">
              Supplier Portal
            </span>
          </div>
        </header>
        <main className="mx-auto max-w-3xl px-4 py-8">{children}</main>
      </body>
    </html>
  );
}
