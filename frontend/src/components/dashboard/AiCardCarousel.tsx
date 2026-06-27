"use client";

// File: src/components/dashboard/AiCardCarousel.tsx
// Purpose: Mobile-only horizontal scroll-snap carousel of AI action
// cards. Uses CSS `scroll-snap-type: x mandatory` (no JS lib). Pagination
// dots update via an IntersectionObserver watching each card — the dot
// for the most-visible card is filled.

import { useEffect, useRef, useState, type ReactNode } from "react";
import { useTranslations } from "next-intl";
import { cn } from "@/lib/utils";

export interface AiCarouselItem {
  id: string;
  icon: ReactNode;
  title: string;
  body: string;
  actionLabel?: string;
  onAction?: () => void;
}

interface Props { cards: AiCarouselItem[]; }

export default function AiCardCarousel({ cards }: Props) {
  const t = useTranslations();
  const scrollerRef = useRef<HTMLDivElement>(null);
  const [activeIdx, setActiveIdx] = useState(0);

  useEffect(() => {
    const root = scrollerRef.current;
    if (!root || cards.length === 0) return;
    const slides = Array.from(root.querySelectorAll<HTMLElement>("[data-carousel-slide]"));
    const obs = new IntersectionObserver(
      (entries) => {
        // Pick the entry with the highest intersection ratio.
        const best = entries
          .filter((e) => e.isIntersecting)
          .sort((a, b) => b.intersectionRatio - a.intersectionRatio)[0];
        if (!best) return;
        const idx = Number(best.target.getAttribute("data-idx"));
        if (!Number.isNaN(idx)) setActiveIdx(idx);
      },
      { root, threshold: [0.5, 0.75, 1] },
    );
    slides.forEach((s) => obs.observe(s));
    return () => obs.disconnect();
  }, [cards.length]);

  if (cards.length === 0) {
    return (
      <div
        data-testid="ai-carousel-empty"
        className="rounded-2xl border border-gray-200 bg-white p-8 text-center dark:border-white/10 dark:bg-white/5"
      >
        <p className="text-sm text-gray-500">{t("dashboard.ai_cards_empty")}</p>
      </div>
    );
  }

  return (
    <div data-testid="ai-carousel">
      <p className="mb-2 px-1 text-[11px] font-semibold uppercase tracking-wide text-gray-500">
        {t("dashboard.ai_cards_title", { count: cards.length })}
      </p>
      <div
        ref={scrollerRef}
        className="flex gap-3 overflow-x-auto pb-2 [scroll-snap-type:x_mandatory] [-ms-overflow-style:none] [scrollbar-width:none] [&::-webkit-scrollbar]:hidden"
      >
        {cards.map((c, i) => (
          <div
            key={c.id}
            data-carousel-slide
            data-idx={i}
            className="flex-shrink-0 rounded-2xl border border-gray-200 bg-white p-4 shadow-sm dark:border-white/10 dark:bg-white/5"
            style={{ width: "85vw", scrollSnapAlign: "start" }}
          >
            <div className="mb-2 flex items-center gap-2">{c.icon}<span className="text-sm font-semibold">{c.title}</span></div>
            <p className="mb-3 text-xs text-gray-600 dark:text-gray-300">{c.body}</p>
            {c.actionLabel && (
              <button
                type="button"
                onClick={c.onAction}
                className="h-10 rounded-lg bg-emerald-600 px-3 text-sm font-medium text-white"
              >{c.actionLabel}</button>
            )}
          </div>
        ))}
      </div>
      {/* Pagination dots */}
      <div className="mt-2 flex justify-center gap-1.5" data-testid="ai-carousel-dots">
        {cards.map((_, i) => (
          <span
            key={i}
            className={cn(
              "h-1.5 rounded-full transition-all",
              i === activeIdx ? "w-4 bg-emerald-600" : "w-1.5 bg-gray-300",
            )}
          />
        ))}
      </div>
    </div>
  );
}
