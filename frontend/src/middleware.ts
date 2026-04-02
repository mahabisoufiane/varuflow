import { createServerClient } from "@supabase/ssr";
import createIntlMiddleware from "next-intl/middleware";
import { NextRequest, NextResponse } from "next/server";
import { routing } from "./i18n/routing";

const handleI18nRouting = createIntlMiddleware(routing);

// Paths under (app) that require authentication
const PROTECTED_SEGMENTS = [
  "dashboard",
  "inventory",
  "invoices",
  "customers",
  "settings",
];

function stripLocale(pathname: string): string {
  return pathname.replace(/^\/(en|sv|no|da)(\/|$)/, "/");
}

function getLocalePrefix(pathname: string): string {
  const match = pathname.match(/^\/(sv|no|da)(\/|$)/);
  return match ? `/${match[1]}` : "";
}

export async function middleware(request: NextRequest) {
  // Portal routes are standalone — skip i18n and Supabase auth entirely
  if (request.nextUrl.pathname.startsWith("/portal")) {
    return NextResponse.next();
  }

  // Run next-intl routing first to get the correctly localised response
  const intlResponse = handleI18nRouting(request);

  // Build a mutable response so Supabase can write session cookies
  const response = NextResponse.next({
    request: { headers: request.headers },
  });

  // Only create the Supabase client when the env vars are configured
  if (
    !process.env.NEXT_PUBLIC_SUPABASE_URL ||
    !process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY
  ) {
    return intlResponse;
  }

  const supabase = createServerClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL,
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY,
    {
      cookies: {
        getAll() {
          return request.cookies.getAll();
        },
        setAll(cookiesToSet) {
          cookiesToSet.forEach(({ name, value, options }) => {
            request.cookies.set(name, value);
            response.cookies.set(name, value, options);
            intlResponse.cookies.set(name, value, options);
          });
        },
      },
    }
  );

  // Refresh the session (IMPORTANT: use getUser, not getSession, for security)
  const {
    data: { user },
  } = await supabase.auth.getUser();

  const bare = stripLocale(request.nextUrl.pathname);
  const firstSegment = bare.split("/")[1] ?? "";

  const isProtected = PROTECTED_SEGMENTS.includes(firstSegment);
  const isOnboarding = firstSegment === "onboarding";
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
