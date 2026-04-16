"use client";
// Single source of truth for the backend capability probe
// (/api/system/status). Cached for the browser tab so every component
// sees the same booleans without refetching.

import { useEffect, useState } from "react";
import { api } from "@/lib/api-client";

export interface Capabilities {
  stripe_configured:               boolean;
  billing_checkout_available:      boolean;
  billing_portal_available:        boolean;
  invoice_payment_links_available: boolean;
  fortnox_configured:              boolean;
  transactional_email_available:   boolean;
  auth_email_available:            boolean;
  ai_chat_available:               boolean;
  error_tracking_enabled:          boolean;
  default_country:                 string;
}

let _cached: Capabilities | null = null;
let _inflight: Promise<Capabilities> | null = null;

async function load(): Promise<Capabilities> {
  if (_cached) return _cached;
  if (_inflight) return _inflight;
  _inflight = api
    .get<Capabilities>("/api/system/status")
    .then((c) => {
      _cached = c;
      return c;
    })
    .catch(() => {
      // Fail closed — every optional integration is reported unavailable
      // so the UI hides disabled flows rather than showing broken buttons.
      const fallback: Capabilities = {
        stripe_configured:               false,
        billing_checkout_available:      false,
        billing_portal_available:        false,
        invoice_payment_links_available: false,
        fortnox_configured:              false,
        transactional_email_available:   false,
        auth_email_available:            false,
        ai_chat_available:               false,
        error_tracking_enabled:          false,
        default_country:                 "SE",
      };
      _cached = fallback;
      return fallback;
    })
    .finally(() => {
      _inflight = null;
    });
  return _inflight;
}

export function useCapabilities(): Capabilities | null {
  const [caps, setCaps] = useState<Capabilities | null>(_cached);
  useEffect(() => {
    if (_cached) {
      setCaps(_cached);
      return;
    }
    let cancelled = false;
    load().then((c) => {
      if (!cancelled) setCaps(c);
    });
    return () => {
      cancelled = true;
    };
  }, []);
  return caps;
}
