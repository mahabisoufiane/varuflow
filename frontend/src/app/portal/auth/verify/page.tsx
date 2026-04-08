"use client";

import { Suspense, useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { portalApi, PORTAL_TOKEN_KEY, PORTAL_CUSTOMER_KEY } from "@/lib/portal-client";

function VerifyInner() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const [status, setStatus] = useState<"verifying" | "error">("verifying");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const token = searchParams.get("token");
    if (!token) {
      setStatus("error");
      setError("Missing token in URL.");
      return;
    }

    portalApi
      .get<{ portal_token: string; customer_name: string; org_name: string }>(
        `/api/portal/auth/verify?token=${encodeURIComponent(token)}`
      )
      .then((res) => {
        localStorage.setItem(PORTAL_TOKEN_KEY, res.portal_token);
        localStorage.setItem(
          PORTAL_CUSTOMER_KEY,
          JSON.stringify({ customer_name: res.customer_name, org_name: res.org_name })
        );
        router.replace("/portal/invoices");
      })
      .catch((e) => {
        setStatus("error");
        setError(e.message);
      });
  }, [searchParams, router]);

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
        <a href="/portal/login" className="inline-block text-sm font-medium text-[#1a2332] underline">
          Request a new link
        </a>
      </div>
    );
  }

  return (
    <div className="rounded-xl border bg-white p-8 text-center space-y-3">
      <div className="mx-auto h-8 w-8 animate-spin rounded-full border-2 border-[#1a2332] border-t-transparent" />
      <p className="text-sm text-muted-foreground">Signing you in…</p>
    </div>
  );
}

export default function PortalVerifyPage() {
  return (
    <Suspense fallback={
      <div className="rounded-xl border bg-white p-8 text-center space-y-3">
        <div className="mx-auto h-8 w-8 animate-spin rounded-full border-2 border-[#1a2332] border-t-transparent" />
        <p className="text-sm text-muted-foreground">Loading…</p>
      </div>
    }>
      <VerifyInner />
    </Suspense>
  );
}
