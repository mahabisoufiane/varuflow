// Region-specific landing page data — SE, SA, AE, MA

export type RegionSlug = "se" | "sa" | "ae" | "ma";

export const REGION_SLUGS: RegionSlug[] = ["se", "sa", "ae", "ma"];

export interface RegionFeature {
  title: string;
  description: string;
}

export interface RegionData {
  slug: RegionSlug;
  locale: string;          // BCP 47 locale for OG / hreflang
  dir: "ltr" | "rtl";
  currency: string;        // ISO 4217
  metaTitle: string;
  metaDescription: string;
  eyebrow: string;
  headline: string;
  subheadline: string;
  ctaLabel: string;
  complianceHighlights: string[];
  features: RegionFeature[];
  pricingFrom: string;
}

export const REGIONS: RegionData[] = [
  {
    slug: "se",
    locale: "sv_SE",
    dir: "ltr",
    currency: "SEK",
    metaTitle: "Varuflow Sverige — Lager & Fakturering för Svenska Företag",
    metaDescription:
      "Varuflow är byggt för svenska grossister: Bokföringslagen, BankID, Kivra, Peppol och 25/12/6%-moms. Starta gratis.",
    eyebrow: "Byggt för den svenska marknaden",
    headline: "Allt en svensk grossist behöver — i ett system",
    subheadline:
      "Lager i realtid, fakturering med rätt moms, B2B-kundportal, Peppol, Kivra och BankID-stöd. GDPR-kompatibelt med EU-datalagring.",
    ctaLabel: "Starta gratis",
    complianceHighlights: [
      "Bokföringslagen-kompatibel SIE-export",
      "25%, 12% och 6% moms",
      "Peppol BIS 3.0 e-faktura",
      "Kivra-integration (digital brevlåda)",
      "BankID för kundportalen",
      "EU-datalagring (GDPR)",
    ],
    features: [
      {
        title: "Automatisk moms & faktureringsstöd",
        description:
          "Rätt momssats på varje rad automatiskt. Exportera SIE-filer direkt till din revisor.",
      },
      {
        title: "Peppol & e-faktura",
        description:
          "Skicka Peppol BIS 3.0-fakturor till offentlig sektor och stora bolag utan extramodul.",
      },
      {
        title: "Kivra & BankID",
        description:
          "Leverera fakturor till kundens digitala brevlåda via Kivra. Stöd för BankID-inloggning i kundportalen.",
      },
    ],
    pricingFrom: "0 SEK/mån",
  },
  {
    slug: "sa",
    locale: "ar_SA",
    dir: "rtl",
    currency: "SAR",
    metaTitle: "Varuflow — نظام إدارة المخزون والفواتير للمملكة العربية السعودية",
    metaDescription:
      "منصة متوافقة مع متطلبات هيئة الزكاة والضريبة والجمارك (زاتكا). فواتير إلكترونية، مخزون في الوقت الفعلي، بوابة عملاء B2B. ابدأ مجاناً.",
    eyebrow: "مصمم للسوق السعودي",
    headline: "نظام متكامل متوافق مع زاتكا للشركات السعودية",
    subheadline:
      "فوترة إلكترونية متوافقة مع متطلبات زاتكا (المرحلة الأولى والثانية)، إدارة المخزون، وبوابة عملاء B2B — كل ذلك في منصة واحدة.",
    ctaLabel: "ابدأ مجاناً",
    complianceHighlights: [
      "متوافق مع زاتكا المرحلة 1 و2",
      "رمز QR على كل فاتورة",
      "ضريبة القيمة المضافة 15%",
      "تخزين البيانات محلياً",
      "تقارير الاستحقاق بالريال السعودي",
      "واجهة عربية بالكامل",
    ],
    features: [
      {
        title: "الفوترة الإلكترونية المتوافقة مع زاتكا",
        description:
          "أنشئ فواتير إلكترونية معتمدة مع رمز QR وأرسلها مباشرة إلى منصة فاتورة.",
      },
      {
        title: "إدارة المخزون في الوقت الفعلي",
        description:
          "تتبع مستويات المخزون عبر جميع المستودعات مع تنبيهات إعادة الطلب التلقائية.",
      },
      {
        title: "بوابة عملاء B2B",
        description:
          "أعطِ عملاءك بوابة احترافية لوضع الطلبات ومتابعة الفواتير وتتبع التسليم.",
      },
    ],
    pricingFrom: "0 SAR/شهر",
  },
  {
    slug: "ae",
    locale: "ar_AE",
    dir: "rtl",
    currency: "AED",
    metaTitle: "Varuflow UAE — Inventory & Invoicing for UAE Businesses",
    metaDescription:
      "UAE VAT-compliant invoicing, real-time inventory, and B2B portal. FTA-ready with Arabic and English interface. Start free.",
    eyebrow: "Built for UAE businesses",
    headline: "FTA-compliant invoicing & inventory for the UAE",
    subheadline:
      "Manage VAT invoices, inventory, and B2B customers with full Arabic/English support and FTA-compliant reporting. AED pricing.",
    ctaLabel: "Start free",
    complianceHighlights: [
      "UAE VAT (5%) compliant",
      "FTA-ready tax invoices",
      "Arabic + English interface",
      "AED pricing",
      "Peppol support",
      "EU + regional data hosting",
    ],
    features: [
      {
        title: "UAE VAT invoicing",
        description:
          "Generate tax invoices that meet FTA requirements — with mandatory fields, TRN, and proper VAT treatment.",
      },
      {
        title: "Arabic / English bilingual",
        description:
          "Switch the entire interface between Arabic (RTL) and English at any time. Invoices print in your preferred language.",
      },
      {
        title: "Multi-currency",
        description:
          "Sell in AED, USD, or EUR. Exchange rates from open banking APIs — automatically applied to invoices.",
      },
    ],
    pricingFrom: "0 AED/month",
  },
  {
    slug: "ma",
    locale: "fr_MA",
    dir: "ltr",
    currency: "MAD",
    metaTitle: "Varuflow Maroc — Gestion de Stock et Facturation (Prix PPP)",
    metaDescription:
      "Logiciel de gestion d'inventaire et de facturation pour les entreprises marocaines. Tarification PPP en MAD. Interface française et arabe.",
    eyebrow: "Conçu pour le marché marocain",
    headline: "Gérez votre stock et vos factures — au prix du marché local",
    subheadline:
      "Tarification ajustée au pouvoir d'achat marocain (PPP), interface en français et arabe, TVA marocaine, et facturation PDF/XLS conforme.",
    ctaLabel: "Démarrer gratuitement",
    complianceHighlights: [
      "TVA marocaine (20% / 14% / 10% / 7%)",
      "Facturation PDF et XLS",
      "DH (MAD) natif",
      "Interface français + arabe",
      "Tarification PPP",
      "Export comptable",
    ],
    features: [
      {
        title: "Facturation avec TVA marocaine",
        description:
          "Prend en charge les taux TVA marocains standard. Génère des factures conformes en PDF avec numérotation séquentielle.",
      },
      {
        title: "Gestion des stocks en temps réel",
        description:
          "Suivez les niveaux de stock dans tous vos entrepôts. Alertes de réapprovisionnement automatiques en MAD.",
      },
      {
        title: "Portail client B2B",
        description:
          "Donnez à vos clients professionnels un portail pour passer des commandes, consulter les factures, et suivre les livraisons.",
      },
    ],
    pricingFrom: "0 MAD/mois",
  },
];

export function getRegion(slug: string): RegionData | undefined {
  return REGIONS.find((r) => r.slug === slug);
}
