"use client";

import { useParams } from "next/navigation";
import Link from "next/link";
import { Leaf, BarChart3, Award, ChevronRight } from "lucide-react";

const CARDS = [
  {
    key: "carbon",
    icon: Leaf,
    title: "Carbon Calculator",
    description: "Track Scope 1, 2, and 3 emissions and monitor your carbon footprint over time.",
    color: "text-green-500",
    bg: "bg-green-50",
  },
  {
    key: "esg",
    icon: BarChart3,
    title: "ESG Reports",
    description: "Create and publish Environmental, Social, and Governance reports for stakeholders.",
    color: "text-blue-500",
    bg: "bg-blue-50",
  },
  {
    key: "suppliers",
    icon: Award,
    title: "Supplier Ratings",
    description: "Assess and track sustainability performance scores across your supplier base.",
    color: "text-amber-500",
    bg: "bg-amber-50",
  },
];

export default function SustainabilityHubPage() {
  const params = useParams<{ locale: string }>();
  const locale = params?.locale ?? "en";

  return (
    <div className="mx-auto max-w-4xl space-y-6 p-6">
      <div>
        <h1 className="text-xl font-semibold text-gray-900">Sustainability</h1>
        <p className="text-sm text-muted-foreground mt-0.5">
          Measure your environmental impact, report ESG metrics, and rate supplier sustainability.
        </p>
      </div>

      <div className="grid gap-4 sm:grid-cols-3">
        {CARDS.map((card) => {
          const Icon = card.icon;
          return (
            <Link key={card.key} href={`/${locale}/sustainability/${card.key}`}>
              <div className="rounded-xl border bg-white shadow-sm hover:shadow-md transition-shadow cursor-pointer p-5 flex flex-col gap-3 group">
                <div className={`flex-shrink-0 rounded-lg ${card.bg} p-3 w-fit`}>
                  <Icon className={`h-5 w-5 ${card.color}`} />
                </div>
                <div className="flex-1">
                  <p className="text-sm font-semibold text-gray-900 group-hover:text-[#1a2332]">{card.title}</p>
                  <p className="text-xs text-muted-foreground mt-1 leading-relaxed">{card.description}</p>
                </div>
                <div className="flex items-center gap-1 text-xs text-[#1a2332] font-medium group-hover:underline">
                  Open <ChevronRight className="h-3.5 w-3.5" />
                </div>
              </div>
            </Link>
          );
        })}
      </div>
    </div>
  );
}
