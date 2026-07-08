// File: src/components/console/ConsoleShell.tsx
// Purpose: Operator-console shell — orchestrates the four regions:
//   1) ConsoleHeader (top)      2) ResourceTree (left, collapsible / mobile slide-over)
//   3) {children} (center)      4) TaskDrawer (bottom, collapsible)
// It replaces the legacy AppShell in (app)/layout.tsx but preserves everything
// AppShell provided: Branding + Role providers, the ⌘K CommandPalette, AiChat,
// PwaInstallBanner, SessionTimeoutModal, MaintenanceBanner and the dev toolbar.
// Region 3 renders the real route page, so all routing/i18n/guards are intact.

"use client";

import { useEffect, useState } from "react";
import dynamic from "next/dynamic";
import { useTranslations } from "next-intl";
import { PanelLeftClose, PanelLeftOpen } from "lucide-react";

import { createClient, isSupabaseConfigured } from "@/lib/supabase/client";
import { BrandingProvider } from "@/lib/branding";
import { RoleProvider } from "@/components/app/RoleContext";
import { useRouter, usePathname } from "@/i18n/navigation";
import { cn } from "@/lib/utils";
import { Sheet, SheetContent, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { DevToolbar } from "@/components/app/DevToolbar";
import ConsoleHeader from "@/components/console/ConsoleHeader";
import ResourceTree from "@/components/console/ResourceTree";
import TaskDrawer from "@/components/console/TaskDrawer";
import { TaskDrawerProvider } from "@/components/console/TaskDrawerContext";

// Preserve the same client-only overlays AppShell mounted.
const AiChat = dynamic(() => import("@/components/app/AiChat"), { ssr: false });
const CommandPalette = dynamic(() => import("@/components/app/CommandPalette"), { ssr: false });
const PwaInstallBanner = dynamic(() => import("@/components/app/PwaInstallBanner"), { ssr: false });
const SessionTimeoutModal = dynamic(() => import("@/components/app/SessionTimeoutModal"), { ssr: false });
const MaintenanceBanner = dynamic(
  () => import("@/components/app/MaintenanceBanner").then((m) => m.MaintenanceBanner),
  { ssr: false }
);

const COLLAPSE_KEY = "hf-console-tree-collapsed";

function ConsoleShellInner({ children }: { children: React.ReactNode }) {
  const t = useTranslations("console");
  const router = useRouter();
  const supabase = createClient();

  const [collapsed, setCollapsed] = useState(false);
  const [mobileTreeOpen, setMobileTreeOpen] = useState(false);
  const [userLabel, setUserLabel] = useState<string | null>(null);

  useEffect(() => {
    setCollapsed(localStorage.getItem(COLLAPSE_KEY) === "1");
    if (isSupabaseConfigured) {
      supabase.auth
        .getUser()
        .then(({ data }) => setUserLabel(data.user?.user_metadata?.full_name ?? data.user?.email ?? null))
        .catch(() => {});
    }
  }, []);

  function toggleCollapsed() {
    setCollapsed((c) => {
      const next = !c;
      localStorage.setItem(COLLAPSE_KEY, next ? "1" : "0");
      return next;
    });
  }

  async function handleSignOut() {
    try {
      if (isSupabaseConfigured) await supabase.auth.signOut();
    } catch {
      /* ignore */
    }
    router.push("/auth/login");
  }

  return (
    <div className="flex h-screen flex-col overflow-hidden bg-background text-foreground">
      <MaintenanceBanner />

      {/* Region 1 */}
      <ConsoleHeader
        onOpenTree={() => setMobileTreeOpen(true)}
        userLabel={userLabel}
        onSignOut={handleSignOut}
      />

      <div className="flex min-h-0 flex-1">
        {/* Region 2 — desktop resource tree (persistent, collapsible) */}
        <aside
          className={cn(
            "hidden shrink-0 border-r bg-background transition-[width] duration-200 lg:block",
            collapsed ? "w-12" : "w-64"
          )}
        >
          {collapsed ? (
            <button
              type="button"
              onClick={toggleCollapsed}
              aria-label={t("tree.expand")}
              className="grid h-11 w-full place-items-center text-muted-foreground hover:bg-accent"
            >
              <PanelLeftOpen className="h-5 w-5" />
            </button>
          ) : (
            <div className="flex h-full flex-col">
              <div className="flex justify-end px-2 pt-2">
                <button
                  type="button"
                  onClick={toggleCollapsed}
                  aria-label={t("tree.collapse")}
                  className="rounded p-1 text-muted-foreground hover:bg-accent hover:text-foreground"
                >
                  <PanelLeftClose className="h-4 w-4" />
                </button>
              </div>
              <div className="min-h-0 flex-1">
                <ResourceTree />
              </div>
            </div>
          )}
        </aside>

        {/* Regions 3 + 4 */}
        <div className="flex min-w-0 flex-1 flex-col">
          <main className="min-h-0 flex-1 overflow-auto">{children}</main>
          <TaskDrawer />
        </div>
      </div>

      {/* Region 2 — mobile slide-over (requirement #7) */}
      <Sheet open={mobileTreeOpen} onOpenChange={setMobileTreeOpen}>
        <SheetContent side="left" className="w-72 p-0">
          <SheetHeader className="border-b">
            <SheetTitle>{t("tree.title")}</SheetTitle>
          </SheetHeader>
          <ResourceTree onNavigate={() => setMobileTreeOpen(false)} />
        </SheetContent>
      </Sheet>

      {/* Preserved overlays */}
      <CommandPalette />
      <AiChat />
      <PwaInstallBanner />
      <SessionTimeoutModal />
      {process.env.NODE_ENV === "development" && <DevToolbar />}
    </div>
  );
}

export default function ConsoleShell({ children }: { children: React.ReactNode }) {
  // The cash register runs distraction-free: no header, tree, or drawer —
  // a till shows the till. usePathname from @/i18n/navigation is already
  // locale-stripped ("/pos", not "/sv/pos"). Exact match only: /pos/zreport
  // and other sub-pages keep the normal console chrome.
  const pathname = usePathname();
  if (pathname === "/pos") {
    return <div className="h-dvh">{children}</div>;
  }
  return (
    <BrandingProvider>
      <RoleProvider>
        <TaskDrawerProvider>
          <ConsoleShellInner>{children}</ConsoleShellInner>
        </TaskDrawerProvider>
      </RoleProvider>
    </BrandingProvider>
  );
}
