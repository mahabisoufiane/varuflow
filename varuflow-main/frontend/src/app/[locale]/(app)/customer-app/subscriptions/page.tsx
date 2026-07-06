"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api-client";
import { RefreshCw, Repeat2, PlusCircle } from "lucide-react";
import { Button } from "@/components/ui/button";
import { toast } from "sonner";
import styles from "./page.module.scss";

interface BookingSubscription {
  id: string;
  customer_id: string;
  service_id: string;
  staff_id: string | null;
  day_of_week: number;
  start_time: string;
  duration_minutes: number;
  frequency: string;
  status: string;
  next_booking_date: string | null;
  starts_on: string;
  ends_on: string | null;
}

const DAY_NAMES = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];

const STATUS_CONFIG: Record<string, { label: string; color: string }> = {
  active: { label: "Active", color: "bg-green-100 text-green-700" },
  paused: { label: "Paused", color: "bg-amber-100 text-amber-700" },
  cancelled: { label: "Cancelled", color: "bg-gray-100 text-gray-500" },
};

const STATUS_MODULE: Record<string, keyof typeof styles> = {
  active:    "statusActive",
  paused:    "statusPaused",
  cancelled: "statusCancelled",
};

type StatusFilter = "all" | "active" | "paused" | "cancelled";

export default function BookingSubscriptionsPage() {
  const [subscriptions, setSubscriptions] = useState<BookingSubscription[]>([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState<StatusFilter>("all");
  const [actionLoading, setActionLoading] = useState<string | null>(null);
  const [showCreateForm, setShowCreateForm] = useState(false);
  const [createForm, setCreateForm] = useState({
    customer_id: "",
    service_id: "",
    staff_id: "",
    day_of_week: "0",
    start_time: "09:00",
    duration_minutes: "60",
    starts_on: "",
    ends_on: "",
  });

  async function load() {
    setLoading(true);
    try {
      const data = await api.get<BookingSubscription[]>("/api/booking-subscriptions");
      setSubscriptions(data);
    } catch {
      toast.error("Failed to load recurring bookings");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { load(); }, []);  // eslint-disable-line react-hooks/exhaustive-deps

  async function createSubscription() {
    if (!createForm.customer_id.trim() || !createForm.service_id.trim()) {
      toast.error("Customer ID and Service ID are required");
      return;
    }
    setActionLoading("create");
    try {
      await api.post("/api/booking-subscriptions", {
        customer_id: createForm.customer_id,
        service_id: createForm.service_id,
        staff_id: createForm.staff_id || null,
        day_of_week: parseInt(createForm.day_of_week),
        start_time: createForm.start_time,
        duration_minutes: parseInt(createForm.duration_minutes),
        starts_on: createForm.starts_on,
        ends_on: createForm.ends_on || null,
      });
      toast.success("Recurring booking created");
      setShowCreateForm(false);
      setCreateForm({ customer_id: "", service_id: "", staff_id: "", day_of_week: "0", start_time: "09:00", duration_minutes: "60", starts_on: "", ends_on: "" });
      await load();
    } catch {
      toast.error("Something went wrong");
    } finally {
      setActionLoading(null);
    }
  }

  async function generateNext(id: string) {
    setActionLoading(id + "_gen");
    try {
      const data = await api.post<{ date?: string }>(`/api/booking-subscriptions/${id}/generate-next`, {});
      toast.success(`Appointment created for ${data.date ?? "next slot"}`);
      await load();
    } catch {
      toast.error("Something went wrong");
    } finally {
      setActionLoading(null);
    }
  }

  async function updateStatus(id: string, action: "pause" | "resume" | "cancel") {
    setActionLoading(id + "_" + action);
    try {
      await api.post(`/api/booking-subscriptions/${id}/${action}`, {});
      toast.success(`Subscription ${action}d`);
      await load();
    } catch {
      toast.error("Something went wrong");
    } finally {
      setActionLoading(null);
    }
  }

  const filtered = subscriptions.filter((s) => filter === "all" || s.status === filter);
  const inputCls = "block w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-[var(--vf-brand-primary)]";

  return (
    <div className="mx-auto max-w-4xl space-y-6 p-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-gray-900">Recurring Bookings</h1>
          <p className="text-sm text-muted-foreground mt-0.5">Manage auto-generating recurring appointment subscriptions.</p>
        </div>
        <Button onClick={() => setShowCreateForm((s) => !s)} className="bg-[var(--vf-brand-primary)] hover:bg-[var(--vf-brand-primary-hover)] text-white gap-2">
          <PlusCircle className="h-4 w-4" /> New Subscription
        </Button>
      </div>

      {/* Filter tabs */}
      <div className="flex gap-1 border-b">
        {(["all", "active", "paused", "cancelled"] as StatusFilter[]).map((f) => (
          <button key={f} type="button" onClick={() => setFilter(f)}
            className={`px-4 py-2.5 text-sm font-medium border-b-2 capitalize transition-colors ${
              filter === f ? "border-[var(--vf-brand-primary)] text-[var(--vf-text-primary)]" : "border-transparent text-muted-foreground hover:text-gray-700"
            }`}>
            {f === "all" ? "All" : f.charAt(0).toUpperCase() + f.slice(1)}
          </button>
        ))}
      </div>

      {/* Create form */}
      {showCreateForm && (
        <div className="rounded-xl border border-[var(--vf-brand-primary)]/20 bg-white p-5 shadow-sm space-y-3">
          <h3 className="text-sm font-semibold text-gray-900">New Recurring Booking</h3>
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1">
              <label className="text-xs font-medium text-gray-700">Customer ID *</label>
              <input value={createForm.customer_id}
                onChange={(e) => setCreateForm((f) => ({ ...f, customer_id: e.target.value }))}
                placeholder="UUID" className={inputCls} />
            </div>
            <div className="space-y-1">
              <label className="text-xs font-medium text-gray-700">Service ID *</label>
              <input value={createForm.service_id}
                onChange={(e) => setCreateForm((f) => ({ ...f, service_id: e.target.value }))}
                placeholder="UUID" className={inputCls} />
            </div>
            <div className="space-y-1">
              <label className="text-xs font-medium text-gray-700">Staff ID (optional)</label>
              <input value={createForm.staff_id}
                onChange={(e) => setCreateForm((f) => ({ ...f, staff_id: e.target.value }))}
                placeholder="UUID" className={inputCls} />
            </div>
            <div className="space-y-1">
              <label className="text-xs font-medium text-gray-700">Day of Week</label>
              <select value={createForm.day_of_week}
                onChange={(e) => setCreateForm((f) => ({ ...f, day_of_week: e.target.value }))}
                className={inputCls}>
                {DAY_NAMES.map((d, i) => <option key={i} value={i}>{d}</option>)}
              </select>
            </div>
            <div className="space-y-1">
              <label className="text-xs font-medium text-gray-700">Start Time</label>
              <input type="time" value={createForm.start_time}
                onChange={(e) => setCreateForm((f) => ({ ...f, start_time: e.target.value }))}
                className={inputCls} />
            </div>
            <div className="space-y-1">
              <label className="text-xs font-medium text-gray-700">Duration (minutes)</label>
              <input type="number" value={createForm.duration_minutes} min="15"
                onChange={(e) => setCreateForm((f) => ({ ...f, duration_minutes: e.target.value }))}
                className={inputCls} />
            </div>
            <div className="space-y-1">
              <label className="text-xs font-medium text-gray-700">Starts On</label>
              <input type="date" value={createForm.starts_on}
                onChange={(e) => setCreateForm((f) => ({ ...f, starts_on: e.target.value }))}
                className={inputCls} />
            </div>
            <div className="space-y-1">
              <label className="text-xs font-medium text-gray-700">Ends On (optional)</label>
              <input type="date" value={createForm.ends_on}
                onChange={(e) => setCreateForm((f) => ({ ...f, ends_on: e.target.value }))}
                className={inputCls} />
            </div>
          </div>
          <div className="flex gap-2">
            <Button variant="outline" onClick={() => setShowCreateForm(false)}>Cancel</Button>
            <Button disabled={actionLoading === "create"} onClick={createSubscription}
              className="bg-[var(--vf-brand-primary)] hover:bg-[var(--vf-brand-primary-hover)] text-white">
              {actionLoading === "create" ? "Creating…" : "Create"}
            </Button>
          </div>
        </div>
      )}

      {/* List */}
      <div className="rounded-xl border bg-white shadow-sm">
        {loading ? (
          <div className="py-12 text-center">
            <RefreshCw className="h-6 w-6 animate-spin mx-auto text-muted-foreground" />
          </div>
        ) : filtered.length === 0 ? (
          <div className="py-12 text-center">
            <Repeat2 className="h-10 w-10 text-muted-foreground mx-auto mb-3" />
            <p className="text-gray-600 font-medium">No recurring bookings found</p>
          </div>
        ) : (
          <div className="divide-y divide-gray-100">
            {filtered.map((s) => {
              const cfg = STATUS_CONFIG[s.status] ?? STATUS_CONFIG.cancelled;
              const isLoading = (key: string) => actionLoading === s.id + "_" + key;
              return (
                <div key={s.id} className="flex items-center gap-4 px-5 py-4">
                  <div className="flex-1 min-w-0 space-y-0.5">
                    <div className="flex items-center gap-2">
                      <p className="text-xs font-mono text-gray-700">{s.customer_id.slice(0, 8)}…</p>
                      <span className="text-muted-foreground">·</span>
                      <p className="text-xs font-mono text-gray-500">{s.service_id.slice(0, 8)}…</p>
                    </div>
                    <p className="text-xs text-muted-foreground">
                      {DAY_NAMES[s.day_of_week]} at {s.start_time} · {s.duration_minutes}min
                      {s.next_booking_date && ` · Next: ${new Date(s.next_booking_date).toLocaleDateString()}`}
                    </p>
                  </div>
                  <span className={styles[STATUS_MODULE[s.status] ?? "statusActive"]}>
                    {cfg.label}
                  </span>
                  <div className="flex items-center gap-1.5 flex-shrink-0">
                    {s.status === "active" && (
                      <Button variant="outline" size="sm" disabled={!!actionLoading}
                        onClick={() => generateNext(s.id)}>
                        {isLoading("gen") ? <RefreshCw className="h-3 w-3 animate-spin" /> : "Generate Next"}
                      </Button>
                    )}
                    {s.status === "active" && (
                      <Button variant="outline" size="sm" disabled={!!actionLoading}
                        onClick={() => updateStatus(s.id, "pause")}>
                        {isLoading("pause") ? <RefreshCw className="h-3 w-3 animate-spin" /> : "Pause"}
                      </Button>
                    )}
                    {s.status === "paused" && (
                      <Button variant="outline" size="sm" disabled={!!actionLoading}
                        onClick={() => updateStatus(s.id, "resume")}>
                        {isLoading("resume") ? <RefreshCw className="h-3 w-3 animate-spin" /> : "Resume"}
                      </Button>
                    )}
                    {s.status !== "cancelled" && (
                      <Button variant="outline" size="sm" disabled={!!actionLoading}
                        onClick={() => updateStatus(s.id, "cancel")}
                        className="text-red-600 border-red-200 hover:bg-red-50">
                        {isLoading("cancel") ? <RefreshCw className="h-3 w-3 animate-spin" /> : "Cancel"}
                      </Button>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
