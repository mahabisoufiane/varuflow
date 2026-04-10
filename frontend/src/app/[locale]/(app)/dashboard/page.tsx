"use client";

import { api } from "@/lib/api-client";
import { Link } from "@/i18n/navigation";
import { useEffect, useState, useId } from "react";
import {
  AlertTriangle, ArrowRight, ArrowUpRight, ArrowDownRight,
  FileText, Package, Plus, ShoppingCart, TrendingUp,
  Users, Zap, CheckCircle2, Activity,
} from "lucide-react";
import AiActionCards from "@/components/app/AiActionCards";
import { cn } from "@/lib/utils";

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
function Sparkline({ data, color = "#6366f1", w = 72, h = 30 }: {
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
          <stop offset="0%" stopColor={color} stopOpacity="0.3" />
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
    <div className="flex items-end gap-[3px] h-9">
      {data.map((v, i) => {
        const h = Math.max(6, (v / max) * 100);
        const isLast = i === data.length - 1;
        return (
          <div
            key={i}
            style={{ height: `${h}%` }}
            className={cn("flex-1 rounded-[3px] transition-all", isLast ? "bg-indigo-400" : "bg-white/[0.10]")}
          />
        );
      })}
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

  const [now, setNow] = useState<Date | null>(null);
  const [todayLabel, setTodayLabel] = useState("");
  const [movementDates, setMovementDates] = useState<Record<string, string>>({});

  useEffect(() => {
    const d = new Date();
    setNow(d);
    setTodayLabel(d.toLocaleDateString("sv-SE", { weekday: "long", day: "numeric", month: "long" }));
  }, []);

  useEffect(() => {
    Promise.all([
      api.get<StockLevel[]>("/api/inventory/stock?low_stock_only=true").catch(() => [] as StockLevel[]),
      api.get<Invoice[]>("/api/invoicing/invoices?status=SENT").catch(() => [] as Invoice[]),
      api.get<Movement[]>("/api/inventory/movements?limit=8").catch(() => [] as Movement[]),
      api.get<AnalyticsOverview>("/api/analytics/overview").catch(() => null),
    ]).then(([stock, invoices, movements, ov]) => {
      setLowStock(stock.slice(0, 6));
      setOpenInvoices(invoices.slice(0, 6));
      setRecentMovements(movements);
      setOverview(ov);
      const dates: Record<string, string> = {};
      for (const m of movements) {
        dates[m.id] = new Date(m.created_at).toLocaleDateString("sv-SE");
      }
      setMovementDates(dates);
    }).finally(() => setLoading(false));
  }, []);

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
        <div className="space-y-1.5"><Sk className="h-3 w-28" /><Sk className="h-6 w-20" /></div>
        <div className="flex gap-2"><Sk className="h-8 w-24 rounded-lg" /><Sk className="h-8 w-24 rounded-lg" /></div>
      </div>
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        {[0,1,2,3].map(i => <Sk key={i} className="h-28 rounded-xl" />)}
      </div>
      <div className="grid md:grid-cols-3 gap-4">
        <Sk className="md:col-span-2 h-52 rounded-xl" />
        <Sk className="h-52 rounded-xl" />
      </div>
      <div className="grid md:grid-cols-2 gap-4">
        <Sk className="h-64 rounded-xl" /><Sk className="h-64 rounded-xl" />
      </div>
    </div>
  );

  /* ── Page ────────────────────────────────────────────────────────────── */
  return (
    <div className="space-y-5">

      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <p className="text-[11px] text-slate-600 capitalize tracking-widest" suppressHydrationWarning>
            {todayLabel}
          </p>
          <h1 className="text-xl font-bold text-slate-100 tracking-tight">Overview</h1>
        </div>
        <div className="flex gap-2">
          <Link href="/inventory/products/new"
            className="vf-btn-ghost text-xs px-3 py-1.5 h-auto">
            <Plus className="h-3.5 w-3.5" />Product
          </Link>
          <Link href="/invoices/new"
            className="vf-btn text-xs px-3 py-1.5 h-auto">
            <Plus className="h-3.5 w-3.5" />Invoice
          </Link>
        </div>
      </div>

      {/* ── KPI strip ──────────────────────────────────────────────────────── */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <KpiCard
          label="Outstanding"
          value={`${fmt(outstanding)} kr`}
          sub={`${openInvoices.length} open invoice${openInvoices.length !== 1 ? "s" : ""}`}
          trend={overdueCount > 0 ? { label: `${overdueCount} overdue`, up: false } : undefined}
          icon={<FileText className="h-4 w-4" />}
          iconCls="text-indigo-400 bg-indigo-500/10"
          href="/invoices?status=SENT"
          spark={revData}
          sparkColor="#6366f1"
        />
        <KpiCard
          label="Invoiced this month"
          value={`${fmt(thisMonth)} kr`}
          sub="revenue"
          trend={lastMonth > 0 ? { label: `${revDelta > 0 ? "+" : ""}${revDelta}% vs last month`, up: revDelta >= 0 } : undefined}
          icon={<TrendingUp className="h-4 w-4" />}
          iconCls="text-emerald-400 bg-emerald-500/10"
          href="/analytics"
          spark={revData}
          sparkColor="#10b981"
        />
        <KpiCard
          label="Low stock"
          value={String(lowStock.length)}
          sub="items need reorder"
          trend={lowStock.length > 0
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

      {/* ── Hero + Quick actions ────────────────────────────────────────────── */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">

        {/* Dark hero card */}
        <div className="md:col-span-2 relative overflow-hidden rounded-xl border border-white/[0.08] bg-vf-surface p-6 shadow-elevated">
          <div className="pointer-events-none absolute inset-0 overflow-hidden">
            <div className="absolute -top-12 -right-12 h-56 w-56 rounded-full bg-indigo-600/10 blur-3xl" />
            <div className="absolute bottom-0 left-4 h-40 w-40 rounded-full bg-violet-600/8 blur-2xl" />
          </div>
          <div className="relative">
            <div className="flex items-start justify-between mb-5">
              <div>
                <p className="text-[10px] text-slate-600 font-semibold uppercase tracking-[0.14em]">Total receivables</p>
                <p className="mt-1.5 text-[40px] font-bold tracking-tight leading-none text-white tabular-nums">
                  {fmt(outstanding)}
                  <span className="ml-1.5 text-xl font-normal text-slate-600">SEK</span>
                </p>
                <p className="mt-2 text-sm text-slate-500">
                  {openInvoices.length} {openInvoices.length === 1 ? "invoice" : "invoices"} awaiting payment
                </p>
              </div>
              {overdueCount > 0 && (
                <div className="flex items-center gap-1.5 rounded-full border border-red-500/25 bg-red-500/10 px-3 py-1.5">
                  <AlertTriangle className="h-3.5 w-3.5 text-red-400" />
                  <span className="text-[11px] font-semibold text-red-300">{overdueCount} overdue</span>
                </div>
              )}
            </div>

            {revData.length > 1 && (
              <div className="mb-5">
                <p className="text-[10px] text-slate-600 uppercase tracking-[0.12em] mb-2.5">
                  Monthly invoiced · last {revData.length} months
                </p>
                <MiniBar data={revData} />
              </div>
            )}

            {collectedThisMonth > 0 && (
              <div className="mb-5 inline-flex items-center gap-2 rounded-lg border border-emerald-500/20 bg-emerald-500/10 px-3 py-2">
                <CheckCircle2 className="h-3.5 w-3.5 text-emerald-400" />
                <span className="text-[11px] text-emerald-300 font-medium">
                  {fmt(collectedThisMonth)} kr collected this month
                </span>
              </div>
            )}

            <div className="flex items-center gap-2">
              <Link href="/invoices?status=SENT"
                className="inline-flex items-center gap-1.5 rounded-lg bg-indigo-500/15 border border-indigo-500/20 px-3.5 py-2 text-xs font-semibold text-indigo-300 hover:bg-indigo-500/25 transition-colors">
                View invoices <ArrowUpRight className="h-3 w-3" />
              </Link>
              <Link href="/analytics"
                className="inline-flex items-center gap-1.5 rounded-lg bg-white/5 px-3.5 py-2 text-xs font-medium text-slate-500 hover:bg-white/10 hover:text-slate-300 transition-colors">
                Analytics <ArrowRight className="h-3 w-3" />
              </Link>
            </div>
          </div>
        </div>

        {/* Quick actions */}
        <div className="rounded-xl border border-white/[0.08] bg-vf-surface p-4 flex flex-col">
          <p className="text-[10px] font-semibold text-slate-600 uppercase tracking-widest mb-3">Quick actions</p>
          <div className="flex flex-col gap-[2px] flex-1">
            {[
              { href: "/invoices/new",           icon: FileText,     label: "New invoice",   col: "text-indigo-400 bg-indigo-500/10"  },
              { href: "/inventory/products/new", icon: Package,      label: "Add product",   col: "text-amber-400 bg-amber-500/10"    },
              { href: "/customers/new",          icon: Users,        label: "Add customer",  col: "text-emerald-400 bg-emerald-500/10" },
              { href: "/pos",                    icon: ShoppingCart, label: "Open register", col: "text-violet-400 bg-violet-500/10"  },
              { href: "/ai",                     icon: Zap,          label: "AI insights",   col: "text-indigo-400 bg-indigo-500/10"  },
            ].map(({ href, icon: Icon, label, col }) => (
              <Link key={href} href={href}
                className="flex items-center gap-3 rounded-lg px-3 py-2.5 text-[13px] font-medium text-slate-400 hover:bg-white/[0.05] hover:text-slate-200 transition-colors group">
                <span className={cn("inline-flex h-7 w-7 shrink-0 items-center justify-center rounded-lg", col)}>
                  <Icon className="h-3.5 w-3.5" />
                </span>
                {label}
                <ArrowRight className="ml-auto h-3.5 w-3.5 text-slate-700 group-hover:text-slate-500 transition-colors" />
              </Link>
            ))}
          </div>
        </div>
      </div>

      {/* ── Invoices + Low stock ────────────────────────────────────────────── */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">

        {/* Awaiting payment */}
        <div className="rounded-xl border border-white/[0.08] bg-vf-surface overflow-hidden">
          <div className="flex items-center justify-between px-5 py-3.5 border-b border-white/[0.08]">
            <h2 className="flex items-center gap-2 text-[13px] font-semibold text-slate-200">
              <FileText className="h-4 w-4 text-indigo-400" />Awaiting payment
            </h2>
            <Link href="/invoices" className="flex items-center gap-1 text-xs text-slate-600 hover:text-slate-300 transition-colors">
              All <ArrowRight className="h-3 w-3" />
            </Link>
          </div>
          {openInvoices.length === 0 ? (
            <div className="py-10 text-center">
              <CheckCircle2 className="mx-auto h-8 w-8 text-emerald-500/30 mb-2" />
              <p className="text-sm text-slate-600">No outstanding invoices</p>
            </div>
          ) : (
            <div className="divide-y divide-white/[0.04]">
              {openInvoices.map((inv) => {
                const overdue = now != null && new Date(inv.due_date) < now;
                return (
                  <div key={inv.id} className="flex items-center gap-3 px-5 py-3 hover:bg-white/[0.03] transition-colors">
                    {overdue
                      ? <span className="shrink-0 rounded-full bg-red-500/10 border border-red-500/20 px-1.5 py-0.5 text-[10px] font-semibold text-red-400 leading-none">Overdue</span>
                      : <span className="h-1.5 w-1.5 rounded-full bg-indigo-400 shrink-0" />
                    }
                    <div className="flex-1 min-w-0">
                      <Link href={`/invoices/${inv.id}`}
                        className="text-[13px] font-medium text-slate-200 hover:text-indigo-400 transition-colors">
                        {inv.invoice_number}
                      </Link>
                      <p className="text-xs text-slate-600 truncate">{inv.customer.company_name}</p>
                    </div>
                    <div className="text-right shrink-0">
                      <p className="font-mono text-[13px] font-semibold text-slate-200">{fmt(Number(inv.total_sek))} kr</p>
                      <p className="text-[11px] text-slate-600">Due {inv.due_date}</p>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>

        {/* Low stock */}
        <div className="rounded-xl border border-white/[0.08] bg-vf-surface overflow-hidden">
          <div className="flex items-center justify-between px-5 py-3.5 border-b border-white/[0.08]">
            <h2 className="flex items-center gap-2 text-[13px] font-semibold text-slate-200">
              <Package className="h-4 w-4 text-amber-400" />Low stock alerts
            </h2>
            <Link href="/inventory" className="flex items-center gap-1 text-xs text-slate-600 hover:text-slate-300 transition-colors">
              All <ArrowRight className="h-3 w-3" />
            </Link>
          </div>
          {lowStock.length === 0 ? (
            <div className="py-10 text-center">
              <CheckCircle2 className="mx-auto h-8 w-8 text-emerald-500/30 mb-2" />
              <p className="text-sm text-slate-600">All products well-stocked</p>
            </div>
          ) : (
            <div className="divide-y divide-white/[0.04]">
              {lowStock.map((sl, i) => {
                const ratio = sl.min_threshold > 0 ? sl.quantity / sl.min_threshold : 1;
                const urgent = ratio <= 0.5;
                return (
                  <div key={i} className="flex items-center gap-3 px-5 py-3 hover:bg-white/[0.03] transition-colors">
                    <div className={cn(
                      "shrink-0 flex h-7 w-7 items-center justify-center rounded-lg",
                      urgent ? "bg-red-500/10" : "bg-amber-500/10"
                    )}>
                      <AlertTriangle className={cn("h-3.5 w-3.5", urgent ? "text-red-400" : "text-amber-400")} />
                    </div>
                    <div className="flex-1 min-w-0">
                      <p className="text-[13px] font-medium text-slate-200 truncate">{sl.product.name}</p>
                      <p className="text-xs text-slate-600">{sl.product.sku} · {sl.warehouse.name}</p>
                    </div>
                    <div className="text-right shrink-0">
                      <p className={cn("text-[13px] font-bold tabular-nums", urgent ? "text-red-400" : "text-amber-400")}>
                        {sl.quantity}
                      </p>
                      <p className="text-[11px] text-slate-600">min {sl.min_threshold}</p>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </div>

      {/* ── AI Action Cards ──────────────────────────────────────────────────── */}
      <AiActionCards />

      {/* ── Recent movements ─────────────────────────────────────────────────── */}
      {recentMovements.length > 0 && (
        <div className="rounded-xl border border-white/[0.08] bg-vf-surface overflow-hidden">
          <div className="flex items-center justify-between px-5 py-3.5 border-b border-white/[0.08]">
            <h2 className="flex items-center gap-2 text-[13px] font-semibold text-slate-200">
              <Activity className="h-4 w-4 text-slate-600" />Recent movements
            </h2>
            <Link href="/inventory/movements"
              className="flex items-center gap-1 text-xs text-slate-600 hover:text-slate-300 transition-colors">
              All <ArrowRight className="h-3 w-3" />
            </Link>
          </div>
          <div className="p-4 grid grid-cols-1 sm:grid-cols-2 gap-2">
            {recentMovements.map((m) => (
              <div key={m.id} className="flex items-center gap-2.5 rounded-lg bg-white/[0.03] border border-white/[0.04] px-3 py-2.5">
                <span className={cn(
                  "shrink-0 w-8 rounded-md py-0.5 text-center text-[10px] font-bold",
                  m.type === "IN"  ? "bg-emerald-500/15 text-emerald-400" :
                  m.type === "OUT" ? "bg-red-500/15 text-red-400" : "bg-white/5 text-slate-500"
                )}>{m.type}</span>
                <span className="flex-1 min-w-0 truncate text-[13px] font-medium text-slate-300">{m.product.name}</span>
                <span className="shrink-0 tabular-nums text-[13px] font-semibold text-slate-400">{m.quantity}</span>
                <span className="shrink-0 text-[11px] text-slate-600">{movementDates[m.id] ?? ""}</span>
              </div>
            ))}
          </div>
        </div>
      )}

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
      className="group relative overflow-hidden rounded-xl border border-white/[0.08] bg-vf-surface p-4 shadow-card hover:border-white/[0.10] hover:bg-vf-elevated transition-all duration-150">
      <div className="flex items-start justify-between mb-3">
        <span className={cn("inline-flex h-8 w-8 items-center justify-center rounded-lg", iconCls)}>{icon}</span>
        {spark && spark.length > 1 && sparkColor && (
          <Sparkline data={spark} color={sparkColor} w={60} h={26} />
        )}
      </div>
      <p className="text-2xl font-bold text-white tracking-tight leading-tight tabular-nums">{value}</p>
      {sub && <p className="text-xs text-slate-600 mt-0.5">{sub}</p>}
      {trend && (
        <p className={cn(
          "mt-2 inline-flex items-center gap-0.5 text-[11px] font-medium",
          trend.up ? "text-emerald-400" : "text-red-400"
        )}>
          {trend.up ? <ArrowUpRight className="h-3 w-3" /> : <ArrowDownRight className="h-3 w-3" />}
          {trend.label}
        </p>
      )}
    </Link>
  );
}
