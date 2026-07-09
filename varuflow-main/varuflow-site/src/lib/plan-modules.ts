// Which product modules each marketing tier includes.
//
// Source: backend app/services/plan_limits.py
//   - PLAN_MODULES: FREE = {dashboard, settings} (showcase only),
//     PRO = all operational modules, ENTERPRISE = "*"
//   - The comment on _PRO: "PRO plan — covers both Starter (499 SEK) and
//     Professional (1490 SEK) tiers" — i.e. BOTH paid tiers run on the
//     backend PRO plan. Tiers therefore differ by limits and platform
//     flags, not by module access: every paid tier includes all six
//     marketed modules.
import type { TierId } from "./pricing";

const BACKEND_PLAN: Record<TierId, "PRO" | "ENTERPRISE"> = {
  starter: "PRO",
  professional: "PRO",
  enterprise: "ENTERPRISE",
};

const PLAN_MODULES: Record<"PRO" | "ENTERPRISE", "*" | readonly string[]> = {
  PRO: [
    "dashboard", "analytics", "pos", "invoicing", "inventory",
    "crm", "hr", "finance", "ai", "manufacturing", "settings",
  ],
  ENTERPRISE: "*",
};

export function tierIncludesModule(tier: TierId, gate: string): boolean {
  const mods = PLAN_MODULES[BACKEND_PLAN[tier]];
  return mods === "*" || mods.includes(gate);
}
