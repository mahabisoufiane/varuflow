// File: src/lib/plan-limits.ts
// Purpose: Plan limit constants and helpers mirroring backend/app/services/plan_limits.py
// Used by: LimitWarningBanner, LimitBlockedModal, LockedFeatureCard, any page that
//          needs to check tier entitlements before hitting the API.

export type OrgPlan = "FREE" | "PRO" | "ENTERPRISE";

// ── Resource keys (must match backend plan_limits.py) ────────────────────────
export const RESOURCE_USERS               = "max_users";
export const RESOURCE_WAREHOUSES          = "max_warehouses";
export const RESOURCE_PRODUCTS            = "max_products";
export const RESOURCE_INVOICES_PER_MONTH  = "max_invoices_per_month";
export const RESOURCE_CUSTOMERS           = "max_customers";
export const RESOURCE_STORAGE_GB          = "max_storage_gb";
export const RESOURCE_AI_CALLS_PER_DAY    = "ai_calls_per_day";

// ── Feature keys (must match backend plan_limits.py) ─────────────────────────
export const FEATURE_API_WEBHOOKS     = "api_webhooks";
export const FEATURE_WHITE_LABEL      = "white_label";
export const FEATURE_MULTI_WAREHOUSE  = "multi_warehouse";
export const FEATURE_ESIGN            = "esign";
export const FEATURE_ADVANCED_REPORTS = "advanced_reports";
export const FEATURE_FORTNOX_SYNC     = "fortnox_sync";
export const FEATURE_ZAPIER           = "zapier";
export const FEATURE_PRIORITY_SUPPORT = "priority_support";
export const FEATURE_AI_CHAT          = "ai_chat";
export const FEATURE_LOYALTY          = "loyalty";
export const FEATURE_FAMILY_GROUPS    = "family_groups";
export const FEATURE_PORTAL_CUSTOM    = "portal_customisation";
export const FEATURE_MULTI_ENTITY     = "multi_entity";
export const FEATURE_IP_ALLOWLIST     = "ip_allowlist";
export const FEATURE_AUDIT_LOG        = "audit_log";

// ── Tier limits (null = unlimited) ──────────────────────────────────────────
const PLAN_LIMITS: Record<OrgPlan, Record<string, number | null>> = {
  FREE: {
    [RESOURCE_USERS]:              3,
    [RESOURCE_WAREHOUSES]:         1,
    [RESOURCE_PRODUCTS]:         500,
    [RESOURCE_INVOICES_PER_MONTH]: 50,
    [RESOURCE_CUSTOMERS]:        200,
    [RESOURCE_STORAGE_GB]:         1,
    [RESOURCE_AI_CALLS_PER_DAY]:   0,
  },
  PRO: {
    [RESOURCE_USERS]:              20,
    [RESOURCE_WAREHOUSES]:          5,
    [RESOURCE_PRODUCTS]:        5_000,
    [RESOURCE_INVOICES_PER_MONTH]: 500,
    [RESOURCE_CUSTOMERS]:       2_000,
    [RESOURCE_STORAGE_GB]:         10,
    [RESOURCE_AI_CALLS_PER_DAY]:  100,
  },
  ENTERPRISE: {
    [RESOURCE_USERS]:              null,
    [RESOURCE_WAREHOUSES]:         null,
    [RESOURCE_PRODUCTS]:           null,
    [RESOURCE_INVOICES_PER_MONTH]: null,
    [RESOURCE_CUSTOMERS]:          null,
    [RESOURCE_STORAGE_GB]:         null,
    [RESOURCE_AI_CALLS_PER_DAY]:   null,
  },
};

// ── Feature flags ─────────────────────────────────────────────────────────────
const PLAN_FEATURES: Record<OrgPlan, Set<string>> = {
  FREE: new Set([FEATURE_LOYALTY]),
  PRO: new Set([
    FEATURE_LOYALTY,
    FEATURE_MULTI_WAREHOUSE,
    FEATURE_ESIGN,
    FEATURE_ADVANCED_REPORTS,
    FEATURE_FORTNOX_SYNC,
    FEATURE_ZAPIER,
    FEATURE_AI_CHAT,
    FEATURE_FAMILY_GROUPS,
    FEATURE_PORTAL_CUSTOM,
    FEATURE_AUDIT_LOG,
    FEATURE_IP_ALLOWLIST,
  ]),
  ENTERPRISE: new Set([
    FEATURE_LOYALTY,
    FEATURE_MULTI_WAREHOUSE,
    FEATURE_ESIGN,
    FEATURE_ADVANCED_REPORTS,
    FEATURE_FORTNOX_SYNC,
    FEATURE_ZAPIER,
    FEATURE_AI_CHAT,
    FEATURE_FAMILY_GROUPS,
    FEATURE_PORTAL_CUSTOM,
    FEATURE_AUDIT_LOG,
    FEATURE_IP_ALLOWLIST,
    FEATURE_API_WEBHOOKS,
    FEATURE_WHITE_LABEL,
    FEATURE_PRIORITY_SUPPORT,
    FEATURE_MULTI_ENTITY,
  ]),
};

/** Warning threshold — matches backend WARNING_THRESHOLD = 0.80 */
export const WARNING_THRESHOLD = 0.8;

// ── Pure helpers ──────────────────────────────────────────────────────────────

/** Returns the numeric limit for a resource on a plan, or null if unlimited. */
export function getLimit(plan: OrgPlan, resource: string): number | null {
  return PLAN_LIMITS[plan]?.[resource] ?? 0;
}

/** Returns true when the feature is available on this plan. */
export function isFeatureUnlocked(plan: OrgPlan, feature: string): boolean {
  return PLAN_FEATURES[plan]?.has(feature) ?? false;
}

/** Returns usage as a fraction (0–1+). Returns 0 for unlimited plans. */
export function usageFraction(plan: OrgPlan, resource: string, current: number): number {
  const lim = getLimit(plan, resource);
  if (lim === null) return 0;
  if (lim === 0) return current > 0 ? 1 : 0;
  return current / lim;
}

/** Returns true when usage is at or above the warning threshold. */
export function isApproachingLimit(plan: OrgPlan, resource: string, current: number): boolean {
  const frac = usageFraction(plan, resource, current);
  return frac >= WARNING_THRESHOLD && frac < 1.0;
}

/** Returns true when usage has reached 100 % of the plan limit. */
export function isLimitExceeded(plan: OrgPlan, resource: string, current: number): boolean {
  const lim = getLimit(plan, resource);
  if (lim === null) return false;
  return current >= lim;
}

// ── usePlanLimits hook ────────────────────────────────────────────────────────

export interface PlanLimitsContext {
  plan: OrgPlan;
  getLimit: (resource: string) => number | null;
  isFeatureUnlocked: (feature: string) => boolean;
  usageFraction: (resource: string, current: number) => number;
  isApproachingLimit: (resource: string, current: number) => boolean;
  isLimitExceeded: (resource: string, current: number) => boolean;
  billingUrl: string;
}

/**
 * React hook that returns plan-limit helpers bound to the caller's current plan.
 *
 * Usage:
 *   const limits = usePlanLimits(orgPlan);
 *   if (limits.isLimitExceeded(RESOURCE_PRODUCTS, productCount)) { ... }
 */
export function usePlanLimits(plan: OrgPlan): PlanLimitsContext {
  const billingUrl = "/en/settings/billing";
  return {
    plan,
    getLimit:           (r) => getLimit(plan, r),
    isFeatureUnlocked:  (f) => isFeatureUnlocked(plan, f),
    usageFraction:      (r, n) => usageFraction(plan, r, n),
    isApproachingLimit: (r, n) => isApproachingLimit(plan, r, n),
    isLimitExceeded:    (r, n) => isLimitExceeded(plan, r, n),
    billingUrl,
  };
}
