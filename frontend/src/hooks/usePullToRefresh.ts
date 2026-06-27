"use client";

// File: src/hooks/usePullToRefresh.ts
// Purpose: Native touch-event pull-to-refresh for mobile web. Only
// activates when the page is scrolled to the very top (window.scrollY === 0)
// so it never clashes with interior scroll containers. Rubber-band
// translates the page content, fires onRefresh past a 60 px threshold
// and snaps back with a CSS transition.
//
// Usage:
//   const { isRefreshing, pullDistance, isPulling, handlers } =
//     usePullToRefresh({ onRefresh: async () => { ... } });
//   <div {...handlers} style={{ transform: `translateY(${pullDistance}px)` }}>

import { useCallback, useRef, useState } from "react";

interface Options {
  onRefresh: () => void | Promise<void>;
  /** Px of pull required to trigger a refresh. */
  threshold?: number;
  /** Max rubber-band translate in px. */
  maxPull?: number;
  /** Resistance factor — 0.4 = pull feels "heavy", 1.0 = 1:1. */
  resistance?: number;
}

export function usePullToRefresh({
  onRefresh,
  threshold = 60,
  maxPull = 80,
  resistance = 0.4,
}: Options) {
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [pullDistance, setPullDistance] = useState(0);
  const [isPulling, setIsPulling] = useState(false);
  const startY = useRef(0);
  const activePull = useRef(false);

  const onTouchStart = useCallback((e: React.TouchEvent) => {
    if (isRefreshing) return;
    // Only arm the pull when the page itself is scrolled to top.
    if (typeof window !== "undefined" && window.scrollY > 0) return;
    startY.current = e.touches[0].clientY;
    activePull.current = true;
  }, [isRefreshing]);

  const onTouchMove = useCallback((e: React.TouchEvent) => {
    if (!activePull.current || isRefreshing) return;
    const dy = e.touches[0].clientY - startY.current;
    if (dy <= 0) {
      // User scrolled upward — stop pulling.
      if (isPulling) setIsPulling(false);
      setPullDistance(0);
      return;
    }
    setIsPulling(true);
    setPullDistance(Math.min(dy * resistance, maxPull));
  }, [isRefreshing, isPulling, maxPull, resistance]);

  const onTouchEnd = useCallback(async () => {
    if (!activePull.current) return;
    activePull.current = false;
    const triggered = pullDistance >= threshold && !isRefreshing;
    setIsPulling(false);
    setPullDistance(0);
    if (triggered) {
      if (typeof navigator !== "undefined" && navigator.vibrate) navigator.vibrate(10);
      setIsRefreshing(true);
      try { await onRefresh(); }
      finally { setIsRefreshing(false); }
    }
  }, [pullDistance, threshold, isRefreshing, onRefresh]);

  return {
    isRefreshing,
    pullDistance,
    isPulling,
    handlers: { onTouchStart, onTouchMove, onTouchEnd },
  };
}
