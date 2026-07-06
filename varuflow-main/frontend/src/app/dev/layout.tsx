// File: src/app/dev/layout.tsx
// Standalone route groups in this app provide their own <html>/<body> and
// import globals.css themselves (the root layout renders bare children; only
// the [locale] tree has a full document). Without this, /dev throws
// "Missing <html> and <body> tags" and renders unstyled.
import type { Metadata } from "next";
import "../globals.css";

export const metadata: Metadata = {
  title: "Dev Hub — Varuflow",
  description: "Local development hub: project info, service URLs, run commands",
  robots: { index: false, follow: false },
};

export default function DevLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="min-h-screen bg-[var(--vf-bg-primary)] antialiased">
        {children}
      </body>
    </html>
  );
}
