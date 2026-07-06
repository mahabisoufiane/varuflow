"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api-client";
import { RefreshCw, Clock, PlusCircle } from "lucide-react";
import { Button } from "@/components/ui/button";
import { toast } from "sonner";
import styles from "./page.module.scss";

interface WaitlistEntry {
  id: string;
  customer_id: string;
  service_id: string | null;
  preferred_date: string | null;
  preferred_time_from: string | null;
  preferred_time_to: string | null;
  flexibility_days: number;
  status: string;
  notified_at: string | null;
  created_at: string;
  notes: string | null;
}

const STATUS_CONFIG: Record<string, { label: string; color: string }> = {
  waiting: { label: "Waiting", color: "bg-blue-100 text-blue-700" },
  offered: { label: "Offered", color: "bg-amber-100 text-amber-700" },
  booked: { label: "Booked", color: "bg-green-100 text-green-700" },
  expired: { label: "Expired", color: "bg-gray-100 text-gray-500" },
  cancelled: { label: "Cancelled", color: "bg-gray-100 text-gray-500" },
};

const STATUS_MODULE: Record<string, keyof typeof styles> = {
  waiting:   "statusWaiting",
  offered:   "statusOffered",
  booked:    "statusBooked",
  expired:   "statusExpired",
  cancelled: "statusCancelled",
};

type StatusFilter = "all" | "waiting" | "offered" | "booked" | "expired" | "cancelled";

export default function WaitlistPage() {
  const [entries, setEntries] = useState<WaitlistEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState<StatusFilter>("all");
  const [actionLoading, setActionLoading] = useState<string | null>(null);
  const [showAddForm, setShowAddForm] = useState(false);
  const [addForm, setAddForm] = useState({
    customer_id: "",
    service_id: "",
    preferred_date: "",
    preferred_time_from: "",
    preferred_time_to: "",
    flexibility_days: "0",
    notes: "",
  });

  async function load() {
    setLoading(true);
    try {
      const data = await api.get<WaitlistEntry[]>("/api/booking-waitlist");
      data.sort((a, b) => new Date(a.created_at).getTime() - new Date(b.created_at).getTime());
      setEntries(data);
    } catch {
      toast.error("Failed to load waitlist");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { load(); }, []);  // eslint-disable-line react-hooks/exhaustive-deps

  async function addToWaitlist() {
    if (!addForm.customer_id.trim()) { toast.error("Customer ID is required"); return; }
    setActionLoading("add");
    try {
      await api.post("/api/booking-waitlist", {
        customer_id: addForm.customer_id,
        service_id: addForm.service_id || null,
        preferred_date: addForm.preferred_date || null,
        preferred_time_from: addForm.preferred_time_from || null,
        preferred_time_to: addForm.preferred_time_to || null,
        flexibility_days: parseInt(addForm.flexibility_days),
        notes: addForm.notes || null,
      });
      toast.success("Added to waitlist");
      setShowAddForm(false);
      setAddForm({ customer_id: "", service_id: "", preferred_date: "", preferred_time_from: "", preferred_time_to: "", flexibility_days: "0", notes: "" });
      await load();
    } catch {
      toast.error("Something went wrong");
    } finally {
      setActionLoading(null);
    }
  }

  async function notifyEntry(id: string) {
    setActionLoading(id + "_notify");
    try {
      await api.post(`/api/booking-waitlist/${id}/notify`, {});
      toast.success("Customer notified, offer expires in 24h");
      await load();
    } catch {
      toast.error("Something went wrong");
    } finally {
      setActionLoading(null);
    }
  }

  async function bookEntry(id: string) {
    setActionLoading(id + "_book");
    try {
      await api.post(`/api/booking-waitlist/${id}/book`, {});
      toast.success("Waitlist booking confirmed");
      await load();
    } catch {
      toast.error("Something went wrong");
    } finally {
      setActionLoading(null);
    }
  }

  async function removeEntry(id: string) {
    setActionLoading(id + "_remove");
    try {
      await api.delete(`/api/booking-waitlist/${id}`);
      toast.success("Removed from waitlist");
      await load();
    } catch {
      toast.error("Something went wrong");
    } finally {
      setActionLoading(null);
    }
  }

  const filtered = entries.filter((e) => filter === "all" || e.status === filter);
  const inputCls = "block w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-[var(--vf-brand-primary)]";

  return (
    <div className="mx-auto max-w-4xl space-y-6 p-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-gray-900">Booking Waitlist</h1>
          <p className="text-sm text-muted-foreground mt-0.5">Auto-offer open slots to customers on the waitlist.</p>
        </div>
        <Button onClick={() => setShowAddForm((s) => !s)} className="bg-[var(--vf-brand-primary)] hover:bg-[var(--vf-brand-primary-hover)] text-white gap-2">
          <PlusCircle className="h-4 w-4" /> Add to Waitlist
        </Button>
      </div>

      {/* Filter tabs */}
      <div className="flex gap-1 border-b overflow-x-auto">
        {(["all", "waiting", "offered", "booked", "expired", "cancelled"] as StatusFilter[]).map((f) => (
          <button key={f} type="button" onClick={() => setFilter(f)}
            className={`px-4 py-2.5 text-sm font-medium border-b-2 whitespace-nowrap capitalize transition-colors ${
              filter === f ? "border-[var(--vf-brand-primary)] text-[var(--vf-text-primary)]" : "border-transparent text-muted-foreground hover:text-gray-700"
            }`}>
            {f === "all" ? "All" : f.charAt(0).toUpperCase() + f.slice(1)}
          </button>
        ))}
      </div>

      {/* Add form */}
      {showAddForm && (
        <div className="rounded-xl border border-[var(--vf-brand-primary)]/20 bg-white p-5 shadow-sm space-y-3">
          <h3 className="text-sm font-semibold text-gray-900">Add to Waitlist</h3>
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1">
              <label className="text-xs font-medium text-gray-700">Customer ID *</label>
              <input value={addForm.customer_id}
                onChange={(e) => setAddForm((f) => ({ ...f, customer_id: e.target.value }))}
                placeholder="UUID" className={inputCls} />
            </div>
            <div className="space-y-1">
              <label className="text-xs font-medium text-gray-700">Service ID (optional)</label>
              <input value={addForm.service_id}
                onChange={(e) => setAddForm((f) => ({ ...f, service_id: e.target.value }))}
                placeholder="UUID" className={inputCls} />
            </div>
            <div className="space-y-1">
              <label className="text-xs font-medium text-gray-700">Preferred Date</label>
              <input type="date" value={addForm.preferred_date}
                onChange={(e) => setAddForm((f) => ({ ...f, preferred_date: e.target.value }))}
                className={inputCls} />
            </div>
            <div className="space-y-1">
              <label className="text-xs font-medium text-gray-700">Flexibility (days)</label>
              <input type="number" min="0" value={addForm.flexibility_days}
                onChange={(e) => setAddForm((f) => ({ ...f, flexibility_days: e.target.value }))}
                className={inputCls} />
            </div>
            <div className="space-y-1">
              <label className="text-xs font-medium text-gray-700">Preferred From</label>
              <input type="time" value={addForm.preferred_time_from}
                onChange={(e) => setAddForm((f) => ({ ...f, preferred_time_from: e.target.value }))}
                className={inputCls} />
            </div>
            <div className="space-y-1">
              <label className="text-xs font-medium text-gray-700">Preferred To</label>
              <input type="time" value={addForm.preferred_time_to}
                onChange={(e) => setAddForm((f) => ({ ...f, preferred_time_to: e.target.value }))}
                className={inputCls} />
            </div>
          </div>
          <div className="space-y-1">
            <label className="text-xs font-medium text-gray-700">Notes</label>
            <input value={addForm.notes}
              onChange={(e) => setAddForm((f) => ({ ...f, notes: e.target.value }))}
              placeholder="Any special requirements…" className={inputCls} />
          </div>
          <div className="flex gap-2">
            <Button variant="outline" onClick={() => setShowAddForm(false)}>Cancel</Button>
            <Button disabled={actionLoading === "add"} onClick={addToWaitlist}
              className="bg-[var(--vf-brand-primary)] hover:bg-[var(--vf-brand-primary-hover)] text-white">
              {actionLoading === "add" ? "Adding…" : "Add to Waitlist"}
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
            <Clock className="h-10 w-10 text-muted-foreground mx-auto mb-3" />
            <p className="text-gray-600 font-medium">No waitlist entries found</p>
          </div>
        ) : (
          <div className="divide-y divide-gray-100">
            {filtered.map((e, idx) => {
              const cfg = STATUS_CONFIG[e.status] ?? STATUS_CONFIG.waiting;
              const isLoading = (key: string) => actionLoading === e.id + "_" + key;
              return (
                <div key={e.id} className="flex items-center gap-4 px-5 py-4">
                  <span className="flex-shrink-0 w-6 text-center text-xs font-medium text-muted-foreground">
                    {idx + 1}
                  </span>
                  <div className="flex-1 min-w-0 space-y-0.5">
                    <div className="flex items-center gap-2">
                      <p className="text-xs font-mono text-gray-700">{e.customer_id.slice(0, 8)}…</p>
                      {e.service_id && (
                        <>
                          <span className="text-muted-foreground">·</span>
                          <p className="text-xs font-mono text-gray-500">{e.service_id.slice(0, 8)}…</p>
                        </>
                      )}
                    </div>
                    <p className="text-xs text-muted-foreground">
                      {e.preferred_date && new Date(e.preferred_date).toLocaleDateString()}
                      {e.preferred_time_from && ` · ${e.preferred_time_from}`}
                      {e.preferred_time_to && ` – ${e.preferred_time_to}`}
                      {e.flexibility_days > 0 && ` (±${e.flexibility_days}d flex)`}
                    </p>
                    {e.notified_at && (
                      <p className="text-xs text-amber-700">
                        Notified {new Date(e.notified_at).toLocaleDateString()}
                      </p>
                    )}
                  </div>
                  <span className={styles[STATUS_MODULE[e.status] ?? "statusWaiting"]}>
                    {cfg.label}
                  </span>
                  <div className="flex items-center gap-1.5 flex-shrink-0">
                    {e.status === "waiting" && (
                      <Button variant="outline" size="sm" disabled={!!actionLoading}
                        onClick={() => notifyEntry(e.id)}>
                        {isLoading("notify") ? <RefreshCw className="h-3 w-3 animate-spin" /> : "Notify"}
                      </Button>
                    )}
                    {e.status === "offered" && (
                      <Button size="sm" disabled={!!actionLoading}
                        onClick={() => bookEntry(e.id)}
                        className="bg-green-600 hover:bg-green-700 text-white">
                        {isLoading("book") ? <RefreshCw className="h-3 w-3 animate-spin" /> : "Book"}
                      </Button>
                    )}
                    <Button variant="ghost" size="sm" disabled={!!actionLoading}
                      onClick={() => removeEntry(e.id)}>
                      {isLoading("remove")
                        ? <RefreshCw className="h-3.5 w-3.5 animate-spin" />
                        : <span className="text-xs text-red-500">Remove</span>}
                    </Button>
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
