"use client";

import { createClient } from "@/lib/supabase/client";
import { Link, usePathname, useRouter } from "@/i18n/navigation";
import { useState } from "react";
import { useTranslations, useLocale } from "next-intl";
import { ArrowLeft, ArrowRight, Loader2, Mail, Zap } from "lucide-react";
import ThemeToggle from "@/components/ui/ThemeToggle";

function LocaleSwitcher() {
  const pathname = usePathname();
  const router   = useRouter();
  const locale   = useLocale();
  return (
    <div className="flex items-center gap-1 rounded-lg border p-0.5" style={{ borderColor:"var(--vf-border)" }}>
      {(["sv","en"] as const).map((l) => (
        <button key={l} onClick={() => router.replace(pathname,{locale:l})}
          className="rounded-md px-2.5 py-1 text-xs font-semibold transition-all duration-150"
          style={{ background:locale===l?"var(--vf-bg-elevated)":"transparent", color:locale===l?"var(--vf-text-primary)":"var(--vf-text-muted)" }}>
          {l.toUpperCase()}
        </button>
      ))}
    </div>
  );
}

export default function ForgotPasswordPage() {
  const t = useTranslations();
  const supabase = createClient();
  const [email, setEmail]     = useState("");
  const [loading, setLoading] = useState(false);
  const [sent, setSent]       = useState(false);
  const [error, setError]     = useState<string|null>(null);

  async function handleSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setLoading(true); setError(null);
    try {
      const { error } = await supabase.auth.resetPasswordForEmail(email, {
        redirectTo: `${location.origin}/en/auth/reset-password`,
      });
      if (error) throw error;
      setSent(true);
    } catch {
      setError(t("errors.networkError"));
    } finally {
      setLoading(false);
    }
  }

  if (sent) {
    return (
      <div className="flex min-h-screen items-center justify-center px-6 animate-fade-in"
        style={{ background:"var(--vf-bg-primary)" }}>
        <div className="absolute top-6 right-6 flex items-center gap-3">
          <LocaleSwitcher />
          <ThemeToggle />
        </div>
        <div className="w-full max-w-sm space-y-6 text-center">
          <div className="mx-auto flex h-16 w-16 items-center justify-center rounded-2xl bg-[#6366F1]/15 border border-[#6366F1]/20">
            <Mail className="h-8 w-8 text-[#6366F1]" />
          </div>
          <div className="space-y-2">
            <h2 className="text-2xl font-bold" style={{ color:"var(--vf-text-primary)" }}>
              {t("auth.resetLinkSentTitle")}
            </h2>
            <p className="text-sm leading-relaxed" style={{ color:"var(--vf-text-secondary)" }}>
              {t("auth.resetLinkSentSubtitle").split("{email}")[0]}
              <span className="font-semibold" style={{ color:"var(--vf-text-primary)" }}>{email}</span>
              {t("auth.resetLinkSentSubtitle").split("{email}")[1]}
            </p>
          </div>
          <Link href="/auth/login"
            className="inline-flex items-center gap-1.5 text-sm font-medium text-[#6366F1] hover:text-[#4F46E5] transition-colors">
            <ArrowLeft className="h-3.5 w-3.5" />
            {t("auth.backToSignIn")}
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className="flex min-h-screen items-center justify-center px-6"
      style={{ background:"var(--vf-bg-primary)" }}>
      <div className="absolute top-6 right-6 flex items-center gap-3">
        <LocaleSwitcher />
        <ThemeToggle />
      </div>

      <div className="w-full max-w-sm space-y-8 animate-fade-in">
        {/* Logo */}
        <div className="flex items-center gap-2.5">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-gradient-to-br from-[#6366F1] to-[#4F46E5]">
            <Zap className="h-4 w-4 text-white" />
          </div>
          <span className="text-base font-bold tracking-tight" style={{ color:"var(--vf-text-primary)" }}>Varuflow</span>
        </div>

        <Link href="/auth/login"
          className="inline-flex items-center gap-1.5 text-sm transition-colors"
          style={{ color:"var(--vf-text-muted)" }}>
          <ArrowLeft className="h-3.5 w-3.5" />
          {t("auth.backToSignIn")}
        </Link>

        <div className="space-y-1">
          <h2 className="text-2xl font-bold" style={{ color:"var(--vf-text-primary)" }}>
            {t("auth.forgotPasswordTitle")}
          </h2>
          <p className="text-sm" style={{ color:"var(--vf-text-secondary)" }}>
            {t("auth.forgotPasswordSubtitle")}
          </p>
        </div>

        <form onSubmit={handleSubmit} noValidate className="space-y-4">
          <div className="space-y-1.5">
            <label className="text-xs font-medium" style={{ color:"var(--vf-text-secondary)" }}>
              {t("auth.email")}
            </label>
            <input type="email" autoComplete="email" value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="you@company.se" className="vf-input" />
          </div>

          {error && (
            <div className="flex items-start gap-2.5 rounded-xl border border-red-500/20 bg-red-500/10 px-3.5 py-3 text-sm text-red-400">
              <svg className="mt-0.5 h-4 w-4 shrink-0" viewBox="0 0 20 20" fill="currentColor">
                <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm-.75-11.25a.75.75 0 011.5 0v4.5a.75.75 0 01-1.5 0v-4.5zm.75 7.5a.875.875 0 100-1.75.875.875 0 000 1.75z" clipRule="evenodd" />
              </svg>
              <span>{error}</span>
            </div>
          )}

          <button type="submit" disabled={loading||!email.trim()} className="vf-btn w-full">
            {loading
              ? <Loader2 className="h-4 w-4 animate-spin" />
              : <><span>{t("auth.sendResetLink")}</span><ArrowRight className="h-4 w-4" /></>
            }
          </button>
        </form>
      </div>
    </div>
  );
}
