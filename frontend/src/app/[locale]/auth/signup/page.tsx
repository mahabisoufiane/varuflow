"use client";

import { createClient, signInWithGoogle, signInWithMicrosoft } from "@/lib/supabase/client";
import { Link, usePathname, useRouter } from "@/i18n/navigation";
import { useState } from "react";
import { useSearchParams } from "next/navigation";
import { useTranslations, useLocale } from "next-intl";
import { Eye, EyeOff, Loader2, Mail, Zap, Check, X } from "lucide-react";
import ThemeToggle from "@/components/ui/ThemeToggle";

/* ── Locale switcher ─────────────────────────────────────────────────────── */
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

/* ── Strength helpers ────────────────────────────────────────────────────── */
function strengthScore(p: string): 0|1|2|3|4 {
  let s = 0;
  if (p.length >= 8) s++;
  if (/[A-Z]/.test(p)) s++;
  if (/[0-9]/.test(p)) s++;
  if (/[^A-Za-z0-9]/.test(p)) s++;
  return Math.min(s,4) as 0|1|2|3|4;
}
const STRENGTH_COLORS = ["","#EF4444","#F59E0B","#F59E0B","#10B981"];

/* ── Left panel ──────────────────────────────────────────────────────────── */
function AuthLeft() {
  return (
    <div className="hidden lg:flex lg:w-1/2 relative flex-col justify-between overflow-hidden p-12 text-white"
      style={{ background:"linear-gradient(135deg,#0F172A 0%,#1E293B 100%)" }}>
      <div className="pointer-events-none absolute inset-0 overflow-hidden">
        <div className="absolute -top-32 -right-32 h-96 w-96 rounded-full opacity-20 animate-orb-float"
          style={{ background:"radial-gradient(circle,#6366F1 0%,transparent 70%)" }} />
        <div className="absolute bottom-0 left-0 h-80 w-80 rounded-full opacity-15 animate-orb-float"
          style={{ background:"radial-gradient(circle,#4F46E5 0%,transparent 70%)", animationDelay:"4s" }} />
      </div>
      <div className="relative flex items-center gap-3">
        <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-gradient-to-br from-[#6366F1] to-[#4F46E5]">
          <Zap className="h-[18px] w-[18px] text-white" />
        </div>
        <span className="text-xl font-bold tracking-tight">Varuflow</span>
      </div>
      <div className="relative space-y-8">
        <div>
          <h1 className="text-4xl font-bold leading-tight tracking-tight">Start managing your wholesale business smarter.</h1>
          <p className="mt-4 text-base text-white/50">Join Nordic wholesalers who replaced spreadsheets with Varuflow.</p>
        </div>
        <ul className="space-y-3">
          {["Free to get started — no credit card required","Inventory, invoicing & POS in one place","Set up in under 10 minutes"].map((item) => (
            <li key={item} className="flex items-center gap-3 text-sm text-white/70">
              <span className="flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-[#6366F1]/20 border border-[#6366F1]/30 text-[#818CF8] text-xs font-bold">✓</span>
              {item}
            </li>
          ))}
        </ul>
      </div>
      <p className="relative text-xs text-white/25">© {new Date().getFullYear()} Varuflow AB</p>
    </div>
  );
}

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

function MicrosoftIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 18 18" fill="none">
      <rect x="0" y="0" width="8.5" height="8.5" fill="#F25022"/>
      <rect x="9.5" y="0" width="8.5" height="8.5" fill="#7FBA00"/>
      <rect x="0" y="9.5" width="8.5" height="8.5" fill="#00A4EF"/>
      <rect x="9.5" y="9.5" width="8.5" height="8.5" fill="#FFB900"/>
    </svg>
  );
}

function ErrorBanner({ message }: { message: string }) {
  return (
    <div className="flex items-start gap-2.5 rounded-xl border border-red-500/20 bg-red-500/10 px-3.5 py-3 text-sm text-red-400">
      <svg className="mt-0.5 h-4 w-4 shrink-0" viewBox="0 0 20 20" fill="currentColor">
        <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm-.75-11.25a.75.75 0 011.5 0v4.5a.75.75 0 01-1.5 0v-4.5zm.75 7.5a.875.875 0 100-1.75.875.875 0 000 1.75z" clipRule="evenodd" />
      </svg>
      <span>{message}</span>
    </div>
  );
}

function mapSignupError(msg: string, t: ReturnType<typeof useTranslations>): string {
  const m = msg.toLowerCase();
  if (m.includes("already registered")||m.includes("already in use")||m.includes("email taken")) return t("errors.emailTaken");
  if (m.includes("weak password")||m.includes("password should")) return t("errors.weakPassword");
  if (m.includes("network")||m.includes("fetch")||m.includes("failed to fetch")) return t("errors.networkError");
  return t("errors.serverError");
}

/* ── Success state ───────────────────────────────────────────────────────── */
function SuccessState({ email, onResend }: { email: string; onResend: () => void }) {
  const t = useTranslations();
  const domain    = email.split("@")[1]?.toLowerCase() ?? "";
  const isGmail   = domain.includes("gmail");
  const isOutlook = domain.includes("outlook")||domain.includes("hotmail")||domain.includes("live");
  return (
    <div className="flex min-h-screen flex-col items-center justify-center px-6 py-12 animate-fade-in"
      style={{ background:"var(--vf-bg-primary)" }}>
      <div className="w-full max-w-sm space-y-6 rounded-2xl p-8 text-center"
        style={{ background:"var(--vf-glass-bg)", backdropFilter:"blur(12px)", WebkitBackdropFilter:"blur(12px)", border:"1px solid var(--vf-glass-border)" }}>
        <div className="mx-auto flex h-16 w-16 items-center justify-center rounded-2xl bg-[#6366F1]/15 border border-[#6366F1]/20">
          <Mail className="h-8 w-8 text-[#6366F1]" />
        </div>
        <div className="space-y-2">
          <h2 className="text-2xl font-bold" style={{ color:"var(--vf-text-primary)" }}>{t("auth.checkInboxTitle")}</h2>
          <p className="text-sm leading-relaxed" style={{ color:"var(--vf-text-secondary)" }}>
            {t("auth.checkInboxSubtitle").replace("{email}","").trim().split(".")[0]}{" "}
            <span className="font-semibold" style={{ color:"var(--vf-text-primary)" }}>{email}</span>.
          </p>
        </div>
        {(isGmail||isOutlook) && (
          <a href={isGmail?"https://mail.google.com":"https://outlook.live.com"}
            target="_blank" rel="noopener noreferrer" className="vf-btn w-full inline-flex items-center justify-center">
            {isGmail ? t("auth.openGmail") : t("auth.openOutlook")}
          </a>
        )}
        <button type="button" onClick={onResend}
          className="text-sm font-medium text-[#6366F1] hover:text-[#4F46E5] transition-colors">
          {t("auth.resendEmail")}
        </button>
        <div style={{ borderTop:"1px solid var(--vf-border)", paddingTop:"16px" }}>
          <Link href="/auth/login" className="text-sm" style={{ color:"var(--vf-text-muted)" }}>
            {t("auth.backToSignIn")}
          </Link>
        </div>
      </div>
    </div>
  );
}

/* ── Page ────────────────────────────────────────────────────────────────── */
export default function SignupPage() {
  const t = useTranslations();
  const supabase = createClient();
  const searchParams = useSearchParams();
  const plan = searchParams.get("plan") ?? "";

  const [fullName, setFullName]           = useState("");
  const [email, setEmail]                 = useState("");
  const [password, setPassword]           = useState("");
  const [confirm, setConfirm]             = useState("");
  const [showPw, setShowPw]               = useState(false);
  const [showConfirm, setShowConfirm]     = useState(false);
  const [pwFocused, setPwFocused]         = useState(false);
  const [loading, setLoading]             = useState(false);
  const [oauthLoading, setOauthLoading]   = useState<"google"|"microsoft"|null>(null);
  const [error, setError]                 = useState<string|null>(null);
  const [fieldErrors, setFieldErrors]     = useState<Record<string,string>>({});
  const [sent, setSent]                   = useState(false);

  const score        = strengthScore(password);
  const confirmMatch = confirm.length > 0 && confirm === password;
  const confirmBad   = confirm.length > 0 && confirm !== password;
  const canSubmit    = score >= 3 && email.length > 0 && fullName.length > 0 && confirmMatch;

  const strengthLabels = [t("auth.strengthWeak"), t("auth.strengthWeak"), t("auth.strengthFair"), t("auth.strengthGood"), t("auth.strengthStrong")];
  const requirements = [
    { label: t("auth.reqLength"),   met: password.length >= 8 },
    { label: t("auth.reqUppercase"), met: /[A-Z]/.test(password) },
    { label: t("auth.reqNumber"),   met: /[0-9]/.test(password) },
  ];

  function clearField(f: string) { setFieldErrors(p => { const n={...p}; delete n[f]; return n; }); }

  function validate() {
    const e: Record<string,string> = {};
    if (!fullName.trim()) e.fullName = t("errors.validationError");
    if (!email.trim()) e.email = t("errors.validationError");
    else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) e.email = t("errors.validationError");
    if (!password) e.password = t("errors.validationError");
    if (!confirm) e.confirm = t("errors.validationError");
    else if (confirm !== password) e.confirm = t("errors.passwordMismatch");
    setFieldErrors(e);
    return !Object.keys(e).length;
  }

  async function handleSignup(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    if (!validate()) return;
    setLoading(true); setError(null);
    try {
      const { error } = await supabase.auth.signUp({
        email, password,
        options: { data:{ full_name:fullName }, emailRedirectTo:`${location.origin}/en/auth/callback?next=/onboarding${plan ? `%3Fplan%3D${plan}` : ""}` },
      });
      if (error) return setError(mapSignupError(error.message, t));
      setSent(true);
    } catch { setError(t("errors.networkError")); }
    finally { setLoading(false); }
  }

  async function handleResend() { try { await supabase.auth.resend({ type:"signup", email }); } catch {} }

  async function handleGoogle() {
    setOauthLoading("google"); setError(null);
    try { const { error } = await signInWithGoogle(); if (error) { setError(mapSignupError(error.message,t)); setOauthLoading(null); } }
    catch { setError(t("errors.networkError")); setOauthLoading(null); }
  }

  async function handleMicrosoft() {
    setOauthLoading("microsoft"); setError(null);
    try { const { error } = await signInWithMicrosoft(); if (error) { setError(mapSignupError(error.message,t)); setOauthLoading(null); } }
    catch { setError(t("errors.networkError")); setOauthLoading(null); }
  }

  if (sent) return <SuccessState email={email} onResend={handleResend} />;

  return (
    <div className="flex min-h-screen" style={{ background:"var(--vf-bg-primary)" }}>
      <AuthLeft />
      <div className="relative flex w-full lg:w-1/2 flex-col items-center justify-center px-6 py-12 overflow-y-auto">
        <div className="absolute top-6 right-6 flex items-center gap-3">
          <LocaleSwitcher />
          <ThemeToggle />
        </div>

        <div className="w-full max-w-sm space-y-6 rounded-2xl p-8 animate-fade-in"
          style={{ background:"var(--vf-glass-bg)", backdropFilter:"blur(12px)", WebkitBackdropFilter:"blur(12px)", border:"1px solid var(--vf-glass-border)" }}>

          <div className="space-y-1">
            <h2 className="text-2xl font-bold" style={{ color:"var(--vf-text-primary)" }}>{t("auth.createAccount")}</h2>
            <p className="text-sm" style={{ color:"var(--vf-text-secondary)" }}>{t("auth.signUpDescription")}</p>
          </div>

          {/* Social */}
          <div className="space-y-2.5">
            <button type="button" onClick={handleGoogle} disabled={!!oauthLoading||loading}
              className="flex h-11 w-full items-center justify-center gap-3 rounded-xl border border-white/10 bg-white/[0.06] text-sm font-medium transition-all hover:bg-white/[0.10] active:scale-[0.98] disabled:opacity-40 disabled:cursor-not-allowed"
              style={{ color:"var(--vf-text-primary)" }}>
              {oauthLoading==="google" ? <Loader2 className="h-4 w-4 animate-spin" /> : <GoogleIcon />}
              {t("auth.continueWithGoogle")}
            </button>
            <button type="button" onClick={handleMicrosoft} disabled={!!oauthLoading||loading}
              className="flex h-11 w-full items-center justify-center gap-3 rounded-xl border border-white/10 bg-white/[0.06] text-sm font-medium transition-all hover:bg-white/[0.10] active:scale-[0.98] disabled:opacity-40 disabled:cursor-not-allowed"
              style={{ color:"var(--vf-text-primary)" }}>
              {oauthLoading==="microsoft" ? <Loader2 className="h-4 w-4 animate-spin" /> : <MicrosoftIcon />}
              {t("auth.continueWithMicrosoft")}
            </button>
          </div>

          {/* Divider */}
          <div className="flex items-center gap-3">
            <div className="h-px flex-1" style={{ background:"var(--vf-border)" }} />
            <span className="text-[11px] font-semibold tracking-widest" style={{ color:"var(--vf-text-muted)" }}>{t("auth.orDivider")}</span>
            <div className="h-px flex-1" style={{ background:"var(--vf-border)" }} />
          </div>

          {/* Form */}
          <form onSubmit={handleSignup} noValidate className="space-y-4">

            {/* Full name */}
            <div className="space-y-1.5">
              <label className="text-xs font-medium" style={{ color:"var(--vf-text-secondary)" }}>{t("auth.fullName")}</label>
              <input type="text" autoComplete="name" value={fullName}
                onChange={(e) => { setFullName(e.target.value); clearField("fullName"); }}
                placeholder={t("auth.fullNamePlaceholder")} className="vf-input"
                style={{ borderColor:fieldErrors.fullName?"rgba(239,68,68,0.6)":undefined }} />
              {fieldErrors.fullName && <p className="text-xs" style={{ color:"#EF4444" }}>{fieldErrors.fullName}</p>}
            </div>

            {/* Email */}
            <div className="space-y-1.5">
              <label className="text-xs font-medium" style={{ color:"var(--vf-text-secondary)" }}>{t("auth.email")}</label>
              <input type="email" autoComplete="email" value={email}
                onChange={(e) => { setEmail(e.target.value); clearField("email"); }}
                placeholder="you@company.se" className="vf-input"
                style={{ borderColor:fieldErrors.email?"rgba(239,68,68,0.6)":undefined }} />
              {fieldErrors.email && <p className="text-xs" style={{ color:"#EF4444" }}>{fieldErrors.email}</p>}
            </div>

            {/* Password */}
            <div className="space-y-1.5">
              <label className="text-xs font-medium" style={{ color:"var(--vf-text-secondary)" }}>{t("auth.password")}</label>
              <div className="relative">
                <input type={showPw?"text":"password"} autoComplete="new-password" value={password}
                  onChange={(e) => { setPassword(e.target.value); clearField("password"); }}
                  onFocus={() => setPwFocused(true)} onBlur={() => setPwFocused(false)}
                  placeholder={t("auth.newPasswordPlaceholder")} className="vf-input pr-11"
                  style={{ borderColor:fieldErrors.password?"rgba(239,68,68,0.6)":undefined }} />
                <button type="button" tabIndex={-1} onClick={() => setShowPw(!showPw)}
                  className="absolute right-3 top-1/2 -translate-y-1/2" style={{ color:"var(--vf-text-muted)" }}>
                  {showPw ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                </button>
              </div>
              {password.length > 0 && (
                <div className="space-y-1.5">
                  <div className="flex gap-1">
                    {[1,2,3,4].map((i) => (
                      <div key={i} className="h-1 flex-1 rounded-full transition-all duration-300"
                        style={{ background: i<=score ? STRENGTH_COLORS[score] : "var(--vf-bg-elevated)" }} />
                    ))}
                  </div>
                  {score > 0 && (
                    <p className="text-xs font-medium" style={{ color:STRENGTH_COLORS[score] }}>{strengthLabels[score]}</p>
                  )}
                </div>
              )}
              {(pwFocused || password.length > 0) && (
                <ul className="space-y-1 pt-1">
                  {requirements.map((req) => (
                    <li key={req.label} className="flex items-center gap-2 text-xs">
                      <span className="flex h-4 w-4 shrink-0 items-center justify-center rounded-full transition-all duration-200"
                        style={{ background:req.met?"rgba(16,185,129,0.15)":"var(--vf-bg-elevated)", border:`1px solid ${req.met?"rgba(16,185,129,0.3)":"var(--vf-border)"}` }}>
                        <Check className="h-2.5 w-2.5" style={{ color:req.met?"#10B981":"var(--vf-text-muted)" }} />
                      </span>
                      <span style={{ color:req.met?"#10B981":"var(--vf-text-muted)" }}>{req.label}</span>
                    </li>
                  ))}
                </ul>
              )}
            </div>

            {/* Confirm password */}
            <div className="space-y-1.5">
              <label className="text-xs font-medium" style={{ color:"var(--vf-text-secondary)" }}>{t("auth.confirmPassword")}</label>
              <div className="relative">
                <input type={showConfirm?"text":"password"} autoComplete="new-password" value={confirm}
                  onChange={(e) => { setConfirm(e.target.value); clearField("confirm"); }}
                  placeholder={t("auth.confirmPasswordPlaceholder")} className="vf-input pr-20"
                  style={{ borderColor:confirmMatch?"rgba(16,185,129,0.5)":confirmBad?"rgba(239,68,68,0.5)":fieldErrors.confirm?"rgba(239,68,68,0.6)":undefined }} />
                {confirm.length > 0 && (
                  <span className="absolute right-10 top-1/2 -translate-y-1/2">
                    {confirmMatch ? <Check className="h-4 w-4 text-[#10B981]" /> : <X className="h-4 w-4 text-[#EF4444]" />}
                  </span>
                )}
                <button type="button" tabIndex={-1} onClick={() => setShowConfirm(!showConfirm)}
                  className="absolute right-3 top-1/2 -translate-y-1/2" style={{ color:"var(--vf-text-muted)" }}>
                  {showConfirm ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                </button>
              </div>
              {fieldErrors.confirm && <p className="text-xs" style={{ color:"#EF4444" }}>{fieldErrors.confirm}</p>}
            </div>

            {error && <ErrorBanner message={error} />}

            <button type="submit" disabled={loading||!canSubmit||!!oauthLoading} className="vf-btn w-full">
              {loading ? <><Loader2 className="h-4 w-4 animate-spin" /> {t("common.loading")}</> : t("auth.createAccount")}
            </button>
          </form>

          <p className="text-center text-sm" style={{ color:"var(--vf-text-muted)" }}>
            {t("auth.hasAccount")}{" "}
            <Link href="/auth/login" className="font-semibold text-[#6366F1] hover:text-[#4F46E5] transition-colors">
              {t("auth.login")}
            </Link>
          </p>
        </div>
      </div>
    </div>
  );
}
