<!-- BEGIN:nextjs-agent-rules -->
# This is NOT the Next.js you know

This version has breaking changes — APIs, conventions, and file structure may all differ from your training data. Read the relevant guide in `node_modules/next/dist/docs/` before writing any code. Heed deprecation notices.
<!-- END:nextjs-agent-rules -->

## Varuflow site — stack rules (strict)

- **Latest only**: Next.js 16.2 App Router, TypeScript strict, React 19.2 with
  the React Compiler enabled (`reactCompiler: true` in next.config.ts).
  No Next 13/14 patterns — consult `node_modules/next/dist/docs/` before
  writing any Next.js code.
- **Async request APIs everywhere**: `params`, `searchParams`, `cookies()`,
  `headers()` are Promises — always `await` (or `use()`) them.
- **proxy.ts, not middleware.ts** (the middleware convention is deprecated).
- **Turbopack only** — never add a webpack config.
- **Tailwind v4, CSS-first**: all design tokens live in `@theme` in
  `src/app/globals.css`. There is no `tailwind.config.js` and there must
  never be one.
- **Design**: Nordic aesthetic — whitespace, high contrast, flat color.
  No gradients. No stock photos. Two fonts max, loaded via `next/font`
  (Inter = --font-sans, Space Grotesk = --font-display).
- **i18n**: next-intl with `/sv` (default) and `/en`, `[locale]` segment,
  `localePrefix: "always"`. Use `Link`/`useRouter` from `@/i18n/navigation`,
  never `next/link` directly.
- **Server components by default**; add `"use client"` only when required.
- **Facts discipline**: pricing, module names, limits and vertical copy are
  REAL product facts pulled from the main repo (`frontend/src/lib/plan.ts`,
  `frontend/messages/*.json`, verticals.ts). Never invent numbers or
  features. `src/lib/pricing.ts` and `src/content/**` are the only places
  business facts may live — pages must import from there, never hardcode.
