import { api } from "@/lib/api-client";

/**
 * Onboarding step keys — keep in sync with
 * `backend/app/routers/onboarding.ONBOARDING_STEPS`.
 */
export type OnboardingStep =
  | "ADD_FIRST_PRODUCT"
  | "ADD_FIRST_CUSTOMER"
  | "CREATE_FIRST_INVOICE"
  | "INVITE_TEAM_MEMBER"
  | "CONNECT_FORTNOX"
  | "SEND_FIRST_INVOICE";

/**
 * Fire-and-forget: mark an onboarding step complete.
 * Errors are swallowed — the checklist is a nudge, not a
 * transactional guarantee, and must never block the user flow.
 *
 * The backend is idempotent on (org_id, step) so repeated calls
 * for the same step after the first are cheap no-ops.
 */
export function markOnboardingStep(step: OnboardingStep): void {
  api.post<{ completion_pct: number }>("/api/onboarding/complete-step", { step })
    .catch(() => {/* ignore */});
}
