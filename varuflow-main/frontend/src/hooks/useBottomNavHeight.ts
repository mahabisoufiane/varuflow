"use client";

// File: src/hooks/useBottomNavHeight.ts
// Purpose: Measures the rendered height of the mobile bottom nav and
// publishes it as `--bottom-nav-height` on <html> so any component
// (e.g. the FAB, the main scroll container padding-bottom) can reserve
// space without hard-coding 64 px. Desktop sets the var to `0px`.

import { useEffect } from "react";

const MOBILE_BREAKPOINT_PX = 768;

export function useBottomNavHeight(navSelector = "[data-mobile-bottom-nav]") {
  useEffect(() => {
    if (typeof window === "undefined") return;
    const root = document.documentElement;

    function apply() {
      const isMobile = window.matchMedia(`(max-width: ${MOBILE_BREAKPOINT_PX - 1}px)`).matches;
      if (!isMobile) {
        root.style.setProperty("--bottom-nav-height", "0px");
        return;
      }
      const el = document.querySelector<HTMLElement>(navSelector);
      if (!el) {
        // Fallback — 64 px + safe-area-inset-bottom.
        root.style.setProperty(
          "--bottom-nav-height",
          "calc(64px + env(safe-area-inset-bottom))",
        );
        return;
      }
      root.style.setProperty("--bottom-nav-height", `${el.offsetHeight}px`);
    }

    apply();
    window.addEventListener("resize", apply);
    const obs = typeof ResizeObserver !== "undefined" ? new ResizeObserver(apply) : null;
    const el = document.querySelector<HTMLElement>(navSelector);
    if (obs && el) obs.observe(el);
    return () => {
      window.removeEventListener("resize", apply);
      obs?.disconnect();
    };
  }, [navSelector]);
}
