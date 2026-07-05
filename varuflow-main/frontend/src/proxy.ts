import { createServerClient } from "@supabase/ssr";
import createIntlMiddleware from "next-intl/middleware";
import { type NextRequest, NextResponse } from "next/server";
import { routing } from "./i18n/routing";

const handleI18nRouting = createIntlMiddleware(routing);

const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL || "";
const supabaseKey =
  process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY ||
  process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_DEFAULT_KEY ||
  "";

// Paths under (app) that require authentication.
// Every directory under src/app/[locale]/(app)/ must appear here so that
// unauthenticated requests are redirected to /auth/login rather than
// rendering a blank page. Verified against the filesystem in Phase 6 (M-11).
const PROTECTED_SEGMENTS = [
  "dashboard",
  "inventory",
  "invoices",
  "customers",
  "settings",
  "analytics",
  "ai",
  "pos",
  "recurring",
  "shop",
  "crm",
  "hr",
  "manufacturing",
  "projects",
  "work",
  "scheduling",
  "purchase-requests",
  "petty-cash",
  "reports",
  "portal-admin",
  "quotes",
  "payment-options",
  "deposits",
  "after-sales",
  "mena",
  "integrations",
  "mobile",
  "multi-entity",
  "franchise",
  "ceo",
  "growth",
  "governance",
  "job-cards",
  "time-tracking",
  "email-templates",
  "sms-outbox",
  "local-payments",
  "reconciliation",
  "merchant-subscriptions",
  "landed-costs",
  "vendor-ratings",
  "kitting",
  "dashboard-builder",
  "report-builder",
  "cashflow-prediction",
  "anomaly-detection",
  "cohort-analysis",
  "contract-signing",
  "gdpr",
  "compliance",
  "sustainability",
  "investor",
  "marketing",
  "ops",
  "customer-app",
  "b2b",
  "trust",
  "customer-service",
  "trust-safety",
  "inbox",
  "reporting",
  "ai-tools",
  // M-11 additions — routes present in (app) but missing from this list:
  "accounting",
  "admin",
  "bookings",
  "budget",
  "campaigns",
  "documents",
  "expenses",
  "gift-cards",
  "partner",
  "referrals",
  "reviews",
];

function stripLocale(pathname: string): string {
  return pathname.replace(/^\/(sv|en|no|da|ar)(\/|$)/, "/");
}

function getLocalePrefix(pathname: string): string {
  const match = pathname.match(/^\/(sv|en|no|da|ar)(\/|$)/);
  return match ? `/${match[1]}` : "";
}

export async function proxy(request: NextRequest) {
  // Portal routes are standalone — skip i18n and auth entirely
  if (request.nextUrl.pathname.startsWith("/portal")) {
    return NextResponse.next();
  }

  // Public quote acceptance pages (/quotes/{token}) are standalone — no auth, no i18n
  if (request.nextUrl.pathname.startsWith("/quotes/")) {
    return NextResponse.next();
  }

  // Public storefront routes (/shop/{slug}/...) are outside locale routing —
  // skip auth and i18n. Admin shop routes are under /[locale]/(app)/shop/...
  // which always carry a locale prefix and are caught by PROTECTED_SEGMENTS.
  if (request.nextUrl.pathname.startsWith("/shop")) {
    return NextResponse.next();
  }

  // Public meeting scheduler and lead form pages
  if (request.nextUrl.pathname.startsWith("/meet")) {
    return NextResponse.next();
  }
  if (request.nextUrl.pathname.startsWith("/forms")) {
    return NextResponse.next();
  }

  // Public quote acceptance pages — no auth, no i18n
  if (request.nextUrl.pathname.startsWith("/q/")) {
    return NextResponse.next();
  }

  // Skip Supabase session refresh if not configured (local dev without auth).
  // Also treat placeholder/localhost Supabase URLs as "unconfigured" so the app
  // is explorable in local dev — mirrors ENFORCE_AUTH in (app)/layout.tsx. In
  // production NEXT_PUBLIC_SUPABASE_URL is a real host, so auth stays enforced.
  const authDisabled =
    !supabaseUrl ||
    !supabaseKey ||
    supabaseUrl.includes("placeholder.supabase.co") ||
    supabaseUrl.includes("localhost") ||
    supabaseUrl.includes("127.0.0.1");
  if (authDisabled) {
    return handleI18nRouting(request);
  }

  // CRITICAL: supabaseResponse must be the response returned to the browser.
  // If Supabase needs to write refreshed session cookies, it calls setAll()
  // which rebuilds supabaseResponse. We MUST return this response (or merge
  // its cookies) — never return a different response object after this point
  // without copying cookies across, or the refreshed token is silently dropped.
  let supabaseResponse = NextResponse.next({ request });

  const supabase = createServerClient(supabaseUrl, supabaseKey, {
    cookies: {
      getAll() {
        return request.cookies.getAll();
      },
      setAll(cookiesToSet) {
        // Write cookies into the request so downstream reads see them
        cookiesToSet.forEach(({ name, value }) => request.cookies.set(name, value));
        // Rebuild supabaseResponse with the updated request
        supabaseResponse = NextResponse.next({ request });
        // Write the new session cookies into the response
        cookiesToSet.forEach(({ name, value, options }) =>
          supabaseResponse.cookies.set(name, value, options)
        );
      },
    },
  });

  // CRITICAL: getUser() triggers the token refresh flow. Never skip this call.
  // Use getUser() (not getSession()) — getSession() reads from the local cookie
  // only and does NOT validate the JWT against Supabase servers.
  const {
    data: { user },
  } = await supabase.auth.getUser();

  const bare = stripLocale(request.nextUrl.pathname);
  const segments = bare.split("/").filter(Boolean);
  const firstSegment = segments[0] ?? "";
  const secondSegment = segments[1] ?? "";

  const isProtected = PROTECTED_SEGMENTS.includes(firstSegment);
  const isAuth = firstSegment === "auth";
  // Supabase's password-recovery and OAuth-callback flows log the user in
  // *before* they arrive at these pages. If we redirect authenticated users
  // away from /auth/*, a recovery-link user would be bounced to /dashboard
  // and could never actually set a new password. Exempt these sub-paths.
  const isAuthPassthrough =
    isAuth && (secondSegment === "reset-password" || secondSegment === "callback");

  // Unauthenticated user trying to reach a protected page → login
  if (isProtected && !user) {
    const prefix = getLocalePrefix(request.nextUrl.pathname);
    const loginUrl = new URL(`${prefix}/auth/login`, request.url);
    loginUrl.searchParams.set("next", request.nextUrl.pathname);
    return NextResponse.redirect(loginUrl);
  }

  // Authenticated user visiting auth pages → dashboard
  // (but not recovery / callback flows — see comment above)
  if (user && isAuth && !isAuthPassthrough) {
    const prefix = getLocalePrefix(request.nextUrl.pathname);
    return NextResponse.redirect(new URL(`${prefix}/dashboard`, request.url));
  }

  // Run next-intl routing and merge any session cookies Supabase wrote.
  // We must return a single response — if Supabase wrote cookies we copy them
  // onto the intl response so both concerns are satisfied.
  const intlResponse = handleI18nRouting(request);

  // Copy any Supabase session cookies onto the intl response
  supabaseResponse.cookies.getAll().forEach((cookie) => {
    intlResponse.cookies.set(cookie.name, cookie.value, cookie);
  });

  return intlResponse;
}

export const config = {
  matcher: "/((?!api|trpc|_next|_vercel|.*\\..*).*)",
};
