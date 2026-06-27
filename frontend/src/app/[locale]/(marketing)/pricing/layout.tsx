import type { Metadata } from "next";

const BASE = process.env.NEXT_PUBLIC_SITE_URL ?? "https://varuflow.vercel.app";

export const metadata: Metadata = {
  title: "Pricing — Varuflow",
  description:
    "Simple, transparent pricing for inventory, invoicing, and POS. Start free. No credit card required. Upgrade as you grow.",
  alternates: { canonical: `${BASE}/en/pricing` },
  openGraph: {
    title: "Pricing — Varuflow",
    description:
      "Simple, transparent pricing for inventory, invoicing, and POS. Start free. No credit card required.",
    type: "website",
    url: `${BASE}/en/pricing`,
  },
  twitter: {
    card: "summary_large_image",
    title: "Pricing — Varuflow",
    description: "Simple, transparent pricing. Start free, no credit card required.",
  },
};

export default function PricingLayout({ children }: { children: React.ReactNode }) {
  return children;
}
