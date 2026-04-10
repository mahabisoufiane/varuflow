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

const AiChat        = dynamic(() => import("@/components/app/AiChat"),         { ssr: false });
const CommandPalette = dynamic(() => import("@/components/app/CommandPalette"), { ssr: false });
const PwaInstallBanner = dynamic(() => import("@/components/app/PwaInstallBanner"), { ssr: false });

/* ── Nav groups ─────────────────────────────────────────────────────────────── */
const NAV_GROUPS = [
  {
    label: "OVERVIEW",
    items: [
      { href: "/dashboard", icon: LayoutDashboard, key: "dashboard"  },
      { href: "/analytics", icon: BarChart3,        key: "analytics"  },
    ],
  },
  {
    label: "OPERATIONS",
    items: [
      { href: "/inventory", icon: Package,   key: "inventory"    },
      { href: "/invoices",  icon: FileText,  key: "invoices"     },
      { href: "/recurring", icon: RefreshCw, key: "recurring"    },
      { href: "/pos",       icon: ShoppingCart, key: "cashRegister" },
      { href: "/customers", icon: Users,     key: "customers"    },
    ],
  },
  {
    label: "INTELLIGENCE",
    items: [
      { href: "/ai", icon: Bot, key: "aiAdvisor" },
    ],
  },
  {
    label: "SETTINGS",
    items: [
      { href: "/settings", icon: Settings, key: "settings" },
    ],
  },
] as const;

/* Bottom mobile nav — 5 key items */
const MOBILE_NAV = [
  { href: "/dashboard",  icon: Home,      label: "Home"      },
  { href: "/inventory",  icon: Package,   label: "Inventory" },
  { href: "/invoices",   icon: FileText,  label: "Invoices"  },
  { href: "/ai",         icon: Bot,       label: "AI"        },
  { href: "/settings",   icon: Settings,  label: "More"      },
] as const;

const LOCALES = [
  { code: "sv", label: "SV" },
  { code: "en", label: "EN" },
] as const;

export default function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const router   = useRouter();
  const locale   = useLocale();
  const t        = useTranslations("nav");
  // Supabase client — created inside the component, never at module level
  const supabase = createClient();

  const [isClient,        setIsClient]        = useState(false);
  const [email,           setEmail]           = useState<string | null>(null);
  const [fortnoxConnected,setFortnoxConnected] = useState(false);
  const [openaiConnected, setOpenaiConnected]  = useState(false);
  const [sidebarOpen,     setSidebarOpen]      = useState(false);

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
    // Check OpenAI by seeing if settings has it (simple heuristic)
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

  const avatarLetter = isClient && email ? email[0].toUpperCase() : "?";

  const SidebarContent = () => (
    <>
      {/* Logo */}
      <div className="flex h-14 items-center gap-3 border-b border-white/[0.06] px-5">
        <div className="flex h-8 w-8 items-center justify-center rounded-xl bg-gradient-to-br from-indigo-500 to-violet-600 shadow-glow shrink-0">
          <Zap className="h-4 w-4 text-white" />
        </div>
        <div className="flex-1 min-w-0">
          <span className="bg-gradient-to-r from-indigo-400 to-violet-400 bg-clip-text text-transparent text-[15px] font-bold tracking-tight">
            Varuflow
          </span>
        </div>
        {isClient && fortnoxConnected && (
          <span className="shrink-0 rounded-full bg-emerald-500/20 border border-emerald-500/20 px-1.5 py-0.5 text-[9px] font-bold text-emerald-400">
            FX
          </span>
        )}
        <button
          className="lg:hidden ml-auto text-slate-500 hover:text-slate-300"
          onClick={() => setSidebarOpen(false)}
        >
          <X className="h-4 w-4" />
        </button>
      </div>

      {/* Search */}
      <div className="px-3 pt-3 pb-1">
        <button
          onClick={() => {
            setSidebarOpen(false);
            document.dispatchEvent(new KeyboardEvent("keydown", { key: "k", metaKey: true, bubbles: true }));
          }}
          className="flex w-full items-center gap-2 rounded-lg bg-white/[0.04] border border-white/[0.06] px-3 py-2 text-xs text-slate-500 hover:bg-white/[0.07] hover:text-slate-300 transition-colors"
        >
          <Search className="h-3.5 w-3.5 shrink-0" />
          <span className="flex-1 text-left">Search…</span>
          <kbd className="rounded bg-white/5 border border-white/10 px-1.5 py-0.5 text-[10px] text-slate-600">⌘K</kbd>
        </button>
      </div>

      {/* Nav groups */}
      <nav className="flex flex-1 flex-col gap-4 overflow-y-auto px-3 py-3">
        {NAV_GROUPS.map((group) => (
          <div key={group.label}>
            <p className="mb-1 px-2 text-[10px] font-semibold tracking-[0.12em] text-slate-600">
              {group.label}
            </p>
            <div className="flex flex-col gap-[2px]">
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
                        ? "bg-indigo-500/10 text-indigo-400"
                        : "text-slate-400 hover:bg-white/[0.05] hover:text-slate-200"
                    )}
                  >
                    {active && (
                      <span className="absolute left-0 top-1/2 -translate-y-1/2 h-4 w-[3px] rounded-r-full bg-indigo-500" />
                    )}
                    <Icon className={cn("h-4 w-4 shrink-0 transition-colors", active ? "text-indigo-400" : "text-slate-600 group-hover:text-slate-400")} />
                    {t(key as Parameters<typeof t>[0])}
                  </Link>
                );
              })}
            </div>
          </div>
        ))}
      </nav>

      {/* AI status + locale */}
      <div className="border-t border-white/[0.06] px-3 py-2 space-y-2">
        {/* AI indicator */}
        {isClient && (
          <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-white/[0.03]">
            <span className={cn(
              "h-1.5 w-1.5 rounded-full",
              openaiConnected ? "bg-emerald-400 animate-pulse-dot" : "bg-slate-600"
            )} />
            <span className="text-[11px] text-slate-500">
              AI {openaiConnected ? "connected" : "not configured"}
            </span>
          </div>
        )}
        {/* Locale */}
        <div className="flex gap-[3px]">
          {LOCALES.map(({ code, label }) => (
            <button
              key={code}
              onClick={() => router.replace(pathname, { locale: code })}
              className={cn(
                "flex-1 rounded-md py-1 text-[10px] font-bold tracking-wider transition-colors",
                isClient && locale === code
                  ? "bg-white/10 text-white"
                  : "text-slate-700 hover:bg-white/5 hover:text-slate-400"
              )}
            >
              {label}
            </button>
          ))}
        </div>
      </div>

      {/* User */}
      <div className="px-2 pb-3">
        <button
          onClick={handleSignOut}
          className="flex w-full items-center gap-2.5 rounded-lg px-3 py-2 transition-colors hover:bg-white/[0.05] group"
        >
          <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-gradient-to-br from-indigo-600 to-violet-700 text-[11px] font-bold text-white">
            {avatarLetter}
          </div>
          <div className="flex-1 min-w-0 text-left">
            <p className="truncate text-[12px] font-medium text-slate-400 group-hover:text-slate-200 transition-colors">
              {isClient ? (email ?? "Account") : "Account"}
            </p>
            <p className="text-[10px] text-slate-600">Free plan</p>
          </div>
          <LogOut className="h-3.5 w-3.5 shrink-0 text-slate-700 group-hover:text-slate-500 transition-colors" />
        </button>
      </div>
    </>
  );

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

        {/* ── Mobile overlay ────────────────────────────────────────── */}
        {sidebarOpen && (
          <div
            className="fixed inset-0 z-30 bg-black/60 lg:hidden"
            onClick={() => setSidebarOpen(false)}
          />
        )}

        {/* ── Sidebar desktop ───────────────────────────────────────── */}
        <aside className={cn(
          "fixed inset-y-0 left-0 z-40 flex w-60 shrink-0 flex-col border-r border-white/[0.06] bg-vf-base transition-transform duration-200 lg:static lg:translate-x-0",
          sidebarOpen ? "translate-x-0" : "-translate-x-full"
        )}>
          <SidebarContent />
        </aside>

        {/* ── Main ──────────────────────────────────────────────────── */}
        <div className="flex flex-1 min-w-0 flex-col">
          {/* Mobile top bar */}
          <header className="flex h-14 items-center gap-3 border-b border-white/[0.06] px-4 lg:hidden">
            <button onClick={() => setSidebarOpen(true)} className="text-slate-400 hover:text-slate-200">
              <Menu className="h-5 w-5" />
            </button>
            <span className="bg-gradient-to-r from-indigo-400 to-violet-400 bg-clip-text text-transparent text-[15px] font-bold tracking-tight">
              Varuflow
            </span>
          </header>

          <main className="flex-1 min-w-0 overflow-auto">
            <div className="mx-auto max-w-6xl px-4 sm:px-8 py-7 page-enter">
              {children}
            </div>
          </main>

          {/* Mobile bottom nav */}
          <nav className="lg:hidden flex border-t border-white/[0.06] bg-vf-base pb-safe">
            {MOBILE_NAV.map(({ href, icon: Icon, label }) => {
              const active = isActive(href);
              return (
                <Link
                  key={href}
                  href={href}
                  className={cn(
                    "flex flex-1 flex-col items-center gap-1 py-2.5 text-[10px] font-medium transition-colors",
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
