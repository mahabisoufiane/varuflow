"use client";

// File: src/components/app/PostHogInit.tsx
// Purpose: Initialises posthog-js once per browser session.
// Pattern mirrors SentryInit.tsx — a useEffect-only client component that
// returns null so it can be dropped anywhere in the layout without adding DOM.
//
// PostHog configuration choices:
// - autocapture: true (clicks, inputs, submissions) with PII scrubbing
//   on all <input> fields — values are masked, only element metadata is sent.
// - capture_pageview: false — we fire $pageview manually on pathname change.
// - persistence: "localStorage+cookie" for cross-tab identity.
// - Disabled entirely when NEXT_PUBLIC_POSTHOG_KEY is not set or in dev.

import { useEffect } from "react";
import { usePathname } from "next/navigation";

export default function PostHogInit() {
  const pathname = usePathname();

  // ── Initialise once on mount ──────────────────────────────────────────────
  useEffect(() => {
    const key  = process.env.NEXT_PUBLIC_POSTHOG_KEY;
    const host = process.env.NEXT_PUBLIC_POSTHOG_HOST ?? "https://eu.i.posthog.com";

    if (!key || process.env.NODE_ENV !== "production") return;

    // Dynamic import keeps posthog-js out of the initial JS bundle.
    import("posthog-js")
      .then(({ default: posthog }) => {
        if ((posthog as { __loaded?: boolean }).__loaded) return;

        posthog.init(key, {
          api_host:         host,
          capture_pageview: false, // manual pageview below
          autocapture:      true,
          persistence:      "localStorage+cookie",
          sanitize_properties(props: Record<string, unknown>) {
            // PII scrubbing: strip any accidentally captured input values
            const clean = { ...props };
            for (const k of Object.keys(clean)) {
              if (k === "$el_text" || k === "$input_value" || k === "value") {
                delete clean[k];
              }
            }
            return clean;
          },
        });

        // Attach to window so analytics.ts can reach it via window.posthog
        (window as unknown as Record<string, unknown>).posthog = posthog;
      })
      .catch(() => {
        // posthog-js not installed or failed to load — silent no-op
      });
  }, []);

  // ── Manual pageview on route change ───────────────────────────────────────
  useEffect(() => {
    if (typeof window === "undefined") return;
    const ph = (window as unknown as Record<string, unknown>).posthog as
      | { capture?: (e: string, p: object) => void }
      | undefined;
    if (!ph?.capture) return;
    ph.capture("$pageview", { path: pathname });
  }, [pathname]);

  return null;
}
