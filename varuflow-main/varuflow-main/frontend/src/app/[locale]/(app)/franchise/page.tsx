"use client";

import { useLocale } from "next-intl";
import { Users, Receipt, Package, GitBranch } from "lucide-react";

const FEATURES = [
  {
    icon: <Users className="h-8 w-8" />,
    title: "Franchisee Onboarding",
    description: "Register new franchisees, set royalty rates and billing cycle. Approve and activate agreements.",
    href: "franchise/onboarding",
    color: "bg-blue-50 text-blue-600",
  },
  {
    icon: <Receipt className="h-8 w-8" />,
    title: "Royalty Billing",
    description: "Calculate, issue, and track royalty invoices for each franchisee by period.",
    href: "franchise/royalties",
    color: "bg-green-50 text-green-600",
  },
  {
    icon: <Package className="h-8 w-8" />,
    title: "Franchise Catalogue",
    description: "Push your master product catalogue to franchisee organisations in one click.",
    href: "franchise/catalog",
    color: "bg-purple-50 text-purple-600",
  },
  {
    icon: <GitBranch className="h-8 w-8" />,
    title: "Multi-Entity",
    description: "Manage subsidiaries and consolidated group reporting.",
    href: "multi-entity",
    color: "bg-amber-50 text-amber-600",
  },
];

export default function FranchiseHubPage() {
  const locale = useLocale();

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-semibold text-gray-900">Franchise Management</h1>
        <p className="mt-1 text-sm text-gray-500">
          Onboard franchisees, run royalty billing, and push your product catalogue across the network.
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
