import createNextIntlPlugin from "next-intl/plugin";

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
  // Security headers applied to every response
  async headers() {
    return [
      {
        source: "/(.*)",
        headers: [
          { key: "X-Frame-Options",          value: "DENY" },
          { key: "X-Content-Type-Options",    value: "nosniff" },
          { key: "Referrer-Policy",           value: "strict-origin-when-cross-origin" },
          { key: "Permissions-Policy",        value: "camera=(), microphone=(), geolocation=()" },
        ],
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
