"use client";
import { useEffect, useRef, useState } from "react";
import { MessageCircle, Send, Users, Hash, Plus, X } from "lucide-react";
import { api } from "@/lib/api-client";

type ConvType = "dm" | "channel";
interface DmThread { type: "dm"; staff_id: string; last_message: string; last_at: string; unread: number; }
interface Channel { type: "channel"; slug: string; name: string; }
interface Msg { id: string; sender_id: string | null; body: string; created_at: string; is_mine: boolean; }
interface StaffMember { id: string; name: string; }

export default function MessagesPage() {
  const [dms, setDms] = useState<DmThread[]>([]);
  const [channels, setChannels] = useState<Channel[]>([]);
  const [active, setActive] = useState<{ type: ConvType; id: string; label: string } | null>(null);
  const [messages, setMessages] = useState<Msg[]>([]);
  const [draft, setDraft] = useState("");
  const [sending, setSending] = useState(false);
  const [allStaff, setAllStaff] = useState<StaffMember[]>([]);
  const [showNewDm, setShowNewDm] = useState(false);
  const [staffSearch, setStaffSearch] = useState("");
  const [unread, setUnread] = useState<{ dm: number; channels: Record<string, number> }>({ dm: 0, channels: {} });
  const bottomRef = useRef<HTMLDivElement>(null);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // Load sidebar on mount
  useEffect(() => {
    loadConversations();
    api.get<{ dm: number; channels: Record<string, number> }>("/api/work/messages/unread").then(setUnread).catch(() => {});
    api.get<{ staff_id: string; name: string }[]>("/api/hr/employees").then((data) =>
      setAllStaff(data.map(e => ({ id: e.staff_id, name: e.name })))
    ).catch(() => {});
  }, []);

  const loadConversations = () =>
    api.get<{ dms: DmThread[]; channels: Channel[] }>("/api/work/messages/conversations")
      .then((c) => {
        setDms(c.dms);
        setChannels(c.channels);
      })
      .catch(() => {});

  // Load thread when active changes
  useEffect(() => {
    if (!active) return;
    loadThread();
    if (pollRef.current) clearInterval(pollRef.current);
    pollRef.current = setInterval(loadThread, 3000);
    return () => { if (pollRef.current) clearInterval(pollRef.current); };
  }, [active?.id]);

  const loadThread = () => {
    if (!active) return;
    const url =
      active.type === "dm"
        ? `/api/work/messages/dm/${active.id}`
        : `/api/work/messages/channel/${active.id}`;
    api.get<Msg[]>(url).then((msgs) => {
      setMessages(msgs);
      // Refresh unread counts after reading
      api.get<{ dm: number; channels: Record<string, number> }>("/api/work/messages/unread").then(setUnread).catch(() => {});
    }).catch(() => {});
  };

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const send = async () => {
    if (!draft.trim() || !active) return;
    setSending(true);
    try {
      if (active.type === "dm") {
        await api.post("/api/work/messages/dm", { recipient_id: active.id, body: draft.trim() });
      } else {
        await api.post("/api/work/messages/channel", { slug: active.id, body: draft.trim() });
      }
      setDraft("");
      loadThread();
      loadConversations();
    } catch { /* quiet */ }
    finally { setSending(false); }
  };

  const openDm = (staffId: string, name: string) => {
    setActive({ type: "dm", id: staffId, label: name });
    setShowNewDm(false);
    setStaffSearch("");
  };

  const openChannel = (slug: string) => {
    setActive({ type: "channel", id: slug, label: `#${slug}` });
  };

  const filteredStaff = allStaff.filter(s =>
    s.name.toLowerCase().includes(staffSearch.toLowerCase())
  );

  const totalUnread = unread.dm + Object.values(unread.channels).reduce((a, b) => a + b, 0);

  return (
    <div className="flex h-[calc(100vh-4rem)] overflow-hidden border rounded bg-white">
      {/* ── Sidebar ─────────────────────────────────────────────────────── */}
      <aside className="w-64 border-r flex flex-col shrink-0">
        <div className="p-3 border-b flex items-center justify-between">
          <div className="flex items-center gap-2 font-semibold text-sm">
            <MessageCircle size={16} />
            Messages
            {totalUnread > 0 && (
              <span className="ml-1 px-1.5 py-0.5 rounded-full bg-[#1a2332] text-white text-xs">{totalUnread}</span>
            )}
          </div>
          <button
            onClick={() => setShowNewDm(s => !s)}
            title="New direct message"
            className="p-1 rounded hover:bg-gray-100"
          >
            <Plus size={15} />
          </button>
        </div>

        {/* New DM people picker */}
        {showNewDm && (
          <div className="border-b p-2 space-y-1">
            <div className="flex items-center gap-1">
              <input
                autoFocus
                className="flex-1 text-xs border rounded px-2 py-1"
                placeholder="Search staff…"
                value={staffSearch}
                onChange={e => setStaffSearch(e.target.value)}
              />
              <button onClick={() => setShowNewDm(false)} className="p-1 rounded hover:bg-gray-100 text-gray-400">
                <X size={13} />
              </button>
            </div>
            <div className="max-h-40 overflow-y-auto space-y-0.5">
              {filteredStaff.slice(0, 8).map(s => (
                <button
                  key={s.id}
                  onClick={() => openDm(s.id, s.name)}
                  className="w-full text-left text-xs px-2 py-1.5 rounded hover:bg-gray-100 flex items-center gap-2"
                >
                  <div className="w-5 h-5 rounded-full bg-[#1a2332] text-white text-[10px] flex items-center justify-center shrink-0">
                    {s.name[0]?.toUpperCase()}
                  </div>
                  {s.name}
                </button>
              ))}
              {filteredStaff.length === 0 && (
                <p className="text-xs text-gray-400 px-2 py-1">No staff found</p>
              )}
            </div>
          </div>
        )}

        <div className="flex-1 overflow-y-auto">
          {/* Channels section */}
          <div className="px-3 pt-3 pb-1">
            <p className="text-[10px] font-semibold text-gray-400 uppercase tracking-wide flex items-center gap-1">
              <Hash size={11} /> Channels
            </p>
          </div>
          {channels.map(ch => (
            <button
              key={ch.slug}
              onClick={() => openChannel(ch.slug)}
              className={`w-full text-left px-3 py-1.5 text-sm flex items-center justify-between hover:bg-gray-50 ${active?.id === ch.slug ? "bg-blue-50 text-blue-700 font-medium" : "text-gray-700"}`}
            >
              <span>{ch.name}</span>
              {(unread.channels[ch.slug] ?? 0) > 0 && (
                <span className="px-1.5 py-0.5 rounded-full bg-[#1a2332] text-white text-[10px]">
                  {unread.channels[ch.slug]}
                </span>
              )}
            </button>
          ))}

          {/* Direct messages section */}
          <div className="px-3 pt-4 pb-1">
            <p className="text-[10px] font-semibold text-gray-400 uppercase tracking-wide flex items-center gap-1">
              <Users size={11} /> Direct Messages
            </p>
          </div>
          {dms.length === 0 && (
            <p className="px-3 text-xs text-gray-400">No conversations yet. Click + to start one.</p>
          )}
          {dms.map(dm => (
            <button
              key={dm.staff_id}
              onClick={() => setActive({ type: "dm", id: dm.staff_id, label: dm.staff_id })}
              className={`w-full text-left px-3 py-2 hover:bg-gray-50 ${active?.id === dm.staff_id ? "bg-blue-50" : ""}`}
            >
              <div className="flex items-center justify-between gap-2">
                <div className="flex items-center gap-2 min-w-0">
                  <div className="w-6 h-6 rounded-full bg-gray-300 text-gray-600 text-[10px] flex items-center justify-center shrink-0">
                    {dm.staff_id.slice(0, 1).toUpperCase()}
                  </div>
                  <span className="text-xs font-medium truncate">
                    {allStaff.find(s => s.id === dm.staff_id)?.name ?? dm.staff_id.slice(0, 8) + "…"}
                  </span>
                </div>
                {dm.unread > 0 && (
                  <span className="px-1.5 py-0.5 rounded-full bg-[#1a2332] text-white text-[10px] shrink-0">{dm.unread}</span>
                )}
              </div>
              <p className="text-xs text-gray-400 truncate mt-0.5 pl-8">{dm.last_message}</p>
            </button>
          ))}
        </div>
      </aside>

      {/* ── Thread panel ────────────────────────────────────────────────── */}
      {active ? (
        <div className="flex-1 flex flex-col min-w-0">
          {/* Header */}
          <div className="border-b px-4 py-3 flex items-center gap-2 shrink-0">
            {active.type === "channel" ? (
              <Hash size={16} className="text-gray-500" />
            ) : (
              <div className="w-6 h-6 rounded-full bg-[#1a2332] text-white text-xs flex items-center justify-center shrink-0">
                {(allStaff.find(s => s.id === active.id)?.name ?? active.label)[0]?.toUpperCase()}
              </div>
            )}
            <span className="font-semibold text-sm">
              {active.type === "channel"
                ? `#${active.id}`
                : allStaff.find(s => s.id === active.id)?.name ?? active.label}
            </span>
          </div>

          {/* Messages */}
          <div className="flex-1 overflow-y-auto px-4 py-4 space-y-3">
            {messages.length === 0 && (
              <div className="flex flex-col items-center justify-center h-full text-gray-400 gap-2">
                <MessageCircle size={32} />
                <p className="text-sm">No messages yet. Say hello!</p>
              </div>
            )}
            {messages.map((m, i) => {
              const showDate =
                i === 0 ||
                new Date(m.created_at).toDateString() !==
                  new Date(messages[i - 1].created_at).toDateString();
              return (
                <div key={m.id}>
                  {showDate && (
                    <div className="flex items-center gap-2 my-3">
                      <div className="flex-1 border-t" />
                      <span className="text-xs text-gray-400">
                        {new Date(m.created_at).toLocaleDateString()}
                      </span>
                      <div className="flex-1 border-t" />
                    </div>
                  )}
                  <div className={`flex gap-2 ${m.is_mine ? "flex-row-reverse" : ""}`}>
                    <div className={`w-7 h-7 rounded-full text-xs flex items-center justify-center shrink-0 font-medium ${m.is_mine ? "bg-[#1a2332] text-white" : "bg-gray-200 text-gray-600"}`}>
                      {m.is_mine
                        ? "Me"
                        : (allStaff.find(s => s.id === m.sender_id)?.name ?? "?")[0]?.toUpperCase()}
                    </div>
                    <div className={`max-w-[70%] ${m.is_mine ? "items-end" : "items-start"} flex flex-col gap-0.5`}>
                      {!m.is_mine && active.type === "channel" && (
                        <span className="text-[10px] text-gray-400 px-1">
                          {allStaff.find(s => s.id === m.sender_id)?.name ?? "Staff"}
                        </span>
                      )}
                      <div className={`px-3 py-2 rounded-2xl text-sm leading-relaxed ${m.is_mine ? "bg-[#1a2332] text-white rounded-tr-sm" : "bg-gray-100 text-gray-900 rounded-tl-sm"}`}>
                        {m.body}
                      </div>
                      <span className="text-[10px] text-gray-400 px-1">
                        {new Date(m.created_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
                      </span>
                    </div>
                  </div>
                </div>
              );
            })}
            <div ref={bottomRef} />
          </div>

          {/* Compose */}
          <div className="border-t px-4 py-3 shrink-0">
            <form
              onSubmit={e => { e.preventDefault(); send(); }}
              className="flex items-end gap-2"
            >
              <textarea
                rows={1}
                value={draft}
                onChange={e => setDraft(e.target.value)}
                onKeyDown={e => {
                  if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(); }
                }}
                placeholder={`Message ${active.type === "channel" ? "#" + active.id : allStaff.find(s => s.id === active.id)?.name ?? "…"}…`}
                className="flex-1 border rounded-xl px-3 py-2 text-sm resize-none focus:outline-none focus:ring-1 focus:ring-[#1a2332]"
              />
              <button
                type="submit"
                disabled={sending || !draft.trim()}
                className="p-2 rounded-xl bg-[#1a2332] text-white hover:opacity-90 disabled:opacity-40 shrink-0"
              >
                <Send size={16} />
              </button>
            </form>
            <p className="text-[10px] text-gray-400 mt-1">Enter to send · Shift+Enter for new line</p>
          </div>
        </div>
      ) : (
        <div className="flex-1 flex items-center justify-center">
          <div className="text-center text-gray-400 space-y-2">
            <MessageCircle size={40} className="mx-auto" />
            <p className="text-sm">Select a conversation or channel</p>
            <p className="text-xs">Or click + to send a direct message to a colleague</p>
          </div>
        </div>
      )}
    </div>
  );
}
