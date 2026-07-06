"use client";

import { useParams } from "next/navigation";
import { Link } from "@/i18n/navigation";
import { BookOpen, CheckSquare, Bell, ClipboardList } from "lucide-react";

const CARDS = [
  {
    key: "sop",
    icon: BookOpen,
    title: "SOP Library",
    description: "Document company procedures and processes",
    path: "sop",
  },
  {
    key: "checklists",
    icon: CheckSquare,
    title: "Checklists",
    description: "Reusable checklists for daily, weekly and monthly routines",
    path: "checklists",
  },
  {
    key: "reminders",
    icon: Bell,
    title: "Recurring Reminders",
    description: "User-defined recurring reminders and task triggers",
    path: "reminders",
  },
  {
    key: "decisions",
    icon: ClipboardList,
    title: "Decision Log",
    description: "Record significant business decisions with context and outcomes",
    path: "decisions",
  },
];

export default function OpsPage() {
  const params = useParams<{ locale: string }>();
  const locale = params?.locale ?? "en";

  return (
    <div className="mx-auto max-w-4xl space-y-6 p-6">
      <div>
        <h1 className="text-xl font-semibold text-gray-900">Operational Excellence</h1>
        <p className="text-sm text-muted-foreground mt-0.5">
          Manage your company&apos;s procedures, checklists, reminders, and key decisions.
        </p>
      </div>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        {CARDS.map(({ key, icon: Icon, title, description, path }) => (
          <Link key={key} href={`/${locale}/ops/${path}`}>
            <div className="rounded-xl border bg-white shadow-sm p-6 hover:shadow-md transition-shadow cursor-pointer group">
              <div className="flex items-start gap-4">
                <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-[var(--vf-brand-primary)]/10 group-hover:bg-[var(--vf-brand-primary)]/20 transition-colors">
                  <Icon className="h-5 w-5 text-[var(--vf-text-primary)]" />
                </div>
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-semibold text-gray-900">{title}</p>
                  <p className="text-xs text-muted-foreground mt-0.5">{description}</p>
                </div>
              </div>
            </div>
          </Link>
        ))}
      </div>
    </div>
  );
}
