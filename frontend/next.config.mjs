import createNextIntlPlugin from "next-intl/plugin";

const withNextIntl = createNextIntlPlugin("./src/i18n/request.ts");

/** @type {import('next').NextConfig} */
const nextConfig = {
  output: "standalone",
  reactStrictMode: false,
  // In Next.js 16, Turbopack alias config moved from experimental.turbo → top-level turbopack
  turbopack: {
    resolveAlias: {
      "next-intl/config": "./src/i18n/request.ts",
    },
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
