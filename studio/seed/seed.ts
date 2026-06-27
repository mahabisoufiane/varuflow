// studio/seed/seed.ts
// Pushes the 10 cornerstone articles to Sanity Cloud.
// Prerequisites:
//   1. Create a Sanity project at sanity.io/manage
//   2. Set SANITY_PROJECT_ID and SANITY_AUTH_TOKEN in studio/.env
//   3. Run: cd studio && npm run seed
//
// This script is idempotent — running it twice will update, not duplicate.

import { createClient } from "@sanity/client";
import * as dotenv from "dotenv";
import path from "path";
import { fileURLToPath } from "url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
dotenv.config({ path: path.join(__dirname, "../.env") });

const PROJECT_ID = process.env.SANITY_PROJECT_ID;
const DATASET = process.env.SANITY_DATASET ?? "production";
const TOKEN = process.env.SANITY_AUTH_TOKEN;

if (!PROJECT_ID || !TOKEN) {
  console.error("❌  SANITY_PROJECT_ID and SANITY_AUTH_TOKEN must be set in studio/.env");
  console.error("    Get your token from: https://sanity.io/manage → API → Tokens");
  process.exit(1);
}

const client = createClient({
  projectId: PROJECT_ID,
  dataset: DATASET,
  apiVersion: "2024-01-01",
  token: TOKEN,
  useCdn: false,
});

// ── Authors ──────────────────────────────────────────────────────────────────

const authors = [
  {
    _id: "author-sara-lindqvist",
    _type: "author",
    name: "Sara Lindqvist",
    role: "Compliance Lead, Varuflow",
    bio: "Sara writes about Nordic accounting law, e-invoicing standards, and GDPR compliance for wholesale businesses. Previously worked as an accountant specialising in Swedish SMEs.",
    initials: "SL",
  },
  {
    _id: "author-marcus-berg",
    _type: "author",
    name: "Marcus Berg",
    role: "Co-founder & CEO, Varuflow",
    bio: "Marcus co-founded Varuflow after spending 8 years in wholesale distribution. He writes about founder learnings, product strategy, and the future of B2B commerce tools.",
    initials: "MB",
  },
  {
    _id: "author-alex-chen",
    _type: "author",
    name: "Alex Chen",
    role: "Product Manager, Varuflow",
    bio: "Alex owns the core inventory and invoicing product at Varuflow. Writes about product decisions, workflow optimisation, and software comparisons for operators.",
    initials: "AC",
  },
];

// ── Categories ───────────────────────────────────────────────────────────────

const categories = [
  { _id: "cat-compliance", _type: "category", slug: "compliance", title: "Compliance", description: "Swedish, Nordic, and EU compliance guides for wholesalers and SMEs." },
  { _id: "cat-comparison", _type: "category", slug: "comparison", title: "Comparison", description: "Side-by-side comparisons of business software tools." },
  { _id: "cat-vertical", _type: "category", slug: "vertical", title: "Industry", description: "Guides and case studies for specific industry vertical use cases." },
  { _id: "cat-product-update", _type: "category", slug: "product-update", title: "Product updates", description: "Varuflow feature releases and platform improvements." },
  { _id: "cat-founder-story", _type: "category", slug: "founder-story", title: "Founder story", description: "Behind-the-scenes stories from the Varuflow founding team." },
  { _id: "cat-customer-story", _type: "category", slug: "customer-story", title: "Customer story", description: "How Varuflow customers run their businesses." },
];

// ── Posts — minimal seed for Sanity ─────────────────────────────────────────
// These are lightweight Sanity documents that point to the front-end seed data.
// For full content, edit the PortableText body in Sanity Studio or import
// the extended articles from articles-1-5.ts / articles-6-10.ts.

const posts = [
  {
    _id: "post-bokforingslagen",
    _type: "post",
    title: "Swedish Bookkeeping Law: A Practical Guide for Wholesalers",
    slug: { _type: "slug", current: "swedish-bookkeeping-law-guide" },
    locale: "en",
    category: { _type: "reference", _ref: "cat-compliance" },
    author: { _type: "reference", _ref: "author-sara-lindqvist" },
    publishedAt: "2025-09-01T09:00:00Z",
    updatedAt: "2026-03-15T09:00:00Z",
    excerpt: "Bokföringslagen (the Swedish Bookkeeping Act) sets the rules for how businesses must record, store, and present financial transactions. Here is what wholesale operators actually need to know.",
    seoTitle: "Swedish Bookkeeping Law Guide for Wholesalers",
    seoDescription: "Practical guide to Bokföringslagen for Nordic wholesale businesses — retention periods, digital records, and common compliance mistakes to avoid.",
    tags: ["Bokföringslagen", "Swedish accounting", "compliance", "invoicing"],
    readingTimeMinutes: 9,
    leadMagnet: {
      title: "Swedish Bookkeeping Compliance Checklist",
      description: "A one-page checklist covering record retention, digital archiving, and year-end obligations under Bokföringslagen.",
      pdfSlug: "swedish-bookkeeping-checklist",
      buttonLabel: "Download free checklist",
    },
  },
  {
    _id: "post-zatca",
    _type: "post",
    title: "ZATCA Phase 2 E-Invoicing: What Nordic Exporters Need to Know",
    slug: { _type: "slug", current: "zatca-phase-2-compliance-guide" },
    locale: "en",
    category: { _type: "reference", _ref: "cat-compliance" },
    author: { _type: "reference", _ref: "author-sara-lindqvist" },
    publishedAt: "2025-10-01T09:00:00Z",
    updatedAt: "2026-01-10T09:00:00Z",
    excerpt: "Saudi Arabia's ZATCA Phase 2 e-invoicing mandate affects every business that invoices Saudi customers. This guide covers the technical requirements, timelines, and how to stay compliant.",
    seoTitle: "ZATCA Phase 2 E-Invoicing Guide 2025",
    seoDescription: "Complete guide to ZATCA Phase 2 e-invoicing requirements for businesses selling to Saudi Arabia — technical specs, timelines, and compliance steps.",
    tags: ["ZATCA", "e-invoicing", "Saudi Arabia", "compliance"],
    readingTimeMinutes: 11,
    leadMagnet: {
      title: "ZATCA Phase 2 Compliance Checklist",
      description: "Step-by-step checklist to verify your invoicing system meets all ZATCA Phase 2 technical and procedural requirements.",
      pdfSlug: "zatca-phase-2-checklist",
      buttonLabel: "Download ZATCA checklist",
    },
  },
  {
    _id: "post-peppol",
    _type: "post",
    title: "Peppol BIS 3.0: The Complete Nordic E-Invoicing Standard Explained",
    slug: { _type: "slug", current: "peppol-bis-3-e-invoicing" },
    locale: "en",
    category: { _type: "reference", _ref: "cat-compliance" },
    author: { _type: "reference", _ref: "author-sara-lindqvist" },
    publishedAt: "2025-10-15T09:00:00Z",
    updatedAt: "2026-02-01T09:00:00Z",
    excerpt: "Peppol BIS 3.0 is the pan-European e-invoicing format used across Nordic public procurement. If you invoice government entities in Sweden, Norway, Denmark, or Finland, this guide explains what you need.",
    seoTitle: "Peppol BIS 3.0 E-Invoicing Guide for Nordic Businesses",
    seoDescription: "Everything Nordic wholesale businesses need to know about Peppol BIS 3.0 — format, access points, mandatory fields, and how to become compliant.",
    tags: ["Peppol", "e-invoicing", "BIS 3.0", "Nordic", "compliance"],
    readingTimeMinutes: 10,
  },
  {
    _id: "post-gdpr-retention",
    _type: "post",
    title: "GDPR Data Retention for Invoice Records: What You Must Keep (and Delete)",
    slug: { _type: "slug", current: "gdpr-data-retention-invoices" },
    locale: "en",
    category: { _type: "reference", _ref: "cat-compliance" },
    author: { _type: "reference", _ref: "author-sara-lindqvist" },
    publishedAt: "2025-11-01T09:00:00Z",
    updatedAt: "2026-01-20T09:00:00Z",
    excerpt: "GDPR requires you to delete personal data when you no longer need it. Bokföringslagen requires you to keep financial records for 7 years. How do you reconcile that conflict for your invoice archive?",
    seoTitle: "GDPR Data Retention for Invoices — What to Keep",
    seoDescription: "How to balance GDPR right-to-erasure with Bokföringslagen 7-year retention for invoice records. Practical guidance for Nordic wholesale businesses.",
    tags: ["GDPR", "data retention", "invoicing", "compliance", "privacy"],
    readingTimeMinutes: 8,
    leadMagnet: {
      title: "GDPR + Bokföringslagen Retention Schedule",
      description: "A document category + retention period table covering all record types a wholesale business holds, showing which law governs and when deletion is permitted.",
      pdfSlug: "gdpr-retention-schedule",
      buttonLabel: "Download retention schedule",
    },
  },
  {
    _id: "post-varuflow-vs-fortnox",
    _type: "post",
    title: "Varuflow vs Fortnox: Which Is Right for Your Wholesale Business?",
    slug: { _type: "slug", current: "varuflow-vs-fortnox" },
    locale: "en",
    category: { _type: "reference", _ref: "cat-comparison" },
    author: { _type: "reference", _ref: "author-alex-chen" },
    publishedAt: "2025-11-15T09:00:00Z",
    updatedAt: "2026-04-10T09:00:00Z",
    excerpt: "Fortnox is Sweden's most popular accounting tool. Varuflow is purpose-built for wholesale operators who need inventory control and B2B invoicing in one place. Here is an honest head-to-head.",
    seoTitle: "Varuflow vs Fortnox 2025 — Wholesale Business Comparison",
    seoDescription: "Honest comparison of Varuflow vs Fortnox for Nordic wholesale businesses. Pricing, features, inventory management, and e-invoicing compliance compared.",
    tags: ["Fortnox", "comparison", "invoicing software", "inventory", "Sweden"],
    readingTimeMinutes: 12,
  },
  {
    _id: "post-fortnox-alternativ",
    _type: "post",
    title: "5 Fortnox-alternativ för grossister 2025",
    slug: { _type: "slug", current: "fortnox-alternativ" },
    locale: "sv",
    translationSlug: "varuflow-vs-fortnox",
    category: { _type: "reference", _ref: "cat-comparison" },
    author: { _type: "reference", _ref: "author-alex-chen" },
    publishedAt: "2025-11-20T09:00:00Z",
    updatedAt: "2026-04-10T09:00:00Z",
    excerpt: "Fortnox passar bra för redovisningsbyråer, men grossister behöver mer: lagerhantering, inköpsordrar, B2B-fakturering och Peppol-support. Här är de 5 bästa alternativen.",
    seoTitle: "Fortnox-alternativ 2025 — Bäst för grossister",
    seoDescription: "Vi jämför de 5 bästa Fortnox-alternativen för svenska grossister. Lagerhantering, fakturering och SE-compliance jämförs sida vid sida.",
    tags: ["Fortnox alternativ", "grossist", "lagersystem", "fakturering"],
    readingTimeMinutes: 10,
  },
  {
    _id: "post-odoo-alternatives",
    _type: "post",
    title: "Odoo Alternatives for Small Wholesalers: Simpler Tools That Actually Fit",
    slug: { _type: "slug", current: "odoo-alternatives-wholesale" },
    locale: "en",
    category: { _type: "reference", _ref: "cat-comparison" },
    author: { _type: "reference", _ref: "author-alex-chen" },
    publishedAt: "2025-12-01T09:00:00Z",
    updatedAt: "2026-03-05T09:00:00Z",
    excerpt: "Odoo is powerful but notoriously complex to implement for small wholesale teams. We look at 5 Odoo alternatives that deliver inventory + invoicing without the 6-month configuration project.",
    seoTitle: "Odoo Alternatives for Small Wholesalers 2025",
    seoDescription: "5 simpler alternatives to Odoo for small wholesale businesses needing inventory management and B2B invoicing without the complexity overhead.",
    tags: ["Odoo alternatives", "wholesale software", "inventory", "comparison"],
    readingTimeMinutes: 11,
  },
  {
    _id: "post-salon-inventory",
    _type: "post",
    title: "Salon Inventory Management: The No-Spreadsheet Guide for 2025",
    slug: { _type: "slug", current: "salon-inventory-management" },
    locale: "en",
    category: { _type: "reference", _ref: "cat-vertical" },
    author: { _type: "reference", _ref: "author-alex-chen" },
    publishedAt: "2025-12-10T09:00:00Z",
    updatedAt: "2026-02-20T09:00:00Z",
    excerpt: "Most salon owners track stock in a spreadsheet or don't track it at all — until they run out of their best-selling product mid-appointment. Here is how to set up lean inventory management for a salon or beauty studio.",
    seoTitle: "Salon Inventory Management Guide 2025",
    seoDescription: "How to manage product inventory for salons and beauty studios — stock counts, reorder points, supplier ordering, and the tools that make it simple.",
    tags: ["salon inventory", "beauty business", "stock management", "vertical"],
    readingTimeMinutes: 8,
  },
  {
    _id: "post-multi-warehouse",
    _type: "post",
    title: "Multi-Warehouse Inventory: How to Scale Without Losing Control",
    slug: { _type: "slug", current: "multi-warehouse-inventory" },
    locale: "en",
    category: { _type: "reference", _ref: "cat-vertical" },
    author: { _type: "reference", _ref: "author-alex-chen" },
    publishedAt: "2026-01-10T09:00:00Z",
    updatedAt: "2026-04-15T09:00:00Z",
    excerpt: "Running stock across two or more locations exponentially increases the complexity of inventory management. This guide covers the systems, processes, and software features that keep multi-site operations under control.",
    seoTitle: "Multi-Warehouse Inventory Management Guide",
    seoDescription: "How to manage inventory across multiple warehouse locations — split stock, inter-warehouse transfers, location-specific reorder points, and the right software.",
    tags: ["multi-warehouse", "inventory management", "logistics", "wholesale"],
    readingTimeMinutes: 13,
    leadMagnet: {
      title: "Multi-Warehouse Setup Checklist",
      description: "A step-by-step checklist for setting up multi-location inventory management — from location codes to transfer workflows and reporting.",
      pdfSlug: "multi-warehouse-checklist",
      buttonLabel: "Download setup checklist",
    },
  },
  {
    _id: "post-building-varuflow",
    _type: "post",
    title: "Why We Built Varuflow: The Problem No One Was Solving for Nordic Wholesalers",
    slug: { _type: "slug", current: "building-varuflow" },
    locale: "en",
    category: { _type: "reference", _ref: "cat-founder-story" },
    author: { _type: "reference", _ref: "author-marcus-berg" },
    publishedAt: "2026-02-01T09:00:00Z",
    updatedAt: "2026-04-20T09:00:00Z",
    excerpt: "After 8 years in wholesale distribution, I kept hitting the same wall: accounting tools built for accountants, ERP systems that cost as much as a new hire, and nothing in between. This is why we built Varuflow.",
    seoTitle: "Why We Built Varuflow — Founder Story",
    seoDescription: "The story behind Varuflow — why a former wholesale operator built a compliance-first inventory and invoicing tool for Nordic SMEs.",
    tags: ["founder story", "startup", "wholesale", "product philosophy"],
    readingTimeMinutes: 7,
  },
];

// ── Main ─────────────────────────────────────────────────────────────────────

async function seed() {
  console.log(`\n🌱  Seeding Sanity project ${PROJECT_ID} / dataset ${DATASET}\n`);

  const transaction = client.transaction();

  for (const author of authors) {
    transaction.createOrReplace(author);
    console.log(`  ✓ author: ${author.name}`);
  }

  for (const category of categories) {
    transaction.createOrReplace(category);
    console.log(`  ✓ category: ${category.title}`);
  }

  for (const post of posts) {
    transaction.createOrReplace(post);
    console.log(`  ✓ post: ${post.slug.current}`);
  }

  try {
    await transaction.commit();
    console.log(`\n✅  Seeded ${authors.length} authors, ${categories.length} categories, ${posts.length} posts.\n`);
    console.log("Next steps:");
    console.log("  1. Open Sanity Studio: cd studio && npm run dev");
    console.log("  2. Add PortableText body to each post in the Studio editor");
    console.log("  3. Add NEXT_PUBLIC_SANITY_PROJECT_ID to Vercel env vars to go live");
    console.log(`     Project ID: ${PROJECT_ID}\n`);
  } catch (err) {
    console.error("❌  Transaction failed:", err);
    process.exit(1);
  }
}

seed();
