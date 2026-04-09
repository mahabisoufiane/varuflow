"use client";

import { supabase, isSupabaseConfigured } from "@/lib/supabase/client";
import { api } from "@/lib/api-client";
import { cn } from "@/lib/utils";
import { Link, usePathname, useRouter } from "@/i18n/navigation";
import { useLocale, useTranslations } from "next-intl";
import { useEffect, useState } from "react";
import { toast } from "sonner";
import {
  BarChart3, Bot, FileText, LayoutDashboard, LogOut,
  Package, RefreshCw, Search, Settings, ShoppingCart, Users, Zap,
} from "lucide-react";

import dynamic from "next/dynamic";

const AiChat = dynamic(() => import("@/components/app/AiChat"), { ssr: false });
const CommandPalette = dynamic(() => import("@/components/app/CommandPalette"), { ssr: false });
const PwaInstallBanner = dynamic(() => import("@/components/app/PwaInstallBanner"), { ssr: false });

const NAV = [
  { href: "/dashboard",  icon: LayoutDashboard, key: "dashboard"    },
  { href: "/analytics",  icon: BarChart3,        key: "analytics"    },
  { href: "/ai",         icon: Bot,              key: "aiAdvisor"    },
  { href: "/inventory",  icon: Package,          key: "inventory"    },
  { href: "/invoices",   icon: FileText,         key: "invoices"     },
  { href: "/recurring",  icon: RefreshCw,        key: "recurring"    },
  { href: "/pos",        icon: ShoppingCart,     key: "cashRegister" },
  { href: "/customers",  icon: Users,            key: "customers"    },
  { href: "/settings",   icon: Settings,         key: "settings"     },
] as const;

const LOCALES = [
  { code: "sv", label: "SV" },
  { code: "en", label: "EN" },
] as const;

export default function AppShell({ children }: { children: React.ReactNode }) {
  const pathname  = usePathname();
  const router    = useRouter();
  const locale    = useLocale();
  // isClient: false on server → all nav items render inactive (no mismatch)
  // becomes true after first paint → correct active item shown
  const t = useTranslations("nav");

  const [isClient, setIsClient] = useState(false);
  const [email, setEmail] = useState<string | null>(null);
  const [fortnoxConnected, setFortnoxConnected] = useState(false);

  useEffect(() => {
    setIsClient(true);
    if (isSupabaseConfigured) {
      supabase.auth.getUser().then((res: Awaited<ReturnType<typeof supabase.auth.getUser>>) => {
        const userEmail = res.data.user?.email ?? null;
        setEmail(userEmail);
        // Boot Crisp with user identity once we know who's logged in
        if (userEmail && process.env.NEXT_PUBLIC_CRISP_WEBSITE_ID && typeof window !== "undefined") {
          const w = window as unknown as Record<string, unknown>;
          if (w.$crisp) {
            (w.$crisp as string[][]).push(["set", "user:email", userEmail]);
          }
        }
      });
    }
    api.get<{ connected: boolean }>("/api/integrations/fortnox/status")
      .then((s) => setFortnoxConnected(s.connected))
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

  return (
    <>
    {/* Crisp support chat — only loads when NEXT_PUBLIC_CRISP_WEBSITE_ID is set */}
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
    <div className="flex min-h-screen bg-[#f4f5f7]">

        {/* ── Sidebar ───────────────────────────────────────────────── */}
        <aside className="flex w-[220px] shrink-0 flex-col bg-[#0d1117] text-white">

          {/* Logo */}
          <div className="flex h-[56px] items-center gap-2.5 border-b border-white/5 px-5">
            <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-gradient-to-br from-blue-500 to-indigo-600 shadow-lg">
              <Zap className="h-3.5 w-3.5 text-white" />
            </div>
            <span className="text-[14px] font-semibold tracking-tight">Varuflow</span>
            {isClient && fortnoxConnected && (
              <span className="ml-auto inline-flex items-center gap-1 rounded-full bg-emerald-500/20 px-1.5 py-0.5 text-[9px] font-bold text-emerald-400 tracking-wide">
                FX
              </span>
            )}
          </div>

          {/* Search */}
          <div className="px-3 pt-3 pb-1">
            <button
              onClick={() => document.dispatchEvent(new KeyboardEvent("keydown", { key: "k", metaKey: true, bubbles: true }))}
              className="flex w-full items-center gap-2 rounded-lg bg-white/[0.05] px-3 py-2 text-xs text-gray-500 hover:bg-white/[0.08] hover:text-gray-300 transition-colors"
            >
              <Search className="h-3.5 w-3.5 shrink-0" />
              <span className="flex-1 text-left">Search…</span>
              <kbd className="rounded bg-white/5 px-1.5 py-0.5 text-[10px] text-gray-600">⌘K</kbd>
            </button>
          </div>

          {/* Nav */}
          <nav className="flex flex-1 flex-col gap-[2px] px-2 py-2">
            {NAV.map(({ href, icon: Icon, key }) => {
              const active = isActive(href);
              return (
                <Link
                  key={href}
                  href={href}
                  className={cn(
                    "group relative flex items-center gap-2.5 rounded-lg px-3 py-[7px] text-[13px] font-medium transition-all duration-100",
                    active
                      ? "bg-white/10 text-white"
                      : "text-gray-500 hover:bg-white/[0.05] hover:text-gray-200"
                  )}
                >
                  {active && (
                    <span className="absolute left-0 top-1/2 -translate-y-1/2 h-4 w-[3px] rounded-r-full bg-blue-400" />
                  )}
                  <Icon className={cn("h-4 w-4 shrink-0", active ? "text-blue-300" : "text-gray-600 group-hover:text-gray-400")} />
                  {t(key)}
                </Link>
              );
            })}
          </nav>

          {/* Locale switcher */}
          <div className="border-t border-white/5 px-3 py-2">
            <div className="flex gap-[3px]">
              {LOCALES.map(({ code, label }) => (
                <button
                  key={code}
                  onClick={() => router.replace(pathname, { locale: code })}
                  className={cn(
                    "flex-1 rounded-md py-1 text-[10px] font-bold tracking-wider transition-colors",
                    isClient && locale === code
                      ? "bg-white/15 text-white"
                      : "text-gray-700 hover:bg-white/5 hover:text-gray-400"
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
              className="flex w-full items-center gap-2.5 rounded-lg px-3 py-2 text-[12px] transition-colors hover:bg-white/5 group"
            >
              <div className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-gradient-to-br from-gray-600 to-gray-700 text-[10px] font-bold uppercase text-gray-200">
                {isClient && email ? email[0] : "?"}
              </div>
              <span className="flex-1 min-w-0 truncate text-left text-gray-500 group-hover:text-gray-300 text-[11px]">
                {isClient ? (email ?? "Account") : "Account"}
              </span>
              <LogOut className="h-3.5 w-3.5 shrink-0 text-gray-700 group-hover:text-gray-500" />
            </button>
          </div>
        </aside>

        {/* ── Main ──────────────────────────────────────────────────── */}
        <main className="flex-1 min-w-0 overflow-auto">
          <div className="mx-auto max-w-6xl px-8 py-7">{children}</div>
        </main>
      </div>

      <CommandPalette />
      <AiChat />
      <PwaInstallBanner />
    </>
  );
}
