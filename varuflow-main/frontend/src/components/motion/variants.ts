// File: src/components/motion/variants.ts
// Purpose: Shared framer-motion variants + timing constants. These MIRROR the
//          --vf-dur-* / --vf-ease-* CSS tokens in globals.css so JS-driven
//          motion feels identical to CSS-driven motion across the app.

import type { Variants } from "framer-motion";

/** Durations in seconds — mirror --vf-dur-fast/base/slow (150/250/400ms). */
export const DUR = { fast: 0.15, base: 0.25, slow: 0.4 } as const;

/** Easings — mirror --vf-ease-* cubic-beziers (mutable tuples for framer-motion). */
export const EASE_STANDARD: [number, number, number, number] = [0.4, 0, 0.2, 1];
export const EASE_EMPHASIZED: [number, number, number, number] = [0.2, 0, 0, 1];

/** Single element fading up into place — the app's default entrance. */
export const fadeInUp: Variants = {
  hidden: { opacity: 0, y: 12 },
  show: {
    opacity: 1,
    y: 0,
    transition: { duration: DUR.base, ease: EASE_STANDARD },
  },
};

/** Container that reveals its children one after another. */
export const staggerContainer = (
  staggerChildren = 0.06,
  delayChildren = 0,
): Variants => ({
  hidden: {},
  show: { transition: { staggerChildren, delayChildren } },
});
