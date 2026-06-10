"use client";

import { createClient } from "@/lib/supabase/client";
import { Link } from "@/i18n/navigation";
import { useSearchParams } from "next/navigation";
import { useState } from "react";
import { Mail, CheckCircle2, Loader2, RefreshCw } from "lucide-react";

export default function VerifyEmailPage() {
  const searchParams = useSearchParams();
  const email = searchParams.get("email") ?? "";

  const [resending, setResending] = useState(false);
  const [resent, setResent] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleResend() {
    if (!email) { setError("No email address found. Please sign up again."); return; }
    setResending(true);
    setError(null);
    try {
      const supabase = createClient();
      const { error: resendError } = await supabase.auth.resend({
        type: "signup",
        email,
      });
      if (resendError) throw new Error(resendError.message);
      setResent(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to resend. Please try again.");
    } finally {
      setResending(false);
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-gray-50 px-4">
      <div className="w-full max-w-md rounded-xl border bg-white p-8 shadow-sm text-center space-y-6">

        <div className="mx-auto flex h-16 w-16 items-center justify-center rounded-full bg-blue-50">
          <Mail className="h-8 w-8 text-blue-600" />
        </div>

        <div className="space-y-2">
          <h1 className="text-xl font-semibold text-gray-900">Check your email</h1>
          <p className="text-sm text-gray-500">
            We sent a confirmation link to{" "}
            {email ? (
              <span className="font-medium text-gray-900">{email}</span>
            ) : (
              "your email address"
            )}
            . Click it to activate your account.
          </p>
        </div>

        {error && (
          <div className="rounded-md bg-red-50 border border-red-200 px-4 py-3 text-sm text-red-700 text-left">
            {error}
          </div>
        )}

        {resent ? (
          <div className="flex items-center justify-center gap-2 rounded-md bg-green-50 border border-green-200 px-4 py-3 text-sm text-green-700">
            <CheckCircle2 className="h-4 w-4 flex-shrink-0" />
            Confirmation email resent. Check your inbox.
          </div>
        ) : (
          <button
            onClick={handleResend}
            disabled={resending}
            className="inline-flex items-center gap-2 rounded-md border border-gray-300 bg-white px-4 py-2 text-sm font-medium text-gray-700 shadow-sm hover:bg-gray-50 disabled:opacity-50 transition-colors"
          >
            {resending ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <RefreshCw className="h-4 w-4" />
            )}
            {resending ? "Sending…" : "Resend confirmation email"}
          </button>
        )}

        <div className="text-xs text-gray-400 space-y-1">
          <p>Didn&apos;t get it? Check your spam folder.</p>
          <p>
            Wrong address?{" "}
            <Link href="/auth/signup" className="text-blue-600 hover:underline">
              Sign up again
            </Link>
          </p>
        </div>

      </div>
    </div>
  );
}
