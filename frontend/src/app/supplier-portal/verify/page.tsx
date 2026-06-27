"use client";

// Verify a supplier-portal magic link (Item 37).
//
// The operator emails the supplier a URL of the form
//   {PORTAL_BASE_URL}/supplier-portal/verify?token=<raw>
// Our backend dependency ``get_portal_supplier`` validates the raw
// token on every API call, so there's no JWT exchange step — we
// simply stash the raw token under ``SUPPLIER_PORTAL_TOKEN_KEY`` and
// bounce to the PO list.

import { Suspense, useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import {
  SUPPLIER_PORTAL_TOKEN_KEY,
  SUPPLIER_PORTAL_ME_KEY,
  supplierPortalApi,
} from "@/lib/supplier-portal-client";

interface MeResponse {
  supplier_id: string;
  supplier_name: string;
  org_id: string;
  token_expires_at: string;
}

function VerifyInner() {
  const params = useSearchParams();
  const router = useRouter();
  const [status, setStatus] = useState<"verifying" | "error">("verifying");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const token = params.get("token");
    if (!token) {
      setStatus("error");
      setError("Missing token.");
      return;
    }

    // Stash the raw token before calling /me so the Authorization
    // header is attached automatically by supplierPortalApi.
    try {
      localStorage.setItem(SUPPLIER_PORTAL_TOKEN_KEY, token);
    } catch {
      setStatus("error");
      setError("Could not save session. Enable local storage and try again.");
      return;
    }

    supplierPortalApi
      .get<MeResponse>("/api/supplier-portal/me")
      .then((me) => {
        try {
          localStorage.setItem(SUPPLIER_PORTAL_ME_KEY, JSON.stringify(me));
        } catch {
          // Non-fatal.
        }
        router.replace("/supplier-portal/purchase-orders");
      })
      .catch((e) => {
        // Clear the token — it's invalid / expired / revoked.
        supplierPortalApi.clearSession();
        setStatus("error");
        setError(e.message);
      });
  }, [params, router]);

  if (status === "error") {
    return (
      <div className="rounded-xl border bg-white p-8 text-center space-y-4">
        <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-red-100">
          <svg className="h-6 w-6 text-red-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
          </svg>
        </div>
        <h2 className="text-lg font-semibold text-gray-900">Link invalid or expired</h2>
        <p className="text-sm text-muted-foreground">{error}</p>
        <p className="text-xs text-muted-foreground">
          Ask the organisation to send you a new access link.
        </p>
      </div>
    );
  }

  return (
    <div className="rounded-xl border bg-white p-8 text-center">
      <p className="text-sm text-muted-foreground">Verifying your link…</p>
    </div>
  );
}

export default function VerifyPage() {
  return (
    <Suspense fallback={<div className="text-sm text-muted-foreground">Loading…</div>}>
      <VerifyInner />
    </Suspense>
  );
}
