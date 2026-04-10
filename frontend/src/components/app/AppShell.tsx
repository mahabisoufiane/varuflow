"use client";

import { createClient, isSupabaseConfigured } from "@/lib/supabase/client";
import { api } from "@/lib/api-client";
import { cn } from "@/lib/utils";
import { Link, usePathname, useRouter } from "@/i18n/navigation";
import { useLocale, useTranslations } from "next-intl";
import { useEffect, useState } from "react";
import { toast } from "sonner";
import {
  BarChart3, Bot, FileText, LayoutDashboard, LogOut,
  Package, RefreshCw, Search, Settings, ShoppingCart, Users, Zap,
  Menu, X, Home,
} from "lucide-react";
import dynamic from "next/dynamic";

const AiChat         = dynamic(() => import("@/components/app/AiChat"),         { ssr: false });
const CommandPalette = dynamic(() => import("@/components/app/CommandPalette"), { ssr: false });
const PwaInstallBanner = dynamic(() => import("@/components/app/PwaInstallBanner"), { ssr: false });

/* ── Nav groups ─────────────────────────────────────────────────────────────── */
const NAV_GROUPS = [
  {
    label: "Overview",
    items: [
      { href: "/dashboard", icon: LayoutDashboard, key: "dashboard" },
      { href: "/analytics", icon: BarChart3,        key: "analytics" },
    ],
  },
  {
    label: "Operations",
    items: [
      { href: "/inventory", icon: Package,      key: "inventory"    },
      { href: "/invoices",  icon: FileText,     key: "invoices"     },
      { href: "/recurring", icon: RefreshCw,    key: "recurring"    },
      { href: "/pos",       icon: ShoppingCart, key: "cashRegister" },
      { href: "/customers", icon: Users,        key: "customers"    },
    ],
  },
  {
    label: "Intelligence",
    items: [
      { href: "/ai", icon: Bot, key: "aiAdvisor" },
    ],
  },
  {
    label: "Settings",
    items: [
      { href: "/settings", icon: Settings, key: "settings" },
    ],
  },
] as const;

/* Mobile bottom nav — 5 key items */
const MOBILE_NAV = [
  { href: "/dashboard", icon: Home,      label: "Home"      },
  { href: "/inventory", icon: Package,   label: "Inventory" },
  { href: "/invoices",  icon: FileText,  label: "Invoices"  },
  { href: "/ai",        icon: Bot,       label: "AI"        },
  { href: "/settings",  icon: Settings,  label: "More"      },
] as const;

const LOCALES = [
  { code: "sv", label: "SV" },
  { code: "en", label: "EN" },
] as const;

/* Page title derived from pathname for the desktop topbar */
const PAGE_TITLE_MAP: Record<string, string> = {
  "/dashboard": "Dashboard",
  "/inventory": "Inventory",
  "/invoices":  "Invoices",
  "/recurring": "Recurring",
  "/pos":       "Cash Register",
  "/customers": "Customers",
  "/analytics": "Analytics",
  "/ai":        "AI Advisor",
  "/settings":  "Settings",
};

function getPageTitle(pathname: string): string {
  for (const [path, title] of Object.entries(PAGE_TITLE_MAP)) {
    if (pathname === path || pathname.startsWith(path + "/")) return title;
  }
  return "Varuflow";
}

/* ── Component ──────────────────────────────────────────────────────────────── */
export default function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const router   = useRouter();
  const locale   = useLocale();
  const t        = useTranslations("nav");
  const supabase = createClient();

  const [isClient,         setIsClient]         = useState(false);
  const [email,            setEmail]            = useState<string | null>(null);
  const [fortnoxConnected, setFortnoxConnected] = useState(false);
  const [openaiConnected,  setOpenaiConnected]  = useState(false);
  const [sidebarOpen,      setSidebarOpen]      = useState(false);

  useEffect(() => {
    setIsClient(true);
    if (isSupabaseConfigured) {
      supabase.auth.getUser().then(({ data }) => {
        const userEmail = data.user?.email ?? null;
        setEmail(userEmail);
        if (userEmail && process.env.NEXT_PUBLIC_CRISP_WEBSITE_ID && typeof window !== "undefined") {
          const w = window as unknown as Record<string, unknown>;
          if (w.$crisp) (w.$crisp as unknown[][]).push(["set", "user:email", userEmail]);
        }
      });
    }
    api.get<{ connected: boolean }>("/api/integrations/fortnox/status")
      .then((s) => setFortnoxConnected(s.connected))
      .catch(() => {});
    api.get<{ openai_configured: boolean }>("/api/integrations/config")
      .then((s) => setOpenaiConnected(s.openai_configured))
      .catch(() => {});
  }, []);

  function isActive(href: string) {
    if (!isClient) return false;
    if (href === "/dashboard") return pathname === "/dashboard";
    return pathname === href || pathname.startsWith(href + "/");
  }

  async function handleSignOut() {
    await supabase.auth.signOut();
    toast.success("Signed out");
    router.push("/auth/login");
  }

  function openSearch() {
    document.dispatchEvent(
      new KeyboardEvent("keydown", { key: "k", metaKey: true, bubbles: true })
    );
  }

  const avatarLetter = isClient && email ? email[0].toUpperCase() : "?";

  /* ── Sidebar ───────────────────────────────────────────────────────────── */
  const SidebarContent = () => (
    <>
      {/* Logo */}
      <div className="flex h-[57px] shrink-0 items-center gap-3 border-b border-white/[0.07] px-5">
        <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-gradient-to-br from-indigo-500 to-violet-600 shadow-glow shrink-0">
          <Zap className="h-3.5 w-3.5 text-white" />
        </div>
        <span className="bg-gradient-to-r from-indigo-400 to-violet-400 bg-clip-text text-transparent text-[15px] font-bold tracking-tight flex-1 min-w-0">
          Varuflow
        </span>
        {isClient && fortnoxConnected && (
          <span className="shrink-0 rounded-full bg-emerald-500/15 border border-emerald-500/20 px-1.5 py-0.5 text-[9px] font-bold text-emerald-400 tracking-wide">
            FX
          </span>
        )}
        <button
          className="lg:hidden ml-1 text-slate-600 hover:text-slate-300 transition-colors"
          onClick={() => setSidebarOpen(false)}
        >
          <X className="h-4 w-4" />
        </button>
      </div>

      {/* Nav groups */}
      <nav className="flex flex-1 flex-col gap-1 overflow-y-auto px-2 py-3">
        {NAV_GROUPS.map((group, gi) => (
          <div key={group.label} className={cn(gi > 0 && "mt-3")}>
            <p className="mb-0.5 px-3 text-[10px] font-medium text-slate-700 select-none">
              {group.label}
            </p>
            <div className="flex flex-col gap-[1px]">
              {group.items.map(({ href, icon: Icon, key }) => {
                const active = isActive(href);
                return (
                  <Link
                    key={href}
                    href={href}
                    onClick={() => setSidebarOpen(false)}
                    className={cn(
                      "group relative flex items-center gap-2.5 rounded-lg px-3 py-[7px] text-[13px] font-medium transition-all duration-100",
                      active
                        ? "bg-indigo-500/[0.12] text-indigo-300"
                        : "text-slate-500 hover:bg-white/[0.05] hover:text-slate-200"
                    )}
                  >
                    {active && (
                      <span className="absolute left-0 top-1/2 -translate-y-1/2 h-4 w-0.5 rounded-r-full bg-indigo-400" />
                    )}
                    <Icon className={cn(
                      "h-[15px] w-[15px] shrink-0 transition-colors",
                      active ? "text-indigo-400" : "text-slate-600 group-hover:text-slate-400"
                    )} />
                    {t(key as Parameters<typeof t>[0])}
                  </Link>
                );
              })}
            </div>
          </div>
        ))}
      </nav>

      {/* Bottom: AI indicator + locale + sign out */}
      <div className="shrink-0 border-t border-white/[0.07] px-2 py-3 space-y-1">
        {/* AI indicator */}
        {isClient && (
          <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg">
            <span className={cn(
              "h-1.5 w-1.5 rounded-full shrink-0",
              openaiConnected ? "bg-emerald-400 animate-pulse-dot" : "bg-slate-700"
            )} />
            <span className="text-[11px] text-slate-600">
              AI {openaiConnected ? "connected" : "not configured"}
            </span>
          </div>
        )}

        {/* Locale switcher */}
        <div className="flex gap-[2px] px-1">
          {LOCALES.map(({ code, label }) => (
            <button
              key={code}
              onClick={() => router.replace(pathname, { locale: code })}
              className={cn(
                "flex-1 rounded-md py-1.5 text-[10px] font-bold tracking-wider transition-colors",
                isClient && locale === code
                  ? "bg-white/[0.08] text-slate-300"
                  : "text-slate-700 hover:bg-white/[0.04] hover:text-slate-500"
              )}
            >
              {label}
            </button>
          ))}
        </div>

        {/* Sign out */}
        <button
          onClick={handleSignOut}
          className="flex w-full items-center gap-2.5 rounded-lg px-3 py-2 transition-colors hover:bg-white/[0.05] group"
        >
          <div className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-gradient-to-br from-indigo-600 to-violet-700 text-[10px] font-bold text-white">
            {avatarLetter}
          </div>
          <div className="flex-1 min-w-0 text-left">
            <p className="truncate text-[12px] font-medium text-slate-500 group-hover:text-slate-300 transition-colors">
              {isClient ? (email ?? "Account") : "Account"}
            </p>
            <p className="text-[10px] text-slate-700">Free plan</p>
          </div>
          <LogOut className="h-3 w-3 shrink-0 text-slate-700 group-hover:text-slate-500 transition-colors" />
        </button>
      </div>
    </>
  );

  /* ── Layout ────────────────────────────────────────────────────────────── */
  return (
    <>
      {process.env.NEXT_PUBLIC_CRISP_WEBSITE_ID && (
        <script
          dangerouslySetInnerHTML={{
            __html: `
              window.$crisp=[];window.CRISP_WEBSITE_ID="${process.env.NEXT_PUBLIC_CRISP_WEBSITE_ID}";
              (function(){var d=document;var s=d.createElement("script");
              s.src="https://client.crisp.chat/l.js";s.async=1;d.getElementsByTagName("head")[0].appendChild(s);})();
            `,
          }}
        />
      )}

      <div className="flex min-h-screen bg-vf-base">

        {/* Mobile overlay */}
        {sidebarOpen && (
          <div
            className="fixed inset-0 z-30 bg-black/60 backdrop-blur-sm lg:hidden"
            onClick={() => setSidebarOpen(false)}
          />
        )}

        {/* Sidebar */}
        <aside className={cn(
          "fixed inset-y-0 left-0 z-40 flex w-[220px] shrink-0 flex-col border-r border-white/[0.07] bg-[#090C12] transition-transform duration-200 lg:static lg:translate-x-0",
          sidebarOpen ? "translate-x-0" : "-translate-x-full"
        )}>
          <SidebarContent />
        </aside>

        {/* Main column */}
        <div className="flex flex-1 min-w-0 flex-col">

          {/* Mobile top bar */}
          <header className="flex h-14 shrink-0 items-center gap-3 border-b border-white/[0.07] px-4 lg:hidden">
            <button
              onClick={() => setSidebarOpen(true)}
              className="text-slate-500 hover:text-slate-300 transition-colors"
            >
              <Menu className="h-5 w-5" />
            </button>
            <span className="bg-gradient-to-r from-indigo-400 to-violet-400 bg-clip-text text-transparent text-[15px] font-bold tracking-tight">
              Varuflow
            </span>
          </header>

          {/* Desktop topbar */}
          <header className="hidden lg:flex h-[57px] shrink-0 items-center justify-between gap-4 border-b border-white/[0.07] px-6">
            <h1 className="text-[13px] font-semibold text-slate-300 tracking-tight">
              {getPageTitle(pathname)}
            </h1>
            <div className="flex items-center gap-2">
              {/* ⌘K trigger */}
              <button
                onClick={openSearch}
                className="flex items-center gap-2 rounded-lg border border-white/[0.08] bg-white/[0.03] px-3 py-[7px] text-xs text-slate-500 hover:bg-white/[0.06] hover:text-slate-300 transition-colors"
              >
                <Search className="h-3.5 w-3.5" />
                <span className="hidden xl:inline">Search</span>
                <kbd className="hidden xl:inline-block rounded bg-white/[0.06] border border-white/[0.08] px-1.5 py-0.5 text-[10px] text-slate-600 font-mono">
                  ⌘K
                </kbd>
              </button>
              {/* Avatar */}
              <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-gradient-to-br from-indigo-600 to-violet-700 text-[11px] font-bold text-white select-none">
                {avatarLetter}
              </div>
            </div>
          </header>

          {/* Page content */}
          <main className="flex-1 min-w-0 overflow-auto">
            <div className="mx-auto max-w-6xl px-4 sm:px-6 py-6 page-enter">
              {children}
            </div>
          </main>

          {/* Mobile bottom nav */}
          <nav className="lg:hidden flex border-t border-white/[0.07] bg-[#090C12] pb-safe">
            {MOBILE_NAV.map(({ href, icon: Icon, label }) => {
              const active = isActive(href);
              return (
                <Link
                  key={href}
                  href={href}
                  className={cn(
                    "flex flex-1 flex-col items-center gap-1 py-3 text-[10px] font-medium transition-colors",
                    active ? "text-indigo-400" : "text-slate-600 hover:text-slate-400"
                  )}
                >
                  <Icon className="h-5 w-5" />
                  {label}
                </Link>
              );
            })}
          </nav>
        </div>
      </div>

      <CommandPalette />
      <AiChat />
      <PwaInstallBanner />
    </>
  );
}
