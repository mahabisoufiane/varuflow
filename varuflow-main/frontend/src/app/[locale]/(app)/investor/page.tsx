"use client";

import { useParams } from "next/navigation";
import Link from "next/link";
import { TrendingUp, PieChart, FileText, FolderLock } from "lucide-react";

const CARDS = [
  {
    icon: TrendingUp,
    title: "Investor Updates",
    description: "Monthly investor updates with revenue snapshots",
    href: "investor/updates",
  },
  {
    icon: PieChart,
    title: "Cap Table",
    description: "Shareholders, share classes, and dilution scenarios",
    href: "investor/cap-table",
  },
  {
    icon: FileText,
    title: "Board Packs",
    description: "Board meeting packs with auto-populated financials",
    href: "investor/board-packs",
  },
  {
    icon: FolderLock,
    title: "Data Room",
    description: "Secure document sharing for fundraising and M&A",
    href: "investor/data-room",
  },
];

export default function InvestorPage() {
  const params = useParams<{ locale: string }>();
  const locale = params?.locale ?? "en";

  return (
    <div className="mx-auto max-w-4xl space-y-6 p-6">
      <div>
        <h1 className="text-xl font-semibold text-gray-900">Investor &amp; Board</h1>
        <p className="text-sm text-muted-foreground mt-0.5">
          Manage investor relations, cap table, board packs, and secure data rooms.
        </p>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        {CARDS.map(({ icon: Icon, title, description, href }) => (
          <Link key={href} href={`/${locale}/${href}`}>
            <div className="rounded-xl border bg-white shadow-sm p-5 hover:shadow-md transition-shadow cursor-pointer flex items-start gap-4">
              <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-[#1a2332]/10">
                <Icon className="h-5 w-5 text-[#1a2332]" />
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
