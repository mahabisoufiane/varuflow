"use client";

import { useState } from "react";
import { ChevronLeft, ChevronRight, Quote } from "lucide-react";

export interface Testimonial {
  quote: string;
  author: string;
  role: string;
  company: string;
  initials: string;
}

interface TestimonialCarouselProps {
  testimonials: Testimonial[];
}

export default function TestimonialCarousel({ testimonials }: TestimonialCarouselProps) {
  const [idx, setIdx] = useState(0);
  const t = testimonials[idx];

  function prev() {
    setIdx((i) => (i - 1 + testimonials.length) % testimonials.length);
  }
  function next() {
    setIdx((i) => (i + 1) % testimonials.length);
  }

  return (
    <div className="mx-auto max-w-2xl text-center">
      <Quote className="mx-auto mb-6 h-8 w-8 text-indigo-500/50" />

      <blockquote className="vf-text-1 text-xl font-medium leading-relaxed">
        &ldquo;{t.quote}&rdquo;
      </blockquote>

      <div className="mt-6 flex items-center justify-center gap-3">
        <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-indigo-600 text-sm font-bold text-white">
          {t.initials}
        </div>
        <div className="text-left">
          <p className="vf-text-1 text-sm font-semibold">{t.author}</p>
          <p className="vf-text-m text-xs">
            {t.role} · {t.company}
          </p>
        </div>
      </div>

      {testimonials.length > 1 && (
        <div className="mt-8 flex items-center justify-center gap-4">
          <button
            onClick={prev}
            className="rounded-full border border-white/15 p-2 text-slate-400 transition-colors hover:border-white/30 hover:text-white"
            aria-label="Previous testimonial"
          >
            <ChevronLeft className="h-4 w-4" />
          </button>

          <div className="flex gap-1.5">
            {testimonials.map((_, i) => (
              <button
                key={i}
                onClick={() => setIdx(i)}
                className={`h-1.5 rounded-full transition-all ${
                  i === idx ? "w-6 bg-indigo-500" : "w-1.5 bg-white/20"
                }`}
                aria-label={`Go to testimonial ${i + 1}`}
              />
            ))}
          </div>

          <button
            onClick={next}
            className="rounded-full border border-white/15 p-2 text-slate-400 transition-colors hover:border-white/30 hover:text-white"
            aria-label="Next testimonial"
          >
            <ChevronRight className="h-4 w-4" />
          </button>
        </div>
      )}
    </div>
  );
}
