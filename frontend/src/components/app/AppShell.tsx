"use client";

import { createClient, isSupabaseConfigured } from "@/lib/supabase/client";
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
import ThemeToggle from "@/components/ui/ThemeToggle";
import { useCapabilities } from "@/hooks/useCapabilities";

const AiChat              = dynamic(() => import("@/components/app/AiChat"),              { ssr: false });
const CommandPalette      = dynamic(() => import("@/components/app/CommandPalette"),      { ssr: false });
const PwaInstallBanner    = dynamic(() => import("@/components/app/PwaInstallBanner"),    { ssr: false });
const SessionTimeoutModal = dynamic(() => import("@/components/app/SessionTimeoutModal"), { ssr: false });
const CountryPicker       = dynamic(() => import("@/components/app/CountryPicker"),       { ssr: false });

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

/* Mobile bottom nav */
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

  const [isClient,    setIsClient]    = useState(false);
  const [email,       setEmail]       = useState<string | null>(null);
  const [sidebarOpen, setSidebarOpen] = useState(false);

  // Unified capability probe — tells us which integrations are active so
  // we can hide disabled flows instead of showing broken buttons.
  const caps = useCapabilities();
  const fortnoxConnected = caps?.fortnox_configured ?? false;
  const openaiConnected  = caps?.ai_chat_available  ?? false;

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

  /* ── Sidebar content ────────────────────────────────────────────────────── */
  const SidebarContent = () => (
    <>
      {/* Logo */}
      <div className="flex h-[57px] shrink-0 items-center gap-3 px-5"
        style={{ borderBottom: "1px solid var(--vf-border)" }}>
        <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-gradient-to-br from-indigo-500 to-violet-600 shadow-glow shrink-0">
          <Zap className="h-3.5 w-3.5 text-white" />
        </div>
        <span className="bg-gradient-to-r from-indigo-500 to-violet-500 bg-clip-text text-transparent text-[15px] font-bold tracking-tight flex-1 min-w-0">
          Varuflow
        </span>
        {isClient && fortnoxConnected && (
          <span className="shrink-0 rounded-full bg-emerald-500/15 border border-emerald-500/25 px-1.5 py-0.5 text-[9px] font-bold text-emerald-500 tracking-wide">
            FX
          </span>
        )}
        <button
          className="lg:hidden ml-1 vf-text-m hover:vf-text-1 transition-colors"
          onClick={() => setSidebarOpen(false)}
        >
          <X className="h-4 w-4" />
        </button>
      </div>

      {/* Nav groups */}
      <nav className="flex flex-1 flex-col gap-1 overflow-y-auto px-2 py-3">
        {NAV_GROUPS.map((group, gi) => (
          <div key={group.label} className={cn(gi > 0 && "mt-3")}>
            <p className="mb-1 px-3 text-[10px] font-semibold vf-text-m uppercase tracking-[0.08em] select-none">
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
                      "group relative flex items-center gap-2.5 rounded-xl px-3 py-[7px] text-[13px] font-medium transition-all duration-100",
                      active
                        ? "bg-indigo-500/[0.12] text-indigo-500"
                        : "vf-text-m hover:vf-text-2 hover:bg-[var(--vf-hover)]"
                    )}
                  >
                    {active && (
                      <span className="absolute left-0 top-1/2 -translate-y-1/2 h-5 w-[3px] rounded-r-full bg-indigo-500" />
                    )}
                    <Icon className={cn(
                      "h-[18px] w-[18px] shrink-0 transition-colors",
                      active ? "text-indigo-500" : "vf-text-m group-hover:vf-text-2"
                    )} />
                    {t(key as Parameters<typeof t>[0])}
                  </Link>
                );
              })}
            </div>
          </div>
        ))}
      </nav>

      {/* Bottom: theme + locale + account */}
      <div className="shrink-0 px-2 py-3 space-y-1" style={{ borderTop: "1px solid var(--vf-border)" }}>
        {/* Theme toggle */}
        <div className="flex justify-end px-1 pb-1">
          <ThemeToggle />
        </div>

        {/* AI indicator */}
        {isClient && (
          <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg">
            <span className={cn(
              "h-1.5 w-1.5 rounded-full shrink-0",
              openaiConnected ? "bg-emerald-500 animate-pulse-dot" : "bg-[var(--vf-text-muted)]/30"
            )} />
            <span className="text-[11px] vf-text-m">
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
                  ? "vf-text-2 bg-[var(--vf-bg-elevated)]"
                  : "vf-text-m hover:vf-text-m"
              )}
            >
              {label}
            </button>
          ))}
        </div>

        {/* Account row */}
        <button
          onClick={handleSignOut}
          className="flex w-full items-center gap-2.5 rounded-lg px-3 py-2 transition-colors vf-row group"
        >
          <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-gradient-to-br from-indigo-600 to-violet-700 text-[11px] font-bold text-white select-none">
            {avatarLetter}
          </div>
          <div className="flex-1 min-w-0 text-left">
            <p className="truncate text-[12px] font-medium vf-text-2 transition-colors">
              {isClient ? (email ?? "Account") : "Account"}
            </p>
            <p className="text-[10px] vf-text-m">Free plan</p>
          </div>
          <LogOut className="h-3.5 w-3.5 shrink-0 vf-text-m transition-colors" />
        </button>
      </div>
    </>
  );

  /* ── Layout ─────────────────────────────────────────────────────────────── */
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

      <div className="win11 flex min-h-screen" style={{ background: "var(--vf-bg-primary)" }}>

        {/* Mobile overlay */}
        {sidebarOpen && (
          <div
            className="fixed inset-0 z-30 bg-black/50 backdrop-blur-sm lg:hidden"
            onClick={() => setSidebarOpen(false)}
          />
        )}

        {/* Sidebar */}
        <aside className={cn(
          "fixed inset-y-0 left-0 z-40 flex w-[220px] shrink-0 flex-col transition-transform duration-200 lg:static lg:translate-x-0",
          sidebarOpen ? "translate-x-0" : "-translate-x-full"
        )} style={{ background: "var(--vf-bg-primary)", borderRight: "1px solid var(--vf-border)" }}>
          <SidebarContent />
        </aside>

        {/* Main column */}
        <div className="flex flex-1 min-w-0 flex-col">

          {/* Mobile top bar */}
          <header className="flex h-14 shrink-0 items-center gap-3 px-4 lg:hidden"
            style={{ borderBottom: "1px solid var(--vf-border)" }}>
            <button
              onClick={() => setSidebarOpen(true)}
              className="vf-text-m hover:vf-text-1 transition-colors"
            >
              <Menu className="h-5 w-5" />
            </button>
            <span className="bg-gradient-to-r from-indigo-500 to-violet-500 bg-clip-text text-transparent text-[15px] font-bold tracking-tight">
              Varuflow
            </span>
          </header>

          {/* Desktop topbar */}
          <header className="hidden lg:flex h-[57px] shrink-0 items-center justify-between gap-4 px-6"
            style={{ borderBottom: "1px solid var(--vf-border)" }}>
            <h1 className="text-[13px] font-semibold tracking-tight vf-text-1">
              {getPageTitle(pathname)}
            </h1>
            <div className="flex items-center gap-2">
              <CountryPicker />
              <button
                onClick={openSearch}
                className="flex items-center gap-2 rounded-xl px-3 py-2 text-xs vf-text-m transition-all vf-btn-ghost h-9"
              >
                <Search className="h-3.5 w-3.5" />
                <span className="hidden xl:inline">Search</span>
                <kbd className="hidden xl:inline-block rounded-md px-1.5 py-0.5 text-[10px] vf-text-m font-mono"
                  style={{ background: "var(--vf-bg-elevated)", border: "1px solid var(--vf-border)" }}>
                  ⌘K
                </kbd>
              </button>
              <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-gradient-to-br from-indigo-600 to-violet-700 text-[11px] font-bold text-white select-none">
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
          <nav className="lg:hidden flex pb-safe" style={{ borderTop: "1px solid var(--vf-border)", background: "var(--vf-bg-primary)" }}>
            {MOBILE_NAV.map(({ href, icon: Icon, label }) => {
              const active = isActive(href);
              return (
                <Link
                  key={href}
                  href={href}
                  className={cn(
                    "flex flex-1 flex-col items-center gap-1 py-3 text-[10px] font-medium transition-colors",
                    active ? "text-indigo-500" : "vf-text-m hover:vf-text-2"
                  )}
                >
                  <Icon className="h-[20px] w-[20px]" />
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
      <SessionTimeoutModal />
    </>
  );
}
