"use client";

import { createClient } from "@/lib/supabase/client";
import { api } from "@/lib/api-client";
import { cn } from "@/lib/utils";
import { Link, usePathname, useRouter } from "@/i18n/navigation";
import { useLocale } from "next-intl";
import { useEffect, useState } from "react";
import { toast } from "sonner";
import CommandPalette from "@/components/app/CommandPalette";
import AiChat from "@/components/app/AiChat";
import {
  BarChart3,
  Bot,
  FileText,
  LayoutDashboard,
  LogOut,
  Package,
  RefreshCw,
  Search,
  Settings,
  ShoppingCart,
  Users,
  Zap,
} from "lucide-react";

const NAV = [
  { href: "/dashboard", icon: LayoutDashboard, label: "Dashboard" },
  { href: "/analytics", icon: BarChart3, label: "Analytics" },
  { href: "/ai", icon: Bot, label: "AI Advisor" },
  { href: "/inventory", icon: Package, label: "Inventory" },
  { href: "/invoices", icon: FileText, label: "Invoices" },
  { href: "/recurring", icon: RefreshCw, label: "Recurring" },
  { href: "/pos", icon: ShoppingCart, label: "Cash Register" },
  { href: "/customers", icon: Users, label: "Customers" },
  { href: "/settings", icon: Settings, label: "Settings" },
] as const;

const LOCALES = [
  { code: "en", flag: "🇬🇧", label: "EN" },
  { code: "sv", flag: "🇸🇪", label: "SV" },
  { code: "no", flag: "🇳🇴", label: "NO" },
  { code: "da", flag: "🇩🇰", label: "DA" },
] as const;

export default function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const locale = useLocale();
  const supabase = createClient();
  const [email, setEmail] = useState<string | null>(null);
  const [fortnoxConnected, setFortnoxConnected] = useState(false);

  useEffect(() => {
    supabase.auth.getUser().then(({ data }) => {
      setEmail(data.user?.email ?? null);
    });
    api.get<{ connected: boolean }>("/api/integrations/fortnox/status")
      .then((s: { connected: boolean }) => setFortnoxConnected(s.connected))
      .catch(() => {});
  }, []);

  async function handleSignOut() {
    await supabase.auth.signOut();
    toast.success("Signed out");
    router.push("/auth/login");
  }

  return (
    <>
      <CommandPalette />
      <AiChat />
      <div className="flex min-h-screen bg-gray-50">
        {/* Sidebar */}
        <aside className="flex w-60 flex-col bg-[#0f1724] text-white shrink-0">
          {/* Logo */}
          <div className="flex h-14 items-center gap-2.5 px-5 border-b border-white/5">
            <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-white/10">
              <Zap className="h-4 w-4 text-white" />
            </div>
            <span className="text-[15px] font-semibold tracking-tight">Varuflow</span>
            {fortnoxConnected && (
              <span className="ml-auto inline-flex items-center gap-1 rounded-full bg-emerald-500/20 px-2 py-0.5 text-[10px] font-medium text-emerald-400">
                <span className="h-1 w-1 rounded-full bg-emerald-400" />FX
              </span>
            )}
          </div>

          {/* Search trigger */}
          <div className="px-3 pt-3 pb-1">
            <button
              onClick={() => {
                const e = new KeyboardEvent("keydown", { key: "k", metaKey: true, bubbles: true });
                document.dispatchEvent(e);
              }}
              className="flex w-full items-center gap-2 rounded-lg bg-white/5 px-3 py-2 text-sm text-gray-400 hover:bg-white/10 transition-colors"
            >
              <Search className="h-3.5 w-3.5 shrink-0" />
              <span className="flex-1 text-left text-xs">Search…</span>
              <kbd className="hidden sm:inline-flex items-center gap-0.5 text-[10px] text-gray-500">
                <span className="text-[11px]">⌘</span>K
              </kbd>
            </button>
          </div>

          {/* Nav */}
          <nav className="flex flex-1 flex-col gap-0.5 px-3 py-2">
            {NAV.map(({ href, icon: Icon, label }) => {
              const active = pathname === href || (href !== "/dashboard" && pathname.startsWith(href + "/")) || pathname.startsWith(href);
              return (
                <Link
                  key={href}
                  href={href}
                  className={cn(
                    "group flex items-center gap-2.5 rounded-lg px-3 py-2 text-[13px] font-medium transition-all duration-150",
                    active
                      ? "bg-white/10 text-white"
                      : "text-gray-400 hover:bg-white/5 hover:text-gray-200"
                  )}
                >
                  <Icon className={cn("h-4 w-4 shrink-0 transition-colors", active ? "text-white" : "text-gray-500 group-hover:text-gray-300")} />
                  {label}
                  {active && <span className="ml-auto h-1.5 w-1.5 rounded-full bg-blue-400" />}
                </Link>
              );
            })}
          </nav>

          {/* Locale switcher */}
          <div className="border-t border-white/5 px-3 pt-2 pb-1">
            <div className="flex gap-0.5">
              {LOCALES.map(({ code, flag, label }) => (
                <button
                  key={code}
                  onClick={() => router.replace(pathname, { locale: code })}
                  title={label}
                  className={cn(
                    "flex-1 rounded py-1 text-[11px] font-medium transition-colors",
                    locale === code
                      ? "bg-white/15 text-white"
                      : "text-gray-500 hover:bg-white/5 hover:text-gray-300"
                  )}
                >
                  {flag}
                </button>
              ))}
            </div>
          </div>

          {/* User footer */}
          <div className="px-3 pb-3">
            <button
              onClick={handleSignOut}
              className="flex w-full items-center gap-2.5 rounded-lg px-3 py-2 text-[13px] transition-colors hover:bg-white/5 group"
            >
              <div className="flex h-6 w-6 items-center justify-center rounded-full bg-white/10 text-[10px] font-bold uppercase text-gray-300 shrink-0">
                {email ? email[0] : "?"}
              </div>
              <span className="flex-1 min-w-0 text-left truncate text-gray-400 group-hover:text-gray-200 text-xs">
                {email ?? "Account"}
              </span>
              <LogOut className="h-3.5 w-3.5 text-gray-600 group-hover:text-gray-400 shrink-0" />
            </button>
          </div>
        </aside>

        {/* Main */}
        <main className="flex-1 min-w-0 overflow-auto">
          <div className="mx-auto max-w-6xl p-8">{children}</div>
        </main>
      </div>
    </>
  );
}
