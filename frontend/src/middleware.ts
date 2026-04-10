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

// Paths under (app) that require authentication
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
];

function stripLocale(pathname: string): string {
  return pathname.replace(/^\/(sv|en)(\/|$)/, "/");
}

function getLocalePrefix(pathname: string): string {
  const match = pathname.match(/^\/(en|sv)(\/|$)/);
  return match ? `/${match[1]}` : "";
}

export async function middleware(request: NextRequest) {
  // Portal routes are standalone — skip i18n and auth entirely
  if (request.nextUrl.pathname.startsWith("/portal")) {
    return NextResponse.next();
  }

  // Skip Supabase session refresh if not configured (local dev without auth)
  if (!supabaseUrl || !supabaseKey) {
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
  const firstSegment = bare.split("/")[1] ?? "";

  const isProtected = PROTECTED_SEGMENTS.includes(firstSegment);
  const isAuth = firstSegment === "auth";

  // Unauthenticated user trying to reach a protected page → login
  if (isProtected && !user) {
    const prefix = getLocalePrefix(request.nextUrl.pathname);
    const loginUrl = new URL(`${prefix}/auth/login`, request.url);
    loginUrl.searchParams.set("next", request.nextUrl.pathname);
    return NextResponse.redirect(loginUrl);
  }

  // Authenticated user visiting auth pages → dashboard
  if (user && isAuth) {
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
