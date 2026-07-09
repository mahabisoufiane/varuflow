// File: src/lib/plan.ts
// Purpose: Plan feature access definitions and helper functions
// Used by: PlanGate component, pricing page, feature-gated sections

export type Plan = "starter" | "professional" | "enterprise";

export const PLAN_FEATURES = {
  starter: {
    maxProducts: 2000,
    maxCustomers: 500,
    maxInvoicesPerMonth: 200,
    maxSeats: 5,
    mobileApp: false,
    advancedAnalytics: false,
    apiAccess: false,
    prioritySupport: false,
    bulkImport: true,
    customIntegrations: false,
    fortnoxIntegration: true,
  },
  professional: {
    maxProducts: 25000,
    maxCustomers: Infinity,
    maxInvoicesPerMonth: Infinity,
    maxSeats: 20,
    mobileApp: true,
    advancedAnalytics: true,
    apiAccess: false,
    prioritySupport: true,
    bulkImport: true,
    customIntegrations: false,
    fortnoxIntegration: true,
  },
  enterprise: {
    maxProducts: Infinity,
    maxCustomers: Infinity,
    maxInvoicesPerMonth: Infinity,
    maxSeats: Infinity,
    mobileApp: true,
    advancedAnalytics: true,
    apiAccess: true,
    prioritySupport: true,
    bulkImport: true,
    customIntegrations: true,
    fortnoxIntegration: true,
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
    monthly: { sek: 499, eur: 49 },
    yearly:  { sek: 399, eur: 39, annualSek: 4788, annualEur: 468 },
  },
  professional: {
    monthly: { sek: 1490, eur: 149 },
    yearly:  { sek: 1190, eur: 119, annualSek: 14280, annualEur: 1428 },
  },
  enterprise: {
    monthly: { sek: 3990, eur: 399 },
    yearly:  { sek: 3190, eur: 319, annualSek: 38280, annualEur: 3828 },
  },
} as const;

export const PLAN_ORDER: Plan[] = ["starter", "professional", "enterprise"];

export function planRank(plan: Plan): number {
  return PLAN_ORDER.indexOf(plan);
}

export function hasAccess(userPlan: Plan, requiredPlan: Plan): boolean {
  return planRank(userPlan) >= planRank(requiredPlan);
}
