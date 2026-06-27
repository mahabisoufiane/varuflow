"use client";

import { useEffect, useState } from "react";
import { useRouter, useParams } from "next/navigation";
import { createClient } from "@/lib/supabase/client";
import {
  RefreshCw, Trash2, Calendar, Receipt, Star, Gift,
  MessageCircle, FileText, Camera, ThumbsUp, PlusCircle, Search,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { toast } from "sonner";

interface HistoryEvent {
  id: string;
  event_type: string;
  event_date: string;
  title: string;
  description: string | null;
  amount: number | null;
  currency: string | null;
}

interface HistorySummary {
  total_appointments: number;
  total_spend: number;
  spend_currency: string;
  loyalty_points_earned: number;
  last_visit: string | null;
  member_since: string | null;
}

const EVENT_TYPE_CONFIG: Record<string, { Icon: React.ElementType; color: string; label: string }> = {
  appointment:    { Icon: Calendar,       color: "text-blue-600 bg-blue-100",   label: "Appointment" },
  purchase:       { Icon: Receipt,        color: "text-green-600 bg-green-100", label: "Purchase"    },
  invoice:        { Icon: Receipt,        color: "text-green-600 bg-green-100", label: "Invoice"     },
  loyalty_earn:   { Icon: Star,           color: "text-amber-600 bg-amber-100", label: "Loyalty Earn"},
  loyalty_redeem: { Icon: Gift,           color: "text-purple-600 bg-purple-100",label: "Loyalty Redeem"},
  message:        { Icon: MessageCircle,  color: "text-gray-600 bg-gray-100",   label: "Message"     },
  note:           { Icon: FileText,       color: "text-gray-600 bg-gray-100",   label: "Note"        },
  photo:          { Icon: Camera,         color: "text-pink-600 bg-pink-100",   label: "Photo"       },
  review:         { Icon: ThumbsUp,       color: "text-yellow-600 bg-yellow-100",label: "Review"     },
};

const FILTER_CHIPS = [
  { key: "all",         label: "All"         },
  { key: "appointment", label: "Appointment" },
  { key: "purchase",    label: "Purchase"    },
  { key: "loyalty_earn",label: "Loyalty"     },
  { key: "message",     label: "Message"     },
  { key: "note",        label: "Note"        },
];

function formatCurrency(amount: number, currency: string | null): string {
  const c = currency ?? "SEK";
  return new Intl.NumberFormat("sv-SE", { style: "currency", currency: c, maximumFractionDigits: 0 }).format(amount);
}

function formatEventDate(dateStr: string): string {
  const d = new Date(dateStr);
  return d.toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric" }) +
    " at " + d.toLocaleTimeString("en-GB", { hour: "2-digit", minute: "2-digit" });
}

export default function CustomerHistoryPage() {
  const router = useRouter();
  const params = useParams<{ locale: string }>();
  const locale = params?.locale ?? "en";
  const supabase = createClient();

  const [customerId, setCustomerId] = useState("");
  const [events, setEvents] = useState<HistoryEvent[]>([]);
  const [summary, setSummary] = useState<HistorySummary | null>(null);
  const [loaded, setLoaded] = useState(false);
  const [loading, setLoading] = useState(false);
  const [actionLoading, setActionLoading] = useState<string | null>(null);
  const [filter, setFilter] = useState("all");

  const [logForm, setLogForm] = useState({
    event_type: "appointment",
    event_date: new Date().toISOString().slice(0, 16),
    title: "",
    description: "",
    amount: "",
    currency: "SEK",
  });
  const [showLogForm, setShowLogForm] = useState(false);

  async function getToken() {
    const { data: { session } } = await supabase.auth.getSession();
    return session?.access_token ?? null;
  }
  function apiUrl(p: string) { return `${process.env.NEXT_PUBLIC_API_URL}${p}`; }

  // Auto-load if customerId is set on mount (e.g. from query param) — not needed, just use button
  useEffect(() => {}, []); // eslint-disable-line react-hooks/exhaustive-deps

  async function loadHistory() {
    if (!customerId.trim()) { toast.error("Enter a customer ID"); return; }
    setLoading(true);
    try {
      const token = await getToken();
      if (!token) { router.push(`/${locale}/auth/login`); return; }
      const [evtRes, sumRes] = await Promise.all([
        fetch(apiUrl(`/api/history/${customerId}`), { headers: { Authorization: `Bearer ${token}` } }),
        fetch(apiUrl(`/api/history/${customerId}/summary`), { headers: { Authorization: `Bearer ${token}` } }),
      ]);
      if (evtRes.status === 401) { router.push(`/${locale}/auth/login`); return; }
      if (evtRes.ok) setEvents(await evtRes.json());
      else {
        const b = await evtRes.json().catch(() => ({}));
        toast.error(b.detail ?? "Failed to load history");
      }
      if (sumRes.ok) setSummary(await sumRes.json());
      setLoaded(true);
    } catch {
      toast.error("Failed to load history");
    } finally {
      setLoading(false);
    }
  }

  async function backfill() {
    if (!customerId.trim()) return;
    setActionLoading("backfill");
    try {
      const token = await getToken();
      if (!token) return;
      const res = await fetch(apiUrl(`/api/history/${customerId}/backfill`), {
        method: "POST",
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) {
        const b = await res.json().catch(() => ({}));
        toast.error(b.detail ?? "Backfill failed");
        return;
      }
      const data = await res.json();
      toast.success(`Created ${data.created ?? 0} events, skipped ${data.skipped ?? 0} already logged`);
      await loadHistory();
    } catch {
      toast.error("Something went wrong");
    } finally {
      setActionLoading(null);
    }
  }

  async function logEvent() {
    if (!customerId.trim()) { toast.error("Load a customer first"); return; }
    if (!logForm.title.trim()) { toast.error("Title is required"); return; }
    setActionLoading("log");
    try {
      const token = await getToken();
      if (!token) return;
      const res = await fetch(apiUrl(`/api/history/${customerId}`), {
        method: "POST",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
        body: JSON.stringify({
          event_type: logForm.event_type,
          event_date: new Date(logForm.event_date).toISOString(),
          title: logForm.title,
          description: logForm.description || null,
          amount: logForm.amount ? parseFloat(logForm.amount) : null,
          currency: logForm.currency,
        }),
      });
      if (!res.ok) {
        const b = await res.json().catch(() => ({}));
        toast.error(b.detail ?? "Failed to log event");
        return;
      }
      toast.success("Event logged");
      setLogForm({ event_type: "appointment", event_date: new Date().toISOString().slice(0, 16), title: "", description: "", amount: "", currency: "SEK" });
      setShowLogForm(false);
      await loadHistory();
    } catch {
      toast.error("Something went wrong");
    } finally {
      setActionLoading(null);
    }
  }

  async function deleteEvent(id: string) {
    setActionLoading("del_" + id);
    try {
      const token = await getToken();
      if (!token) return;
      const res = await fetch(apiUrl(`/api/history/events/${id}`), {
        method: "DELETE",
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) {
        const b = await res.json().catch(() => ({}));
        toast.error(b.detail ?? "Failed to delete event");
        return;
      }
      toast.success("Event deleted");
      await loadHistory();
    } catch {
      toast.error("Something went wrong");
    } finally {
      setActionLoading(null);
    }
  }

  const filteredEvents = filter === "all"
    ? events
    : events.filter((e) => {
        if (filter === "loyalty_earn") return e.event_type === "loyalty_earn" || e.event_type === "loyalty_redeem";
        if (filter === "purchase") return e.event_type === "purchase" || e.event_type === "invoice";
        return e.event_type === filter;
      });

  const sortedEvents = filteredEvents.slice().sort(
    (a, b) => new Date(b.event_date).getTime() - new Date(a.event_date).getTime()
  );

  return (
    <div className="mx-auto max-w-4xl space-y-6 p-6">
      {/* Header */}
      <div>
        <h1 className="text-xl font-semibold text-gray-900">Customer History</h1>
        <p className="text-sm text-muted-foreground mt-0.5">
          View and manage the full service history timeline for any customer.
        </p>
      </div>

      {/* Customer lookup */}
      <div className="rounded-xl border border-[#1a2332]/20 bg-white p-5 shadow-sm space-y-3">
        <h3 className="text-sm font-semibold text-gray-900">Customer Lookup</h3>
        <div className="flex gap-3">
          <input
            value={customerId}
            onChange={(e) => setCustomerId(e.target.value)}
            onKeyDown={(e) => { if (e.key === "Enter") loadHistory(); }}
            placeholder="Customer UUID"
            className="flex-1 rounded-md border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-[#1a2332]"
          />
          <Button disabled={loading} onClick={loadHistory}
            className="bg-[#1a2332] hover:bg-[#2a3342] text-white gap-2">
            {loading ? <RefreshCw className="h-4 w-4 animate-spin" /> : <Search className="h-4 w-4" />}
            Load History
          </Button>
        </div>
      </div>

      {/* Summary cards */}
      {loaded && summary && (
        <div className="grid grid-cols-5 gap-3">
          <div className="rounded-xl border bg-white shadow-sm p-4 text-center">
            <p className="text-2xl font-bold text-gray-900">{summary.total_appointments}</p>
            <p className="text-xs text-muted-foreground mt-1">Appointments</p>
          </div>
          <div className="rounded-xl border bg-white shadow-sm p-4 text-center">
            <p className="text-lg font-bold text-gray-900 truncate">
              {formatCurrency(summary.total_spend, summary.spend_currency)}
            </p>
            <p className="text-xs text-muted-foreground mt-1">Total Spend</p>
          </div>
          <div className="rounded-xl border bg-white shadow-sm p-4 text-center">
            <p className="text-2xl font-bold text-amber-600">{summary.loyalty_points_earned}</p>
            <p className="text-xs text-muted-foreground mt-1">Loyalty Points</p>
          </div>
          <div className="rounded-xl border bg-white shadow-sm p-4 text-center">
            <p className="text-sm font-semibold text-gray-900">
              {summary.last_visit ? new Date(summary.last_visit).toLocaleDateString() : "—"}
            </p>
            <p className="text-xs text-muted-foreground mt-1">Last Visit</p>
          </div>
          <div className="rounded-xl border bg-white shadow-sm p-4 text-center">
            <p className="text-sm font-semibold text-gray-900">
              {summary.member_since ? new Date(summary.member_since).toLocaleDateString() : "—"}
            </p>
            <p className="text-xs text-muted-foreground mt-1">Member Since</p>
          </div>
        </div>
      )}

      {/* Action buttons (after load) */}
      {loaded && (
        <div className="flex items-center gap-3 flex-wrap">
          <Button variant="outline" onClick={() => setShowLogForm((v) => !v)} className="gap-2">
            <PlusCircle className="h-4 w-4" /> Log Event
          </Button>
          <Button variant="outline"
            disabled={actionLoading === "backfill"}
            onClick={backfill}
            className="gap-2"
          >
            {actionLoading === "backfill" ? <RefreshCw className="h-4 w-4 animate-spin" /> : <RefreshCw className="h-4 w-4" />}
            Backfill from Existing Data
          </Button>
        </div>
      )}

      {/* Log event form */}
      {showLogForm && (
        <div className="rounded-xl border border-[#1a2332]/20 bg-white p-5 shadow-sm space-y-3">
          <h3 className="text-sm font-semibold text-gray-900">Log Event</h3>
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1">
              <label className="text-xs font-medium text-gray-700">Event Type</label>
              <select
                value={logForm.event_type}
                onChange={(e) => setLogForm((f) => ({ ...f, event_type: e.target.value }))}
                className="block w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-[#1a2332]"
              >
                {Object.entries(EVENT_TYPE_CONFIG).map(([val, cfg]) => (
                  <option key={val} value={val}>{cfg.label}</option>
                ))}
              </select>
            </div>
            <div className="space-y-1">
              <label className="text-xs font-medium text-gray-700">Event Date *</label>
              <input
                type="datetime-local"
                value={logForm.event_date}
                onChange={(e) => setLogForm((f) => ({ ...f, event_date: e.target.value }))}
                className="block w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-[#1a2332]"
              />
            </div>
          </div>
          <div className="space-y-1">
            <label className="text-xs font-medium text-gray-700">Title *</label>
            <input
              value={logForm.title}
              onChange={(e) => setLogForm((f) => ({ ...f, title: e.target.value }))}
              placeholder="Service appointment"
              className="block w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-[#1a2332]"
            />
          </div>
          <div className="space-y-1">
            <label className="text-xs font-medium text-gray-700">Description</label>
            <textarea
              rows={2}
              value={logForm.description}
              onChange={(e) => setLogForm((f) => ({ ...f, description: e.target.value }))}
              className="block w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-[#1a2332]"
            />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1">
              <label className="text-xs font-medium text-gray-700">Amount</label>
              <input
                type="number"
                step="any"
                value={logForm.amount}
                onChange={(e) => setLogForm((f) => ({ ...f, amount: e.target.value }))}
                placeholder="0"
                className="block w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-[#1a2332]"
              />
            </div>
            <div className="space-y-1">
              <label className="text-xs font-medium text-gray-700">Currency</label>
              <select
                value={logForm.currency}
                onChange={(e) => setLogForm((f) => ({ ...f, currency: e.target.value }))}
                className="block w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-[#1a2332]"
              >
                <option>SEK</option>
                <option>NOK</option>
                <option>DKK</option>
                <option>EUR</option>
              </select>
            </div>
          </div>
          <div className="flex gap-2">
            <Button variant="outline" onClick={() => setShowLogForm(false)}>Cancel</Button>
            <Button disabled={actionLoading === "log"} onClick={logEvent}
              className="bg-[#1a2332] hover:bg-[#2a3342] text-white">
              {actionLoading === "log" ? "Saving…" : "Save Event"}
            </Button>
          </div>
        </div>
      )}

      {/* Empty state before lookup */}
      {!loaded && (
        <div className="rounded-xl border bg-white shadow-sm py-16 text-center">
          <Calendar className="h-12 w-12 text-muted-foreground mx-auto mb-4" />
          <p className="text-gray-600 font-medium">Enter a customer ID above to view their full history with your business.</p>
          <p className="text-sm text-muted-foreground mt-1">Appointments, purchases, loyalty points, and more.</p>
        </div>
      )}

      {/* Timeline */}
      {loaded && (
        <div className="space-y-4">
          {/* Filter chips */}
          <div className="flex flex-wrap gap-2">
            {FILTER_CHIPS.map((chip) => (
              <button
                key={chip.key}
                type="button"
                onClick={() => setFilter(chip.key)}
                className={`rounded-full px-3 py-1 text-xs font-medium border transition-colors ${
                  filter === chip.key
                    ? "bg-[#1a2332] text-white border-[#1a2332]"
                    : "bg-white text-gray-600 border-gray-300 hover:border-gray-400"
                }`}
              >
                {chip.label}
              </button>
            ))}
          </div>

          {sortedEvents.length === 0 ? (
            <div className="rounded-xl border bg-white shadow-sm py-10 text-center">
              <p className="text-muted-foreground text-sm">No events found{filter !== "all" ? " for this filter" : ""}.</p>
            </div>
          ) : (
            <div className="space-y-0">
              {sortedEvents.map((evt, idx) => {
                const cfg = EVENT_TYPE_CONFIG[evt.event_type] ?? EVENT_TYPE_CONFIG.note;
                const Icon = cfg.Icon;
                const isLast = idx === sortedEvents.length - 1;
                return (
                  <div key={evt.id} className="flex gap-4">
                    {/* Vertical line + icon */}
                    <div className="flex flex-col items-center flex-shrink-0 pt-1">
                      <div className={`h-8 w-8 rounded-full flex items-center justify-center ${cfg.color}`}>
                        <Icon className="h-4 w-4" />
                      </div>
                      {!isLast && <div className="w-px flex-1 bg-gray-200 my-1" style={{ minHeight: "1rem" }} />}
                    </div>

                    {/* Content */}
                    <div className={`flex-1 min-w-0 ${isLast ? "pb-0" : "pb-6"}`}>
                      <div className="rounded-xl border bg-white shadow-sm px-4 py-3">
                        <div className="flex items-start justify-between gap-3">
                          <div className="min-w-0">
                            <p className="text-sm font-medium text-gray-900">{evt.title}</p>
                            {evt.description && (
                              <p className="text-xs text-muted-foreground mt-0.5">{evt.description}</p>
                            )}
                            <div className="flex items-center gap-3 mt-1">
                              <p className="text-xs text-muted-foreground">{formatEventDate(evt.event_date)}</p>
                              {evt.amount != null && (
                                <span className="text-xs font-medium text-green-700">
                                  {formatCurrency(evt.amount, evt.currency)}
                                </span>
                              )}
                            </div>
                          </div>
                          <Button variant="ghost" size="sm"
                            disabled={actionLoading === "del_" + evt.id}
                            onClick={() => deleteEvent(evt.id)}
                            className="flex-shrink-0 text-red-400 hover:text-red-600 hover:bg-red-50"
                          >
                            {actionLoading === "del_" + evt.id
                              ? <RefreshCw className="h-3 w-3 animate-spin" />
                              : <Trash2 className="h-3 w-3" />}
                          </Button>
                        </div>
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
