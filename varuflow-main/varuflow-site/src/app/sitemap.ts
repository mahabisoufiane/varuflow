import type { MetadataRoute } from "next";
import { MODULES } from "@/content/modules";
import { SOLUTIONS } from "@/content/solutions";
import { routing } from "@/i18n/routing";
import { SITE_URL } from "@/lib/seo";

// Fully static route inventory: every locale-less path on the site.
// /legal/* deliberately excluded while noindexed (placeholder copy).
const PATHS = [
  "",
  "/pricing",
  "/demo",
  ...MODULES.map((m) => `/modules/${m.slug}`),
  ...SOLUTIONS.map((s) => `/solutions/${s.slug}`),
];

export default function sitemap(): MetadataRoute.Sitemap {
  return PATHS.flatMap((path) =>
    routing.locales.map((locale) => ({
      url: `${SITE_URL}/${locale}${path}`,
      lastModified: new Date(),
      changeFrequency: "weekly" as const,
      priority: path === "" ? 1 : 0.7,
      alternates: {
        languages: {
          sv: `${SITE_URL}/sv${path}`,
          en: `${SITE_URL}/en${path}`,
        },
      },
    })),
  );
}
