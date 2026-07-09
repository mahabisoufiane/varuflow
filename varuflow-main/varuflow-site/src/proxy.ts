// Next 16 file convention: proxy.ts (middleware.ts is deprecated).
// Delegates to next-intl for locale detection + prefix routing.
import createIntlProxy from "next-intl/middleware";
import type { NextRequest } from "next/server";
import { routing } from "./i18n/routing";

const handleI18nRouting = createIntlProxy(routing);

export function proxy(request: NextRequest) {
  return handleI18nRouting(request);
}

export const config = {
  matcher: "/((?!api|_next|_vercel|.*\\..*).*)",
};
