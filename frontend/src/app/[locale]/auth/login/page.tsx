// File: src/app/[locale]/auth/login/page.tsx
// Purpose: Login page — split-screen, glass card form, Google/Microsoft OAuth, password auth
// Used by: Unauthenticated users redirected here by middleware

"use client";

import { createClient, signInWithGoogle, signInWithMicrosoft } from "@/lib/supabase/client";
// Use next-intl Link so locale is injected automatically — never bare next/link
import { Link } from "@/i18n/navigation";
import { useSearchParams } from "next/navigation";
import { useState } from "react";
import { useTranslations } from "next-intl";
import { Eye, EyeOff, Loader2, Zap } from "lucide-react";
import ThemeToggle from "@/components/ui/ThemeToggle";

/* ── Left brand panel ───────────────────────────────────────────────────────── */
function AuthLeft() {
  return (
    <div
      className="hidden lg:flex lg:w-1/2 relative flex-col justify-between overflow-hidden p-12 text-white"
      style={{ background: "linear-gradient(135deg, #0F172A 0%, #1E293B 100%)" }}
    >
      {/* Animated gradient orbs */}
      <div className="pointer-events-none absolute inset-0 overflow-hidden">
        <div
          className="absolute -top-32 -left-32 h-96 w-96 rounded-full opacity-20 animate-orb-float"
          style={{ background: "radial-gradient(circle, #6366F1 0%, transparent 70%)" }}
        />
        <div
          className="absolute top-1/2 -right-24 h-80 w-80 rounded-full opacity-15 animate-orb-float"
          style={{ background: "radial-gradient(circle, #4F46E5 0%, transparent 70%)", animationDelay: "3s" }}
        />
        <div
          className="absolute -bottom-24 left-1/3 h-64 w-64 rounded-full opacity-10 animate-orb-float"
          style={{ background: "radial-gradient(circle, #818CF8 0%, transparent 70%)", animationDelay: "6s" }}
        />
      </div>

      {/* Logo */}
      <div className="relative flex items-center gap-3">
        <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-gradient-to-br from-[#6366F1] to-[#4F46E5] shadow-glow">
          <Zap className="h-[18px] w-[18px] text-white" />
        </div>
        <span className="text-xl font-bold tracking-tight">Varuflow</span>
      </div>

      {/* Headline */}
      <div className="relative space-y-8">
        <div>
          <h1 className="text-4xl font-bold leading-tight tracking-tight">
            The smart backoffice<br />for Nordic wholesalers.
          </h1>
          <p className="mt-4 text-base text-white/50">
            Inventory, invoicing, POS, and AI-driven insights — all in one platform.
          </p>
        </div>
        <ul className="space-y-3">
          {[
            "Real-time inventory across all warehouses",
            "Invoicing with Stripe & Fortnox integration",
            "AI advisor that flags risks before they cost you",
          ].map((item) => (
            <li key={item} className="flex items-center gap-3 text-sm text-white/70">
              <span className="flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-[#6366F1]/20 border border-[#6366F1]/30 text-[#818CF8] text-xs font-bold">
                ✓
              </span>
              {item}
            </li>
          ))}
        </ul>
      </div>

      <p className="relative text-xs text-white/25">© {new Date().getFullYear()} Varuflow AB</p>
    </div>
  );
}

/* ── Google SVG icon ────────────────────────────────────────────────────────── */
function GoogleIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 18 18" fill="none">
      <path d="M17.64 9.205c0-.639-.057-1.252-.164-1.841H9v3.481h4.844a4.14 4.14 0 0 1-1.796 2.716v2.259h2.908c1.702-1.567 2.684-3.875 2.684-6.615Z" fill="#4285F4"/>
      <path d="M9 18c2.43 0 4.467-.806 5.956-2.18l-2.908-2.259c-.806.54-1.837.86-3.048.86-2.344 0-4.328-1.584-5.036-3.711H.957v2.332A8.997 8.997 0 0 0 9 18Z" fill="#34A853"/>
      <path d="M3.964 10.71A5.41 5.41 0 0 1 3.682 9c0-.593.102-1.17.282-1.71V4.958H.957A8.996 8.996 0 0 0 0 9c0 1.452.348 2.827.957 4.042l3.007-2.332Z" fill="#FBBC05"/>
      <path d="M9 3.58c1.321 0 2.508.454 3.44 1.345l2.582-2.58C13.463.891 11.426 0 9 0A8.997 8.997 0 0 0 .957 4.958L3.964 7.29C4.672 5.163 6.656 3.58 9 3.58Z" fill="#EA4335"/>
    </svg>
  );
}

/* ── Microsoft SVG icon ─────────────────────────────────────────────────────── */
function MicrosoftIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 18 18" fill="none">
      <rect x="0"   y="0"   width="8.5" height="8.5" fill="#F25022"/>
      <rect x="9.5" y="0"   width="8.5" height="8.5" fill="#7FBA00"/>
      <rect x="0"   y="9.5" width="8.5" height="8.5" fill="#00A4EF"/>
      <rect x="9.5" y="9.5" width="8.5" height="8.5" fill="#FFB900"/>
    </svg>
  );
}

// Guard against open-redirect attacks — only allow relative paths from ?next=
function safeNext(raw: string | null): string {
  if (!raw) return "/dashboard";
  // Reject anything that starts with // or contains :// (absolute URL)
  if (raw.startsWith("//") || raw.includes("://")) return "/dashboard";
  // Must start with / to be a valid relative path
  return raw.startsWith("/") ? raw : "/dashboard";
}

// Map Supabase error messages to i18n translation keys
function mapAuthError(msg: string, t: ReturnType<typeof useTranslations>): string {
  const lower = msg.toLowerCase();
  if (lower.includes("invalid login") || lower.includes("invalid credentials") || lower.includes("wrong password")) {
    return t("errors.invalidCredentials");
  }
  if (lower.includes("email not confirmed")) return t("errors.emailNotConfirmed");
  if (lower.includes("too many") || lower.includes("rate limit"))  return t("errors.accountLocked");
  if (lower.includes("network") || lower.includes("fetch"))        return t("errors.networkError");
  return t("errors.serverError");
}

/* ── Page ───────────────────────────────────────────────────────────────────── */
export default function LoginPage() {
  const searchParams = useSearchParams();
  const t = useTranslations();
  // createClient() must be called inside the component body — never at module level
  const supabase = createClient();
  const next = safeNext(searchParams.get("next"));

  const [email, setEmail]               = useState("");
  const [password, setPassword]         = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [loading, setLoading]           = useState(false);
  const [oauthLoading, setOauthLoading] = useState<"google" | "microsoft" | null>(null);
  const [error, setError]               = useState<string | null>(null);

  async function handlePassword(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setLoading(true);
    setError(null);
    const { error } = await supabase.auth.signInWithPassword({ email, password });
    setLoading(false);
    if (error) return setError(mapAuthError(error.message, t));
    window.location.href = next;
  }

  async function handleGoogle() {
    setOauthLoading("google");
    setError(null);
    const { error } = await signInWithGoogle();
    if (error) { setError(mapAuthError(error.message, t)); setOauthLoading(null); }
  }

  async function handleMicrosoft() {
    setOauthLoading("microsoft");
    setError(null);
    const { error } = await signInWithMicrosoft();
    if (error) { setError(mapAuthError(error.message, t)); setOauthLoading(null); }
  }

  return (
    <div className="flex min-h-screen" style={{ background: "var(--vf-bg-primary)" }}>
      <AuthLeft />

      {/* Right panel */}
      <div className="relative flex w-full lg:w-1/2 flex-col items-center justify-center px-6 py-12">

        {/* Theme toggle */}
        <div className="absolute top-6 right-6">
          <ThemeToggle />
        </div>

        {/* Glass card */}
        <div
          className="w-full max-w-sm space-y-6 rounded-2xl p-8 animate-fade-in"
          style={{
            background: "var(--vf-glass-bg)",
            backdropFilter: "blur(12px)",
            WebkitBackdropFilter: "blur(12px)",
            border: "1px solid var(--vf-glass-border)",
          }}
        >
          {/* Header */}
          <div className="space-y-1">
            <h2 className="text-2xl font-bold" style={{ color: "var(--vf-text-primary)" }}>
              Welcome back
            </h2>
            <p className="text-sm" style={{ color: "var(--vf-text-secondary)" }}>
              Sign in to your account
            </p>
          </div>

          {/* Social buttons */}
          <div className="space-y-3">
            <button
              type="button"
              onClick={handleGoogle}
              disabled={!!oauthLoading || loading}
              className="flex h-11 w-full items-center justify-center gap-3 rounded-xl border border-gray-200 bg-white text-sm font-medium text-gray-700 shadow-sm transition-all duration-200 hover:scale-[1.01] hover:shadow-md active:scale-[0.98] disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {oauthLoading === "google"
                ? <Loader2 className="h-4 w-4 animate-spin text-gray-400" />
                : <GoogleIcon />
              }
              Continue with Google
            </button>

            <button
              type="button"
              onClick={handleMicrosoft}
              disabled={!!oauthLoading || loading}
              className="flex h-11 w-full items-center justify-center gap-3 rounded-xl border border-gray-200 bg-white text-sm font-medium text-gray-700 shadow-sm transition-all duration-200 hover:scale-[1.01] hover:shadow-md active:scale-[0.98] disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {oauthLoading === "microsoft"
                ? <Loader2 className="h-4 w-4 animate-spin text-gray-400" />
                : <MicrosoftIcon />
              }
              Continue with Microsoft
            </button>
          </div>

          {/* Divider */}
          <div className="flex items-center gap-3">
            <div className="h-px flex-1" style={{ background: "var(--vf-border)" }} />
            <span className="text-xs font-medium" style={{ color: "var(--vf-text-muted)" }}>OR</span>
            <div className="h-px flex-1" style={{ background: "var(--vf-border)" }} />
          </div>

          {/* Form */}
          <form onSubmit={handlePassword} className="space-y-4">
            {/* Email */}
            <div className="space-y-1.5">
              <label className="text-xs font-medium" style={{ color: "var(--vf-text-secondary)" }}>
                Email address
              </label>
              <input
                type="email"
                required
                autoComplete="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="you@company.se"
                className="vf-input"
              />
            </div>

            {/* Password */}
            <div className="space-y-1.5">
              <div className="flex items-center justify-between">
                <label className="text-xs font-medium" style={{ color: "var(--vf-text-secondary)" }}>
                  Password
                </label>
                <Link
                  href="/auth/forgot-password"
                  className="text-xs font-semibold text-[#6366F1] hover:text-[#4F46E5] transition-colors"
                >
                  Forgot password?
                </Link>
              </div>
              <div className="relative">
                <input
                  type={showPassword ? "text" : "password"}
                  required
                  autoComplete="current-password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="••••••••"
                  className="vf-input pr-11"
                />
                <button
                  type="button"
                  tabIndex={-1}
                  onClick={() => setShowPassword(!showPassword)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 transition-colors hover:text-[var(--vf-text-secondary)]"
                  style={{ color: "var(--vf-text-muted)" }}
                >
                  {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                </button>
              </div>
            </div>

            {/* Error */}
            {error && (
              <div className="flex items-start gap-2 rounded-xl border border-red-500/20 bg-red-500/10 px-3.5 py-2.5 text-sm text-red-400">
                <span className="mt-0.5 shrink-0">⚠</span>
                {error}
              </div>
            )}

            {/* Submit */}
            <button
              type="submit"
              disabled={loading || !!oauthLoading}
              className="vf-btn w-full"
            >
              {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : "Sign in"}
            </button>
          </form>

          {/* Footer link */}
          <p className="text-center text-sm" style={{ color: "var(--vf-text-muted)" }}>
            Don&apos;t have an account?{" "}
            <Link
              href="/auth/signup"
              className="font-semibold text-[#6366F1] hover:text-[#4F46E5] transition-colors"
            >
              Sign up
            </Link>
          </p>
        </div>
      </div>
    </div>
  );
}
