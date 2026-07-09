// Single source of truth for plans on the marketing site.
// Facts copied from the product: varuflow-main/frontend/src/lib/plan.ts
// (PLAN_PRICES + PLAN_FEATURES) — do not edit numbers here without
// changing them there first. Trial: 14-day PRO trial (backend
// app/features/auth/organization.py).

export type TierId = "starter" | "professional" | "enterprise";

export interface Price {
  sek: number;
  eur: number;
}

export interface Tier {
  id: TierId;
  monthly: Price;
  /** Per-month price when billed yearly. */
  yearlyPerMonth: Price;
  annual: Price;
  limits: {
    maxProducts: number | null; // null = unlimited
    maxCustomers: number | null;
    maxInvoicesPerMonth: number | null;
    maxSeats: number | null;
  };
  flags: {
    mobileApp: boolean;
    advancedAnalytics: boolean;
    apiAccess: boolean;
    prioritySupport: boolean;
    customIntegrations: boolean;
    fortnoxIntegration: boolean;
  };
}

export const TRIAL_DAYS = 14;

export const TIERS: Tier[] = [
  {
    id: "starter",
    monthly: { sek: 499, eur: 49 },
    yearlyPerMonth: { sek: 399, eur: 39 },
    annual: { sek: 4788, eur: 468 },
    limits: { maxProducts: 500, maxCustomers: 150, maxInvoicesPerMonth: 200, maxSeats: 5 },
    flags: {
      mobileApp: false, advancedAnalytics: false, apiAccess: false,
      prioritySupport: false, customIntegrations: false, fortnoxIntegration: true,
    },
  },
  {
    id: "professional",
    monthly: { sek: 1490, eur: 149 },
    yearlyPerMonth: { sek: 1190, eur: 119 },
    annual: { sek: 14280, eur: 1428 },
    limits: { maxProducts: 10000, maxCustomers: null, maxInvoicesPerMonth: null, maxSeats: 20 },
    flags: {
      mobileApp: true, advancedAnalytics: true, apiAccess: false,
      prioritySupport: true, customIntegrations: false, fortnoxIntegration: true,
    },
  },
  {
    id: "enterprise",
    monthly: { sek: 3990, eur: 399 },
    yearlyPerMonth: { sek: 3190, eur: 319 },
    annual: { sek: 38280, eur: 3828 },
    limits: { maxProducts: null, maxCustomers: null, maxInvoicesPerMonth: null, maxSeats: null },
    flags: {
      mobileApp: true, advancedAnalytics: true, apiAccess: true,
      prioritySupport: true, customIntegrations: true, fortnoxIntegration: true,
    },
  },
];
