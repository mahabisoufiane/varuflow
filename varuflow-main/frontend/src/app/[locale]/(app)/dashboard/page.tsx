"use client";

import { api } from "@/lib/api-client";
import { Link } from "@/i18n/navigation";
import { useCallback, useEffect, useState, useId } from "react";
import {
  AlertTriangle, ArrowRight, ArrowUpRight, ArrowDownRight,
  FileText, Package, Plus, ShoppingCart, TrendingUp,
  Users, Zap, CheckCircle2, Activity, RefreshCw,
} from "lucide-react";
import AiActionCards from "@/components/app/AiActionCards";
import OnboardingChecklist from "@/components/app/OnboardingChecklist";
import RecentActivity from "@/components/dashboard/RecentActivity";
import { usePullToRefresh } from "@/hooks/usePullToRefresh";
import { cn } from "@/lib/utils";
import { Reveal } from "@/components/motion";
import { EmptyInvoices } from "@/components/illustrations";
import styles from "./page.module.scss";

/* ── Types ──────────────────────────────────────────────────────────────────── */
interface StockLevel {
  product: { name: string; sku: string };
  warehouse: { name: string };
  quantity: number;
  min_threshold: number;
}
interface Invoice {
  id: string;
  invoice_number: string;
  customer: { company_name: string };
  total_sek: string;
  due_date: string;
  status: string;
}
interface Movement {
  id: string;
  type: string;
  product: { name: string };
  quantity: number;
  created_at: string;
}
interface RevenuePoint { month: string; invoiced: number; collected: number; }
interface AnalyticsOverview { revenue_points: RevenuePoint[]; }

/* ── Helpers ─────────────────────────────────────────────────────────────────── */
function fmt(n: number) {
  return n.toLocaleString("sv-SE", { minimumFractionDigits: 0, maximumFractionDigits: 0 });
}
function pct(a: number, b: number) {
  if (b === 0) return 0;
  return Math.round(((a - b) / b) * 100);
}

/* ── Skeleton ────────────────────────────────────────────────────────────────── */
function Sk({ className }: { className?: string }) {
  return <div className={cn("skeleton", className)} />;
}

/* ── Sparkline ───────────────────────────────────────────────────────────────── */
function Sparkline({ data, color = "var(--vf-brand-primary)", w = 72, h = 30 }: {
  data: number[]; color?: string; w?: number; h?: number;
}) {
  const uid = useId().replace(/:/g, "");
  if (data.length < 2) return <div style={{ width: w, height: h }} />;
  const max = Math.max(...data, 1);
  const min = Math.min(...data, 0);
  const range = max - min || 1;
  const xs = data.map((_, i) => (i / (data.length - 1)) * w);
  const ys = data.map((v) => h - ((v - min) / range) * (h - 4) - 2);
  const pts = data.map((_, i) => `${xs[i]},${ys[i]}`);
  const line = `M${pts.join(" L")}`;
  const area = `${line} L${w},${h} L0,${h} Z`;
  return (
    <svg width={w} height={h} viewBox={`0 0 ${w} ${h}`} fill="none">
      <defs>
        <linearGradient id={`g${uid}`} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={color} stopOpacity="0.35" />
          <stop offset="100%" stopColor={color} stopOpacity="0" />
        </linearGradient>
      </defs>
      <path d={area} fill={`url(#g${uid})`} />
      <path d={line} stroke={color} strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

/* ── MiniBar ─────────────────────────────────────────────────────────────────── */
function MiniBar({ data }: { data: number[] }) {
  if (!data.length) return null;
  const max = Math.max(...data, 1);
  return (
    <div className="flex items-end gap-[3px] h-10">
      {data.map((v, i) => {
        const h = Math.max(8, (v / max) * 100);
        const isLast = i === data.length - 1;
        return (
          <div
            key={i}
            style={{ height: `${h}%` }}
            className={cn(
              "flex-1 rounded-[3px] transition-all",
              isLast ? "bg-[var(--vf-brand-primary)]" : "bg-[var(--vf-brand-primary)]/20"
            )}
          />
        );
      })}
    </div>
  );
}

/* ── Widget error state ─────────────────────────────────────────────────────
   Deliberately styled UNLIKE any empty state: danger-tinted dashed panel with
   a warning icon and a retry action. Empty = calm/neutral ("All clear" with an
   emerald check); failed = alarmed and actionable. The two must never be
   confusable — that distinction is the point. */
function WidgetError({ onRetry, compact = false }: { onRetry: () => void; compact?: boolean }) {
  return (
    <div className={cn(
      "m-4 flex flex-col items-center justify-center gap-2 rounded-lg border border-dashed",
      "border-[var(--vf-danger)]/40 bg-[var(--vf-danger-bg)]",
      compact ? "py-4" : "py-8"
    )}>
      <AlertTriangle className="h-4 w-4 text-[var(--vf-danger)]" />
      <p className="text-xs font-medium text-[var(--vf-danger)]">Couldn&apos;t load</p>
      <button
        type="button"
        onClick={onRetry}
        className="inline-flex items-center gap-1 text-xs font-semibold text-[var(--vf-danger)] underline underline-offset-2 hover:opacity-80"
      >
        <RefreshCw className="h-3 w-3" />Retry
      </button>
    </div>
  );
}

/* ════════════════════════════════════════════════════════════════════════════ */
export default function DashboardPage() {
  const [lowStock, setLowStock] = useState<StockLevel[]>([]);
  const [openInvoices, setOpenInvoices] = useState<Invoice[]>([]);
  const [recentMovements, setRecentMovements] = useState<Movement[]>([]);
  const [overview, setOverview] = useState<AnalyticsOverview | null>(null);
  const [loading, setLoading] = useState(true);
  // Per-source failure flags (P0): a failed fetch must NEVER render as a zero —
  // "0 kr outstanding" and "the API is down" are different facts. Each source
  // fails independently: the other widgets keep their data, the failed one
  // shows an explicit error with its own retry.
  const [errs, setErrs] = useState({ stock: false, invoices: false, movements: false, overview: false });

  const [now, setNow] = useState<Date | null>(null);
  const [todayLabel, setTodayLabel] = useState("");
  const [movementDates, setMovementDates] = useState<Record<string, string>>({});

  const loadStock = useCallback(async () => {
    try {
      const stock = await api.get<StockLevel[]>("/api/inventory/stock?low_stock_only=true");
      setLowStock(stock.slice(0, 6));
      setErrs((e) => ({ ...e, stock: false }));
    } catch {
      setErrs((e) => ({ ...e, stock: true }));
    }
  }, []);

  const loadInvoices = useCallback(async () => {
    try {
      const invoices = await api.get<Invoice[]>("/api/invoicing/invoices?status=SENT");
      setOpenInvoices(invoices.slice(0, 6));
      setErrs((e) => ({ ...e, invoices: false }));
    } catch {
      setErrs((e) => ({ ...e, invoices: true }));
    }
  }, []);

  const loadMovements = useCallback(async () => {
    try {
      const movements = await api.get<Movement[]>("/api/inventory/movements?limit=8");
      setRecentMovements(movements);
      const dates: Record<string, string> = {};
      for (const m of movements) {
        dates[m.id] = new Date(m.created_at).toLocaleDateString("sv-SE");
      }
      setMovementDates(dates);
      setErrs((e) => ({ ...e, movements: false }));
    } catch {
      setErrs((e) => ({ ...e, movements: true }));
    }
  }, []);

  const loadOverview = useCallback(async () => {
    try {
      const ov = await api.get<AnalyticsOverview>("/api/analytics/overview");
      setOverview(ov);
      setErrs((e) => ({ ...e, overview: false }));
    } catch {
      setErrs((e) => ({ ...e, overview: true }));
    }
  }, []);

  const loadDashboard = useCallback(async () => {
    // Each loader self-catches, so one failing source never blocks the rest.
    await Promise.all([loadStock(), loadInvoices(), loadMovements(), loadOverview()]);
  }, [loadStock, loadInvoices, loadMovements, loadOverview]);

  useEffect(() => {
    const d = new Date();
    setNow(d);
    setTodayLabel(d.toLocaleDateString("sv-SE", { weekday: "long", day: "numeric", month: "long" }));
  }, []);

  useEffect(() => {
    loadDashboard().finally(() => setLoading(false));
  }, [loadDashboard]);

  // Item 12 — mobile pull-to-refresh. Desktop browsers (no touch) never
  // fire these handlers so the desktop UX is unchanged.
  const { isRefreshing, pullDistance, isPulling, handlers } = usePullToRefresh({
    onRefresh: loadDashboard,
  });
  const pulledPx = isRefreshing ? 48 : pullDistance;
  const pullProgress = Math.min(pullDistance / 60, 1);

  /* ── Derived ─────────────────────────────────────────────────────────── */
  const outstanding = openInvoices.reduce((s, i) => s + Number(i.total_sek), 0);
  const revData = (overview?.revenue_points ?? []).slice(-6).map((r) => Number(r.invoiced));
  const collectedData = (overview?.revenue_points ?? []).slice(-6).map((r) => Number(r.collected));
  const thisMonth = revData.at(-1) ?? 0;
  const lastMonth = revData.at(-2) ?? 0;
  const collectedThisMonth = collectedData.at(-1) ?? 0;
  const revDelta = pct(thisMonth, lastMonth);
  const overdueCount = now ? openInvoices.filter((i) => new Date(i.due_date) < now).length : 0;

  /* ── Loading ─────────────────────────────────────────────────────────── */
  if (loading) return (
    <div className="space-y-5">
      <div className="flex items-center justify-between">
        <div className="space-y-2"><Sk className="h-3 w-32" /><Sk className="h-7 w-24" /></div>
        <div className="flex gap-2"><Sk className="h-9 w-28 rounded-lg" /><Sk className="h-9 w-28 rounded-lg" /></div>
      </div>
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        {[0,1,2,3].map(i => <Sk key={i} className="h-28 rounded-xl" />)}
      </div>
      <div className="grid md:grid-cols-3 gap-4">
        <Sk className="md:col-span-2 h-56 rounded-xl" />
        <Sk className="h-56 rounded-xl" />
      </div>
      <div className="grid md:grid-cols-2 gap-4">
        <Sk className="h-64 rounded-xl" /><Sk className="h-64 rounded-xl" />
      </div>
    </div>
  );

  /* ── Page ────────────────────────────────────────────────────────────── */
  return (
    <div
      {...handlers}
      data-testid="dashboard-pull-root"
      className="relative"
      style={{
        transform: `translateY(${pulledPx}px)`,
        transition: isPulling ? "none" : "transform 200ms ease-out",
      }}
    >
      {/* Pull-to-refresh indicator — absolute, overlaid, hidden above viewport
          by default. Appears during pull + spins while refreshing. */}
      <div
        data-testid="dashboard-pull-indicator"
        aria-hidden={!isPulling && !isRefreshing}
        className="pointer-events-none absolute left-1/2 -translate-x-1/2 flex h-10 w-10 items-center justify-center rounded-full bg-white shadow-md dark:bg-white/10"
        style={{
          top: "-60px",
          opacity: isRefreshing ? 1 : pullProgress,
          transform: `translate(-50%, ${isRefreshing ? 60 : pullProgress * 60}px) rotate(${pullDistance * 4}deg)`,
          transition: isPulling ? "none" : "opacity 200ms, transform 200ms",
        }}
      >
        <RefreshCw className={cn("h-5 w-5", isRefreshing && "animate-spin")} />
      </div>

      <div className="space-y-5">

      {/* ── Header ──────────────────────────────────────────────────────── */}
      <div className="flex items-center justify-between">
        <div>
          <p className="text-[11px] vf-text-m capitalize tracking-widest" suppressHydrationWarning>
            {todayLabel}
          </p>
          <h1 className="text-xl font-bold tracking-tight vf-text-1">Overview</h1>
        </div>
        <div className="flex gap-2">
          <Link href="/inventory/products/new" className="vf-btn-ghost text-xs px-3 h-9">
            <Plus className="h-3.5 w-3.5" />Product
          </Link>
          <Link href="/invoices/new" className="vf-btn text-xs px-3 h-9">
            <Plus className="h-3.5 w-3.5" />Invoice
          </Link>
        </div>
      </div>

      {/* ── Onboarding checklist (self-hides when dismissed or 100% done) ─ */}
      <OnboardingChecklist />

      {/* ── KPI strip ──────────────────────────────────────────────────── */}
      {/* Item 12: mobile stacks vertically (grid-cols-1). Desktop grid
          (md:grid-cols-4) is unchanged — no layout regression. */}
      <Reveal>
      <div className="grid grid-cols-1 md:grid-cols-4 gap-3" data-testid="kpi-strip">
        <KpiCard
          label="Outstanding"
          value={errs.invoices ? "—" : `${fmt(outstanding)} kr`}
          sub={errs.invoices ? "couldn't load" : `${openInvoices.length} open invoice${openInvoices.length !== 1 ? "s" : ""}`}
          trend={!errs.invoices && overdueCount > 0 ? { label: `${overdueCount} overdue`, up: false } : undefined}
          icon={<FileText className="h-4 w-4" />}
          iconCls="text-[var(--vf-brand-primary)] bg-[var(--vf-brand-primary-subtle)]"
          href="/invoices?status=SENT"
          spark={revData}
          sparkColor="var(--vf-brand-primary)"
        />
        <KpiCard
          label="Invoiced this month"
          value={errs.overview ? "—" : `${fmt(thisMonth)} kr`}
          sub={errs.overview ? "couldn't load" : "revenue"}
          trend={!errs.overview && lastMonth > 0 ? { label: `${revDelta > 0 ? "+" : ""}${revDelta}% vs last month`, up: revDelta >= 0 } : undefined}
          icon={<TrendingUp className="h-4 w-4" />}
          iconCls="text-emerald-400 bg-emerald-500/10"
          href="/analytics"
          spark={revData}
          sparkColor="#10b981"
        />
        <KpiCard
          label="Low stock"
          value={errs.stock ? "—" : String(lowStock.length)}
          sub={errs.stock ? "couldn't load" : "items need reorder"}
          trend={errs.stock ? undefined : lowStock.length > 0
            ? { label: "Action needed", up: false }
            : { label: "All stocked", up: true }}
          icon={<Package className="h-4 w-4" />}
          iconCls="text-amber-400 bg-amber-500/10"
          href="/inventory"
        />
        <KpiCard
          label="Cash register"
          value="Open"
          sub="POS terminal"
          icon={<ShoppingCart className="h-4 w-4" />}
          iconCls="text-violet-400 bg-violet-500/10"
          href="/pos"
        />
      </div>
      </Reveal>

      {/* ── Hero + Quick actions ─────────────────────────────────────────── */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">

        {/* Hero card */}
        <div className="md:col-span-2 relative overflow-hidden vf-section p-6">
          {/* Ambient orbs */}
          <div className="pointer-events-none absolute inset-0 overflow-hidden">
            <div className="absolute -top-16 -right-16 h-64 w-64 rounded-full bg-[var(--vf-brand-primary)]/10 blur-3xl" />
            <div className="absolute bottom-0 left-0 h-48 w-48 rounded-full bg-violet-600/8 blur-3xl" />
          </div>
          <div className="relative">
            {errs.invoices || errs.overview ? (
              /* Failed fetch must not fall through to the first-run empty state
                 below — "no invoices yet" and "API down" are different facts. */
              <WidgetError onRetry={() => { loadInvoices(); loadOverview(); }} />
            ) : outstanding === 0 && revData.length === 0 ? (
              /* First-run state — user has no invoices yet */
              <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-6 py-2">
                <div className="flex flex-col items-start gap-4">
                  <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-[var(--vf-brand-primary-subtle)]">
                    <FileText className="h-6 w-6 text-[var(--vf-brand-primary)]" />
                  </div>
                  <div>
                    <p className="text-base font-semibold vf-text-1">Ready to send your first invoice?</p>
                    <p className="mt-1 text-sm vf-text-m">Create an invoice and it will appear here with payment tracking.</p>
                  </div>
                  <div className="flex items-center gap-2">
                    <Link href="/invoices/new" className="vf-btn-secondary text-xs px-3.5 h-8">
                      <Plus className="h-3.5 w-3.5" />Create invoice
                    </Link>
                    <Link href="/customers/new" className="vf-btn-ghost text-xs px-3.5 h-8">
                      Add customer first <ArrowRight className="h-3 w-3" />
                    </Link>
                  </div>
                </div>
                <div className="hidden sm:block w-40 shrink-0 opacity-90">
                  <EmptyInvoices />
                </div>
              </div>
            ) : (
              <>
                <div className="flex items-start justify-between mb-5">
                  <div>
                    <p className="text-[10px] vf-text-m font-semibold uppercase tracking-[0.14em]">
                      Total receivables
                    </p>
                    <p className="mt-1.5 text-[42px] font-bold tracking-tight leading-none tabular-nums vf-text-1">
                      {fmt(outstanding)}
                      <span className="ml-2 text-lg font-normal vf-text-m">SEK</span>
                    </p>
                    <p className="mt-2 text-sm vf-text-m">
                      {openInvoices.length} {openInvoices.length === 1 ? "invoice" : "invoices"} awaiting payment
                    </p>
                  </div>
                  {overdueCount > 0 && (
                    <div className={styles.overdueBadge}>
                      <AlertTriangle className="h-3.5 w-3.5 text-red-400" />
                      <span className="text-[11px] font-semibold text-red-400">{overdueCount} overdue</span>
                    </div>
                  )}
                </div>

                {revData.length > 1 && (
                  <div className="mb-5">
                    <p className="text-[10px] vf-text-m uppercase tracking-[0.12em] mb-2.5">
                      Monthly invoiced · last {revData.length} months
                    </p>
                    <MiniBar data={revData} />
                  </div>
                )}

                {collectedThisMonth > 0 && (
                  <div className={cn("mb-5", styles.collectedBadge)}>
                    <CheckCircle2 className="h-3.5 w-3.5 text-emerald-400" />
                    <span className="text-[11px] text-emerald-500 font-medium">
                      {fmt(collectedThisMonth)} kr collected this month
                    </span>
                  </div>
                )}

                <div className="flex items-center gap-2">
                  <Link href="/invoices?status=SENT"
                    className="vf-btn-secondary text-xs px-3.5 h-8">
                    View invoices <ArrowUpRight className="h-3 w-3" />
                  </Link>
                  <Link href="/analytics"
                    className="vf-btn-ghost text-xs px-3.5 h-8">
                    Analytics <ArrowRight className="h-3 w-3" />
                  </Link>
                </div>
              </>
            )}
          </div>
        </div>

        {/* Quick actions */}
        <div className="vf-section p-4 flex flex-col">
          <p className="text-[10px] font-semibold vf-text-m uppercase tracking-widest mb-3 px-1">
            Quick actions
          </p>
          <div className="flex flex-col gap-[2px] flex-1">
            {[
              { href: "/invoices/new",           icon: FileText,     label: "New invoice",   cls: "text-[var(--vf-brand-primary)] bg-[var(--vf-brand-primary-subtle)]"  },
              { href: "/inventory/products/new", icon: Package,      label: "Add product",   cls: "text-amber-400 bg-amber-500/10"    },
              { href: "/customers/new",          icon: Users,        label: "Add customer",  cls: "text-emerald-400 bg-emerald-500/10" },
              { href: "/pos",                    icon: ShoppingCart, label: "Open register", cls: "text-violet-400 bg-violet-500/10"  },
              { href: "/ai",                     icon: Zap,          label: "AI insights",   cls: "text-[var(--vf-brand-primary)] bg-[var(--vf-brand-primary-subtle)]"  },
            ].map(({ href, icon: Icon, label, cls }) => (
              <Link key={href} href={href}
                className="vf-row flex items-center gap-3 rounded-lg px-3 py-2.5 text-[13px] font-medium vf-text-2 hover:vf-text-1 transition-colors group">
                <span className={cn("inline-flex h-7 w-7 shrink-0 items-center justify-center rounded-lg", cls)}>
                  <Icon className="h-3.5 w-3.5" />
                </span>
                <span className="vf-text-2">{label}</span>
                <ArrowRight className="ml-auto h-3.5 w-3.5 vf-text-m group-hover:vf-text-2 transition-colors" />
              </Link>
            ))}
          </div>
        </div>
      </div>

      {/* ── Invoices + Low stock ─────────────────────────────────────────── */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">

        {/* Awaiting payment */}
        <div className="vf-section">
          <div className="vf-section-header">
            <h2 className="flex items-center gap-2 text-[13px] font-semibold vf-text-1">
              <FileText className="h-4 w-4 text-[var(--vf-brand-primary)]" />Awaiting payment
            </h2>
            <Link href="/invoices" className="flex items-center gap-1 text-xs vf-text-m hover:vf-text-2 transition-colors">
              All <ArrowRight className="h-3 w-3" />
            </Link>
          </div>
          {errs.invoices ? (
            <WidgetError onRetry={loadInvoices} />
          ) : openInvoices.length === 0 ? (
            <div className="py-12 text-center">
              <div className="mx-auto mb-3 flex h-12 w-12 items-center justify-center rounded-full bg-emerald-500/10">
                <CheckCircle2 className="h-6 w-6 text-emerald-400" />
              </div>
              <p className="text-sm font-medium vf-text-2">All clear</p>
              <p className="text-xs vf-text-m mt-0.5">No outstanding invoices</p>
            </div>
          ) : (
            <div className="vf-divide">
              {openInvoices.map((inv) => {
                const overdue = now != null && new Date(inv.due_date) < now;
                return (
                  <div key={inv.id} className="vf-row flex items-center gap-3 px-5 py-3.5">
                    {overdue
                      ? <span className="pill-overdue shrink-0">Overdue</span>
                      : <span className="h-2 w-2 rounded-full bg-[var(--vf-brand-primary)] shrink-0" />
                    }
                    <div className="flex-1 min-w-0">
                      <Link href={`/invoices/${inv.id}`}
                        className="text-[13px] font-medium hover:text-[var(--vf-brand-primary)] transition-colors vf-text-1">
                        {inv.invoice_number}
                      </Link>
                      <p className="text-xs vf-text-m truncate">{inv.customer.company_name}</p>
                    </div>
                    <div className="text-right shrink-0">
                      <p className="font-mono text-[13px] font-semibold vf-text-1">{fmt(Number(inv.total_sek))} kr</p>
                      <p className="text-[11px] vf-text-m">Due {inv.due_date}</p>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>

        {/* Low stock */}
        <div className="vf-section">
          <div className="vf-section-header">
            <h2 className="flex items-center gap-2 text-[13px] font-semibold vf-text-1">
              <Package className="h-4 w-4 text-amber-400" />Low stock alerts
            </h2>
            <Link href="/inventory" className="flex items-center gap-1 text-xs vf-text-m hover:vf-text-2 transition-colors">
              All <ArrowRight className="h-3 w-3" />
            </Link>
          </div>
          {errs.stock ? (
            <WidgetError onRetry={loadStock} />
          ) : lowStock.length === 0 ? (
            <div className="py-12 text-center">
              <div className="mx-auto mb-3 flex h-12 w-12 items-center justify-center rounded-full bg-emerald-500/10">
                <CheckCircle2 className="h-6 w-6 text-emerald-400" />
              </div>
              <p className="text-sm font-medium vf-text-2">Fully stocked</p>
              <p className="text-xs vf-text-m mt-0.5">All products above minimum</p>
            </div>
          ) : (
            <div className="vf-divide">
              {lowStock.map((sl, i) => {
                const ratio = sl.min_threshold > 0 ? sl.quantity / sl.min_threshold : 1;
                const urgent = ratio <= 0.5;
                return (
                  <div key={i} className="vf-row flex items-center gap-3 px-5 py-3.5">
                    <div className={cn(
                      "shrink-0 flex h-8 w-8 items-center justify-center rounded-lg",
                      urgent ? "bg-red-500/10" : "bg-amber-500/10"
                    )}>
                      <AlertTriangle className={cn("h-4 w-4", urgent ? "text-red-400" : "text-amber-400")} />
                    </div>
                    <div className="flex-1 min-w-0">
                      <p className="text-[13px] font-medium truncate vf-text-1">{sl.product.name}</p>
                      <p className="text-xs vf-text-m">{sl.product.sku} · {sl.warehouse.name}</p>
                    </div>
                    <div className="text-right shrink-0">
                      <p className={cn("text-[15px] font-bold tabular-nums", urgent ? "text-red-400" : "text-amber-400")}>
                        {sl.quantity}
                      </p>
                      <p className="text-[11px] vf-text-m">min {sl.min_threshold}</p>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </div>

      {/* ── AI Action Cards ──────────────────────────────────────────────── */}
      <AiActionCards />

      {/* ── Recent movements ─────────────────────────────────────────────── */}
      <div className="vf-section">
        <div className="vf-section-header">
          <h2 className="flex items-center gap-2 text-[13px] font-semibold vf-text-1">
            <Activity className="h-4 w-4 vf-text-m" />Recent movements
          </h2>
          <Link href="/inventory/movements"
            className="flex items-center gap-1 text-xs vf-text-m hover:vf-text-2 transition-colors">
            All <ArrowRight className="h-3 w-3" />
          </Link>
        </div>
        {errs.movements ? (
          <WidgetError onRetry={loadMovements} compact />
        ) : recentMovements.length === 0 ? (
          <div className="py-10 text-center">
            <p className="text-sm font-medium vf-text-2">No stock movements yet</p>
            <p className="text-xs vf-text-m mt-0.5">Add products to inventory to start tracking stock.</p>
            <Link href="/inventory/products/new" className="mt-3 inline-flex items-center gap-1 text-xs text-[var(--vf-brand-primary)] hover:text-[var(--vf-brand-primary)]">
              <Plus className="h-3 w-3" />Add first product
            </Link>
          </div>
        ) : (
          <div className="p-4 grid grid-cols-1 sm:grid-cols-2 gap-2">
            {recentMovements.map((m) => (
              <div key={m.id} className="vf-stat-tile flex items-center gap-2.5">
                <span className={cn(
                  "shrink-0 w-8 rounded-md py-0.5 text-center text-[10px] font-bold",
                  m.type === "IN"  ? "bg-emerald-500/15 text-emerald-500" :
                  m.type === "OUT" ? "bg-red-500/15 text-red-400" : "vf-glass text-slate-500"
                )}>{m.type}</span>
                <span className="flex-1 min-w-0 truncate text-[13px] font-medium vf-text-2">
                  {m.product.name}
                </span>
                <span className="shrink-0 tabular-nums text-[13px] font-semibold vf-text-2">{m.quantity}</span>
                <span className="shrink-0 text-[11px] vf-text-m">{movementDates[m.id] ?? ""}</span>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* ── Recent activity feed (Item 12) — mobile-first but visible on both. */}
      <RecentActivity />

      </div>
    </div>
  );
}

/* ── KpiCard ─────────────────────────────────────────────────────────────────── */
function KpiCard({ label, value, sub, trend, icon, iconCls, href, spark, sparkColor }: {
  label: string; value: string; sub?: string;
  trend?: { label: string; up: boolean };
  icon: React.ReactNode; iconCls: string; href: string;
  spark?: number[]; sparkColor?: string;
}) {
  return (
    <Link href={href}
      className="group relative overflow-hidden vf-section p-4 hover:shadow-card transition-all duration-150 rounded-[14px]">
      <div className="flex items-start justify-between mb-3">
        <span className={cn("inline-flex h-9 w-9 items-center justify-center rounded-xl", iconCls)}>{icon}</span>
        {spark && spark.length > 1 && sparkColor && (
          <Sparkline data={spark} color={sparkColor} w={64} h={28} />
        )}
      </div>
      <p className="text-[11px] vf-text-m font-medium uppercase tracking-wide mb-1">{label}</p>
      <p className="text-xl font-bold tracking-tight leading-tight tabular-nums vf-text-1">{value}</p>
      {sub && <p className="text-xs vf-text-m mt-0.5">{sub}</p>}
      {trend && (
        <p className={cn(
          "mt-2 inline-flex items-center gap-0.5 text-[11px] font-semibold",
          trend.up ? "text-emerald-500" : "text-red-400"
        )}>
          {trend.up ? <ArrowUpRight className="h-3 w-3" /> : <ArrowDownRight className="h-3 w-3" />}
          {trend.label}
        </p>
      )}
    </Link>
  );
}
