// Vertical landing page data — salons, retail, b2b-wholesale, restaurants

export type VerticalSlug = "salons" | "retail" | "b2b" | "restaurants";

export const VERTICAL_SLUGS: VerticalSlug[] = ["salons", "retail", "b2b", "restaurants"];

export interface VerticalFeature {
  title: string;
  description: string;
}

export interface VerticalTestimonial {
  quote: string;
  author: string;
  role: string;
  company: string;
  initials: string;
}

export interface VerticalData {
  slug: VerticalSlug;
  metaTitle: string;
  metaDescription: string;
  eyebrow: string;
  headline: string;
  subheadline: string;
  ctaLabel: string;
  demoVideoId?: string;
  features: VerticalFeature[];
  testimonials: VerticalTestimonial[];
}

export const VERTICALS: VerticalData[] = [
  {
    slug: "salons",
    metaTitle: "Varuflow for Salons & Spas — Booking, POS & Loyalty in One",
    metaDescription:
      "Run your salon on Varuflow: online booking, walk-in POS, staff commissions, loyalty points, and gift cards — all synced. Free to start.",
    eyebrow: "Built for beauty & wellness",
    headline: "The all-in-one platform salons actually use",
    subheadline:
      "Online booking, POS, staff management, loyalty rewards, and client history — no plug-ins, no integrations, one monthly price.",
    ctaLabel: "Start free for salons",
    features: [
      {
        title: "Online booking portal",
        description:
          "Let clients book services 24/7 through a branded portal. Automatic SMS and email reminders cut no-shows by up to 40%.",
      },
      {
        title: "Walk-in POS",
        description:
          "Accept card, cash, gift cards, or loyalty points at the counter. Works offline — syncs when back online.",
      },
      {
        title: "Staff commissions",
        description:
          "Set commission rules per service or staff member. Varuflow calculates and tracks payouts automatically.",
      },
      {
        title: "Client loyalty & gift cards",
        description:
          "Built-in loyalty points, birthday vouchers, and digital gift cards. No third-party app required.",
      },
      {
        title: "Inventory for salon products",
        description:
          "Track retail products, professional supplies, and consumables. Get reorder alerts before you run out.",
      },
      {
        title: "Automated invoicing",
        description:
          "B2B clients, corporate accounts, and insurance billing handled automatically with GDPR-compliant storage.",
      },
    ],
    testimonials: [
      {
        quote:
          "We replaced three separate tools with Varuflow. Bookings, POS, and inventory all in one — the team loves it.",
        author: "Sara Lindqvist",
        role: "Owner",
        company: "Sallys Salong, Göteborg",
        initials: "SL",
      },
      {
        quote:
          "Our no-show rate dropped from 25% to under 8% after we switched to automated reminders.",
        author: "Mia Bergström",
        role: "Manager",
        company: "Studio Glow, Stockholm",
        initials: "MB",
      },
    ],
  },
  {
    slug: "retail",
    metaTitle: "Varuflow for Retail — Mobile POS & Inventory Management",
    metaDescription:
      "Run your retail store with Varuflow: mobile POS, barcode scanning, real-time inventory, and e-commerce sync. 14-day free trial, no credit card required.",
    eyebrow: "Built for modern retail",
    headline: "Sell anywhere. Never lose track of stock.",
    subheadline:
      "Mobile POS that works on any device, barcode scanning, real-time inventory across all locations, and automatic reorder points.",
    ctaLabel: "Start free for retail",
    features: [
      {
        title: "Mobile POS on any device",
        description:
          "Turn any tablet or phone into a full POS terminal. Accept card via Stripe Reader or manual entry.",
      },
      {
        title: "Barcode scanning",
        description:
          "Scan product barcodes with your phone camera to add items to a sale or receive stock — no dedicated scanner needed.",
      },
      {
        title: "Multi-location inventory",
        description:
          "Track stock levels across every store in real time. Transfer stock between locations with a few taps.",
      },
      {
        title: "E-commerce sync",
        description:
          "Connect your Shopify or WooCommerce store. Orders sync automatically; inventory stays accurate everywhere.",
      },
      {
        title: "Automatic reorder alerts",
        description:
          "Set minimum stock levels per product. Get notified (and auto-generate purchase orders) before shelves go empty.",
      },
      {
        title: "Customer loyalty",
        description:
          "Built-in points program. Customers earn points on every purchase and redeem in-store or online.",
      },
    ],
    testimonials: [
      {
        quote:
          "The mobile POS was live in our store in under an hour. Inventory updates in real time — exactly what we needed.",
        author: "Johan Ek",
        role: "Store Manager",
        company: "Ek Sports & Outdoor",
        initials: "JE",
      },
    ],
  },
  {
    slug: "b2b",
    metaTitle: "Varuflow for B2B Wholesale — Invoicing, Portal & Inventory",
    metaDescription:
      "B2B wholesale platform: customer portal, bulk invoicing, credit terms, Peppol e-invoicing, and real-time inventory. GDPR-compliant. Free to start.",
    eyebrow: "Built for B2B wholesalers",
    headline: "Your B2B customers deserve a modern portal",
    subheadline:
      "Let customers place orders, track invoices, and see delivery status in a branded portal — while you manage inventory, credit terms, and e-invoicing from one dashboard.",
    ctaLabel: "Start free for wholesale",
    features: [
      {
        title: "Branded customer portal",
        description:
          "Give each B2B customer their own portal to place orders, view invoices, and track deliveries — white-labelled with your logo.",
      },
      {
        title: "Credit terms & custom pricing",
        description:
          "Set per-customer payment terms (NET 30, NET 60). Override prices per customer or customer group.",
      },
      {
        title: "Peppol & e-invoicing",
        description:
          "Send Peppol BIS 3.0 invoices automatically to Swedish public sector and enterprise buyers. ZATCA-compliant for KSA.",
      },
      {
        title: "Automated dunning",
        description:
          "Overdue invoices trigger a configurable reminder sequence — email on day 3, 7, 14, then final notice. No manual chasing.",
      },
      {
        title: "Purchase orders & receiving",
        description:
          "Create POs for suppliers, receive partial deliveries, and track landed costs — all reconciled with inventory.",
      },
      {
        title: "Demand forecasting",
        description:
          "AI-powered demand forecast per SKU based on 12 months of sales history. Cut overstock by up to 30%.",
      },
    ],
    testimonials: [
      {
        quote:
          "Our customers love the portal. Order errors dropped to near-zero once they could see live stock levels and place orders themselves.",
        author: "Erik Nilsson",
        role: "CEO",
        company: "Nordic Parts Distribution",
        initials: "EN",
      },
    ],
  },
  {
    slug: "restaurants",
    metaTitle: "Varuflow for Restaurants — POS, Booking & Inventory",
    metaDescription:
      "Restaurant management on Varuflow: table POS, online reservations, kitchen inventory tracking, and staff scheduling. Free to start.",
    eyebrow: "Built for restaurants & cafés",
    headline: "Front of house meets back of house",
    subheadline:
      "Table POS, online reservations, kitchen stock management, and supplier ordering — linked together so nothing slips through the cracks.",
    ctaLabel: "Start free for restaurants",
    features: [
      {
        title: "Table POS with splits",
        description:
          "Fast table-based POS with bill splitting, modifiers, and open tabs. Works on iPad or any touch device.",
      },
      {
        title: "Online reservations",
        description:
          "Bookings page on your website. Automatic confirmation and reminder messages — fully white-labelled.",
      },
      {
        title: "Kitchen stock tracking",
        description:
          "Track ingredient usage per dish. Get low-stock alerts before service and automated supplier reorders.",
      },
      {
        title: "Supplier invoices & costs",
        description:
          "Receive supplier invoices and match against POs. Track food cost % in real time across all categories.",
      },
      {
        title: "Staff rosters",
        description:
          "Build weekly rosters, track hours worked, and export timesheets for payroll — from the same dashboard.",
      },
      {
        title: "Loyalty & gift cards",
        description:
          "Regulars earn points on every visit. Digital gift cards your customers can buy and share directly.",
      },
    ],
    testimonials: [
      {
        quote:
          "We track food cost in real time now. I used to find out we were losing money after the fact — not anymore.",
        author: "Anna-Karin Svensson",
        role: "Owner",
        company: "Kafé Svensson, Malmö",
        initials: "AS",
      },
    ],
  },
];

export function getVertical(slug: string): VerticalData | undefined {
  return VERTICALS.find((v) => v.slug === slug);
}
