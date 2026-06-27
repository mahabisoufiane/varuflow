"use client";

import { api } from "@/lib/api-client";
import { useEffect, useState } from "react";
import { toast } from "sonner";
import { useRouter, useParams } from "next/navigation";
import { cn } from "@/lib/utils";
import {
  Watch, Plus, Trash2, X, Copy, Check,
  Clock, Calendar, Bluetooth,
} from "lucide-react";

interface WatchSession {
  id: string;
  device_id: string;
  platform: "apple_watch" | "wear_os";
  session_token?: string;
  paired_at: string;
  expires_at: string;
}

interface TodayScheduleItem {
  id: string;
  title: string;
  start_time: string;
  end_time: string;
  customer_name?: string;
}

const PLATFORM_META: Record<WatchSession["platform"], { label: string; color: string; bg: string }> = {
  apple_watch: { label: "Apple Watch", color: "text-gray-300", bg: "bg-gray-500/10" },
  wear_os: { label: "Wear OS", color: "text-emerald-400", bg: "bg-emerald-500/10" },
};

export default function WatchPage() {
  const router = useRouter();
  const params = useParams<{ locale: string }>();
  const locale = params.locale;

  const [sessions, setSessions] = useState<WatchSession[]>([]);
  const [schedule, setSchedule] = useState<TodayScheduleItem[]>([]);
  const [loading, setLoading] = useState(true);

  // Form state
  const [showForm, setShowForm] = useState(false);
  const [deviceId, setDeviceId] = useState("");
  const [platform, setPlatform] = useState<WatchSession["platform"]>("apple_watch");
  const [submitting, setSubmitting] = useState(false);

  // Token modal
  const [tokenModal, setTokenModal] = useState<{ token: string } | null>(null);
  const [copied, setCopied] = useState(false);

  // Deleting
  const [deletingId, setDeletingId] = useState<string | null>(null);

  useEffect(() => {
    const fetchAll = async () => {
      try {
        const [sessionsData, scheduleData] = await Promise.all([
          api.get<WatchSession[]>("/api/watch-sessions"),
          api.get<TodayScheduleItem[]>("/api/watch-sessions/today").catch(() => [] as TodayScheduleItem[]),
        ]);
        setSessions(sessionsData);
        setSchedule(scheduleData);
      } catch (e: unknown) {
        const err = e as { status?: number; message?: string };
        if (err.status === 401) { router.push(`/${locale}/auth/login`); return; }
        toast.error(err.message ?? "Failed to load watch sessions");
      } finally {
        setLoading(false);
      }
    };
    fetchAll();
  }, [locale, router]);

  async function handlePair(e: React.FormEvent) {
    e.preventDefault();
    if (!deviceId.trim()) { toast.error("Device ID is required"); return; }
    setSubmitting(true);
    try {
      const created = await api.post<WatchSession>("/api/watch-sessions", { device_id: deviceId.trim(), platform });
      setSessions((prev) => [...prev, created]);
      setDeviceId("");
      setShowForm(false);
      if (created.session_token) {
        setTokenModal({ token: created.session_token });
      }
      toast.success("Watch paired successfully");
    } catch (e: unknown) {
      const err = e as { status?: number; message?: string };
      if (err.status === 401) { router.push(`/${locale}/auth/login`); return; }
      toast.error(err.message ?? "Failed to pair watch");
    } finally {
      setSubmitting(false);
    }
  }

  async function handleDelete(id: string) {
    setDeletingId(id);
    try {
      await api.delete(`/api/watch-sessions/${id}`);
      setSessions((prev) => prev.filter((s) => s.id !== id));
      toast.success("Watch unpaired");
    } catch (e: unknown) {
      const err = e as { status?: number; message?: string };
      if (err.status === 401) { router.push(`/${locale}/auth/login`); return; }
      toast.error(err.message ?? "Failed to unpair watch");
    } finally {
      setDeletingId(null);
    }
  }

  function handleCopy() {
    if (!tokenModal) return;
    navigator.clipboard.writeText(tokenModal.token).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    });
  }

  const isExpired = (expiresAt: string) => new Date(expiresAt) < new Date();

  return (
    <div className="space-y-6">

      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold tracking-tight vf-text-1">Apple Watch &amp; Wear OS</h1>
          <p className="text-xs vf-text-m mt-0.5">Manage paired watch devices and view today's schedule</p>
        </div>
        <button onClick={() => setShowForm(true)} className="vf-btn text-xs">
          <Plus className="h-3.5 w-3.5" />Pair new watch
        </button>
      </div>

      {/* Pair Form */}
      {showForm && (
        <div className="vf-section p-5" style={{ borderRadius: 14 }}>
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-[13px] font-semibold vf-text-1">Pair a new watch</h2>
            <button onClick={() => setShowForm(false)} className="vf-text-m hover:text-red-400 transition-colors">
              <X className="h-4 w-4" />
            </button>
          </div>
          <form onSubmit={handlePair} className="space-y-3">
            <div>
              <label className="text-[11px] font-semibold uppercase tracking-wide vf-text-m mb-1 block">Device ID</label>
              <input
                value={deviceId}
                onChange={(e) => setDeviceId(e.target.value)}
                placeholder="e.g. A1B2C3D4-XXXX-XXXX-XXXX-XXXXXXXXXXXX"
                className="vf-input text-xs w-full"
                style={{ height: 36 }}
                disabled={submitting}
              />
              <p className="text-[11px] vf-text-m mt-1">
                Find the device ID in your watch companion app settings
              </p>
            </div>
            <div>
              <label className="text-[11px] font-semibold uppercase tracking-wide vf-text-m mb-1 block">Platform</label>
              <select
                value={platform}
                onChange={(e) => setPlatform(e.target.value as WatchSession["platform"])}
                className="vf-input text-xs w-full"
                style={{ height: 36 }}
                disabled={submitting}
              >
                <option value="apple_watch">Apple Watch</option>
                <option value="wear_os">Wear OS</option>
              </select>
            </div>
            <div className="flex gap-2 pt-1">
              <button type="submit" disabled={submitting} className="vf-btn text-xs">
                <Bluetooth className="h-3.5 w-3.5" />
                {submitting ? "Pairing…" : "Pair watch"}
              </button>
              <button
                type="button"
                onClick={() => setShowForm(false)}
                className="vf-btn-secondary text-xs"
              >
                Cancel
              </button>
            </div>
          </form>
        </div>
      )}

      {/* Paired Devices */}
      <div className="vf-section">
        <div className="vf-section-header">
          <h2 className="text-[13px] font-semibold vf-text-1">Paired devices</h2>
          <span className="text-[11px] vf-text-m">{sessions.length} paired</span>
        </div>

        {loading ? (
          Array.from({ length: 3 }).map((_, i) => (
            <div key={i} className="flex gap-4 px-5 py-4" style={{ borderBottom: "1px solid var(--vf-divider)" }}>
              <div className="h-4 w-40 skeleton rounded" />
              <div className="h-4 w-24 skeleton rounded ml-auto" />
            </div>
          ))
        ) : sessions.length === 0 ? (
          <div className="py-16 text-center">
            <div className="mx-auto mb-3 flex h-12 w-12 items-center justify-center rounded-2xl"
              style={{ background: "var(--vf-bg-elevated)" }}>
              <Watch className="h-6 w-6 vf-text-m" />
            </div>
            <p className="text-sm font-medium vf-text-2">No watches paired</p>
            <p className="text-xs vf-text-m mt-1">Pair a watch to view your schedule on your wrist</p>
          </div>
        ) : (
          sessions.map((s, i) => {
            const meta = PLATFORM_META[s.platform];
            const expired = isExpired(s.expires_at);
            return (
              <div key={s.id} className="flex items-center gap-4 px-5 py-4"
                style={{ borderBottom: i < sessions.length - 1 ? "1px solid var(--vf-divider)" : "none" }}>
                <div className={cn("flex h-9 w-9 shrink-0 items-center justify-center rounded-xl", meta.bg)}>
                  <Watch className={cn("h-4 w-4", meta.color)} />
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 flex-wrap">
                    <p className="text-[13px] font-semibold vf-text-1 font-mono truncate">{s.device_id}</p>
                    <span className={cn("rounded-full px-2 py-0.5 text-[10px] font-semibold", meta.bg, meta.color)}>
                      {meta.label}
                    </span>
                    {expired && (
                      <span className="rounded-full bg-red-500/10 px-2 py-0.5 text-[10px] font-semibold text-red-400">
                        Expired
                      </span>
                    )}
                  </div>
                  <div className="flex gap-3 mt-0.5">
                    <p className="text-xs vf-text-m">
                      Paired {new Date(s.paired_at).toLocaleDateString()}
                    </p>
                    <p className="text-xs vf-text-m">
                      Expires {new Date(s.expires_at).toLocaleDateString()}
                    </p>
                  </div>
                </div>
                <button
                  disabled={deletingId === s.id}
                  onClick={() => handleDelete(s.id)}
                  className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg transition-colors hover:bg-red-500/10 hover:text-red-400 vf-text-m disabled:opacity-50"
                >
                  <Trash2 className="h-3.5 w-3.5" />
                </button>
              </div>
            );
          })
        )}
      </div>

      {/* Today's Schedule Preview */}
      <div className="vf-section">
        <div className="vf-section-header">
          <div className="flex items-center gap-2">
            <Calendar className="h-4 w-4 vf-text-m" />
            <h2 className="text-[13px] font-semibold vf-text-1">Today&apos;s schedule preview</h2>
          </div>
          <span className="text-[11px] vf-text-m">{schedule.length} items</span>
        </div>

        {loading ? (
          Array.from({ length: 3 }).map((_, i) => (
            <div key={i} className="flex gap-4 px-5 py-4" style={{ borderBottom: "1px solid var(--vf-divider)" }}>
              <div className="h-4 w-16 skeleton rounded" />
              <div className="h-4 w-32 skeleton rounded" />
            </div>
          ))
        ) : schedule.length === 0 ? (
          <div className="py-10 text-center">
            <p className="text-sm font-medium vf-text-2">No schedule items today</p>
            <p className="text-xs vf-text-m mt-1">Schedule items will appear here</p>
          </div>
        ) : (
          schedule.map((item, i) => (
            <div key={item.id} className="flex items-center gap-4 px-5 py-4"
              style={{ borderBottom: i < schedule.length - 1 ? "1px solid var(--vf-divider)" : "none" }}>
              <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-indigo-500/10">
                <Clock className="h-4 w-4 text-indigo-400" />
              </div>
              <div className="flex-1 min-w-0">
                <p className="text-[13px] font-semibold vf-text-1 truncate">{item.title}</p>
                {item.customer_name && (
                  <p className="text-xs vf-text-m">{item.customer_name}</p>
                )}
              </div>
              <div className="text-right shrink-0">
                <p className="text-[13px] font-semibold tabular-nums vf-text-1">
                  {item.start_time.slice(0, 5)}
                </p>
                <p className="text-[11px] vf-text-m">
                  – {item.end_time.slice(0, 5)}
                </p>
              </div>
            </div>
          ))
        )}
      </div>

      {/* Token Modal */}
      {tokenModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4"
          style={{ background: "rgba(0,0,0,0.6)", backdropFilter: "blur(4px)" }}
          onClick={() => setTokenModal(null)}>
          <div className="w-full max-w-md vf-section p-6 space-y-4"
            style={{ borderRadius: 18 }}
            onClick={(e) => e.stopPropagation()}>
            <div className="flex items-center justify-between">
              <h2 className="text-[15px] font-bold vf-text-1">Watch Session Token</h2>
              <button onClick={() => setTokenModal(null)} className="vf-text-m hover:text-red-400 transition-colors">
                <X className="h-5 w-5" />
              </button>
            </div>

            <p className="text-xs vf-text-m">
              Copy this token and enter it in your watch companion app. This token will only be shown once.
            </p>

            {/* Token display */}
            <div className="rounded-xl p-4 font-mono text-xs break-all vf-text-1"
              style={{ background: "var(--vf-bg-elevated)", border: "1px solid var(--vf-border)" }}>
              {tokenModal.token}
            </div>

            <button
              onClick={handleCopy}
              className={cn(
                "flex w-full items-center justify-center gap-2 rounded-xl py-2.5 text-sm font-semibold transition-colors",
                copied
                  ? "bg-emerald-500/10 text-emerald-400"
                  : "bg-indigo-500/10 text-indigo-400 hover:bg-indigo-500/20"
              )}
            >
              {copied ? <Check className="h-4 w-4" /> : <Copy className="h-4 w-4" />}
              {copied ? "Copied!" : "Copy token"}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
