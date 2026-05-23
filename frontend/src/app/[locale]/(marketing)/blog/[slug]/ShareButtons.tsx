"use client";
// frontend/src/app/[locale]/(marketing)/blog/[slug]/ShareButtons.tsx

import { useState } from "react";
import { Link2, Twitter, Linkedin, Check } from "lucide-react";

interface ShareButtonsProps {
  url: string;
  title: string;
}

export default function ShareButtons({ url, title }: ShareButtonsProps) {
  const [copied, setCopied] = useState(false);

  async function copyLink() {
    await navigator.clipboard.writeText(url);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }

  const encoded = encodeURIComponent(url);
  const encodedTitle = encodeURIComponent(title);

  return (
    <div className="flex items-center gap-2">
      <span className="text-xs text-slate-500">Share:</span>
      <a
        href={`https://twitter.com/intent/tweet?url=${encoded}&text=${encodedTitle}`}
        target="_blank"
        rel="noopener noreferrer"
        aria-label="Share on X / Twitter"
        className="flex h-8 w-8 items-center justify-center rounded-lg bg-white/6 text-slate-400 transition-colors hover:bg-white/12 hover:text-white"
      >
        <Twitter className="h-3.5 w-3.5" />
      </a>
      <a
        href={`https://www.linkedin.com/sharing/share-offsite/?url=${encoded}`}
        target="_blank"
        rel="noopener noreferrer"
        aria-label="Share on LinkedIn"
        className="flex h-8 w-8 items-center justify-center rounded-lg bg-white/6 text-slate-400 transition-colors hover:bg-white/12 hover:text-white"
      >
        <Linkedin className="h-3.5 w-3.5" />
      </a>
      <button
        onClick={copyLink}
        aria-label="Copy link"
        className="flex h-8 w-8 items-center justify-center rounded-lg bg-white/6 text-slate-400 transition-colors hover:bg-white/12 hover:text-white"
      >
        {copied ? <Check className="h-3.5 w-3.5 text-green-400" /> : <Link2 className="h-3.5 w-3.5" />}
      </button>
    </div>
  );
}
