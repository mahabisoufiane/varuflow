// File: src/components/console/ConsoleHeader.tsx
// Purpose: Region 1 of the operator console — fixed top header: mobile tree
// toggle · brand · global search · quick-create (+New) · tenant switcher ·
// notification bell · theme · user menu.
//
// Reuse: WorkspaceSwitcher (tenant switch), CommandPalette (⌘K search — we just
// dispatch the shortcut it already listens for), QUICK_ACTIONS (create menu),
// ThemeToggle, useBranding, TaskDrawerContext (bell opens the activity drawer).
// Popovers are lightweight (no @radix DropdownMenu dependency is installed).

"use client";

import { useState } from "react";
import { useLocale, useTranslations } from "next-intl";
import { usePathname, useRouter } from "@/i18n/navigation";
import {
  Menu, Search, Plus, Bell, ChevronDown, LogOut, Globe,
  FileSignature, FileText, UserPlus, PackagePlus, ClipboardList,
  type LucideIcon,
} from "lucide-react";

import { routing } from "@/i18n/routing";
import { useBranding } from "@/lib/branding";
import { cn } from "@/lib/utils";
import ThemeToggle from "@/components/ui/ThemeToggle";
import { WorkspaceSwitcher } from "@/components/app/WorkspaceSwitcher";
import { useTaskDrawer } from "@/components/console/TaskDrawerContext";

// +New targets the real create pages (labels under console.create.*). The old
// menu reused the mobile quick-actions, whose inline-sheet/scanner entries had
// no desktop host and just dumped users on /inventory.
const CREATE_ITEMS: { key: string; href: string; icon: LucideIcon }[] = [
  { key: "newQuote", href: "/quotes/new", icon: FileSignature },
  { key: "newInvoice", href: "/invoices/new", icon: FileText },
  { key: "newCustomer", href: "/customers/new", icon: UserPlus },
  { key: "newProduct", href: "/inventory/products/new", icon: PackagePlus },
  { key: "newPurchaseOrder", href: "/inventory/purchase-orders/new", icon: ClipboardList },
];

/** Opens the ⌘K CommandPalette that is already mounted in ConsoleShell. */
function openSearch() {
  document.dispatchEvent(new KeyboardEvent("keydown", { key: "k", metaKey: true, bubbles: true }));
}

export default function ConsoleHeader({
  onOpenTree,
  userLabel,
  onSignOut,
}: {
  onOpenTree: () => void;
  userLabel: string | null;
  onSignOut: () => void;
}) {
  const t = useTranslations("console");
  const locale = useLocale();
  const router = useRouter();
  const pathname = usePathname();
  const branding = useBranding();
  const { setOpen: setTasksOpen } = useTaskDrawer();

  const [createOpen, setCreateOpen] = useState(false);
  const [userOpen, setUserOpen] = useState(false);

  const avatar = (userLabel?.[0] ?? "?").toUpperCase();

  return (
    <header className="flex h-14 shrink-0 items-center gap-2 border-b bg-background px-3">
      {/* Mobile: open resource tree */}
      <button
        type="button"
        onClick={onOpenTree}
        aria-label={t("header.openTree")}
        className="grid h-9 w-9 place-items-center rounded-md hover:bg-accent lg:hidden"
      >
        <Menu className="h-5 w-5" />
      </button>

      {/* Brand */}
      <span className="mr-1 hidden truncate font-semibold text-foreground sm:inline">
        {branding.app_name}
      </span>

      {/* Global search */}
      <button
        type="button"
        onClick={openSearch}
        className="flex h-9 max-w-md flex-1 items-center gap-2 rounded-md border bg-background px-3 text-sm text-muted-foreground hover:bg-accent/40"
      >
        <Search className="h-4 w-4" />
        <span className="truncate">{t("search.placeholder")}</span>
        <kbd className="ml-auto hidden rounded border bg-muted px-1.5 text-xs sm:inline">⌘K</kbd>
      </button>

      <div className="ml-auto flex items-center gap-1.5">
        {/* Quick-create (+New) */}
        <div className="relative">
          <button
            type="button"
            onClick={() => setCreateOpen((o) => !o)}
            className="inline-flex h-9 items-center gap-1.5 rounded-md bg-[var(--vf-brand-primary,#2563eb)] px-3 text-sm font-semibold text-white hover:opacity-90"
          >
            <Plus className="h-4 w-4" />
            <span className="hidden sm:inline">{t("header.quickCreate")}</span>
          </button>
          {createOpen && (
            <>
              <div className="fixed inset-0 z-40" onClick={() => setCreateOpen(false)} />
              <div className="absolute right-0 z-50 mt-1 w-60 rounded-md border bg-background p-1 shadow-lg">
                {CREATE_ITEMS.map(({ key, href, icon: Icon }) => (
                  <button
                    key={key}
                    type="button"
                    onClick={() => {
                      setCreateOpen(false);
                      router.push(href);
                    }}
                    className="flex w-full items-center gap-2.5 rounded px-2 py-2 text-left text-sm hover:bg-accent"
                  >
                    <span className="grid h-7 w-7 place-items-center rounded-md bg-accent text-foreground">
                      <Icon className="h-4 w-4" />
                    </span>
                    {t(`create.${key}` as Parameters<typeof t>[0])}
                  </button>
                ))}
              </div>
            </>
          )}
        </div>

        {/* Tenant switcher (reused) */}
        <div className="hidden sm:block">
          <WorkspaceSwitcher />
        </div>

        {/* Notification bell → opens the activity/task drawer */}
        <button
          type="button"
          onClick={() => setTasksOpen(true)}
          aria-label={t("header.notifications")}
          className="grid h-9 w-9 place-items-center rounded-md hover:bg-accent"
        >
          <Bell className="h-4.5 w-4.5" />
        </button>

        <ThemeToggle />

        {/* User menu */}
        <div className="relative">
          <button
            type="button"
            onClick={() => setUserOpen((o) => !o)}
            aria-label={t("header.account")}
            className="flex items-center gap-1 rounded-md p-0.5 hover:bg-accent"
          >
            <span className="grid h-8 w-8 place-items-center rounded-full bg-[var(--vf-brand-primary,#2563eb)] text-sm font-semibold text-white">
              {avatar}
            </span>
            <ChevronDown className="h-3.5 w-3.5 text-muted-foreground" />
          </button>
          {userOpen && (
            <>
              <div className="fixed inset-0 z-40" onClick={() => setUserOpen(false)} />
              <div className="absolute right-0 z-50 mt-1 w-56 rounded-md border bg-background p-1 shadow-lg">
                <p className="truncate px-2 py-1.5 text-xs text-muted-foreground">{userLabel ?? "—"}</p>
                <div className="my-1 border-t" />
                <div className="flex items-center gap-1 px-2 py-1">
                  <Globe className="h-3.5 w-3.5 text-muted-foreground" />
                  {routing.locales.map((code) => (
                    <button
                      key={code}
                      type="button"
                      onClick={() => router.replace(pathname, { locale: code })}
                      className={cn(
                        "rounded px-1.5 py-0.5 text-xs uppercase",
                        locale === code ? "bg-accent font-semibold text-foreground" : "text-muted-foreground hover:bg-accent/60"
                      )}
                    >
                      {code}
                    </button>
                  ))}
                </div>
                <div className="my-1 border-t" />
                <button
                  type="button"
                  onClick={onSignOut}
                  className="flex w-full items-center gap-2 rounded px-2 py-2 text-left text-sm hover:bg-accent"
                >
                  <LogOut className="h-4 w-4" />
                  {t("header.signOut")}
                </button>
              </div>
            </>
          )}
        </div>
      </div>
    </header>
  );
}
