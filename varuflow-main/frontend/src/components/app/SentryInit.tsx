"use client";

import { useEffect } from "react";

// Initializes Sentry (loaded via CDN) once the DSN env var is set.
// Retries for up to 10 s in case the CDN script hasn't executed yet
// when this component mounts (both run after-interactive).
export default function SentryInit() {
  useEffect(() => {
    const dsn = process.env.NEXT_PUBLIC_SENTRY_DSN;
    if (!dsn) return;

    function tryInit(): boolean {
      const w = window as unknown as Record<string, unknown>;
      if (typeof w.Sentry !== "object" || !w.Sentry) return false;
      const Sentry = w.Sentry as {
        init: (cfg: object) => void;
        isInitialized?: () => boolean;
      };
      if (Sentry.isInitialized?.()) return true;
      Sentry.init({
        dsn,
        environment: process.env.NODE_ENV,
        tracesSampleRate: 0.1,
        replaysOnErrorSampleRate: 1.0,
      });
      return true;
    }

    if (tryInit()) return;

    // CDN not ready yet — poll until it loads (max 10 s)
    const interval = setInterval(() => {
      if (tryInit()) clearInterval(interval);
    }, 200);
    const timeout = setTimeout(() => clearInterval(interval), 10_000);
    return () => {
      clearInterval(interval);
      clearTimeout(timeout);
    };
  }, []);

  return null;
}
