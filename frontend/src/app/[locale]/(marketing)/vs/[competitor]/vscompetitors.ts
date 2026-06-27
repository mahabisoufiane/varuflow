// English-market competitor comparison data — separate from the Swedish /jämför/ pages.

export type VsSlug = "fortnox" | "odoo" | "visma" | "bokio";

export const VS_SLUGS: VsSlug[] = ["fortnox", "odoo", "visma", "bokio"];

export interface VsRow {
  feature: string;
  varuflow: string;
  competitor: string;
}

export interface VsData {
  slug: VsSlug;
  metaTitle: string;
  metaDescription: string;
  headline: string;
  angle: string;
  tagline: string;
  rows: VsRow[];
  customerQuote: {
    quote: string;
    author: string;
    company: string;
    initials: string;
  };
  migrationCta: string;
}

const y = "Yes";
const n = "No";

export const VS_COMPETITORS: VsData[] = [
  {
    slug: "fortnox",
    metaTitle: "Varuflow vs Fortnox — The Better Alternative for Wholesalers",
    metaDescription:
      "Fortnox is great for accounting. Varuflow adds real inventory, B2B portal, and demand forecasting. Compare features and pricing.",
    headline: "Why Varuflow over Fortnox?",
    angle: "feature comparison",
    tagline:
      "Fortnox is Sweden's leading accounting platform — but it was never designed for wholesalers who need live inventory, B2B portals, and demand forecasting.",
    rows: [
      { feature: "Real-time inventory", varuflow: y, competitor: "Limited (add-on)" },
      { feature: "Swedish VAT (25/12/6%)", varuflow: y, competitor: y },
      { feature: "B2B customer portal", varuflow: y, competitor: n },
      { feature: "Demand forecasting (AI)", varuflow: y, competitor: n },
      { feature: "Mobile barcode scanning", varuflow: y, competitor: n },
      { feature: "Peppol e-invoicing", varuflow: y, competitor: y },
      { feature: "Automated dunning", varuflow: y, competitor: y },
      { feature: "Multi-warehouse", varuflow: y, competitor: "Paid add-on" },
      { feature: "POS terminal", varuflow: y, competitor: "Limited" },
      { feature: "Price from (SEK/month)", varuflow: "0", competitor: "249" },
    ],
    customerQuote: {
      quote:
        "We kept Fortnox for accounting and switched to Varuflow for everything else. Best decision we made — inventory, portal, forecasting all in one place.",
      author: "Helena Strand",
      company: "Strand Wholesale",
      initials: "HS",
    },
    migrationCta: "Migrating from Fortnox takes under 30 minutes. We handle the data import.",
  },
  {
    slug: "odoo",
    metaTitle: "Varuflow vs Odoo — Simpler Alternative with Full Wholesale Features",
    metaDescription:
      "Odoo is powerful but complex. Varuflow delivers the same inventory and invoicing features in a product your team can actually use. Compare.",
    headline: "Why Varuflow over Odoo?",
    angle: "complexity comparison",
    tagline:
      "Odoo covers every department in a large enterprise — which means 18-month implementations and €50,000 consulting fees for SMBs. Varuflow gives you the critical 20% in a day.",
    rows: [
      { feature: "Setup time", varuflow: "< 1 hour", competitor: "3–18 months" },
      { feature: "Per-user pricing", varuflow: n, competitor: y },
      { feature: "Real-time inventory", varuflow: y, competitor: y },
      { feature: "Swedish VAT compliance", varuflow: y, competitor: "Requires config" },
      { feature: "B2B customer portal", varuflow: y, competitor: "Paid module" },
      { feature: "Mobile POS (native)", varuflow: y, competitor: "Paid app" },
      { feature: "Consultant required", varuflow: n, competitor: y },
      { feature: "Free tier available", varuflow: y, competitor: n },
      { feature: "AI demand forecast", varuflow: y, competitor: "Enterprise only" },
      { feature: "Price from (USD/month)", varuflow: "0", competitor: "~$150+" },
    ],
    customerQuote: {
      quote:
        "We tried Odoo for six months and spent more time configuring it than selling. Varuflow was live in an afternoon.",
      author: "Marcus Lindgren",
      company: "Linco Distribution",
      initials: "ML",
    },
    migrationCta: "Switch from Odoo in one afternoon. No consultants, no lost data.",
  },
  {
    slug: "visma",
    metaTitle: "Varuflow vs Visma — Smarter Choice for Growing Nordic SMBs",
    metaDescription:
      "Visma eEkonomi is built for small service companies. Varuflow adds inventory, B2B, and forecasting without a price jump. Compare plans.",
    headline: "Why Varuflow over Visma?",
    angle: "pricing comparison",
    tagline:
      "Visma eEkonomi works well for small service businesses. But the moment you need inventory management, B2B invoicing, and a customer portal, you need Varuflow.",
    rows: [
      { feature: "Real-time inventory", varuflow: y, competitor: "Add-on" },
      { feature: "Swedish VAT", varuflow: y, competitor: y },
      { feature: "B2B customer portal", varuflow: y, competitor: n },
      { feature: "Automated dunning", varuflow: y, competitor: y },
      { feature: "Mobile POS", varuflow: y, competitor: n },
      { feature: "Demand forecasting", varuflow: y, competitor: n },
      { feature: "Fortnox integration", varuflow: y, competitor: n },
      { feature: "Free tier", varuflow: y, competitor: n },
      { feature: "Price from (SEK/month)", varuflow: "0", competitor: "199" },
      { feature: "Contract required", varuflow: n, competitor: "Monthly / Annual" },
    ],
    customerQuote: {
      quote:
        "Visma couldn't handle our inventory. Varuflow does everything Visma did — and adds real stock management at a better price.",
      author: "Petra Holm",
      company: "Holm Trading",
      initials: "PH",
    },
    migrationCta: "Import your Visma customer and product data in minutes.",
  },
  {
    slug: "bokio",
    metaTitle: "Varuflow vs Bokio — The Growth-Ready Alternative",
    metaDescription:
      "Bokio is great for micro-businesses. When you're ready to grow — add inventory, B2B clients, and a portal — Varuflow is the natural next step.",
    headline: "Why Varuflow over Bokio?",
    angle: "growth angle",
    tagline:
      "Bokio is the best free accounting tool for one-person companies. But when orders, inventory, and B2B customers enter the picture, Varuflow is the natural upgrade.",
    rows: [
      { feature: "Inventory management", varuflow: y, competitor: n },
      { feature: "B2B customer portal", varuflow: y, competitor: n },
      { feature: "POS terminal", varuflow: y, competitor: n },
      { feature: "Swedish VAT invoicing", varuflow: y, competitor: y },
      { feature: "Automated reminders", varuflow: y, competitor: "Basic" },
      { feature: "Mobile app (iOS/Android)", varuflow: y, competitor: "Limited" },
      { feature: "Demand forecasting", varuflow: y, competitor: n },
      { feature: "Multi-user (free)", varuflow: "3 users free", competitor: "1 user" },
      { feature: "Free tier", varuflow: y, competitor: y },
      { feature: "Upgradeable as you grow", varuflow: y, competitor: n },
    ],
    customerQuote: {
      quote:
        "Bokio got us started. The moment we hired staff and needed inventory, Varuflow was the obvious upgrade.",
      author: "Daniel Johansson",
      company: "Johansson Parts AB",
      initials: "DJ",
    },
    migrationCta: "Growing past Bokio? Import your data and be live in an afternoon.",
  },
];

export function getVsData(slug: string): VsData | undefined {
  return VS_COMPETITORS.find((c) => c.slug === slug);
}
