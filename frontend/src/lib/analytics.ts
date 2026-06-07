// File: src/lib/analytics.ts
// Purpose: PostHog analytics wrappers — frontend event tracking, identify, reset.
// Usage: import { track, EVENTS } from "@/lib/analytics"
//
// Design:
// - Disabled in development (NODE_ENV !== "production")
// - PII scrubbing: input field values are never captured via autocapture (configured at init)
// - All functions are null-safe — posthog not loaded → silent no-op
// - Event names are string constants mirroring backend/app/services/analytics.py

// ── Event constants ───────────────────────────────────────────────────────────
export const EVENTS = {
  // Acquisition
  LANDING_PAGE_VIEWED:       "landing_page_viewed",
  PRICING_VIEWED:            "pricing_viewed",
  COMPARISON_PAGE_VIEWED:    "comparison_page_viewed",

  // Signup & onboarding
  SIGNUP_STARTED:            "signup_started",
  SIGNUP_COMPLETED:          "signup_completed",
  TRIAL_STARTED:             "trial_started",
  ONBOARDING_STEP_COMPLETED: "onboarding_step_completed",

  // Activation / time-to-value
  FIRST_INVOICE_CREATED:     "first_invoice_created",
  FIRST_POS_SALE:            "first_pos_sale",
  INVOICE_CREATED:           "invoice_created",
  POS_SALE:                  "pos_sale",

  // Upsell funnel
  UPSELL_SHOWN:              "upsell_shown",
  UPSELL_CLICKED:            "upsell_clicked",
  UPSELL_DISMISSED:          "upsell_dismissed",
  UPSELL_CONVERTED:          "upsell_converted",

  // Subscription lifecycle
  SUBSCRIPTION_STARTED:      "subscription_started",
  SUBSCRIPTION_UPGRADED:     "subscription_upgraded",
  SUBSCRIPTION_DOWNGRADED:   "subscription_downgraded",
  SUBSCRIPTION_CANCELED:     "subscription_canceled",

  // Engagement
  FEATURE_USED:              "feature_used",
  AI_QUERY_MADE:             "ai_query_made",

  // Plan limits
  LIMIT_WARNING_SHOWN:       "limit_warning_shown",
  LIMIT_BLOCKED_SHOWN:       "limit_blocked_shown",
} as const;

export type EventName = typeof EVENTS[keyof typeof EVENTS];

// ── Typed property helpers ────────────────────────────────────────────────────

export interface LandingPageProps   { page_name: string }
export interface ComparisonProps    { competitor: string }
export interface OnboardingProps    { step: string; step_number?: number }
export interface UpsellProps        { placement: string; tier_offered: string; trigger?: string }
export interface SubscriptionProps  { tier: string; interval?: "month" | "year" }
export interface FeatureProps       { feature: string }
export interface LimitProps         { resource: string; plan: string; current?: number; limit?: number }

// ── posthog lazy accessor ─────────────────────────────────────────────────────

function ph(): typeof import("posthog-js").default | null {
  if (typeof window === "undefined") return null;
  if (process.env.NODE_ENV !== "production") return null;
  // posthog-js attaches to window.posthog after init
  const w = window as unknown as Record<string, unknown>;
  const phog = w.posthog;
  if (!phog || typeof (phog as { capture?: unknown }).capture !== "function") return null;
  return phog as typeof import("posthog-js").default;
}

// ── Core primitives ───────────────────────────────────────────────────────────

/** Identify the logged-in user.  Call after successful sign-in or onboarding. */
export function identify(userId: string, traits?: Record<string, unknown>): void {
  try {
    ph()?.identify(userId, traits);
  } catch {
    // never throw
  }
}

/** Fire a PostHog event.  No-op when posthog is not loaded or not in production. */
export function track(event: string, properties?: object): void {
  try {
    ph()?.capture(event, properties);
  } catch {
    // never throw
  }
}

/** Reset posthog state on logout — unlinks the anonymous ID from the user. */
export function reset(): void {
  try {
    ph()?.reset();
  } catch {
    // never throw
  }
}

/** Set super-properties that will be included with every event from this browser. */
export function setSuperProperties(properties: object): void {
  try {
    ph()?.register(properties);
  } catch {
    // never throw
  }
}

// ── High-level typed wrappers ─────────────────────────────────────────────────

export const Analytics = {
  landingPageViewed:       (props: LandingPageProps)  => track(EVENTS.LANDING_PAGE_VIEWED, props),
  pricingViewed:           ()                          => track(EVENTS.PRICING_VIEWED),
  comparisonPageViewed:    (props: ComparisonProps)    => track(EVENTS.COMPARISON_PAGE_VIEWED, props),
  signupStarted:           ()                          => track(EVENTS.SIGNUP_STARTED),
  signupCompleted:         (props: Record<string, unknown>) => track(EVENTS.SIGNUP_COMPLETED, props),
  trialStarted:            (props: Record<string, unknown>) => track(EVENTS.TRIAL_STARTED, props),
  onboardingStepCompleted: (props: OnboardingProps)    => track(EVENTS.ONBOARDING_STEP_COMPLETED, props),
  firstInvoiceCreated:     ()                          => track(EVENTS.FIRST_INVOICE_CREATED),
  firstPosSale:            ()                          => track(EVENTS.FIRST_POS_SALE),
  upsellShown:             (props: UpsellProps)        => track(EVENTS.UPSELL_SHOWN, props),
  upsellClicked:           (props: UpsellProps)        => track(EVENTS.UPSELL_CLICKED, props),
  upsellDismissed:         (props: UpsellProps)        => track(EVENTS.UPSELL_DISMISSED, props),
  upsellConverted:         (props: UpsellProps)        => track(EVENTS.UPSELL_CONVERTED, props),
  subscriptionStarted:     (props: SubscriptionProps)  => track(EVENTS.SUBSCRIPTION_STARTED, props),
  subscriptionUpgraded:    (props: SubscriptionProps)  => track(EVENTS.SUBSCRIPTION_UPGRADED, props),
  subscriptionDowngraded:  (props: SubscriptionProps)  => track(EVENTS.SUBSCRIPTION_DOWNGRADED, props),
  subscriptionCanceled:    (props: SubscriptionProps)  => track(EVENTS.SUBSCRIPTION_CANCELED, props),
  featureUsed:             (props: FeatureProps)       => track(EVENTS.FEATURE_USED, props),
  aiQueryMade:             ()                          => track(EVENTS.AI_QUERY_MADE),
  limitWarningShown:       (props: LimitProps)         => track(EVENTS.LIMIT_WARNING_SHOWN, props),
  limitBlockedShown:       (props: LimitProps)         => track(EVENTS.LIMIT_BLOCKED_SHOWN, props),
} as const;
