import type { Metadata } from "next";
import { Mail, MessageSquare } from "lucide-react";
import ContactForm from "./ContactForm";
import JsonLd, { organizationSchema } from "@/components/marketing/JsonLd";

const BASE = process.env.NEXT_PUBLIC_SITE_URL ?? "https://varuflow.vercel.app";

export const metadata: Metadata = {
  title: "Contact Us — Varuflow",
  description: "Questions about Varuflow, sales enquiries, partnerships, or press — we're here. Email us or fill in the contact form.",
  openGraph: { title: "Contact Varuflow", description: "Get in touch — we respond within 1 business day.", type: "website", url: `${BASE}/en/contact` },
  twitter: { card: "summary_large_image", title: "Contact Varuflow" },
  alternates: { canonical: `${BASE}/en/contact`, languages: { en: `${BASE}/en/contact`, sv: `${BASE}/sv/contact`, "x-default": `${BASE}/en/contact` } },
};

export default function ContactPage() {
  return (
    <>
      <JsonLd data={organizationSchema()} />
      <div className="mx-auto max-w-5xl px-4 py-20">
        <div className="grid gap-16 lg:grid-cols-2 lg:items-start">
          <div>
            <h1 className="vf-text-1 text-4xl font-extrabold tracking-tight">Get in touch</h1>
            <p className="vf-text-2 mt-4 text-base leading-relaxed">
              Questions about Varuflow, sales enquiries, partnerships, or press — we&apos;re here.
            </p>
            <div className="mt-10 space-y-5">
              {[
                { icon: <Mail className="h-4 w-4" />, label: "General", email: "hello@varuflow.se" },
                { icon: <MessageSquare className="h-4 w-4" />, label: "Support", email: "support@varuflow.se" },
                { icon: <Mail className="h-4 w-4" />, label: "Press", email: "press@varuflow.se" },
              ].map((c) => (
                <div key={c.label} className="flex items-center gap-3">
                  <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-[var(--vf-brand-primary-soft)] text-[var(--vf-brand-primary-light)]">{c.icon}</div>
                  <div>
                    <p className="vf-text-m text-xs">{c.label}</p>
                    <a href={`mailto:${c.email}`} className="vf-text-1 text-sm hover:underline">{c.email}</a>
                  </div>
                </div>
              ))}
            </div>
          </div>
          <div className="rounded-2xl border border-white/10 bg-white/4 p-8">
            <ContactForm />
          </div>
        </div>
      </div>
    </>
  );
}
