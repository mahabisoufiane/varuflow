"use client";

// "Book a demo" CTA that opens the demo form in a modal instead of
// navigating. The /demo page stays as the direct/SEO entry point.
import { useCallback, useEffect, useState } from "react";
import { X } from "lucide-react";
import { useTranslations } from "next-intl";
import { DemoForm } from "./DemoForm";

export function BookDemoButton({
  label,
  className = "",
}: {
  label: string;
  className?: string;
}) {
  const t = useTranslations("demo");
  const [open, setOpen] = useState(false);

  const onKey = useCallback((e: KeyboardEvent) => {
    if (e.key === "Escape") setOpen(false);
  }, []);
  useEffect(() => {
    if (!open) return;
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [open, onKey]);

  return (
    <>
      <button type="button" onClick={() => setOpen(true)} className={className}>
        {label}
      </button>
      {open && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-ink/60 p-4"
          onClick={() => setOpen(false)}
        >
          <div
            role="dialog"
            aria-modal="true"
            aria-label={t("title")}
            className="max-h-[90dvh] w-full max-w-lg overflow-y-auto rounded-card border border-line bg-paper p-6 sm:p-8"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="mb-6 flex items-start justify-between gap-4">
              <div>
                <h2 className="font-display text-title font-bold text-ink">{t("title")}</h2>
                <p className="mt-1 text-small text-mist">{t("sub")}</p>
              </div>
              <button type="button" onClick={() => setOpen(false)} aria-label="Close" className="text-mist hover:text-ink">
                <X className="h-5 w-5" />
              </button>
            </div>
            <DemoForm />
          </div>
        </div>
      )}
    </>
  );
}
