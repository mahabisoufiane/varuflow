"use client";

import { createClient } from "@/lib/supabase/client";
import { cn } from "@/lib/utils";
import { Link, usePathname } from "@/i18n/navigation";
import { useTranslations } from "next-intl";
import { useRouter } from "next/navigation";
import {
  FileText,
  LayoutDashboard,
  LogOut,
  Package,
  Settings,
  Users,
} from "lucide-react";

const navItems = [
  { href: "/dashboard", icon: LayoutDashboard, labelKey: "dashboard" },
  { href: "/inventory", icon: Package, labelKey: "inventory" },
  { href: "/invoices", icon: FileText, labelKey: "invoices" },
  { href: "/customers", icon: Users, labelKey: "customers" },
  { href: "/settings", icon: Settings, labelKey: "settings" },
] as const;

export default function AppShell({ children }: { children: React.ReactNode }) {
  const t = useTranslations("nav");
  const pathname = usePathname();
  const router = useRouter();
  const supabase = createClient();

  async function handleSignOut() {
    await supabase.auth.signOut();
    router.push("/auth/login");
  }

  return (
    <div className="flex min-h-screen">
      <aside className="flex w-64 flex-col border-r bg-[#1a2332] text-white">
        {/* Logo */}
        <div className="flex h-16 items-center border-b border-white/10 px-6">
          <span className="text-xl font-bold">Varuflow</span>
        </div>

        {/* Nav */}
        <nav className="flex flex-1 flex-col gap-1 p-4">
          {navItems.map(({ href, icon: Icon, labelKey }) => (
            <Link
              key={href}
              href={href}
              className={cn(
                "flex items-center gap-3 rounded-lg px-3 py-2 text-sm transition-colors",
                pathname === href
                  ? "bg-white/10 text-white"
                  : "text-gray-400 hover:bg-white/5 hover:text-white"
              )}
            >
              <Icon className="h-4 w-4 shrink-0" />
              {t(labelKey)}
            </Link>
          ))}
        </nav>

        {/* Sign out */}
        <div className="border-t border-white/10 p-4">
          <button
            onClick={handleSignOut}
            className="flex w-full items-center gap-3 rounded-lg px-3 py-2 text-sm text-gray-400 transition-colors hover:bg-white/5 hover:text-white"
          >
            <LogOut className="h-4 w-4 shrink-0" />
            {t("signOut")}
          </button>
        </div>
      </aside>

      <main className="flex-1 bg-gray-50">
        <div className="container mx-auto p-6">{children}</div>
      </main>
    </div>
  );
}
