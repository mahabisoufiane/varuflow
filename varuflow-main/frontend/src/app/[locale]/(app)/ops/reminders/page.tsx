"use client";

import { useEffect, useState } from "react";
import { useRouter, useParams } from "next/navigation";
import { createClient } from "@/lib/supabase/client";
import { PlusCircle, RefreshCw, Bell, ChevronDown, ChevronRight } from "lucide-react";
import { Button } from "@/components/ui/button";
import { toast } from "sonner";
import styles from "./page.module.scss";

const FREQ_MODULE: Record<string, keyof typeof styles> = { daily: "freqDaily", weekly: "freqWeekly", monthly: "freqMonthly" };
const OCC_MODULE: Record<string, keyof typeof styles> = { pending: "occPending", completed: "occCompleted", dismissed: "occDismissed", snoozed: "occSnoozed" };

interface ReminderOccurrence {
  id: string;
  due_at: string;
  status: string;
}

interface Reminder {
  id: string;
  title: string;
  description: string | null;
  frequency: string;
  day_of_week: string | null;
  day_of_month: number | null;
  time_of_day: string;
  next_due_at: string | null;
  is_active: boolean;
  occurrences?: ReminderOccurrence[];
}

const FREQ_CONFIG: Record<string, { label: string; color: string }> = {
  daily:   { label: "Daily",   color: "bg-green-100 text-green-700"   },
  weekly:  { label: "Weekly",  color: "bg-blue-100 text-blue-700"     },
  monthly: { label: "Monthly", color: "bg-purple-100 text-purple-700" },
};

const OCC_STATUS_CONFIG: Record<string, { label: string; color: string }> = {
  pending:   { label: "Pending",   color: "bg-amber-100 text-amber-700"   },
  completed: { label: "Completed", color: "bg-green-100 text-green-700"   },
  dismissed: { label: "Dismissed", color: "bg-gray-100 text-gray-500"     },
  snoozed:   { label: "Snoozed",   color: "bg-purple-100 text-purple-700" },
};

const DAYS_OF_WEEK = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];

export default function RemindersPage() {
  const router = useRouter();
  const params = useParams<{ locale: string }>();
  const locale = params?.locale ?? "en";
  const supabase = createClient();

  const [reminders, setReminders] = useState<Reminder[]>([]);
  const [dueReminders, setDueReminders] = useState<Reminder[]>([]);
  const [loading, setLoading] = useState(true);
  const [activeOnly, setActiveOnly] = useState(true);
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [actionLoading, setActionLoading] = useState<string | null>(null);

  const [showNew, setShowNew] = useState(false);
  const [newForm, setNewForm] = useState({
    title: "",
    description: "",
    frequency: "daily",
    day_of_week: "Mon",
    day_of_month: "1",
    time_of_day: "09:00",
    assigned_to_user_id: "",
  });

  async function getToken() {
    const { data: { session } } = await supabase.auth.getSession();
    return session?.access_token ?? null;
  }
  function apiUrl(p: string) { return `${process.env.NEXT_PUBLIC_API_URL}${p}`; }

  async function load() {
    setLoading(true);
    try {
      const token = await getToken();
      if (!token) { router.push(`/${locale}/auth/login`); return; }

      const [remRes, dueRes] = await Promise.all([
        fetch(apiUrl(`/api/reminders${activeOnly ? "?is_active=true" : ""}`), {
          headers: { Authorization: `Bearer ${token}` },
        }),
        fetch(apiUrl("/api/reminders/due"), { headers: { Authorization: `Bearer ${token}` } }),
      ]);
      if (remRes.status === 401) { router.push(`/${locale}/auth/login`); return; }
      if (remRes.ok) setReminders(await remRes.json());
      if (dueRes.ok) setDueReminders(await dueRes.json());
    } catch {
      toast.error("Failed to load reminders");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { load(); }, []);  // eslint-disable-line react-hooks/exhaustive-deps

  async function createReminder() {
    if (!newForm.title.trim()) { toast.error("Title is required"); return; }
    setActionLoading("create");
    try {
      const token = await getToken();
      if (!token) return;
      const body: Record<string, unknown> = {
        title: newForm.title,
        description: newForm.description || null,
        frequency: newForm.frequency,
        time_of_day: newForm.time_of_day,
        assigned_to_user_id: newForm.assigned_to_user_id || null,
      };
      if (newForm.frequency === "weekly") body.day_of_week = newForm.day_of_week;
      if (newForm.frequency === "monthly") body.day_of_month = parseInt(newForm.day_of_month) || 1;

      const res = await fetch(apiUrl("/api/reminders"), {
        method: "POST",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
        body: JSON.stringify(body),
      });
      if (!res.ok) {
        const b = await res.json().catch(() => ({}));
        toast.error(b.detail ?? "Failed to create reminder");
        return;
      }
      toast.success("Reminder created");
      setShowNew(false);
      setNewForm({ title: "", description: "", frequency: "daily", day_of_week: "Mon", day_of_month: "1", time_of_day: "09:00", assigned_to_user_id: "" });
      await load();
    } catch {
      toast.error("Something went wrong");
    } finally {
      setActionLoading(null);
    }
  }

  async function triggerNow(id: string) {
    setActionLoading(id + "_trigger");
    try {
      const token = await getToken();
      if (!token) return;
      const res = await fetch(apiUrl(`/api/reminders/${id}/trigger`), {
        method: "POST",
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) {
        const b = await res.json().catch(() => ({}));
        toast.error(b.detail ?? "Failed to trigger");
        return;
      }
      toast.success("Reminder triggered");
      await load();
    } catch {
      toast.error("Something went wrong");
    } finally {
      setActionLoading(null);
    }
  }

  async function togglePause(id: string, isActive: boolean) {
    const action = isActive ? "pause" : "resume";
    setActionLoading(id + "_" + action);
    try {
      const token = await getToken();
      if (!token) return;
      const res = await fetch(apiUrl(`/api/reminders/${id}/${action}`), {
        method: "POST",
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) {
        const b = await res.json().catch(() => ({}));
        toast.error(b.detail ?? `Failed to ${action}`);
        return;
      }
      toast.success(`Reminder ${action}d`);
      await load();
    } catch {
      toast.error("Something went wrong");
    } finally {
      setActionLoading(null);
    }
  }

  async function deleteReminder(id: string) {
    setActionLoading(id + "_delete");
    try {
      const token = await getToken();
      if (!token) return;
      const res = await fetch(apiUrl(`/api/reminders/${id}`), {
        method: "DELETE",
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) {
        const b = await res.json().catch(() => ({}));
        toast.error(b.detail ?? "Failed to delete");
        return;
      }
      toast.success("Reminder deleted");
      await load();
    } catch {
      toast.error("Something went wrong");
    } finally {
      setActionLoading(null);
    }
  }

  async function loadReminderDetail(id: string) {
    try {
      const token = await getToken();
      if (!token) return;
      const res = await fetch(apiUrl(`/api/reminders/${id}`), {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (res.ok) {
        const data = await res.json();
        setReminders((prev) => prev.map((r) => (r.id === id ? { ...r, occurrences: data.occurrences ?? [] } : r)));
      }
    } catch {
      toast.error("Failed to load reminder detail");
    }
  }

  async function markOccurrenceComplete(occId: string) {
    setActionLoading(occId + "_complete");
    try {
      const token = await getToken();
      if (!token) return;
      const res = await fetch(apiUrl(`/api/reminders/occurrences/${occId}`), {
        method: "PATCH",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
        body: JSON.stringify({ status: "completed" }),
      });
      if (!res.ok) {
        const b = await res.json().catch(() => ({}));
        toast.error(b.detail ?? "Failed to mark complete");
        return;
      }
      toast.success("Occurrence marked complete");
      if (expandedId) await loadReminderDetail(expandedId);
    } catch {
      toast.error("Something went wrong");
    } finally {
      setActionLoading(null);
    }
  }

  function handleExpand(id: string) {
    if (expandedId === id) {
      setExpandedId(null);
    } else {
      setExpandedId(id);
      loadReminderDetail(id);
    }
  }

  function formatDayInfo(r: Reminder) {
    if (r.frequency === "weekly") return r.day_of_week ?? "–";
    if (r.frequency === "monthly") return r.day_of_month ? `${r.day_of_month}th` : "–";
    return "Every day";
  }

  return (
    <div className="mx-auto max-w-4xl space-y-6 p-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-gray-900">Recurring Reminders</h1>
          <p className="text-sm text-muted-foreground mt-0.5">
            User-defined recurring reminders and task triggers.
          </p>
        </div>
        <Button onClick={() => setShowNew(true)} className="bg-[var(--vf-brand-primary)] hover:bg-[var(--vf-brand-primary-hover)] text-white gap-2">
          <PlusCircle className="h-4 w-4" /> New Reminder
        </Button>
      </div>

      {/* Due alert strip */}
      {dueReminders.length > 0 && (
        <div className="flex items-center gap-2 rounded-lg bg-amber-50 border border-amber-200 px-4 py-3">
          <Bell className="h-4 w-4 text-amber-600 flex-shrink-0" />
          <p className="text-sm text-amber-800 font-medium">
            {dueReminders.length} reminder{dueReminders.length !== 1 ? "s" : ""} due in the next 24 hours
          </p>
        </div>
      )}

      {/* Filters */}
      <div className="flex items-center gap-3">
        <label className="flex items-center gap-2 text-sm text-gray-700 cursor-pointer select-none">
          <input
            type="checkbox"
            checked={activeOnly}
            onChange={(e) => {
              setActiveOnly(e.target.checked);
              setTimeout(() => load(), 0);
            }}
            className="h-4 w-4 rounded border-gray-300 accent-[var(--vf-brand-primary)]"
          />
          Active only
        </label>
      </div>

      {/* New reminder form */}
      {showNew && (
        <div className="rounded-xl border border-[var(--vf-brand-primary)]/20 bg-white p-5 shadow-sm space-y-3">
          <h3 className="text-sm font-semibold text-gray-900">Create Reminder</h3>
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1">
              <label className="text-xs font-medium text-gray-700">Title *</label>
              <input
                value={newForm.title}
                onChange={(e) => setNewForm((f) => ({ ...f, title: e.target.value }))}
                placeholder="Monthly stock count"
                className="block w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-[var(--vf-brand-primary)]"
              />
            </div>
            <div className="space-y-1">
              <label className="text-xs font-medium text-gray-700">Frequency</label>
              <select
                value={newForm.frequency}
                onChange={(e) => setNewForm((f) => ({ ...f, frequency: e.target.value }))}
                className="block w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-[var(--vf-brand-primary)]"
              >
                <option value="daily">Daily</option>
                <option value="weekly">Weekly</option>
                <option value="monthly">Monthly</option>
              </select>
            </div>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1">
              <label className="text-xs font-medium text-gray-700">Time of Day</label>
              <input
                type="time"
                value={newForm.time_of_day}
                onChange={(e) => setNewForm((f) => ({ ...f, time_of_day: e.target.value }))}
                className="block w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-[var(--vf-brand-primary)]"
              />
            </div>
            {newForm.frequency === "weekly" && (
              <div className="space-y-1">
                <label className="text-xs font-medium text-gray-700">Day of Week</label>
                <select
                  value={newForm.day_of_week}
                  onChange={(e) => setNewForm((f) => ({ ...f, day_of_week: e.target.value }))}
                  className="block w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-[var(--vf-brand-primary)]"
                >
                  {DAYS_OF_WEEK.map((d) => (
                    <option key={d} value={d}>{d}</option>
                  ))}
                </select>
              </div>
            )}
            {newForm.frequency === "monthly" && (
              <div className="space-y-1">
                <label className="text-xs font-medium text-gray-700">Day of Month (1–31)</label>
                <input
                  type="number"
                  min={1}
                  max={31}
                  value={newForm.day_of_month}
                  onChange={(e) => setNewForm((f) => ({ ...f, day_of_month: e.target.value }))}
                  className="block w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-[var(--vf-brand-primary)]"
                />
              </div>
            )}
          </div>
          <div className="space-y-1">
            <label className="text-xs font-medium text-gray-700">Description</label>
            <input
              value={newForm.description}
              onChange={(e) => setNewForm((f) => ({ ...f, description: e.target.value }))}
              placeholder="Optional description…"
              className="block w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-[var(--vf-brand-primary)]"
            />
          </div>
          <div className="space-y-1">
            <label className="text-xs font-medium text-gray-700">Assign to User ID (optional)</label>
            <input
              value={newForm.assigned_to_user_id}
              onChange={(e) => setNewForm((f) => ({ ...f, assigned_to_user_id: e.target.value }))}
              placeholder="UUID…"
              className="block w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-[var(--vf-brand-primary)]"
            />
          </div>
          <div className="flex gap-2">
            <Button variant="outline" onClick={() => setShowNew(false)}>Cancel</Button>
            <Button
              disabled={actionLoading === "create"}
              onClick={createReminder}
              className="bg-[var(--vf-brand-primary)] hover:bg-[var(--vf-brand-primary-hover)] text-white"
            >
              {actionLoading === "create" ? "Creating…" : "Create Reminder"}
            </Button>
          </div>
        </div>
      )}

      {/* List */}
      {loading && reminders.length === 0 ? (
        <div className="text-center py-12">
          <RefreshCw className="h-6 w-6 animate-spin mx-auto text-muted-foreground" />
        </div>
      ) : reminders.length === 0 ? (
        <div className="rounded-xl border bg-white shadow-sm py-12 text-center">
          <Bell className="h-10 w-10 text-muted-foreground mx-auto mb-3" />
          <p className="text-gray-600 font-medium">No reminders found</p>
        </div>
      ) : (
        <div className="rounded-xl border bg-white shadow-sm divide-y divide-gray-100">
          {reminders.map((rem) => {
            const freq = FREQ_CONFIG[rem.frequency] ?? FREQ_CONFIG.daily;
            const isExpanded = expandedId === rem.id;

            return (
              <div key={rem.id}>
                <div className="flex items-center gap-4 px-5 py-4">
                  <button
                    type="button"
                    onClick={() => handleExpand(rem.id)}
                    className="flex-1 min-w-0 text-left"
                  >
                    <div className="flex items-center gap-2">
                      {isExpanded
                        ? <ChevronDown className="h-4 w-4 text-muted-foreground flex-shrink-0" />
                        : <ChevronRight className="h-4 w-4 text-muted-foreground flex-shrink-0" />}
                      <span className="text-sm font-medium text-gray-900">{rem.title}</span>
                      <span className={styles[FREQ_MODULE[rem.frequency] ?? "freqDaily"]}>
                        {freq.label}
                      </span>
                      <span className="text-xs text-muted-foreground">{formatDayInfo(rem)}</span>
                    </div>
                    <p className="text-xs text-muted-foreground mt-0.5 pl-6">
                      {rem.time_of_day}
                      {rem.next_due_at ? ` · Next: ${new Date(rem.next_due_at).toLocaleDateString()}` : ""}
                    </p>
                  </button>

                  {/* Active dot */}
                  <span
                    className={`h-2.5 w-2.5 rounded-full flex-shrink-0 ${rem.is_active ? "bg-green-500" : "bg-gray-300"}`}
                    title={rem.is_active ? "Active" : "Paused"}
                  />

                  <div className="flex items-center gap-2 flex-shrink-0">
                    <Button
                      variant="outline"
                      size="sm"
                      disabled={actionLoading === rem.id + "_trigger"}
                      onClick={() => triggerNow(rem.id)}
                    >
                      {actionLoading === rem.id + "_trigger"
                        ? <RefreshCw className="h-3 w-3 animate-spin" />
                        : "Trigger Now"}
                    </Button>
                    <Button
                      variant="outline"
                      size="sm"
                      disabled={!!actionLoading?.startsWith(rem.id + "_pause") || !!actionLoading?.startsWith(rem.id + "_resume")}
                      onClick={() => togglePause(rem.id, rem.is_active)}
                      className={rem.is_active ? "border-amber-200 text-amber-700 hover:bg-amber-50" : "border-green-200 text-green-700 hover:bg-green-50"}
                    >
                      {rem.is_active ? "Pause" : "Resume"}
                    </Button>
                    <Button
                      variant="ghost"
                      size="sm"
                      disabled={actionLoading === rem.id + "_delete"}
                      onClick={() => deleteReminder(rem.id)}
                      className="text-red-500 hover:text-red-600 hover:bg-red-50"
                    >
                      Delete
                    </Button>
                  </div>
                </div>

                {isExpanded && (
                  <div className="border-t border-gray-100 bg-gray-50 px-5 py-4 space-y-3">
                    <p className="text-xs font-semibold text-gray-700 uppercase tracking-wide">Occurrences</p>
                    {!rem.occurrences ? (
                      <RefreshCw className="h-4 w-4 animate-spin text-muted-foreground" />
                    ) : rem.occurrences.length === 0 ? (
                      <p className="text-sm text-muted-foreground">No occurrences yet.</p>
                    ) : (
                      <div className="overflow-x-auto">
                        <table className="w-full text-sm">
                          <thead>
                            <tr className="text-xs font-medium text-muted-foreground border-b border-gray-200">
                              <th className="text-left pb-2 pr-4">Due</th>
                              <th className="text-left pb-2 pr-4">Status</th>
                              <th className="text-left pb-2" />
                            </tr>
                          </thead>
                          <tbody className="divide-y divide-gray-100">
                            {rem.occurrences.map((occ) => {
                              const occCfg = OCC_STATUS_CONFIG[occ.status] ?? OCC_STATUS_CONFIG.pending;
                              return (
                                <tr key={occ.id}>
                                  <td className="py-2 pr-4 text-gray-700">
                                    {new Date(occ.due_at).toLocaleString()}
                                  </td>
                                  <td className="py-2 pr-4">
                                    <span className={styles[OCC_MODULE[occ.status] ?? "occPending"]}>
                                      {occCfg.label}
                                    </span>
                                  </td>
                                  <td className="py-2">
                                    {occ.status === "pending" && (
                                      <Button
                                        size="sm"
                                        variant="outline"
                                        disabled={actionLoading === occ.id + "_complete"}
                                        onClick={() => markOccurrenceComplete(occ.id)}
                                        className="text-xs h-7"
                                      >
                                        {actionLoading === occ.id + "_complete"
                                          ? <RefreshCw className="h-3 w-3 animate-spin" />
                                          : "Mark Complete"}
                                      </Button>
                                    )}
                                  </td>
                                </tr>
                              );
                            })}
                          </tbody>
                        </table>
                      </div>
                    )}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
