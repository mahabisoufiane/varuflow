"use client";

import { useParams } from "next/navigation";
import { Link } from "@/i18n/navigation";
import { Target, GitBranch, Layout, Radio, Star } from "lucide-react";

const CARDS = [
  {
    icon: Target,
    title: "Attribution",
    description: "Track which channels bring the highest LTV customers",
    href: "marketing/attribution",
  },
  {
    icon: GitBranch,
    title: "A/B Testing",
    description: "Test campaign variants and auto-promote winners",
    href: "marketing/ab-testing",
  },
  {
    icon: Layout,
    title: "Landing Pages",
    description: "Campaign-specific landing pages with lead capture",
    href: "marketing/landing-pages",
  },
  {
    icon: Radio,
    title: "Broadcasts",
    description: "SMS and WhatsApp promotional campaigns to opted-in segments",
    href: "marketing/broadcasts",
  },
  {
    icon: Star,
    title: "Surveys",
    description: "Net Promoter Score surveys with trend tracking",
    href: "marketing/surveys",
  },
];

export default function MarketingPage() {
  const params = useParams<{ locale: string }>();
  const locale = params?.locale ?? "en";

  return (
    <div className="mx-auto max-w-4xl space-y-6 p-6">
      <div>
        <h1 className="text-xl font-semibold text-gray-900">Marketing Insights</h1>
        <p className="text-sm text-muted-foreground mt-0.5">
          Manage attribution, A/B tests, landing pages, broadcasts, and customer surveys.
        </p>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        {CARDS.map(({ icon: Icon, title, description, href }) => (
          <Link key={href} href={`/${locale}/${href}`}>
            <div className="rounded-xl border bg-white shadow-sm p-5 hover:shadow-md transition-shadow cursor-pointer flex items-start gap-4">
              <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-[var(--vf-brand-primary)]/10">
                <Icon className="h-5 w-5 text-[var(--vf-text-primary)]" />
              </div>
              <div>
                <p className="text-sm font-semibold text-gray-900">{title}</p>
                <p className="text-xs text-muted-foreground mt-0.5">{description}</p>
              </div>
            </div>
          </Link>
        ))}
      </div>
    </div>
  );
}
