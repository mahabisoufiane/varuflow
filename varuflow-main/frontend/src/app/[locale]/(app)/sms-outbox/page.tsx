"use client";
import { useEffect, useState } from "react";
import { api } from "@/lib/api-client";
import { toast } from "sonner";
import styles from "./page.module.scss";
import { MessageSquare, Plus, Phone, Send, CheckCheck, Clock, XCircle, AlertTriangle, Ban, ChevronRight, Filter } from "lucide-react";

interface SmsMsg {
  id: string;
  customer_id: string | null;
  to_number: string;
  from_number: string | null;
  body: string;
  channel: "sms" | "whatsapp";
  direction: "in" | "out";
  status: string;
  delivered_at: string | null;
  read_at: string | null;
  cost_credits: number | null;
  sent_at: string;
  created_at: string;
}

interface OptOut {
  id: string;
  phone_number: string;
  channel: string;
  opted_out_at: string;
}

const STATUS_ICON: Record<string, React.ReactNode> = {
  queued:       <Clock size={12} className="text-gray-400" />,
  sent:         <CheckCheck size={12} className="text-blue-400" />,
  delivered:    <CheckCheck size={12} className="text-green-500" />,
  read:         <CheckCheck size={12} className="text-green-600" />,
  failed:       <XCircle size={12} className="text-red-500" />,
  undelivered:  <AlertTriangle size={12} className="text-amber-500" />,
};

const STATUS_LABEL: Record<string, string> = {
  queued: "Queued", sent: "Sent", delivered: "Delivered",
  read: "Read", failed: "Failed", undelivered: "Undelivered",
};

export default function SmsOutboxPage() {
  const [messages, setMessages] = useState<SmsMsg[]>([]);
  const [optOuts, setOptOuts] = useState<OptOut[]>([]);
  const [tab, setTab] = useState<"outbox" | "conversation" | "opt-outs">("outbox");
  const [selected, setSelected] = useState<SmsMsg | null>(null);
  const [thread, setThread] = useState<SmsMsg[]>([]);
  const [filterChannel, setFilterChannel] = useState("");
  const [filterStatus, setFilterStatus] = useState("");
  const [loading, setLoading] = useState(true);
  const [showCompose, setShowCompose] = useState(false);

  // Compose form
  const [compose, setCompose] = useState({
    to_number: "", body: "", channel: "sms", from_number: ""
  });
  // Opt-out form
  const [optOutForm, setOptOutForm] = useState({ phone_number: "", channel: "sms" });

  useEffect(() => { loadMessages(); }, [filterChannel, filterStatus]);
  useEffect(() => { if (tab === "opt-outs") loadOptOuts(); }, [tab]);

  async function loadMessages() {
    setLoading(true);
    try {
      const params = new URLSearchParams();
      if (filterChannel) params.set("channel", filterChannel);
      if (filterStatus) params.set("status", filterStatus);
      params.set("limit", "100");
      const data = await api.get(`/api/sms-outbox?${params.toString()}`);
      setMessages(Array.isArray(data) ? data : []);
    } catch { toast.error("Failed to load messages"); }
    finally { setLoading(false); }
  }

  async function loadOptOuts() {
    try {
      const data = await api.get("/api/sms-outbox/opt-outs");
      setOptOuts(Array.isArray(data) ? data : []);
    } catch { toast.error("Failed to load opt-outs"); }
  }

  async function openConversation(msg: SmsMsg) {
    setSelected(msg);
    setTab("conversation");
    try {
      const number = msg.direction === "out" ? msg.to_number : (msg.from_number || msg.to_number);
      const data = await api.get(`/api/sms-outbox/conversation/${encodeURIComponent(number)}?channel=${msg.channel}`);
      setThread(Array.isArray(data) ? data : []);
    } catch { toast.error("Failed to load conversation"); }
  }

  async function send() {
    if (!compose.to_number || !compose.body) { toast.error("Phone number and body required"); return; }
    try {
      const msg = await api.post("/api/sms-outbox", {
        to_number: compose.to_number,
        body: compose.body,
        channel: compose.channel,
        from_number: compose.from_number || undefined,
      });
      setMessages(prev => [msg, ...prev]);
      setShowCompose(false);
      setCompose({ to_number: "", body: "", channel: "sms", from_number: "" });
      toast.success("Message queued");
    } catch (e: any) {
      toast.error(e?.message ?? "Failed to send");
    }
  }

  async function replyInThread() {
    if (!selected || !compose.body) return;
    const number = selected.direction === "out" ? selected.to_number : (selected.from_number || selected.to_number);
    try {
      const msg = await api.post("/api/sms-outbox", {
        to_number: number,
        body: compose.body,
        channel: selected.channel,
      });
      setThread(prev => [...prev, msg]);
      setMessages(prev => [msg, ...prev]);
      setCompose(p => ({ ...p, body: "" }));
      toast.success("Message queued");
    } catch { toast.error("Failed to send"); }
  }

  async function addOptOut() {
    if (!optOutForm.phone_number) { toast.error("Phone number required"); return; }
    try {
      const r = await api.post("/api/sms-outbox/opt-outs", optOutForm);
      setOptOuts(prev => [r, ...prev]);
      setOptOutForm({ phone_number: "", channel: "sms" });
      toast.success("Opt-out recorded");
    } catch { toast.error("Failed to record opt-out"); }
  }

  async function removeOptOut(id: string) {
    if (!confirm("Remove this opt-out? The number will be able to receive messages again.")) return;
    try {
      await api.delete(`/api/sms-outbox/opt-outs/${id}`);
      setOptOuts(prev => prev.filter(o => o.id !== id));
      toast.success("Opt-out removed");
    } catch { toast.error("Failed to remove opt-out"); }
  }

  // Cost summary
  const totalCost = messages.reduce((s, m) => s + (m.cost_credits ?? 0), 0);
  const deliveredCount = messages.filter(m => m.status === "delivered" || m.status === "read").length;
  const failedCount = messages.filter(m => m.status === "failed" || m.status === "undelivered").length;

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold flex items-center gap-2"><MessageSquare size={22} /> SMS / WhatsApp Outbox</h1>
          <p className="text-sm text-gray-500 mt-0.5">Outbound log, delivery status, opt-out management</p>
        </div>
        <button onClick={() => setShowCompose(true)} className="btn-primary flex items-center gap-2">
          <Plus size={16} /> New message
        </button>
      </div>

      {/* Summary cards */}
      <div className="grid grid-cols-4 gap-4">
        {[
          { label: "Total sent", value: messages.filter(m => m.direction === "out").length, icon: <Send size={18} />, color: "text-blue-600" },
          { label: "Delivered", value: deliveredCount, icon: <CheckCheck size={18} />, color: "text-green-600" },
          { label: "Failed", value: failedCount, icon: <XCircle size={18} />, color: "text-red-600" },
          { label: "Cost credits", value: totalCost.toFixed(2), icon: <Phone size={18} />, color: "text-gray-600" },
        ].map(c => (
          <div key={c.label} className="bg-white border rounded-lg p-4">
            <div className={`${c.color} mb-1`}>{c.icon}</div>
            <p className="text-lg font-bold">{c.value}</p>
            <p className="text-xs text-gray-500">{c.label}</p>
          </div>
        ))}
      </div>

      {/* Tab bar */}
      <div className="flex gap-1 border-b">
        {(["outbox", "conversation", "opt-outs"] as const).map(t => (
          <button key={t} onClick={() => setTab(t)}
            className={`px-4 py-2 text-sm font-medium capitalize ${tab === t ? "border-b-2 border-[var(--vf-brand-primary)] text-[var(--vf-text-primary)]" : "text-gray-500"}`}>
            {t === "opt-outs" ? `Opt-outs (${optOuts.length})` : t.charAt(0).toUpperCase() + t.slice(1)}
          </button>
        ))}
      </div>

      {/* ── Outbox tab ───────────────────────────────────────────────── */}
      {tab === "outbox" && (
        <div className="bg-white border rounded-lg overflow-hidden">
          {/* Filters */}
          <div className="flex gap-3 p-3 border-b bg-gray-50">
            <select value={filterChannel} onChange={e => setFilterChannel(e.target.value)}
              className="text-xs border rounded px-2 py-1">
              <option value="">All channels</option>
              <option value="sms">SMS</option>
              <option value="whatsapp">WhatsApp</option>
            </select>
            <select value={filterStatus} onChange={e => setFilterStatus(e.target.value)}
              className="text-xs border rounded px-2 py-1">
              <option value="">All statuses</option>
              {Object.keys(STATUS_LABEL).map(s => <option key={s} value={s}>{STATUS_LABEL[s]}</option>)}
            </select>
          </div>

          {loading ? (
            <p className="p-4 text-sm text-gray-400">Loading…</p>
          ) : messages.length === 0 ? (
            <div className="p-8 text-center text-gray-400">
              <MessageSquare size={32} className="mx-auto mb-2 opacity-30" />
              <p className="text-sm">No messages yet.</p>
            </div>
          ) : (
            <table className="w-full text-xs">
              <thead className="bg-gray-50 border-b">
                <tr>
                  {["Channel", "To", "Body", "Direction", "Status", "Sent", ""].map(h => (
                    <th key={h} className="px-3 py-2 text-left font-semibold text-gray-500">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {messages.map(m => (
                  <tr key={m.id} className="border-b hover:bg-gray-50">
                    <td className="px-3 py-2">
                      <span className={styles[m.channel === "whatsapp" ? "channelWhatsapp" : "channelSms"]}>
                        {m.channel === "whatsapp" ? "WA" : "SMS"}
                      </span>
                    </td>
                    <td className="px-3 py-2 font-mono">{m.to_number}</td>
                    <td className="px-3 py-2 max-w-xs truncate text-gray-700">{m.body}</td>
                    <td className="px-3 py-2">
                      <span className={`px-1.5 py-0.5 rounded text-[10px] ${m.direction === "in" ? "bg-purple-100 text-purple-700" : "bg-gray-100 text-gray-600"}`}>
                        {m.direction === "in" ? "Inbound" : "Outbound"}
                      </span>
                    </td>
                    <td className="px-3 py-2">
                      <div className="flex items-center gap-1">
                        {STATUS_ICON[m.status] ?? <Clock size={12} />}
                        <span>{STATUS_LABEL[m.status] ?? m.status}</span>
                      </div>
                    </td>
                    <td className="px-3 py-2 text-gray-400">{new Date(m.sent_at).toLocaleDateString()}</td>
                    <td className="px-3 py-2">
                      <button onClick={() => openConversation(m)} className="p-1 rounded hover:bg-gray-100">
                        <ChevronRight size={14} />
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}

      {/* ── Conversation tab ─────────────────────────────────────────── */}
      {tab === "conversation" && (
        <div className="bg-white border rounded-lg flex flex-col" style={{ height: "calc(100vh - 22rem)" }}>
          {selected ? (
            <>
              <div className="border-b p-3 flex items-center gap-2">
                <Phone size={15} className="text-gray-500" />
                <span className="font-semibold text-sm">
                  {selected.direction === "out" ? selected.to_number : (selected.from_number || selected.to_number)}
                </span>
                <span className={`ml-2 ${styles[selected.channel === "whatsapp" ? "channelWhatsapp" : "channelSms"]}`}>
                  {selected.channel}
                </span>
              </div>

              <div className="flex-1 overflow-y-auto px-4 py-3 space-y-3">
                {thread.map(m => (
                  <div key={m.id} className={`flex ${m.direction === "out" ? "justify-end" : "justify-start"}`}>
                    <div className={`max-w-[70%] space-y-0.5 ${m.direction === "out" ? "items-end" : "items-start"} flex flex-col`}>
                      <div className={`px-3 py-2 rounded-2xl text-sm ${m.direction === "out" ? "bg-[var(--vf-brand-primary)] text-white rounded-tr-sm" : "bg-gray-100 text-gray-900 rounded-tl-sm"}`}>
                        {m.body}
                      </div>
                      <div className="flex items-center gap-1 text-[10px] text-gray-400 px-1">
                        <span>{new Date(m.sent_at).toLocaleString([], { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" })}</span>
                        {m.direction === "out" && STATUS_ICON[m.status]}
                      </div>
                    </div>
                  </div>
                ))}
              </div>

              <div className="border-t p-3 flex gap-2">
                <input value={compose.body} onChange={e => setCompose(p => ({ ...p, body: e.target.value }))}
                  onKeyDown={e => e.key === "Enter" && replyInThread()}
                  placeholder="Type a reply…" className="flex-1 border rounded-xl px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-[var(--vf-brand-primary)]" />
                <button onClick={replyInThread} disabled={!compose.body.trim()}
                  className="p-2 rounded-xl bg-[var(--vf-brand-primary)] text-white hover:opacity-90 disabled:opacity-40">
                  <Send size={16} />
                </button>
              </div>
            </>
          ) : (
            <div className="flex-1 flex items-center justify-center text-gray-400">
              <div className="text-center space-y-2">
                <MessageSquare size={32} className="mx-auto opacity-30" />
                <p className="text-sm">Select a message from the Outbox tab to view its conversation</p>
              </div>
            </div>
          )}
        </div>
      )}

      {/* ── Opt-outs tab ─────────────────────────────────────────────── */}
      {tab === "opt-outs" && (
        <div className="space-y-4">
          {/* Add opt-out */}
          <div className="bg-white border rounded-lg p-4 flex gap-3 items-end">
            <div className="flex-1">
              <label className="block text-xs font-medium mb-1">Phone number</label>
              <input value={optOutForm.phone_number} onChange={e => setOptOutForm(p => ({ ...p, phone_number: e.target.value }))}
                className="input w-full" placeholder="+46701234567" />
            </div>
            <div>
              <label className="block text-xs font-medium mb-1">Channel</label>
              <select value={optOutForm.channel} onChange={e => setOptOutForm(p => ({ ...p, channel: e.target.value }))} className="input">
                <option value="sms">SMS</option>
                <option value="whatsapp">WhatsApp</option>
              </select>
            </div>
            <button onClick={addOptOut} className="btn-primary flex items-center gap-2">
              <Ban size={14} /> Add opt-out
            </button>
          </div>

          <div className="bg-white border rounded-lg overflow-hidden">
            {optOuts.length === 0 ? (
              <p className="p-6 text-center text-sm text-gray-400">No opt-outs recorded.</p>
            ) : (
              <table className="w-full text-xs">
                <thead className="bg-gray-50 border-b">
                  <tr>
                    {["Phone number", "Channel", "Opted out", ""].map(h => (
                      <th key={h} className="px-4 py-2 text-left font-semibold text-gray-500">{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {optOuts.map(o => (
                    <tr key={o.id} className="border-b hover:bg-gray-50">
                      <td className="px-4 py-2 font-mono">{o.phone_number}</td>
                      <td className="px-4 py-2">
                        <span className={styles[o.channel === "whatsapp" ? "channelWhatsapp" : "channelSms"]}>
                          {o.channel}
                        </span>
                      </td>
                      <td className="px-4 py-2 text-gray-500">{new Date(o.opted_out_at).toLocaleDateString()}</td>
                      <td className="px-4 py-2">
                        <button onClick={() => removeOptOut(o.id)} className="text-red-500 hover:text-red-700 text-xs">
                          Remove
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        </div>
      )}

      {/* ── Compose modal ────────────────────────────────────────────── */}
      {showCompose && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50">
          <div className="bg-white rounded-xl shadow-xl w-full max-w-md p-6 space-y-3">
            <h3 className="font-semibold">New Message</h3>
            <div>
              <label className="block text-xs font-medium mb-1">Channel</label>
              <select value={compose.channel} onChange={e => setCompose(p => ({ ...p, channel: e.target.value }))} className="input w-full">
                <option value="sms">SMS</option>
                <option value="whatsapp">WhatsApp</option>
              </select>
            </div>
            <div>
              <label className="block text-xs font-medium mb-1">To (phone number)</label>
              <input value={compose.to_number} onChange={e => setCompose(p => ({ ...p, to_number: e.target.value }))}
                className="input w-full" placeholder="+46701234567" />
            </div>
            <div>
              <label className="block text-xs font-medium mb-1">From number <span className="text-gray-400">(optional)</span></label>
              <input value={compose.from_number} onChange={e => setCompose(p => ({ ...p, from_number: e.target.value }))}
                className="input w-full" placeholder="Your Twilio number" />
            </div>
            <div>
              <label className="block text-xs font-medium mb-1">Message</label>
              <textarea value={compose.body} onChange={e => setCompose(p => ({ ...p, body: e.target.value }))}
                rows={4} className="input w-full" placeholder="Write your message…" />
            </div>
            <div className="flex gap-2 justify-end">
              <button onClick={() => setShowCompose(false)} className="btn-secondary">Cancel</button>
              <button onClick={send} className="btn-primary flex items-center gap-2"><Send size={14} /> Queue message</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
