"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
import { COMPANY_SIZES, leadSchema } from "@/lib/lead";

const field =
  "w-full rounded-lg border border-line bg-paper px-4 py-2.5 text-body text-ink outline-none focus:border-brand";

export function DemoForm() {
  const t = useTranslations("demo");
  const [status, setStatus] = useState<"idle" | "submitting" | "success" | "error">("idle");

  async function onSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const data = Object.fromEntries(new FormData(e.currentTarget).entries());
    const parsed = leadSchema.safeParse(data);
    if (!parsed.success) {
      setStatus("error");
      return;
    }
    setStatus("submitting");
    try {
      const res = await fetch("/api/lead", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(parsed.data),
      });
      setStatus(res.ok ? "success" : "error");
    } catch {
      setStatus("error");
    }
  }

  if (status === "success") {
    return <p className="rounded-lg border border-line bg-paper-shade p-6 text-body text-ink">{t("success")}</p>;
  }

  return (
    <form onSubmit={onSubmit} className="space-y-4">
      <div className="grid gap-4 sm:grid-cols-2">
        <label className="block">
          <span className="mb-1.5 block text-small font-medium text-ink">{t("name")}</span>
          <input name="name" required maxLength={200} className={field} />
        </label>
        <label className="block">
          <span className="mb-1.5 block text-small font-medium text-ink">{t("company")}</span>
          <input name="company" required maxLength={200} className={field} />
        </label>
      </div>
      <div className="grid gap-4 sm:grid-cols-2">
        <label className="block">
          <span className="mb-1.5 block text-small font-medium text-ink">{t("email")}</span>
          <input name="email" type="email" required maxLength={320} className={field} />
        </label>
        <label className="block">
          <span className="mb-1.5 block text-small font-medium text-ink">{t("size")}</span>
          <select name="size" required defaultValue="" className={field}>
            <option value="" disabled>
              {t("sizePlaceholder")}
            </option>
            {COMPANY_SIZES.map((s) => (
              <option key={s} value={s}>
                {s}
              </option>
            ))}
          </select>
        </label>
      </div>
      <label className="block">
        <span className="mb-1.5 block text-small font-medium text-ink">{t("message")}</span>
        <textarea name="message" rows={4} maxLength={2000} className={field} />
      </label>
      {status === "error" && <p className="text-small font-medium text-red-600">{t("error")}</p>}
      <button
        type="submit"
        disabled={status === "submitting"}
        className="inline-flex items-center justify-center rounded-full bg-brand px-8 py-3 text-body font-semibold text-white transition-colors hover:bg-brand-strong disabled:opacity-50"
      >
        {status === "submitting" ? t("submitting") : t("submit")}
      </button>
    </form>
  );
}
