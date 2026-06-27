"use client";

import { api } from "@/lib/api-client";
import { useEffect, useState } from "react";
import { toast } from "sonner";
import { useRouter, useParams } from "next/navigation";
import { cn } from "@/lib/utils";
import {
  LayoutGrid, RefreshCw, Smartphone, Apple, Info,
  ToggleLeft, ToggleRight, Maximize2, TrendingUp, AlertTriangle, Lock,
} from "lucide-react";

interface Widget {
  id: string;
  widget_type: "todays_bookings" | "todays_revenue" | "low_stock_alerts" | "lock_screen_alerts";
  platform: "ios" | "android";
  size: "small" | "medium" | "large";
  is_active: boolean;
  snapshot?: Record<string, unknown>;
  last_refreshed_at?: string;
}

const WIDGET_META: Record<Widget["widget_type"], { label: string; description: string; icon: React.ReactNode }> = {
  todays_bookings: {
    label: "Today's Bookings",
    description: "Shows upcoming bookings count and next appointment",
    icon: <LayoutGrid className="h-5 w-5 text-indigo-400" />,
  },
  todays_revenue: {
    label: "Today's Revenue",
    description: "Shows real-time revenue total for today",
    icon: <TrendingUp className="h-5 w-5 text-emerald-400" />,
  },
  low_stock_alerts: {
    label: "Low Stock Alerts",
    description: "Shows count of products below minimum threshold",
    icon: <AlertTriangle className="h-5 w-5 text-amber-400" />,
  },
  lock_screen_alerts: {
    label: "Lock Screen Alerts",
    description: "Critical alerts displayed on your lock screen",
    icon: <Lock className="h-5 w-5 text-rose-400" />,
  },
};

const WIDGET_TYPES: Widget["widget_type"][] = [
  "todays_bookings",
  "todays_revenue",
  "low_stock_alerts",
  "lock_screen_alerts",
];

const PLATFORMS: { value: Widget["platform"]; label: string }[] = [
  { value: "ios", label: "iOS" },
  { value: "android", label: "Android" },
];

const SIZES: { value: Widget["size"]; label: string }[] = [
  { value: "small", label: "Small" },
  { value: "medium", label: "Medium" },
  { value: "large", label: "Large" },
];

const IOS_STEPS = [
  "Long-press your home screen until icons wiggle",
  'Tap the "+" button in the top-left corner',
  'Search for "Varuflow" in the widget gallery',
  "Select your preferred widget size",
  "Tap Add Widget, then Done",
];

const ANDROID_STEPS = [
  "Long-press an empty area on your home screen",
  'Select "Widgets" from the menu',
  "Find Varuflow in the widget list",
  "Long-press and drag the widget to your home screen",
  "Resize as needed and tap outside to confirm",
];

export default function HomeScreenWidgetsPage() {
  const router = useRouter();
  const params = useParams<{ locale: string }>();
  const locale = params.locale;

  const [widgets, setWidgets] = useState<Widget[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState<string | null>(null);
  const [saving, setSaving] = useState<string | null>(null);

  useEffect(() => {
    api.get<Widget[]>("/api/home-screen-widgets")
      .then(setWidgets)
      .catch((e: { status?: number; message?: string }) => {
        if (e.status === 401) {
          router.push(`/${locale}/auth/login`);
          return;
        }
        toast.error(e.message ?? "Failed to load widgets");
      })
      .finally(() => setLoading(false));
  }, [locale, router]);

  // Merge API widgets with defaults for widget types not yet configured
  const allWidgets: (Widget | { widget_type: Widget["widget_type"]; platform: "ios"; size: "medium"; is_active: false; id: null })[] =
    WIDGET_TYPES.map((type) => {
      const existing = widgets.find((w) => w.widget_type === type);
      return existing ?? { widget_type: type, platform: "ios", size: "medium", is_active: false, id: null };
    });

  async function handleToggle(widget: Widget) {
    setSaving(widget.id);
    try {
      const updated = await api.patch<Widget>(`/api/home-screen-widgets/${widget.id}`, {
        is_active: !widget.is_active,
      });
      setWidgets((prev) => prev.map((w) => (w.id === widget.id ? updated : w)));
    } catch (e: unknown) {
      const err = e as { status?: number; message?: string };
      if (err.status === 401) { router.push(`/${locale}/auth/login`); return; }
      toast.error(err.message ?? "Failed to update widget");
    } finally {
      setSaving(null);
    }
  }

  async function handleFieldChange(widget: Widget, field: "platform" | "size", value: string) {
    setSaving(widget.id);
    try {
      const updated = await api.patch<Widget>(`/api/home-screen-widgets/${widget.id}`, { [field]: value });
      setWidgets((prev) => prev.map((w) => (w.id === widget.id ? updated : w)));
    } catch (e: unknown) {
      const err = e as { status?: number; message?: string };
      if (err.status === 401) { router.push(`/${locale}/auth/login`); return; }
      toast.error(err.message ?? "Failed to update widget");
    } finally {
      setSaving(null);
    }
  }

  async function handleCreate(type: Widget["widget_type"]) {
    setSaving(type);
    try {
      const created = await api.post<Widget>("/api/home-screen-widgets", {
        widget_type: type,
        platform: "ios",
        size: "medium",
        is_active: true,
      });
      setWidgets((prev) => [...prev, created]);
      toast.success("Widget enabled");
    } catch (e: unknown) {
      const err = e as { status?: number; message?: string };
      if (err.status === 401) { router.push(`/${locale}/auth/login`); return; }
      toast.error(err.message ?? "Failed to create widget");
    } finally {
      setSaving(null);
    }
  }

  async function handleRefresh(widgetType: Widget["widget_type"]) {
    setRefreshing(widgetType);
    try {
      await api.post(`/api/home-screen-widgets/snapshot/${widgetType}/refresh`, {});
      toast.success("Widget data refreshed");
      const updated = await api.get<Widget[]>("/api/home-screen-widgets");
      setWidgets(updated);
    } catch (e: unknown) {
      const err = e as { status?: number; message?: string };
      if (err.status === 401) { router.push(`/${locale}/auth/login`); return; }
      toast.error(err.message ?? "Failed to refresh widget");
    } finally {
      setRefreshing(null);
    }
  }

  return (
    <div className="space-y-6">

      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold tracking-tight vf-text-1">Home Screen &amp; Lock Screen Widgets</h1>
          <p className="text-xs vf-text-m mt-0.5">Configure widgets for iOS and Android home screens</p>
        </div>
      </div>

      {/* Widget Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {loading ? (
          Array.from({ length: 4 }).map((_, i) => (
            <div key={i} className="vf-section p-5 space-y-3" style={{ borderRadius: 14 }}>
              <div className="h-5 w-40 skeleton rounded" />
              <div className="h-4 w-56 skeleton rounded" />
              <div className="h-8 w-full skeleton rounded" />
            </div>
          ))
        ) : (
          allWidgets.map((w) => {
            const meta = WIDGET_META[w.widget_type];
            const isExisting = (w as Widget).id != null;
            const widget = isExisting ? (w as Widget) : null;
            const isSaving = saving === (widget?.id ?? w.widget_type);
            const isRefreshing = refreshing === w.widget_type;
            const isActive = widget?.is_active ?? false;

            return (
              <div
                key={w.widget_type}
                className="vf-section p-5 space-y-4"
                style={{ borderRadius: 14, opacity: isSaving ? 0.7 : 1 }}
              >
                {/* Title row */}
                <div className="flex items-start justify-between gap-3">
                  <div className="flex items-center gap-3">
                    <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl"
                      style={{ background: "var(--vf-bg-elevated)" }}>
                      {meta.icon}
                    </div>
                    <div>
                      <p className="text-[13px] font-semibold vf-text-1">{meta.label}</p>
                      <p className="text-xs vf-text-m mt-0.5">{meta.description}</p>
                    </div>
                  </div>
                  <button
                    disabled={isSaving}
                    onClick={() => {
                      if (!isExisting) {
                        handleCreate(w.widget_type);
                      } else {
                        handleToggle(widget!);
                      }
                    }}
                    className="shrink-0 transition-colors"
                  >
                    {isActive ? (
                      <ToggleRight className="h-7 w-7 text-indigo-500" />
                    ) : (
                      <ToggleLeft className="h-7 w-7 vf-text-m" />
                    )}
                  </button>
                </div>

                {/* Config row (only if active) */}
                {isActive && widget && (
                  <div className="grid grid-cols-2 gap-2">
                    <div>
                      <label className="text-[10px] font-semibold uppercase tracking-wide vf-text-m mb-1 block">Platform</label>
                      <select
                        value={widget.platform}
                        disabled={isSaving}
                        onChange={(e) => handleFieldChange(widget, "platform", e.target.value)}
                        className="vf-input text-xs w-full"
                        style={{ height: 34 }}
                      >
                        {PLATFORMS.map((p) => (
                          <option key={p.value} value={p.value}>{p.label}</option>
                        ))}
                      </select>
                    </div>
                    <div>
                      <label className="text-[10px] font-semibold uppercase tracking-wide vf-text-m mb-1 block">Size</label>
                      <select
                        value={widget.size}
                        disabled={isSaving}
                        onChange={(e) => handleFieldChange(widget, "size", e.target.value)}
                        className="vf-input text-xs w-full"
                        style={{ height: 34 }}
                      >
                        {SIZES.map((s) => (
                          <option key={s.value} value={s.value}>{s.label}</option>
                        ))}
                      </select>
                    </div>
                  </div>
                )}

                {/* Snapshot preview */}
                {isActive && widget?.snapshot && (
                  <div className="rounded-xl p-3 text-xs vf-text-m font-mono"
                    style={{ background: "var(--vf-bg-elevated)" }}>
                    {JSON.stringify(widget.snapshot, null, 2)}
                  </div>
                )}

                {/* Refresh button */}
                {isActive && (
                  <button
                    disabled={isRefreshing || isSaving}
                    onClick={() => handleRefresh(w.widget_type)}
                    className="flex items-center gap-1.5 text-xs font-semibold vf-text-m hover:text-indigo-500 transition-colors disabled:opacity-50"
                  >
                    <RefreshCw className={cn("h-3.5 w-3.5", isRefreshing && "animate-spin")} />
                    {isRefreshing ? "Refreshing…" : "Refresh data"}
                  </button>
                )}

                {widget?.last_refreshed_at && (
                  <p className="text-[11px] vf-text-m">
                    Last refreshed: {new Date(widget.last_refreshed_at).toLocaleString()}
                  </p>
                )}
              </div>
            );
          })
        )}
      </div>

      {/* Instructions */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {/* iOS */}
        <div className="vf-section p-5" style={{ borderRadius: 14 }}>
          <div className="flex items-center gap-2 mb-4">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-indigo-500/10">
              <Apple className="h-4 w-4 text-indigo-400" />
            </div>
            <h2 className="text-[13px] font-semibold vf-text-1">How to add on iOS</h2>
          </div>
          <ol className="space-y-2">
            {IOS_STEPS.map((step, i) => (
              <li key={i} className="flex items-start gap-2.5">
                <span className="flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-indigo-500/10 text-[10px] font-bold text-indigo-400">
                  {i + 1}
                </span>
                <span className="text-xs vf-text-2">{step}</span>
              </li>
            ))}
          </ol>
        </div>

        {/* Android */}
        <div className="vf-section p-5" style={{ borderRadius: 14 }}>
          <div className="flex items-center gap-2 mb-4">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-emerald-500/10">
              <Smartphone className="h-4 w-4 text-emerald-400" />
            </div>
            <h2 className="text-[13px] font-semibold vf-text-1">How to add on Android</h2>
          </div>
          <ol className="space-y-2">
            {ANDROID_STEPS.map((step, i) => (
              <li key={i} className="flex items-start gap-2.5">
                <span className="flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-emerald-500/10 text-[10px] font-bold text-emerald-400">
                  {i + 1}
                </span>
                <span className="text-xs vf-text-2">{step}</span>
              </li>
            ))}
          </ol>
        </div>
      </div>

      {/* Info note */}
      <div className="flex items-start gap-3 rounded-xl p-4"
        style={{ background: "rgba(99,102,241,0.05)", border: "1px solid rgba(99,102,241,0.15)" }}>
        <Info className="h-4 w-4 text-indigo-400 mt-0.5 shrink-0" />
        <p className="text-xs vf-text-2">
          Widget data is refreshed automatically every 15 minutes. Use the "Refresh data" button to force an immediate update.
          Widget availability depends on your device OS version (iOS 14+ / Android 12+).
        </p>
      </div>
    </div>
  );
}
