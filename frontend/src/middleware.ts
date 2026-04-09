import { createServerClient } from "@supabase/ssr";
import createIntlMiddleware from "next-intl/middleware";
import { type NextRequest, NextResponse } from "next/server";
import { routing } from "./i18n/routing";

const handleI18nRouting = createIntlMiddleware(routing);

const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL || "";
const supabaseKey = process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_DEFAULT_KEY || "";

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
  const match = pathname.match(/^\/(en)(\/|$)/);
  return match ? `/${match[1]}` : "";
}

export async function middleware(request: NextRequest) {
  // Portal routes are standalone — skip i18n and auth entirely
  if (request.nextUrl.pathname.startsWith("/portal")) {
    return NextResponse.next();
  }

  // Run next-intl routing first
  const intlResponse = handleI18nRouting(request);

  // Skip Supabase session refresh if not configured (local dev without auth)
  if (!supabaseUrl || !supabaseKey) {
    return intlResponse;
  }

  // Build a mutable response for Supabase to write session cookies into
  let supabaseResponse = NextResponse.next({ request: { headers: request.headers } });

  const supabase = createServerClient(supabaseUrl, supabaseKey, {
    cookies: {
      getAll() {
        return request.cookies.getAll();
      },
      setAll(cookiesToSet) {
        cookiesToSet.forEach(({ name, value }) => request.cookies.set(name, value));
        supabaseResponse = NextResponse.next({ request });
        cookiesToSet.forEach(({ name, value, options }) =>
          supabaseResponse.cookies.set(name, value, options)
        );
        // Mirror cookies onto the intl response too
        cookiesToSet.forEach(({ name, value, options }) =>
          intlResponse.cookies.set(name, value, options)
        );
      },
    },
  });

  // Refresh the session — IMPORTANT: use getUser (not getSession) for security
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

  return intlResponse;
}

export const config = {
  matcher: "/((?!api|trpc|_next|_vercel|.*\\..*).*)",
};
