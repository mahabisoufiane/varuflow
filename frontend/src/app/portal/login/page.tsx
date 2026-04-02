"use client";

import { useState } from "react";
import { portalApi } from "@/lib/portal-client";

export default function PortalLoginPage() {
  const [email, setEmail] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [sent, setSent] = useState(false);
  const [devUrl, setDevUrl] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      const res = await portalApi.post<{ status: string; dev_magic_url?: string | null }>(
        "/api/portal/auth/magic-link",
        { email }
      );
      setSent(true);
      if (res.dev_magic_url) setDevUrl(res.dev_magic_url);
    } catch (e: any) {
      setError(e.message);
    } finally {
      setSubmitting(false);
    }
  }

  if (sent) {
    return (
      <div className="rounded-xl border bg-white p-8 text-center space-y-3">
        <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-green-100">
          <svg className="h-6 w-6 text-green-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
          </svg>
        </div>
        <h2 className="text-lg font-semibold text-gray-900">Check your inbox</h2>
        <p className="text-sm text-muted-foreground">
          If that email matches a customer account, we sent a login link. It expires in 15 minutes.
        </p>
        {devUrl && (
          <div className="rounded-lg border border-yellow-200 bg-yellow-50 p-3 text-left">
            <p className="text-xs font-medium text-yellow-800 mb-1">Dev mode — Resend not configured</p>
            <a href={devUrl} className="text-xs text-blue-600 underline break-all">{devUrl}</a>
          </div>
        )}
        <button
          onClick={() => { setSent(false); setDevUrl(null); }}
          className="text-sm text-[#1a2332] underline"
        >
          Try a different email
        </button>
      </div>
    );
  }

  return (
    <div className="rounded-xl border bg-white p-8 space-y-6">
      <div>
        <h1 className="text-xl font-bold text-[#1a2332]">Sign in to your portal</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Enter the email address associated with your account and we&apos;ll send you a magic link.
        </p>
      </div>

      <form onSubmit={handleSubmit} className="space-y-4">
        <div className="space-y-1.5">
          <label className="block text-sm font-medium text-gray-700">Email address</label>
          <input
            type="email"
            required
            autoFocus
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder="you@company.com"
            className="block w-full rounded-md border border-gray-300 px-3 py-2.5 text-sm focus:border-[#1a2332] focus:outline-none focus:ring-1 focus:ring-[#1a2332]"
          />
        </div>
        {error && <p className="text-sm text-red-600">{error}</p>}
        <button
          type="submit"
          disabled={submitting}
          className="w-full rounded-md bg-[#1a2332] px-4 py-2.5 text-sm font-semibold text-white hover:bg-[#2a3342] disabled:opacity-60"
        >
          {submitting ? "Sending…" : "Send magic link"}
        </button>
      </form>
    </div>
  );
}
