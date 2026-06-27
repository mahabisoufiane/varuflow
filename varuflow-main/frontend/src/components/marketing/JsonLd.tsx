// JsonLd — injects a JSON-LD <script> block for structured data.
// Uses next/script to avoid the React 19 raw-script warning during client navigation.
import Script from "next/script";

interface JsonLdProps {
  data: Record<string, unknown>;
  id?: string;
}

export default function JsonLd({ data, id = "jsonld" }: JsonLdProps) {
  return (
    <Script
      id={id}
      type="application/ld+json"
      // nosemgrep: typescript.react.security.audit.react-dangerouslysetinnerhtml.react-dangerouslysetinnerhtml
      dangerouslySetInnerHTML={{ __html: JSON.stringify(data) }}
    />
  );
}

// ---- Preset schema builders ------------------------------------------------

const BASE_URL = process.env.NEXT_PUBLIC_SITE_URL ?? "https://varuflow.vercel.app";

export function organizationSchema() {
  return {
    "@context": "https://schema.org",
    "@type": "Organization",
    name: "Varuflow",
    url: BASE_URL,
    logo: `${BASE_URL}/logo.png`,
    sameAs: ["https://varuflow.se"],
    contactPoint: {
      "@type": "ContactPoint",
      contactType: "customer support",
      email: "support@varuflow.se",
      availableLanguage: ["English", "Swedish", "Arabic"],
    },
  };
}

export function softwareApplicationSchema(description?: string) {
  return {
    "@context": "https://schema.org",
    "@type": "SoftwareApplication",
    name: "Varuflow",
    applicationCategory: "BusinessApplication",
    operatingSystem: "Web, iOS, Android",
    description: description ?? "Inventory and invoicing platform for Nordic wholesalers",
    offers: {
      "@type": "AggregateOffer",
      lowPrice: "499",
      highPrice: "3990",
      priceCurrency: "SEK",
      offerCount: "3",
    },
    url: BASE_URL,
  };
}

export function pricingOfferSchema() {
  return {
    "@context": "https://schema.org",
    "@type": "ItemList",
    name: "Varuflow Pricing Plans",
    itemListElement: [
      {
        "@type": "Offer",
        name: "Starter",
        price: "499",
        priceCurrency: "SEK",
        description: "For small wholesale businesses — up to 500 products, 150 customers, Fortnox integration",
        url: `${BASE_URL}/en/pricing`,
      },
      {
        "@type": "Offer",
        name: "Professional",
        price: "1490",
        priceCurrency: "SEK",
        description: "For growing wholesale teams — unlimited customers and invoices, mobile app, advanced analytics",
        url: `${BASE_URL}/en/pricing`,
      },
      {
        "@type": "Offer",
        name: "Enterprise",
        price: "3990",
        priceCurrency: "SEK",
        description: "For large operations — unlimited everything, API access, custom integrations, white-label",
        url: `${BASE_URL}/en/pricing`,
      },
    ],
  };
}
