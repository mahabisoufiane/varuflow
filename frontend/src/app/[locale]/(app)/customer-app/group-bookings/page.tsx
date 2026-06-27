"use client";

import { useEffect, useState } from "react";
import { useRouter, useParams } from "next/navigation";
import { createClient } from "@/lib/supabase/client";
import { RefreshCw, UserPlus, ChevronDown, ChevronRight, PlusCircle, Trash2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { toast } from "sonner";

interface GroupParticipant {
  id: string;
  name: string;
  email: string | null;
  amount_due: number;
  paid: boolean;
}

interface GroupBooking {
  id: string;
  lead_customer_id: string;
  service_id: string;
  title: string | null;
  party_size: number;
  status: string;
  split_payment: boolean;
  total_amount: number | null;
  participants: GroupParticipant[];
}

const STATUS_CONFIG: Record<string, { label: string; color: string }> = {
  pending: { label: "Pending", color: "bg-amber-100 text-amber-700" },
  confirmed: { label: "Confirmed", color: "bg-green-100 text-green-700" },
  cancelled: { label: "Cancelled", color: "bg-gray-100 text-gray-500" },
};

type StatusFilter = "all" | "pending" | "confirmed" | "cancelled";

interface ParticipantDraft {
  name: string;
  email: string;
  amount_due: string;
}

export default function GroupBookingsPage() {
  const router = useRouter();
  const params = useParams<{ locale: string }>();
  const locale = params?.locale ?? "en";
  const supabase = createClient();

  const [bookings, setBookings] = useState<GroupBooking[]>([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState<StatusFilter>("all");
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [actionLoading, setActionLoading] = useState<string | null>(null);
  const [showCreateForm, setShowCreateForm] = useState(false);
  const [createForm, setCreateForm] = useState({
    lead_customer_id: "",
    service_id: "",
    title: "",
    party_size: "2",
    split_payment: false,
    total_amount: "",
  });
  const [participants, setParticipants] = useState<ParticipantDraft[]>([
    { name: "", email: "", amount_due: "" },
  ]);

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
      const res = await fetch(apiUrl("/api/group-bookings"), {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (res.status === 401) { router.push(`/${locale}/auth/login`); return; }
      if (res.ok) setBookings(await res.json());
    } catch {
      toast.error("Failed to load group bookings");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { load(); }, []);  // eslint-disable-line react-hooks/exhaustive-deps

  async function createBooking() {
    if (!createForm.lead_customer_id.trim() || !createForm.service_id.trim()) {
      toast.error("Lead customer ID and service ID are required");
      return;
    }
    setActionLoading("create");
    try {
      const token = await getToken();
      if (!token) return;
      const res = await fetch(apiUrl("/api/group-bookings"), {
        method: "POST",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
        body: JSON.stringify({
          lead_customer_id: createForm.lead_customer_id,
          service_id: createForm.service_id,
          title: createForm.title || null,
          party_size: parseInt(createForm.party_size),
          split_payment: createForm.split_payment,
          total_amount: createForm.total_amount ? parseFloat(createForm.total_amount) : null,
          participants: participants
            .filter((p) => p.name.trim())
            .map((p) => ({
              name: p.name,
              email: p.email || null,
              amount_due: p.amount_due ? parseFloat(p.amount_due) : 0,
            })),
        }),
      });
      if (!res.ok) {
        const b = await res.json().catch(() => ({}));
        toast.error(b.detail ?? "Failed to create group booking");
        return;
      }
      toast.success("Group booking created");
      setShowCreateForm(false);
      setCreateForm({ lead_customer_id: "", service_id: "", title: "", party_size: "2", split_payment: false, total_amount: "" });
      setParticipants([{ name: "", email: "", amount_due: "" }]);
      await load();
    } catch {
      toast.error("Something went wrong");
    } finally {
      setActionLoading(null);
    }
  }

  async function changeStatus(id: string, action: "confirm" | "cancel") {
    setActionLoading(id + "_" + action);
    try {
      const token = await getToken();
      if (!token) return;
      const res = await fetch(apiUrl(`/api/group-bookings/${id}/${action}`), {
        method: "POST",
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) {
        const b = await res.json().catch(() => ({}));
        toast.error(b.detail ?? `Failed to ${action}`);
        return;
      }
      toast.success(`Booking ${action}ed`);
      await load();
    } catch {
      toast.error("Something went wrong");
    } finally {
      setActionLoading(null);
    }
  }

  async function markPaid(bookingId: string, participantId: string) {
    setActionLoading(participantId + "_paid");
    try {
      const token = await getToken();
      if (!token) return;
      const res = await fetch(apiUrl(`/api/group-bookings/${bookingId}/participants/${participantId}`), {
        method: "PATCH",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
        body: JSON.stringify({ paid: true }),
      });
      if (!res.ok) {
        const b = await res.json().catch(() => ({}));
        toast.error(b.detail ?? "Failed to mark paid");
        return;
      }
      toast.success("Marked as paid");
      await load();
    } catch {
      toast.error("Something went wrong");
    } finally {
      setActionLoading(null);
    }
  }

  function addParticipantRow() {
    setParticipants((p) => [...p, { name: "", email: "", amount_due: "" }]);
  }

  function updateParticipant(i: number, field: keyof ParticipantDraft, value: string) {
    setParticipants((ps) => ps.map((p, idx) => idx === i ? { ...p, [field]: value } : p));
  }

  function removeParticipantRow(i: number) {
    setParticipants((ps) => ps.filter((_, idx) => idx !== i));
  }

  const filtered = bookings.filter((b) => filter === "all" || b.status === filter);
  const inputCls = "block w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-[#1a2332]";

  return (
    <div className="mx-auto max-w-4xl space-y-6 p-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-gray-900">Group Bookings</h1>
          <p className="text-sm text-muted-foreground mt-0.5">Book for multiple people with optional split payment.</p>
        </div>
        <Button onClick={() => setShowCreateForm((s) => !s)} className="bg-[#1a2332] hover:bg-[#2a3342] text-white gap-2">
          <PlusCircle className="h-4 w-4" /> New Group Booking
        </Button>
      </div>

      {/* Filter tabs */}
      <div className="flex gap-1 border-b">
        {(["all", "pending", "confirmed", "cancelled"] as StatusFilter[]).map((f) => (
          <button key={f} type="button" onClick={() => setFilter(f)}
            className={`px-4 py-2.5 text-sm font-medium border-b-2 capitalize transition-colors ${
              filter === f ? "border-[#1a2332] text-[#1a2332]" : "border-transparent text-muted-foreground hover:text-gray-700"
            }`}>
            {f === "all" ? "All" : f.charAt(0).toUpperCase() + f.slice(1)}
          </button>
        ))}
      </div>

      {/* Create form */}
      {showCreateForm && (
        <div className="rounded-xl border border-[#1a2332]/20 bg-white p-5 shadow-sm space-y-4">
          <h3 className="text-sm font-semibold text-gray-900">New Group Booking</h3>
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1">
              <label className="text-xs font-medium text-gray-700">Lead Customer ID *</label>
              <input value={createForm.lead_customer_id}
                onChange={(e) => setCreateForm((f) => ({ ...f, lead_customer_id: e.target.value }))}
                placeholder="UUID" className={inputCls} />
            </div>
            <div className="space-y-1">
              <label className="text-xs font-medium text-gray-700">Service ID *</label>
              <input value={createForm.service_id}
                onChange={(e) => setCreateForm((f) => ({ ...f, service_id: e.target.value }))}
                placeholder="UUID" className={inputCls} />
            </div>
            <div className="space-y-1">
              <label className="text-xs font-medium text-gray-700">Title</label>
              <input value={createForm.title}
                onChange={(e) => setCreateForm((f) => ({ ...f, title: e.target.value }))}
                placeholder="Birthday party, team outing…" className={inputCls} />
            </div>
            <div className="space-y-1">
              <label className="text-xs font-medium text-gray-700">Party Size *</label>
              <input type="number" min="2" value={createForm.party_size}
                onChange={(e) => setCreateForm((f) => ({ ...f, party_size: e.target.value }))}
                className={inputCls} />
            </div>
          </div>
          <div className="flex items-center gap-4">
            <label className="flex items-center gap-2 cursor-pointer">
              <input type="checkbox" checked={createForm.split_payment}
                onChange={(e) => setCreateForm((f) => ({ ...f, split_payment: e.target.checked }))}
                className="h-4 w-4 rounded border-gray-300" />
              <span className="text-sm text-gray-700">Split payment</span>
            </label>
            {createForm.split_payment && (
              <div className="flex-1 space-y-1">
                <label className="text-xs font-medium text-gray-700">Total Amount</label>
                <input type="number" value={createForm.total_amount} min="0" step="0.01"
                  onChange={(e) => setCreateForm((f) => ({ ...f, total_amount: e.target.value }))}
                  placeholder="0.00" className={inputCls} />
              </div>
            )}
          </div>

          {/* Participants */}
          <div className="space-y-2">
            <p className="text-xs font-semibold text-gray-700">Participants</p>
            {participants.map((p, i) => (
              <div key={i} className="grid grid-cols-3 gap-2 items-end">
                <div className="space-y-1">
                  <label className="text-xs font-medium text-gray-700">Name *</label>
                  <input value={p.name} onChange={(e) => updateParticipant(i, "name", e.target.value)}
                    placeholder="Full name" className={inputCls} />
                </div>
                <div className="space-y-1">
                  <label className="text-xs font-medium text-gray-700">Email</label>
                  <input type="email" value={p.email} onChange={(e) => updateParticipant(i, "email", e.target.value)}
                    placeholder="email@example.com" className={inputCls} />
                </div>
                <div className="flex gap-2 items-end">
                  <div className="flex-1 space-y-1">
                    <label className="text-xs font-medium text-gray-700">Amount Due</label>
                    <input type="number" value={p.amount_due} min="0" step="0.01"
                      onChange={(e) => updateParticipant(i, "amount_due", e.target.value)}
                      placeholder="0.00" className={inputCls} />
                  </div>
                  {participants.length > 1 && (
                    <Button type="button" variant="ghost" size="sm" onClick={() => removeParticipantRow(i)}
                      className="mb-0.5">
                      <Trash2 className="h-3.5 w-3.5 text-red-500" />
                    </Button>
                  )}
                </div>
              </div>
            ))}
            <Button type="button" variant="outline" size="sm" onClick={addParticipantRow} className="gap-1">
              <PlusCircle className="h-3.5 w-3.5" /> Add Participant
            </Button>
          </div>

          <div className="flex gap-2">
            <Button variant="outline" onClick={() => setShowCreateForm(false)}>Cancel</Button>
            <Button disabled={actionLoading === "create"} onClick={createBooking}
              className="bg-[#1a2332] hover:bg-[#2a3342] text-white">
              {actionLoading === "create" ? "Creating…" : "Create Booking"}
            </Button>
          </div>
        </div>
      )}

      {/* List */}
      <div className="space-y-3">
        {loading ? (
          <div className="rounded-xl border bg-white shadow-sm py-12 text-center">
            <RefreshCw className="h-6 w-6 animate-spin mx-auto text-muted-foreground" />
          </div>
        ) : filtered.length === 0 ? (
          <div className="rounded-xl border bg-white shadow-sm py-12 text-center">
            <UserPlus className="h-10 w-10 text-muted-foreground mx-auto mb-3" />
            <p className="text-gray-600 font-medium">No group bookings found</p>
          </div>
        ) : (
          filtered.map((b) => {
            const cfg = STATUS_CONFIG[b.status] ?? STATUS_CONFIG.pending;
            const isExpanded = expandedId === b.id;
            return (
              <div key={b.id} className="rounded-xl border bg-white shadow-sm">
                <div className="flex items-center gap-3 px-5 py-4">
                  <button type="button" onClick={() => setExpandedId(isExpanded ? null : b.id)}
                    className="flex items-center gap-2 flex-1 min-w-0 text-left">
                    {isExpanded
                      ? <ChevronDown className="h-4 w-4 text-muted-foreground flex-shrink-0" />
                      : <ChevronRight className="h-4 w-4 text-muted-foreground flex-shrink-0" />}
                    <div className="min-w-0">
                      <p className="text-sm font-medium text-gray-900">{b.title ?? "Group booking"}</p>
                      <div className="flex items-center gap-2 mt-0.5">
                        <p className="text-xs font-mono text-muted-foreground">{b.lead_customer_id.slice(0, 8)}…</p>
                        <span className="text-muted-foreground">·</span>
                        <p className="text-xs text-muted-foreground">{b.party_size} people</p>
                      </div>
                    </div>
                  </button>
                  {b.split_payment && (
                    <span className="inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-medium bg-blue-100 text-blue-700">
                      Split Payment
                    </span>
                  )}
                  <span className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-medium ${cfg.color}`}>
                    {cfg.label}
                  </span>
                  <div className="flex items-center gap-1.5 flex-shrink-0">
                    {b.status === "pending" && (
                      <Button size="sm" disabled={!!actionLoading}
                        onClick={() => changeStatus(b.id, "confirm")}
                        className="bg-green-600 hover:bg-green-700 text-white">
                        {actionLoading === b.id + "_confirm" ? <RefreshCw className="h-3 w-3 animate-spin" /> : "Confirm"}
                      </Button>
                    )}
                    {b.status !== "cancelled" && (
                      <Button variant="outline" size="sm" disabled={!!actionLoading}
                        onClick={() => changeStatus(b.id, "cancel")}
                        className="text-red-600 border-red-200 hover:bg-red-50">
                        {actionLoading === b.id + "_cancel" ? <RefreshCw className="h-3 w-3 animate-spin" /> : "Cancel"}
                      </Button>
                    )}
                  </div>
                </div>

                {/* Participants table */}
                {isExpanded && b.participants.length > 0 && (
                  <div className="border-t border-gray-100 px-5 py-4">
                    <p className="text-xs font-semibold text-gray-700 mb-3">Participants</p>
                    <div className="divide-y divide-gray-100">
                      {b.participants.map((p) => (
                        <div key={p.id} className="flex items-center gap-3 py-2.5">
                          <div className="flex-1 min-w-0">
                            <p className="text-sm font-medium text-gray-900">{p.name}</p>
                            {p.email && <p className="text-xs text-muted-foreground">{p.email}</p>}
                          </div>
                          <p className="text-sm font-medium text-gray-900">
                            {p.amount_due.toLocaleString("sv-SE", { minimumFractionDigits: 2 })}
                          </p>
                          {p.paid ? (
                            <span className="inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-medium bg-green-100 text-green-700">
                              Paid
                            </span>
                          ) : (
                            <Button variant="outline" size="sm" disabled={actionLoading === p.id + "_paid"}
                              onClick={() => markPaid(b.id, p.id)}>
                              {actionLoading === p.id + "_paid" ? <RefreshCw className="h-3 w-3 animate-spin" /> : "Mark Paid"}
                            </Button>
                          )}
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            );
          })
        )}
      </div>
    </div>
  );
}
