"use client";

/**
 * Cookie-consent banner.
 *
 * Varuflow only uses strictly-necessary cookies (auth session) and
 * localStorage for UI preferences. Under GDPR/ePrivacy this banner is
 * informational: dismissal is stored so repeat visitors are not nagged.
 *
 * If analytics/tracking cookies are ever added, this banner must be
 * upgraded to a real consent-manager with per-category opt-in before any
 * non-essential script is loaded.
 */
import { useEffect, useState } from "react";
import Link from "next/link";
import { useLocale, useTranslations } from "next-intl";
import { X } from "lucide-react";

const STORAGE_KEY = "varuflow-cookie-ack";

export default function CookieConsent() {
  const t       = useTranslations("cookies");
  const locale  = useLocale();
  const [show, setShow] = useState(false);

  useEffect(() => {
    try {
      if (typeof window !== "undefined" && !localStorage.getItem(STORAGE_KEY)) {
        setShow(true);
      }
    } catch {
      // localStorage blocked (private mode, etc.) — don't render the banner
    }
  }, []);

  function dismiss() {
    try { localStorage.setItem(STORAGE_KEY, "1"); } catch {}
    setShow(false);
  }

  if (!show) return null;

  return (
    <div
      role="dialog"
      aria-live="polite"
      aria-label={t("title")}
      className="fixed bottom-4 left-4 right-4 z-[60] mx-auto max-w-xl rounded-xl border border-white/10 bg-neutral-900/95 p-4 text-sm text-white shadow-2xl backdrop-blur"
    >
      <div className="flex items-start gap-3">
        <div className="flex-1 space-y-2">
          <p className="font-medium">{t("title")}</p>
          <p className="vf-text-m leading-relaxed text-neutral-300">{t("body")}</p>
          <Link
            href={`/${locale}/privacy`}
            className="inline-block text-xs underline decoration-neutral-500 underline-offset-2 hover:text-white"
          >
            {t("learnMore")}
          </Link>
        </div>
        <button
          type="button"
          onClick={dismiss}
          aria-label={t("accept")}
          className="vf-btn vf-btn-primary shrink-0"
        >
          {t("accept")}
        </button>
        <button
          type="button"
          onClick={dismiss}
          aria-label={t("accept")}
          className="shrink-0 rounded-md p-1 text-neutral-400 hover:bg-white/5 hover:text-white"
        >
          <X size={16} />
        </button>
      </div>
    </div>
  );
}
