// File: src/app/[locale]/(app)/template.tsx
// Purpose: Subtle cross-fade on every in-app route change. A *template* (unlike
//          a layout) re-mounts on each navigation, so wrapping its children
//          gives an enter animation every time the route changes.
//
// Opacity-only on purpose: no transform means this never becomes a containing
// block, so it can't break `position: fixed`/`sticky` content inside a page.
// Honors prefers-reduced-motion (renders children straight through).

"use client";

import { motion, useReducedMotion } from "framer-motion";
import { DUR, EASE_STANDARD } from "@/components/motion/variants";

export default function AppRouteTemplate({
  children,
}: {
  children: React.ReactNode;
}) {
  const reduce = useReducedMotion();
  if (reduce) return <>{children}</>;

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      transition={{ duration: DUR.fast, ease: EASE_STANDARD }}
    >
      {children}
    </motion.div>
  );
}
