"use client";

import { useState } from "react";
import { useRouter, useParams } from "next/navigation";
import { Loader2 } from "lucide-react";

const API = process.env.NEXT_PUBLIC_API_URL ?? "";

export default function TrialSignupForm() {
  const router = useRouter();
  const params = useParams();
  const locale = (params?.locale as string) ?? "en";

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError("");

    if (!email || !password) {
      setError("Email and password are required.");
      return;
    }
    if (password.length < 8) {
      setError("Password must be at least 8 characters.");
      return;
    }

    setLoading(true);
    try {
      // First create the account via Supabase sign-up, then activate trial.
      // We redirect to the app's signup flow with ?trial=pro pre-selected
      // so the existing onboarding handles account creation + trial activation.
      const url = new URL(`/${locale}/auth/signup`, window.location.origin);
      url.searchParams.set("email", email);
      url.searchParams.set("trial", "pro");
      router.push(url.toString());
    } catch {
      setError("Something went wrong. Please try again.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <form
      onSubmit={handleSubmit}
      className="mx-auto w-full max-w-md space-y-4"
      noValidate
    >
      <div>
        <label htmlFor="trial-email" className="vf-text-m mb-1.5 block text-xs font-medium">
          Work email
        </label>
        <input
          id="trial-email"
          type="email"
          autoComplete="email"
          required
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          placeholder="you@company.com"
          className="vf-input w-full rounded-xl border px-4 py-3 text-sm outline-none focus:ring-2 focus:ring-indigo-500"
          style={{ borderColor: "rgba(255,255,255,0.12)" }}
        />
      </div>

      <div>
        <label htmlFor="trial-password" className="vf-text-m mb-1.5 block text-xs font-medium">
          Password (min. 8 characters)
        </label>
        <input
          id="trial-password"
          type="password"
          autoComplete="new-password"
          required
          minLength={8}
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          placeholder="Create a password"
          className="vf-input w-full rounded-xl border px-4 py-3 text-sm outline-none focus:ring-2 focus:ring-indigo-500"
          style={{ borderColor: "rgba(255,255,255,0.12)" }}
        />
      </div>

      {error && (
        <p className="rounded-lg bg-red-500/10 px-4 py-3 text-sm text-red-400">{error}</p>
      )}

      <button
        type="submit"
        disabled={loading}
        className="vf-btn w-full rounded-xl py-3 text-sm font-semibold"
      >
        {loading ? (
          <span className="flex items-center justify-center gap-2">
            <Loader2 className="h-4 w-4 animate-spin" />
            Starting trial…
          </span>
        ) : (
          "Start 14-day free trial — no card required"
        )}
      </button>

      <p className="vf-text-m text-center text-xs">
        No credit card required · Cancel anytime · Full Pro access
      </p>
    </form>
  );
}
