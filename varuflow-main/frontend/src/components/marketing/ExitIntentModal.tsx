"use client";

import { useEffect, useState } from "react";
import { Link } from "@/i18n/navigation";
import { X } from "lucide-react";

const COOKIE_KEY = "vf_exit_intent_dismissed";
const COOKIE_DAYS = 7;

function setCookie(name: string, value: string, days: number) {
  const expires = new Date(Date.now() + days * 86400_000).toUTCString();
  document.cookie = `${name}=${value}; expires=${expires}; path=/; SameSite=Lax`;
}

function getCookie(name: string): string {
  return document.cookie
    .split("; ")
    .find((row) => row.startsWith(`${name}=`))
    ?.split("=")[1] ?? "";
}

export default function ExitIntentModal(_props: {
  headline?: string;
  subheadline?: string;
  ctaLabel?: string;
}) {
  const [show, setShow] = useState(false);

  useEffect(() => {
    if (getCookie(COOKIE_KEY) === "1") return;

    function handleMouseLeave(e: MouseEvent) {
      if (e.clientY <= 5) {
        setShow(true);
        document.removeEventListener("mouseleave", handleMouseLeave);
      }
    }

    // Only fire on desktop
    if (window.matchMedia("(pointer: fine)").matches) {
      document.addEventListener("mouseleave", handleMouseLeave);
    }

    return () => document.removeEventListener("mouseleave", handleMouseLeave);
  }, []);

  function dismiss() {
    setShow(false);
    setCookie(COOKIE_KEY, "1", COOKIE_DAYS);
  }

  if (!show) return null;

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label="Special offer"
      className="fixed inset-0 z-[200] flex items-center justify-center p-4"
      style={{ background: "rgba(0,0,0,0.70)", backdropFilter: "blur(6px)" }}
    >
      <div
        className="relative w-full max-w-md rounded-2xl border border-white/10 p-8 text-center shadow-2xl"
        style={{ background: "#141c2e" }}
      >
        <button
          onClick={dismiss}
          aria-label="Close"
          className="absolute right-4 top-4 rounded-full border border-white/10 p-1.5 text-slate-500 hover:text-white"
        >
          <X className="h-4 w-4" />
        </button>

        <div className="mb-4 mx-auto flex h-12 w-12 items-center justify-center rounded-xl bg-gradient-to-br from-[var(--vf-brand-primary)] to-[var(--vf-brand-primary-hover)]">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
            <polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2" />
          </svg>
        </div>

        <h2 className="vf-text-1 text-xl font-bold">Before you go…</h2>
        <p className="vf-text-2 mt-3 text-sm leading-relaxed">
          Start your 14-day Pro trial today — no credit card required, cancel anytime.
          Full access to all features from day one.
        </p>

        <Link
          href="/trial"
          onClick={dismiss}
          className="vf-btn mt-6 block w-full rounded-xl py-3 text-sm font-semibold"
        >
          Start free trial
        </Link>

        <button
          onClick={dismiss}
          className="vf-text-m mt-3 block w-full text-xs hover:underline"
        >
          No thanks, I&apos;ll pay full price later
        </button>
      </div>
    </div>
  );
}
