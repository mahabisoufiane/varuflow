"use client";

import { useState } from "react";
import { Link } from "@/i18n/navigation";
import { Check, Minus, X } from "lucide-react";

type BillingPeriod = "monthly" | "yearly";

interface PricingFeature {
  label: string;
  starter: boolean | string;
  pro: boolean | string;
  enterprise: boolean | string;
}

const FEATURES: PricingFeature[] = [
  { label: "Products", starter: "100", pro: "2,000", enterprise: "Unlimited" },
  { label: "Customers", starter: "20", pro: "Unlimited", enterprise: "Unlimited" },
  { label: "Team members", starter: "3", pro: "10", enterprise: "Unlimited" },
  { label: "Invoices / month", starter: "50", pro: "Unlimited", enterprise: "Unlimited" },
  { label: "Warehouses", starter: "1", pro: "5", enterprise: "Unlimited" },
  { label: "Inventory management", starter: true, pro: true, enterprise: true },
  { label: "POS terminal", starter: true, pro: true, enterprise: true },
  { label: "Fortnox integration", starter: false, pro: true, enterprise: true },
  { label: "B2B customer portal", starter: false, pro: true, enterprise: true },
  { label: "AI action cards", starter: false, pro: true, enterprise: true },
  { label: "Demand forecasting", starter: false, pro: true, enterprise: true },
  { label: "Multi-warehouse", starter: false, pro: true, enterprise: true },
  { label: "ZATCA e-invoicing", starter: false, pro: true, enterprise: true },
  { label: "Peppol / PINT", starter: false, pro: true, enterprise: true },
  { label: "Multi-entity / Franchise", starter: false, pro: false, enterprise: true },
  { label: "Custom integrations", starter: false, pro: false, enterprise: true },
  { label: "Dedicated onboarding", starter: false, pro: false, enterprise: true },
  { label: "SLA / support tier", starter: "Email (48h)", pro: "Priority (4h)", enterprise: "Dedicated CSM" },
];

const YEARLY_DISCOUNT = 0.2; // 20% off

export default function PricingTable() {
  const [billing, setBilling] = useState<BillingPeriod>("yearly");
  const [contactOpen, setContactOpen] = useState(false);
  const [sent, setSent] = useState(false);
  const [email, setEmail] = useState("");
  const [company, setCompany] = useState("");

  const monthly = { starter: 0, pro: 599 };
  function price(base: number) {
    if (base === 0) return "Free";
    const amt = billing === "yearly" ? Math.round(base * (1 - YEARLY_DISCOUNT)) : base;
    return `${amt} SEK`;
  }

  async function handleContact(e: React.FormEvent) {
    e.preventDefault();
    const apiUrl = process.env.NEXT_PUBLIC_API_URL ?? "";
    try {
      await fetch(`${apiUrl}/api/waitlist`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, company_name: company }),
      });
    } catch {}
    setSent(true);
  }

  const highlightBg = "bg-gradient-to-br from-indigo-600 to-violet-700";

  return (
    <div>
      {/* Contact Sales Modal */}
      {contactOpen && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center p-4"
          style={{ background: "rgba(0,0,0,0.7)", backdropFilter: "blur(4px)" }}
          onClick={(e) => e.target === e.currentTarget && setContactOpen(false)}
        >
          <div className="w-full max-w-md rounded-2xl border border-white/10 bg-slate-900 p-8 relative">
            <button type="button" onClick={() => setContactOpen(false)}
              className="absolute right-4 top-4 rounded-lg p-1.5 text-slate-400 hover:text-white">
              <X className="h-4 w-4" />
            </button>
            {sent ? (
              <div className="flex flex-col items-center gap-4 py-6 text-center">
                <Check className="h-8 w-8 text-emerald-400" />
                <p className="text-lg font-bold text-white">We'll be in touch shortly.</p>
                <button type="button" onClick={() => { setContactOpen(false); setSent(false); }}
                  className="rounded-lg border border-white/20 px-6 py-2 text-sm text-white">
                  Close
                </button>
              </div>
            ) : (
              <>
                <h2 className="text-xl font-bold text-white mb-1">Talk to our sales team</h2>
                <p className="text-sm text-slate-400 mb-6">Tell us about your business and we'll prepare a custom quote.</p>
                <form onSubmit={handleContact} className="space-y-3">
                  <input required type="email" value={email} onChange={(e) => setEmail(e.target.value)}
                    placeholder="Work email" className="w-full rounded-lg border border-white/10 bg-white/5 px-4 py-2.5 text-sm text-white placeholder:text-slate-500 focus:outline-none focus:border-indigo-500" />
                  <input required value={company} onChange={(e) => setCompany(e.target.value)}
                    placeholder="Company name" className="w-full rounded-lg border border-white/10 bg-white/5 px-4 py-2.5 text-sm text-white placeholder:text-slate-500 focus:outline-none focus:border-indigo-500" />
                  <button type="submit" className="w-full rounded-xl bg-gradient-to-br from-amber-500 to-amber-600 py-2.5 text-sm font-semibold text-white">
                    Contact sales
                  </button>
                </form>
              </>
            )}
          </div>
        </div>
      )}
      {/* Billing toggle */}
      <div className="mb-10 flex items-center justify-center gap-4">
        <button
          onClick={() => setBilling("monthly")}
          className={`rounded-lg px-5 py-2 text-sm font-medium transition-colors ${
            billing === "monthly"
              ? "bg-white/15 text-white"
              : "text-slate-400 hover:text-white"
          }`}
        >
          Monthly
        </button>
        <button
          onClick={() => setBilling("yearly")}
          className={`relative rounded-lg px-5 py-2 text-sm font-medium transition-colors ${
            billing === "yearly"
              ? "bg-white/15 text-white"
              : "text-slate-400 hover:text-white"
          }`}
        >
          Yearly
          <span className="absolute -top-2 -right-2 rounded-full bg-green-500 px-1.5 py-0.5 text-[10px] font-bold text-white">
            −20%
          </span>
        </button>
      </div>

      {/* Tier cards */}
      <div className="mx-auto grid max-w-5xl grid-cols-1 gap-6 sm:grid-cols-3">
        {/* Starter */}
        <div className="rounded-2xl border border-white/10 bg-white/5 p-8">
          <p className="text-xs font-semibold uppercase tracking-widest text-slate-400">Starter</p>
          <p className="mt-3 text-4xl font-extrabold text-white">{price(monthly.starter)}</p>
          <p className="mt-1 text-sm text-slate-500">per month</p>
          <Link
            href="/auth/signup?plan=starter"
            className="mt-6 block rounded-xl border border-white/20 py-2.5 text-center text-sm font-semibold text-white transition-colors hover:border-white/40"
          >
            Get started →
          </Link>

          <ul className="mt-8 space-y-3">
            {["100 products", "20 customers", "50 invoices/month", "3 seats", "1 warehouse"].map((f) => (
              <li key={f} className="flex items-center gap-2 text-sm text-slate-300">
                <Check className="h-4 w-4 shrink-0 text-slate-500" />
                {f}
              </li>
            ))}
          </ul>
        </div>

        {/* Pro — highlighted */}
        <div className={`relative rounded-2xl p-8 shadow-2xl ${highlightBg}`}>
          <div className="absolute -top-3 left-1/2 -translate-x-1/2 rounded-full bg-yellow-400 px-4 py-1 text-xs font-bold text-yellow-900">
            Most popular
          </div>
          <p className="text-xs font-semibold uppercase tracking-widest text-indigo-200">Pro</p>
          <p className="mt-3 text-4xl font-extrabold text-white">{price(monthly.pro)}</p>
          <p className="mt-1 text-sm text-indigo-200">per month</p>
          <Link
            href="/auth/signup?plan=professional"
            className="mt-6 block rounded-xl bg-white py-2.5 text-center text-sm font-semibold text-indigo-700 transition-opacity hover:opacity-90"
          >
            Get started →
          </Link>

          <ul className="mt-8 space-y-3">
            {["2,000 products", "Unlimited customers", "10 seats", "Unlimited invoices", "5 warehouses", "Fortnox integration", "B2B portal", "AI insights", "Demand forecast"].map((f) => (
              <li key={f} className="flex items-center gap-2 text-sm text-white">
                <Check className="h-4 w-4 shrink-0 text-indigo-300" />
                {f}
              </li>
            ))}
          </ul>
        </div>

        {/* Enterprise */}
        <div className="rounded-2xl border border-white/10 bg-white/5 p-8">
          <p className="text-xs font-semibold uppercase tracking-widest text-slate-400">Enterprise</p>
          <p className="mt-3 text-4xl font-extrabold text-white">Custom</p>
          <p className="mt-1 text-sm text-slate-500">pricing on request</p>
          <button
            type="button"
            onClick={() => setContactOpen(true)}
            className="mt-6 block w-full rounded-xl border border-amber-500/40 bg-amber-500/10 py-2.5 text-center text-sm font-semibold text-amber-400 transition-colors hover:bg-amber-500/20"
          >
            Contact sales
          </button>

          <ul className="mt-8 space-y-3">
            {["Everything in Pro", "Multi-entity / Franchise", "Custom integrations", "Dedicated CSM", "SLA guarantee", "ZATCA / Peppol", "Custom contract"].map((f) => (
              <li key={f} className="flex items-center gap-2 text-sm text-slate-300">
                <Check className="h-4 w-4 shrink-0 text-violet-400" />
                {f}
              </li>
            ))}
          </ul>
        </div>
      </div>

      {/* Full feature comparison table */}
      <div className="mx-auto mt-20 max-w-5xl overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-white/10">
              <th className="pb-3 text-left font-medium text-slate-400">Feature</th>
              <th className="pb-3 text-center font-medium text-slate-400">Starter</th>
              <th className="pb-3 text-center font-medium text-indigo-300">Pro</th>
              <th className="pb-3 text-center font-medium text-slate-400">Enterprise</th>
            </tr>
          </thead>
          <tbody>
            {FEATURES.map((row) => (
              <tr key={row.label} className="border-b border-white/5">
                <td className="py-3 text-slate-300">{row.label}</td>
                <td className="py-3 text-center">{renderCell(row.starter)}</td>
                <td className="py-3 text-center">{renderCell(row.pro, true)}</td>
                <td className="py-3 text-center">{renderCell(row.enterprise)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function renderCell(val: boolean | string, highlight = false) {
  if (val === true) return <Check className={`mx-auto h-4 w-4 ${highlight ? "text-indigo-400" : "text-slate-400"}`} />;
  if (val === false) return <Minus className="mx-auto h-4 w-4 text-slate-700" />;
  return <span className={highlight ? "font-medium text-indigo-300" : "text-slate-400"}>{val}</span>;
}
