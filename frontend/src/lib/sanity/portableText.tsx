"use client";
// frontend/src/lib/sanity/portableText.tsx
// PortableText renderer for Sanity blog body. Used only when Sanity is live.

import { PortableText, type PortableTextComponents } from "@portabletext/react";
import Image from "next/image";
import { urlForWidth } from "./image";

const ptComponents: PortableTextComponents = {
  types: {
    image: ({ value }) => {
      const imgUrl = urlForWidth(value, 1200);
      if (!imgUrl) return null;
      return (
        <figure className="my-8">
          <div className="relative overflow-hidden rounded-2xl border border-white/8">
            <Image
              src={imgUrl}
              alt={value.alt ?? ""}
              width={1200}
              height={675}
              className="w-full object-cover"
            />
          </div>
          {value.caption && (
            <figcaption className="mt-2 text-center text-xs text-slate-500">
              {value.caption}
            </figcaption>
          )}
        </figure>
      );
    },
    codeBlock: ({ value }) => (
      <pre className="my-6 overflow-x-auto rounded-xl border border-white/8 bg-[#0d1117] p-4">
        {value.filename && (
          <div className="mb-3 text-xs font-mono text-slate-500">{value.filename}</div>
        )}
        <code className={`language-${value.language ?? "plaintext"} text-sm text-slate-200`}>
          {value.code}
        </code>
      </pre>
    ),
    callout: ({ value }) => {
      const variants = {
        info: "border-indigo-500/30 bg-indigo-500/10 text-indigo-300",
        warning: "border-yellow-500/30 bg-yellow-500/10 text-yellow-300",
        success: "border-green-500/30 bg-green-500/10 text-green-300",
        tip: "border-violet-500/30 bg-violet-500/10 text-violet-300",
      } as const;
      const cls = variants[(value.variant as keyof typeof variants) ?? "info"] ?? variants.info;
      return (
        <div className={`my-6 rounded-xl border px-5 py-4 text-sm leading-relaxed ${cls}`}>
          {value.body}
        </div>
      );
    },
  },
  block: {
    h2: ({ children }) => (
      <h2 className="mt-12 mb-4 text-xl font-bold text-white" style={{ scrollMarginTop: "80px" }}>
        {children}
      </h2>
    ),
    h3: ({ children }) => (
      <h3 className="mt-8 mb-3 text-base font-semibold text-white" style={{ scrollMarginTop: "80px" }}>
        {children}
      </h3>
    ),
    blockquote: ({ children }) => (
      <blockquote className="my-6 border-l-4 border-indigo-500 pl-5 text-slate-300 italic">
        {children}
      </blockquote>
    ),
    normal: ({ children }) => <p className="my-4 leading-relaxed">{children}</p>,
  },
  list: {
    bullet: ({ children }) => (
      <ul className="my-4 ml-6 space-y-2 list-disc text-slate-300">{children}</ul>
    ),
    number: ({ children }) => (
      <ol className="my-4 ml-6 space-y-2 list-decimal text-slate-300">{children}</ol>
    ),
  },
  marks: {
    strong: ({ children }) => <strong className="font-semibold text-white">{children}</strong>,
    em: ({ children }) => <em className="text-slate-300">{children}</em>,
    code: ({ children }) => (
      <code className="rounded bg-white/8 px-1.5 py-0.5 font-mono text-xs text-indigo-300">
        {children}
      </code>
    ),
    link: ({ value, children }) => (
      <a
        href={value?.href}
        target={value?.blank ? "_blank" : undefined}
        rel={value?.blank ? "noopener noreferrer" : undefined}
        className="text-indigo-400 underline hover:text-indigo-300"
      >
        {children}
      </a>
    ),
    internalLink: ({ value, children }) => (
      <a href={value?.href} className="text-indigo-400 underline hover:text-indigo-300">
        {children}
      </a>
    ),
  },
};

export function SanityBody({ body }: { body: unknown[] }) {
  return (
    <div className="text-slate-300 text-base leading-relaxed">
      <PortableText value={body} components={ptComponents} />
    </div>
  );
}
