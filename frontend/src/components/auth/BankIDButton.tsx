"use client";

/**
 * BankID sign-in flow — opens a BankID order, polls /collect every 1s,
 * refreshes the animated QR code, and redirects on success.
 *
 * Flow:
 *   POST /api/local-auth/bankid/init         → { order_ref, auto_start_token, qr_data }
 *   GET  /api/local-auth/bankid/collect      → { status, qr_data?, access_token?, refresh_token? }
 *
 * On "complete" we persist the Varuflow tokens in localStorage (the
 * same bucket used by the password login path) and push the user to
 * the locale-prefixed dashboard. On "failed" we show the translated
 * error and reset the dialog so the user can retry.
 */
import { useEffect, useRef, useState } from "react";
import { useTranslations, useLocale } from "next-intl";
import { Loader2, X } from "lucide-react";
import { QRCodeSVG } from "qrcode.react";
import { toast } from "sonner";

import { api } from "@/lib/api-client";
import { useRouter } from "@/i18n/navigation";

type InitResp = {
  order_ref: string;
  auto_start_token: string;
  qr_data: string;
};
type CollectResp = {
  status: "pending" | "complete" | "failed";
  hint_code?: string | null;
  qr_data?: string | null;
  access_token?: string | null;
  refresh_token?: string | null;
};

function isMobileUA(): boolean {
  if (typeof navigator === "undefined") return false;
  return /Android|iPhone|iPad|iPod/i.test(navigator.userAgent);
}

export default function BankIDButton({ disabled }: { disabled?: boolean }) {
  const t = useTranslations("auth");
  const locale = useLocale();
  const router = useRouter();

  const [open, setOpen] = useState(false);
  const [starting, setStarting] = useState(false);
  const [orderRef, setOrderRef] = useState<string | null>(null);
  const [autoStartToken, setAutoStartToken] = useState<string | null>(null);
  const [qrData, setQrData] = useState<string | null>(null);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  function stopPolling() {
    if (pollRef.current) {
      clearInterval(pollRef.current);
      pollRef.current = null;
    }
  }

  async function begin() {
    setStarting(true);
    try {
      const init = await api.post<InitResp>("/api/local-auth/bankid/init", {});
      setOrderRef(init.order_ref);
      setAutoStartToken(init.auto_start_token);
      setQrData(init.qr_data);
      setOpen(true);

      // On mobile, auto-launch the BankID app on the same device via
      // the documented deep link. Desktop users scan the QR instead.
      if (isMobileUA()) {
        const returnUrl = encodeURIComponent(window.location.href);
        window.location.href =
          `bankid:///?autostarttoken=${init.auto_start_token}&redirect=${returnUrl}`;
      }

      // Poll every 1 s — BankID's server supports 2 s so we're well
      // within rate limits, and the animated QR expects ≤ 1 s cadence.
      pollRef.current = setInterval(() => pollOnce(init.order_ref), 1000);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : t("bankid_failed"));
    } finally {
      setStarting(false);
    }
  }

  async function pollOnce(ref: string) {
    try {
      const res = await api.get<CollectResp>(
        `/api/local-auth/bankid/collect?orderRef=${encodeURIComponent(ref)}`,
      );
      if (res.status === "pending") {
        if (res.qr_data) setQrData(res.qr_data);
        return;
      }
      stopPolling();
      if (res.status === "complete" && res.access_token && res.refresh_token) {
        // Same storage bucket used by the /login path
        localStorage.setItem("varuflow_access_token", res.access_token);
        localStorage.setItem("varuflow_refresh_token", res.refresh_token);
        setOpen(false);
        router.push(`/${locale}/dashboard`);
        return;
      }
      // failed
      toast.error(t("bankid_failed"));
      setOpen(false);
    } catch {
      // Network blips during polling shouldn't nuke the flow — keep
      // the timer alive. Real hard failures (order expired, etc.)
      // surface as `status: "failed"` above.
    }
  }

  function cancel() {
    stopPolling();
    setOpen(false);
    setOrderRef(null);
    setQrData(null);
  }

  useEffect(() => stopPolling, []);

  return (
    <>
      <button
        type="button"
        onClick={begin}
        disabled={disabled || starting}
        className="flex h-11 w-full items-center justify-center gap-3 rounded-xl border border-white/10 bg-white/[0.06] text-sm font-medium transition-all hover:bg-white/[0.10] active:scale-[0.98] disabled:opacity-40 disabled:cursor-not-allowed"
        style={{ color: "var(--vf-text-primary)" }}
      >
        {starting ? (
          <Loader2 className="h-4 w-4 animate-spin" />
        ) : (
          <span className="inline-flex h-4 w-4 items-center justify-center rounded bg-[#193E8F] text-[10px] font-bold text-white">
            B
          </span>
        )}
        {starting ? t("bankid_starting") : t("bankid_login")}
      </button>

      {open && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm"
          role="dialog"
          aria-modal="true"
        >
          <div
            className="relative w-full max-w-sm rounded-2xl p-6 text-center"
            style={{ background: "var(--vf-bg-elevated)", border: "1px solid var(--vf-border)" }}
          >
            <button
              onClick={cancel}
              className="absolute right-3 top-3 rounded-full p-1 opacity-60 hover:opacity-100"
              aria-label="Close"
            >
              <X size={18} />
            </button>
            <h3 className="text-lg font-semibold mb-4">{t("bankid_login")}</h3>
            <p className="text-sm mb-4" style={{ color: "var(--vf-text-muted)" }}>
              {t("bankid_scanning")}
            </p>
            <div className="mx-auto flex items-center justify-center rounded-xl bg-white p-4">
              {qrData ? (
                <QRCodeSVG value={qrData} size={220} level="M" />
              ) : (
                <Loader2 className="animate-spin text-black/50" />
              )}
            </div>
            {autoStartToken && (
              <a
                href={`bankid:///?autostarttoken=${autoStartToken}&redirect=null`}
                className="mt-4 inline-block text-sm font-medium text-[#193E8F] hover:underline"
              >
                {t("bankid_open_on_device")}
              </a>
            )}
            {/* orderRef is exposed for debugging — harmless because
                the ref expires in 5 min and is useless without mTLS. */}
            {orderRef && (
              <p className="mt-3 text-[10px] opacity-40 break-all">{orderRef}</p>
            )}
          </div>
        </div>
      )}
    </>
  );
}
