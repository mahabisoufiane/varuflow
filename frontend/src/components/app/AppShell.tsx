"use client";

import { createClient, isSupabaseConfigured } from "@/lib/supabase/client";
import { api } from "@/lib/api-client";
import { BrandingProvider, useBranding } from "@/lib/branding";
import { Link, usePathname, useRouter } from "@/i18n/navigation";
import { useLocale, useTranslations } from "next-intl";
import { useEffect, useState } from "react";
import { toast } from "sonner";
import {
  BarChart3, BookOpen, Bot, Building2, FileText, LayoutDashboard, LogOut,
  Package, PiggyBank, RefreshCw, Search, Settings, ShoppingBag, ShoppingCart, Store, Users, Zap,
  Menu, X, Home, Landmark, ReceiptText, Wallet, Target, TrendingUp, Mail, Link2, Calendar,
  Users2, CalendarOff, Timer, ClipboardList, GitFork, GitBranch, FileSignature,
  FileCheck2, Calculator, CreditCard,
  Factory, BookCopy, CalendarCheck2, ClipboardCheck, Package2,
  FolderKanban, Clock, BarChart2, Repeat2,
  Plug, Navigation, Mic, Wifi, PenLine, Bell,
  Network, ArrowLeftRight, Receipt,
  DollarSign, FileBarChart2, FlaskConical, TrendingDown, ShieldCheck,
  CalendarDays, GraduationCap, CheckSquare,
  Megaphone, Wrench, Ticket,
  Banknote, FileSpreadsheet, Activity,
  MessageCircle, HelpCircle, List,
  Leaf, Award, CalendarClock, Eye, EyeOff, Fingerprint,
  PieChart, FolderLock, Radio, Star,
  Smartphone, UserPlus,
  Video, Camera, MapPin, AlertCircle,
  Gift, Flame, Heart, Globe,
  Shield, FileSearch,
  ChevronRight, Lock,
} from "lucide-react";
import Script from "next/script";
import dynamic from "next/dynamic";
import ThemeToggle from "@/components/ui/ThemeToggle";
import { WorkspaceSwitcher } from "@/components/app/WorkspaceSwitcher";
import { DevToolbar } from "@/components/app/DevToolbar";
import { cx } from "@/lib/cx";
import styles from "./AppShell.module.scss";

const AiChat              = dynamic(() => import("@/components/app/AiChat"),              { ssr: false });
const CommandPalette      = dynamic(() => import("@/components/app/CommandPalette"),      { ssr: false });
const PwaInstallBanner    = dynamic(() => import("@/components/app/PwaInstallBanner"),    { ssr: false });
const SessionTimeoutModal = dynamic(() => import("@/components/app/SessionTimeoutModal"), { ssr: false });
const MaintenanceBanner   = dynamic(() => import("@/components/app/MaintenanceBanner").then(m => m.MaintenanceBanner), { ssr: false });

/* ── Sidebar sections (collapsible) ────────────────────────────────────────── */
type NavItem = { href: string; icon: typeof LayoutDashboard; key: string; module: string };
type SidebarSection = { key: string; icon: typeof LayoutDashboard; label: string; items: NavItem[]; modules: string[] };

const SIDEBAR_SECTIONS: SidebarSection[] = [
  {
    key: "core",
    icon: Home,
    label: "Core",
    modules: ["dashboard", "invoicing", "pos"],
    items: [
      { href: "/dashboard",   icon: LayoutDashboard, key: "dashboard",    module: "dashboard" },
      { href: "/invoices",    icon: FileText,        key: "invoices",     module: "invoicing" },
      { href: "/quotes",      icon: FileSignature,   key: "quotes",       module: "invoicing" },
      { href: "/customers",   icon: Users,           key: "customers",    module: "invoicing" },
      { href: "/recurring",   icon: RefreshCw,       key: "recurring",    module: "invoicing" },
      { href: "/shop/orders", icon: ShoppingBag,     key: "shopOrders",   module: "invoicing" },
      { href: "/pos",         icon: ShoppingCart,    key: "cashRegister", module: "pos"       },
    ],
  },
  {
    key: "inventory",
    icon: Package,
    label: "Inventory",
    modules: ["inventory"],
    items: [
      { href: "/inventory",      icon: Package,    key: "inventory",     module: "inventory" },
      { href: "/kitting",        icon: Package2,   key: "kitting",       module: "inventory" },
      { href: "/landed-costs",   icon: DollarSign, key: "landedCosts",   module: "inventory" },
      { href: "/vendor-ratings", icon: Activity,   key: "vendorRatings", module: "inventory" },
    ],
  },
  {
    key: "operations",
    icon: Wrench,
    label: "Operations",
    modules: ["hr", "manufacturing"],
    items: [
      { href: "/hr",                     icon: Users2,        key: "hrEmployees",  module: "hr"            },
      { href: "/hr/leave",               icon: CalendarOff,   key: "hrLeave",      module: "hr"            },
      { href: "/hr/shifts",              icon: CalendarDays,  key: "hrShifts",     module: "hr"            },
      { href: "/hr/timesheets",          icon: ClipboardCheck,key: "hrTimesheets", module: "hr"            },
      { href: "/scheduling",             icon: CalendarDays,  key: "schRoster",    module: "hr"            },
      { href: "/projects",               icon: FolderKanban,  key: "pmProjects",   module: "hr"            },
      { href: "/work",                   icon: ClipboardList, key: "wmTasks",      module: "hr"            },
      { href: "/hr/org-chart",           icon: GitFork,       key: "hrOrgChart",   module: "hr"            },
      { href: "/manufacturing",          icon: Factory,       key: "mfgOrders",    module: "manufacturing" },
      { href: "/manufacturing/bom",      icon: BookCopy,      key: "mfgBom",       module: "manufacturing" },
      { href: "/manufacturing/kits",     icon: Package2,      key: "mfgKits",      module: "manufacturing" },
      { href: "/manufacturing/planning", icon: CalendarCheck2,key: "mfgPlanning",  module: "manufacturing" },
      { href: "/manufacturing/qc",       icon: ClipboardCheck,key: "mfgQc",        module: "manufacturing" },
    ],
  },
  {
    key: "finance",
    icon: Landmark,
    label: "Finance",
    modules: ["finance"],
    items: [
      { href: "/ceo",                    icon: TrendingUp,     key: "ceoDashboard",        module: "finance" },
      { href: "/ceo/cash-forecast",      icon: DollarSign,     key: "ceoCashFlow",         module: "finance" },
      { href: "/accounting",             icon: BookOpen,       key: "ledger",              module: "finance" },
      { href: "/accounting/vat",         icon: ReceiptText,    key: "vatReturn",           module: "finance" },
      { href: "/accounting/payroll",     icon: Wallet,         key: "payroll",             module: "finance" },
      { href: "/accounting/bank-feed",   icon: Building2,      key: "bankFeed",            module: "finance" },
      { href: "/budget",                 icon: PiggyBank,      key: "budgetWorkflow",      module: "finance" },
      { href: "/purchase-requests",      icon: FileSpreadsheet,key: "finPurchaseRequests", module: "finance" },
      { href: "/expenses",               icon: Receipt,        key: "expenses",            module: "finance" },
      { href: "/reconciliation",         icon: BarChart2,      key: "reconciliation",      module: "finance" },
    ],
  },
  {
    key: "growth",
    icon: BarChart3,
    label: "Growth",
    modules: ["crm", "analytics", "ai"],
    items: [
      { href: "/crm",                    icon: Target,         key: "crmPipeline",         module: "crm"       },
      { href: "/crm/leads",              icon: Users,          key: "crmLeads",            module: "crm"       },
      { href: "/crm/forecast",           icon: TrendingUp,     key: "crmForecast",         module: "crm"       },
      { href: "/b2b",                    icon: Building2,      key: "b2bHub",              module: "crm"       },
      { href: "/analytics",              icon: BarChart3,      key: "analytics",           module: "analytics" },
      { href: "/analytics/dashboard",    icon: LayoutDashboard,key: "biDashboards",        module: "analytics" },
      { href: "/analytics/reports",      icon: ClipboardList,  key: "biReports",           module: "analytics" },
      { href: "/reports/pnl",            icon: BarChart3,      key: "rptPnl",              module: "analytics" },
      { href: "/reports/cashflow",       icon: TrendingUp,     key: "rptCashflow",         module: "analytics" },
      { href: "/reports/balance-sheet",  icon: Landmark,       key: "rptBalanceSheet",     module: "analytics" },
      { href: "/growth",                 icon: TrendingUp,     key: "growthHub",           module: "analytics" },
      { href: "/marketing/broadcasts",   icon: Radio,          key: "marketingBroadcasts", module: "ai"        },
    ],
  },
  {
    key: "ai",
    icon: Bot,
    label: "AI & Intelligence",
    modules: ["ai"],
    items: [
      { href: "/ai",                            icon: Bot,          key: "aiAdvisor",     module: "ai" },
      { href: "/ai/automation",                 icon: Zap,          key: "aiAutomation",  module: "ai" },
      { href: "/ai/workflows",                  icon: GitBranch,    key: "aiWorkflows",   module: "ai" },
      { href: "/ai-tools/product-descriptions", icon: FileText,     key: "aiProductDesc", module: "ai" },
      { href: "/ai-tools/email-drafts",         icon: Mail,         key: "aiEmailDrafts", module: "ai" },
      { href: "/ai-tools/pricing",              icon: DollarSign,   key: "aiPricing",     module: "ai" },
      { href: "/inbox",                         icon: MessageCircle,key: "unifiedInbox",  module: "ai" },
    ],
  },
  {
    key: "settings",
    icon: Settings,
    label: "Settings",
    modules: ["settings"],
    items: [
      { href: "/settings",              icon: Settings,       key: "settings",       module: "settings" },
      { href: "/settings/setup-health", icon: Activity,       key: "setupHealth",    module: "settings" },
      { href: "/settings/data-import",  icon: FileSpreadsheet,key: "dataImport",     module: "settings" },
      { href: "/integrations",          icon: Plug,           key: "intgHub",        module: "settings" },
      { href: "/integrations/api-keys", icon: Fingerprint,    key: "apiKeys",        module: "settings" },
      { href: "/multi-entity",          icon: Network,        key: "multiEntityHub", module: "settings" },
    ],
  },
];

function getSectionForPath(pathname: string): string | null {
  for (const section of SIDEBAR_SECTIONS) {
    for (const item of section.items) {
      if (pathname === item.href || pathname.startsWith(item.href + "/")) {
        return section.key;
      }
    }
  }
  return null;
}

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
function AppShellInner({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const router   = useRouter();
  const locale   = useLocale();
  const t        = useTranslations("nav");
  const supabase = createClient();

  const [isClient,         setIsClient]         = useState(false);
  const [email,            setEmail]            = useState<string | null>(null);
  const [displayName,      setDisplayName]      = useState<string | null>(null);
  const [allowedModules,   setAllowedModules]   = useState<string[]>(["*"]);
  const [planModules,      setPlanModules]       = useState<string[]>(["*"]);
  const [userPlan,         setUserPlan]         = useState<string | null>(null);
  const [fortnoxConnected, setFortnoxConnected] = useState(false);
  const [openaiConnected,  setOpenaiConnected]  = useState(false);
  const [sidebarOpen,      setSidebarOpen]      = useState(false);
  const [expandedSection,  setExpandedSection]  = useState<string | null>(null);

  useEffect(() => {
    setIsClient(true);
    const saved = localStorage.getItem("vf-sidebar-section");
    const fromPath = getSectionForPath(pathname);
    setExpandedSection(saved && !fromPath ? saved : fromPath ?? "core");
    if (isSupabaseConfigured) {
      supabase.auth.getUser().then(({ data }) => {
        const userEmail = data.user?.email ?? null;
        setEmail(userEmail);
        setDisplayName(data.user?.user_metadata?.full_name ?? null);
        if (userEmail && process.env.NEXT_PUBLIC_CRISP_WEBSITE_ID && typeof window !== "undefined") {
          const w = window as unknown as Record<string, unknown>;
          if (w.$crisp) (w.$crisp as unknown[][]).push(["set", "user:email", userEmail]);
        }
      });
    }
    api.get<{ connected: boolean }>("/api/integrations/fortnox/status", { silent: true })
      .then((s) => setFortnoxConnected(s.connected))
      .catch(() => {});
    api.get<{ openai_configured: boolean }>("/api/integrations/config", { silent: true })
      .then((s) => setOpenaiConnected(s.openai_configured))
      .catch(() => {});
    api.get<{ allowed_modules: string[]; plan_modules: string[]; plan?: string; organization?: { plan: string } }>("/api/auth/me", { silent: true })
      .then((me) => {
        setAllowedModules(me.allowed_modules);
        setPlanModules(me.plan_modules);
        const plan = me.plan ?? me.organization?.plan ?? null;
        if (plan) setUserPlan(plan);
        if (
          me.allowed_modules.length === 1 &&
          me.allowed_modules[0] === "pos"
        ) {
          router.push("/register");
        }
      })
      .catch(() => {});
  }, []);

  function isActive(href: string) {
    if (!isClient) return false;
    if (href === "/dashboard") return pathname === "/dashboard";
    return pathname === href || pathname.startsWith(href + "/");
  }

  function toggleSection(key: string) {
    const next = expandedSection === key ? null : key;
    setExpandedSection(next);
    if (next) localStorage.setItem("vf-sidebar-section", next);
  }

  useEffect(() => {
    const section = getSectionForPath(pathname);
    if (section && section !== expandedSection) {
      setExpandedSection(section);
      localStorage.setItem("vf-sidebar-section", section);
    }
  }, [pathname]);

  async function handleSignOut() {
    try {
      if (isSupabaseConfigured) await supabase.auth.signOut();
    } catch {}
    router.push(`/${locale}/auth/login`);
  }

  function openSearch() {
    document.dispatchEvent(
      new KeyboardEvent("keydown", { key: "k", metaKey: true, bubbles: true })
    );
  }

  const avatarLetter = isClient && (displayName || email) ? (displayName ?? email)![0].toUpperCase() : "?";
  const branding = useBranding();

  const visibleSections = allowedModules.includes("*")
    ? SIDEBAR_SECTIONS
    : SIDEBAR_SECTIONS.filter((s) => s.modules.some((m) => allowedModules.includes(m)));

  const lockedSections = (planModules.includes("*") || allowedModules.includes("*"))
    ? []
    : SIDEBAR_SECTIONS.filter(
        (s) =>
          !s.modules.some((m) => allowedModules.includes(m)) &&
          !s.modules.some((m) => planModules.includes(m))
      );

  /* ── Sidebar content ────────────────────────────────────────────────────── */
  const SidebarContent = () => (
    <>
      {/* Logo */}
      <div className={styles.logoBar}>
        {branding.logo_url ? (
          <img src={branding.logo_url} alt={branding.app_name} className={styles.logoImg} />
        ) : (
          <div className={styles.logoIcon}
            style={{ background: `linear-gradient(135deg, ${branding.primary_color}, ${branding.accent_color})` }}>
            <Zap className="h-3.5 w-3.5 text-white" />
          </div>
        )}
        <span className={styles.logoText}
          style={{ background: `linear-gradient(to right, ${branding.primary_color}, ${branding.accent_color})`, WebkitBackgroundClip: "text", WebkitTextFillColor: "transparent" }}>
          {branding.app_name}
        </span>
        {isClient && fortnoxConnected && (
          <span className={styles.logoBadge}>FX</span>
        )}
        <button className={styles.closeBtn} onClick={() => setSidebarOpen(false)}>
          <X className="h-4 w-4" />
        </button>
      </div>

      {/* Nav sections */}
      <nav className={styles.nav}>
        {visibleSections.map((section) => {
          const isExpanded = expandedSection === section.key;
          const hasActive = section.items.some(item => isActive(item.href));
          const SectionIcon = section.icon;
          return (
            <div key={section.key}>
              <button
                onClick={() => toggleSection(section.key)}
                className={cx(styles.sectionBtn, hasActive && styles.sectionBtnActive)}
              >
                <SectionIcon className={cx(styles.sectionIcon, hasActive && styles.sectionIconActive)} />
                <span className={styles.sectionLabel}>{section.label}</span>
                <ChevronRight className={cx(styles.sectionChevron, isExpanded && styles.sectionChevronOpen)} />
              </button>
              {isExpanded && (
                <div className={styles.itemList}>
                  {section.items
                    .filter(item => allowedModules.includes("*") || allowedModules.includes(item.module))
                    .map(({ href, icon: Icon, key }) => {
                    const active = isActive(href);
                    return (
                      <Link
                        key={href}
                        href={href}
                        onClick={() => setSidebarOpen(false)}
                        className={cx(styles.navItem, active && styles.navItemActive)}
                      >
                        <Icon className={cx(styles.navItemIcon, active && styles.navItemIconActive)} />
                        {t(key as Parameters<typeof t>[0])}
                      </Link>
                    );
                  })}
                </div>
              )}
            </div>
          );
        })}
        {lockedSections.length > 0 && (
          <>
            <div className={styles.lockedDivider} />
            {lockedSections.map((section) => {
              const SectionIcon = section.icon;
              return (
                <div key={section.key} className={styles.lockedSection}>
                  <SectionIcon className={cx(styles.sectionIcon)} />
                  <span className={cx(styles.sectionLabel, "vf-text-2")}>{section.label}</span>
                  <span className={styles.lockedBadge}>
                    <Lock className={styles.lockedIcon} />
                    PRO
                  </span>
                </div>
              );
            })}
          </>
        )}
      </nav>

      {/* Bottom */}
      <div className={styles.sidebarBottom}>
        <div className={styles.themeRow}>
          <ThemeToggle />
        </div>

        {isClient && (
          <div className={styles.aiStatus}>
            <span className={cx(styles.aiDot, openaiConnected ? styles.aiDotConnected : styles.aiDotDisconnected)} />
            <span className={styles.aiLabel}>
              AI {openaiConnected ? "connected" : "not configured"}
            </span>
          </div>
        )}

        <div className={styles.localeRow}>
          {LOCALES.map(({ code, label }) => (
            <button
              key={code}
              onClick={() => router.replace(pathname, { locale: code })}
              className={cx(styles.localeBtn, isClient && locale === code && styles.localeBtnActive)}
            >
              {label}
            </button>
          ))}
        </div>

        <button onClick={handleSignOut} className={styles.accountRow} title="Sign out">
          <div className={styles.avatar}>{avatarLetter}</div>
          <div className={styles.accountInfo}>
            <p className={styles.accountEmail}>
              {isClient ? (displayName ?? email ?? "Account") : "Account"}
            </p>
            <p className={styles.accountPlan}>
              {userPlan === "PRO" ? "Professional" : userPlan === "ENTERPRISE" ? "Enterprise" : userPlan === "FREE" ? "Free" : "Starter"}
            </p>
          </div>
          <div className="flex items-center gap-1 shrink-0">
            <span className="text-[11px] vf-text-m">Sign out</span>
            <LogOut className={styles.logoutIcon} />
          </div>
        </button>
      </div>
    </>
  );

  /* ── Layout ─────────────────────────────────────────────────────────────── */
  return (
    <>
      <MaintenanceBanner />
      {process.env.NEXT_PUBLIC_CRISP_WEBSITE_ID && /^[A-Za-z0-9-]{1,64}$/.test(process.env.NEXT_PUBLIC_CRISP_WEBSITE_ID) && (
        <Script
          id="crisp-chat"
          strategy="afterInteractive"
          dangerouslySetInnerHTML={{
            __html: `
              window.$crisp=[];window.CRISP_WEBSITE_ID="${process.env.NEXT_PUBLIC_CRISP_WEBSITE_ID}";
              (function(){var d=document;var s=d.createElement("script");
              s.src="https://client.crisp.chat/l.js";s.async=1;d.getElementsByTagName("head")[0].appendChild(s);})();
            `,
          }}
        />
      )}

      <div className={styles.shell}>

        {/* Mobile overlay */}
        {sidebarOpen && (
          <div className={styles.overlay} onClick={() => setSidebarOpen(false)} />
        )}

        {/* Sidebar */}
        <aside className={cx(styles.sidebar, sidebarOpen && styles.sidebarOpen)}>
          <SidebarContent />
        </aside>

        {/* Main column */}
        <div className={styles.main}>

          {/* Mobile top bar */}
          <header className={styles.mobileHeader}>
            <button onClick={() => setSidebarOpen(true)} className={styles.menuBtn}>
              <Menu className="h-5 w-5" />
            </button>
            <span className={styles.mobileLogo}>{branding.app_name}</span>
          </header>

          {/* Desktop topbar */}
          <header className={styles.desktopHeader}>
            <h1 className={styles.pageTitle}>{getPageTitle(pathname)}</h1>
            <div className={styles.headerActions}>
              <button onClick={openSearch} className={styles.searchBtn}>
                <Search className={styles.searchIcon} />
                <span className={styles.searchLabel}>Search</span>
                <kbd className={styles.searchKbd}>⌘K</kbd>
              </button>
              <WorkspaceSwitcher />
              <div className={styles.avatarHeader}>{avatarLetter}</div>
            </div>
          </header>

          {/* Page content */}
          <main className={styles.content}>
            <div className={styles.pageWrapper}>
              {children}
            </div>
          </main>
        </div>
      </div>

      <CommandPalette />
      <AiChat />
      <PwaInstallBanner />
      <SessionTimeoutModal />
      {process.env.NODE_ENV === "development" && <DevToolbar />}
    </>
  );
}

export default function AppShell({ children }: { children: React.ReactNode }) {
  return (
    <BrandingProvider>
      <AppShellInner>{children}</AppShellInner>
    </BrandingProvider>
  );
}
