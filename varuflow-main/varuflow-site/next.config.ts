import type { NextConfig } from "next";
import createNextIntlPlugin from "next-intl/plugin";

// Resolves ./src/i18n/request.ts (the default path) for server components.
const withNextIntl = createNextIntlPlugin();

const nextConfig: NextConfig = {
  reactCompiler: true,
  // The monorepo has lockfiles above this app; without an explicit root,
  // Turbopack/Tailwind source detection is non-deterministic (utilities
  // like overflow-x-auto were silently dropped in some builds).
  turbopack: { root: __dirname },
};

export default withNextIntl(nextConfig);
