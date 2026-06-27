"use client";

import { useParams } from "next/navigation";
import Link from "next/link";
import { Shield, Building2, Calendar, Eye, Users, ChevronRight } from "lucide-react";

const CARDS = [
  {
    key: "risk",
    icon: Shield,
    title: "Risk Register",
    description: "Track and monitor business risks by category, likelihood, and impact score.",
    color: "text-red-500",
    bg: "bg-red-50",
  },
  {
    key: "insurance",
    icon: Building2,
    title: "Insurance Policies",
    description: "Manage insurance policies, track renewals, and log claims.",
    color: "text-blue-500",
    bg: "bg-blue-50",
  },
  {
    key: "regulatory",
    icon: Calendar,
    title: "Regulatory Calendar",
    description: "Stay on top of regulatory deadlines across Sweden, Norway, and Denmark.",
    color: "text-purple-500",
    bg: "bg-purple-50",
  },
  {
    key: "whistleblower",
    icon: Eye,
    title: "Whistleblower Reports",
    description: "Review and manage anonymous whistleblower submissions.",
    color: "text-amber-500",
    bg: "bg-amber-50",
  },
  {
    key: "conflicts",
    icon: Users,
    title: "Conflict of Interest",
    description: "Declare and review potential conflicts of interest across your organisation.",
    color: "text-green-500",
    bg: "bg-green-50",
  },
];

export default function ComplianceHubPage() {
  const params = useParams<{ locale: string }>();
  const locale = params?.locale ?? "en";

  return (
    <div className="mx-auto max-w-4xl space-y-6 p-6">
      <div>
        <h1 className="text-xl font-semibold text-gray-900">Compliance</h1>
        <p className="text-sm text-muted-foreground mt-0.5">
          Manage risks, insurance, regulatory obligations, and governance across your organisation.
        </p>
      </div>

      <div className="grid gap-4 sm:grid-cols-2">
        {CARDS.map((card) => {
          const Icon = card.icon;
          return (
            <Link key={card.key} href={`/${locale}/compliance/${card.key}`}>
              <div className="rounded-xl border bg-white shadow-sm hover:shadow-md transition-shadow cursor-pointer p-5 flex items-start gap-4 group">
                <div className={`flex-shrink-0 rounded-lg ${card.bg} p-3`}>
                  <Icon className={`h-5 w-5 ${card.color}`} />
                </div>
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-semibold text-gray-900 group-hover:text-[#1a2332]">{card.title}</p>
                  <p className="text-xs text-muted-foreground mt-0.5 leading-relaxed">{card.description}</p>
                </div>
                <ChevronRight className="h-4 w-4 text-muted-foreground flex-shrink-0 mt-0.5 group-hover:text-gray-700" />
              </div>
            </Link>
          );
        })}
      </div>
    </div>
  );
}
