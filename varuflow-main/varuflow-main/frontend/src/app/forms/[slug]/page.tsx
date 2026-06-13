"use client";

import { useEffect, useState } from "react";
import { Loader2, CheckCircle } from "lucide-react";

const BASE = process.env.NEXT_PUBLIC_API_URL ?? "";

interface FormField {
  name: string;
  label: string;
  type: string;
  required?: boolean;
  options?: string[];
}

interface FormInfo {
  title: string;
  description: string | null;
  fields: FormField[];
  redirect_url: string | null;
}

export default function FormsPage({ params }: { params: { slug: string } }) {
  const { slug } = params;
  const [form, setForm] = useState<FormInfo | null>(null);
  const [notFound, setNotFound] = useState(false);
  const [data, setData] = useState<Record<string, string>>({});
  const [submitting, setSubmitting] = useState(false);
  const [submitted, setSubmitted] = useState(false);
  const [redirectUrl, setRedirectUrl] = useState<string | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    fetch(`${BASE}/api/forms/${slug}`)
      .then((r) => {
        if (r.status === 404) { setNotFound(true); return null; }
        return r.json();
      })
      .then((d) => d && setForm(d))
      .catch(() => setNotFound(true));
  }, [slug]);

  function handleChange(name: string, value: string) {
    setData((prev) => ({ ...prev, [name]: value }));
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError("");

    // Client-side required validation
    for (const field of form?.fields ?? []) {
      if (field.required && !data[field.name]) {
        setError(`${field.label} is required.`);
        return;
      }
    }

    setSubmitting(true);
    try {
      const r = await fetch(`${BASE}/api/forms/${slug}/submit`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ data }),
      });
      if (!r.ok) {
        const d = await r.json().catch(() => ({}));
        throw new Error(d.detail ?? "Submission failed");
      }
      const res = await r.json();
      setRedirectUrl(res.redirect_url ?? null);
      setSubmitted(true);
      if (res.redirect_url) {
        window.location.href = res.redirect_url;
      }
    } catch (err: unknown) {
      setError((err as Error).message ?? "Something went wrong.");
    } finally {
      setSubmitting(false);
    }
  }

  if (notFound) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <p className="text-gray-500">Form not found.</p>
      </div>
    );
  }

  if (!form) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <Loader2 className="h-6 w-6 animate-spin text-gray-400" />
      </div>
    );
  }

  if (submitted && !redirectUrl) {
    return (
      <div className="flex flex-col items-center justify-center min-h-screen gap-4 text-center px-4">
        <CheckCircle className="h-12 w-12 text-green-500" />
        <h1 className="text-2xl font-semibold">Submitted!</h1>
        <p className="text-gray-500">Thank you for reaching out.</p>
      </div>
    );
  }

  return (
    <div className="max-w-lg mx-auto px-4 py-10">
      <div className="bg-white border rounded-2xl p-6">
        <h1 className="text-2xl font-semibold mb-1">{form.title}</h1>
        {form.description && (
          <p className="text-gray-500 text-sm mb-5">{form.description}</p>
        )}

        <form onSubmit={handleSubmit} className="space-y-4">
          {form.fields.map((field) => (
            <div key={field.name}>
              <label className="text-sm font-medium text-gray-700">
                {field.label}{field.required && " *"}
              </label>
              {field.type === "textarea" ? (
                <textarea
                  name={field.name}
                  required={field.required}
                  rows={4}
                  value={data[field.name] ?? ""}
                  onChange={(e) => handleChange(field.name, e.target.value)}
                  className="mt-1 w-full border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-300 resize-none"
                />
              ) : field.type === "select" ? (
                <select
                  name={field.name}
                  required={field.required}
                  value={data[field.name] ?? ""}
                  onChange={(e) => handleChange(field.name, e.target.value)}
                  className="mt-1 w-full border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-300"
                >
                  <option value="">Select…</option>
                  {(field.options ?? []).map((opt) => (
                    <option key={opt} value={opt}>{opt}</option>
                  ))}
                </select>
              ) : (
                <input
                  type={field.type}
                  name={field.name}
                  required={field.required}
                  value={data[field.name] ?? ""}
                  onChange={(e) => handleChange(field.name, e.target.value)}
                  className="mt-1 w-full border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-300"
                />
              )}
            </div>
          ))}

          {error && <p className="text-sm text-red-600">{error}</p>}

          <button
            type="submit"
            disabled={submitting}
            className="w-full flex items-center justify-center gap-2 bg-indigo-600 text-white rounded-lg py-2.5 text-sm font-medium hover:bg-indigo-700 disabled:opacity-50 transition-colors"
          >
            {submitting && <Loader2 className="h-4 w-4 animate-spin" />}
            Submit
          </button>
        </form>
      </div>
    </div>
  );
}
