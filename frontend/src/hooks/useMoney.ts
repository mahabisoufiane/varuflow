"use client";
// Country-aware money, number, date, and VAT helpers.
// Single source of truth — everywhere in the app should import from here
// instead of hardcoding "sv-SE" or "kr"/"SEK".
//
// Data flow:
//   1. resolveCountryCode() → "SE" | "DE" | "FR" | ... (from subdomain,
//      localStorage override, or NEXT_PUBLIC_DEFAULT_COUNTRY)
//   2. fetchCountryConfig() → reads /api/countries/{code} once per tab,
//      caches in module state.
//   3. useMoney() exposes { fmt, symbol, code, vatRates, locale } tied to
//      the resolved country.

import { useEffect, useState } from "react";
import { api } from "@/lib/api-client";
import { resolveCountryCode } from "@/lib/country";

export interface CountryConfig {
  iso_alpha2:    string;
  display_name:  string;
  default_locale: string;
  currency:      string;
  vat: {
    standard_rate_pct: number;
    reduced_rates_pct: number[];
    reverse_charge_b2b?: boolean;
    tax_id_regex?:   string;
    einvoicing_status?: string;
  };
  invoice?: {
    due_days_default?: number;
    sequence_format?:  string;
  };
}

const _cache = new Map<string, CountryConfig>();
const _inflight = new Map<string, Promise<CountryConfig | null>>();

function loadConfig(code: string): Promise<CountryConfig | null> {
  const key = code.toUpperCase();
  if (_cache.has(key)) return Promise.resolve(_cache.get(key)!);
  if (_inflight.has(key)) return _inflight.get(key)!;
  const p = api
    .get<CountryConfig>(`/api/countries/${encodeURIComponent(key)}`)
    .then((c) => {
      _cache.set(key, c);
      return c;
    })
    .catch(() => null)
    .finally(() => {
      _inflight.delete(key);
    });
  _inflight.set(key, p);
  return p;
}

export interface MoneyTools {
  /** Format a numeric amount with the country's currency symbol. */
  fmt: (n: number, opts?: { decimals?: number; withCode?: boolean }) => string;
  /** ISO-4217 code, e.g. "SEK", "EUR". */
  code: string;
  /** BCP-47 locale tag, e.g. "sv-SE", "de-DE". */
  locale: string;
  /** Country ISO alpha-2. */
  country: string;
  /** Full country config once loaded (null while fetching or if unavailable). */
  config: CountryConfig | null;
  /** VAT rates available in the country: [standard, ...reduced, 0]. */
  vatRates: number[];
  /** Format a date using the country's default locale. */
  fmtDate: (d: Date | string | number, style?: "short" | "medium" | "long") => string;
}

const FALLBACK_CURRENCY: Record<string, string> = {
  SE: "SEK", NO: "NOK", DK: "DKK", IS: "ISK", GB: "GBP", CH: "CHF",
  PL: "PLN", CZ: "CZK", HU: "HUF", RO: "RON", BG: "BGN", HR: "HRK",
  RS: "RSD", TR: "TRY", AE: "AED", SA: "SAR", IL: "ILS", US: "USD",
  CA: "CAD", MX: "MXN", BR: "BRL", AR: "ARS",
};

function fallbackCurrency(country: string): string {
  return FALLBACK_CURRENCY[country] ?? "EUR";
}

function inferLocale(country: string, currency: string): string {
  // Rough mapping — Intl falls back sensibly if the exact tag is unknown.
  const byCountry: Record<string, string> = {
    SE: "sv-SE", NO: "nb-NO", DK: "da-DK", FI: "fi-FI", IS: "is-IS",
    DE: "de-DE", AT: "de-AT", CH: "de-CH", FR: "fr-FR", BE: "fr-BE",
    ES: "es-ES", IT: "it-IT", PT: "pt-PT", NL: "nl-NL", LU: "fr-LU",
    PL: "pl-PL", CZ: "cs-CZ", SK: "sk-SK", HU: "hu-HU", RO: "ro-RO",
    BG: "bg-BG", GR: "el-GR", HR: "hr-HR", SI: "sl-SI", EE: "et-EE",
    LV: "lv-LV", LT: "lt-LT", IE: "en-IE", GB: "en-GB", MT: "en-MT",
    CY: "el-CY",
    AE: "ar-AE", SA: "ar-SA", IL: "he-IL", TR: "tr-TR",
    US: "en-US", CA: "en-CA", MX: "es-MX", BR: "pt-BR", AR: "es-AR",
  };
  return byCountry[country] ?? `en-${country}`;
}

export function useMoney(): MoneyTools {
  const [country] = useState<string>(() =>
    resolveCountryCode(typeof window !== "undefined" ? window.location.host : null),
  );
  const [config, setConfig] = useState<CountryConfig | null>(_cache.get(country) ?? null);

  useEffect(() => {
    if (_cache.has(country)) {
      setConfig(_cache.get(country)!);
      return;
    }
    let cancelled = false;
    loadConfig(country).then((c) => {
      if (!cancelled) setConfig(c);
    });
    return () => {
      cancelled = true;
    };
  }, [country]);

  const code   = config?.currency       ?? fallbackCurrency(country);
  const locale = config?.default_locale ?? inferLocale(country, code);

  const fmt: MoneyTools["fmt"] = (n, opts) => {
    const decimals = opts?.decimals ?? 0;
    try {
      const s = new Intl.NumberFormat(locale, {
        style: "currency",
        currency: code,
        minimumFractionDigits: decimals,
        maximumFractionDigits: decimals,
      }).format(Number.isFinite(n) ? n : 0);
      if (opts?.withCode) return `${s} (${code})`;
      return s;
    } catch {
      // Unknown currency code → plain number + ISO tail
      const plain = new Intl.NumberFormat(locale, {
        minimumFractionDigits: decimals,
        maximumFractionDigits: decimals,
      }).format(Number.isFinite(n) ? n : 0);
      return `${plain} ${code}`;
    }
  };

  const fmtDate: MoneyTools["fmtDate"] = (d, style = "medium") => {
    try {
      const date = typeof d === "string" || typeof d === "number" ? new Date(d) : d;
      return new Intl.DateTimeFormat(locale, { dateStyle: style }).format(date);
    } catch {
      return String(d);
    }
  };

  const vatRates: number[] = (() => {
    if (!config) return [25, 12, 6, 0]; // SE defaults while loading
    const set = new Set<number>([config.vat.standard_rate_pct, ...config.vat.reduced_rates_pct, 0]);
    return Array.from(set).sort((a, b) => b - a);
  })();

  return { fmt, code, locale, country, config, vatRates, fmtDate };
}
