"use client";

// File: src/components/MobileBottomNav.tsx
// Purpose: Sticky 5-tab bottom nav for mobile (< 768 px). The 5th tab,
// "Mer" (More), opens a slide-up drawer listing the remaining app
// sections (Analytics, Customers, AI, Settings, Recurring, GDPR, Audit).
//
// - Hidden at ≥ 768 px via `md:hidden`
// - Hidden on /pos, /onboarding/*, /auth/* via `isNavHidden(pathname)`
// - z-30 — below the FAB (z-50) and its sheet (z-50) so quick actions
//   always float above the nav.
// - Exposes its rendered height via `[data-mobile-bottom-nav]` so
//   `useBottomNavHeight` can publish `--bottom-nav-height`.
// - Uses `env(safe-area-inset-bottom)` padding for iPhone home bar.

import { useEffect, useState } from "react";
import { usePathname, useRouter } from "next/navigation";
import { useTranslations, useLocale } from "next-intl";
import {
  Home, Package, FileText, ShoppingCart, MoreHorizontal,
  BarChart3, Users, Bot, Settings, RefreshCw, ShieldCheck, FileSearch,
  type LucideIcon,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { isNavHidden } from "@/lib/quick-actions";
import { useBottomNavHeight } from "@/hooks/useBottomNavHeight";

type TabId = "home" | "inventory" | "invoices" | "pos" | "more";

interface Tab {
  id: TabId;
  icon: LucideIcon;
  labelKey: string;
  href?: string;
}

const TABS: Tab[] = [
  { id: "home",      icon: Home,            labelKey: "dashboard.nav_home",      href: "/dashboard" },
  { id: "inventory", icon: Package,         labelKey: "dashboard.nav_inventory", href: "/inventory" },
  { id: "invoices",  icon: FileText,        labelKey: "dashboard.nav_invoices",  href: "/invoices"  },
  { id: "pos",       icon: ShoppingCart,    labelKey: "dashboard.nav_pos",       href: "/pos"       },
  { id: "more",      icon: MoreHorizontal,  labelKey: "dashboard.nav_more" },
];

interface MoreItem { href: string; icon: LucideIcon; label: string; }

const MORE_ITEMS: MoreItem[] = [
  { href: "/analytics", icon: BarChart3,    label: "Analytics" },
  { href: "/customers", icon: Users,        label: "Customers" },
  { href: "/ai",        icon: Bot,          label: "AI"        },
  { href: "/settings",  icon: Settings,     label: "Settings"  },
  { href: "/recurring", icon: RefreshCw,    label: "Recurring" },
  { href: "/settings/gdpr",  icon: ShieldCheck, label: "GDPR"  },
  { href: "/settings/audit", icon: FileSearch, label: "Audit"  },
];

function getActive(pathname: string): TabId {
  const stripped = pathname.replace(/^\/[a-z]{2}(?=\/|$)/i, "") || "/";
  if (stripped === "/dashboard") return "home";
  if (stripped.startsWith("/inventory")) return "inventory";
  if (stripped.startsWith("/invoices") || stripped.startsWith("/customers") || stripped.startsWith("/recurring")) return "invoices";
  if (stripped.startsWith("/pos")) return "pos";
  return "more";
}

export default function MobileBottomNav() {
  const t = useTranslations();
  const locale = useLocale();
  const router = useRouter();
  const pathname = usePathname() ?? "/";
  useBottomNavHeight();

  const [moreOpen, setMoreOpen] = useState(false);

  // Auto-close the drawer when the route changes.
  useEffect(() => { setMoreOpen(false); }, [pathname]);

  // Escape closes the More drawer.
  useEffect(() => {
    if (!moreOpen) return;
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") { e.preventDefault(); setMoreOpen(false); }
    }
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [moreOpen]);

  if (isNavHidden(pathname)) return null;

  const active = getActive(pathname);
  const hasMoreIndicator = active === "more";

  function tap(tab: Tab) {
    if (tab.id === "more") { setMoreOpen(true); return; }
    if (tab.href) router.push(`/${locale}${tab.href}`);
  }

  return (
    <>
      <nav
        data-mobile-bottom-nav
        data-testid="mobile-bottom-nav"
        role="navigation"
        aria-label={t("dashboard.nav_more")}
        className="fixed bottom-0 left-0 right-0 z-30 flex border-t border-gray-200 bg-white shadow-[0_-4px_10px_-4px_rgba(0,0,0,0.08)] md:hidden dark:border-white/10 dark:bg-gray-900"
        style={{ paddingBottom: "env(safe-area-inset-bottom)" }}
      >
        {TABS.map((tab) => {
          const Icon = tab.icon;
          const isActive = tab.id === active;
          return (
            <button
              key={tab.id}
              type="button"
              onClick={() => tap(tab)}
              data-testid={`nav-${tab.id}`}
              data-active={isActive ? "true" : "false"}
              className={cn(
                "relative flex min-h-[44px] flex-1 flex-col items-center justify-center gap-0.5 py-2 text-[11px] font-medium transition-transform active:scale-[0.92]",
                isActive ? "text-emerald-700" : "text-gray-500",
              )}
              style={isActive ? { color: "#2d6a4f" } : undefined}
            >
              {isActive && tab.id !== "more" && (
                <span className="absolute top-1 h-1 w-1 rounded-full bg-emerald-700" style={{ backgroundColor: "#2d6a4f" }} />
              )}
              {tab.id === "more" && hasMoreIndicator && (
                <span className="absolute top-1 h-1 w-1 rounded-full bg-emerald-700" style={{ backgroundColor: "#2d6a4f" }} />
              )}
              <Icon className="h-6 w-6" />
              <span>{t(tab.labelKey as Parameters<typeof t>[0])}</span>
            </button>
          );
        })}
      </nav>

      {moreOpen && (
        <>
          <div
            data-testid="nav-more-backdrop"
            className="fixed inset-0 z-40 bg-black/40 md:hidden"
            onClick={() => setMoreOpen(false)}
            aria-hidden="true"
          />
          <div
            data-testid="nav-more-drawer"
            role="dialog"
            aria-modal="true"
            className="fixed inset-x-0 bottom-0 z-40 max-h-[75vh] animate-[navSlideUp_250ms_ease-out] overflow-hidden rounded-t-2xl bg-white pb-[env(safe-area-inset-bottom)] shadow-2xl md:hidden dark:bg-gray-900"
          >
            <div className="flex justify-center py-3">
              <span className="h-1 w-8 rounded-full bg-gray-300" />
            </div>
            <ul className="divide-y divide-gray-100 px-2 pb-4 dark:divide-white/5">
              {MORE_ITEMS.map((m) => {
                const Icon = m.icon;
                return (
                  <li key={m.href}>
                    <button
                      type="button"
                      onClick={() => { setMoreOpen(false); router.push(`/${locale}${m.href}`); }}
                      className="flex w-full min-h-[56px] items-center gap-3 rounded-lg px-3 py-3 text-left hover:bg-gray-50 dark:hover:bg-white/5"
                    >
                      <span className="flex h-10 w-10 items-center justify-center rounded-xl bg-gray-100 text-gray-700 dark:bg-white/10 dark:text-gray-200">
                        <Icon className="h-5 w-5" />
                      </span>
                      <span className="text-sm font-medium">{m.label}</span>
                    </button>
                  </li>
                );
              })}
            </ul>
          </div>
          <style jsx global>{`
            @keyframes navSlideUp {
              from { transform: translateY(100%); }
              to   { transform: translateY(0);    }
            }
          `}</style>
        </>
      )}
    </>
  );
}
