"use client";

/**
 * Settings → Security (Item 23).
 *
 * Renders:
 *   • Enforcement banner — "your org requires MFA" when the backend says so.
 *   • TOTP setup flow: /api/auth/mfa/enable → show provisioning URI +
 *     <QRCodeSVG> → enter 6-digit code → /api/auth/mfa/confirm.
 *   • TOTP disable flow (requires current password + TOTP code).
 *
 * All mutations go through the existing /api/auth/mfa/* endpoints —
 * we don't mirror them in a new route so the audit surface stays in
 * one place (see backend/app/routers/local_auth.py).
 */
import { api } from "@/lib/api-client";
import { useEffect, useState } from "react";
import { toast } from "sonner";
import { QRCodeSVG } from "qrcode.react";
import { useTranslations } from "next-intl";
import { useParams, useRouter } from "next/navigation";
import { Shield, ShieldCheck, ShieldAlert, ArrowLeft } from "lucide-react";

interface SecurityStatus {
  role: "OWNER" | "ADMIN" | "MEMBER";
  plan: "FREE" | "PRO" | "ENTERPRISE";
  member_count: number;
  mfa_enabled: boolean;
  mfa_required: boolean;
  mfa_enforced_at: string | null;
  member_threshold: number;
}

export default function SecuritySettingsPage() {
  const t = useTranslations("settings.security");
  const router = useRouter();
  const params = useParams<{ locale: string }>();
  const locale = params?.locale ?? "en";

  const [status, setStatus]   = useState<SecurityStatus | null>(null);
  const [loading, setLoading] = useState(true);

  // Setup flow state
  const [provisioningUri, setProvisioningUri] = useState<string | null>(null);
  const [totpCode, setTotpCode]               = useState("");
  const [busy, setBusy]                       = useState(false);

  // Disable flow state
  const [disablePw, setDisablePw]             = useState("");
  const [disableCode, setDisableCode]         = useState("");

  async function loadStatus() {
    try {
      const s = await api.get<SecurityStatus>("/api/settings/security/status");
      setStatus(s);
    } catch {
      // Non-owner / unauthenticated — render nothing rather than an error;
      // the route-level 404/403 will already redirect on sensitive routes.
      setStatus(null);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { loadStatus(); }, []);

  async function handleEnable() {
    setBusy(true);
    try {
      const res = await api.post<{ provisioning_uri: string }>("/api/auth/mfa/enable", {});
      setProvisioningUri(res.provisioning_uri);
    } catch (e) {
      toast.error(t("enable_failed"));
    } finally { setBusy(false); }
  }

  async function handleConfirm() {
    if (!/^\d{6}$/.test(totpCode)) { toast.error(t("invalid_code")); return; }
    setBusy(true);
    try {
      await api.post("/api/auth/mfa/confirm", { totp_code: totpCode });
      toast.success(t("enabled"));
      setProvisioningUri(null);
      setTotpCode("");
      await loadStatus();
    } catch (e) {
      toast.error(t("confirm_failed"));
    } finally { setBusy(false); }
  }

  async function handleDisable() {
    if (!disablePw || !/^\d{6}$/.test(disableCode)) { toast.error(t("disable_need_both")); return; }
    setBusy(true);
    try {
      await api.post("/api/auth/mfa/disable", { password: disablePw, totp_code: disableCode });
      toast.success(t("disabled"));
      setDisablePw(""); setDisableCode("");
      await loadStatus();
    } catch (e) {
      toast.error(t("disable_failed"));
    } finally { setBusy(false); }
  }

  if (loading) {
    return (
      <div className="max-w-2xl space-y-4">
        <div className="h-8 w-48 skeleton rounded" />
        <div className="h-48 skeleton rounded-xl" />
      </div>
    );
  }

  if (!status) {
    return (
      <div className="max-w-2xl space-y-4">
        <h1 className="text-xl font-bold vf-text-1">{t("title")}</h1>
        <p className="text-sm vf-text-m">{t("unavailable")}</p>
      </div>
    );
  }

  const { mfa_enabled, mfa_required, plan, member_count, member_threshold } = status;

  return (
    <div className="max-w-2xl space-y-6">
      <button
        onClick={() => router.push(`/${locale}/settings`)}
        className="inline-flex items-center gap-1.5 text-xs vf-text-m hover:vf-text-2"
      >
        <ArrowLeft className="h-3.5 w-3.5" /> {t("back")}
      </button>

      <div>
        <h1 className="text-xl font-bold vf-text-1 flex items-center gap-2">
          <Shield className="h-5 w-5" /> {t("title")}
        </h1>
        <p className="text-xs vf-text-m mt-0.5">{t("subtitle")}</p>
      </div>

      {/* Enforcement banner ─────────────────────────────────────────── */}
      {mfa_required && !mfa_enabled && (
        <div className="vf-section p-4 flex items-start gap-3 rounded-[14px] border-red-500/40">
          <ShieldAlert className="h-5 w-5 text-red-500 shrink-0 mt-0.5" />
          <div className="space-y-1">
            <p className="text-sm font-medium vf-text-1">{t("required_title")}</p>
            <p className="text-xs vf-text-m">
              {plan === "FREE"
                ? t("required_reason_team", { count: member_count, threshold: member_threshold })
                : t("required_reason_plan", { plan })}
            </p>
            <p className="text-xs vf-text-m">{t("required_consequence")}</p>
          </div>
        </div>
      )}

      {/* Status panel ───────────────────────────────────────────────── */}
      <div className="vf-section p-5 space-y-3" >
        <div className="flex items-center gap-2">
          {mfa_enabled
            ? <ShieldCheck className="h-5 w-5 text-emerald-500" />
            : <Shield className="h-5 w-5 vf-text-m" />}
          <span className="text-sm font-medium vf-text-1">
            {mfa_enabled ? t("status_enabled") : t("status_disabled")}
          </span>
        </div>
        {mfa_enabled && status.mfa_enforced_at && (
          <p className="text-xs vf-text-m">
            {t("enforced_since", { date: new Date(status.mfa_enforced_at).toLocaleDateString(locale) })}
          </p>
        )}
        {!mfa_enabled && !mfa_required && (
          <p className="text-xs vf-text-m">{t("recommended_optional")}</p>
        )}
      </div>

      {/* Setup flow ─────────────────────────────────────────────────── */}
      {!mfa_enabled && (
        <div className="vf-section p-5 space-y-4" >
          <h2 className="text-sm font-semibold vf-text-1">{t("setup_title")}</h2>
          {!provisioningUri ? (
            <>
              <p className="text-xs vf-text-m">{t("setup_intro")}</p>
              <button onClick={handleEnable} disabled={busy} className="vf-btn-primary text-sm">
                {busy ? t("working") : t("start_setup")}
              </button>
            </>
          ) : (
            <>
              <p className="text-xs vf-text-m">{t("scan_qr")}</p>
              <div className="bg-white p-3 inline-block rounded">
                <QRCodeSVG value={provisioningUri} size={180} />
              </div>
              <details className="text-xs vf-text-m">
                <summary className="cursor-pointer">{t("cant_scan")}</summary>
                <code className="block mt-2 p-2 bg-black/5 rounded break-all text-[11px]">{provisioningUri}</code>
              </details>
              <div className="space-y-2">
                <label className="text-xs font-medium vf-text-m">{t("enter_code")}</label>
                <input
                  value={totpCode}
                  onChange={e => setTotpCode(e.target.value.replace(/\D/g, "").slice(0, 6))}
                  inputMode="numeric" autoComplete="one-time-code"
                  className="vf-input w-36 font-mono tracking-widest" placeholder="123456"
                />
              </div>
              <button onClick={handleConfirm} disabled={busy || totpCode.length !== 6}
                      className="vf-btn-primary text-sm">
                {busy ? t("working") : t("confirm_enable")}
              </button>
            </>
          )}
        </div>
      )}

      {/* Disable flow ───────────────────────────────────────────────── */}
      {mfa_enabled && (
        <div className="vf-section p-5 space-y-4" >
          <h2 className="text-sm font-semibold vf-text-1">{t("disable_title")}</h2>
          {mfa_required
            ? <p className="text-xs text-red-500">{t("disable_blocked")}</p>
            : <>
                <p className="text-xs vf-text-m">{t("disable_intro")}</p>
                <div className="space-y-2">
                  <label className="text-xs font-medium vf-text-m">{t("password")}</label>
                  <input type="password" value={disablePw} onChange={e => setDisablePw(e.target.value)}
                         className="vf-input" autoComplete="current-password" />
                </div>
                <div className="space-y-2">
                  <label className="text-xs font-medium vf-text-m">{t("enter_code")}</label>
                  <input value={disableCode}
                         onChange={e => setDisableCode(e.target.value.replace(/\D/g, "").slice(0, 6))}
                         inputMode="numeric" autoComplete="one-time-code"
                         className="vf-input w-36 font-mono tracking-widest" placeholder="123456" />
                </div>
                <button onClick={handleDisable} disabled={busy || !disablePw || disableCode.length !== 6}
                        className="vf-btn-secondary text-sm">
                  {busy ? t("working") : t("disable")}
                </button>
              </>}
        </div>
      )}

      {/* IP Allowlist link (Enterprise + owner only) ─────────────────── */}
      {status.role === "OWNER" && status.plan === "ENTERPRISE" && (
        <button
          onClick={() => router.push(`/${locale}/settings/security/ip-allowlist`)}
          className="vf-section p-5 w-full text-left flex items-center gap-3 hover:bg-white/5 transition"
          
        >
          <Shield className="h-5 w-5 vf-text-1" />
          <div className="flex-1">
            <div className="text-sm font-semibold vf-text-1">{t("ip_allowlist_card_title")}</div>
            <div className="text-xs vf-text-m">{t("ip_allowlist_card_subtitle")}</div>
          </div>
          <span className="text-xs vf-text-m">→</span>
        </button>
      )}
    </div>
  );
}
