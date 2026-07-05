import { defineRouting } from "next-intl/routing";

export const routing = defineRouting({
  locales: ["sv", "en", "no", "da", "ar"],
  defaultLocale: "sv",
  // "always": every locale (incl. the default sv) carries a URL prefix, so app
  // routes are /sv/… and never collide with the prefix-less public routes
  // (/shop, /quotes/[token], /portal, /q, /meet, /forms). Sweden-first.
  localePrefix: "always",
});
