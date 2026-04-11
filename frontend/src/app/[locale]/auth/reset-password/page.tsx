"use client";

import { createClient } from "@/lib/supabase/client";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { useTranslations } from "next-intl";
import { Eye, EyeOff, ArrowRight, Loader2, ShieldCheck, Zap } from "lucide-react";
import ThemeToggle from "@/components/ui/ThemeToggle";

function strengthScore(p: string): number {
  let s = 0;
  if (p.length >= 8) s++;
  if (p.length >= 12) s++;
  if (/[A-Z]/.test(p)) s++;
  if (/[0-9]/.test(p)) s++;
  if (/[^A-Za-z0-9]/.test(p)) s++;
  return s;
}
const STRENGTH_COLORS = ["","#EF4444","#F97316","#F59E0B","#10B981","#10B981"];

export default function ResetPasswordPage() {
  const t = useTranslations();
  const supabase = createClient();
  const router = useRouter();

  const [password, setPassword]   = useState("");
  const [confirm, setConfirm]     = useState("");
  const [showPw, setShowPw]       = useState(false);
  const [showCf, setShowCf]       = useState(false);
  const [loading, setLoading]     = useState(false);
  const [error, setError]         = useState<string|null>(null);
  const [ready, setReady]         = useState(false);
  const [done, setDone]           = useState(false);

  useEffect(() => {
    const { data: { subscription } } = supabase.auth.onAuthStateChange((event) => {
      if (event === "PASSWORD_RECOVERY") setReady(true);
    });
    return () => subscription.unsubscribe();
  }, []);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (password !== confirm) return setError(t("errors.passwordMismatch"));
    if (password.length < 8) return setError(t("errors.weakPassword"));
    setLoading(true); setError(null);
    try {
      const { error } = await supabase.auth.updateUser({ password });
      if (error) throw error;
      setDone(true);
      setTimeout(() => router.push("/dashboard"), 2000);
    } catch {
      setError(t("errors.serverError"));
    } finally {
      setLoading(false);
    }
  }

  const score    = strengthScore(password);
  const mismatch = confirm.length > 0 && confirm !== password;

  /* ── Verifying link ────────────────────────────────────────────────────── */
  if (!ready) {
    return (
      <div className="flex min-h-screen items-center justify-center px-6" style={{ background:"var(--vf-bg-primary)" }}>
        <div className="flex items-center gap-3 text-sm" style={{ color:"var(--vf-text-muted)" }}>
          <Loader2 className="h-4 w-4 animate-spin text-[#6366F1]" />
          {t("auth.verifyingLink")}
        </div>
      </div>
    );
  }

  /* ── Success ────────────────────────────────────────────────────────────── */
  if (done) {
    return (
      <div className="flex min-h-screen items-center justify-center px-6 animate-fade-in" style={{ background:"var(--vf-bg-primary)" }}>
        <div className="w-full max-w-sm space-y-5 text-center">
          <div className="mx-auto flex h-16 w-16 items-center justify-center rounded-2xl bg-[#10B981]/15 border border-[#10B981]/25">
            <ShieldCheck className="h-8 w-8 text-[#10B981]" />
          </div>
          <div className="space-y-1">
            <h2 className="text-2xl font-bold" style={{ color:"var(--vf-text-primary)" }}>{t("auth.passwordUpdatedTitle")}</h2>
            <p className="text-sm" style={{ color:"var(--vf-text-secondary)" }}>{t("auth.passwordUpdatedSubtitle")}</p>
          </div>
        </div>
      </div>
    );
  }

  /* ── Form ────────────────────────────────────────────────────────────────── */
  return (
    <div className="flex min-h-screen items-center justify-center px-6" style={{ background:"var(--vf-bg-primary)" }}>
      <div className="absolute top-6 right-6">
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

        <div className="space-y-1">
          <h2 className="text-2xl font-bold" style={{ color:"var(--vf-text-primary)" }}>{t("auth.resetPasswordTitle")}</h2>
          <p className="text-sm" style={{ color:"var(--vf-text-secondary)" }}>{t("auth.resetPasswordSubtitle")}</p>
        </div>

        <form onSubmit={handleSubmit} noValidate className="space-y-4">

          {/* New password */}
          <div className="space-y-1.5">
            <label className="text-xs font-medium" style={{ color:"var(--vf-text-secondary)" }}>{t("auth.newPassword")}</label>
            <div className="relative">
              <input type={showPw?"text":"password"} autoComplete="new-password" value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder={t("auth.newPasswordPlaceholder")} className="vf-input pr-11" />
              <button type="button" tabIndex={-1} onClick={() => setShowPw(!showPw)}
                className="absolute right-3 top-1/2 -translate-y-1/2" style={{ color:"var(--vf-text-muted)" }}>
                {showPw ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
              </button>
            </div>
            {password.length > 0 && (
              <div className="flex gap-1 pt-0.5">
                {[1,2,3,4,5].map((i) => (
                  <div key={i} className="h-1 flex-1 rounded-full transition-all duration-300"
                    style={{ background: i<=score ? STRENGTH_COLORS[score] : "var(--vf-bg-elevated)" }} />
                ))}
              </div>
            )}
          </div>

          {/* Confirm password */}
          <div className="space-y-1.5">
            <label className="text-xs font-medium" style={{ color:"var(--vf-text-secondary)" }}>{t("auth.confirmPassword")}</label>
            <div className="relative">
              <input type={showCf?"text":"password"} autoComplete="new-password" value={confirm}
                onChange={(e) => setConfirm(e.target.value)}
                placeholder={t("auth.confirmPasswordPlaceholder")} className="vf-input pr-11"
                style={{ borderColor:mismatch?"rgba(239,68,68,0.6)":undefined }} />
              <button type="button" tabIndex={-1} onClick={() => setShowCf(!showCf)}
                className="absolute right-3 top-1/2 -translate-y-1/2" style={{ color:"var(--vf-text-muted)" }}>
                {showCf ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
              </button>
            </div>
            {mismatch && <p className="text-xs" style={{ color:"#EF4444" }}>{t("errors.passwordMismatch")}</p>}
          </div>

          {error && (
            <div className="flex items-start gap-2.5 rounded-xl border border-red-500/20 bg-red-500/10 px-3.5 py-3 text-sm text-red-400">
              <svg className="mt-0.5 h-4 w-4 shrink-0" viewBox="0 0 20 20" fill="currentColor">
                <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm-.75-11.25a.75.75 0 011.5 0v4.5a.75.75 0 01-1.5 0v-4.5zm.75 7.5a.875.875 0 100-1.75.875.875 0 000 1.75z" clipRule="evenodd" />
              </svg>
              <span>{error}</span>
            </div>
          )}

          <button type="submit" disabled={loading||mismatch||password.length<8} className="vf-btn w-full">
            {loading
              ? <Loader2 className="h-4 w-4 animate-spin" />
              : <><span>{t("auth.setNewPassword")}</span><ArrowRight className="h-4 w-4" /></>
            }
          </button>
        </form>
      </div>
    </div>
  );
}
