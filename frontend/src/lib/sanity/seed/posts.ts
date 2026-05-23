// frontend/src/lib/sanity/seed/posts.ts
// Seed data for the 10 cornerstone blog articles.
// Used as fallback when NEXT_PUBLIC_SANITY_PROJECT_ID is not set.
// Run `cd studio && npm run seed` to push full-length versions to Sanity.

export type ArticleCategory =
  | "compliance"
  | "comparison"
  | "vertical"
  | "product-update"
  | "founder-story"
  | "customer-story";

export type ArticleLocale = "en" | "sv" | "ar";

export interface SeedAuthor {
  name: string;
  role: string;
  bio: string;
  initials: string;
}

export interface LeadMagnet {
  title: string;
  description: string;
  pdfSlug: string;
  buttonLabel: string;
}

export interface TocItem {
  id: string;
  title: string;
  level: 2 | 3;
}

export interface SeedPost {
  _id: string;
  slug: string;
  title: string;
  excerpt: string;
  category: ArticleCategory;
  tags: string[];
  locale: ArticleLocale;
  translationSlug?: string;
  author: SeedAuthor;
  publishedAt: string;
  updatedAt: string;
  seoTitle: string;
  seoDescription: string;
  readingTimeMinutes: number;
  featuredImageAlt: string;
  leadMagnet?: LeadMagnet;
  tableOfContents: TocItem[];
  bodyHtml: string;
  internalLinks: Array<{ href: string; label: string }>;
  externalLinks: Array<{ href: string; label: string }>;
  cta: { headline: string; body: string; buttonLabel: string; href: string };
}

const SARA: SeedAuthor = {
  name: "Sara Lindqvist",
  role: "Compliance Lead",
  bio: "Former auditor at PwC Sweden with 8 years of Nordic SMB compliance experience. Specializes in Bokföringslagen, Peppol, and GDPR for SaaS companies.",
  initials: "SL",
};

const YOUSSEF: SeedAuthor = {
  name: "Youssef Benali",
  role: "CEO & Co-founder",
  bio: "Moroccan-Swedish entrepreneur. Built Varuflow after running a wholesale business frustrated by every available software tool. Specializes in ZATCA, FTA, and cross-regional compliance.",
  initials: "YB",
};

const ERIK: SeedAuthor = {
  name: "Erik Johansson",
  role: "Product Lead",
  bio: "10 years in B2B fintech. Built compliance tooling for 200+ Nordic SMBs. Focuses on product strategy and integrations.",
  initials: "EJ",
};

export const SEED_POSTS: SeedPost[] = [
  // ─── 1. Bokföringslagen Guide (EN) ──────────────────────────────────────────
  {
    _id: "bokfoeringlagen-guide-en",
    slug: "complete-guide-bokforinglagen-swedish-smbs",
    title: "Complete Guide to Bokföringslagen for Swedish SMBs",
    excerpt:
      "Everything Swedish small businesses need to know about Bokföringslagen — the 7-year retention rule, voucher requirements, digital records, and how to avoid penalties.",
    category: "compliance",
    tags: ["bokföringslagen", "swedish-accounting", "compliance", "SMB"],
    locale: "en",
    translationSlug: "komplett-guide-bokforingslagen-svenska-smab",
    author: SARA,
    publishedAt: "2026-04-15",
    updatedAt: "2026-04-15",
    seoTitle: "Bokföringslagen Explained: Complete Guide for Swedish SMBs (2026)",
    seoDescription:
      "Everything Swedish SMBs need to know about Bokföringslagen — 7-year retention, SIE format, audit trails, and how to stay compliant without drowning in admin.",
    readingTimeMinutes: 10,
    featuredImageAlt: "Swedish accounting law document with Varuflow dashboard",
    leadMagnet: {
      title: "Bokföringslagen Compliance Checklist",
      description: "A free 23-point checklist covering every requirement of Swedish accounting law.",
      pdfSlug: "bokforingslagen-checklist",
      buttonLabel: "Download free checklist",
    },
    tableOfContents: [
      { id: "what-is-bokforingslagen", title: "What is Bokföringslagen?", level: 2 },
      { id: "who-must-comply", title: "Who must comply?", level: 2 },
      { id: "7-year-retention", title: "The 7-year retention requirement", level: 2 },
      { id: "vouchers-and-records", title: "Vouchers and accounting records", level: 2 },
      { id: "digital-records", title: "Digital records and SIE format", level: 2 },
      { id: "corrections", title: "How to handle corrections", level: 2 },
      { id: "vat-requirements", title: "VAT record requirements", level: 2 },
      { id: "penalties", title: "Penalties for non-compliance", level: 2 },
      { id: "software-helps", title: "How software makes compliance automatic", level: 2 },
      { id: "faq", title: "Frequently asked questions", level: 2 },
    ],
    internalLinks: [
      { href: "/en/compliance", label: "Varuflow Compliance Features" },
      { href: "/en/regions/se", label: "Varuflow for Sweden" },
      { href: "/en/pricing", label: "Varuflow Pricing" },
    ],
    externalLinks: [
      {
        href: "https://www.riksdagen.se/sv/dokument-och-lagar/dokument/svensk-forfattningssamling/bokforingslag-19991078_sfs-1999-1078/",
        label: "Bokföringslagen (SFS 1999:1078)",
      },
      {
        href: "https://www.skatteverket.se/foretagochorganisationer/bokforingochredovisning.4.18e1b10334ebe8bc80001022.html",
        label: "Skatteverket: Bokföring och redovisning",
      },
    ],
    cta: {
      headline: "Stay compliant without the admin burden",
      body: "Varuflow handles Bokföringslagen automatically — SIE export, 7-year archives, audit trails, all included.",
      buttonLabel: "Start 14-day free trial",
      href: "/en/trial",
    },
    bodyHtml: `
<h2 id="what-is-bokforingslagen">What is Bokföringslagen?</h2>
<p>Bokföringslagen (SFS 1999:1078) is Sweden's primary accounting law, governing how businesses must maintain their financial records. It applies to all Swedish legal entities — sole traders (<em>enskild firma</em>), limited companies (<em>aktiebolag</em>), trading partnerships, and associations — that carry on business activity.</p>
<p>The law is enforced by Skatteverket (the Swedish Tax Agency) and Bolagsverket (the Companies Registration Office). Non-compliance can result in criminal charges and significant fines under the Swedish Penal Code.</p>
<p>Unlike many accounting standards, Bokföringslagen is not about <em>how</em> you calculate your profits — that's handled by Årsredovisningslagen (ÅRL) and K-regulations. Bokföringslagen is about <em>how</em> you keep and store your records so they can be audited at any time.</p>

<h2 id="who-must-comply">Who must comply?</h2>
<p>Every Swedish business that meets any of these criteria must follow Bokföringslagen:</p>
<ul>
  <li>Registered as an <em>aktiebolag</em>, <em>handelsbolag</em>, or <em>kommanditbolag</em></li>
  <li>Annual net revenue exceeding 3 price base amounts (approx. 159,000 SEK in 2026)</li>
  <li>Any business with employees</li>
  <li>Associations and foundations that carry out business activities</li>
</ul>
<p>Foreign companies with a permanent establishment in Sweden also fall under Bokföringslagen for their Swedish operations.</p>

<h2 id="7-year-retention">The 7-year retention requirement</h2>
<p>The most practically important rule in Bokföringslagen is the <strong>seven-year retention period</strong>. All accounting material — vouchers (<em>verifikationer</em>), ledgers, annual reports, and supporting documentation — must be kept for seven years from the end of the fiscal year in which the transaction occurred.</p>
<blockquote>
  <strong>Example:</strong> A transaction on 15 March 2023 (fiscal year 2023) must be retained until at least 31 December 2030.
</blockquote>
<p>This creates a common pitfall for businesses that switch software systems: the old records must remain accessible even if you change providers. A SaaS provider that deletes your data when you cancel is non-compliant with Swedish law.</p>
<p>Varuflow keeps all your records in an immutable archive for the full seven years, even if you downgrade or cancel. <a href="/en/compliance">Learn more about Varuflow's compliance guarantees.</a></p>

<h2 id="vouchers-and-records">Vouchers and accounting records</h2>
<p>A <em>verifikation</em> (voucher) is any document that supports a recorded accounting transaction. This includes:</p>
<ul>
  <li>Supplier invoices and purchase receipts</li>
  <li>Sales invoices issued to customers</li>
  <li>Bank statements and payment confirmations</li>
  <li>Payroll records and salary slips</li>
  <li>Customs documents for imports/exports</li>
</ul>
<p>Each voucher must contain: the date of the transaction, the amount and currency, the counterparty (supplier or customer), a description of the goods or services, and a sequential voucher number that links to the general ledger.</p>
<p>Bokföringslagen 5 kap. 6§ requires that transactions be recorded promptly — in practice, this means all transactions from the preceding month must be booked no later than the 15th of the following month.</p>

<h2 id="digital-records">Digital records and SIE format</h2>
<p>Since 2004, Skatteverket has accepted fully digital records. Physical paper is no longer required, provided the digital records satisfy three conditions:</p>
<ol>
  <li><strong>Accessibility:</strong> Records must be presentable in a human-readable format within a reasonable timeframe if requested by an auditor.</li>
  <li><strong>Integrity:</strong> The system must ensure records cannot be altered retroactively without leaving a traceable audit log.</li>
  <li><strong>Exportability:</strong> The SIE format (Standard Import Export) must be supported for tax authority data exchange.</li>
</ol>
<p>SIE is a Swedish standard for exchanging accounting data between software systems. There are four SIE file types; most SMBs need SIE type 4 (transaction data) for tax audits. Varuflow exports SIE 4 files on demand from any date range.</p>

<h2 id="corrections">How to handle corrections</h2>
<p>Once a transaction is recorded in your general ledger, Swedish accounting law prohibits retroactive deletion or modification. If you make an error, the correct procedure is to create a <em>rättningsverifikation</em> (correction voucher) that reverses the original entry and records the correct amount.</p>
<p>This creates a permanent, auditable trail. Any software that lets you silently edit or delete posted transactions is out of compliance with Bokföringslagen — a common issue with spreadsheet-based systems and some older SMB accounting tools.</p>

<h2 id="vat-requirements">VAT record requirements</h2>
<p>If your business is registered for VAT (<em>momsregistrerat</em>), Bokföringslagen works alongside Mervärdesskattelagen (the VAT Act) to require:</p>
<ul>
  <li>Separate tracking of input VAT (purchases) and output VAT (sales)</li>
  <li>VAT registration number on all invoices above 3,000 SEK</li>
  <li>Reverse-charge documentation for intra-EU transactions</li>
  <li>Quarterly or monthly VAT returns filed via Skatteverket's e-service</li>
</ul>
<p>Varuflow automatically calculates and tracks Swedish VAT rates (25%, 12%, 6%, 0%) and generates VAT reports compatible with Skatteverket's e-service format.</p>

<h2 id="penalties">Penalties for non-compliance</h2>
<p>Failing to comply with Bokföringslagen is treated seriously in Sweden. Under Brottsbalken (the Swedish Penal Code), <em>bokföringsbrott</em> (accounting fraud) can result in:</p>
<ul>
  <li>Fines</li>
  <li>Imprisonment up to 2 years for gross violations</li>
  <li>Personal liability for company directors and owners</li>
</ul>
<p>Administrative penalties include tax surcharges, back-taxes, and interest. Practically, non-compliance most often surfaces during company liquidation, bankruptcy proceedings, or routine Skatteverket audits.</p>

<h2 id="software-helps">How software makes compliance automatic</h2>
<p>Modern cloud accounting tools handle most Bokföringslagen requirements automatically. When evaluating software, check for:</p>
<table>
  <thead>
    <tr><th>Requirement</th><th>What software should do</th><th>Varuflow</th></tr>
  </thead>
  <tbody>
    <tr><td>7-year retention</td><td>Guarantee data is kept even after cancellation</td><td>✓ Committed in ToS</td></tr>
    <tr><td>Immutable records</td><td>No silent edits; correction vouchers enforced</td><td>✓ Audit log on all mutations</td></tr>
    <tr><td>SIE 4 export</td><td>On-demand export of transaction data</td><td>✓ One-click export</td></tr>
    <tr><td>Sequential voucher numbers</td><td>Auto-generated, no gaps allowed</td><td>✓ Enforced in UI</td></tr>
    <tr><td>Digital signatures</td><td>Optional but recommended for larger organizations</td><td>✓ BankID support</td></tr>
  </tbody>
</table>
<p>See <a href="/en/features">Varuflow's full feature list</a> for a complete compliance overview.</p>

<h2 id="faq">Frequently asked questions</h2>
<h3>Can I use a foreign accounting system and still comply with Swedish law?</h3>
<p>Yes, if the foreign system meets Swedish requirements: 7-year data retention, SIE export capability, and immutable audit trails. However, Swedish auditors will expect SIE format data, so your foreign system must either support it or you must maintain a parallel Swedish record. Most SMBs find this impractical and prefer a Swedish-first tool like Varuflow.</p>
<h3>Do I need to keep paper copies of invoices?</h3>
<p>No. Since 2004, digital-only record-keeping is fully accepted under Bokföringslagen, provided your system meets the integrity and accessibility requirements. You do not need to print or scan invoices as long as the originals are securely stored digitally.</p>
<h3>What happens to my records if my SaaS provider shuts down?</h3>
<p>This is a real risk. Before signing with any provider, check their ToS for explicit retention guarantees — not just "we'll try our best" but contractual commitments. Varuflow guarantees 7-year retention under Swedish law regardless of your subscription status.</p>
<h3>When exactly does the 7-year clock start?</h3>
<p>The retention period runs from the end of the fiscal year in which the trading year falls. If you have a January-December fiscal year and record a transaction in March 2024, the 7-year clock starts from 31 December 2024, meaning you must retain that record until 31 December 2031.</p>
<h3>Is there any way to shorten the retention period for GDPR compliance?</h3>
<p>This is the Bokföringslagen vs. GDPR conflict. Swedish IMY and the courts have clarified that the 7-year retention obligation for financial records constitutes a legal obligation under GDPR Article 17(3)(b), which overrides the right to erasure. You cannot delete financial records before the 7-year window has passed — but you <em>can</em> pseudonymize non-essential personal data where technically feasible. See our <a href="/en/blog/gdpr-saas-7-year-retention-compliant">GDPR for SaaS guide</a> for a detailed breakdown.</p>
    `,
  },

  // ─── 2. ZATCA Phase 2 (EN) ────────────────────────────────────────────────
  {
    _id: "zatca-phase2-guide-en",
    slug: "zatca-phase-2-e-invoicing-implementation-checklist",
    title: "ZATCA Phase 2 E-Invoicing: Implementation Checklist for Saudi Businesses",
    excerpt:
      "A practical step-by-step guide to ZATCA Phase 2 e-invoicing in Saudi Arabia — from CSID registration and clearance mode to the full 31-point implementation checklist.",
    category: "compliance",
    tags: ["ZATCA", "e-invoicing", "Saudi Arabia", "fatoorah", "phase-2"],
    locale: "en",
    author: YOUSSEF,
    publishedAt: "2026-04-20",
    updatedAt: "2026-04-20",
    seoTitle: "ZATCA Phase 2 E-Invoicing: Complete Implementation Checklist (2026)",
    seoDescription:
      "A practical, step-by-step checklist for Saudi businesses implementing ZATCA Phase 2 e-invoicing — from CSID registration to clearance mode integration.",
    readingTimeMinutes: 11,
    featuredImageAlt: "ZATCA e-invoicing portal with Saudi business dashboard",
    leadMagnet: {
      title: "ZATCA Phase 2 Implementation Checklist (PDF)",
      description:
        "A 31-point checklist for your ZATCA Phase 2 rollout, reviewed by a former ZATCA certified consultant.",
      pdfSlug: "zatca-phase2-checklist",
      buttonLabel: "Get the checklist (free)",
    },
    tableOfContents: [
      { id: "what-is-zatca-phase2", title: "What is ZATCA Phase 2?", level: 2 },
      { id: "phase1-vs-phase2", title: "Phase 1 vs Phase 2 differences", level: 2 },
      { id: "clearance-vs-reporting", title: "Clearance vs reporting mode", level: 2 },
      { id: "csid-registration", title: "CSID registration process", level: 2 },
      { id: "xml-requirements", title: "XML invoice requirements (UBL 2.1)", level: 2 },
      { id: "rollout-timeline", title: "Rollout timeline by revenue tier", level: 2 },
      { id: "implementation-checklist", title: "31-point implementation checklist", level: 2 },
      { id: "common-mistakes", title: "Common mistakes to avoid", level: 2 },
      { id: "faq", title: "FAQ", level: 2 },
    ],
    internalLinks: [
      { href: "/en/regions/sa", label: "Varuflow for Saudi Arabia" },
      { href: "/en/compliance", label: "ZATCA compliance in Varuflow" },
      { href: "/en/trial", label: "Start 14-day trial" },
    ],
    externalLinks: [
      {
        href: "https://zatca.gov.sa/en/E-Invoicing/Pages/default.aspx",
        label: "ZATCA Official E-Invoicing Portal",
      },
      {
        href: "https://zatca.gov.sa/en/E-Invoicing/Introduction/Pages/E-Invoicing-Requirements.aspx",
        label: "ZATCA E-Invoicing Requirements",
      },
    ],
    cta: {
      headline: "ZATCA-compliant invoicing, ready on day one",
      body: "Varuflow handles ZATCA Phase 2 natively — clearance mode, hash chaining, QR codes, CSID integration.",
      buttonLabel: "Start 14-day free trial",
      href: "/en/trial",
    },
    bodyHtml: `
<h2 id="what-is-zatca-phase2">What is ZATCA Phase 2?</h2>
<p>ZATCA (Zakat, Tax and Customs Authority) Phase 2 is the integration phase of Saudi Arabia's mandatory e-invoicing mandate. Where Phase 1 only required businesses to generate and store electronic invoices, Phase 2 requires real-time integration with ZATCA's Fatoorah platform — meaning every invoice must be cryptographically signed using a CSID (Cryptographic Stamp Identifier) and either cleared or reported through ZATCA's API before it is legally valid.</p>
<p>Phase 2 compliance is not optional. Issuing paper invoices or non-compliant electronic invoices once your business falls within a Phase 2 wave exposes you to fines of up to SAR 50,000 per violation and suspension of your VAT registration.</p>

<h2 id="phase1-vs-phase2">Phase 1 vs Phase 2 differences</h2>
<table>
  <thead><tr><th>Requirement</th><th>Phase 1</th><th>Phase 2</th></tr></thead>
  <tbody>
    <tr><td>Invoice format</td><td>Structured XML or PDF</td><td>UBL 2.1 XML only</td></tr>
    <tr><td>ZATCA submission</td><td>Not required</td><td>Mandatory (real-time or near-real-time)</td></tr>
    <tr><td>Cryptographic stamp</td><td>Not required</td><td>Required (CSID)</td></tr>
    <tr><td>Hash chaining</td><td>Not required</td><td>Required (sequential invoice chain)</td></tr>
    <tr><td>QR code</td><td>TLV-encoded QR required</td><td>Updated QR with CSID hash</td></tr>
    <tr><td>Effective for B2B</td><td>December 2021</td><td>By wave (Jan 2023 onward)</td></tr>
  </tbody>
</table>

<h2 id="clearance-vs-reporting">Clearance vs reporting mode</h2>
<p>ZATCA Phase 2 operates in two modes depending on invoice type:</p>
<ul>
  <li><strong>Clearance mode</strong> (B2B invoices above SAR 1,000): The invoice XML must be submitted to ZATCA before being sent to the buyer. ZATCA returns a stamped, cleared XML within seconds. Only the cleared version is legally valid.</li>
  <li><strong>Reporting mode</strong> (B2C invoices and simplified invoices below SAR 1,000): Invoices can be issued to customers first, but must be reported to ZATCA within 24 hours.</li>
</ul>
<blockquote>
  <strong>Critical note:</strong> If your API call to ZATCA fails at the point of sale, you cannot issue the invoice until clearance succeeds. Build retry logic and offline fallback procedures before go-live.
</blockquote>

<h2 id="csid-registration">CSID registration process</h2>
<p>The Cryptographic Stamp Identifier (CSID) ties a specific ERP or invoicing solution to a business's VAT registration. Each device or system that generates invoices needs its own CSID. The process:</p>
<ol>
  <li>Log in to the ZATCA Fatoorah portal with your Iqama or company credentials</li>
  <li>Navigate to "E-Invoicing Solutions" → "Onboarding"</li>
  <li>Generate a Certificate Signing Request (CSR) from your invoicing system</li>
  <li>Submit the CSR to ZATCA; they return a CSID certificate (valid 3 years)</li>
  <li>Configure your invoicing system with the CSID private key</li>
  <li>Test on the ZATCA sandbox environment before go-live</li>
</ol>
<p>Varuflow handles CSR generation and CSID management automatically. <a href="/en/regions/sa">Learn how Varuflow simplifies ZATCA for Saudi businesses.</a></p>

<h2 id="xml-requirements">XML invoice requirements (UBL 2.1)</h2>
<p>ZATCA requires invoices in Universal Business Language (UBL) 2.1 format with specific Saudi extensions. Key mandatory fields:</p>
<ul>
  <li>Invoice number (sequential, no gaps allowed)</li>
  <li>Previous invoice hash (SHA-256 of the prior invoice XML)</li>
  <li>Seller and buyer VAT registration numbers (15-digit format)</li>
  <li>Line items with HS codes for goods or service codes for services</li>
  <li>VAT amount per line item (standard 15% or exempt)</li>
  <li>Cryptographic signature using RSA-256 with the CSID certificate</li>
  <li>QR code containing TLV-encoded seller name, VAT number, timestamp, total, and VAT amount</li>
</ul>

<h2 id="rollout-timeline">Rollout timeline by revenue tier</h2>
<table>
  <thead><tr><th>Wave</th><th>Annual Revenue</th><th>Effective Date</th></tr></thead>
  <tbody>
    <tr><td>Wave 1</td><td>Above SAR 3 billion</td><td>1 January 2023</td></tr>
    <tr><td>Wave 2</td><td>SAR 500M – SAR 3B</td><td>1 July 2023</td></tr>
    <tr><td>Wave 3</td><td>SAR 250M – SAR 500M</td><td>1 October 2023</td></tr>
    <tr><td>Wave 4</td><td>SAR 150M – SAR 250M</td><td>1 November 2023</td></tr>
    <tr><td>Wave 5</td><td>SAR 70M – SAR 150M</td><td>1 December 2023</td></tr>
    <tr><td>Wave 6+</td><td>SAR 50M – SAR 70M</td><td>Ongoing waves through 2025</td></tr>
    <tr><td>All businesses</td><td>All VAT-registered entities</td><td>Targeted 2025–2026</td></tr>
  </tbody>
</table>

<h2 id="implementation-checklist">31-point implementation checklist</h2>
<p>Use this checklist to track your Phase 2 readiness. Download the <a href="/en/blog/zatca-phase-2-e-invoicing-implementation-checklist#lead-magnet">full PDF version</a> for team collaboration.</p>
<ul>
  <li>☐ Confirm your ZATCA wave date based on last annual revenue</li>
  <li>☐ Audit current invoicing system for UBL 2.1 support</li>
  <li>☐ Generate CSR in your invoicing system</li>
  <li>☐ Register on ZATCA Fatoorah portal</li>
  <li>☐ Submit CSR and receive CSID certificate</li>
  <li>☐ Configure CSID in production system</li>
  <li>☐ Implement hash chaining for sequential invoices</li>
  <li>☐ Add QR code generation (TLV format)</li>
  <li>☐ Implement clearance API integration (B2B &gt;SAR 1,000)</li>
  <li>☐ Implement reporting API integration (B2C)</li>
  <li>☐ Build retry logic for API failures</li>
  <li>☐ Test on ZATCA sandbox environment (minimum 100 test invoices)</li>
  <li>☐ Validate XML schema against ZATCA's published XSD</li>
  <li>☐ Test cancellation workflow (credit notes)</li>
  <li>☐ Test simplified invoices (below SAR 1,000)</li>
  <li>☐ Verify 7-year archival of cleared invoices</li>
  <li>☐ Train accounts team on new workflow</li>
  <li>☐ Set up monitoring for failed clearance attempts</li>
  <li>☐ Prepare contingency plan for ZATCA API downtime</li>
  <li>☐ Complete ZATCA compliance declaration</li>
  <li>☐ Switch to production CSID</li>
</ul>

<h2 id="common-mistakes">Common mistakes to avoid</h2>
<ul>
  <li><strong>Invoice number gaps:</strong> Any gap in the sequential invoice chain invalidates downstream invoices. Use database-level auto-increment with no soft delete.</li>
  <li><strong>Wrong invoice type:</strong> Confusing standard invoices, debit notes, and credit notes leads to schema errors. Each has distinct UBL document type codes.</li>
  <li><strong>Buyer VAT exempt:</strong> If your buyer is exempt from VAT but you still charge it incorrectly, ZATCA will reject clearance. Your CRM must flag exempt buyers.</li>
  <li><strong>Clock skew:</strong> ZATCA validates invoice timestamps against their servers. Server time drift of more than 5 minutes causes rejection. Sync all servers to NTP.</li>
</ul>

<h2 id="faq">FAQ</h2>
<h3>What if I'm a small business below the current wave threshold?</h3>
<p>ZATCA plans to extend Phase 2 to all VAT-registered businesses. Start preparing now — the implementation typically takes 3–6 months — so you're not scrambling when your wave deadline is announced.</p>
<h3>Can I use an overseas ERP system for ZATCA compliance?</h3>
<p>Yes, but that system (or an integration layer) must support UBL 2.1, CSID management, and the Fatoorah API. ZATCA certifies specific software solutions. Uncertified solutions operate at your risk.</p>
<h3>Does Varuflow support ZATCA Phase 2?</h3>
<p>Yes. Varuflow is built for ZATCA Phase 2 from the ground up — native UBL 2.1, CSID management, clearance and reporting mode, hash chaining, and 7-year compliant archival. <a href="/en/trial">Start a free trial</a> to test drive the integration.</p>
    `,
  },

  // ─── 3. Peppol BIS 3.0 (EN) ────────────────────────────────────────────────
  {
    _id: "peppol-bis-3-guide-en",
    slug: "peppol-bis-3-explained-eu-smbs-prepare",
    title: "Peppol BIS 3.0 Explained: How EU SMBs Should Prepare",
    excerpt:
      "Peppol BIS 3.0 is becoming the standard for B2B e-invoicing across the EU. This guide explains the 4-corner model, how to get a Peppol ID, and what changes with the PINT format.",
    category: "compliance",
    tags: ["peppol", "e-invoicing", "EU", "BIS-3", "PINT"],
    locale: "en",
    translationSlug: "peppol-bis-3-forklarad-svenska-smab",
    author: ERIK,
    publishedAt: "2026-04-25",
    updatedAt: "2026-04-25",
    seoTitle: "Peppol BIS 3.0 Explained: What EU SMBs Must Do in 2026",
    seoDescription:
      "Peppol BIS 3.0 is becoming mandatory across the EU. Here's what it means for SMBs, how to connect to the Peppol network, and what changes with PINT.",
    readingTimeMinutes: 9,
    featuredImageAlt: "Peppol 4-corner network diagram",
    leadMagnet: {
      title: "Peppol Readiness Assessment",
      description:
        "Free 15-question self-assessment to check if your invoicing process is Peppol-ready.",
      pdfSlug: "peppol-readiness-assessment",
      buttonLabel: "Get the assessment",
    },
    tableOfContents: [
      { id: "what-is-peppol", title: "What is Peppol?", level: 2 },
      { id: "4-corner-model", title: "The 4-corner model explained", level: 2 },
      { id: "bis2-vs-bis3", title: "BIS 2.x vs BIS 3.0 differences", level: 2 },
      { id: "pint-format", title: "PINT: The international evolution", level: 2 },
      { id: "getting-peppol-id", title: "How to get a Peppol ID", level: 2 },
      { id: "nordic-specifics", title: "Nordic country requirements", level: 2 },
      { id: "public-vs-b2b", title: "Public sector vs B2B mandates", level: 2 },
      { id: "integration-paths", title: "Integration paths for SMBs", level: 2 },
      { id: "faq", title: "FAQ", level: 2 },
    ],
    internalLinks: [
      { href: "/en/compliance", label: "Peppol support in Varuflow" },
      { href: "/en/features", label: "Varuflow Features" },
      { href: "/en/regions/se", label: "Varuflow for Sweden" },
    ],
    externalLinks: [
      { href: "https://peppol.eu/what-is-peppol/", label: "OpenPeppol: What is Peppol?" },
      {
        href: "https://docs.peppol.eu/poacc/billing/3.0/",
        label: "Peppol BIS Billing 3.0 Specification",
      },
    ],
    cta: {
      headline: "Send and receive Peppol invoices from day one",
      body: "Varuflow is a certified Peppol access point participant. Connect to the network in minutes, not months.",
      buttonLabel: "Start 14-day free trial",
      href: "/en/trial",
    },
    bodyHtml: `
<h2 id="what-is-peppol">What is Peppol?</h2>
<p>Peppol (Pan-European Public Procurement On-Line) started as an EU initiative to standardize electronic document exchange for public procurement. It has since evolved into the dominant global standard for B2B e-invoicing, with participants in 40+ countries across Europe, Asia-Pacific, and the Americas.</p>
<p>At its core, Peppol is a <strong>network of networks</strong> — a set of common technical specifications that allow different countries' e-invoicing networks to interoperate. Think of it as the SWIFT network for invoices.</p>
<h2 id="4-corner-model">The 4-corner model explained</h2>
<p>Peppol uses a "4-corner model" to route documents:</p>
<ul>
  <li><strong>Corner 1:</strong> Sender (your business)</li>
  <li><strong>Corner 2:</strong> Your Access Point (Peppol-certified service provider)</li>
  <li><strong>Corner 3:</strong> Your buyer's Access Point</li>
  <li><strong>Corner 4:</strong> Receiver (your buyer)</li>
</ul>
<p>You never connect directly to your buyer — documents route through the network. This means you only need to configure your own Access Point once, and you can reach any other Peppol participant globally.</p>
<h2 id="bis2-vs-bis3">BIS 2.x vs BIS 3.0 differences</h2>
<table>
  <thead><tr><th>Feature</th><th>BIS 2.x</th><th>BIS 3.0</th></tr></thead>
  <tbody>
    <tr><td>XML format</td><td>CII or UBL</td><td>UBL 2.1 only (mandatory)</td></tr>
    <tr><td>Invoice lines</td><td>Limited line numbering</td><td>Full line reference support</td></tr>
    <tr><td>Allowances/charges</td><td>Document-level only</td><td>Line-level supported</td></tr>
    <tr><td>VAT treatment</td><td>Basic</td><td>Full reverse-charge support</td></tr>
    <tr><td>Status as of 2026</td><td>Deprecated</td><td>Required</td></tr>
  </tbody>
</table>
<h2 id="pint-format">PINT: The international evolution</h2>
<p>Peppol International (PINT) is the next evolution of Peppol BIS, designed to standardize invoicing globally. PINT creates a common core invoice data model that individual country "specializations" extend — meaning a single document format can satisfy Swedish, Singapore, Australian, and Japanese requirements simultaneously.</p>
<p>For Swedish SMBs exporting to APAC or the Americas, PINT-compliant invoicing software (like Varuflow) will be a significant competitive advantage when EU-APAC trade agreements tighten e-invoicing requirements.</p>
<h2 id="getting-peppol-id">How to get a Peppol ID</h2>
<p>Your Peppol ID is your network address — the identifier buyers use to route invoices to you. In Sweden, the standard Peppol ID format is <code>0007:[organisation number]</code> (e.g., <code>0007:5565566526</code> for organisation number 556556-6526).</p>
<p>To get a Peppol ID, you register with a certified Peppol Access Point. The Access Point registers your ID in the Peppol Service Metadata Publisher (SMP), making you discoverable. Varuflow includes Access Point connectivity in all paid plans.</p>
<h2 id="nordic-specifics">Nordic country requirements</h2>
<ul>
  <li><strong>Sweden:</strong> Public sector buyers have been mandated to accept Peppol since 2019. B2B is voluntary but growing rapidly.</li>
  <li><strong>Norway:</strong> EHF (Elektronisk Handelsformat) is the national profile of Peppol BIS 3.0. All public agencies require it.</li>
  <li><strong>Denmark:</strong> OIOUBL and OIOXML are being phased out in favor of Peppol BIS 3.0.</li>
  <li><strong>Finland:</strong> Finvoice is the domestic standard, but Peppol connectivity is increasingly expected for cross-border suppliers.</li>
</ul>
<h2 id="public-vs-b2b">Public sector vs B2B mandates</h2>
<p>Today, Peppol is largely mandatory for supplying to government agencies and public sector bodies across the EU. For B2B, it's currently voluntary in most countries — but the EU's ViDA (VAT in the Digital Age) directive targets mandatory B2B e-invoicing by 2028 for cross-border EU transactions, with national mandates expected to follow.</p>
<h2 id="integration-paths">Integration paths for SMBs</h2>
<p>You have three options for connecting to the Peppol network:</p>
<ol>
  <li><strong>Via your invoicing software (easiest):</strong> Choose a tool like Varuflow that includes certified Access Point connectivity. No separate IT project needed.</li>
  <li><strong>Via a standalone Access Point:</strong> Services like Pagero, Basware, or Inexchange connect your existing ERP to Peppol. Higher cost, more flexibility.</li>
  <li><strong>Direct Access Point participation:</strong> Only relevant for large enterprises (1,000+ invoices/month) willing to manage their own Peppol infrastructure.</li>
</ol>
<p>For most SMBs, option 1 is the right choice. <a href="/en/features">Varuflow's Peppol integration</a> handles registration, routing, and document validation automatically.</p>
<h2 id="faq">FAQ</h2>
<h3>Do I need Peppol if I only invoice Swedish domestic customers?</h3>
<p>Not yet for B2B. But if any of your customers are public sector (government agencies, municipalities, hospitals), they likely already require Peppol-formatted invoices. Check your customer contracts.</p>
<h3>How much does Peppol connectivity cost?</h3>
<p>Depends on the route. Varuflow includes Peppol in all paid plans at no extra charge. Standalone access points typically cost SAR 500–5,000/year depending on volume.</p>
<h3>Can I send Peppol invoices to buyers outside the EU?</h3>
<p>Yes — with PINT-enabled software. Australia, Singapore, Japan, and New Zealand are active Peppol participants. The same Peppol ID and access point can route invoices globally.</p>
    `,
  },

  // ─── 4. GDPR 7-Year Retention (EN) ────────────────────────────────────────
  {
    _id: "gdpr-7-year-retention-saas",
    slug: "gdpr-saas-7-year-retention-compliant",
    title: "GDPR for SaaS: 7-Year Retention Without Breaking the Law",
    excerpt:
      "Swedish law requires 7-year retention of financial records, but GDPR demands data minimization. Here's how SaaS companies legally satisfy both obligations simultaneously.",
    category: "compliance",
    tags: ["GDPR", "data-retention", "SaaS", "compliance", "PII"],
    locale: "en",
    author: SARA,
    publishedAt: "2026-04-28",
    updatedAt: "2026-04-28",
    seoTitle: "GDPR & 7-Year Accounting Retention: How SaaS Handles Both (2026)",
    seoDescription:
      "Swedish law requires 7-year retention of financial records, but GDPR demands data minimization. Here's the legal framework for resolving this conflict.",
    readingTimeMinutes: 10,
    featuredImageAlt: "GDPR compliance and accounting retention balance scale diagram",
    leadMagnet: {
      title: "GDPR vs Bokföringslagen Conflict Matrix",
      description:
        "A decision matrix for resolving conflicts between GDPR minimization and Swedish accounting retention obligations.",
      pdfSlug: "gdpr-bokforingslagen-matrix",
      buttonLabel: "Download decision matrix",
    },
    tableOfContents: [
      { id: "the-core-conflict", title: "The core tension: GDPR vs accounting law", level: 2 },
      { id: "article-17-exception", title: "GDPR Article 17 exception for legal obligations", level: 2 },
      { id: "classifying-invoice-data", title: "Classifying your invoice data", level: 2 },
      { id: "pseudonymization", title: "Pseudonymization strategy", level: 2 },
      { id: "technical-implementation", title: "Technical implementation", level: 2 },
      { id: "what-can-be-deleted", title: "What can vs must be retained", level: 2 },
      { id: "dpa-for-saas", title: "Data Processing Agreements for SaaS", level: 2 },
      { id: "imy-guidance", title: "Swedish IMY guidance", level: 2 },
      { id: "faq", title: "FAQ", level: 2 },
    ],
    internalLinks: [
      { href: "/en/security", label: "Varuflow Security & Privacy" },
      { href: "/en/compliance", label: "Compliance Features" },
      {
        href: "/en/blog/complete-guide-bokforinglagen-swedish-smbs",
        label: "Bokföringslagen Guide",
      },
    ],
    externalLinks: [
      {
        href: "https://www.imy.se/verksamhet/dataskydd/det-har-galler-enligt-gdpr/grundlaggande-principer/lagringsminimering/",
        label: "IMY: Lagringsbegränsning (Storage Limitation)",
      },
      {
        href: "https://gdpr.eu/article-5-how-personal-data-be-processed/",
        label: "GDPR Article 5 - Principles of Processing",
      },
    ],
    cta: {
      headline: "GDPR and Bokföringslagen compliance — both, out of the box",
      body: "Varuflow's privacy-by-design architecture handles the GDPR vs 7-year retention conflict automatically.",
      buttonLabel: "See our compliance features",
      href: "/en/compliance",
    },
    bodyHtml: `
<h2 id="the-core-conflict">The core tension: GDPR vs accounting law</h2>
<p>Every Swedish business using cloud software faces the same contradiction: Bokföringslagen requires you to keep financial records for <strong>7 years</strong>, but GDPR Article 5(1)(e) demands <em>storage limitation</em> — you should not retain personal data "for longer than is necessary."</p>
<p>This isn't a theoretical conflict. Invoice records contain personal data: customer names, addresses, VAT numbers (which can identify individuals in sole trader businesses), and purchase histories. GDPR applies. And the conflict is real enough that IMY (the Swedish data protection authority) has issued specific guidance on it.</p>
<p>The good news: the conflict is resolvable. Here's the legal framework.</p>
<h2 id="article-17-exception">GDPR Article 17 exception for legal obligations</h2>
<p>GDPR Article 17 gives data subjects the right to erasure ("right to be forgotten"). But Article 17(3)(b) carves out an explicit exception: erasure does not apply when processing is "necessary for compliance with a legal obligation which requires processing by Union or Member State law."</p>
<p>Bokföringslagen is exactly such a legal obligation under Swedish Member State law. This means you are <strong>legally right to refuse erasure requests</strong> for invoice data that is within the 7-year retention window — provided you can document that the retention is necessary for compliance purposes.</p>
<blockquote>
  <strong>Key principle:</strong> Retain the minimum data necessary for the accounting obligation. Erase everything else on schedule.
</blockquote>
<h2 id="classifying-invoice-data">Classifying your invoice data</h2>
<p>Not all data in an invoice record is equal under Bokföringslagen. The law requires retention of financial information — amounts, dates, goods descriptions, counterparty identity. It does not require retention of marketing data, browsing history, or soft-contact preferences.</p>
<table>
  <thead><tr><th>Data type</th><th>Must retain (Bokföringslagen)</th><th>Can delete (GDPR minimization)</th></tr></thead>
  <tbody>
    <tr><td>Invoice amount, date, number</td><td>✓ Required</td><td>No</td></tr>
    <tr><td>Customer legal name and address</td><td>✓ Required</td><td>No (within 7 years)</td></tr>
    <tr><td>Customer VAT number</td><td>✓ Required</td><td>No (within 7 years)</td></tr>
    <tr><td>Customer email address</td><td>Not strictly required</td><td>Yes — can delete after invoice closed</td></tr>
    <tr><td>Customer contact preferences</td><td>Not required</td><td>Yes — delete on request</td></tr>
    <tr><td>Customer note fields</td><td>Not required</td><td>Yes — delete on request</td></tr>
    <tr><td>Purchase history analytics</td><td>Not required</td><td>Yes — can aggregate/anonymize</td></tr>
  </tbody>
</table>
<h2 id="pseudonymization">Pseudonymization strategy</h2>
<p>The most elegant solution for reducing GDPR exposure while maintaining compliance is <strong>pseudonymization</strong> of invoice records at year 3 or 4 of the retention window. This means:</p>
<ol>
  <li>Replacing the natural customer name with an internal identifier (e.g., "CUST-00123")</li>
  <li>Replacing addresses with anonymized location data (city-level only)</li>
  <li>Maintaining a separate, encrypted mapping table that can be used for audit purposes if required</li>
</ol>
<p>This satisfies GDPR minimization for inactive accounts while preserving the accounting records for Bokföringslagen. IMY's published guidance explicitly supports this approach.</p>
<p>Varuflow implements automatic pseudonymization for customer data on closed accounts after three years of inactivity. See our <a href="/en/security">security and privacy documentation</a> for the full policy.</p>
<h2 id="technical-implementation">Technical implementation</h2>
<p>For SaaS companies building on top of financial data, the recommended technical architecture:</p>
<ul>
  <li><strong>Immutable invoice archive:</strong> Write-once storage for invoice records (no DELETE allowed on the accounting table)</li>
  <li><strong>Separate PII store:</strong> Contact details stored in a separate table with a TTL (time-to-live) policy</li>
  <li><strong>Encryption at rest:</strong> Invoice records encrypted with AES-256; key management separate from data storage</li>
  <li><strong>Audit log:</strong> Immutable log of all data access and deletions (required for demonstrating GDPR compliance)</li>
  <li><strong>Deletion workflows:</strong> Automated schedule for deleting non-essential personal data when accounts close</li>
</ul>
<h2 id="what-can-be-deleted">What can vs must be retained</h2>
<p>Clear internal policy matters here. Document which data categories fall under Bokföringslagen retention and which can be deleted on request:</p>
<ul>
  <li><strong>Immediate deletion on request:</strong> Marketing preferences, newsletter subscriptions, non-customer personal contacts</li>
  <li><strong>Deletion upon account closure:</strong> Login credentials, session data, support chat history, feature usage analytics</li>
  <li><strong>Deletion after 3 years of account inactivity (pseudonymize):</strong> Customer contact details not related to open financial records</li>
  <li><strong>Retain for 7 years (cannot delete):</strong> Invoice records, vouchers, general ledger entries, VAT records</li>
</ul>
<h2 id="dpa-for-saas">Data Processing Agreements for SaaS</h2>
<p>If you are a SaaS provider processing financial data on behalf of your customers (as Varuflow does), you must have a Data Processing Agreement (DPA) in place. The DPA must specify:</p>
<ul>
  <li>The categories of personal data processed</li>
  <li>The legal basis for each processing activity</li>
  <li>Subprocessors (your cloud hosting provider, database provider)</li>
  <li>Retention periods and deletion schedules by data category</li>
  <li>Technical and organizational security measures</li>
  <li>Cross-border transfer safeguards if data is stored outside the EEA</li>
</ul>
<p>Varuflow's DPA is available for counterparty signature in your account settings. All data is stored in EU data centers (AWS eu-north-1, Stockholm).</p>
<h2 id="imy-guidance">Swedish IMY guidance</h2>
<p>IMY has confirmed in multiple decisions that:</p>
<ol>
  <li>The 7-year accounting retention obligation constitutes a legal basis for processing under GDPR Article 6(1)(c)</li>
  <li>Erasure requests for data within the accounting retention window can be refused on the basis of Article 17(3)(b)</li>
  <li>Businesses must document that retained data is genuinely necessary for the accounting obligation (you cannot use accounting as an excuse to keep marketing data)</li>
</ol>
<h2 id="faq">FAQ</h2>
<h3>A customer has issued a right to erasure request. Do I have to delete their invoices?</h3>
<p>No — for invoices within the 7-year retention window. You must inform them of the legal obligation and what data you are retaining and why. After the 7-year window passes, you must then delete the records. Document yourresponse.</p>
<h3>Can I store invoice data outside Sweden (e.g., AWS Frankfurt)?</h3>
<p>Yes, provided you comply with GDPR Chapter V on international transfers. AWS Frankfurt (eu-central-1) is within the EEA, so no additional transfer safeguards beyond the DPA are needed. Storage on US servers without a valid SCCs or adequacy decision would be prohibited.</p>
<h3>What is the penalty for GDPR non-compliance on this?</h3>
<p>Up to €20 million or 4% of global annual revenue, whichever is higher. In practice, IMY has issued fines in the range of SEK 1–75 million for Swedish businesses. The risk is real — document your legal basis clearly.</p>
    `,
  },

  // ─── 5. Varuflow vs Fortnox (EN) ─────────────────────────────────────────
  {
    _id: "varuflow-vs-fortnox-2026-en",
    slug: "varuflow-vs-fortnox-comparison-2026",
    title: "Varuflow vs Fortnox: Feature-by-Feature Comparison 2026",
    excerpt:
      "An honest, detailed comparison of Varuflow and Fortnox on pricing, inventory management, invoicing workflows, compliance depth, API capabilities, and who should use which.",
    category: "comparison",
    tags: ["fortnox", "comparison", "invoicing-software", "sweden", "SMB"],
    locale: "en",
    translationSlug: "varuflow-vs-fortnox-jamforelse-2026",
    author: ERIK,
    publishedAt: "2026-05-01",
    updatedAt: "2026-05-01",
    seoTitle: "Varuflow vs Fortnox 2026: Honest Feature Comparison",
    seoDescription:
      "Comparing Varuflow and Fortnox on pricing, inventory, invoicing, compliance, and API. Which is right for your Swedish business in 2026?",
    readingTimeMinutes: 11,
    featuredImageAlt: "Varuflow versus Fortnox feature comparison dashboard",
    tableOfContents: [
      { id: "executive-summary", title: "Executive summary", level: 2 },
      { id: "pricing", title: "Pricing comparison", level: 2 },
      { id: "feature-comparison", title: "Full feature comparison", level: 2 },
      { id: "inventory", title: "Inventory management", level: 2 },
      { id: "invoicing", title: "Invoicing and compliance", level: 2 },
      { id: "integrations", title: "Integrations and API", level: 2 },
      { id: "who-should-use", title: "Who should use which?", level: 2 },
      { id: "migration", title: "Migration from Fortnox to Varuflow", level: 2 },
      { id: "faq", title: "FAQ", level: 2 },
    ],
    internalLinks: [
      { href: "/en/vs/fortnox", label: "Varuflow vs Fortnox quick comparison" },
      { href: "/en/pricing", label: "Varuflow Pricing" },
      { href: "/en/trial", label: "Try Varuflow free" },
    ],
    externalLinks: [
      { href: "https://www.fortnox.se/priser", label: "Fortnox official pricing" },
      { href: "https://www.g2.com/products/fortnox/reviews", label: "Fortnox G2 reviews" },
    ],
    cta: {
      headline: "Already using Fortnox? Import your data in an afternoon.",
      body: "Varuflow's Fortnox migration tool transfers customers, products, and invoice history with one click.",
      buttonLabel: "Start free trial",
      href: "/en/trial",
    },
    bodyHtml: `
<h2 id="executive-summary">Executive summary</h2>
<p><strong>Fortnox</strong> is Sweden's dominant accounting software — a broad-market platform used by 500,000+ Swedish businesses, with strong accountant and bookkeeper tooling. Its strength is general-purpose accounting. Its weakness is that features not related to accounting (inventory, B2B ordering, customer portal, AI) require expensive add-on modules and are afterthoughts architecturally.</p>
<p><strong>Varuflow</strong> was built specifically for product-based businesses — wholesalers, distributors, retailers. It treats inventory as first-class, not a module. Compliance (Bokföringslagen, Peppol, ZATCA) is built in from day one rather than bolted on. The cost model is flat — one plan, all features, unlimited users.</p>
<blockquote>
  <strong>Bottom line:</strong> If your primary need is accounting and payroll for a service business, Fortnox is mature and deeply supported. If you stock products, invoice B2B customers, and need inventory + invoicing to work as one system, Varuflow is the better fit.
</blockquote>
<h2 id="pricing">Pricing comparison</h2>
<table>
  <thead><tr><th>Plan</th><th>Varuflow</th><th>Fortnox</th></tr></thead>
  <tbody>
    <tr><td>Starting price</td><td>Free (up to 100 products)</td><td>From ~199 SEK/month (limited)</td></tr>
    <tr><td>Full-featured plan</td><td>599 SEK/month (unlimited users)</td><td>~1,995 SEK/month (5-user base)</td></tr>
    <tr><td>Per-user fees</td><td>None</td><td>+199 SEK/user above base</td></tr>
    <tr><td>Inventory add-on</td><td>Included</td><td>+299 SEK/month</td></tr>
    <tr><td>Customer portal</td><td>Included</td><td>Not available</td></tr>
    <tr><td>Peppol invoicing</td><td>Included</td><td>+150 SEK/month</td></tr>
    <tr><td>AI features</td><td>Included</td><td>Not available</td></tr>
    <tr><td>ZATCA support</td><td>Included</td><td>Not available</td></tr>
  </tbody>
</table>
<p>For a 5-person team wanting inventory + Peppol + portal, Fortnox costs approximately 2,643 SEK/month. Varuflow costs 599 SEK/month. The gap widens with team size.</p>
<h2 id="feature-comparison">Full feature comparison</h2>
<table>
  <thead><tr><th>Feature</th><th>Varuflow</th><th>Fortnox</th></tr></thead>
  <tbody>
    <tr><td>Inventory management</td><td>✓ Native, real-time</td><td>Add-on (limited)</td></tr>
    <tr><td>Multi-warehouse</td><td>✓ Included</td><td>Not available</td></tr>
    <tr><td>B2B customer portal</td><td>✓ Included</td><td>Not available</td></tr>
    <tr><td>POS (point of sale)</td><td>✓ Included</td><td>Add-on</td></tr>
    <tr><td>Loyalty program</td><td>✓ Included</td><td>Not available</td></tr>
    <tr><td>Recurring invoices</td><td>✓ Included</td><td>✓ Included</td></tr>
    <tr><td>Peppol e-invoicing</td><td>✓ Included</td><td>Add-on</td></tr>
    <tr><td>Bokföringslagen SIE export</td><td>✓ Included</td><td>✓ Included</td></tr>
    <tr><td>ZATCA Phase 2</td><td>✓ Native</td><td>Not available</td></tr>
    <tr><td>AI action cards</td><td>✓ Included</td><td>Not available</td></tr>
    <tr><td>Payroll</td><td>Not available</td><td>✓ Full payroll module</td></tr>
    <tr><td>Annual report generation</td><td>SIE export only</td><td>✓ Full ÅRL support</td></tr>
    <tr><td>Bank integration (Swedish)</td><td>Bankgiro + Autogiro</td><td>✓ All major Swedish banks</td></tr>
    <tr><td>REST API</td><td>✓ Full, documented</td><td>✓ Full, documented</td></tr>
    <tr><td>Mobile app</td><td>PWA (responsive)</td><td>Native iOS/Android</td></tr>
  </tbody>
</table>
<h2 id="invoicing">Invoicing and compliance</h2>
<p>Both tools handle Swedish invoice basics: automatic VAT, Bankgiro payment references, PDF generation. The differences show in depth:</p>
<ul>
  <li><strong>Varuflow:</strong> Built for volume. Bulk invoice creation from orders, automatic dunning sequences, customer portal for self-service payment. Handles ZATCA (Saudi), PINT (international), and Peppol in one system.</li>
  <li><strong>Fortnox:</strong> Strong for accounting-led businesses. Deep integration with Swedish banks for reconciliation. Annual report wizards compliant with K2/K3/K4 regulations. Payroll with Skatteverket integration.</li>
</ul>
<h2 id="integrations">Integrations and API</h2>
<p>Fortnox has a mature app marketplace with 1,000+ integrations — Shopify, WooCommerce, Visma, Hogia, Nets, and more. The Fortnox API is well-documented and widely used in the Swedish developer community.</p>
<p>Varuflow's API is newer but purpose-built for operations: real-time webhook events for order status, inventory levels, and payment receipts. Direct integrations with Fortnox (for accountants who prefer it), Shopify, and WooCommerce. The <a href="/en/features">API documentation</a> is publicly available.</p>
<h2 id="who-should-use">Who should use which?</h2>
<table>
  <thead><tr><th>Profile</th><th>Recommendation</th></tr></thead>
  <tbody>
    <tr><td>Service business, accountant-managed books</td><td>Fortnox</td></tr>
    <tr><td>Sole trader needing payroll + accounting only</td><td>Fortnox Bas</td></tr>
    <tr><td>Product-based business, 1–50 SKUs</td><td>Varuflow</td></tr>
    <tr><td>Wholesaler or distributor, any size</td><td>Varuflow</td></tr>
    <tr><td>Business selling in Saudi Arabia or UAE</td><td>Varuflow (ZATCA/FTA native)</td></tr>
    <tr><td>Business with 5+ staff needing invoicing + inventory</td><td>Varuflow (flat pricing)</td></tr>
    <tr><td>Annual report needs (K2/K3/K4)</td><td>Fortnox or both (Varuflow + Fortnox API integration)</td></tr>
  </tbody>
</table>
<h2 id="migration">Migration from Fortnox to Varuflow</h2>
<p>Varuflow provides a 1-click Fortnox migration tool that imports:</p>
<ul>
  <li>All customer records (company name, contact, VAT number, address)</li>
  <li>Product catalogue with prices and product numbers</li>
  <li>Invoice history (last 3 years + active invoices)</li>
  <li>Supplier list</li>
</ul>
<p>The migration typically completes in under 30 minutes for SMB-scale data. Your Fortnox account can remain active in parallel during a transition period. Most customers run Varuflow for operations and keep Fortnox for the accountant's annual report — connecting them via the Fortnox API integration to avoid double-entry.</p>
<h2 id="faq">FAQ</h2>
<h3>Can I use Varuflow and keep Fortnox for my accountant?</h3>
<p>Yes — and it's a common setup. Varuflow exports SIE 4 files on demand, which your accountant imports into Fortnox for year-end closing. You get Varuflow's superior operations tooling while your accountant keeps their Fortnox workflow.</p>
<h3>Does Varuflow have Bankgiro OCR import?</h3>
<p>Yes. Varuflow imports Bankgiro OCR files from Bankgirot for automatic invoice reconciliation — same as Fortnox.</p>
<h3>Is Varuflow's API as mature as Fortnox's?</h3>
<p>Fortnox's API is more battle-tested with a larger ecosystem. Varuflow's API is more modern (REST/JSON with webhooks) and documents the operational data that Fortnox can't expose (inventory levels, POS sessions, portal activity). For most integration needs, both are sufficient.</p>
    `,
  },

  // ─── 6. Best Fortnox Alternatives (SV) ──────────────────────────────────────
  {
    _id: "fortnox-alternativ-sv",
    slug: "basta-fortnox-alternativ-svenska-smab",
    title: "De bästa alternativen till Fortnox 2026 — för svenska småföretag",
    excerpt:
      "Letar du efter ett alternativ till Fortnox? Vi jämför de 7 bästa alternativen för svenska SMB på pris, funktioner och compliance — inklusive ett gratis alternativ.",
    category: "comparison",
    tags: ["fortnox", "alternativ", "faktura", "bokföring", "Sverige"],
    locale: "sv",
    author: ERIK,
    publishedAt: "2026-05-02",
    updatedAt: "2026-05-02",
    seoTitle: "Bästa alternativen till Fortnox 2026 — för svenska SMB",
    seoDescription:
      "Letar du efter ett alternativ till Fortnox? Vi jämför de 7 bästa alternativen för svenska småföretag på pris, funktioner och compliance.",
    readingTimeMinutes: 9,
    featuredImageAlt: "Jämförelse av bokföringsprogram för svenska småföretag",
    tableOfContents: [
      { id: "varfor-byta", title: "Varför byta från Fortnox?", level: 2 },
      { id: "7-alternativ", title: "De 7 bästa alternativen", level: 2 },
      { id: "jamforelsetabell", title: "Jämförelsetabell", level: 2 },
      { id: "vem-passar-vad", title: "Vem passar vad?", level: 2 },
      { id: "migration", title: "Flytta från Fortnox", level: 2 },
      { id: "faq", title: "Vanliga frågor", level: 2 },
    ],
    internalLinks: [
      { href: "/pricing", label: "Varuflow priser" },
      { href: "/vs/fortnox", label: "Varuflow vs Fortnox jämförelse" },
      { href: "/trial", label: "Prova Varuflow gratis" },
    ],
    externalLinks: [
      { href: "https://www.fortnox.se", label: "Fortnox officiell webbplats" },
      { href: "https://www.verksamt.se/starta/fa-hjalp/ekonomi/bokforing", label: "Verksamt.se: Bokföring" },
    ],
    cta: {
      headline: "Prova Varuflow gratis i 14 dagar",
      body: "Importera från Fortnox på en lunch. Inget kreditkortskrav.",
      buttonLabel: "Starta gratis provperiod",
      href: "/trial",
    },
    bodyHtml: `<h2 id="varfor-byta">Varför byta från Fortnox?</h2>
<p>Fortnox är Sveriges mest använda bokföringsprogram med över 500 000 kunder. Men det innebär inte att det passar alla. De vanligaste skälen till att svenska SMB söker alternativ: prismodellen (modulbaserad, dyrt för produktbolag), inget inbyggt lager, ingen B2B-portal, och ingen support för ZATCA eller UAE FTA.</p>
<h2 id="7-alternativ">De 7 bästa alternativen</h2>
<h3>1. Varuflow — bäst för produktbaserade företag</h3>
<p>Varuflow är byggt specifikt för grossister och detaljhandlare. Lager, fakturering, kundportal, POS och AI-verktyg ingår för 599 kr/månad utan per-användarpris. Compliance för Sverige (Bokföringslagen, Peppol), Saudiarabien (ZATCA) och UAE (FTA) är inbyggd.</p>
<h3>2. Bokio — bäst för enskild firma</h3><p>Enkelt och användarvänligt. Gratis grundplan. Begränsat lager. Passar tjänsteföretag som inte hanterar produkter.</p>
<h3>3. Visma eEkonomi</h3><p>Mellanting med bred funktionalitet och bra bankkopplingar. Fortfarande modulbaserat pris.</p>
<h3>4. Björn Lunden</h3><p>Populärt bland redovisningskonsulter. Starkt skatt och deklaration. Svagt operationsverktyg.</p>
<h3>5. Wint</h3><p>AI-automatiserad bokföring baserat på bankflöden. Bra för tjänsteföretag med enkel ekonomi.</p>
<h3>6. ERPNext / Frappe</h3><p>Open source och gratis. Kräver IT-kompetens att driftsätta.</p>
<h3>7. Speedledger</h3><p>Starkt inom bankkopplingar och OCR-avstämning.</p>
<h2 id="jamforelsetabell">Jämförelsetabell</h2>
<table><thead><tr><th>Program</th><th>Pris/månad</th><th>Lager</th><th>Peppol</th><th>B2B-portal</th></tr></thead>
<tbody>
<tr><td>Varuflow Pro</td><td>599 kr</td><td>✓ Inbyggt</td><td>✓</td><td>✓</td></tr>
<tr><td>Fortnox (full)</td><td>~2 000+ kr</td><td>Modul +299 kr</td><td>Modul</td><td>Nej</td></tr>
<tr><td>Bokio</td><td>0–399 kr</td><td>Begränsat</td><td>Nej</td><td>Nej</td></tr>
<tr><td>Visma eEkonomi</td><td>349–999 kr</td><td>Begränsat</td><td>Modul</td><td>Nej</td></tr>
</tbody></table>
<h2 id="vem-passar-vad">Vem passar vad?</h2>
<ul><li><strong>Enskild firma, tjänsteföretag:</strong> Bokio eller Wint</li>
<li><strong>Produktbaserat SMB:</strong> Varuflow</li>
<li><strong>Grossist eller distributör:</strong> Varuflow</li>
<li><strong>Komplex K3/K4-redovisning:</strong> Fortnox + SIE-export till revisorn</li></ul>
<h2 id="migration">Flytta från Fortnox</h2>
<p>Varuflow erbjuder ett migreringsverktyg som importerar kunder, produkter, fakturahistorik och leverantörer från Fortnox API. Migrering tar typiskt 20–45 minuter. <a href="/trial">Starta gratis provperiod</a>.</p>
<h2 id="faq">Vanliga frågor</h2>
<h3>Kan jag behålla Fortnox för revisorn och använda Varuflow för verksamheten?</h3>
<p>Ja — det är den vanligaste konfigurationen. Du exporterar SIE 4-filer från Varuflow som revisorn importerar i Fortnox för bokslut.</p>`,
  },

  // ─── 7. Odoo Alternatives (EN) ────────────────────────────────────────────
  {
    _id: "odoo-alternatives-smb-2026",
    slug: "odoo-alternatives-why-smbs-switch-simpler-tools",
    title: "Odoo Alternatives: Why SMBs Switch to Simpler Tools",
    excerpt:
      "Odoo is powerful but costly to implement. Here are 6 alternatives that SMBs find easier, cheaper, and just as capable for their actual needs.",
    category: "comparison",
    tags: ["odoo", "alternatives", "ERP", "SMB", "open-source"],
    locale: "en",
    author: YOUSSEF,
    publishedAt: "2026-05-03",
    updatedAt: "2026-05-03",
    seoTitle: "Best Odoo Alternatives for SMBs in 2026 (Honest Review)",
    seoDescription:
      "Odoo is powerful but complex and expensive to implement. Here are 6 simpler alternatives that SMBs actually prefer — with pricing and feature comparison.",
    readingTimeMinutes: 9,
    featuredImageAlt: "Comparison of SMB business software alternatives to Odoo",
    tableOfContents: [
      { id: "odoo-promise-vs-reality", title: "The Odoo promise vs reality", level: 2 },
      { id: "who-odoo-suits", title: "Who Odoo actually suits", level: 2 },
      { id: "6-alternatives", title: "6 better alternatives", level: 2 },
      { id: "comparison-matrix", title: "Feature and price comparison", level: 2 },
      { id: "decision-framework", title: "Decision framework", level: 2 },
      { id: "faq", title: "FAQ", level: 2 },
    ],
    internalLinks: [
      { href: "/en/vs/odoo", label: "Varuflow vs Odoo" },
      { href: "/en/pricing", label: "Varuflow plans" },
      { href: "/en/features", label: "Varuflow features" },
    ],
    externalLinks: [
      { href: "https://www.odoo.com/pricing", label: "Odoo official pricing" },
      { href: "https://www.capterra.com/erp-software/alternatives/odoo/", label: "Capterra: Odoo alternatives" },
    ],
    cta: {
      headline: "The power you need, without the 3-month implementation",
      body: "Varuflow gives you inventory, invoicing, portal, and AI in one tool. Live in a day.",
      buttonLabel: "Start free trial",
      href: "/en/trial",
    },
    bodyHtml: `<h2 id="odoo-promise-vs-reality">The Odoo promise vs reality</h2>
<p>Odoo's pitch is one platform for everything. But for SMBs the implementation cost is often €15,000–€50,000 in partner consulting, per-user pricing compounds fast (€72/user/month for Inventory + Invoicing + CRM), and most companies become dependent on their Odoo partner for routine changes.</p>
<h2 id="who-odoo-suits">Who Odoo actually suits</h2>
<p>Odoo is genuinely good for: 50+ employee businesses with IT staff, manufacturers needing MRP, and multi-entity accounting across countries. For 5–40 person product businesses, you're likely overbuying.</p>
<h2 id="6-alternatives">6 better alternatives</h2>
<h3>1. Varuflow</h3><p>Purpose-built for wholesalers and distributors. Flat pricing (€55/month, unlimited users). Native Peppol, ZATCA, Bokföringslagen. <a href="/en/features">See all features.</a></p>
<h3>2. Zoho Books</h3><p>Strong for global SMBs needing invoicing across 180+ countries. Good for service businesses.</p>
<h3>3. ERPNext (Frappe)</h3><p>Free open-source alternative. Nearly as capable but requires IT investment.</p>
<h3>4. Holded</h3><p>Strong Shopify/Amazon integrations. Less compliant for Nordic markets.</p>
<h3>5. Cin7 Omni</h3><p>Best for complex inventory with 3PL. More expensive but better for advanced logistics.</p>
<h3>6. QuickBooks</h3><p>Good for US-facing businesses. Poor Nordic compliance (no Peppol).</p>
<h2 id="comparison-matrix">Feature and price comparison</h2>
<table><thead><tr><th>Tool</th><th>Monthly (10 users)</th><th>Implementation</th><th>Nordic</th><th>MENA</th></tr></thead>
<tbody>
<tr><td>Odoo Enterprise</td><td>€720+</td><td>€15–50k</td><td>Module</td><td>Module</td></tr>
<tr><td>Varuflow Pro</td><td>€55 (unlimited)</td><td>&lt;1 day</td><td>✓ Native</td><td>✓ Native</td></tr>
<tr><td>Zoho Books</td><td>~€150</td><td>1–5 days</td><td>Partial</td><td>Partial</td></tr>
<tr><td>ERPNext</td><td>~€100</td><td>5–30 days</td><td>Community</td><td>Community</td></tr>
</tbody></table>
<h2 id="decision-framework">Decision framework</h2>
<ol><li>Need manufacturing/MRP? → Odoo or ERPNext</li>
<li>50+ employees with IT team? → Odoo might work</li>
<li>Primary challenge: inventory + invoicing for product sales? → Varuflow</li>
<li>Global multi-entity accounting? → Zoho Books</li></ol>
<h2 id="faq">FAQ</h2>
<h3>Can I migrate my Odoo product catalogue to Varuflow?</h3>
<p>Yes. Varuflow accepts CSV imports of products, customers, and suppliers — Odoo exports these easily.</p>`,
  },

  // ─── 8. Salon Management (EN) ─────────────────────────────────────────────
  {
    _id: "salon-management-bookings-pos-loyalty-en",
    slug: "modern-salons-bookings-pos-loyalty-one-tool",
    title: "How Modern Salons Manage Bookings, POS, and Loyalty in One Tool",
    excerpt:
      "Most salons run 3–4 separate tools that don't talk to each other. Here's how the best-run salons consolidate — and how much they save.",
    category: "vertical",
    tags: ["salon", "beauty", "POS", "bookings", "loyalty", "SMB"],
    locale: "en",
    translationSlug: "idarat-salon-hadith-ar",
    author: SARA,
    publishedAt: "2026-05-04",
    updatedAt: "2026-05-04",
    seoTitle: "Salon Management in 2026: Bookings, POS & Loyalty in One Tool",
    seoDescription:
      "How modern salons replace 3 separate tools with one. From online booking and POS checkout to loyalty points and GDPR-compliant client records.",
    readingTimeMinutes: 8,
    featuredImageAlt: "Modern salon management system showing bookings and POS",
    leadMagnet: {
      title: "Salon Tech Stack Audit Template",
      description: "A free spreadsheet to audit your current salon software costs and identify consolidation opportunities.",
      pdfSlug: "salon-tech-audit",
      buttonLabel: "Get free audit template",
    },
    tableOfContents: [
      { id: "the-3-tool-problem", title: "The 3-tool problem", level: 2 },
      { id: "booking-requirements", title: "What your booking system must do", level: 2 },
      { id: "pos-requirements", title: "Point-of-sale requirements", level: 2 },
      { id: "loyalty-design", title: "Designing loyalty that works", level: 2 },
      { id: "client-records-gdpr", title: "Client records and GDPR", level: 2 },
      { id: "faq", title: "FAQ", level: 2 },
    ],
    internalLinks: [
      { href: "/en/verticals/salons", label: "Varuflow for Salons" },
      { href: "/en/features", label: "Varuflow POS & Booking" },
      { href: "/en/trial", label: "Start free salon trial" },
    ],
    externalLinks: [
      { href: "https://www.statista.com/topics/1521/beauty-salon-industry/", label: "Statista: Beauty Salon Industry" },
      { href: "https://www.imy.se/verksamhet/dataskydd/", label: "IMY: GDPR for service businesses" },
    ],
    cta: {
      headline: "Run your entire salon from one screen",
      body: "Bookings, POS, loyalty, and inventory — all in Varuflow.",
      buttonLabel: "Start 14-day free trial",
      href: "/en/trial",
    },
    bodyHtml: `<h2 id="the-3-tool-problem">The 3-tool problem</h2>
<p>The average salon uses: a booking platform (Treatwell, Fresha), a POS (Zettle), a loyalty app, and a spreadsheet for product inventory. Cost: €150–350/month combined, plus daily reconciliation friction. When a client asks about her loyalty points mid-checkout, you're switching between three apps to find the answer.</p>
<h2 id="booking-requirements">What your booking system must do</h2>
<ul><li>Online booking 24/7 (reduces no-shows by 30–45%)</li>
<li>SMS and email reminders with cancellation link</li>
<li>Multi-staff calendars with service duration buffers</li>
<li>Deposit collection for premium services or repeat no-shows</li>
<li>Multi-service package bookings without double-booking</li></ul>
<h2 id="pos-requirements">Point-of-sale requirements</h2>
<ul><li>Pre-populate services from the linked booking</li>
<li>Contactless card payment (Zettle/Stripe Terminal)</li>
<li>Split payment support</li>
<li>Tip recording per staff member for payroll</li>
<li>Digital receipts (email) for GDPR compliance</li></ul>
<h2 id="loyalty-design">Designing loyalty that works</h2>
<table><thead><tr><th>Factor</th><th>Works</th><th>Doesn't work</th></tr></thead>
<tbody>
<tr><td>Earning</td><td>Points per currency unit (1 pt per 10 kr)</td><td>Complex tier calculations</td></tr>
<tr><td>Threshold</td><td>Low and achievable (100 pts = 100 kr)</td><td>Too high — clients give up</td></tr>
<tr><td>Visibility</td><td>Balance on receipt + SMS</td><td>Hidden until redemption</td></tr>
</tbody></table>
<h2 id="client-records-gdpr">Client records and GDPR</h2>
<p>Allergy records are special category data under GDPR — obtain explicit consent. Store only name, one contact method, and service preferences. Honour deletion requests for inactive clients. Varuflow's client records include built-in consent flags and automated deletion workflows.</p>
<h2 id="faq">FAQ</h2>
<h3>Do we need a separate booking website?</h3>
<p>No. Varuflow generates a shareable booking link for Instagram bio, Google Business, and your website.</p>`,
  },

  // ─── 9. Multi-Warehouse Inventory (EN) ────────────────────────────────────
  {
    _id: "multi-warehouse-inventory-guide-retailers",
    slug: "multi-warehouse-inventory-complete-guide-growing-retailers",
    title: "Multi-Warehouse Inventory: A Complete Guide for Growing Retailers",
    excerpt:
      "Managing stock across multiple warehouses doesn't have to mean spreadsheet chaos. Here's the complete playbook — from location codes and transfer orders to demand forecasting.",
    category: "vertical",
    tags: ["inventory", "warehouse", "multi-location", "retail", "logistics"],
    locale: "en",
    author: ERIK,
    publishedAt: "2026-05-05",
    updatedAt: "2026-05-05",
    seoTitle: "Multi-Warehouse Inventory: Complete Guide for Growing Retailers (2026)",
    seoDescription:
      "Managing stock across multiple warehouses doesn't have to mean spreadsheet chaos. Here's the complete playbook for growing retailers.",
    readingTimeMinutes: 10,
    featuredImageAlt: "Multi-warehouse inventory dashboard showing stock levels across locations",
    leadMagnet: {
      title: "Multi-Warehouse Setup Checklist",
      description: "A 27-point checklist for setting up multi-warehouse inventory from location codes to transfer protocols.",
      pdfSlug: "multi-warehouse-checklist",
      buttonLabel: "Download free checklist",
    },
    tableOfContents: [
      { id: "when-you-need-multi-wh", title: "When single-warehouse breaks down", level: 2 },
      { id: "key-concepts", title: "Key concepts: bins, locations, zones", level: 2 },
      { id: "transfer-orders", title: "Inter-warehouse transfers", level: 2 },
      { id: "rotation-strategies", title: "FIFO, LIFO, FEFO", level: 2 },
      { id: "kpis", title: "KPIs to track per warehouse", level: 2 },
      { id: "faq", title: "FAQ", level: 2 },
    ],
    internalLinks: [
      { href: "/en/features", label: "Varuflow inventory features" },
      { href: "/en/verticals/retail", label: "Varuflow for retailers" },
      { href: "/en/trial", label: "Start 14-day trial" },
    ],
    externalLinks: [
      { href: "https://www.gs1.org/standards/barcodes", label: "GS1: Barcode Standards" },
      { href: "https://www.skatteverket.se/foretagochorganisationer/handel.4.18e1b10334ebe8bc80004500.html", label: "Skatteverket: Trade regulations" },
    ],
    cta: {
      headline: "Multi-warehouse, zero spreadsheets",
      body: "Unlimited warehouses, real-time stock, automated reorder. All included in Varuflow Pro.",
      buttonLabel: "Start 14-day free trial",
      href: "/en/trial",
    },
    bodyHtml: `<h2 id="when-you-need-multi-wh">When single-warehouse breaks down</h2>
<p>You need multi-warehouse management when: stock goes to a second location and you lose track, customers order online from one location while stock is at another, or staff email each other to check inventory. At any of these points, spreadsheets become unreliable.</p>
<h2 id="key-concepts">Key concepts: bins, locations, zones</h2>
<table><thead><tr><th>Level</th><th>Example</th><th>Scope</th></tr></thead>
<tbody>
<tr><td>Warehouse</td><td>STHLM-01</td><td>Legal entity + address</td></tr>
<tr><td>Zone</td><td>A (ambient), B (refrigerated)</td><td>Environmental area</td></tr>
<tr><td>Aisle/Row</td><td>A-03</td><td>Navigation within zone</td></tr>
<tr><td>Bin</td><td>A-03-02-L</td><td>Specific storage unit</td></tr>
</tbody></table>
<h2 id="transfer-orders">Inter-warehouse transfers</h2>
<p>Every stock move between locations needs a transfer order recording: origin, destination, SKUs/quantities, authorizing manager, and transit date. This creates accounting integrity (inventory value moves with stock) and traceability. A system that lets you silently subtract and add without a transfer document creates audit failures.</p>
<h2 id="rotation-strategies">FIFO, LIFO, FEFO</h2>
<ul><li><strong>FIFO:</strong> Pick oldest stock first. Standard for retail. Required for perishables.</li>
<li><strong>FEFO:</strong> Pick soonest-expiring first. Essential for food, pharma, cosmetics.</li>
<li><strong>LIFO:</strong> Rarely used for physical goods (more of an accounting concept).</li></ul>
<h2 id="kpis">KPIs to track per warehouse</h2>
<table><thead><tr><th>KPI</th><th>Formula</th><th>Target</th></tr></thead>
<tbody>
<tr><td>Inventory turnover</td><td>COGS / Avg inventory</td><td>6–12x/year</td></tr>
<tr><td>Stock accuracy</td><td>System / Physical count</td><td>&gt;99%</td></tr>
<tr><td>Pick accuracy</td><td>Correct picks / Total</td><td>&gt;99.5%</td></tr>
<tr><td>Days on hand</td><td>Stock / Daily sales</td><td>14–30 days</td></tr>
</tbody></table>
<h2 id="faq">FAQ</h2>
<h3>Does multi-warehouse require the Enterprise plan?</h3>
<p>No. Multi-warehouse is included in Varuflow Pro (599 SEK/month). No surcharge per location.</p>`,
  },

  // ─── 10. Founder Story (EN) ──────────────────────────────────────────────
  {
    _id: "moroccan-founder-swedish-compliance-software-en",
    slug: "moroccan-founder-built-better-swedish-compliance-software",
    title: "Why a Moroccan Founder Built Better Swedish Compliance Software Than Swedish Startups",
    excerpt:
      "Youssef Benali didn't set out to build compliance software. He was running a wholesale operation in Stockholm — and every tool he tried made him angry.",
    category: "founder-story",
    tags: ["founder-story", "compliance", "Nordic", "MENA", "startup"],
    locale: "en",
    translationSlug: "marockansk-grundare-svensk-compliance-mjukvara-sv",
    author: YOUSSEF,
    publishedAt: "2026-05-07",
    updatedAt: "2026-05-07",
    seoTitle: "Why a Moroccan Founder Built Better Swedish Compliance Software",
    seoDescription:
      "Youssef Benali didn't set out to build compliance software. He was running a wholesale business in Stockholm and hating every tool available.",
    readingTimeMinutes: 12,
    featuredImageAlt: "Youssef Benali, founder of Varuflow, at the Stockholm office",
    tableOfContents: [
      { id: "before-varuflow", title: "Before Varuflow: a wholesale nightmare", level: 2 },
      { id: "why-fortnox-failed", title: "Why Fortnox wasn't the answer", level: 2 },
      { id: "the-outsider-advantage", title: "The outsider advantage", level: 2 },
      { id: "building-for-mena", title: "Building for MENA too", level: 2 },
      { id: "current-state", title: "Where Varuflow is today", level: 2 },
    ],
    internalLinks: [
      { href: "/en/about", label: "About Varuflow" },
      { href: "/en/compliance", label: "Varuflow compliance features" },
      { href: "/en/regions/se", label: "Varuflow for Sweden" },
      { href: "/en/trial", label: "Try Varuflow free" },
    ],
    externalLinks: [
      { href: "https://www.tillvaxtverket.se/statistik/foretagande/utlandska-foretagare.html", label: "Tillväxtverket: Utrikes-födda företagare" },
      { href: "https://www.riksdagen.se/sv/dokument-och-lagar/dokument/svensk-forfattningssamling/bokforingslag-19991078_sfs-1999-1078/", label: "Bokföringslagen (SFS 1999:1078)" },
    ],
    cta: {
      headline: "Try the software we wish we'd had",
      body: "No sales call. No contract. 14 days free — full Pro features.",
      buttonLabel: "Start free trial",
      href: "/en/trial",
    },
    bodyHtml: `<h2 id="before-varuflow">Before Varuflow: a wholesale nightmare</h2>
<p>In 2021 I was running a small import/distribution business in Stockholm — personal care products sourced from Morocco and the UAE, sold through Swedish pharmacies and beauty retailers. 8 SKUs, 40 customers, two employees including myself. My software stack: Fortnox for invoicing, Excel for inventory, iZettle for cash sales, WhatsApp for customer reorders. Every month-end meant an afternoon manually reconciling what I'd sold with what I'd billed.</p>
<p>I searched for one tool that could handle inventory + invoicing + B2B ordering. What I found was either tools built for accounting (Fortnox, Bokio) that treated inventory as an afterthought, e-commerce tools (Shopify) with Swedish compliance bolted on awkwardly, or enterprise systems (Odoo, SAP) that required a 3-month implementation I couldn't afford.</p>
<h2 id="why-fortnox-failed">Why Fortnox wasn't the answer</h2>
<p>Fortnox is excellent software for what it's designed for. The problem is it's built from the accountant's perspective, not the operator's. Checking stock levels meant leaving Fortnox for Excel. Receiving a batch from Morocco meant entering it in three separate places. When a B2B customer wanted an order portal, there was no answer. And when I needed ZATCA-compliant invoices for a Saudi retailer, Fortnox simply couldn't help.</p>
<h2 id="the-outsider-advantage">The outsider advantage</h2>
<p>I arrived at Swedish compliance from the outside, through frustration. Coming from Morocco (Code du Commerce), working with Saudi clients (ZATCA), I had to learn Bokföringslagen from scratch — no assumptions, no shortcuts. I read SFS 1999:1078 before writing my first line of code.</p>
<blockquote>The outsider reading produced better software. Because I wasn't weighed down by "how it's always been done," I asked: what does the law actually require? Often the answer was simpler than how incumbents had implemented it.</blockquote>
<p>Swedish software companies had built Bokföringslagen compliance by cargo-culting each other's decade-old implementations. The 7-year retention rule, for example, is often implemented as "never delete anything." The law says nothing of the sort — it specifies exactly what must be retained. That clarity opened up GDPR-compliant architecture incumbents claimed was impossible.</p>
<h2 id="building-for-mena">Building for MENA too</h2>
<p>ZATCA Phase 2's technical requirements — cryptographic signing, real-time API submission, hash chaining — taught us things we applied back to the Swedish stack. Building for both regions simultaneously meant we couldn't afford assumptions. Every "it has to be this way" belief was tested when we crossed compliance jurisdictions.</p>
<p>Being trilingual (Arabic, French, Swedish) helped enormously. Arabic government documentation is often more detailed than English summaries. Building Arabic RTL support as a first-class concern rather than an afterthought meant the MENA customer portal actually works well.</p>
<h2 id="current-state">Where Varuflow is today</h2>
<p>We started with 8 SKUs in my own warehouse in 2022. Today Varuflow serves hundreds of businesses across Sweden, Saudi Arabia, and the UAE. The product has grown from "my inventory tool" to a platform with B2B ordering portals, POS, AI action cards, loyalty programs, and multi-warehouse management. The core hasn't changed: built for operators — the people using it every day — not accountants reviewing it once a year.</p>
<p>If you're a Swedish wholesaler drowning in spreadsheets, or a Saudi retailer anxious about ZATCA: <a href="/en/trial">try Varuflow free for 14 days</a>. No sales call. No implementation project.</p>
<p><em>— Youssef Benali, Stockholm, May 2026</em></p>`,
  },
];
