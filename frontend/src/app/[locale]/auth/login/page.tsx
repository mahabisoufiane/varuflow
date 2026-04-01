"use client";

import { createClient } from "@/lib/supabase/client";
import { useTranslations } from "next-intl";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useState } from "react";
import { Button } from "@/components/ui/button";

type Mode = "magic" | "password";

export default function LoginPage() {
  const t = useTranslations("auth");
  const searchParams = useSearchParams();
  const next = searchParams.get("next") ?? "/dashboard";

  const [mode, setMode] = useState<Mode>("magic");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [magicSent, setMagicSent] = useState(false);

  const supabase = createClient();

  async function handleMagicLink(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError(null);

    const { error } = await supabase.auth.signInWithOtp({
      email,
      options: { emailRedirectTo: `${location.origin}/auth/callback?next=${next}` },
    });

    setLoading(false);
    if (error) return setError(error.message);
    setMagicSent(true);
  }

  async function handlePassword(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError(null);

    const { error } = await supabase.auth.signInWithPassword({ email, password });

    setLoading(false);
    if (error) return setError(error.message);
    window.location.href = next;
  }

  if (magicSent) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-gray-50 px-4">
        <div className="w-full max-w-sm space-y-4 rounded-xl border bg-white p-8 shadow-sm text-center">
          <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-green-100 text-2xl">
            ✉️
          </div>
          <h2 className="text-lg font-semibold text-[#1a2332]">Check your inbox</h2>
          <p className="text-sm text-muted-foreground">
            {t("magicLinkSent", { email })}
          </p>
          <Button
            variant="ghost"
            className="text-sm"
            onClick={() => setMagicSent(false)}
          >
            Use a different email
          </Button>
        </div>
      </div>
    );
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-gray-50 px-4">
      <div className="w-full max-w-sm space-y-6 rounded-xl border bg-white p-8 shadow-sm">
        {/* Logo */}
        <div className="text-center">
          <span className="text-2xl font-bold text-[#1a2332]">Varuflow</span>
          <p className="mt-1 text-sm text-muted-foreground">{t("loginDescription")}</p>
        </div>

        <form
          onSubmit={mode === "magic" ? handleMagicLink : handlePassword}
          className="space-y-4"
        >
          {/* Email */}
          <div className="space-y-1">
            <label htmlFor="email" className="text-sm font-medium text-gray-700">
              {t("email")}
            </label>
            <input
              id="email"
              type="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="you@company.se"
              className="block w-full rounded-md border border-gray-300 px-3 py-2 text-sm shadow-sm focus:border-[#1a2332] focus:outline-none focus:ring-1 focus:ring-[#1a2332]"
            />
          </div>

          {/* Password (only in password mode) */}
          {mode === "password" && (
            <div className="space-y-1">
              <label htmlFor="password" className="text-sm font-medium text-gray-700">
                {t("password")}
              </label>
              <input
                id="password"
                type="password"
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="block w-full rounded-md border border-gray-300 px-3 py-2 text-sm shadow-sm focus:border-[#1a2332] focus:outline-none focus:ring-1 focus:ring-[#1a2332]"
              />
            </div>
          )}

          {error && (
            <p className="rounded-md bg-red-50 px-3 py-2 text-sm text-red-600">
              {error}
            </p>
          )}

          <Button
            type="submit"
            disabled={loading}
            className="w-full bg-[#1a2332] hover:bg-[#2a3342] text-white"
          >
            {loading
              ? "..."
              : mode === "magic"
              ? t("magicLink")
              : t("signInWithPassword")}
          </Button>
        </form>

        {/* Toggle mode */}
        <div className="text-center">
          <button
            type="button"
            className="text-sm text-[#1a2332] underline-offset-4 hover:underline"
            onClick={() => {
              setMode(mode === "magic" ? "password" : "magic");
              setError(null);
            }}
          >
            {t("orContinueWith")}
          </button>
        </div>

        {/* Sign up link */}
        <p className="text-center text-sm text-muted-foreground">
          {t("noAccount")}{" "}
          <Link href="/auth/signup" className="font-medium text-[#1a2332] hover:underline">
            {t("createAccount")}
          </Link>
        </p>
      </div>
    </div>
  );
}
