import type { Metadata } from "next";

// Marketing-site origin. varuflow.se is registered to the project (Vercel
// is provisioning certs for it); override with NEXT_PUBLIC_SITE_URL until
// DNS is final.
export const SITE_URL = process.env.NEXT_PUBLIC_SITE_URL ?? "https://varuflow.se";

/** Canonical + sv↔en hreflang alternates for a route.
 *  `path` is the locale-less pathname ("/pricing", "/modules/pos", ""). */
export function pageMetadata(opts: {
  locale: string;
  path: string;
  title: string;
  description: string;
}): Metadata {
  const { locale, path, title, description } = opts;
  return {
    title,
    description,
    alternates: {
      canonical: `${SITE_URL}/${locale}${path}`,
      languages: {
        sv: `${SITE_URL}/sv${path}`,
        en: `${SITE_URL}/en${path}`,
        "x-default": `${SITE_URL}/sv${path}`,
      },
    },
    openGraph: {
      title,
      description,
      url: `${SITE_URL}/${locale}${path}`,
      siteName: "Varuflow",
      locale: locale === "en" ? "en_US" : "sv_SE",
      type: "website",
    },
  };
}
