"use client";

import { createClient } from "@/lib/supabase/client";
import { useTranslations } from "next-intl";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useState } from "react";
import { Eye, EyeOff, ArrowRight, Loader2, Mail } from "lucide-react";

type Mode = "magic" | "password";

function AuthLeft() {
  return (
    <div className="hidden lg:flex lg:w-1/2 flex-col justify-between bg-[#1a2332] p-12 text-white">
      <div>
        <span className="text-2xl font-bold tracking-tight">Varuflow</span>
      </div>
      <div className="space-y-8">
        <div>
          <h1 className="text-4xl font-bold leading-tight">
            The smart backoffice for Nordic wholesalers.
          </h1>
          <p className="mt-4 text-base text-white/60">
            Inventory, invoicing, POS, and AI-driven insights — all in one platform.
          </p>
        </div>
        <ul className="space-y-3">
          {[
            "Real-time inventory across all warehouses",
            "Invoicing with Stripe & Fortnox integration",
            "AI advisor that flags risks before they cost you",
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

export default function LoginPage() {
  const t = useTranslations("auth");
  const searchParams = useSearchParams();
  // Supabase client — created inside the component, never at module level
  const supabase = createClient();
  const next = searchParams.get("next") ?? "/dashboard";

  const [mode, setMode] = useState<Mode>("magic");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [magicSent, setMagicSent] = useState(false);

  async function handleMagicLink(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError(null);
    const { error } = await supabase.auth.signInWithOtp({
      email,
      options: { emailRedirectTo: `${location.origin}/auth/callback?next=${next}` },
    });
    setLoading(false);
    if (error) return setError(error.message);
    setMagicSent(true);
  }

  async function handlePassword(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError(null);
    const { error } = await supabase.auth.signInWithPassword({ email, password });
    setLoading(false);
    if (error) return setError(error.message);
    window.location.href = next;
  }

  if (magicSent) {
    return (
      <div className="flex min-h-screen">
        <AuthLeft />
        <div className="flex w-full lg:w-1/2 items-center justify-center px-6 py-16">
          <div className="w-full max-w-sm text-center space-y-6">
            <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-2xl bg-[#1a2332]/8 text-[#1a2332]">
              <Mail className="h-7 w-7" />
            </div>
            <div className="space-y-2">
              <h2 className="text-2xl font-bold text-[#1a2332]">Check your inbox</h2>
              <p className="text-sm text-gray-500">
                We sent a magic link to <span className="font-medium text-gray-800">{email}</span>.<br />
                Click it to sign in — no password needed.
              </p>
            </div>
            <button
              onClick={() => { setMagicSent(false); setEmail(""); }}
              className="text-sm text-[#1a2332] hover:underline underline-offset-4"
            >
              Use a different email
            </button>
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
            <h2 className="text-2xl font-bold text-[#1a2332]">Welcome back</h2>
            <p className="text-sm text-gray-500">{t("loginDescription")}</p>
          </div>

          {/* Mode tabs */}
          <div className="flex rounded-lg bg-gray-100 p-1 text-sm font-medium">
            <button
              type="button"
              onClick={() => { setMode("magic"); setError(null); }}
              className={`flex-1 rounded-md py-1.5 transition-all ${
                mode === "magic"
                  ? "bg-white text-[#1a2332] shadow-sm"
                  : "text-gray-500 hover:text-gray-700"
              }`}
            >
              Magic link
            </button>
            <button
              type="button"
              onClick={() => { setMode("password"); setError(null); }}
              className={`flex-1 rounded-md py-1.5 transition-all ${
                mode === "password"
                  ? "bg-white text-[#1a2332] shadow-sm"
                  : "text-gray-500 hover:text-gray-700"
              }`}
            >
              Password
            </button>
          </div>

          {/* Form */}
          <form
            onSubmit={mode === "magic" ? handleMagicLink : handlePassword}
            className="space-y-4"
          >
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

            {mode === "password" && (
              <div className="space-y-1.5">
                <div className="flex items-center justify-between">
                  <label htmlFor="password" className="text-sm font-medium text-gray-700">
                    Password
                  </label>
                  <Link
                    href="/auth/forgot-password"
                    className="text-xs text-gray-500 hover:text-[#1a2332] transition"
                  >
                    Forgot password?
                  </Link>
                </div>
                <div className="relative">
                  <input
                    id="password"
                    type={showPassword ? "text" : "password"}
                    required
                    autoComplete="current-password"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    placeholder="••••••••"
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
              </div>
            )}

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
                  {mode === "magic" ? "Send magic link" : "Sign in"}
                  <ArrowRight className="h-4 w-4" />
                </>
              )}
            </button>
          </form>

          <p className="text-center text-sm text-gray-500">
            Don&apos;t have an account?{" "}
            <Link href="/auth/signup" className="font-medium text-[#1a2332] hover:underline underline-offset-4">
              Create one free
            </Link>
          </p>
        </div>
      </div>
    </div>
  );
}
