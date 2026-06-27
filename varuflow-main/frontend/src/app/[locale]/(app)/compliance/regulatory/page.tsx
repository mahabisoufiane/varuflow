"use client";

import { useEffect, useState } from "react";
import { useRouter, useParams } from "next/navigation";
import { createClient } from "@/lib/supabase/client";
import { PlusCircle, Calendar, RefreshCw, CheckCircle2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { toast } from "sonner";
import styles from "./page.module.scss";

interface RegulatoryEvent {
  id: string;
  title: string;
  event_type: string | null;
  country: string;
  due_date: string;
  status: string;
  recurrence: string | null;
  notes: string | null;
}

const STATUS_COLORS: Record<string, string> = {
  upcoming: "bg-blue-100 text-blue-700",
  completed: "bg-green-100 text-green-700",
  overdue: "bg-red-100 text-red-700",
};

const STATUS_MODULE: Record<string, keyof typeof styles> = {
  upcoming:  "statusUpcoming",
  completed: "statusCompleted",
  overdue:   "statusOverdue",
};

const COUNTRY_FLAGS: Record<string, string> = {
  SE: "🇸🇪",
  NO: "🇳🇴",
  DK: "🇩🇰",
};

function groupByMonth(events: RegulatoryEvent[]): Record<string, RegulatoryEvent[]> {
  const result: Record<string, RegulatoryEvent[]> = {};
  for (const e of events) {
    const key = e.due_date ? new Date(e.due_date).toLocaleString("default", { month: "long", year: "numeric" }) : "Unknown";
    if (!result[key]) result[key] = [];
    result[key].push(e);
  }
  return result;
}

const EMPTY_FORM = {
  title: "", event_type: "", country: "SE", due_date: "", recurrence: "", notes: "",
};

export default function RegulatoryCalendarPage() {
  const router = useRouter();
  const params = useParams<{ locale: string }>();
  const locale = params?.locale ?? "en";
  const supabase = createClient();

  const [events, setEvents] = useState<RegulatoryEvent[]>([]);
  const [loading, setLoading] = useState(true);
  const [countryFilter, setCountryFilter] = useState("all");
  const [showNew, setShowNew] = useState(false);
  const [newForm, setNewForm] = useState(EMPTY_FORM);
  const [actionLoading, setActionLoading] = useState<string | null>(null);

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
      const res = await fetch(apiUrl("/api/regulatory"), { headers: { Authorization: `Bearer ${token}` } });
      if (res.status === 401) { router.push(`/${locale}/auth/login`); return; }
      if (res.ok) setEvents(await res.json());
    } catch {
      toast.error("Failed to load regulatory calendar");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { load(); }, []);  // eslint-disable-line react-hooks/exhaustive-deps

  async function markComplete(id: string) {
    setActionLoading(id + "_complete");
    try {
      const token = await getToken();
      if (!token) return;
      const res = await fetch(apiUrl(`/api/regulatory/${id}`), {
        method: "PATCH",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
        body: JSON.stringify({ status: "completed" }),
      });
      if (!res.ok) {
        const b = await res.json().catch(() => ({}));
        toast.error(b.detail ?? "Failed to update");
        return;
      }
      toast.success("Marked as complete");
      await load();
    } catch {
      toast.error("Something went wrong");
    } finally {
      setActionLoading(null);
    }
  }

  async function seedCountry(country: string) {
    setActionLoading("seed_" + country);
    try {
      const token = await getToken();
      if (!token) return;
      const res = await fetch(apiUrl(`/api/regulatory/seed/${country}`), {
        method: "POST",
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) {
        const b = await res.json().catch(() => ({}));
        toast.error(b.detail ?? `Failed to seed ${country}`);
        return;
      }
      toast.success(`${country} regulatory events seeded`);
      await load();
    } catch {
      toast.error("Something went wrong");
    } finally {
      setActionLoading(null);
    }
  }

  async function createEvent() {
    if (!newForm.title.trim() || !newForm.due_date) { toast.error("Title and due date are required"); return; }
    setActionLoading("create");
    try {
      const token = await getToken();
      if (!token) return;
      const res = await fetch(apiUrl("/api/regulatory"), {
        method: "POST",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
        body: JSON.stringify({
          title: newForm.title,
          event_type: newForm.event_type || null,
          country: newForm.country,
          due_date: newForm.due_date,
          recurrence: newForm.recurrence || null,
          notes: newForm.notes || null,
        }),
      });
      if (!res.ok) {
        const b = await res.json().catch(() => ({}));
        toast.error(b.detail ?? "Failed to create event");
        return;
      }
      toast.success("Regulatory event added");
      setShowNew(false);
      setNewForm(EMPTY_FORM);
      await load();
    } catch {
      toast.error("Something went wrong");
    } finally {
      setActionLoading(null);
    }
  }

  const filtered = countryFilter === "all" ? events : events.filter((e) => e.country === countryFilter);
  const sorted = [...filtered].sort((a, b) => new Date(a.due_date).getTime() - new Date(b.due_date).getTime());
  const grouped = groupByMonth(sorted);

  return (
    <div className="mx-auto max-w-4xl space-y-6 p-6">
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <h1 className="text-xl font-semibold text-gray-900">Regulatory Calendar</h1>
          <p className="text-sm text-muted-foreground mt-0.5">Track compliance deadlines across Sweden, Norway, and Denmark.</p>
        </div>
        <div className="flex items-center gap-2 flex-wrap">
          {["SE", "NO", "DK"].map((c) => (
            <Button key={c} variant="outline" size="sm"
              disabled={actionLoading === "seed_" + c}
              onClick={() => seedCountry(c)}
              className="gap-1 text-xs">
              {actionLoading === "seed_" + c ? <RefreshCw className="h-3 w-3 animate-spin" /> : COUNTRY_FLAGS[c]}
              Seed {c}
            </Button>
          ))}
          <Button onClick={() => setShowNew(true)} className="bg-[#1a2332] hover:bg-[#2a3342] text-white gap-2">
            <PlusCircle className="h-4 w-4" /> Add Event
          </Button>
        </div>
      </div>

      {/* Country filter */}
      <div className="flex items-center gap-2">
        {["all", "SE", "NO", "DK"].map((c) => (
          <button key={c} type="button" onClick={() => setCountryFilter(c)}
            className={`rounded-full px-3 py-1 text-xs font-medium transition-colors ${
              countryFilter === c ? "bg-[#1a2332] text-white" : "bg-gray-100 text-gray-600 hover:bg-gray-200"
            }`}>
            {c === "all" ? "All" : `${COUNTRY_FLAGS[c]} ${c}`}
          </button>
        ))}
      </div>

      {/* Create form */}
      {showNew && (
        <div className="rounded-xl border border-[#1a2332]/20 bg-white p-5 shadow-sm space-y-3">
          <h3 className="text-sm font-semibold text-gray-900">New Regulatory Event</h3>
          <input value={newForm.title} onChange={(e) => setNewForm((f) => ({ ...f, title: e.target.value }))}
            placeholder="Event title *"
            className="block w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-[#1a2332]" />
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            <div className="space-y-1">
              <label className="text-xs font-medium text-gray-700">Event Type</label>
              <input value={newForm.event_type} onChange={(e) => setNewForm((f) => ({ ...f, event_type: e.target.value }))}
                placeholder="VAT, AGM, Filing…"
                className="block w-full rounded-md border border-gray-300 px-2 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-[#1a2332]" />
            </div>
            <div className="space-y-1">
              <label className="text-xs font-medium text-gray-700">Country</label>
              <select value={newForm.country} onChange={(e) => setNewForm((f) => ({ ...f, country: e.target.value }))}
                className="block w-full rounded-md border border-gray-300 px-2 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-[#1a2332]">
                <option value="SE">🇸🇪 Sweden</option>
                <option value="NO">🇳🇴 Norway</option>
                <option value="DK">🇩🇰 Denmark</option>
              </select>
            </div>
            <div className="space-y-1">
              <label className="text-xs font-medium text-gray-700">Due Date *</label>
              <input type="date" value={newForm.due_date} onChange={(e) => setNewForm((f) => ({ ...f, due_date: e.target.value }))}
                className="block w-full rounded-md border border-gray-300 px-2 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-[#1a2332]" />
            </div>
            <div className="space-y-1">
              <label className="text-xs font-medium text-gray-700">Recurrence</label>
              <select value={newForm.recurrence} onChange={(e) => setNewForm((f) => ({ ...f, recurrence: e.target.value }))}
                className="block w-full rounded-md border border-gray-300 px-2 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-[#1a2332]">
                <option value="">None</option>
                <option value="monthly">Monthly</option>
                <option value="quarterly">Quarterly</option>
                <option value="annual">Annual</option>
              </select>
            </div>
          </div>
          <textarea value={newForm.notes} onChange={(e) => setNewForm((f) => ({ ...f, notes: e.target.value }))}
            placeholder="Notes (optional)" rows={2}
            className="block w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-[#1a2332]" />
          <div className="flex gap-2">
            <Button variant="outline" onClick={() => setShowNew(false)}>Cancel</Button>
            <Button disabled={actionLoading === "create"} onClick={createEvent}
              className="bg-[#1a2332] hover:bg-[#2a3342] text-white">
              {actionLoading === "create" ? "Saving…" : "Add Event"}
            </Button>
          </div>
        </div>
      )}

      {/* Calendar grouped list */}
      {loading && events.length === 0 ? (
        <div className="text-center py-12"><RefreshCw className="h-6 w-6 animate-spin mx-auto text-muted-foreground" /></div>
      ) : sorted.length === 0 ? (
        <div className="rounded-xl border bg-white p-12 text-center shadow-sm">
          <Calendar className="h-10 w-10 text-muted-foreground mx-auto mb-3" />
          <p className="text-gray-600 font-medium">No regulatory events found</p>
          <p className="text-sm text-muted-foreground mt-1">Use the Seed buttons to pre-populate common deadlines.</p>
        </div>
      ) : (
        <div className="space-y-6">
          {Object.entries(grouped).map(([month, monthEvents]) => (
            <div key={month}>
              <h3 className="text-xs font-semibold text-muted-foreground uppercase tracking-wide mb-3">{month}</h3>
              <div className="rounded-xl border bg-white shadow-sm divide-y divide-gray-100">
                {monthEvents.map((ev) => (
                  <div key={ev.id} className="flex items-center gap-4 px-5 py-3.5">
                    <span className="text-xl flex-shrink-0">{COUNTRY_FLAGS[ev.country] ?? "🌐"}</span>
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-medium text-gray-900 truncate">{ev.title}</p>
                      <p className="text-xs text-muted-foreground mt-0.5">
                        Due {new Date(ev.due_date).toLocaleDateString()}
                        {ev.event_type && ` · ${ev.event_type}`}
                        {ev.recurrence && ` · ${ev.recurrence}`}
                      </p>
                    </div>
                    <span className={styles[STATUS_MODULE[ev.status] ?? "statusUpcoming"]}>
                      {ev.status}
                    </span>
                    {(ev.status === "upcoming" || ev.status === "overdue") && (
                      <Button size="sm" variant="outline"
                        disabled={actionLoading === ev.id + "_complete"}
                        onClick={() => markComplete(ev.id)}
                        className="gap-1 text-xs h-7 flex-shrink-0">
                        {actionLoading === ev.id + "_complete"
                          ? <RefreshCw className="h-3 w-3 animate-spin" />
                          : <CheckCircle2 className="h-3 w-3" />}
                        Mark Complete
                      </Button>
                    )}
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
