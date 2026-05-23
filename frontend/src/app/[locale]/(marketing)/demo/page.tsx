import type { Metadata } from "next";
import { CalendarDays, Clock, Users } from "lucide-react";
import DemoForm from "./DemoForm";
import JsonLd, { organizationSchema } from "@/components/marketing/JsonLd";

const BASE = process.env.NEXT_PUBLIC_SITE_URL ?? "https://varuflow.vercel.app";

export const metadata: Metadata = {
  title: "Book a Demo — Varuflow",
  description: "See Varuflow in action. 30-minute personalised demo with a product specialist. No sales pressure.",
  openGraph: { title: "Book a Varuflow Demo", description: "30-minute live demo. See exactly what Varuflow can do for your business.", type: "website", url: `${BASE}/en/demo` },
  twitter: { card: "summary_large_image", title: "Book a Varuflow Demo" },
  alternates: { canonical: `${BASE}/en/demo`, languages: { en: `${BASE}/en/demo`, sv: `${BASE}/sv/demo`, "x-default": `${BASE}/en/demo` } },
};

export default function DemoPage() {
  return (
    <>
      <JsonLd data={organizationSchema()} />
      <div className="mx-auto max-w-5xl px-4 py-20">
        <div className="grid gap-16 lg:grid-cols-2 lg:items-start">
          <div>
            <p className="mb-4 inline-block rounded-full border border-indigo-500/30 bg-indigo-500/10 px-4 py-1 text-xs font-semibold uppercase tracking-widest text-indigo-400">
              Live demo
            </p>
            <h1 className="vf-text-1 text-3xl font-extrabold tracking-tight sm:text-4xl">
              See Varuflow in 30 minutes
            </h1>
            <p className="vf-text-2 mt-4 text-base leading-relaxed">
              A real product specialist walks you through your specific use case. No slides, no pitch — just the product working with your data.
            </p>
            <div className="mt-8 space-y-4">
              {[
                { icon: <Clock className="h-4 w-4" />, text: "30-minute session, tailored to your industry" },
                { icon: <Users className="h-4 w-4" />, text: "Invite your team — no limit on attendees" },
                { icon: <CalendarDays className="h-4 w-4" />, text: "Usually available within 1 business day" },
              ].map((item) => (
                <div key={item.text} className="flex items-center gap-3 text-sm">
                  <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-indigo-500/15 text-indigo-400">{item.icon}</span>
                  <span className="vf-text-2">{item.text}</span>
                </div>
              ))}
            </div>
          </div>
          <div className="rounded-2xl border border-white/10 bg-white/4 p-8">
            <h2 className="vf-text-1 mb-6 text-lg font-semibold">Request your demo</h2>
            <DemoForm />
          </div>
        </div>
      </div>
    </>
  );
}
