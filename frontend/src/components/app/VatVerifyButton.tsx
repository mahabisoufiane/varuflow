"use client";

import { useState } from "react";
import { api } from "@/lib/api-client";
import { CheckCircle2, XCircle, Loader2, ShieldCheck } from "lucide-react";

type VatResult = {
  valid: boolean;
  name?: string | null;
  address?: string | null;
  source: string;
  vat_registered?: boolean;
};

/**
 * Verifies an EU VAT number (via VIES) or a Norwegian organisation number
 * (via BRREG). Picks the right upstream automatically based on the
 * country-code prefix in the VAT number or the explicit `country` prop.
 */
export function VatVerifyButton({
  vatNumber,
  country,
}: {
  vatNumber: string;
  country?: string;
}) {
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<VatResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function verify() {
    if (!vatNumber) return;
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const trimmed = vatNumber.trim().toUpperCase();
      const cc = (country || trimmed.slice(0, 2)).toUpperCase();

      if (cc === "NO") {
        let num = trimmed.startsWith("NO") ? trimmed.slice(2) : trimmed;
        if (num.endsWith("MVA")) num = num.slice(0, -3);
        const res = await api.get<VatResult>(
          `/api/vat/check-no?org_number=${encodeURIComponent(num)}`
        );
        setResult(res);
      } else {
        const num = trimmed.startsWith(cc) ? trimmed.slice(2) : trimmed;
        const res = await api.get<VatResult>(
          `/api/vat/check?country=${encodeURIComponent(cc)}&vat_number=${encodeURIComponent(num)}`
        );
        setResult(res);
      }
    } catch (e: unknown) {
      setError((e as Error).message ?? "Lookup failed");
    } finally {
      setLoading(false);
    }
  }

  const isValid =
    result?.valid && (result?.source !== "BRREG" || result?.vat_registered !== false);
  const source = result?.source ?? "";

  return (
    <div className="flex flex-col gap-1.5">
      <button
        type="button"
        onClick={verify}
        disabled={loading || !vatNumber}
        className="flex items-center gap-1.5 rounded-lg px-2.5 py-1 text-xs font-medium vf-btn-ghost disabled:opacity-40"
      >
        {loading ? (
          <Loader2 className="h-3.5 w-3.5 animate-spin" />
        ) : (
          <ShieldCheck className="h-3.5 w-3.5" />
        )}
        {loading ? `Checking ${source || "registry"}…` : "Verify company"}
      </button>

      {result && (
        <div
          className="flex items-start gap-1.5 rounded-lg px-2.5 py-1.5 text-[11px]"
          style={{
            background: isValid ? "rgba(34,197,94,0.08)" : "rgba(239,68,68,0.08)",
            border: `1px solid ${isValid ? "rgba(34,197,94,0.2)" : "rgba(239,68,68,0.2)"}`,
            color: isValid ? "rgb(74,222,128)" : "rgb(248,113,113)",
          }}
        >
          {isValid ? (
            <CheckCircle2 className="h-3.5 w-3.5 mt-0.5 shrink-0" />
          ) : (
            <XCircle className="h-3.5 w-3.5 mt-0.5 shrink-0" />
          )}
          <div className="min-w-0">
            {isValid ? (
              <>
                <div className="font-semibold truncate">
                  {result.name || "Registered"}{" "}
                  <span className="opacity-60">· {result.source}</span>
                </div>
                {result.address && result.address !== "---" && (
                  <div className="opacity-80 truncate">{result.address}</div>
                )}
                {result.source === "BRREG" && result.vat_registered === false && (
                  <div className="opacity-80">Exists but not MVA-registered.</div>
                )}
              </>
            ) : (
              <div>
                {result.source === "BRREG"
                  ? "Not found in BRREG"
                  : "Not registered in VIES"}
              </div>
            )}
          </div>
        </div>
      )}

      {error && (
        <div className="text-[11px] text-red-400">Registry unreachable — try again.</div>
      )}
    </div>
  );
}
