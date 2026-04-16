// File: src/lib/country.ts
// Purpose: single source of truth for the resolved country code on the client.
// Used by: <CountryPicker>, invoicing formatting, locale routing.

export type CountryInfo = {
  code: string;          // ISO-3166 alpha-2 (e.g. "SE")
  name: string;
  region: "europe" | "middle-east" | "americas";
  currency: string;      // ISO-4217 (e.g. "SEK")
};

const DEFAULT: CountryInfo = {
  code: (process.env.NEXT_PUBLIC_DEFAULT_COUNTRY ?? "SE").toUpperCase(),
  name: "Sweden",
  region: "europe",
  currency: (process.env.NEXT_PUBLIC_DEFAULT_CURRENCY ?? "SEK").toUpperCase(),
};

/** Reads country from URL subdomain, localStorage override, or falls back
 *  to the build-time env var. Safe in both server and client code. */
export function resolveCountryCode(host?: string | null): string {
  if (host) {
    const label = host.split(".")[0]?.toUpperCase();
    if (label && label.length === 2) return label;
  }
  if (typeof window !== "undefined") {
    const override = window.localStorage.getItem("varuflow.country");
    if (override && override.length === 2) return override.toUpperCase();
  }
  return DEFAULT.code;
}

/** Persists a user-chosen country. Only valid alpha-2 codes are stored. */
export function setCountryOverride(code: string): void {
  if (typeof window === "undefined") return;
  if (!/^[A-Za-z]{2}$/.test(code)) return;
  window.localStorage.setItem("varuflow.country", code.toUpperCase());
}

/** Fetch the full config from the backend. Cached per page via the HTTP
 *  cache — backend response is public, immutable per deploy. */
export async function fetchCountryConfig(
  apiBase: string,
  code: string,
  signal?: AbortSignal,
): Promise<Record<string, unknown> | null> {
  const res = await fetch(`${apiBase}/api/countries/${encodeURIComponent(code)}`, {
    signal,
    headers: { Accept: "application/json" },
    cache: "force-cache",
  });
  if (!res.ok) return null;
  return res.json();
}
