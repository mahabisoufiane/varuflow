"use client";

// File: src/components/OfflineIndicator.tsx
// Purpose: Shows a small pill at the top of the viewport when the
// browser reports it is offline, plus a badge with the count of
// queued mutations waiting to replay. Also nudges the service worker
// to drain the queue on the `online` event (covers Safari / Firefox
// where Background Sync is unavailable).

import { useEffect, useState } from "react";
import { useTranslations } from "next-intl";
import { pendingCount } from "@/lib/offline-db";

export default function OfflineIndicator() {
  const t = useTranslations("pwa.offline");
  const [offline, setOffline] = useState(false);
  const [queued, setQueued] = useState(0);

  useEffect(() => {
    if (typeof navigator === "undefined") return;

    setOffline(!navigator.onLine);
    pendingCount().then(setQueued);

    const onOffline = () => setOffline(true);
    const onOnline = () => {
      setOffline(false);
      // Ask the SW to drain even on browsers without Background Sync.
      if ("serviceWorker" in navigator) {
        navigator.serviceWorker.controller?.postMessage({ type: "drain-mutations" });
      }
      // Refresh the queued counter after a short delay so the drain has time to run.
      setTimeout(() => pendingCount().then(setQueued), 1500);
    };

    window.addEventListener("offline", onOffline);
    window.addEventListener("online", onOnline);
    const poll = setInterval(() => pendingCount().then(setQueued), 5000);

    return () => {
      window.removeEventListener("offline", onOffline);
      window.removeEventListener("online", onOnline);
      clearInterval(poll);
    };
  }, []);

  if (!offline && queued === 0) return null;

  return (
    <div
      role="status"
      aria-live="polite"
      className="fixed left-1/2 top-3 z-50 -translate-x-1/2 rounded-full border border-amber-300 bg-amber-50 px-4 py-2 text-xs font-medium text-amber-900 shadow-sm"
    >
      {offline ? t("banner") : t("syncing", { count: queued })}
    </div>
  );
}
