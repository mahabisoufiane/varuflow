/**
 * Role-within-module helpers — the frontend mirror of the backend
 * `require_role` gate (backend/app/middleware/plan_check.py).
 *
 * Having a *module* lets you open a feature area; your *role* then decides
 * how much of it you see:
 *   MEMBER = regular employee (own data: own leave, own timesheet, clock in/out)
 *   ADMIN  = manager / HR admin (team data: roster, approvals, reviews)
 *   OWNER  = owner (payroll, salaries, destructive actions)
 *
 * Keep ROLE_RANK in sync with _ROLE_RANK on the backend.
 */
export type OrgRole = "MEMBER" | "ADMIN" | "OWNER";

export const ROLE_RANK: Record<OrgRole, number> = {
  MEMBER: 0,
  ADMIN: 1,
  OWNER: 2,
};

/**
 * True when `current` is senior enough to satisfy a `minimum` requirement.
 * Unknown/missing roles are treated as the lowest rank (deny-by-default).
 */
export function hasMinRole(current: string | null | undefined, minimum: OrgRole): boolean {
  const have = ROLE_RANK[(current as OrgRole)] ?? 0;
  const need = ROLE_RANK[minimum] ?? 99;
  return have >= need;
}
