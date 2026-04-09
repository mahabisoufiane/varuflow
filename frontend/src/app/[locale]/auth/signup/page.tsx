"use client";

import { supabase } from "@/lib/supabase/client";
import { useTranslations } from "next-intl";
import Link from "next/link";
import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Check, X } from "lucide-react";

const RULES = [
  { label: "At least 8 characters", test: (p: string) => p.length >= 8 },
  { label: "Uppercase letter (A–Z)", test: (p: string) => /[A-Z]/.test(p) },
  { label: "Lowercase letter (a–z)", test: (p: string) => /[a-z]/.test(p) },
  { label: "Number (0–9)", test: (p: string) => /[0-9]/.test(p) },
  { label: "Special character (!@#$…)", test: (p: string) => /[^A-Za-z0-9]/.test(p) },
];

export default function SignupPage() {
  const t = useTranslations("auth");

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [sent, setSent] = useState(false);

  const allRulesMet = RULES.every((r) => r.test(password));

  async function handleSignup(e: React.FormEvent) {
    e.preventDefault();
    if (!allRulesMet) return;
    setLoading(true);
    setError(null);

    const { error } = await supabase.auth.signUp({
      email,
      password,
      options: {
        emailRedirectTo: `${location.origin}/auth/callback?next=/onboarding`,
      },
    });

    setLoading(false);
    if (error) return setError(error.message);
    setSent(true);
  }

  if (sent) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-gray-50 px-4">
        <div className="w-full max-w-sm space-y-4 rounded-xl border bg-white p-8 shadow-sm text-center">
          <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-green-100 text-2xl">
            ✉️
          </div>
          <h2 className="text-lg font-semibold text-[#1a2332]">Verify your email</h2>
          <p className="text-sm text-muted-foreground">
            {t("magicLinkSent", { email })}
          </p>
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
          <p className="mt-1 text-sm text-muted-foreground">{t("signUpDescription")}</p>
        </div>

        <form onSubmit={handleSignup} className="space-y-4">
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

          <div className="space-y-1">
            <label htmlFor="password" className="text-sm font-medium text-gray-700">
              {t("password")}
            </label>
            <input
              id="password"
              type="password"
              required
              minLength={8}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="Min. 8 characters"
              className="block w-full rounded-md border border-gray-300 px-3 py-2 text-sm shadow-sm focus:border-[#1a2332] focus:outline-none focus:ring-1 focus:ring-[#1a2332]"
            />
            {password.length > 0 && (
              <ul className="mt-2 space-y-1">
                {RULES.map((rule) => {
                  const ok = rule.test(password);
                  return (
                    <li key={rule.label} className={`flex items-center gap-2 text-xs ${ok ? "text-green-600" : "text-red-500"}`}>
                      {ok ? <Check className="h-3 w-3 shrink-0" /> : <X className="h-3 w-3 shrink-0" />}
                      {rule.label}
                    </li>
                  );
                })}
              </ul>
            )}
          </div>

          {error && (
            <p className="rounded-md bg-red-50 px-3 py-2 text-sm text-red-600">
              {error}
            </p>
          )}

          <Button
            type="submit"
            disabled={loading || !allRulesMet}
            className="w-full bg-[#1a2332] hover:bg-[#2a3342] text-white disabled:opacity-50"
          >
            {loading ? "..." : t("createAccount")}
          </Button>
        </form>

        <p className="text-center text-sm text-muted-foreground">
          {t("hasAccount")}{" "}
          <Link href="/auth/login" className="font-medium text-[#1a2332] hover:underline">
            {t("login")}
          </Link>
        </p>
      </div>
    </div>
  );
}
