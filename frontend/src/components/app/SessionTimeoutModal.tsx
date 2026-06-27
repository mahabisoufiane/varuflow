"use client";

/**
 * SessionTimeoutModal
 *
 * Watches the Supabase session expiry and shows a 30-second countdown
 * modal when the session is about to expire.  Clicking "Stay Connected"
 * calls /api/session/keepalive (which triggers a Supabase token refresh
 * server-side) and dismisses the modal.  Clicking "Log Out Now" signs
 * the user out immediately.
 *
 * Accessibility: dialog role, aria-modal, aria-live countdown, focus trap
 * on mount so keyboard users can act without moving the mouse.
 */

import { useEffect, useRef, useState, useCallback } from "react";
import { createClient, isSupabaseConfigured } from "@/lib/supabase/client";
import { useRouter } from "@/i18n/navigation";
import { useLocale } from "next-intl";

/** Show the modal this many seconds before expiry. */
const WARN_BEFORE_SECONDS = 120;
/** Countdown from this value when the modal appears. */
const COUNTDOWN_START = 30;
/** Poll interval (ms) to check session expiry. */
const POLL_MS = 30_000;

export default function SessionTimeoutModal() {
  const supabase  = createClient();
  const router    = useRouter();
  const locale    = useLocale();

  const [visible,   setVisible]   = useState(false);
  const [countdown, setCountdown] = useState(COUNTDOWN_START);
  const [extending, setExtending] = useState(false);

  const countdownRef  = useRef<ReturnType<typeof setInterval> | null>(null);
  const pollRef       = useRef<ReturnType<typeof setInterval> | null>(null);
  const stayBtnRef    = useRef<HTMLButtonElement | null>(null);

  // ── Sign out helper ───────────────────────────────────────────────────────
  const signOut = useCallback(async () => {
    clearInterval(countdownRef.current ?? undefined);
    clearInterval(pollRef.current ?? undefined);
    if (isSupabaseConfigured) await supabase.auth.signOut();
    router.push(`/${locale}/auth/login`);
  }, [locale, router, supabase.auth]);

  // ── Show modal + start 30s countdown ─────────────────────────────────────
  const showModal = useCallback(() => {
    if (visible) return;
    setVisible(true);
    setCountdown(COUNTDOWN_START);

    clearInterval(countdownRef.current ?? undefined);
    countdownRef.current = setInterval(() => {
      setCountdown((c) => {
        if (c <= 1) {
          clearInterval(countdownRef.current ?? undefined);
          signOut();
          return 0;
        }
        return c - 1;
      });
    }, 1_000);

    // Move focus to the "Stay Connected" button for keyboard accessibility
    setTimeout(() => stayBtnRef.current?.focus(), 50);
  }, [visible, signOut]);

  // ── Session polling ───────────────────────────────────────────────────────
  const checkSession = useCallback(async () => {
    if (!isSupabaseConfigured) return;
    const { data: { session } } = await supabase.auth.getSession();
    if (!session) { signOut(); return; }

    const expiresAt  = session.expires_at ?? 0;           // unix seconds
    const nowSeconds = Math.floor(Date.now() / 1000);
    const remaining  = expiresAt - nowSeconds;

    if (remaining <= WARN_BEFORE_SECONDS) {
      showModal();
    } else if (visible) {
      // Session was refreshed externally — dismiss modal
      setVisible(false);
      clearInterval(countdownRef.current ?? undefined);
    }
  }, [isSupabaseConfigured, showModal, signOut, supabase.auth, visible]);

  // Start polling on mount
  useEffect(() => {
    checkSession();
    pollRef.current = setInterval(checkSession, POLL_MS);
    return () => {
      clearInterval(pollRef.current ?? undefined);
      clearInterval(countdownRef.current ?? undefined);
    };
  }, [checkSession]);

  // ── Stay Connected handler ────────────────────────────────────────────────
  const handleStay = useCallback(async () => {
    setExtending(true);
    clearInterval(countdownRef.current ?? undefined);
    try {
      // Proactively refresh the Supabase session
      const { error } = await supabase.auth.refreshSession();
      if (error) throw error;
      setVisible(false);
    } catch {
      // If refresh failed, sign out gracefully
      await signOut();
    } finally {
      setExtending(false);
    }
  }, [signOut, supabase.auth]);

  // ── Keyboard: Escape = sign out (not stay) — intentional ─────────────────
  useEffect(() => {
    if (!visible) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") signOut();
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [visible, signOut]);

  if (!visible) return null;

  return (
    // Backdrop
    <div
      className="fixed inset-0 z-[9999] flex items-center justify-center bg-black/70 backdrop-blur-sm"
      role="dialog"
      aria-modal="true"
      aria-labelledby="session-timeout-title"
      aria-describedby="session-timeout-desc"
    >
      <div className="w-full max-w-sm mx-4 rounded-2xl border shadow-2xl overflow-hidden"
        style={{ background: "var(--vf-bg-secondary)", borderColor: "var(--vf-border)" }}
      >
        {/* Header */}
        <div className="px-6 pt-6 pb-4">
          <div className="flex items-center gap-3 mb-3">
            {/* Warning icon */}
            <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-amber-500/15 border border-amber-500/20">
              <svg className="h-5 w-5 text-amber-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v4m0 4h.01M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z" />
              </svg>
            </div>
            <h2
              id="session-timeout-title"
              className="text-[15px] font-semibold"
              style={{ color: "var(--vf-text-primary)" }}
            >
              Session expiring soon
            </h2>
          </div>

          <p
            id="session-timeout-desc"
            className="text-[13px] leading-relaxed"
            style={{ color: "var(--vf-text-muted)" }}
          >
            Your session will expire due to inactivity. You will be signed out in:
          </p>

          {/* Countdown */}
          <div className="mt-4 flex items-center justify-center">
            <div className="flex flex-col items-center gap-1">
              <span
                className="text-5xl font-bold tabular-nums text-amber-400"
                aria-live="assertive"
                aria-atomic="true"
                aria-label={`${countdown} seconds remaining`}
              >
                {countdown}
              </span>
              <span className="text-[11px] font-medium text-slate-500 uppercase tracking-wider">
                seconds
              </span>
            </div>
          </div>
        </div>

        {/* Progress bar */}
        <div className="h-1 w-full" style={{ background: "var(--vf-border)" }}>
          <div
            className="h-full bg-amber-400 transition-all duration-1000"
            style={{ width: `${(countdown / COUNTDOWN_START) * 100}%` }}
          />
        </div>

        {/* Actions */}
        <div className="flex gap-3 px-6 py-4">
          <button
            ref={stayBtnRef}
            onClick={handleStay}
            disabled={extending}
            className="flex-1 rounded-xl py-2.5 text-[13px] font-semibold transition-all
              bg-indigo-600 hover:bg-indigo-500 active:bg-indigo-700
              text-white disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {extending ? "Extending…" : "Stay Connected"}
          </button>
          <button
            onClick={signOut}
            className="flex-1 rounded-xl py-2.5 text-[13px] font-medium transition-all
              border hover:bg-white/[0.05]"
            style={{ borderColor: "var(--vf-border)", color: "var(--vf-text-muted)" }}
          >
            Log Out Now
          </button>
        </div>
      </div>
    </div>
  );
}
