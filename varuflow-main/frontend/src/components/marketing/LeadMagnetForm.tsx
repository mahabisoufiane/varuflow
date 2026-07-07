"use client";
// frontend/src/components/marketing/LeadMagnetForm.tsx
// Gated PDF download form — collects email before providing download link.

import { useState } from "react";
import { Download, Loader2, CheckCircle2, Lock } from "lucide-react";

const API = process.env.NEXT_PUBLIC_API_URL ?? "";

interface LeadMagnetFormProps {
  title: string;
  description: string;
  pdfSlug: string;
  buttonLabel?: string;
}

export default function LeadMagnetForm({
  title,
  description,
  pdfSlug,
  buttonLabel = "Download free PDF",
}: LeadMagnetFormProps) {
  const [email, setEmail] = useState("");
  const [name, setName] = useState("");
  const [loading, setLoading] = useState(false);
  const [done, setDone] = useState(false);
  const [error, setError] = useState("");

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!email) return;
    setLoading(true);
    setError("");

    try {
      // Register lead with newsletter/waitlist endpoint
      const res = await fetch(`${API}/api/waitlist`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          email,
          // Backend WaitlistJoin accepts { email, company_name } — extras are
          // ignored, so map the name field onto company_name to keep it.
          company_name: name || undefined,
          source: `lead_magnet_${pdfSlug}`,
        }),
      });
      // 409 = already signed up — still give download access
      if (!res.ok && res.status !== 409) throw new Error(`HTTP ${res.status}`);
      setDone(true);
    } catch {
      setError("Something went wrong. Please try again.");
    } finally {
      setLoading(false);
    }
  }

  if (done) {
    return (
      <div className="rounded-2xl border border-green-500/20 bg-green-500/8 p-6 text-center">
        <div className="mb-3 flex justify-center">
          <CheckCircle2 className="h-8 w-8 text-green-400" />
        </div>
        <p className="mb-1 font-semibold text-white">Check your inbox!</p>
        <p className="vf-text-2 mb-4 text-sm">
          We&apos;ve sent the {title} to <strong>{email}</strong>.
        </p>
        <a
          href={`/downloads/${pdfSlug}.pdf`}
          download
          className="vf-btn inline-flex items-center gap-2 rounded-xl px-5 py-2.5 text-sm font-semibold"
        >
          <Download className="h-4 w-4" /> Download now
        </a>
      </div>
    );
  }

  return (
    <div
      className="rounded-2xl border border-[var(--vf-brand-border)] bg-[var(--vf-brand-primary-subtle)] p-6"
      id="lead-magnet"
    >
      <div className="mb-1 flex items-center gap-2">
        <Lock className="h-4 w-4 text-[var(--vf-brand-primary-light)]" />
        <p className="text-xs font-semibold uppercase tracking-wider text-[var(--vf-brand-primary-light)]">
          Free download
        </p>
      </div>
      <h3 className="vf-text-1 mb-2 text-base font-bold">{title}</h3>
      <p className="vf-text-2 mb-5 text-sm leading-relaxed">{description}</p>

      <form onSubmit={handleSubmit} className="space-y-3">
        <input
          type="text"
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="Your name (optional)"
          className="vf-input w-full rounded-xl border px-4 py-2.5 text-sm outline-none focus:ring-2 focus:ring-[var(--vf-brand-primary)]"
          style={{ borderColor: "rgba(255,255,255,0.12)" }}
        />
        <input
          type="email"
          required
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          placeholder="your@email.com"
          className="vf-input w-full rounded-xl border px-4 py-2.5 text-sm outline-none focus:ring-2 focus:ring-[var(--vf-brand-primary)]"
          style={{ borderColor: "rgba(255,255,255,0.12)" }}
        />
        <button
          type="submit"
          disabled={loading}
          className="vf-btn flex w-full items-center justify-center gap-2 rounded-xl py-2.5 text-sm font-semibold"
        >
          {loading ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : (
            <>
              <Download className="h-4 w-4" /> {buttonLabel}
            </>
          )}
        </button>
        {error && <p className="text-xs text-red-400">{error}</p>}
        <p className="text-center text-[11px] text-slate-500">
          No spam. You&apos;ll receive occasional product updates. Unsubscribe anytime.
        </p>
      </form>
    </div>
  );
}
