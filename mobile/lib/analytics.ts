// File: mobile/lib/analytics.ts
// Purpose: PostHog analytics for Expo/React Native.
// All functions are silent no-ops when EXPO_PUBLIC_POSTHOG_KEY is unset
// or when running in development/test mode.

import Constants from "expo-constants";

// ── Event constants (matches frontend/src/lib/analytics.ts) ─────────────────
export const EVENTS = {
  APP_OPENED:                "app_opened",
  SCREEN_VIEWED:             "screen_viewed",

  // Shared with web
  SIGNUP_STARTED:            "signup_started",
  SIGNUP_COMPLETED:          "signup_completed",
  TRIAL_STARTED:             "trial_started",
  ONBOARDING_STEP_COMPLETED: "onboarding_step_completed",

  FIRST_INVOICE_CREATED:     "first_invoice_created",
  FIRST_POS_SALE:            "first_pos_sale",
  INVOICE_CREATED:           "invoice_created",
  POS_SALE:                  "pos_sale",

  UPSELL_SHOWN:              "upsell_shown",
  UPSELL_CLICKED:            "upsell_clicked",
  UPSELL_DISMISSED:          "upsell_dismissed",
  UPSELL_CONVERTED:          "upsell_converted",

  SUBSCRIPTION_STARTED:      "subscription_started",
  SUBSCRIPTION_UPGRADED:     "subscription_upgraded",
  SUBSCRIPTION_DOWNGRADED:   "subscription_downgraded",
  SUBSCRIPTION_CANCELED:     "subscription_canceled",

  FEATURE_USED:              "feature_used",
  AI_QUERY_MADE:             "ai_query_made",
  LIMIT_WARNING_SHOWN:       "limit_warning_shown",
  LIMIT_BLOCKED_SHOWN:       "limit_blocked_shown",
} as const;

export type EventName = typeof EVENTS[keyof typeof EVENTS];

// ── Lazy singleton ─────────────────────────────────────────────────────────

type PHClient = {
  capture: (event: string, properties?: Record<string, unknown>) => void;
  identify: (id: string, properties?: Record<string, unknown>) => void;
  reset: () => void;
} | null;

let _client: PHClient = null;
let _initialized = false;

function getApiKey(): string {
  // Expo public env vars via process.env (set in app.config.js extra section)
  return (
    process.env.EXPO_PUBLIC_POSTHOG_KEY ??
    Constants.expoConfig?.extra?.posthogApiKey ??
    ""
  );
}

function getHost(): string {
  return (
    process.env.EXPO_PUBLIC_POSTHOG_HOST ??
    Constants.expoConfig?.extra?.posthogHost ??
    "https://eu.i.posthog.com"
  );
}

export async function initPostHog(): Promise<void> {
  if (_initialized) return;
  _initialized = true;

  const apiKey = getApiKey();
  if (!apiKey || __DEV__) return;

  try {
    const { PostHog } = await import("posthog-react-native");
    const client = await PostHog.initAsync(apiKey, { host: getHost() });
    _client = {
      capture: (event, props) => client.capture(event, props),
      identify: (id, props) => client.identify(id, props),
      reset: () => client.reset(),
    };
  } catch {
    // posthog-react-native not installed or init failed — silent no-op
  }
}

// ── Core primitives ───────────────────────────────────────────────────────────

export function track(event: string, properties?: Record<string, unknown>): void {
  try {
    _client?.capture(event, properties);
  } catch {
    // never throw
  }
}

export function identify(userId: string, traits?: Record<string, unknown>): void {
  try {
    _client?.identify(userId, traits);
  } catch {
    // never throw
  }
}

export function reset(): void {
  try {
    _client?.reset();
  } catch {
    // never throw
  }
}

// ── High-level wrappers ───────────────────────────────────────────────────────

export const MobileAnalytics = {
  appOpened:  () => track(EVENTS.APP_OPENED),
  screenViewed: (screenName: string) =>
    track(EVENTS.SCREEN_VIEWED, { screen: screenName }),
  featureUsed: (feature: string) =>
    track(EVENTS.FEATURE_USED, { feature }),
  aiQueryMade: () => track(EVENTS.AI_QUERY_MADE),
} as const;
