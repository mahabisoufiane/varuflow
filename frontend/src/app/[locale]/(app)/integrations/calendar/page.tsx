"use client";

import { api } from "@/lib/api-client";
import { useTranslations } from "next-intl";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useLocale } from "next-intl";
import { toast } from "sonner";
import { Calendar, RefreshCw, Trash2, Link2, ArrowLeftRight, ArrowDown, ArrowUp, Clock } from "lucide-react";

type SyncDirection = "push" | "pull" | "both";

interface ConnectedCalendar {
  id: string;
  provider: "google" | "outlook" | "apple";
  email: string;
  sync_direction: SyncDirection;
  last_synced_at: string | null;
  is_active: boolean;
}

const PROVIDERS: { key: "google" | "outlook" | "apple"; label: string; color: string }[] = [
  { key: "google",  label: "Google Calendar",  color: "text-blue-400 bg-blue-500/10"   },
  { key: "outlook", label: "Outlook Calendar", color: "text-indigo-400 bg-indigo-500/10" },
  { key: "apple",   label: "Apple Calendar",   color: "text-gray-400 bg-gray-500/10"    },
];

const DIRECTION_ICONS: Record<SyncDirection, React.ReactNode> = {
  push: <ArrowUp className="h-3 w-3" />,
  pull: <ArrowDown className="h-3 w-3" />,
  both: <ArrowLeftRight className="h-3 w-3" />,
};

export default function CalendarSyncPage() {
  const t      = useTranslations();
  const router = useRouter();
  const locale = useLocale();

  const [calendars, setCalendars] = useState<ConnectedCalendar[]>([]);
  const [loading, setLoading]     = useState(true);
  const [connecting, setConnecting] = useState<string | null>(null);

  useEffect(() => {
    api.get<ConnectedCalendar[]>("/api/merchant-calendar-sync")
      .then(setCalendars)
      .catch((e: Error) => {
        if (e.message.includes("session")) router.push(`/${locale}/auth/login`);
        else toast.error(e.message);
      })
      .finally(() => setLoading(false));
  }, [locale, router]);

  async function handleConnect(provider: string) {
    setConnecting(provider);
    try {
      await api.post("/api/merchant-calendar-sync", { provider });
      const updated = await api.get<ConnectedCalendar[]>("/api/merchant-calendar-sync");
      setCalendars(updated);
      toast.success(t("calendarConnected"));
    } catch (e: unknown) {
      toast.error((e as Error).message);
    } finally {
      setConnecting(null);
    }
  }

  async function handleDisconnect(id: string) {
    try {
      await api.delete(`/api/merchant-calendar-sync/${id}`);
      setCalendars(prev => prev.filter(c => c.id !== id));
      toast.success(t("calendarDisconnected"));
    } catch (e: unknown) {
      toast.error((e as Error).message);
    }
  }

  async function handleDirectionChange(id: string, direction: SyncDirection) {
    try {
      await api.patch(`/api/merchant-calendar-sync/${id}`, { sync_direction: direction });
      setCalendars(prev => prev.map(c => c.id === id ? { ...c, sync_direction: direction } : c));
    } catch (e: unknown) {
      toast.error((e as Error).message);
    }
  }

  const connectedProviders = new Set(calendars.map(c => c.provider));

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-bold tracking-tight vf-text-1">{t("calendarSync")}</h1>
        <p className="text-xs vf-text-m mt-0.5">{t("calendarSyncDesc")}</p>
      </div>

      {/* Connected calendars */}
      <div className="vf-section">
        <div className="vf-section-header">
          <h2 className="text-[13px] font-semibold vf-text-1">{t("connectedCalendars")}</h2>
        </div>

        {loading ? (
          <div className="space-y-3 p-5">
            {[1, 2].map(i => (
              <div key={i} className="h-16 skeleton rounded-xl" />
            ))}
          </div>
        ) : calendars.length === 0 ? (
          <div className="py-14 text-center">
            <div className="mx-auto mb-3 flex h-12 w-12 items-center justify-center rounded-2xl"
              >
              <Calendar className="h-6 w-6 vf-text-m" />
            </div>
            <p className="text-sm font-medium vf-text-2">{t("noCalendarsConnected")}</p>
            <p className="text-xs vf-text-m mt-1">{t("connectCalendarBelow")}</p>
          </div>
        ) : (
          <div className="vf-divide">
            {calendars.map(cal => (
              <div key={cal.id} className="flex items-center gap-4 px-5 py-4">
                <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl"
                  >
                  <Calendar className="h-4 w-4 vf-text-m" />
                </div>
                <div className="flex-1 min-w-0">
                  <p className="text-[13px] font-semibold vf-text-1 capitalize">{cal.provider}</p>
                  <p className="text-xs vf-text-m truncate">{cal.email}</p>
                  {cal.last_synced_at && (
                    <p className="text-[11px] vf-text-m flex items-center gap-1 mt-0.5">
                      <Clock className="h-3 w-3" />
                      {new Date(cal.last_synced_at).toLocaleString()}
                    </p>
                  )}
                </div>
                {/* Sync direction toggle */}
                <div className="flex items-center gap-1 rounded-lg p-1"
                  >
                  {(["push", "pull", "both"] as SyncDirection[]).map(dir => (
                    <button
                      key={dir}
                      onClick={() => handleDirectionChange(cal.id, dir)}
                      className={`flex items-center gap-1 rounded-md px-2 py-1 text-[11px] font-medium transition-colors ${
                        cal.sync_direction === dir
                          ? "bg-indigo-500 text-white"
                          : "vf-text-m hover:vf-text-1"
                      }`}
                    >
                      {DIRECTION_ICONS[dir]}
                      {dir}
                    </button>
                  ))}
                </div>
                <button
                  onClick={() => handleDisconnect(cal.id)}
                  className="flex h-8 w-8 items-center justify-center rounded-lg text-red-400 hover:bg-red-500/10 transition-colors"
                >
                  <Trash2 className="h-4 w-4" />
                </button>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Connect new calendar */}
      <div className="vf-section">
        <div className="vf-section-header">
          <h2 className="text-[13px] font-semibold vf-text-1">{t("addCalendar")}</h2>
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 p-5">
          {PROVIDERS.map(({ key, label, color }) => (
            <button
              key={key}
              disabled={connectedProviders.has(key) || connecting === key}
              onClick={() => handleConnect(key)}
              className={`flex items-center gap-3 rounded-xl px-4 py-3 border border-[var(--vf-border)] bg-[var(--vf-bg-surface)] transition-all ${
                connectedProviders.has(key)
                  ? "opacity-40 cursor-not-allowed"
                  : "hover:shadow-card cursor-pointer"
              }`}
            >
              <div className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-xl ${color}`}>
                {connecting === key ? (
                  <RefreshCw className="h-4 w-4 animate-spin" />
                ) : (
                  <Link2 className="h-4 w-4" />
                )}
              </div>
              <div className="text-left">
                <p className="text-[13px] font-semibold vf-text-1">{label}</p>
                <p className="text-xs vf-text-m">
                  {connectedProviders.has(key) ? t("connected") : t("clickToConnect")}
                </p>
              </div>
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
