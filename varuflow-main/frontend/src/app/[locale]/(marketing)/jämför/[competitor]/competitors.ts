// File: src/app/[locale]/(marketing)/jämför/[competitor]/competitors.ts
// Purpose: Source of truth for the comparison landing pages.
// Consumed by: page.tsx and scripts/test_seo_pages.mjs.
//
// The 8 dimensions are the same across every competitor page so the
// comparison table is structurally comparable. Changing the dimension
// list means every competitor row needs an entry — enforced at build.

export type CompetitorSlug = "fortnox" | "visma" | "excel" | "specter";

export const COMPARE_DIMENSIONS = [
  "Lager i realtid",
  "Svensk fakturering (25/12/6 %)",
  "Fortnox-integration",
  "B2B-portal för kunder",
  "Automatiska betalpåminnelser",
  "Efterfrågeprognos",
  "Mobil streckkodsskanning",
  "Pris från (kr/mån)",
] as const;

export type DimensionRow = {
  [K in (typeof COMPARE_DIMENSIONS)[number]]: string;
};

export interface CompetitorCopy {
  slug: CompetitorSlug;
  /** Display name used in headlines and tables. */
  displayName: string;
  /** SEO meta title — follows the "Varuflow vs X — Sveriges bästa alternativ 2026" pattern. */
  metaTitle: string;
  /** SEO meta description — 140–160 chars, Swedish. */
  metaDescription: string;
  /** One-line positioning statement. */
  tagline: string;
  /** Cells for Varuflow column. "Ja" / "Nej" / free-form strings. */
  varuflow: DimensionRow;
  /** Cells for the competitor column. */
  competitor: DimensionRow;
}

const yes = "Ja";
const no = "Nej";

// Prices are public list prices as of April 2026. Kept in a data file
// so marketing can update them without touching layout.
export const COMPETITORS: CompetitorCopy[] = [
  {
    slug: "fortnox",
    displayName: "Fortnox",
    metaTitle: "Varuflow vs Fortnox — Sveriges bästa alternativ 2026",
    metaDescription:
      "Jämför Varuflow och Fortnox: lager, fakturering, B2B-portal, prognoser och priser. Se varför svenska grossister byter 2026.",
    tagline:
      "Fortnox är starkt på bokföring. Varuflow är byggt för företag som också behöver riktigt lager och B2B-flöden.",
    varuflow: {
      "Lager i realtid": yes,
      "Svensk fakturering (25/12/6 %)": yes,
      "Fortnox-integration": yes,
      "B2B-portal för kunder": yes,
      "Automatiska betalpåminnelser": yes,
      "Efterfrågeprognos": yes,
      "Mobil streckkodsskanning": yes,
      "Pris från (kr/mån)": "0",
    },
    competitor: {
      "Lager i realtid": "Begränsat",
      "Svensk fakturering (25/12/6 %)": yes,
      "Fortnox-integration": "Native",
      "B2B-portal för kunder": no,
      "Automatiska betalpåminnelser": yes,
      "Efterfrågeprognos": no,
      "Mobil streckkodsskanning": no,
      "Pris från (kr/mån)": "249",
    },
  },
  {
    slug: "visma",
    displayName: "Visma eEkonomi",
    metaTitle: "Varuflow vs Visma — Sveriges bästa alternativ 2026",
    metaDescription:
      "Jämför Varuflow och Visma eEkonomi: lager, fakturering, B2B-portal och prognoser. Svensk grossisthandel i praktiken.",
    tagline:
      "Visma fungerar för små tjänsteföretag. Varuflow tar hand om lager, varianter och B2B-order på köpet.",
    varuflow: {
      "Lager i realtid": yes,
      "Svensk fakturering (25/12/6 %)": yes,
      "Fortnox-integration": yes,
      "B2B-portal för kunder": yes,
      "Automatiska betalpåminnelser": yes,
      "Efterfrågeprognos": yes,
      "Mobil streckkodsskanning": yes,
      "Pris från (kr/mån)": "0",
    },
    competitor: {
      "Lager i realtid": "Tillägg",
      "Svensk fakturering (25/12/6 %)": yes,
      "Fortnox-integration": no,
      "B2B-portal för kunder": no,
      "Automatiska betalpåminnelser": yes,
      "Efterfrågeprognos": no,
      "Mobil streckkodsskanning": no,
      "Pris från (kr/mån)": "199",
    },
  },
  {
    slug: "excel",
    displayName: "Excel-kalkylblad",
    metaTitle: "Varuflow vs Excel — Sveriges bästa alternativ 2026",
    metaDescription:
      "Sluta hantera lager och fakturering i Excel. Varuflow samlar allt i ett system och sparar timmar per vecka. Starta gratis.",
    tagline:
      "Excel är flexibelt men går sönder när lager, fakturor och team växer. Varuflow tar över utan att du tappar kontrollen.",
    varuflow: {
      "Lager i realtid": yes,
      "Svensk fakturering (25/12/6 %)": yes,
      "Fortnox-integration": yes,
      "B2B-portal för kunder": yes,
      "Automatiska betalpåminnelser": yes,
      "Efterfrågeprognos": yes,
      "Mobil streckkodsskanning": yes,
      "Pris från (kr/mån)": "0",
    },
    competitor: {
      "Lager i realtid": "Manuellt",
      "Svensk fakturering (25/12/6 %)": "Manuellt",
      "Fortnox-integration": no,
      "B2B-portal för kunder": no,
      "Automatiska betalpåminnelser": no,
      "Efterfrågeprognos": no,
      "Mobil streckkodsskanning": no,
      "Pris från (kr/mån)": "0",
    },
  },
  {
    slug: "specter",
    displayName: "Specter",
    metaTitle: "Varuflow vs Specter — Sveriges bästa alternativ 2026",
    metaDescription:
      "Jämför Varuflow och Specter: lager, fakturering, B2B-portal, prognoser och priser. Svensk SaaS byggd för 2026.",
    tagline:
      "Specter är kraftfullt men tungt. Varuflow ger samma flöden i en modernare, enklare produkt.",
    varuflow: {
      "Lager i realtid": yes,
      "Svensk fakturering (25/12/6 %)": yes,
      "Fortnox-integration": yes,
      "B2B-portal för kunder": yes,
      "Automatiska betalpåminnelser": yes,
      "Efterfrågeprognos": yes,
      "Mobil streckkodsskanning": yes,
      "Pris från (kr/mån)": "0",
    },
    competitor: {
      "Lager i realtid": yes,
      "Svensk fakturering (25/12/6 %)": yes,
      "Fortnox-integration": yes,
      "B2B-portal för kunder": yes,
      "Automatiska betalpåminnelser": "Tillägg",
      "Efterfrågeprognos": "Tillägg",
      "Mobil streckkodsskanning": no,
      "Pris från (kr/mån)": "895",
    },
  },
];

export const COMPETITOR_SLUGS: CompetitorSlug[] = COMPETITORS.map(
  (c) => c.slug,
);

export function getCompetitor(slug: string): CompetitorCopy | undefined {
  return COMPETITORS.find((c) => c.slug === slug);
}
