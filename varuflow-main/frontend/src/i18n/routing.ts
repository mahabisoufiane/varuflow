import { defineRouting } from "next-intl/routing";

export const routing = defineRouting({
  locales: ["sv", "en", "no", "da", "ar"],
  defaultLocale: "sv",
  localePrefix: "as-needed",
});
