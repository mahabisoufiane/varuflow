"use client";

import { useLocale } from "next-intl";
import { Navigation, PenLine, CreditCard, Mic } from "lucide-react";

const FEATURES = [
  {
    icon: <Navigation className="h-8 w-8" />,
    title: "GPS Route Planning",
    description: "Plan optimised delivery routes for drivers and field technicians. Track stop-by-stop progress in real time.",
    href: "mobile/routes",
    color: "bg-blue-50 text-blue-600",
  },
  {
    icon: <PenLine className="h-8 w-8" />,
    title: "Digital Signatures",
    description: "Capture on-device signatures for delivery notes, contracts, and invoices. Legally timestamped with signer IP.",
    href: "mobile/signatures",
    color: "bg-purple-50 text-purple-600",
  },
  {
    icon: <CreditCard className="h-8 w-8" />,
    title: "NFC / Tap-to-Pay",
    description: "Accept card payments on-site via Stripe Terminal. Tap-to-pay with NFC readers, automatically mark invoices paid.",
    href: "mobile/terminal",
    color: "bg-green-50 text-green-600",
  },
  {
    icon: <Mic className="h-8 w-8" />,
    title: "Voice Notes",
    description: "Record audio notes and attach them to customers, suppliers, or route stops. Optional Whisper transcription.",
    href: "mobile/voice-notes",
    color: "bg-amber-50 text-amber-600",
  },
];

export default function MobileHubPage() {
  const locale = useLocale();

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-semibold text-gray-900">Mobile & Field</h1>
        <p className="mt-1 text-sm text-gray-500">
          Tools for delivery drivers, field service technicians, and mobile sales teams.
        </p>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-6">
        {FEATURES.map((f) => (
          <a
            key={f.href}
            href={`/${locale}/${f.href}`}
            className="group flex flex-col gap-4 rounded-2xl border border-gray-200 bg-white p-6 shadow-sm hover:border-blue-400 hover:shadow-md transition-all"
          >
            <div className={`flex h-14 w-14 items-center justify-center rounded-xl ${f.color} transition-transform group-hover:scale-105`}>
              {f.icon}
            </div>
            <div>
              <h2 className="text-base font-semibold text-gray-900">{f.title}</h2>
              <p className="mt-1 text-sm text-gray-500">{f.description}</p>
            </div>
            <span className="mt-auto text-sm font-medium text-blue-600 group-hover:underline">Open →</span>
          </a>
        ))}
      </div>
    </div>
  );
}
