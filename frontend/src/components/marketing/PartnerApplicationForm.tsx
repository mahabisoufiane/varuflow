"use client";
// frontend/src/components/marketing/PartnerApplicationForm.tsx
// Partner application form for accounting firms.

import { useState } from "react";
import { Loader2, CheckCircle2 } from "lucide-react";

const API = process.env.NEXT_PUBLIC_API_URL ?? "";

interface FormState {
  firm_name: string;
  contact_name: string;
  contact_email: string;
  contact_phone: string;
  country: string;
  client_count_estimate: string;
  application_notes: string;
}

const INITIAL: FormState = {
  firm_name: "",
  contact_name: "",
  contact_email: "",
  contact_phone: "",
  country: "SE",
  client_count_estimate: "",
  application_notes: "",
};

const COUNTRIES = [
  { value: "SE", label: "Sweden" },
  { value: "NO", label: "Norway" },
  { value: "DK", label: "Denmark" },
  { value: "FI", label: "Finland" },
  { value: "DE", label: "Germany" },
  { value: "GB", label: "United Kingdom" },
  { value: "NL", label: "Netherlands" },
  { value: "OTHER", label: "Other" },
];

const CLIENT_COUNTS = [
  { value: "1", label: "1 client" },
  { value: "3", label: "3 clients" },
  { value: "6", label: "6 clients" },
  { value: "10", label: "10+ clients" },
];

const inputCls =
  "w-full rounded-xl border border-white/10 bg-white/5 px-4 py-2.5 text-sm text-white placeholder-slate-500 outline-none transition-colors focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500";

const selectCls =
  "w-full rounded-xl border border-white/10 bg-[#0f172a] px-4 py-2.5 text-sm text-white outline-none transition-colors focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 appearance-none";

export default function PartnerApplicationForm() {
  const [form, setForm] = useState<FormState>(INITIAL);
  const [loading, setLoading] = useState(false);
  const [success, setSuccess] = useState(false);
  const [error, setError] = useState("");

  function set(field: keyof FormState, value: string) {
    setForm((prev) => ({ ...prev, [field]: value }));
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError("");

    const body: Record<string, unknown> = {
      firm_name: form.firm_name,
      contact_name: form.contact_name,
      contact_email: form.contact_email,
      country: form.country,
    };
    if (form.contact_phone) body.contact_phone = form.contact_phone;
    if (form.client_count_estimate)
      body.client_count_estimate = Number(form.client_count_estimate);
    if (form.application_notes) body.application_notes = form.application_notes;

    try {
      const res = await fetch(`${API}/api/partners/apply`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        throw new Error(
          (data as { detail?: string }).detail ?? `HTTP ${res.status}`
        );
      }
      setSuccess(true);
    } catch (err: unknown) {
      setError(
        err instanceof Error ? err.message : "Something went wrong. Please try again."
      );
    } finally {
      setLoading(false);
    }
  }

  if (success) {
    return (
      <div className="rounded-2xl border border-green-500/20 bg-green-500/8 p-8 text-center">
        <div className="mb-4 flex justify-center">
          <CheckCircle2 className="h-10 w-10 text-green-400" />
        </div>
        <h3 className="vf-text-1 mb-2 text-xl font-bold">Application received!</h3>
        <p className="vf-text-2 text-sm leading-relaxed">
          We&apos;ll review it within 1 business day and email{" "}
          <strong className="text-white">{form.contact_email}</strong>.
        </p>
      </div>
    );
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      {/* Firm name */}
      <div>
        <label className="mb-1.5 block text-xs font-semibold uppercase tracking-wide text-slate-400">
          Firm name <span className="text-red-400">*</span>
        </label>
        <input
          type="text"
          required
          value={form.firm_name}
          onChange={(e) => set("firm_name", e.target.value)}
          placeholder="Your accounting firm name"
          className={inputCls}
        />
      </div>

      {/* Contact name */}
      <div>
        <label className="mb-1.5 block text-xs font-semibold uppercase tracking-wide text-slate-400">
          Your name <span className="text-red-400">*</span>
        </label>
        <input
          type="text"
          required
          value={form.contact_name}
          onChange={(e) => set("contact_name", e.target.value)}
          placeholder="Your full name"
          className={inputCls}
        />
      </div>

      {/* Email + Phone */}
      <div className="grid gap-4 sm:grid-cols-2">
        <div>
          <label className="mb-1.5 block text-xs font-semibold uppercase tracking-wide text-slate-400">
            Email <span className="text-red-400">*</span>
          </label>
          <input
            type="email"
            required
            value={form.contact_email}
            onChange={(e) => set("contact_email", e.target.value)}
            placeholder="you@firm.com"
            className={inputCls}
          />
        </div>
        <div>
          <label className="mb-1.5 block text-xs font-semibold uppercase tracking-wide text-slate-400">
            Phone <span className="text-slate-600">(optional)</span>
          </label>
          <input
            type="tel"
            value={form.contact_phone}
            onChange={(e) => set("contact_phone", e.target.value)}
            placeholder="+46 70 000 0000"
            className={inputCls}
          />
        </div>
      </div>

      {/* Country + Client count */}
      <div className="grid gap-4 sm:grid-cols-2">
        <div>
          <label className="mb-1.5 block text-xs font-semibold uppercase tracking-wide text-slate-400">
            Country
          </label>
          <div className="relative">
            <select
              value={form.country}
              onChange={(e) => set("country", e.target.value)}
              className={selectCls}
            >
              {COUNTRIES.map((c) => (
                <option key={c.value} value={c.value}>
                  {c.label}
                </option>
              ))}
            </select>
          </div>
        </div>
        <div>
          <label className="mb-1.5 block text-xs font-semibold uppercase tracking-wide text-slate-400">
            Expected referrals in 3 months{" "}
            <span className="text-slate-600">(optional)</span>
          </label>
          <div className="relative">
            <select
              value={form.client_count_estimate}
              onChange={(e) => set("client_count_estimate", e.target.value)}
              className={selectCls}
            >
              <option value="">Expected referrals in 3 months</option>
              {CLIENT_COUNTS.map((c) => (
                <option key={c.value} value={c.value}>
                  {c.label}
                </option>
              ))}
            </select>
          </div>
        </div>
      </div>

      {/* Notes */}
      <div>
        <label className="mb-1.5 block text-xs font-semibold uppercase tracking-wide text-slate-400">
          About your firm <span className="text-slate-600">(optional)</span>
        </label>
        <textarea
          rows={4}
          value={form.application_notes}
          onChange={(e) => set("application_notes", e.target.value)}
          placeholder="Tell us about your firm and why you want to partner..."
          className={`${inputCls} resize-none`}
        />
      </div>

      {/* Error */}
      {error && (
        <div className="rounded-xl border border-red-500/20 bg-red-500/8 px-4 py-3 text-sm text-red-400">
          {error}
        </div>
      )}

      <button
        type="submit"
        disabled={loading}
        className="vf-btn flex w-full items-center justify-center gap-2 rounded-xl py-3 text-sm font-semibold disabled:opacity-60"
      >
        {loading ? (
          <Loader2 className="h-4 w-4 animate-spin" />
        ) : (
          "Apply to become a partner"
        )}
      </button>

      <p className="text-center text-[11px] text-slate-500">
        We review every application within 1 business day. No commitment required.
      </p>
    </form>
  );
}
