"use client";

import { Link } from "@/i18n/navigation";
import { Users, FlaskConical, Globe, TrendingDown, ArrowUpRight } from "lucide-react";

const MODULES = [
  {
    href: "/growth/partners",
    icon: Users,
    title: "Partner Program",
    desc: "Manage B2B affiliate partners, track deals and commissions.",
    color: "blue",
  },
  {
    href: "/growth/experiments",
    icon: FlaskConical,
    title: "Pricing Experiments",
    desc: "A/B test invoice price changes on customer cohorts.",
    color: "purple",
  },
  {
    href: "/growth/expansion",
    icon: Globe,
    title: "Market Expansion",
    desc: "Per-country launch checklists for legal, financial and ops readiness.",
    color: "green",
  },
  {
    href: "/growth/churn",
    icon: TrendingDown,
    title: "Churn Dashboard",
    desc: "See which customers left, why, and who is at risk next.",
    color: "red",
  },
];

export default function GrowthPage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold text-gray-900">Growth</h1>
        <p className="mt-1 text-sm text-gray-500">Tools for expanding revenue, retaining customers and entering new markets.</p>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        {MODULES.map(m => (
          <Link
            key={m.href}
            href={m.href}
            className="group rounded-xl border border-gray-200 bg-white p-5 hover:border-blue-300 hover:shadow-sm transition-all flex items-start gap-4"
          >
            <div className={`p-2.5 rounded-xl bg-${m.color}-50 group-hover:bg-${m.color}-100 transition-colors flex-shrink-0`}>
              <m.icon className={`h-5 w-5 text-${m.color}-600`} />
            </div>
            <div className="min-w-0">
              <div className="flex items-center gap-1.5">
                <p className="font-semibold text-gray-900 group-hover:text-blue-700">{m.title}</p>
                <ArrowUpRight className="h-3.5 w-3.5 text-gray-400 group-hover:text-blue-500 transition-colors" />
              </div>
              <p className="text-sm text-gray-500 mt-0.5">{m.desc}</p>
            </div>
          </Link>
        ))}
      </div>
    </div>
  );
}
