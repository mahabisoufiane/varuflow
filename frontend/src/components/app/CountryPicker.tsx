"use client";
// Compact country picker styled to match the Varuflow app shell.
// Pulls the country list from /api/countries (served by the backend's
// country service). Falls back silently if the backend hasn't deployed
// the new endpoint yet.

import { useEffect, useState } from "react";
import { Globe } from "lucide-react";
import { api } from "@/lib/api-client";
import { resolveCountryCode, setCountryOverride } from "@/lib/country";

type Option = { code: string; name: string };

export default function CountryPicker() {
  const [options, setOptions] = useState<Option[]>([]);
  const [current, setCurrent] = useState<string>("");

  useEffect(() => {
    setCurrent(
      resolveCountryCode(
        typeof window !== "undefined" ? window.location.host : null,
      ),
    );
    api
      .get<{ countries: Option[] }>("/api/countries")
      .then((j) => {
        if (j?.countries?.length) setOptions(j.countries);
      })
      .catch(() => {
        /* silent — old backend without /api/countries */
      });
  }, []);

  if (!options.length) return null;

  return (
    <label className="relative inline-flex items-center gap-1.5 rounded-xl px-2.5 h-9 text-xs vf-text-m vf-btn-ghost cursor-pointer">
      <Globe className="h-3.5 w-3.5" />
      <span className="font-semibold tracking-wide tabular-nums">
        {current || "—"}
      </span>
      <select
        aria-label="Country"
        value={current}
        onChange={(e) => {
          setCountryOverride(e.target.value);
          if (typeof window !== "undefined") window.location.reload();
        }}
        className="absolute inset-0 opacity-0 cursor-pointer"
      >
        {options.map((o) => (
          <option key={o.code} value={o.code}>
            {o.code} — {o.name}
          </option>
        ))}
      </select>
    </label>
  );
}
