"use client";

// File: frontend/src/hooks/useMobileForm.ts
// Purpose: Touch-friendly form helpers (Item 15) — mobile detection,
// focus-next, scroll-to-first-error, numeric keyboard heuristics,
// sticky action-bar visibility gate.
//
// No external deps. SSR-safe: hooks guard for `typeof window`.

import { useCallback, useEffect, useRef, useState } from "react";

export const MOBILE_BREAKPOINT_PX = 768;

/** True when `window.innerWidth < 768px`. SSR renders false. */
export function useIsMobile(breakpointPx: number = MOBILE_BREAKPOINT_PX): boolean {
  const [isMobile, setIsMobile] = useState<boolean>(() => {
    if (typeof window === "undefined") return false;
    return window.innerWidth < breakpointPx;
  });

  useEffect(() => {
    if (typeof window === "undefined") return;
    const onResize = () => setIsMobile(window.innerWidth < breakpointPx);
    onResize();
    window.addEventListener("resize", onResize, { passive: true });
    return () => window.removeEventListener("resize", onResize);
  }, [breakpointPx]);

  return isMobile;
}

/** Pick the right HTML `inputMode` for a given semantic field type. */
export function inputModeFor(
  kind: "text" | "number" | "decimal" | "email" | "tel" | "url" | "search",
): React.HTMLAttributes<HTMLInputElement>["inputMode"] {
  switch (kind) {
    case "number":  return "numeric";
    case "decimal": return "decimal";
    case "email":   return "email";
    case "tel":     return "tel";
    case "url":     return "url";
    case "search":  return "search";
    default:        return "text";
  }
}

/**
 * Scroll the first element matching the invalid selector into view and
 * focus it. Returns true if an element was found.
 *
 * Default selector targets `aria-invalid="true"` + any control that
 * has the `.vf-invalid` helper class our FormField applies.
 */
export function scrollToFirstError(
  container?: HTMLElement | null,
  selector: string = '[aria-invalid="true"], .vf-invalid',
): boolean {
  if (typeof document === "undefined") return false;
  const root: ParentNode = container ?? document;
  const el = root.querySelector<HTMLElement>(selector);
  if (!el) return false;
  el.scrollIntoView({ behavior: "smooth", block: "center" });
  // Prefer focusing an input/textarea/select if we landed on a wrapper.
  const focusTarget =
    el.matches("input, textarea, select, button")
      ? el
      : el.querySelector<HTMLElement>("input, textarea, select, button");
  focusTarget?.focus({ preventScroll: true });
  return true;
}

/** Move focus to the next focusable field inside `formEl`. */
export function focusNextField(currentEl: HTMLElement): boolean {
  const form = currentEl.closest("form");
  if (!form) return false;
  const focusables = Array.from(
    form.querySelectorAll<HTMLElement>(
      'input:not([type="hidden"]):not([disabled]), textarea:not([disabled]), select:not([disabled]), button:not([disabled])',
    ),
  );
  const idx = focusables.indexOf(currentEl);
  if (idx === -1 || idx === focusables.length - 1) return false;
  focusables[idx + 1]?.focus();
  return true;
}

/**
 * Main hook — returns a bundle of helpers for a single form.
 *
 * Usage:
 *   const form = useMobileForm();
 *   <form ref={form.formRef} onSubmit={form.handleSubmit(onValidSubmit)}>
 *     ...
 *     <MobileFormActions visible={form.stickyVisible} ... />
 */
export function useMobileForm() {
  const isMobile = useIsMobile();
  const formRef = useRef<HTMLFormElement | null>(null);

  // Sticky bar is only meaningful on mobile once the form is long enough
  // to push the primary action below the fold. `setStickyVisible(true)`
  // is the default for mobile; callers can gate on scroll if desired.
  const [stickyVisible, setStickyVisible] = useState<boolean>(false);
  useEffect(() => setStickyVisible(isMobile), [isMobile]);

  /** Wrap your submit handler so we scroll-to-first-error on native invalidation. */
  const handleSubmit = useCallback(
    <E extends React.FormEvent<HTMLFormElement>>(
      onValid: (e: E) => void | Promise<void>,
    ) =>
      (e: E) => {
        const form = e.currentTarget as HTMLFormElement;
        if (typeof form.checkValidity === "function" && !form.checkValidity()) {
          e.preventDefault();
          // Native checkValidity stamps :invalid/aria-invalid-like state;
          // honour both. Prefer the first element reporting aria-invalid,
          // fall back to the first `:invalid` native.
          const target =
            form.querySelector<HTMLElement>('[aria-invalid="true"], .vf-invalid') ??
            form.querySelector<HTMLElement>(":invalid");
          if (target) {
            target.scrollIntoView({ behavior: "smooth", block: "center" });
            (target as HTMLInputElement).focus({ preventScroll: true });
          }
          return;
        }
        return onValid(e);
      },
    [],
  );

  return {
    isMobile,
    formRef,
    stickyVisible,
    setStickyVisible,
    handleSubmit,
    inputModeFor,
    scrollToFirstError,
    focusNextField,
  };
}

export default useMobileForm;
