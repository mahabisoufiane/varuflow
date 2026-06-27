// File: src/components/marketing/ScrollReveal.tsx
// Purpose: GSAP + ScrollTrigger scroll-reveal for marketing pages. Fades and
//   rises a block (optionally staggering its direct children) as it scrolls
//   into view. Marketing-only by convention, so GSAP code-splits into the
//   marketing route chunks and never weighs down the app/dashboard bundle.
//
// Progressive enhancement: the children are always server-rendered and visible.
// The animation runs only on the client, after mount, and is skipped entirely
// under prefers-reduced-motion. Use it on BELOW-the-fold blocks (off-screen at
// load) so GSAP's `from` start-state can't cause a flash of the final layout.

"use client";

import { useEffect, useRef } from "react";
import { gsap } from "gsap";
import { ScrollTrigger } from "gsap/ScrollTrigger";

gsap.registerPlugin(ScrollTrigger);

interface ScrollRevealProps {
  children: React.ReactNode;
  className?: string;
  /** Stagger the direct children in sequence instead of animating as one block. */
  stagger?: boolean;
  /** Travel distance in px (default 24). */
  y?: number;
}

export function ScrollReveal({
  children,
  className,
  stagger = false,
  y = 24,
}: ScrollRevealProps) {
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    // Respect the user's OS setting — no movement, content stays as-rendered.
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;

    // gsap.context scopes selectors and gives us a single revert() for cleanup,
    // which also kills the ScrollTrigger instances this effect created.
    const ctx = gsap.context(() => {
      gsap.from(stagger ? Array.from(el.children) : el, {
        opacity: 0,
        y,
        duration: 0.5,
        ease: "power2.out",
        stagger: stagger ? 0.08 : 0,
        scrollTrigger: {
          trigger: el,
          start: "top 85%",
          toggleActions: "play none none none",
        },
      });
    }, el);

    return () => ctx.revert();
  }, [stagger, y]);

  return (
    <div ref={ref} className={className}>
      {children}
    </div>
  );
}
