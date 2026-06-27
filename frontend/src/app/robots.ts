import type { MetadataRoute } from "next";

// Public base URL — read from env so preview deployments produce
// their own robots.txt without leaking the production canonical.
const BASE_URL =
  process.env.NEXT_PUBLIC_SITE_URL ?? "https://varuflow.vercel.app";

export default function robots(): MetadataRoute.Robots {
  return {
    rules: [
      {
        userAgent: "*",
        allow: "/",
        // Block authenticated app surfaces, customer portal, and auth flows
        // from being crawled. next-intl handles localized prefixes, so the
        // patterns must match against any /[locale]/ prefix.
        disallow: [
          "/*/dashboard",
          "/*/analytics",
          "/*/inventory",
          "/*/invoices",
          "/*/customers",
          "/*/recurring",
          "/*/pos",
          "/*/ai",
          "/*/settings",
          "/*/onboarding",
          "/*/auth",
          "/portal",
          "/api",
        ],
      },
    ],
    sitemap: `${BASE_URL}/sitemap.xml`,
    host: BASE_URL,
  };
}
