"use client";

import { useEffect, useState } from "react";
import { useRouter, useParams } from "next/navigation";
import { createClient } from "@/lib/supabase/client";
import { PlusCircle, RefreshCw } from "lucide-react";
import { Button } from "@/components/ui/button";
import { toast } from "sonner";

interface Broadcast {
  id: string;
  name: string;
  channel: "sms" | "whatsapp";
  status: "draft" | "scheduled" | "sent" | "failed";
  body_text: string;
  segment_id: string | null;
  scheduled_for: string | null;
  sent_at: string | null;
  recipient_count: number | null;
  delivered_count: number | null;
}

const STATUS_COLOR: Record<string, string> = {
  draft: "bg-gray-100 text-gray-600",
  scheduled: "bg-yellow-100 text-yellow-700",
  sent: "bg-green-100 text-green-700",
  failed: "bg-red-100 text-red-600",
};

const CHANNEL_COLOR: Record<string, string> = {
  sms: "bg-blue-100 text-blue-700",
  whatsapp: "bg-green-100 text-green-700",
};

const SMS_LIMIT = 160;

export default function BroadcastsPage() {
  const router = useRouter();
  const params = useParams<{ locale: string }>();
  const locale = params?.locale ?? "en";
  const supabase = createClient();

  const [broadcasts, setBroadcasts] = useState<Broadcast[]>([]);
  const [loading, setLoading] = useState(true);
  const [channelFilter, setChannelFilter] = useState<"all" | "sms" | "whatsapp">("all");
  const [actionLoading, setActionLoading] = useState<string | null>(null);

  const [showNew, setShowNew] = useState(false);
  const [newForm, setNewForm] = useState({ name: "", channel: "sms" as "sms" | "whatsapp", body_text: "", segment_id: "", scheduled_for: "" });

  const [scheduleModal, setScheduleModal] = useState<{ id: string; scheduled_for: string } | null>(null);

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
      const res = await fetch(apiUrl("/api/broadcasts"), { headers: { Authorization: `Bearer ${token}` } });
      if (res.status === 401) { router.push(`/${locale}/auth/login`); return; }
      if (res.ok) setBroadcasts(await res.json());
    } catch {
      toast.error("Failed to load broadcasts");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { load(); }, []); // eslint-disable-line react-hooks/exhaustive-deps

  async function createBroadcast() {
    if (!newForm.name.trim() || !newForm.body_text.trim()) { toast.error("Name and body are required"); return; }
    setActionLoading("create");
    try {
      const token = await getToken();
      if (!token) return;
      const res = await fetch(apiUrl("/api/broadcasts"), {
        method: "POST",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
        body: JSON.stringify({
          name: newForm.name,
          channel: newForm.channel,
          body_text: newForm.body_text,
          segment_id: newForm.segment_id || null,
          scheduled_for: newForm.scheduled_for || null,
        }),
      });
      if (!res.ok) { const b = await res.json().catch(() => ({})); toast.error(b.detail ?? "Failed to create"); return; }
      toast.success("Broadcast created");
      setShowNew(false);
      setNewForm({ name: "", channel: "sms", body_text: "", segment_id: "", scheduled_for: "" });
      await load();
    } catch { toast.error("Something went wrong"); }
    finally { setActionLoading(null); }
  }

  async function sendNow(id: string) {
    setActionLoading(id + "_send");
    try {
      const token = await getToken();
      if (!token) return;
      const res = await fetch(apiUrl(`/api/broadcasts/${id}/send`), {
        method: "POST",
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) { const b = await res.json().catch(() => ({})); toast.error(b.detail ?? "Failed to send"); return; }
      toast.success("Broadcast sent");
      await load();
    } catch { toast.error("Something went wrong"); }
    finally { setActionLoading(null); }
  }

  async function scheduleBroadcast() {
    if (!scheduleModal?.scheduled_for) { toast.error("Scheduled time is required"); return; }
    setActionLoading(scheduleModal.id + "_schedule");
    try {
      const token = await getToken();
      if (!token) return;
      const res = await fetch(apiUrl(`/api/broadcasts/${scheduleModal.id}/schedule`), {
        method: "POST",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
        body: JSON.stringify({ scheduled_for: scheduleModal.scheduled_for }),
      });
      if (!res.ok) { const b = await res.json().catch(() => ({})); toast.error(b.detail ?? "Failed to schedule"); return; }
      toast.success("Broadcast scheduled");
      setScheduleModal(null);
      await load();
    } catch { toast.error("Something went wrong"); }
    finally { setActionLoading(null); }
  }

  const filtered = channelFilter === "all" ? broadcasts : broadcasts.filter((b) => b.channel === channelFilter);

  return (
    <div className="mx-auto max-w-4xl space-y-6 p-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-gray-900">Broadcasts</h1>
          <p className="text-sm text-muted-foreground mt-0.5">SMS and WhatsApp promotional campaigns to opted-in segments.</p>
        </div>
        <Button onClick={() => setShowNew(true)} className="bg-[#1a2332] hover:bg-[#2a3342] text-white gap-2">
          <PlusCircle className="h-4 w-4" /> New Broadcast
        </Button>
      </div>

      {/* Channel filter tabs */}
      <div className="flex items-center gap-1 border-b">
        {(["all", "sms", "whatsapp"] as const).map((ch) => (
          <button key={ch} type="button" onClick={() => setChannelFilter(ch)}
            className={`px-4 py-2.5 text-sm font-medium border-b-2 transition-colors capitalize ${channelFilter === ch ? "border-[#1a2332] text-[#1a2332]" : "border-transparent text-muted-foreground hover:text-gray-700"}`}>
            {ch}
          </button>
        ))}
      </div>

      {showNew && (
        <div className="rounded-xl border border-[#1a2332]/20 bg-white p-5 shadow-sm space-y-3">
          <h3 className="text-sm font-semibold text-gray-900">Create Broadcast</h3>
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1">
              <label className="text-xs font-medium text-gray-700">Name *</label>
              <input value={newForm.name} onChange={(e) => setNewForm((f) => ({ ...f, name: e.target.value }))}
                placeholder="Black Friday Promo"
                className="block w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-[#1a2332]" />
            </div>
            <div className="space-y-1">
              <label className="text-xs font-medium text-gray-700">Channel</label>
              <select value={newForm.channel} onChange={(e) => setNewForm((f) => ({ ...f, channel: e.target.value as "sms" | "whatsapp" }))}
                className="block w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-[#1a2332]">
                <option value="sms">SMS</option>
                <option value="whatsapp">WhatsApp</option>
              </select>
            </div>
            <div className="space-y-1 col-span-2">
              <div className="flex items-center justify-between">
                <label className="text-xs font-medium text-gray-700">Body Text *</label>
                {newForm.channel === "sms" && (
                  <span className={`text-xs ${newForm.body_text.length > SMS_LIMIT ? "text-red-600" : "text-muted-foreground"}`}>
                    {newForm.body_text.length}/{SMS_LIMIT}
                  </span>
                )}
              </div>
              <textarea rows={3} value={newForm.body_text} onChange={(e) => setNewForm((f) => ({ ...f, body_text: e.target.value }))}
                className="block w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-[#1a2332]" />
            </div>
            <div className="space-y-1">
              <label className="text-xs font-medium text-gray-700">Segment ID (optional)</label>
              <input value={newForm.segment_id} onChange={(e) => setNewForm((f) => ({ ...f, segment_id: e.target.value }))}
                placeholder="UUID"
                className="block w-full rounded-md border border-gray-300 px-3 py-2 text-sm font-mono focus:outline-none focus:ring-1 focus:ring-[#1a2332]" />
            </div>
            <div className="space-y-1">
              <label className="text-xs font-medium text-gray-700">Schedule For (optional)</label>
              <input type="datetime-local" value={newForm.scheduled_for} onChange={(e) => setNewForm((f) => ({ ...f, scheduled_for: e.target.value }))}
                className="block w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-[#1a2332]" />
            </div>
          </div>
          <div className="flex gap-2">
            <Button variant="outline" onClick={() => setShowNew(false)}>Cancel</Button>
            <Button disabled={actionLoading === "create"} onClick={createBroadcast}
              className="bg-[#1a2332] hover:bg-[#2a3342] text-white">
              {actionLoading === "create" ? "Creating…" : "Create Broadcast"}
            </Button>
          </div>
        </div>
      )}

      {loading && broadcasts.length === 0 ? (
        <div className="text-center py-12"><RefreshCw className="h-6 w-6 animate-spin mx-auto text-muted-foreground" /></div>
      ) : (
        <div className="rounded-xl border bg-white shadow-sm divide-y divide-gray-100">
          {filtered.length === 0 ? (
            <div className="py-12 text-center text-sm text-gray-500">No broadcasts yet</div>
          ) : filtered.map((b) => (
            <div key={b.id} className="flex items-center gap-4 px-5 py-4">
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium text-gray-900">{b.name}</p>
                <p className="text-xs text-muted-foreground">
                  {b.scheduled_for && `Scheduled: ${new Date(b.scheduled_for).toLocaleString()}`}
                  {b.sent_at && `Sent: ${new Date(b.sent_at).toLocaleString()}`}
                  {(b.recipient_count != null || b.delivered_count != null) && ` · ${b.delivered_count ?? 0}/${b.recipient_count ?? 0} delivered`}
                </p>
              </div>
              <span className={`rounded-full px-2.5 py-0.5 text-xs font-medium ${CHANNEL_COLOR[b.channel] ?? "bg-gray-100 text-gray-600"}`}>
                {b.channel}
              </span>
              <span className={`rounded-full px-2.5 py-0.5 text-xs font-medium ${STATUS_COLOR[b.status] ?? STATUS_COLOR.draft}`}>
                {b.status}
              </span>
              <div className="flex items-center gap-2">
                {(b.status === "draft" || b.status === "scheduled") && (
                  <>
                    <Button size="sm" variant="outline"
                      onClick={() => setScheduleModal({ id: b.id, scheduled_for: b.scheduled_for ?? "" })}>
                      Schedule
                    </Button>
                    <Button size="sm" disabled={actionLoading === b.id + "_send"}
                      onClick={() => sendNow(b.id)}
                      className="bg-[#1a2332] hover:bg-[#2a3342] text-white">
                      {actionLoading === b.id + "_send" ? "Sending…" : "Send Now"}
                    </Button>
                  </>
                )}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Schedule modal */}
      {scheduleModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
          <div className="w-full max-w-sm rounded-xl bg-white p-6 shadow-xl space-y-4">
            <h3 className="text-base font-semibold text-gray-900">Schedule Broadcast</h3>
            <div className="space-y-1">
              <label className="text-xs font-medium text-gray-700">Send At</label>
              <input type="datetime-local" value={scheduleModal.scheduled_for}
                onChange={(e) => setScheduleModal((m) => m ? { ...m, scheduled_for: e.target.value } : null)}
                className="block w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-[#1a2332]" />
            </div>
            <div className="flex gap-2 justify-end">
              <Button variant="outline" onClick={() => setScheduleModal(null)}>Cancel</Button>
              <Button disabled={actionLoading?.endsWith("_schedule")} onClick={scheduleBroadcast}
                className="bg-[#1a2332] hover:bg-[#2a3342] text-white">
                {actionLoading?.endsWith("_schedule") ? "Scheduling…" : "Schedule"}
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
