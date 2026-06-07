"use client";

import { api } from "@/lib/api-client";
import { useEffect, useState } from "react";
import { toast } from "sonner";
import { useRouter, useParams } from "next/navigation";
import { cn } from "@/lib/utils";
import {
  Lock, Bell, AlertTriangle, Info, CheckCircle2,
  X, Trash2,
} from "lucide-react";

interface LockScreenAlert {
  id: string;
  title: string;
  message: string;
  severity: "info" | "warning" | "critical";
  is_dismissed: boolean;
  created_at: string;
  dismissed_at?: string;
}

type FilterTab = "all" | "active" | "dismissed";

const SEVERITY_META: Record<LockScreenAlert["severity"], {
  label: string;
  color: string;
  bg: string;
  border: string;
  icon: React.ReactNode;
}> = {
  info: {
    label: "Info",
    color: "text-blue-400",
    bg: "bg-blue-500/10",
    border: "rgba(59,130,246,0.2)",
    icon: <Info className="h-4 w-4 text-blue-400" />,
  },
  warning: {
    label: "Warning",
    color: "text-yellow-400",
    bg: "bg-yellow-500/10",
    border: "rgba(234,179,8,0.2)",
    icon: <AlertTriangle className="h-4 w-4 text-yellow-400" />,
  },
  critical: {
    label: "Critical",
    color: "text-red-400",
    bg: "bg-red-500/10",
    border: "rgba(239,68,68,0.2)",
    icon: <AlertTriangle className="h-4 w-4 text-red-400" />,
  },
};

export default function LockScreenAlertsPage() {
  const router = useRouter();
  const params = useParams<{ locale: string }>();
  const locale = params.locale;

  const [alerts, setAlerts] = useState<LockScreenAlert[]>([]);
  const [loading, setLoading] = useState(true);
  const [tab, setTab] = useState<FilterTab>("all");
  const [dismissingId, setDismissingId] = useState<string | null>(null);
  const [dismissingAll, setDismissingAll] = useState(false);
  const [badgeCount, setBadgeCount] = useState(0);

  useEffect(() => {
    const fetchAll = async () => {
      try {
        const [alertsData, countData] = await Promise.all([
          api.get<LockScreenAlert[]>("/api/lock-screen-alerts"),
          api.get<{ count: number }>("/api/lock-screen-alerts/count").catch(() => ({ count: 0 })),
        ]);
        setAlerts(alertsData);
        setBadgeCount(countData.count);
      } catch (e: unknown) {
        const err = e as { status?: number; message?: string };
        if (err.status === 401) { router.push(`/${locale}/auth/login`); return; }
        toast.error(err.message ?? "Failed to load alerts");
      } finally {
        setLoading(false);
      }
    };
    fetchAll();
  }, [locale, router]);

  async function handleDismiss(id: string) {
    setDismissingId(id);
    try {
      await api.post(`/api/lock-screen-alerts/${id}/dismiss`, {});
      setAlerts((prev) => prev.map((a) => a.id === id ? { ...a, is_dismissed: true, dismissed_at: new Date().toISOString() } : a));
      setBadgeCount((c) => Math.max(0, c - 1));
      toast.success("Alert dismissed");
    } catch (e: unknown) {
      const err = e as { status?: number; message?: string };
      if (err.status === 401) { router.push(`/${locale}/auth/login`); return; }
      toast.error(err.message ?? "Failed to dismiss alert");
    } finally {
      setDismissingId(null);
    }
  }

  async function handleDismissAll() {
    const activeCount = alerts.filter((a) => !a.is_dismissed).length;
    if (activeCount === 0) { toast.info("No active alerts to dismiss"); return; }
    setDismissingAll(true);
    try {
      await api.post("/api/lock-screen-alerts/dismiss-all", {});
      setAlerts((prev) => prev.map((a) => ({ ...a, is_dismissed: true, dismissed_at: new Date().toISOString() })));
      setBadgeCount(0);
      toast.success(`Dismissed ${activeCount} alert${activeCount === 1 ? "" : "s"}`);
    } catch (e: unknown) {
      const err = e as { status?: number; message?: string };
      if (err.status === 401) { router.push(`/${locale}/auth/login`); return; }
      toast.error(err.message ?? "Failed to dismiss all alerts");
    } finally {
      setDismissingAll(false);
    }
  }

  const filtered = alerts.filter((a) => {
    if (tab === "active") return !a.is_dismissed;
    if (tab === "dismissed") return a.is_dismissed;
    return true;
  });

  const activeCount = alerts.filter((a) => !a.is_dismissed).length;
  const criticalCount = alerts.filter((a) => a.severity === "critical" && !a.is_dismissed).length;

  const TABS: { key: FilterTab; label: string; count: number }[] = [
    { key: "all", label: "All", count: alerts.length },
    { key: "active", label: "Active", count: activeCount },
    { key: "dismissed", label: "Dismissed", count: alerts.length - activeCount },
  ];

  return (
    <div className="space-y-6">

      {/* Header */}
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div className="flex items-center gap-3">
          <div>
            <div className="flex items-center gap-2">
              <h1 className="text-xl font-bold tracking-tight vf-text-1">Lock Screen Alerts</h1>
              {badgeCount > 0 && (
                <span className="flex h-5 min-w-5 items-center justify-center rounded-full bg-red-500 px-1.5 text-[10px] font-bold text-white">
                  {badgeCount > 99 ? "99+" : badgeCount}
                </span>
              )}
            </div>
            <p className="text-xs vf-text-m mt-0.5">Alerts displayed on your device lock screen</p>
          </div>
        </div>
        {activeCount > 0 && (
          <button
            disabled={dismissingAll}
            onClick={handleDismissAll}
            className="flex items-center gap-1.5 rounded-xl border border-red-500/20 bg-red-500/5 px-3 py-2 text-xs font-semibold text-red-400 hover:bg-red-500/10 transition-colors disabled:opacity-50"
          >
            <Trash2 className="h-3.5 w-3.5" />
            {dismissingAll ? "Dismissing…" : `Dismiss All (${activeCount})`}
          </button>
        )}
      </div>

      {/* Critical banner */}
      {!loading && criticalCount > 0 && (
        <div className="flex items-start gap-3 rounded-xl p-4 bg-red-500/[0.06] border border-red-500/20">
          <AlertTriangle className="h-4 w-4 text-red-400 mt-0.5 shrink-0" />
          <p className="text-xs text-red-300">
            <span className="font-bold">{criticalCount} critical alert{criticalCount === 1 ? "" : "s"}</span> require your attention.
            Resolve these as soon as possible.
          </p>
        </div>
      )}

      {/* KPI strip */}
      {!loading && (
        <div className="grid grid-cols-3 gap-3">
          {[
            { label: "Total", value: alerts.length, color: "text-indigo-400", bg: "bg-indigo-500/10", icon: <Bell className="h-4 w-4" /> },
            { label: "Active", value: activeCount, color: activeCount > 0 ? "text-amber-400" : "text-emerald-400", bg: activeCount > 0 ? "bg-amber-500/10" : "bg-emerald-500/10", icon: <AlertTriangle className="h-4 w-4" /> },
            { label: "Critical", value: criticalCount, color: criticalCount > 0 ? "text-red-400" : "text-emerald-400", bg: criticalCount > 0 ? "bg-red-500/10" : "bg-emerald-500/10", icon: <Lock className="h-4 w-4" /> },
          ].map(({ label, value, color, bg, icon }) => (
            <div key={label} className="vf-section p-4" >
              <div className={cn("inline-flex h-9 w-9 items-center justify-center rounded-xl mb-3", bg, color)}>
                {icon}
              </div>
              <p className="text-[10px] font-semibold vf-text-m uppercase tracking-wide mb-1">{label}</p>
              <p className="text-xl font-bold tabular-nums vf-text-1">{value}</p>
            </div>
          ))}
        </div>
      )}

      {/* Filter tabs */}
      <div className="flex gap-1 rounded-xl p-1" >
        {TABS.map((t) => (
          <button
            key={t.key}
            onClick={() => setTab(t.key)}
            className={cn(
              "flex flex-1 items-center justify-center gap-1.5 rounded-lg py-2 text-xs font-semibold transition-colors",
              tab === t.key
                ? "bg-indigo-500 text-white shadow-sm"
                : "vf-text-m hover:vf-text-1"
            )}
          >
            {t.label}
            <span className={cn(
              "rounded-full px-1.5 py-0.5 text-[10px] font-bold",
              tab === t.key ? "bg-white/20 text-white" : "bg-indigo-500/10 text-indigo-400"
            )}>
              {t.count}
            </span>
          </button>
        ))}
      </div>

      {/* Alerts list */}
      <div className="space-y-2">
        {loading ? (
          Array.from({ length: 4 }).map((_, i) => (
            <div key={i} className="vf-section p-4" >
              <div className="flex gap-3">
                <div className="h-9 w-9 skeleton rounded-xl shrink-0" />
                <div className="flex-1 space-y-2">
                  <div className="h-4 w-48 skeleton rounded" />
                  <div className="h-3 w-64 skeleton rounded" />
                </div>
              </div>
            </div>
          ))
        ) : filtered.length === 0 ? (
          <div className="py-16 text-center">
            <div className="mx-auto mb-3 flex h-12 w-12 items-center justify-center rounded-2xl"
              >
              {tab === "dismissed" ? (
                <CheckCircle2 className="h-6 w-6 text-emerald-400" />
              ) : (
                <Bell className="h-6 w-6 vf-text-m" />
              )}
            </div>
            <p className="text-sm font-medium vf-text-2">
              {tab === "all" ? "No alerts" : tab === "active" ? "No active alerts" : "No dismissed alerts"}
            </p>
            <p className="text-xs vf-text-m mt-1">
              {tab === "active" ? "All caught up — no alerts require attention" : "Alerts will appear here"}
            </p>
          </div>
        ) : (
          filtered.map((alert) => {
            const meta = SEVERITY_META[alert.severity];
            const isDismissing = dismissingId === alert.id;
            return (
              <div
                key={alert.id}
                className={cn("vf-section p-4 transition-opacity", alert.is_dismissed && "opacity-60")}
                style={{ borderRadius: 14, borderLeft: `3px solid ${meta.border.replace("rgba", "rgb").replace(/,\s*[\d.]+\)/, ")")}` }}
              >
                <div className="flex items-start gap-3">
                  <div className={cn("flex h-9 w-9 shrink-0 items-center justify-center rounded-xl mt-0.5", meta.bg)}>
                    {meta.icon}
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 flex-wrap">
                      <p className="text-[13px] font-semibold vf-text-1">{alert.title}</p>
                      <span className={cn("rounded-full px-2 py-0.5 text-[10px] font-semibold", meta.bg, meta.color)}>
                        {meta.label}
                      </span>
                      {alert.is_dismissed && (
                        <span className="rounded-full bg-emerald-500/10 px-2 py-0.5 text-[10px] font-semibold text-emerald-400">
                          Dismissed
                        </span>
                      )}
                    </div>
                    <p className="text-xs vf-text-m mt-0.5">{alert.message}</p>
                    <p className="text-[11px] vf-text-m mt-1">
                      {new Date(alert.created_at).toLocaleString()}
                      {alert.dismissed_at && ` · Dismissed ${new Date(alert.dismissed_at).toLocaleString()}`}
                    </p>
                  </div>
                  {!alert.is_dismissed && (
                    <button
                      disabled={isDismissing || dismissingAll}
                      onClick={() => handleDismiss(alert.id)}
                      className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg transition-colors hover:bg-red-500/10 hover:text-red-400 vf-text-m disabled:opacity-50"
                      title="Dismiss alert"
                    >
                      <X className={cn("h-3.5 w-3.5", isDismissing && "animate-spin")} />
                    </button>
                  )}
                </div>
              </div>
            );
          })
        )}
      </div>
    </div>
  );
}
