"use client";
// frontend/src/app/[locale]/(marketing)/blog/[slug]/TableOfContents.tsx

import { useState, useEffect } from "react";
import type { TocItem } from "@/lib/sanity/seed/posts";

export default function TableOfContents({ items }: { items: TocItem[] }) {
  const [active, setActive] = useState<string>("");

  useEffect(() => {
    const headings = items.map((i) => document.getElementById(i.id)).filter(Boolean);
    if (!headings.length) return;

    const observer = new IntersectionObserver(
      (entries) => {
        const visible = entries.filter((e) => e.isIntersecting);
        if (visible.length) setActive(visible[0].target.id);
      },
      { rootMargin: "-80px 0px -60% 0px", threshold: 0 },
    );
    headings.forEach((h) => observer.observe(h!));
    return () => observer.disconnect();
  }, [items]);

  if (!items.length) return null;

  return (
    <nav aria-label="Table of contents" className="rounded-xl border border-white/8 bg-white/4 p-5">
      <p className="mb-3 text-xs font-semibold uppercase tracking-widest text-slate-400">
        On this page
      </p>
      <ol className="space-y-1.5">
        {items.map((item) => (
          <li key={item.id} style={{ paddingLeft: item.level === 3 ? "0.75rem" : 0 }}>
            <a
              href={`#${item.id}`}
              className={`block text-sm transition-colors hover:text-indigo-300 ${
                active === item.id ? "font-medium text-indigo-400" : "text-slate-400"
              }`}
            >
              {item.title}
            </a>
          </li>
        ))}
      </ol>
    </nav>
  );
}
