"use client";

import { createClient } from "@/lib/supabase/client";
import { useTranslations } from "next-intl";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { Button } from "@/components/ui/button";

type Step = 1 | 2 | 3;

interface CompanyForm {
  company_name: string;
  org_number: string;
  vat_number: string;
  address: string;
}

// Swedish org number: 6 digits, optional dash, 4 digits
const ORG_NUMBER_RE = /^\d{6}-?\d{4}$/;

export default function OnboardingPage() {
  const t = useTranslations("onboarding");
  const router = useRouter();
  // Supabase client — created inside the component, never at module level
  const supabase = createClient();

  const [step, setStep] = useState<Step>(1);
  const [form, setForm] = useState<CompanyForm>({
    company_name: "",
    org_number: "",
    vat_number: "",
    address: "",
  });
  const [errors, setErrors] = useState<Partial<CompanyForm>>({});
  const [apiError, setApiError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  function validate(): boolean {
    const next: Partial<CompanyForm> = {};
    if (!form.company_name.trim()) next.company_name = "Required";
    if (form.org_number && !ORG_NUMBER_RE.test(form.org_number)) {
      next.org_number = "Format: 556000-0000";
    }
    setErrors(next);
    return Object.keys(next).length === 0;
  }

  async function handleStep1(e: React.FormEvent) {
    e.preventDefault();
    if (!validate()) return;
    setStep(2);
  }

  async function handleFinish() {
    setLoading(true);
    setApiError(null);

    const { data: { session } } = await supabase.auth.getSession();
    if (!session) {
      router.push("/auth/login");
      return;
    }

    try {
      const res = await fetch(
        `${process.env.NEXT_PUBLIC_API_URL}/api/auth/onboarding`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${session.access_token}`,
          },
          body: JSON.stringify({
            company_name: form.company_name,
            org_number: form.org_number || null,
            vat_number: form.vat_number || null,
            address: form.address || null,
          }),
        }
      );

      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error(body.detail ?? "Failed to create organization");
      }

      setStep(3);
    } catch (err) {
      setApiError(err instanceof Error ? err.message : "Something went wrong");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-gray-50 px-4">
      <div className="w-full max-w-lg">
        {/* Header */}
        <div className="mb-8 text-center">
          <span className="text-2xl font-bold text-[#1a2332]">Varuflow</span>
          <h1 className="mt-4 text-xl font-semibold text-gray-900">{t("title")}</h1>
          <p className="mt-1 text-sm text-muted-foreground">{t("subtitle")}</p>
        </div>

        {/* Step indicator */}
        <div className="mb-8 flex items-center justify-center gap-2">
          {([1, 2, 3] as Step[]).map((s) => (
            <div key={s} className="flex items-center gap-2">
              <div
                className={`flex h-7 w-7 items-center justify-center rounded-full text-xs font-medium transition-colors ${
                  s === step
                    ? "bg-[#1a2332] text-white"
                    : s < step
                    ? "bg-green-500 text-white"
                    : "border border-gray-300 text-gray-400"
                }`}
              >
                {s < step ? "✓" : s}
              </div>
              {s < 3 && (
                <div
                  className={`h-px w-8 ${s < step ? "bg-green-500" : "bg-gray-200"}`}
                />
              )}
            </div>
          ))}
        </div>

        {/* Step 1 — Company details */}
        {step === 1 && (
          <form
            onSubmit={handleStep1}
            className="space-y-5 rounded-xl border bg-white p-8 shadow-sm"
          >
            <h2 className="text-base font-semibold text-gray-900">{t("step1Title")}</h2>

            <Field
              id="company_name"
              label={t("companyName")}
              required
              placeholder={t("companyNamePlaceholder")}
              value={form.company_name}
              error={errors.company_name}
              onChange={(v) => setForm((f) => ({ ...f, company_name: v }))}
            />
            <Field
              id="org_number"
              label={t("orgNumber")}
              placeholder={t("orgNumberPlaceholder")}
              hint={t("orgNumberHint")}
              value={form.org_number}
              error={errors.org_number}
              onChange={(v) => setForm((f) => ({ ...f, org_number: v }))}
            />
            <Field
              id="vat_number"
              label={t("vatNumber")}
              placeholder={t("vatNumberPlaceholder")}
              value={form.vat_number}
              onChange={(v) => setForm((f) => ({ ...f, vat_number: v }))}
            />
            <Field
              id="address"
              label={t("address")}
              placeholder="Storgatan 1, 111 23 Stockholm"
              value={form.address}
              onChange={(v) => setForm((f) => ({ ...f, address: v }))}
            />

            <Button
              type="submit"
              className="w-full bg-[#1a2332] hover:bg-[#2a3342] text-white"
            >
              {t("continue")}
            </Button>
          </form>
        )}

        {/* Step 2 — Logo (optional) */}
        {step === 2 && (
          <div className="space-y-5 rounded-xl border bg-white p-8 shadow-sm">
            <h2 className="text-base font-semibold text-gray-900">{t("step2Title")}</h2>

            <div className="flex flex-col items-center gap-4 rounded-lg border-2 border-dashed border-gray-200 p-10 text-center">
              <div className="text-4xl">🏢</div>
              <p className="text-sm font-medium text-gray-700">{t("logoUpload")}</p>
              <p className="text-xs text-muted-foreground">{t("logoHint")}</p>
              <Button variant="outline" disabled className="text-sm">
                Choose file (coming soon)
              </Button>
            </div>

            {apiError && (
              <p className="rounded-md bg-red-50 px-3 py-2 text-sm text-red-600">
                {apiError}
              </p>
            )}

            <div className="flex gap-3">
              <Button
                variant="outline"
                className="flex-1"
                onClick={() => setStep(1)}
              >
                Back
              </Button>
              <Button
                className="flex-1 bg-[#1a2332] hover:bg-[#2a3342] text-white"
                disabled={loading}
                onClick={handleFinish}
              >
                {loading ? "..." : t("continue")}
              </Button>
            </div>

            <div className="text-center">
              <button
                type="button"
                className="text-sm text-muted-foreground underline-offset-4 hover:underline"
                onClick={handleFinish}
                disabled={loading}
              >
                {t("step2Skip")}
              </button>
            </div>
          </div>
        )}

        {/* Step 3 — Done */}
        {step === 3 && (
          <div className="space-y-6 rounded-xl border bg-white p-8 shadow-sm text-center">
            <div className="mx-auto flex h-16 w-16 items-center justify-center rounded-full bg-green-100 text-3xl">
              🎉
            </div>
            <div>
              <h2 className="text-lg font-semibold text-gray-900">{t("step3Title")}</h2>
              <p className="mt-1 text-sm text-muted-foreground">
                {form.company_name} is ready to go.
              </p>
            </div>
            <Button
              className="w-full bg-[#1a2332] hover:bg-[#2a3342] text-white"
              onClick={() => router.push("/dashboard")}
            >
              {t("finish")}
            </Button>
          </div>
        )}
      </div>
    </div>
  );
}

// ---- Small helper component ----

function Field({
  id,
  label,
  required,
  placeholder,
  hint,
  value,
  error,
  onChange,
}: {
  id: string;
  label: string;
  required?: boolean;
  placeholder?: string;
  hint?: string;
  value: string;
  error?: string;
  onChange: (v: string) => void;
}) {
  return (
    <div className="space-y-1">
      <label htmlFor={id} className="text-sm font-medium text-gray-700">
        {label}
        {required && <span className="ml-1 text-red-500">*</span>}
      </label>
      <input
        id={id}
        type="text"
        placeholder={placeholder}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className={`block w-full rounded-md border px-3 py-2 text-sm shadow-sm focus:outline-none focus:ring-1 ${
          error
            ? "border-red-400 focus:border-red-500 focus:ring-red-500"
            : "border-gray-300 focus:border-[#1a2332] focus:ring-[#1a2332]"
        }`}
      />
      {hint && !error && <p className="text-xs text-muted-foreground">{hint}</p>}
      {error && <p className="text-xs text-red-500">{error}</p>}
    </div>
  );
}
