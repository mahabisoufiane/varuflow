"use client";

import { useState } from "react";
import { ChevronDown } from "lucide-react";

export interface FAQItem {
  question: string;
  answer: string;
}

interface FAQProps {
  items: FAQItem[];
}

export function buildFAQSchema(items: FAQItem[]) {
  return {
    "@context": "https://schema.org",
    "@type": "FAQPage",
    mainEntity: items.map((item) => ({
      "@type": "Question",
      name: item.question,
      acceptedAnswer: {
        "@type": "Answer",
        text: item.answer,
      },
    })),
  };
}

export default function FAQ({ items }: FAQProps) {
  const [open, setOpen] = useState<number | null>(null);

  return (
    <div className="mx-auto max-w-2xl space-y-2">
      {items.map((item, i) => (
        <div
          key={i}
          className="rounded-xl border border-white/8 bg-white/4 transition-colors hover:border-white/15"
        >
          <button
            onClick={() => setOpen(open === i ? null : i)}
            aria-expanded={open === i}
            className="flex w-full items-center justify-between px-5 py-4 text-left"
          >
            <span className="vf-text-1 pr-4 text-sm font-medium">{item.question}</span>
            <ChevronDown
              className={`h-4 w-4 shrink-0 text-slate-500 transition-transform ${
                open === i ? "rotate-180" : ""
              }`}
            />
          </button>

          {open === i && (
            <div className="px-5 pb-5">
              <p className="vf-text-2 text-sm leading-relaxed">{item.answer}</p>
            </div>
          )}
        </div>
      ))}
    </div>
  );
}
