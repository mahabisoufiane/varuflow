"use client";

import { supabase } from "@/lib/supabase/client";
import { useTranslations } from "next-intl";
import Link from "next/link";
import { useState } from "react";
import { Eye, EyeOff, ArrowRight, Loader2, Mail } from "lucide-react";

function strengthScore(p: string): number {
  let s = 0;
  if (p.length >= 8) s++;
  if (p.length >= 12) s++;
  if (/[A-Z]/.test(p)) s++;
  if (/[0-9]/.test(p)) s++;
  if (/[^A-Za-z0-9]/.test(p)) s++;
  return s;
}

const STRENGTH_LABELS = ["", "Weak", "Fair", "Good", "Strong", "Very strong"];
const STRENGTH_COLORS = ["", "bg-red-400", "bg-orange-400", "bg-yellow-400", "bg-emerald-400", "bg-emerald-500"];

function AuthLeft() {
  return (
    <div className="hidden lg:flex lg:w-1/2 flex-col justify-between bg-[#1a2332] p-12 text-white">
      <div>
        <span className="text-2xl font-bold tracking-tight">Varuflow</span>
      </div>
      <div className="space-y-8">
        <div>
          <h1 className="text-4xl font-bold leading-tight">
            Start managing your wholesale business smarter.
          </h1>
          <p className="mt-4 text-base text-white/60">
            Join Nordic wholesalers who replaced spreadsheets with Varuflow.
          </p>
        </div>
        <ul className="space-y-3">
          {[
            "Free to get started — no credit card required",
            "Inventory, invoicing & POS in one place",
            "Set up in under 10 minutes",
          ].map((item) => (
            <li key={item} className="flex items-start gap-3 text-sm text-white/80">
              <span className="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-white/10 text-xs">
                ✓
              </span>
              {item}
            </li>
          ))}
        </ul>
      </div>
      <p className="text-xs text-white/30">© {new Date().getFullYear()} Varuflow</p>
    </div>
  );
}

export default function SignupPage() {
  const t = useTranslations("auth");

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [sent, setSent] = useState(false);

  const score = strengthScore(password);
  const canSubmit = score >= 3 && email.length > 0;

  async function handleSignup(e: React.FormEvent) {
    e.preventDefault();
    if (!canSubmit) return;
    setLoading(true);
    setError(null);

    const { error } = await supabase.auth.signUp({
      email,
      password,
      options: {
        emailRedirectTo: `${location.origin}/auth/callback?next=/onboarding`,
      },
    });

    setLoading(false);
    if (error) return setError(error.message);
    setSent(true);
  }

  if (sent) {
    return (
      <div className="flex min-h-screen">
        <AuthLeft />
        <div className="flex w-full lg:w-1/2 items-center justify-center px-6 py-16">
          <div className="w-full max-w-sm text-center space-y-6">
            <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-2xl bg-[#1a2332]/8 text-[#1a2332]">
              <Mail className="h-7 w-7" />
            </div>
            <div className="space-y-2">
              <h2 className="text-2xl font-bold text-[#1a2332]">Verify your email</h2>
              <p className="text-sm text-gray-500">
                We sent a confirmation link to{" "}
                <span className="font-medium text-gray-800">{email}</span>.<br />
                Click it to activate your account.
              </p>
            </div>
            <Link href="/auth/login" className="text-sm text-[#1a2332] hover:underline underline-offset-4">
              Back to sign in
            </Link>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="flex min-h-screen">
      <AuthLeft />

      <div className="flex w-full lg:w-1/2 items-center justify-center px-6 py-16">
        <div className="w-full max-w-sm space-y-8">
          {/* Header */}
          <div className="space-y-1">
            <h2 className="text-2xl font-bold text-[#1a2332]">Create your account</h2>
            <p className="text-sm text-gray-500">{t("signUpDescription")}</p>
          </div>

          {/* Form */}
          <form onSubmit={handleSignup} className="space-y-4">
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

            <div className="space-y-1.5">
              <label htmlFor="password" className="text-sm font-medium text-gray-700">
                Password
              </label>
              <div className="relative">
                <input
                  id="password"
                  type={showPassword ? "text" : "password"}
                  required
                  autoComplete="new-password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="Create a strong password"
                  className="h-11 w-full rounded-lg border border-gray-200 bg-white px-3.5 pr-10 text-sm text-gray-900 placeholder:text-gray-400 transition focus:border-[#1a2332] focus:outline-none focus:ring-2 focus:ring-[#1a2332]/10"
                />
                <button
                  type="button"
                  tabIndex={-1}
                  onClick={() => setShowPassword(!showPassword)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600 transition"
                >
                  {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                </button>
              </div>

              {/* Strength bar */}
              {password.length > 0 && (
                <div className="space-y-1.5">
                  <div className="flex gap-1">
                    {[1, 2, 3, 4, 5].map((i) => (
                      <div
                        key={i}
                        className={`h-1 flex-1 rounded-full transition-all ${
                          i <= score ? STRENGTH_COLORS[score] : "bg-gray-200"
                        }`}
                      />
                    ))}
                  </div>
                  <p className={`text-xs font-medium ${
                    score <= 1 ? "text-red-500" :
                    score === 2 ? "text-orange-500" :
                    score === 3 ? "text-yellow-600" :
                    "text-emerald-600"
                  }`}>
                    {STRENGTH_LABELS[score]}
                    {score < 3 && " — add uppercase, numbers, or symbols"}
                  </p>
                </div>
              )}
            </div>

            {error && (
              <div className="flex items-start gap-2 rounded-lg bg-red-50 border border-red-100 px-3.5 py-2.5 text-sm text-red-600">
                <span className="mt-0.5 shrink-0">⚠</span>
                {error}
              </div>
            )}

            <button
              type="submit"
              disabled={loading || !canSubmit}
              className="flex h-11 w-full items-center justify-center gap-2 rounded-lg bg-[#1a2332] text-sm font-semibold text-white transition hover:bg-[#263347] disabled:opacity-40"
            >
              {loading ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <>
                  Create account
                  <ArrowRight className="h-4 w-4" />
                </>
              )}
            </button>
          </form>

          <p className="text-center text-sm text-gray-500">
            Already have an account?{" "}
            <Link href="/auth/login" className="font-medium text-[#1a2332] hover:underline underline-offset-4">
              Sign in
            </Link>
          </p>
        </div>
      </div>
    </div>
  );
}
