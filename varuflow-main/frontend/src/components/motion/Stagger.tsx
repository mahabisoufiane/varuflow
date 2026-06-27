// File: src/components/motion/Stagger.tsx
// Purpose: Reveal a list/grid of children one after another as it scrolls into
//          view. Pair <Stagger> with <StaggerItem> for each row/card. Both honor
//          prefers-reduced-motion independently so either can be used alone.

"use client";

import * as React from "react";
import { motion, useReducedMotion } from "framer-motion";
import { DUR, EASE_STANDARD } from "./variants";

export interface StaggerProps {
  children: React.ReactNode;
  className?: string;
  /** Seconds between each child animating in (default 0.06). */
  stagger?: number;
  /** Delay before the first child starts (seconds). */
  delayChildren?: number;
  once?: boolean;
  amount?: number;
}

export function Stagger({
  children,
  className,
  stagger = 0.06,
  delayChildren = 0,
  once = true,
  amount = 0.15,
}: StaggerProps) {
  const reduce = useReducedMotion();

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
        hidden: {},
        show: { transition: { staggerChildren: stagger, delayChildren } },
      }}
    >
      {children}
    </motion.div>
  );
}

export function StaggerItem({
  children,
  className,
}: {
  children: React.ReactNode;
  className?: string;
}) {
  const reduce = useReducedMotion();

  if (reduce) {
    return <div className={className}>{children}</div>;
  }

  return (
    <motion.div
      className={className}
      variants={{
        hidden: { opacity: 0, y: 12 },
        show: {
          opacity: 1,
          y: 0,
          transition: { duration: DUR.base, ease: EASE_STANDARD },
        },
      }}
    >
      {children}
    </motion.div>
  );
}
