"use client";

import { supabase } from "@/lib/supabase/client";
import Link from "next/link";
import { useState } from "react";
import { ArrowRight, ArrowLeft, Loader2, Mail } from "lucide-react";

export default function ForgotPasswordPage() {
  const [email, setEmail] = useState("");
  const [loading, setLoading] = useState(false);
  const [sent, setSent] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError(null);

    const { error } = await supabase.auth.resetPasswordForEmail(email, {
      redirectTo: `${location.origin}/auth/reset-password`,
    });

    setLoading(false);
    if (error) return setError(error.message);
    setSent(true);
  }

  if (sent) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-gray-50 px-6">
        <div className="w-full max-w-sm space-y-6 text-center">
          <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-2xl bg-[#1a2332]/8 text-[#1a2332]">
            <Mail className="h-7 w-7" />
          </div>
          <div className="space-y-2">
            <h2 className="text-2xl font-bold text-[#1a2332]">Check your inbox</h2>
            <p className="text-sm text-gray-500">
              We sent a reset link to{" "}
              <span className="font-medium text-gray-800">{email}</span>.<br />
              It expires in 1 hour.
            </p>
          </div>
          <Link
            href="/auth/login"
            className="inline-flex items-center gap-1.5 text-sm text-[#1a2332] hover:underline underline-offset-4"
          >
            <ArrowLeft className="h-3.5 w-3.5" />
            Back to sign in
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-gray-50 px-6">
      <div className="w-full max-w-sm space-y-8">
        {/* Back link */}
        <Link
          href="/auth/login"
          className="inline-flex items-center gap-1.5 text-sm text-gray-500 hover:text-[#1a2332] transition"
        >
          <ArrowLeft className="h-3.5 w-3.5" />
          Back to sign in
        </Link>

        {/* Header */}
        <div className="space-y-1">
          <h2 className="text-2xl font-bold text-[#1a2332]">Forgot your password?</h2>
          <p className="text-sm text-gray-500">
            Enter your email and we&apos;ll send you a reset link.
          </p>
        </div>

        {/* Form */}
        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="space-y-1.5">
            <label htmlFor="email" className="text-sm font-medium text-gray-700">
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
              className="h-11 w-full rounded-lg border border-gray-200 bg-white px-3.5 text-sm text-gray-900 placeholder:text-gray-400 transition focus:border-[#1a2332] focus:outline-none focus:ring-2 focus:ring-[#1a2332]/10"
            />
          </div>

          {error && (
            <div className="flex items-start gap-2 rounded-lg bg-red-50 border border-red-100 px-3.5 py-2.5 text-sm text-red-600">
              <span className="mt-0.5 shrink-0">⚠</span>
              {error}
            </div>
          )}

          <button
            type="submit"
            disabled={loading}
            className="flex h-11 w-full items-center justify-center gap-2 rounded-lg bg-[#1a2332] text-sm font-semibold text-white transition hover:bg-[#263347] disabled:opacity-50"
          >
            {loading ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <>
                Send reset link
                <ArrowRight className="h-4 w-4" />
              </>
            )}
          </button>
        </form>
      </div>
    </div>
  );
}
