"use client";
// File: src/components/app/CountryPicker.tsx
// Purpose: user-visible picker for the active country. Persists selection
// in localStorage via setCountryOverride() and reloads the page so server
// components re-render with the new NEXT_PUBLIC_DEFAULT_COUNTRY context.

import { useEffect, useState } from "react";
import { resolveCountryCode, setCountryOverride } from "@/lib/country";

type Option = { code: string; name: string };

export function CountryPicker({ apiBase }: { apiBase: string }) {
  const [options, setOptions] = useState<Option[]>([]);
  const [current, setCurrent] = useState<string>("");

  useEffect(() => {
    setCurrent(resolveCountryCode(
      typeof window !== "undefined" ? window.location.host : null,
    ));
    const controller = new AbortController();
    fetch(`${apiBase}/api/countries`, { signal: controller.signal })
      .then((r) => (r.ok ? r.json() : null))
      .then((j) => {
        if (j?.countries) setOptions(j.countries);
      })
      .catch(() => {
        /* silent — falls back to just the current country */
      });
    return () => controller.abort();
  }, [apiBase]);

  if (!options.length) return null;

  return (
    <select
      aria-label="Country"
      value={current}
      onChange={(e) => {
        setCountryOverride(e.target.value);
        if (typeof window !== "undefined") window.location.reload();
      }}
      className="rounded-md border border-neutral-300 bg-white px-2 py-1 text-sm"
    >
      {options.map((o) => (
        <option key={o.code} value={o.code}>
          {o.code} — {o.name}
        </option>
      ))}
    </select>
  );
}
