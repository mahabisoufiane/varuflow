"use client";

import { Link } from "@/i18n/navigation";
import { ClipboardCheck, BookOpen, FileSignature, ShieldCheck, ArrowUpRight } from "lucide-react";
import { useState, useEffect } from "react";

const MODULES = [
  { href: "/governance/approvals", icon: ClipboardCheck, title: "Approval Queue", desc: "Invoice and expense thresholds — review items awaiting CEO/owner sign-off.", color: "blue" },
  { href: "/governance/policies",  icon: BookOpen,       title: "Company Policies", desc: "Publish HR, finance and legal policies visible to all staff in-app.", color: "green" },
  { href: "/governance/sign-contract", icon: FileSignature, title: "Sign Contracts", desc: "Add a legally-binding electronic signature to any stored contract.", color: "purple" },
];

export default function GovernancePage() {
  const apiBase = process.env.NEXT_PUBLIC_API_URL!;
  const [pending, setPending] = useState<number | null>(null);

  useEffect(() => {
    fetch(`${apiBase}/api/governance/approvals/summary`, { credentials: "include" })
      .then(r => r.ok ? r.json() : null)
      .then(d => d && setPending(d.pending));
  }, []);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold text-gray-900">Governance</h1>
        <p className="mt-1 text-sm text-gray-500">Controls, approvals, policies and digital signatures for your organisation.</p>
      </div>

      {pending !== null && pending > 0 && (
        <div className="rounded-xl border border-amber-300 bg-amber-50 p-4 flex items-center gap-3">
          <ClipboardCheck className="h-5 w-5 text-amber-600 flex-shrink-0" />
          <div>
            <p className="font-semibold text-amber-800">{pending} item{pending > 1 ? "s" : ""} awaiting approval</p>
            <p className="text-sm text-amber-700">Review pending invoices and expenses that exceed spending thresholds.</p>
          </div>
          <Link href="/governance/approvals" className="ml-auto text-sm font-medium text-amber-700 hover:underline flex-shrink-0">Review →</Link>
        </div>
      )}

      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        {MODULES.map(m => (
          <Link key={m.href} href={m.href}
            className="group rounded-xl border border-gray-200 bg-white p-5 hover:border-blue-300 hover:shadow-sm transition-all flex items-start gap-4">
            <div className={`p-2.5 rounded-xl bg-${m.color}-50 group-hover:bg-${m.color}-100 transition-colors flex-shrink-0`}>
              <m.icon className={`h-5 w-5 text-${m.color}-600`} />
            </div>
            <div className="min-w-0">
              <div className="flex items-center gap-1.5">
                <p className="font-semibold text-gray-900 group-hover:text-blue-700">{m.title}</p>
                {m.href === "/governance/approvals" && pending !== null && pending > 0 && (
                  <span className="text-xs bg-red-500 text-white px-1.5 py-0.5 rounded-full">{pending}</span>
                )}
                <ArrowUpRight className="h-3.5 w-3.5 text-gray-400 group-hover:text-blue-500" />
              </div>
              <p className="text-sm text-gray-500 mt-0.5">{m.desc}</p>
            </div>
          </Link>
        ))}
      </div>

      <div className="rounded-xl border border-gray-200 bg-gray-50 p-5 space-y-2 text-sm text-gray-600">
        <p className="flex items-center gap-2 font-semibold text-gray-700">
          <ShieldCheck className="h-4 w-4 text-blue-500" /> What governance controls are active
        </p>
        <p>• Approval rules: configure monetary thresholds that trigger CEO/owner sign-off on invoices and expenses</p>
        <p>• Spending limits per role: automatically flag expenses submitted by non-owners that exceed the configured limit</p>
        <p>• Digital contract signatures: Simple Electronic Signature (SES) under EU eIDAS — tamper-evident SHA-256 hash stored with each signature</p>
        <p>• Policy library: publish company documents so every staff member can read HR, finance and legal policies from within the app</p>
      </div>
    </div>
  );
}
