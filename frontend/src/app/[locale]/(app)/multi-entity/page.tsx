"use client";

import { useLocale } from "next-intl";
import { Building2, BarChart3, ArrowLeftRight, GitBranch } from "lucide-react";

const FEATURES = [
  {
    icon: <Building2 className="h-8 w-8" />,
    title: "Subsidiaries",
    description: "Manage your group structure — create subsidiary orgs, set legal names, and assign reporting currencies.",
    href: "multi-entity/subsidiaries",
    color: "bg-blue-50 text-blue-600",
  },
  {
    icon: <BarChart3 className="h-8 w-8" />,
    title: "Consolidated Reports",
    description: "View group P&L across all entities with automatic intercompany eliminations.",
    href: "multi-entity/consolidated",
    color: "bg-green-50 text-green-600",
  },
  {
    icon: <ArrowLeftRight className="h-8 w-8" />,
    title: "Intercompany Transfers",
    description: "Record stock, cash, and service transfers between entities at arm's-length transfer prices.",
    href: "multi-entity/intercompany",
    color: "bg-purple-50 text-purple-600",
  },
  {
    icon: <GitBranch className="h-8 w-8" />,
    title: "Franchise",
    description: "Onboard franchisees, run royalty billing, and push your product catalogue across the network.",
    href: "franchise",
    color: "bg-amber-50 text-amber-600",
  },
];

export default function MultiEntityHubPage() {
  const locale = useLocale();

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-semibold text-gray-900">Multi-Entity & Franchise</h1>
        <p className="mt-1 text-sm text-gray-500">
          Manage subsidiary branches, consolidated group reporting, intercompany accounting, and franchise networks.
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
