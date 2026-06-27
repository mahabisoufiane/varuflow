"use client";
import { useState } from "react";
import { Loader2, CheckCircle2 } from "lucide-react";

const API = process.env.NEXT_PUBLIC_API_URL ?? "";

export default function ContactForm() {
  const [form, setForm] = useState({ name: "", email: "", subject: "", message: "" });
  const [loading, setLoading] = useState(false);
  const [done, setDone] = useState(false);
  const [error, setError] = useState("");

  function set(field: string, value: string) {
    setForm((f) => ({ ...f, [field]: value }));
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!form.name || !form.email || !form.message) { setError("Please fill in all required fields."); return; }
    setLoading(true); setError("");
    try {
      await fetch(`${API}/api/waitlist/signup`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ...form, source: "contact_form" }),
      });
      setDone(true);
    } catch {
      setError("Something went wrong. Please email us directly at hello@varuflow.se.");
    } finally {
      setLoading(false);
    }
  }

  if (done) {
    return (
      <div className="flex flex-col items-center gap-3 rounded-2xl border border-green-500/30 bg-green-500/10 px-8 py-10 text-center">
        <CheckCircle2 className="h-10 w-10 text-green-400" />
        <h3 className="vf-text-1 text-lg font-bold">Message sent!</h3>
        <p className="vf-text-2 text-sm">We&apos;ll get back to you within 1 business day.</p>
      </div>
    );
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <div className="grid gap-4 sm:grid-cols-2">
        <div>
          <label className="vf-text-m mb-1.5 block text-xs font-medium">Your name *</label>
          <input value={form.name} onChange={(e) => set("name", e.target.value)} required placeholder="Jane Smith"
            className="vf-input w-full rounded-xl border px-4 py-2.5 text-sm outline-none focus:ring-2 focus:ring-indigo-500"
            style={{ borderColor: "rgba(255,255,255,0.12)" }} />
        </div>
        <div>
          <label className="vf-text-m mb-1.5 block text-xs font-medium">Email *</label>
          <input type="email" value={form.email} onChange={(e) => set("email", e.target.value)} required placeholder="jane@company.com"
            className="vf-input w-full rounded-xl border px-4 py-2.5 text-sm outline-none focus:ring-2 focus:ring-indigo-500"
            style={{ borderColor: "rgba(255,255,255,0.12)" }} />
        </div>
      </div>
      <div>
        <label className="vf-text-m mb-1.5 block text-xs font-medium">Subject</label>
        <input value={form.subject} onChange={(e) => set("subject", e.target.value)} placeholder="How can we help?"
          className="vf-input w-full rounded-xl border px-4 py-2.5 text-sm outline-none focus:ring-2 focus:ring-indigo-500"
          style={{ borderColor: "rgba(255,255,255,0.12)" }} />
      </div>
      <div>
        <label className="vf-text-m mb-1.5 block text-xs font-medium">Message *</label>
        <textarea value={form.message} onChange={(e) => set("message", e.target.value)} required rows={5} placeholder="Tell us what you need…"
          className="vf-input w-full rounded-xl border px-4 py-2.5 text-sm outline-none focus:ring-2 focus:ring-indigo-500 resize-none"
          style={{ borderColor: "rgba(255,255,255,0.12)" }} />
      </div>
      {error && <p className="rounded-lg bg-red-500/10 px-4 py-3 text-sm text-red-400">{error}</p>}
      <button type="submit" disabled={loading} className="vf-btn w-full rounded-xl py-3 text-sm font-semibold">
        {loading ? <span className="flex items-center justify-center gap-2"><Loader2 className="h-4 w-4 animate-spin" />Sending…</span> : "Send message"}
      </button>
    </form>
  );
}
