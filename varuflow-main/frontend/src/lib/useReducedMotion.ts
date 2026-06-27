// File: src/lib/useReducedMotion.ts
// Purpose: Reactive `prefers-reduced-motion` reader for app code (confetti,
//          conditional heavy animations) that doesn't pull in framer-motion.
// Used by: any client component that wants to skip motion for a11y.

"use client";

import { useEffect, useState } from "react";

/**
 * Returns true when the user has asked the OS for reduced motion.
 *
 * SSR-safe: defaults to `false` on the server and the first client render,
 * then syncs after mount and stays reactive to live changes in the setting.
 * For framer-motion components prefer that library's own `useReducedMotion`.
 */
export function useReducedMotion(): boolean {
  const [reduced, setReduced] = useState(false);

  useEffect(() => {
    if (typeof window === "undefined" || !window.matchMedia) return;
    const mq = window.matchMedia("(prefers-reduced-motion: reduce)");
    setReduced(mq.matches);
    const onChange = (e: MediaQueryListEvent) => setReduced(e.matches);
    mq.addEventListener("change", onChange);
    return () => mq.removeEventListener("change", onChange);
  }, []);

  return reduced;
}
