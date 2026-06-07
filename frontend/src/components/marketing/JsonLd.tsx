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
      lowPrice: "0",
      highPrice: "1999",
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
        price: "0",
        priceCurrency: "SEK",
        description: "Free plan for small businesses",
        url: `${BASE_URL}/en/pricing`,
      },
      {
        "@type": "Offer",
        name: "Pro",
        price: "599",
        priceCurrency: "SEK",
        description: "Full-featured plan for growing wholesalers",
        url: `${BASE_URL}/en/pricing`,
      },
      {
        "@type": "Offer",
        name: "Enterprise",
        price: "1999",
        priceCurrency: "SEK",
        description: "Unlimited plan with dedicated support",
        url: `${BASE_URL}/en/pricing`,
      },
    ],
  };
}
