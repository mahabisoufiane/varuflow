"use client";

// File: src/components/MobileQuickActions.tsx
// Purpose: Floating action button + bottom-sheet host, mounted globally
// on the authenticated app layout. Mobile-only (md:hidden + viewport check),
// hidden on /pos, /onboarding/*, /auth/*. Shows a red-dot badge when the
// offline queue has pending mutations (Item 38).

import { useCallback, useEffect, useRef, useState } from "react";
import { usePathname } from "next/navigation";
import { useTranslations } from "next-intl";
import { Plus } from "lucide-react";
import QuickActionSheet from "@/components/QuickActionSheet";
import { isFabHidden } from "@/lib/quick-actions";
import { pendingCount } from "@/lib/offline-db";

export default function MobileQuickActions() {
  const t = useTranslations();
  const pathname = usePathname() ?? "/";
  const [open, setOpen] = useState(false);
  const [pending, setPending] = useState(0);
  const sheetRef = useRef<HTMLDivElement>(null);
  const fabRef = useRef<HTMLButtonElement>(null);

  // Offline-queue badge — poll every 5s (matches OfflineIndicator pattern).
  useEffect(() => {
    let cancelled = false;
    async function refresh() {
      try {
        const n = await pendingCount();
        if (!cancelled) setPending(n);
      } catch { /* queue not initialised yet */ }
    }
    refresh();
    const id = setInterval(refresh, 5000);
    const onSync = () => refresh();
    if (typeof window !== "undefined") {
      window.addEventListener("offline-sync-complete", onSync);
    }
    return () => {
      cancelled = true;
      clearInterval(id);
      if (typeof window !== "undefined") {
        window.removeEventListener("offline-sync-complete", onSync);
      }
    };
  }, []);

  // Close on Escape; trap focus while open.
  useEffect(() => {
    if (!open) return;
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") {
        e.preventDefault();
        setOpen(false);
      }
    }
    document.addEventListener("keydown", onKey);
    // Scroll-lock the body while the sheet is open.
    const prev = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.removeEventListener("keydown", onKey);
      document.body.style.overflow = prev;
    };
  }, [open]);

  // Return focus to the FAB when the sheet closes.
  useEffect(() => {
    if (!open) fabRef.current?.focus({ preventScroll: true });
  }, [open]);

  // Swipe-down-to-close on the sheet handle area.
  const dragState = useRef<{ startY: number; currentY: number } | null>(null);
  const onTouchStart = useCallback((e: React.TouchEvent) => {
    dragState.current = { startY: e.touches[0].clientY, currentY: e.touches[0].clientY };
  }, []);
  const onTouchMove = useCallback((e: React.TouchEvent) => {
    if (!dragState.current) return;
    dragState.current.currentY = e.touches[0].clientY;
    const dy = dragState.current.currentY - dragState.current.startY;
    if (sheetRef.current && dy > 0) {
      sheetRef.current.style.transform = `translateY(${dy}px)`;
    }
  }, []);
  const onTouchEnd = useCallback(() => {
    if (!dragState.current) return;
    const dy = dragState.current.currentY - dragState.current.startY;
    dragState.current = null;
    if (sheetRef.current) sheetRef.current.style.transform = "";
    if (dy > 80) setOpen(false);
  }, []);

  if (isFabHidden(pathname)) return null;

  return (
    <>
      {/* FAB — md:hidden keeps it off desktops even if rendered. */}
      <button
        ref={fabRef}
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-label={t("quickActions.sheet_title")}
        aria-expanded={open}
        aria-controls="mobile-quick-actions-sheet"
        data-testid="mobile-fab"
        className="fixed right-6 z-50 flex h-14 w-14 items-center justify-center rounded-full text-white shadow-lg transition-transform md:hidden"
        style={{
          backgroundColor: "#2d6a4f",
          // Sit 16 px above the bottom nav (Item 12) plus the iPhone
          // home-bar inset. `--bottom-nav-height` is published by
          // `useBottomNavHeight` and defaults to 64 px if unset.
          bottom: "calc(var(--bottom-nav-height, 64px) + 16px)",
        }}
      >
        <Plus
          className="h-6 w-6 transition-transform duration-200"
          style={{ transform: open ? "rotate(45deg)" : "rotate(0deg)" }}
        />
        {pending > 0 && (
          <span
            aria-label={t("quickActions.pending_sync_badge")}
            data-testid="mobile-fab-badge"
            className="absolute -right-1 -top-1 flex min-h-[20px] min-w-[20px] items-center justify-center rounded-full bg-red-500 px-1 text-[11px] font-semibold text-white"
          >
            {pending > 9 ? "9+" : pending}
          </span>
        )}
      </button>

      {/* Backdrop + sheet */}
      {open && (
        <>
          <div
            onClick={() => setOpen(false)}
            data-testid="mobile-fab-backdrop"
            className="fixed inset-0 z-40 bg-black/40 md:hidden"
            aria-hidden="true"
          />
          <div
            ref={sheetRef}
            id="mobile-quick-actions-sheet"
            role="dialog"
            aria-modal="true"
            aria-labelledby="qa-title"
            data-testid="mobile-fab-sheet"
            className="fixed inset-x-0 bottom-0 z-50 max-h-[85vh] animate-[slideUp_300ms_ease-out] overflow-hidden rounded-t-2xl bg-white shadow-2xl md:hidden"
          >
            {/* Handle bar — swipe-down-to-close target */}
            <div
              onTouchStart={onTouchStart}
              onTouchMove={onTouchMove}
              onTouchEnd={onTouchEnd}
              data-testid="mobile-fab-handle"
              className="flex cursor-grab justify-center py-3"
            >
              <span className="h-1 w-8 rounded-full bg-gray-300" />
            </div>
            <div className="max-h-[75vh] overflow-y-auto">
              <QuickActionSheet onClose={() => setOpen(false)} />
            </div>
          </div>
          <style jsx global>{`
            @keyframes slideUp {
              from { transform: translateY(100%); }
              to   { transform: translateY(0);    }
            }
          `}</style>
        </>
      )}
    </>
  );
}
