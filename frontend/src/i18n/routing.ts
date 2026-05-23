import { defineRouting } from "next-intl/routing";

export const routing = defineRouting({
  locales: ["sv", "en", "ar"],
  defaultLocale: "sv",
  localePrefix: "as-needed",
});
