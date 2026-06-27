// File: src/app/[locale]/(marketing)/bransch/[slug]/industries.ts
// Purpose: Source of truth for the Swedish industry landing pages.
// Consumed by: page.tsx (rendering + generateStaticParams + metadata)
// and scripts/test_seo_pages.mjs (build-time sanity check).
//
// The slug vocabulary is intentionally fixed — adding a new industry
// needs a code change (so the metadata + translations stay aligned).

export type IndustrySlug =
  | "grossist"
  | "livsmedel"
  | "byggmaterial"
  | "klaeder"
  | "elektronik";

export interface IndustryCopy {
  slug: IndustrySlug;
  /** H1 on the landing page. */
  headline: string;
  /** Short paragraph under the headline. */
  subheadline: string;
  /** 4–6 short bullet points — rendered as a feature list. */
  features: string[];
  /** SEO meta title. Kept <60 chars where possible. */
  metaTitle: string;
  /** SEO meta description. Target 140–160 chars. */
  metaDescription: string;
  /** Social-proof placeholder shown above the CTA. */
  socialProof: string;
}

export const INDUSTRIES: IndustryCopy[] = [
  {
    slug: "grossist",
    headline: "Grossistlösning byggd för svenska B2B-företag",
    subheadline:
      "Varuflow samlar lager, fakturering och kassaflöde på ett ställe — byggt för svenska grossister som säljer till butiker och återförsäljare.",
    features: [
      "Lagerstatus i realtid över flera lager",
      "B2B-portal där kunder lägger order direkt",
      "Fakturaunderlag med 25/12/6 % moms och Fortnox-koppling",
      "Automatiska påminnelser vid sen betalning",
      "Efterfrågeprognos baserad på historiska rörelser",
    ],
    metaTitle: "Grossist-system — lager + fakturering | Varuflow",
    metaDescription:
      "Varuflow är affärssystemet för svenska grossister: realtidslager, automatisk fakturering, Fortnox-integration och B2B-portal. Starta gratis.",
    socialProof: "Används av växande svenska grossister över hela landet.",
  },
  {
    slug: "livsmedel",
    headline: "Livsmedelsgrossister — håll koll på bäst-före och batcher",
    subheadline:
      "Hantera kylvaror, batchnummer och korta hållbarhetstider. Varuflow är byggt för svenska livsmedelsbranschen med 12 % moms som standard.",
    features: [
      "Batch-spårning och bäst-före-datum per artikel",
      "Lageralert innan varor utgår",
      "12 % moms förinställd på alla livsmedelsartiklar",
      "Snabb orderinläsning via streckkod",
      "Exportera till Fortnox för bokföring",
    ],
    metaTitle: "Livsmedelsgrossist — system för batch & moms | Varuflow",
    metaDescription:
      "Varuflow hjälper svenska livsmedelsgrossister med batch-spårning, bäst-före-datum och 12 % moms. Integration med Fortnox. Starta gratis.",
    socialProof: "Designat tillsammans med svenska livsmedelsgrossister.",
  },
  {
    slug: "byggmaterial",
    headline: "Byggmaterial — från lagerhylla till slutfaktura",
    subheadline:
      "Stora artiklar, långa leveranstider och komplicerade order — Varuflow hanterar byggbranschens flöden från inköp till bokföring.",
    features: [
      "Inköpsorder med leverantörsuppföljning",
      "Order- och faktureringsstöd för stora projekt",
      "Leveranstidsspårning per leverantör",
      "Integration med Fortnox och svensk e-faktura (Peppol)",
      "Lagerrörelser per lager och plats",
    ],
    metaTitle: "Byggmaterial-grossist — affärssystem | Varuflow",
    metaDescription:
      "Varuflow är affärssystemet för svenska byggmaterialgrossister: inköpsorder, leveranstidsspårning, Peppol e-faktura och Fortnox. Starta gratis.",
    socialProof: "Skräddarsytt för svenska byggmaterialföretag.",
  },
  {
    slug: "klaeder",
    headline: "Kläder & mode — storlekar, säsonger, returer",
    subheadline:
      "Hantera varianter per storlek och färg, säsongsinventering och retur-flöden. Byggt för svenska modegrossister och e-handlare.",
    features: [
      "Varianter per storlek och färg med eget SKU",
      "Säsongsbaserad efterfrågeprognos",
      "Returhantering och krediteringsfakturor",
      "Snabb prisuppdatering inför kampanjer",
      "25 % moms och svensk bokföring direkt",
    ],
    metaTitle: "Klädgrossist — lager & fakturering | Varuflow",
    metaDescription:
      "Varuflow hjälper svenska klädgrossister med storleksvarianter, säsongslager, returer och fakturering. Fortnox-integration. Starta gratis.",
    socialProof: "Byggt tillsammans med svenska modeföretag.",
  },
  {
    slug: "elektronik",
    headline: "Elektronik — serienummer, garanti, snabb rotation",
    subheadline:
      "Spåra serienummer, garantiperioder och snabbrörliga elektronikprodukter. Kraftfullt lager med svensk fakturering och Fortnox direkt.",
    features: [
      "Serienummer per artikel med garantistart",
      "Snabb efterfrågeprognos för hög rotation",
      "Koppla Fortnox och exportera till SIE4",
      "B2B-portal för återförsäljare",
      "Streckkod och QR-skanning i mobilen",
    ],
    metaTitle: "Elektronikgrossist — serienummer & lager | Varuflow",
    metaDescription:
      "Varuflow är affärssystemet för svenska elektronikgrossister: serienummer, garantispårning, Fortnox och SIE4-export. Starta gratis.",
    socialProof: "Används av svenska elektronikföretag i tillväxt.",
  },
];

export const INDUSTRY_SLUGS: IndustrySlug[] = INDUSTRIES.map((i) => i.slug);

export function getIndustry(slug: string): IndustryCopy | undefined {
  return INDUSTRIES.find((i) => i.slug === slug);
}
