// File: src/app/[locale]/auth/forgot-password/page.tsx
// Purpose: Password reset request page — sends reset email via Supabase
// Used by: Login page "Forgot password?" link

"use client";

import { createClient } from "@/lib/supabase/client";
// Use next-intl Link so locale is injected automatically
import { Link } from "@/i18n/navigation";
import { useState } from "react";
import { ArrowRight, ArrowLeft, Loader2, Mail } from "lucide-react";

export default function ForgotPasswordPage() {
  const supabase = createClient();
  const [email, setEmail]   = useState("");
  const [loading, setLoading] = useState(false);
  const [sent, setSent]     = useState(false);
  const [error, setError]   = useState<string | null>(null);

  async function handleSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setLoading(true);
    setError(null);
    const { error } = await supabase.auth.resetPasswordForEmail(email, {
      // Callback URL uses the current origin so it works on every environment
      redirectTo: `${location.origin}/en/auth/reset-password`,
    });
    setLoading(false);
    if (error) return setError(error.message);
    setSent(true);
  }

  if (sent) {
    return (
      <div
        className="flex min-h-screen items-center justify-center px-6"
        style={{ background: "var(--vf-bg-primary)" }}
      >
        <div className="w-full max-w-sm space-y-6 text-center animate-fade-in">
          <div
            className="mx-auto flex h-14 w-14 items-center justify-center rounded-2xl"
            style={{ background: "rgba(99,102,241,0.15)", border: "1px solid rgba(99,102,241,0.2)" }}
          >
            <Mail className="h-7 w-7 text-[#6366F1]" />
          </div>
          <div className="space-y-2">
            <h2 className="text-2xl font-bold" style={{ color: "var(--vf-text-primary)" }}>
              Check your inbox
            </h2>
            <p className="text-sm" style={{ color: "var(--vf-text-secondary)" }}>
              We sent a reset link to{" "}
              <span className="font-semibold" style={{ color: "var(--vf-text-primary)" }}>{email}</span>.
              <br />It expires in 1 hour.
            </p>
          </div>
          <Link
            href="/auth/login"
            className="inline-flex items-center gap-1.5 text-sm font-medium text-[#6366F1] hover:text-[#4F46E5] transition-colors"
          >
            <ArrowLeft className="h-3.5 w-3.5" />
            Back to sign in
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div
      className="flex min-h-screen items-center justify-center px-6"
      style={{ background: "var(--vf-bg-primary)" }}
    >
      <div className="w-full max-w-sm space-y-8 animate-fade-in">
        <Link
          href="/auth/login"
          className="inline-flex items-center gap-1.5 text-sm transition-colors"
          style={{ color: "var(--vf-text-muted)" }}
        >
          <ArrowLeft className="h-3.5 w-3.5" />
          Back to sign in
        </Link>

        <div className="space-y-1">
          <h2 className="text-2xl font-bold" style={{ color: "var(--vf-text-primary)" }}>
            Forgot your password?
          </h2>
          <p className="text-sm" style={{ color: "var(--vf-text-secondary)" }}>
            Enter your email and we&apos;ll send you a reset link.
          </p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="space-y-1.5">
            <label htmlFor="email" className="text-xs font-medium" style={{ color: "var(--vf-text-secondary)" }}>
              Work email
            </label>
            <input
              id="email"
              type="email"
              required
              autoComplete="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="you@company.se"
              className="vf-input"
            />
          </div>

          {error && (
            <div className="flex items-start gap-2 rounded-xl border border-red-500/20 bg-red-500/10 px-3.5 py-2.5 text-sm text-red-400">
              <span className="mt-0.5 shrink-0">⚠</span>
              {error}
            </div>
          )}

          <button type="submit" disabled={loading} className="vf-btn w-full">
            {loading ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <>Send reset link <ArrowRight className="h-4 w-4" /></>
            )}
          </button>
        </form>
      </div>
    </div>
  );
}
