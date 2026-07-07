"use client";

import { useState } from "react";
import { Loader2, CheckCircle2 } from "lucide-react";

const API = process.env.NEXT_PUBLIC_API_URL ?? "";

export default function NewsletterSignup({ compact = false }: { compact?: boolean }) {
  const [email, setEmail] = useState("");
  const [loading, setLoading] = useState(false);
  const [done, setDone] = useState(false);
  const [error, setError] = useState("");

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!email) return;
    setLoading(true);
    setError("");

    try {
      // Best-effort: POST to /api/waitlist (re-use existing waitlist endpoint for newsletter)
      const res = await fetch(`${API}/api/waitlist`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, source: "newsletter_signup" }),
      });
      if (!res.ok && res.status !== 409) {
        // 409 = already signed up, still treat as success
        throw new Error(`HTTP ${res.status}`);
      }
      setDone(true);
    } catch {
      setError("Something went wrong. Please try again.");
    } finally {
      setLoading(false);
    }
  }

  if (done) {
    return (
      <div className="flex items-center justify-center gap-2 rounded-xl border border-green-500/30 bg-green-500/10 px-5 py-4 text-sm text-green-400">
        <CheckCircle2 className="h-4 w-4" />
        <span>Great! We&apos;ll send you the Bokföringslagen checklist shortly.</span>
      </div>
    );
  }

  return (
    <form onSubmit={handleSubmit} className={`flex gap-2 ${compact ? "max-w-xs flex-col" : "max-w-md"}`}>
      <input
        type="email"
        required
        value={email}
        onChange={(e) => setEmail(e.target.value)}
        placeholder="your@email.com"
        className="vf-input min-w-0 flex-1 rounded-xl border px-4 py-2.5 text-sm outline-none focus:ring-2 focus:ring-[var(--vf-brand-primary)]"
        style={{ borderColor: "rgba(255,255,255,0.12)" }}
      />
      <button
        type="submit"
        disabled={loading}
        className="vf-btn shrink-0 rounded-xl px-5 py-2.5 text-sm font-semibold"
      >
        {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : "Get checklist"}
      </button>
      {error && <p className="vf-text-m mt-1 text-xs text-red-400">{error}</p>}
    </form>
  );
}
