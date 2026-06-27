// File: src/components/motion/Reveal.tsx
// Purpose: Fade-and-rise a block into view as it scrolls onto screen. This is
//          where framer-motion earns its place — viewport-triggered orchestration
//          that CSS keyframes can't do. Honors prefers-reduced-motion internally.

"use client";

import * as React from "react";
import { motion, useReducedMotion } from "framer-motion";
import { DUR, EASE_STANDARD } from "./variants";

export interface RevealProps {
  children: React.ReactNode;
  className?: string;
  /** Delay before this element animates in (seconds). */
  delay?: number;
  /** Animate only the first time it enters the viewport (default true). */
  once?: boolean;
  /** Fraction of the element that must be visible to trigger (default 0.2). */
  amount?: number;
}

export function Reveal({
  children,
  className,
  delay = 0,
  once = true,
  amount = 0.2,
}: RevealProps) {
  const reduce = useReducedMotion();

  // Reduced motion: render statically so content is instantly visible, no move.
  if (reduce) {
    return <div className={className}>{children}</div>;
  }

  return (
    <motion.div
      className={className}
      initial="hidden"
      whileInView="show"
      viewport={{ once, amount }}
      variants={{
        hidden: { opacity: 0, y: 12 },
        show: {
          opacity: 1,
          y: 0,
          transition: { duration: DUR.base, ease: EASE_STANDARD, delay },
        },
      }}
    >
      {children}
    </motion.div>
  );
}
