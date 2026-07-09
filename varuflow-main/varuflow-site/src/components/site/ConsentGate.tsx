"use client";

// GDPR consent banner. The ONLY localStorage use on the site (AGENTS.md).
// Analytics never load before explicit consent.
import { useEffect, useState } from "react";
import { useTranslations } from "next-intl";

const CONSENT_KEY = "varuflow-consent";

function loadAnalytics() {
  // TODO: replace with the real privacy-friendly analytics loader
  // (e.g. self-hosted Plausible/Umami script tag) once chosen.
  console.info("[analytics] placeholder loader — consent granted");
}

export function ConsentGate() {
  const t = useTranslations("consent");
  const [choice, setChoice] = useState<"granted" | "denied" | "pending" | null>(null);

  useEffect(() => {
    const stored = localStorage.getItem(CONSENT_KEY);
    if (stored === "granted") {
      setChoice("granted");
      loadAnalytics();
    } else if (stored === "denied") {
      setChoice("denied");
    } else {
      setChoice("pending");
    }
  }, []);

  const decide = (value: "granted" | "denied") => {
    localStorage.setItem(CONSENT_KEY, value);
    setChoice(value);
    if (value === "granted") loadAnalytics();
  };

  if (choice !== "pending") return null;

  return (
    <div
      role="region"
      aria-label="Cookie consent"
      className="fixed inset-x-0 bottom-0 z-50 border-t border-line bg-paper p-4 shadow-lg"
    >
      <div className="mx-auto flex max-w-6xl flex-col items-start gap-3 sm:flex-row sm:items-center sm:justify-between">
        <p className="text-small text-ink-soft">{t("text")}</p>
        <div className="flex shrink-0 gap-2">
          <button
            type="button"
            onClick={() => decide("denied")}
            className="rounded-full border border-line px-4 py-2 text-small font-semibold text-ink-soft hover:border-ink"
          >
            {t("decline")}
          </button>
          <button
            type="button"
            onClick={() => decide("granted")}
            className="rounded-full bg-brand px-4 py-2 text-small font-semibold text-white hover:bg-brand-strong"
          >
            {t("accept")}
          </button>
        </div>
      </div>
    </div>
  );
}
