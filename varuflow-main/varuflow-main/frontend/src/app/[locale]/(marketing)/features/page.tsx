import type { Metadata } from "next";
import {
  Package,
  FileText,
  Users,
  BarChart3,
  Bot,
  Globe,
  ShieldCheck,
  Zap,
  Smartphone,
  Receipt,
  Warehouse,
  CreditCard,
  Layers,
  ClipboardList,
  CalendarDays,
  ScanBarcode,
} from "lucide-react";
import FeatureCard from "@/components/marketing/FeatureCard";
import CTABanner from "@/components/marketing/CTABanner";
import JsonLd, { softwareApplicationSchema } from "@/components/marketing/JsonLd";
import StatBar from "@/components/marketing/StatBar";

const BASE = process.env.NEXT_PUBLIC_SITE_URL ?? "https://varuflow.vercel.app";

export const metadata: Metadata = {
  title: "Features — Varuflow",
  description:
    "100+ features for Nordic wholesalers: inventory, invoicing, POS, AI, B2B portal, compliance, and more. See the full feature list.",
  openGraph: {
    title: "Varuflow Features — 100+ Tools for Wholesalers",
    description: "Inventory, invoicing, POS, AI, B2B portal, compliance — all in one platform.",
    type: "website",
    url: `${BASE}/en/features`,
  },
  twitter: { card: "summary_large_image", title: "Varuflow Features" },
  alternates: {
    canonical: `${BASE}/en/features`,
    languages: {
      en: `${BASE}/en/features`,
      sv: `${BASE}/sv/features`,
      ar: `${BASE}/ar/features`,
      "x-default": `${BASE}/en/features`,
    },
  },
};

const CATEGORIES = [
  {
    id: "inventory",
    title: "Inventory & Warehousing",
    icon: <Package className="h-5 w-5" />,
    features: [
      { icon: <Package className="h-5 w-5" />, title: "Real-time stock levels", description: "See live inventory across every warehouse. Low-stock alerts trigger automatically." },
      { icon: <ScanBarcode className="h-5 w-5" />, title: "Barcode scanning", description: "Use your phone camera to scan products in and out. No dedicated scanner needed." },
      { icon: <Warehouse className="h-5 w-5" />, title: "Multi-warehouse", description: "Manage multiple storage locations. Track stock transfers and in-transit inventory." },
      { icon: <ClipboardList className="h-5 w-5" />, title: "Stock counts", description: "Guided stocktake workflows. Variance reports reconcile with expected levels automatically." },
      { icon: <Layers className="h-5 w-5" />, title: "Bill of materials & kitting", description: "Define kit components. Assemble or disassemble kits and track component stock." },
      { icon: <BarChart3 className="h-5 w-5" />, title: "Demand forecasting (AI)", description: "12-month rolling forecast per SKU. Cut overstock by up to 30% with AI reorder suggestions.", badge: "Pro" },
    ],
  },
  {
    id: "invoicing",
    title: "Invoicing & Payments",
    icon: <FileText className="h-5 w-5" />,
    features: [
      { icon: <FileText className="h-5 w-5" />, title: "Professional invoices", description: "Branded PDF invoices with correct VAT treatment (25/12/6%). Email or print instantly." },
      { icon: <Receipt className="h-5 w-5" />, title: "Recurring invoices", description: "Schedule monthly, quarterly, or annual invoices. Auto-send on the right day." },
      { icon: <Globe className="h-5 w-5" />, title: "Peppol e-invoicing", description: "Send Peppol BIS 3.0 invoices to public sector and enterprise buyers. ZATCA included.", badge: "Pro" },
      { icon: <CreditCard className="h-5 w-5" />, title: "Online payment links", description: "Add a pay-now link to every invoice. Customers pay by card — powered by Stripe." },
      { icon: <Zap className="h-5 w-5" />, title: "Automated dunning", description: "Overdue invoices trigger a configurable reminder sequence. Stop chasing manually.", badge: "Pro" },
      { icon: <FileText className="h-5 w-5" />, title: "Credit notes & quotes", description: "Issue credit notes against any invoice. Create quotes and convert to invoice in one click." },
    ],
  },
  {
    id: "portal",
    title: "B2B Customer Portal",
    icon: <Users className="h-5 w-5" />,
    features: [
      { icon: <Users className="h-5 w-5" />, title: "Branded self-service portal", description: "Customers log in to place orders, view invoices, download statements, and track deliveries.", badge: "Pro" },
      { icon: <CreditCard className="h-5 w-5" />, title: "Credit terms & custom pricing", description: "Set NET 30/60 and per-customer price overrides. Customers see their negotiated prices.", badge: "Pro" },
      { icon: <FileText className="h-5 w-5" />, title: "Portal e-signatures", description: "Send quotes for digital signature. Log acceptance with timestamp and IP.", badge: "Pro" },
      { icon: <Globe className="h-5 w-5" />, title: "Multi-language portal", description: "Portal renders in the customer's preferred language: English, Swedish, or Arabic.", badge: "Pro" },
    ],
  },
  {
    id: "ai",
    title: "AI & Automation",
    icon: <Bot className="h-5 w-5" />,
    features: [
      { icon: <Bot className="h-5 w-5" />, title: "AI action cards", description: "Your daily dashboard surfaces the 5 most important actions: overdue invoices, reorders, anomalies.", badge: "Pro" },
      { icon: <BarChart3 className="h-5 w-5" />, title: "Cash-flow forecast", description: "30-day cash-flow projection based on outstanding invoices and expected payments.", badge: "Pro" },
      { icon: <Zap className="h-5 w-5" />, title: "AI product descriptions", description: "Generate SEO-friendly product descriptions in EN, SV, or AR with one click.", badge: "Pro" },
      { icon: <Bot className="h-5 w-5" />, title: "Ask Varuflow (AI chat)", description: "Chat with your data: 'What were my top 10 products last quarter?' in plain language.", badge: "Pro" },
    ],
  },
  {
    id: "pos",
    title: "Point of Sale",
    icon: <Smartphone className="h-5 w-5" />,
    features: [
      { icon: <Smartphone className="h-5 w-5" />, title: "Mobile POS", description: "Turn any phone or tablet into a point-of-sale terminal. Works offline — syncs when back online." },
      { icon: <CreditCard className="h-5 w-5" />, title: "Stripe Terminal", description: "Accept tap-to-pay cards with a Stripe Reader. Reconciles automatically with inventory." },
      { icon: <CalendarDays className="h-5 w-5" />, title: "Booking & service POS", description: "Book appointments directly from the POS. Link services, staff, and products in one transaction." },
    ],
  },
  {
    id: "compliance",
    title: "Compliance & Security",
    icon: <ShieldCheck className="h-5 w-5" />,
    features: [
      { icon: <ShieldCheck className="h-5 w-5" />, title: "Bokföringslagen (SWE)", description: "SIE-file export, immutable audit log, and 7-year record retention. Swedish-law compliant." },
      { icon: <Globe className="h-5 w-5" />, title: "ZATCA Phase 1 & 2 (KSA)", description: "ZATCA-compliant e-invoicing with QR codes and Fatoorah integration for Saudi businesses.", badge: "Pro" },
      { icon: <ShieldCheck className="h-5 w-5" />, title: "GDPR & EU data residency", description: "Data stored in EU (Frankfurt). Full GDPR toolkit: data export, right-to-forget, consent log." },
      { icon: <ShieldCheck className="h-5 w-5" />, title: "SOC 2 (in progress)", description: "Type II audit in progress. Full audit log, MFA, IP allowlist, and encrypted-at-rest storage." },
    ],
  },
];

export default function FeaturesPage() {
  return (
    <>
      <JsonLd data={softwareApplicationSchema()} />

      {/* Hero */}
      <section className="px-4 pb-8 pt-20 text-center">
        <p className="mb-4 inline-block rounded-full border border-indigo-500/30 bg-indigo-500/10 px-4 py-1 text-xs font-semibold uppercase tracking-widest text-indigo-400">
          100+ features
        </p>
        <h1 className="vf-text-1 text-4xl font-extrabold tracking-tight sm:text-5xl">
          Everything your wholesale business needs
        </h1>
        <p className="vf-text-2 mx-auto mt-4 max-w-xl text-lg">
          From barcode scanning to AI demand forecasting — all in one platform, one price.
        </p>
        <div className="mt-6 flex justify-center gap-3">
          <a href="#inventory" className="vf-btn-ghost rounded-xl px-5 py-2 text-sm font-medium">Inventory</a>
          <a href="#invoicing" className="vf-btn-ghost rounded-xl px-5 py-2 text-sm font-medium">Invoicing</a>
          <a href="#ai" className="vf-btn-ghost rounded-xl px-5 py-2 text-sm font-medium">AI</a>
          <a href="#compliance" className="vf-btn-ghost rounded-xl px-5 py-2 text-sm font-medium">Compliance</a>
        </div>
      </section>

      <StatBar />

      {/* Feature categories */}
      {CATEGORIES.map((cat) => (
        <section key={cat.id} id={cat.id} className="px-4 py-16">
          <div className="mx-auto max-w-5xl">
            <div className="mb-8 flex items-center gap-3">
              <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-indigo-500/15 text-indigo-400">
                {cat.icon}
              </div>
              <h2 className="vf-text-1 text-2xl font-bold">{cat.title}</h2>
            </div>
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
              {cat.features.map((f) => (
                <FeatureCard key={f.title} icon={f.icon} title={f.title} description={f.description} badge={f.badge} />
              ))}
            </div>
          </div>
        </section>
      ))}

      <CTABanner
        headline="Ready to see it in action?"
        subheadline="14-day free Pro trial. No credit card. Start now."
        ctaPrimary={{ href: "/trial", label: "Start free trial" }}
        ctaSecondary={{ href: "/demo", label: "Book a demo" }}
      />
    </>
  );
}
