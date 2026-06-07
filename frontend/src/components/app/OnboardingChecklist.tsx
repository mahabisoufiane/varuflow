"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { useTranslations } from "next-intl";
import { Link } from "@/i18n/navigation";
import { api } from "@/lib/api-client";
import { cn } from "@/lib/utils";
import { CheckCircle2, Circle, X } from "lucide-react";

/**
 * Onboarding checklist card.
 *
 * Rendered on /dashboard. Self-hides when:
 *   • the user has dismissed it (persisted in localStorage), OR
 *   • the backend reports 100% completion (after a confetti burst).
 *
 * The dismissed flag is intentionally per-browser rather than a
 * server-side setting — the checklist is a lightweight nudge and
 * syncing its dismissed-state across devices would add a roundtrip
 * without meaningful product value.
 */

interface OnboardingStatus {
  completed_steps: string[];
  completion_pct: number;
  next_step: string | null;
}

const STEPS: { key: string; href: string }[] = [
  { key: "ADD_FIRST_PRODUCT",    href: "/inventory/products/new" },
  { key: "ADD_FIRST_CUSTOMER",   href: "/customers/new" },
  { key: "CREATE_FIRST_INVOICE", href: "/invoices/new" },
  { key: "INVITE_TEAM_MEMBER",   href: "/settings?tab=team" },
  { key: "CONNECT_FORTNOX",      href: "/settings?tab=integrations" },
  { key: "SEND_FIRST_INVOICE",   href: "/invoices" },
];

const DISMISS_KEY = "varuflow.onboarding.dismissed";

export default function OnboardingChecklist() {
  const t = useTranslations("onboarding");
  const [status, setStatus] = useState<OnboardingStatus | null>(null);
  const [dismissed, setDismissed] = useState(true); // default true — hide until we know
  const [loading, setLoading] = useState(true);
  const firedConfettiRef = useRef(false);

  // Initial load — read dismissed flag + fetch status in parallel.
  useEffect(() => {
    try {
      const v = typeof window !== "undefined" ? window.localStorage.getItem(DISMISS_KEY) : null;
      setDismissed(v === "1");
    } catch {
      setDismissed(false);
    }
    api.get<OnboardingStatus>("/api/onboarding")
      .then(setStatus)
      .catch(() => setStatus(null))
      .finally(() => setLoading(false));
  }, []);

  // Confetti on first transition to 100% — fire once per mount.
  useEffect(() => {
    if (!status || firedConfettiRef.current) return;
    if (status.completion_pct !== 100) return;
    firedConfettiRef.current = true;
    // Dynamic import — keeps canvas-confetti out of the initial bundle.
    import("canvas-confetti")
      .then((mod) => {
        const confetti = mod.default;
        confetti({
          particleCount: 140,
          spread: 90,
          origin: { y: 0.35 },
          colors: ["#4A6CF7", "#059669", "#D97706", "#ec4899"],
        });
      })
      .catch(() => {/* offline or blocked — silent */});
  }, [status]);

  const completedSet = useMemo(
    () => new Set(status?.completed_steps ?? []),
    [status],
  );

  function handleDismiss() {
    try {
      window.localStorage.setItem(DISMISS_KEY, "1");
    } catch {
      // Private mode / storage disabled — the card still closes for this
      // session, it'll just reappear on next load.
    }
    setDismissed(true);
  }

  if (loading || !status) return null;
  if (dismissed) return null;
  if (status.completion_pct === 100 && firedConfettiRef.current) {
    // Hide permanently once confetti has fired — also persist the dismiss
    // so a refresh doesn't re-show the finished card.
    try { window.localStorage.setItem(DISMISS_KEY, "1"); } catch { /* ignore */ }
    return null;
  }

  const completedCount = status.completed_steps.length;
  const total = STEPS.length;

  return (
    <div
      className="vf-section p-5 space-y-4 relative"
      style={{ borderRadius: 14 }}
    >
      <button
        type="button"
        onClick={handleDismiss}
        aria-label={t("dismiss")}
        className="absolute top-3 right-3 rounded-md p-1 opacity-60 hover:opacity-100 transition-opacity"
      >
        <X className="h-4 w-4" />
      </button>

      <div className="flex items-start justify-between gap-4 pr-8">
        <div>
          <h2 className="text-sm font-semibold vf-text-1">{t("checklist_title")}</h2>
          <p className="text-xs vf-text-m mt-0.5">
            {status.completion_pct === 100
              ? t("all_done")
              : t("progress_label", { done: completedCount, total })}
          </p>
        </div>
        <div className="text-right shrink-0">
          <div className="text-2xl font-bold vf-text-1 leading-none">
            {status.completion_pct}%
          </div>
        </div>
      </div>

      <div
        className="h-1.5 rounded-full overflow-hidden"
        style={{ background: "var(--vf-divider)" }}
        role="progressbar"
        aria-valuenow={status.completion_pct}
        aria-valuemin={0}
        aria-valuemax={100}
      >
        <div
          className="h-full bg-indigo-500 transition-all"
          style={{ width: `${status.completion_pct}%` }}
        />
      </div>

      <ul className="space-y-1.5">
        {STEPS.map((s) => {
          const done = completedSet.has(s.key);
          return (
            <li key={s.key}>
              <Link
                href={s.href}
                className={cn(
                  "flex items-center gap-2.5 text-sm py-1.5 px-2 rounded-md transition-colors",
                  done
                    ? "vf-text-m line-through opacity-70"
                    : "vf-text-2 hover:bg-white/5",
                )}
              >
                {done ? (
                  <CheckCircle2 className="h-4 w-4 text-emerald-400 shrink-0" />
                ) : (
                  <Circle className="h-4 w-4 vf-text-m shrink-0" />
                )}
                <span>{t(`step_${s.key}`)}</span>
              </Link>
            </li>
          );
        })}
      </ul>
    </div>
  );
}
