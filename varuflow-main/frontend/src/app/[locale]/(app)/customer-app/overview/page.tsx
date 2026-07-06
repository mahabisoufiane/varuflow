"use client";

import { useParams } from "next/navigation";
import { Link } from "@/i18n/navigation";
import { Smartphone, CreditCard, Users, Repeat2, UserPlus, Clock } from "lucide-react";

const NAV_CARDS = [
  {
    icon: Smartphone,
    title: "App Config",
    description: "Branded mobile app settings and push notifications",
    href: (locale: string) => `/${locale}/customer-app`,
  },
  {
    icon: CreditCard,
    title: "Wallet Passes",
    description: "Issue and sync Apple/Google Wallet loyalty cards",
    href: (locale: string) => `/${locale}/customer-app/wallet`,
  },
  {
    icon: Users,
    title: "Family Accounts",
    description: "Manage family groups with shared loyalty",
    href: (locale: string) => `/${locale}/customer-app/family`,
  },
  {
    icon: Repeat2,
    title: "Recurring Bookings",
    description: "Auto-generate recurring appointments",
    href: (locale: string) => `/${locale}/customer-app/subscriptions`,
  },
  {
    icon: UserPlus,
    title: "Group Bookings",
    description: "Book for multiple people with split payment",
    href: (locale: string) => `/${locale}/customer-app/group-bookings`,
  },
  {
    icon: Clock,
    title: "Waitlist",
    description: "Automatic slot offers when cancellations open up",
    href: (locale: string) => `/${locale}/customer-app/waitlist`,
  },
];

export default function CustomerAppOverviewPage() {
  const params = useParams<{ locale: string }>();
  const locale = params?.locale ?? "en";

  return (
    <div className="mx-auto max-w-4xl space-y-6 p-6">
      <div>
        <h1 className="text-xl font-semibold text-gray-900">Customer App</h1>
        <p className="text-sm text-muted-foreground mt-0.5">
          Manage your branded mobile app, loyalty wallet passes, family accounts, and booking features.
        </p>
      </div>

      <div className="grid grid-cols-3 gap-4">
        {NAV_CARDS.map(({ icon: Icon, title, description, href }) => (
          <Link key={title} href={href(locale)}>
            <div className="rounded-xl border bg-white shadow-sm p-5 hover:shadow-md hover:border-[var(--vf-brand-primary)]/30 transition-all cursor-pointer h-full">
              <div className="flex items-center gap-3 mb-3">
                <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-[var(--vf-brand-primary)]/8 bg-gray-100">
                  <Icon className="h-5 w-5 text-[var(--vf-text-primary)]" />
                </div>
                <h3 className="text-sm font-semibold text-gray-900">{title}</h3>
              </div>
              <p className="text-xs text-muted-foreground leading-relaxed">{description}</p>
            </div>
          </Link>
        ))}
      </div>
    </div>
  );
}
