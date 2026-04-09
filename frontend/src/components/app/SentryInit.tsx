"use client";

import { useEffect } from "react";

// Initializes Sentry (loaded via CDN) once the DSN env var is set.
export default function SentryInit() {
  useEffect(() => {
    const dsn = process.env.NEXT_PUBLIC_SENTRY_DSN;
    if (!dsn) return;
    const w = window as Record<string, unknown>;
    if (typeof w.Sentry !== "object" || !w.Sentry) return;
    const Sentry = w.Sentry as {
      init: (cfg: object) => void;
      isInitialized?: () => boolean;
    };
    if (Sentry.isInitialized?.()) return;
    Sentry.init({
      dsn,
      environment: process.env.NODE_ENV,
      tracesSampleRate: 0.1,
      replaysOnErrorSampleRate: 1.0,
    });
  }, []);

  return null;
}
