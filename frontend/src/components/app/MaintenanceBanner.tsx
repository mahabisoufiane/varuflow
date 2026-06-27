"use client";

// File: src/components/app/MaintenanceBanner.tsx
// Purpose: Shows a sticky banner whenever the backend enters READONLY_MODE.
// Listens for the "varuflow:readonly" custom event dispatched by the
// api-client on any 503 response. Auto-hides after 5 minutes of silence
// (covers the standard Retry-After window).

import { useEffect, useState } from "react";
import { useTranslations } from "next-intl";

export function MaintenanceBanner() {
  const t = useTranslations("maintenance");
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    let hideTimer: ReturnType<typeof setTimeout> | null = null;

    const onReadonly = () => {
      setVisible(true);
      if (hideTimer) clearTimeout(hideTimer);
      // Auto-hide after 5 minutes — user can trigger it again if still down
      hideTimer = setTimeout(() => setVisible(false), 5 * 60 * 1000);
    };

    window.addEventListener("varuflow:readonly", onReadonly as EventListener);
    return () => {
      window.removeEventListener("varuflow:readonly", onReadonly as EventListener);
      if (hideTimer) clearTimeout(hideTimer);
    };
  }, []);

  if (!visible) return null;

  return (
    <div
      role="status"
      aria-live="polite"
      className="sticky top-0 z-50 w-full bg-amber-500 px-4 py-2 text-center text-sm font-medium text-amber-950 shadow"
    >
      {t("banner")}
      <button
        type="button"
        onClick={() => setVisible(false)}
        aria-label={t("dismiss")}
        className="ml-3 underline opacity-80 hover:opacity-100"
      >
        {t("dismiss")}
      </button>
    </div>
  );
}
