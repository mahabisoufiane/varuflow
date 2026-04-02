import { defineRouting } from "next-intl/routing";

export const routing = defineRouting({
  locales: ["en", "sv", "no", "da"],
  defaultLocale: "en",
  localePrefix: "as-needed",
});
