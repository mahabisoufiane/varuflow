// File: src/lib/plan.ts
// Purpose: Plan feature access definitions and helper functions
// Used by: PlanGate component, pricing page, feature-gated sections

export type Plan = "starter" | "professional" | "enterprise";

export const PLAN_FEATURES = {
  starter: {
    maxProducts: 500,
    maxSeats: 1,
    mobileApp: false,
    advancedAnalytics: false,
    apiAccess: false,
    prioritySupport: false,
    bulkImport: false,
    customIntegrations: false,
  },
  professional: {
    maxProducts: 5000,
    maxSeats: 5,
    mobileApp: false,
    advancedAnalytics: true,
    apiAccess: false,
    prioritySupport: true,
    bulkImport: true,
    customIntegrations: false,
  },
  enterprise: {
    maxProducts: Infinity,
    maxSeats: Infinity,
    mobileApp: true,
    advancedAnalytics: true,
    apiAccess: true,
    prioritySupport: true,
    bulkImport: true,
    customIntegrations: true,
  },
} as const;

export type Feature = keyof typeof PLAN_FEATURES.enterprise;

export function canAccess(plan: Plan, feature: Feature): boolean {
  const val = PLAN_FEATURES[plan][feature];
  return val === true;
}

export function isEnterprise(plan: Plan): boolean {
  return plan === "enterprise";
}

export function isProfessionalOrAbove(plan: Plan): boolean {
  return plan === "professional" || plan === "enterprise";
}

// Prices in SEK — single source of truth, never hardcoded in JSX
export const PLAN_PRICES = {
  starter: {
    monthly: { sek: 299, eur: 29 },
    yearly:  { sek: 239, eur: 23, annualSek: 2868, annualEur: 276 },
  },
  professional: {
    monthly: { sek: 799, eur: 79 },
    yearly:  { sek: 639, eur: 63, annualSek: 7668, annualEur: 756 },
  },
  enterprise: {
    monthly: { sek: 1999, eur: 199 },
    yearly:  { sek: 1599, eur: 159, annualSek: 19188, annualEur: 1908 },
  },
} as const;

export const PLAN_ORDER: Plan[] = ["starter", "professional", "enterprise"];

export function planRank(plan: Plan): number {
  return PLAN_ORDER.indexOf(plan);
}

export function hasAccess(userPlan: Plan, requiredPlan: Plan): boolean {
  return planRank(userPlan) >= planRank(requiredPlan);
}
