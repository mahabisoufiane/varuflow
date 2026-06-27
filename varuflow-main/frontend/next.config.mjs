import createNextIntlPlugin from "next-intl/plugin";
import { buildSecurityHeaders } from "./src/lib/security-headers.mjs";

const withNextIntl = createNextIntlPlugin("./src/i18n/request.ts");

/** @type {import('next').NextConfig} */
const nextConfig = {
  output: "standalone",
  reactStrictMode: false,
  // Bake NEXT_PUBLIC vars into the Turbopack client bundle at build time.
  // NEXT_PUBLIC_SUPABASE_ANON_KEY is the canonical name — also keep the legacy
  // PUBLISHABLE_DEFAULT_KEY for any remaining references.
  env: {
    NEXT_PUBLIC_SUPABASE_URL: process.env.NEXT_PUBLIC_SUPABASE_URL ?? "",
    NEXT_PUBLIC_SUPABASE_ANON_KEY: process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY ?? "",
    NEXT_PUBLIC_SUPABASE_PUBLISHABLE_DEFAULT_KEY:
      process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_DEFAULT_KEY ?? "",
    NEXT_PUBLIC_API_URL: process.env.NEXT_PUBLIC_API_URL ?? "",
    NEXT_PUBLIC_SENTRY_DSN: process.env.NEXT_PUBLIC_SENTRY_DSN ?? "",
    NEXT_PUBLIC_CRISP_WEBSITE_ID: process.env.NEXT_PUBLIC_CRISP_WEBSITE_ID ?? "",
  },
  // In Next.js 16, Turbopack alias config moved from experimental.turbo → top-level turbopack
  turbopack: {
    resolveAlias: {
      "next-intl/config": "./src/i18n/request.ts",
    },
  },
  // Security headers applied to every response.
  // Policy lives in src/lib/security-headers.mjs so it can be unit-tested
  // (frontend/src/tests/test_security_headers.mjs) and diff-audited in
  // isolation. See docs/operations/security-hardening.md.
  async headers() {
    const securityHeaders = buildSecurityHeaders({
      apiUrl:      process.env.NEXT_PUBLIC_API_URL,
      supabaseUrl: process.env.NEXT_PUBLIC_SUPABASE_URL,
      sentryDsn:   process.env.NEXT_PUBLIC_SENTRY_DSN,
    });

    // Dev only: `next dev` (Turbopack) serves HMR + bootstrap scripts that the
    // strict production CSP blocks — 'strict-dynamic' makes CSP3 browsers trust
    // ONLY nonce-tagged scripts, and nothing issues a nonce here, so every
    // script (and thus hydration) is blocked and the page renders blank.
    // Relax script-src for development; production keeps the full policy and
    // the golden-string test in src/lib/security-headers.mjs is unaffected.
    if (process.env.NODE_ENV !== "production") {
      for (const h of securityHeaders) {
        if (h.key === "Content-Security-Policy") {
          h.value = h.value
            .replace(" 'strict-dynamic'", "")
            .replace(
              "script-src 'self' 'unsafe-inline'",
              "script-src 'self' 'unsafe-inline' 'unsafe-eval'",
            )
            // Allow connections to any supabase.co subdomain in dev so that
            // a missing or wrong NEXT_PUBLIC_SUPABASE_URL doesn't block auth.
            .replace("connect-src ", "connect-src https://*.supabase.co wss://*.supabase.co ");
        }
      }
    }

    return [
      {
        source: "/(.*)",
        headers: securityHeaders,
      },
    ];
  },
};

const finalConfig = withNextIntl(nextConfig);

// next-intl's plugin still injects experimental.turbo (old Next ≤15 key) when
// TURBOPACK env var is not set. Next.js 16 marks this as an unrecognized key
// and logs a warning. Remove it here to keep the console clean.
if (finalConfig.experimental?.turbo) {
  delete finalConfig.experimental.turbo;
}
// Drop the now-empty experimental wrapper if nothing else is in it
if (
  finalConfig.experimental &&
  Object.keys(finalConfig.experimental).length === 0
) {
  delete finalConfig.experimental;
}

export default finalConfig;
