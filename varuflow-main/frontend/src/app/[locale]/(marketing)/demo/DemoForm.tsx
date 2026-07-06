"use client";
import { useState } from "react";
import { Loader2, CheckCircle2 } from "lucide-react";

const API = process.env.NEXT_PUBLIC_API_URL ?? "";

export default function DemoRequestForm() {
  const [form, setForm] = useState({ name: "", email: "", company: "", size: "", message: "" });
  const [loading, setLoading] = useState(false);
  const [done, setDone] = useState(false);
  const [error, setError] = useState("");

  function set(field: string, value: string) {
    setForm((f) => ({ ...f, [field]: value }));
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!form.name || !form.email || !form.company) {
      setError("Please fill in all required fields.");
      return;
    }
    setLoading(true);
    setError("");
    try {
      // Captured via the marketing waitlist (no dedicated demo endpoint yet).
      // Real route is POST /api/waitlist ("/signup" hit a dynamic segment and
      // failed) — and the old code never checked res.ok, so visitors saw
      // "request received" while nothing was saved.
      const res = await fetch(`${API}/api/waitlist`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          email: form.email,
          // Backend stores {email, company_name} — keep company + contact name.
          company_name: `${form.company} — ${form.name} (demo request)`.slice(0, 255),
        }),
      });
      if (!res.ok && res.status !== 409) throw new Error(`HTTP ${res.status}`);
      setDone(true);
    } catch {
      setError("Something went wrong. Please try again or email us directly.");
    } finally {
      setLoading(false);
    }
  }

  if (done) {
    return (
      <div className="flex flex-col items-center justify-center gap-4 rounded-2xl border border-green-500/30 bg-green-500/10 px-8 py-12 text-center">
        <CheckCircle2 className="h-12 w-12 text-green-400" />
        <h3 className="vf-text-1 text-xl font-bold">Demo request received!</h3>
        <p className="vf-text-2 text-sm">We&apos;ll reach out within 1 business day to schedule a time that works for you.</p>
      </div>
    );
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <div className="grid gap-4 sm:grid-cols-2">
        <div>
          <label className="vf-text-m mb-1.5 block text-xs font-medium">Full name *</label>
          <input value={form.name} onChange={(e) => set("name", e.target.value)} required placeholder="Jane Smith"
            className="vf-input w-full rounded-xl border px-4 py-2.5 text-sm outline-none focus:ring-2 focus:ring-indigo-500"
            style={{ borderColor: "rgba(255,255,255,0.12)" }} />
        </div>
        <div>
          <label className="vf-text-m mb-1.5 block text-xs font-medium">Work email *</label>
          <input type="email" value={form.email} onChange={(e) => set("email", e.target.value)} required placeholder="jane@company.com"
            className="vf-input w-full rounded-xl border px-4 py-2.5 text-sm outline-none focus:ring-2 focus:ring-indigo-500"
            style={{ borderColor: "rgba(255,255,255,0.12)" }} />
        </div>
      </div>
      <div className="grid gap-4 sm:grid-cols-2">
        <div>
          <label className="vf-text-m mb-1.5 block text-xs font-medium">Company *</label>
          <input value={form.company} onChange={(e) => set("company", e.target.value)} required placeholder="Acme Wholesale AB"
            className="vf-input w-full rounded-xl border px-4 py-2.5 text-sm outline-none focus:ring-2 focus:ring-indigo-500"
            style={{ borderColor: "rgba(255,255,255,0.12)" }} />
        </div>
        <div>
          <label className="vf-text-m mb-1.5 block text-xs font-medium">Company size</label>
          <select value={form.size} onChange={(e) => set("size", e.target.value)}
            className="vf-input w-full rounded-xl border px-4 py-2.5 text-sm outline-none focus:ring-2 focus:ring-indigo-500"
            style={{ borderColor: "rgba(255,255,255,0.12)" }}>
            <option value="">Select…</option>
            <option>1–5 employees</option>
            <option>6–20 employees</option>
            <option>21–100 employees</option>
            <option>100+ employees</option>
          </select>
        </div>
      </div>
      <div>
        <label className="vf-text-m mb-1.5 block text-xs font-medium">What are you hoping to see?</label>
        <textarea value={form.message} onChange={(e) => set("message", e.target.value)} rows={3}
          placeholder="Inventory management, B2B portal, ZATCA invoicing…"
          className="vf-input w-full rounded-xl border px-4 py-2.5 text-sm outline-none focus:ring-2 focus:ring-indigo-500 resize-none"
          style={{ borderColor: "rgba(255,255,255,0.12)" }} />
      </div>
      {error && <p className="rounded-lg bg-red-500/10 px-4 py-3 text-sm text-red-400">{error}</p>}
      <button type="submit" disabled={loading} className="vf-btn w-full rounded-xl py-3 text-sm font-semibold">
        {loading ? <span className="flex items-center justify-center gap-2"><Loader2 className="h-4 w-4 animate-spin" /> Sending…</span> : "Request a demo"}
      </button>
    </form>
  );
}
