"use client";
import { useEffect, useState } from "react";
import { api } from "@/lib/api-client";

interface Ticket {
  id: string;
  customer_id: string;
  subject: string;
  status: string;
  priority: string;
  ticket_type: string | null;
  sla_hours: number | null;
  sla_overdue: boolean;
  resolved_at: string | null;
  csat_token: string | null;
  assigned_staff_id: string | null;
  created_at: string;
  replies?: Reply[];
}

interface Reply {
  id: string;
  sender_type: string;
  body: string;
  is_internal: boolean;
  created_at: string;
}

const PRIORITY_COLORS: Record<string, string> = {
  low: "bg-gray-100 text-gray-600",
  normal: "bg-blue-100 text-blue-700",
  high: "bg-orange-100 text-orange-700",
  urgent: "bg-red-100 text-red-700",
};

const STATUS_COLORS: Record<string, string> = {
  open: "bg-yellow-100 text-yellow-800",
  in_progress: "bg-blue-100 text-blue-800",
  resolved: "bg-green-100 text-green-700",
  closed: "bg-gray-100 text-gray-600",
};

export default function PortalAdminTicketsPage() {
  const [tickets, setTickets] = useState<Ticket[]>([]);
  const [filter, setFilter] = useState("");
  const [selected, setSelected] = useState<Ticket | null>(null);
  const [replyBody, setReplyBody] = useState("");
  const [isInternal, setIsInternal] = useState(false);
  const [loading, setLoading] = useState(false);

  const load = () => {
    const qs = filter ? `?status=${filter}` : "";
    api.get<Ticket[]>(`/api/portal-admin/tickets${qs}`)
      .then(setTickets)
      .catch(() => {});
  };

  const loadDetail = (id: string) => {
    api.get<Ticket>(`/api/portal-admin/tickets/${id}`)
      .then(setSelected)
      .catch(() => {});
  };

  useEffect(() => { load(); }, [filter]);

  const update = async (id: string, patch: Record<string, unknown>) => {
    await api.patch(`/api/portal-admin/tickets/${id}`, patch);
    load();
    if (selected?.id === id) loadDetail(id);
  };

  const sendReply = async () => {
    if (!replyBody.trim() || !selected) return;
    setLoading(true);
    try {
      await api.post(`/api/portal-admin/tickets/${selected.id}/reply`, { body: replyBody, is_internal: isInternal });
      setReplyBody("");
      setIsInternal(false);
      loadDetail(selected.id);
    } finally {
      setLoading(false);
    }
  };

  const badge = (text: string, cls: string) => (
    <span className={`px-2 py-0.5 rounded text-xs font-medium ${cls}`}>{text}</span>
  );

  const hoursOpen = (created: string) => {
    const h = (Date.now() - new Date(created).getTime()) / 3600000;
    if (h < 1) return `${Math.round(h * 60)}m`;
    if (h < 24) return `${Math.round(h)}h`;
    return `${Math.round(h / 24)}d`;
  };

  return (
    <div className="flex h-screen overflow-hidden bg-gray-50">
      {/* Sidebar */}
      <div className="w-80 border-r bg-white flex flex-col">
        <div className="p-4 border-b">
          <h1 className="text-lg font-bold text-gray-900">Support Inbox</h1>
          <div className="flex gap-1 mt-2 flex-wrap">
            {["", "open", "in_progress", "resolved", "closed"].map(s => (
              <button
                key={s}
                onClick={() => setFilter(s)}
                className={`px-2.5 py-1 rounded text-xs font-medium ${filter === s ? "bg-indigo-600 text-white" : "bg-gray-100 text-gray-600 hover:bg-gray-200"}`}
              >
                {s || "All"}
              </button>
            ))}
          </div>
        </div>
        <div className="flex-1 overflow-y-auto divide-y">
          {tickets.map(t => (
            <button
              key={t.id}
              onClick={() => loadDetail(t.id)}
              className={`w-full text-left px-4 py-3 hover:bg-gray-50 transition-colors ${selected?.id === t.id ? "bg-indigo-50" : ""} ${t.sla_overdue ? "border-l-4 border-red-400" : ""}`}
            >
              <div className="flex items-center justify-between gap-1">
                <span className="text-sm font-medium text-gray-900 truncate">{t.subject}</span>
                {badge(t.status, STATUS_COLORS[t.status] ?? "bg-gray-100 text-gray-600")}
              </div>
              <div className="flex items-center gap-2 mt-1">
                {badge(t.priority, PRIORITY_COLORS[t.priority] ?? "bg-gray-100")}
                {t.ticket_type && <span className="text-xs text-gray-400">{t.ticket_type}</span>}
                {t.sla_overdue && <span className="text-xs text-red-600 font-medium">SLA overdue</span>}
                <span className="text-xs text-gray-400 ml-auto">{hoursOpen(t.created_at)}</span>
              </div>
            </button>
          ))}
          {tickets.length === 0 && <p className="p-4 text-sm text-gray-400">No tickets.</p>}
        </div>
      </div>

      {/* Thread view */}
      <div className="flex-1 flex flex-col overflow-hidden">
        {!selected ? (
          <div className="flex-1 flex items-center justify-center text-gray-400 text-sm">
            Select a ticket to view the thread
          </div>
        ) : (
          <>
            {/* Thread header */}
            <div className="px-6 py-4 border-b bg-white flex items-center justify-between">
              <div>
                <h2 className="font-bold text-gray-900">{selected.subject}</h2>
                <div className="flex items-center gap-2 mt-1">
                  {badge(selected.status, STATUS_COLORS[selected.status] ?? "bg-gray-100")}
                  {badge(selected.priority, PRIORITY_COLORS[selected.priority] ?? "bg-gray-100")}
                  {selected.sla_hours && (
                    <span className={`text-xs ${selected.sla_overdue ? "text-red-600 font-semibold" : "text-gray-500"}`}>
                      SLA {selected.sla_hours}h{selected.sla_overdue ? " — OVERDUE" : ""}
                    </span>
                  )}
                  {selected.ticket_type && <span className="text-xs text-gray-400">Type: {selected.ticket_type}</span>}
                </div>
              </div>
              <div className="flex items-center gap-2">
                {selected.status === "open" && (
                  <button onClick={() => update(selected.id, { status: "in_progress" })} className="text-xs px-3 py-1.5 bg-blue-600 text-white rounded hover:bg-blue-700">Start</button>
                )}
                {selected.status === "in_progress" && (
                  <button onClick={() => update(selected.id, { status: "resolved" })} className="text-xs px-3 py-1.5 bg-green-600 text-white rounded hover:bg-green-700">Resolve</button>
                )}
                {selected.status === "resolved" && (
                  <button onClick={() => update(selected.id, { status: "closed" })} className="text-xs px-3 py-1.5 bg-gray-600 text-white rounded hover:bg-gray-700">Close</button>
                )}
              </div>
            </div>

            {/* CSAT alert */}
            {selected.csat_token && selected.status === "resolved" && (
              <div className="mx-6 mt-4 p-3 bg-green-50 border border-green-200 rounded-lg text-sm text-green-700 flex items-center justify-between">
                <span>CSAT survey token generated — share with customer for feedback.</span>
                <code className="text-xs bg-white px-2 py-0.5 rounded border">{selected.csat_token.slice(0, 12)}…</code>
              </div>
            )}

            {/* Replies */}
            <div className="flex-1 overflow-y-auto px-6 py-4 space-y-3">
              {(selected.replies ?? []).map(r => (
                <div
                  key={r.id}
                  className={`rounded-xl p-3 text-sm max-w-xl ${
                    r.is_internal
                      ? "bg-yellow-50 border border-yellow-200 ml-8"
                      : r.sender_type === "customer"
                      ? "bg-white border"
                      : "bg-indigo-50 border border-indigo-100 ml-8"
                  }`}
                >
                  <div className="flex items-center gap-2 mb-1">
                    <span className="font-semibold text-xs text-gray-600">
                      {r.is_internal ? "🔒 Internal note" : r.sender_type === "customer" ? "Customer" : "Staff"}
                    </span>
                    <span className="text-xs text-gray-400">{new Date(r.created_at).toLocaleString()}</span>
                  </div>
                  <p className="text-gray-800 whitespace-pre-wrap">{r.body}</p>
                </div>
              ))}
              {(selected.replies ?? []).length === 0 && (
                <p className="text-sm text-gray-400">No replies yet.</p>
              )}
            </div>

            {/* Reply form */}
            {selected.status !== "closed" && (
              <div className="px-6 py-4 border-t bg-white space-y-2">
                <div className="flex items-center gap-3">
                  <label className="flex items-center gap-1.5 text-sm text-gray-600 cursor-pointer select-none">
                    <input
                      type="checkbox"
                      checked={isInternal}
                      onChange={e => setIsInternal(e.target.checked)}
                      className="rounded"
                    />
                    Internal note (not visible to customer)
                  </label>
                </div>
                <div className="flex gap-2">
                  <textarea
                    value={replyBody}
                    onChange={e => setReplyBody(e.target.value)}
                    placeholder={isInternal ? "Add internal note…" : "Reply to customer…"}
                    className={`flex-1 border rounded-lg px-3 py-2 text-sm resize-none h-16 focus:outline-none focus:ring-2 ${isInternal ? "focus:ring-yellow-300 bg-yellow-50" : "focus:ring-indigo-300"}`}
                  />
                  <button
                    onClick={sendReply}
                    disabled={loading || !replyBody.trim()}
                    className={`px-4 rounded-lg text-sm font-medium text-white disabled:opacity-50 ${isInternal ? "bg-yellow-500 hover:bg-yellow-600" : "bg-indigo-600 hover:bg-indigo-700"}`}
                  >
                    {loading ? "…" : isInternal ? "Note" : "Reply"}
                  </button>
                </div>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}
