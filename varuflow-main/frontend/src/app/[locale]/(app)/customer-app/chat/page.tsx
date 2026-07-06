"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api-client";
import {
  PlusCircle, MessageCircle, RefreshCw, Send, CheckCheck,
  ChevronDown, ChevronUp, Paperclip, X,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { toast } from "sonner";
import styles from "./page.module.scss";

interface ChatMessage {
  id: string;
  sender_type: "customer" | "staff";
  body: string;
  is_read: boolean;
  attachment_url: string | null;
  created_at: string;
}

interface ChatThread {
  id: string;
  customer_id: string;
  subject: string | null;
  status: "open" | "resolved" | "closed";
  last_message_at: string | null;
  unread_staff_count: number;
  created_at: string;
}

type StatusFilter = "open" | "resolved" | "closed" | "all";

const STATUS_TABS: { value: StatusFilter; label: string }[] = [
  { value: "open", label: "Open" },
  { value: "resolved", label: "Resolved" },
  { value: "closed", label: "Closed" },
  { value: "all", label: "All" },
];

const STATUS_BADGE: Record<string, string> = {
  open:     "bg-green-100 text-green-700",
  resolved: "bg-blue-100 text-blue-700",
  closed:   "bg-gray-100 text-gray-500",
};

const STATUS_MODULE: Record<string, keyof typeof styles> = {
  open:     "statusOpen",
  resolved: "statusResolved",
  closed:   "statusClosed",
};

function relativeTime(iso: string | null): string {
  if (!iso) return "";
  const diff = Date.now() - new Date(iso).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  return `${Math.floor(hrs / 24)}d ago`;
}

function truncate(str: string, n: number) {
  return str.length > n ? str.slice(0, n) + "…" : str;
}

export default function CustomerChatPage() {
  const [threads, setThreads] = useState<ChatThread[]>([]);
  const [loading, setLoading] = useState(true);
  const [statusFilter, setStatusFilter] = useState<StatusFilter>("open");
  const [unreadCount, setUnreadCount] = useState(0);
  const [expandedThreadId, setExpandedThreadId] = useState<string | null>(null);
  const [messages, setMessages] = useState<Record<string, ChatMessage[]>>({});
  const [newMsg, setNewMsg] = useState("");
  const [sendingMsg, setSendingMsg] = useState(false);
  const [showAttachment, setShowAttachment] = useState(false);
  const [attachmentUrl, setAttachmentUrl] = useState("");
  const [actionLoading, setActionLoading] = useState<string | null>(null);

  // New thread form
  const [showNew, setShowNew] = useState(false);
  const [newThreadForm, setNewThreadForm] = useState({ customer_id: "", subject: "" });

  async function load() {
    setLoading(true);
    try {
      const query = statusFilter === "all" ? "" : `?status=${statusFilter}`;
      const [threadsData, unreadData] = await Promise.all([
        api.get<ChatThread[]>(`/api/chat/threads${query}`),
        api.get<{ count: number }>("/api/chat/unread-count"),
      ]);
      setThreads(threadsData);
      setUnreadCount(unreadData.count ?? 0);
    } catch {
      toast.error("Failed to load chat threads");
    } finally {
      setLoading(false);
    }
  }

  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(() => { load(); }, [statusFilter]);

  async function loadThread(id: string) {
    try {
      const data = await api.get<{ messages: ChatMessage[] }>(`/api/chat/threads/${id}`);
      setMessages((prev) => ({ ...prev, [id]: data.messages ?? [] }));
    } catch {
      toast.error("Failed to load messages");
    }
  }

  function toggleThread(id: string) {
    if (expandedThreadId === id) {
      setExpandedThreadId(null);
    } else {
      setExpandedThreadId(id);
      if (!messages[id]) loadThread(id);
    }
  }

  async function sendMessage(threadId: string) {
    if (!newMsg.trim()) return;
    setSendingMsg(true);
    try {
      await api.post(`/api/chat/threads/${threadId}/messages`, {
        sender_type: "staff",
        body: newMsg,
        attachment_url: attachmentUrl || null,
      });
      toast.success("Message sent");
      setNewMsg("");
      setAttachmentUrl("");
      setShowAttachment(false);
      await loadThread(threadId);
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Something went wrong");
    } finally {
      setSendingMsg(false);
    }
  }

  async function markRead(messageId: string, threadId: string) {
    try {
      await api.patch(`/api/chat/messages/${messageId}/read`, {});
      setMessages((prev) => ({
        ...prev,
        [threadId]: (prev[threadId] ?? []).map((m) =>
          m.id === messageId ? { ...m, is_read: true } : m
        ),
      }));
    } catch {
      toast.error("Failed to mark as read");
    }
  }

  async function updateThreadStatus(threadId: string, status: "resolved" | "closed") {
    setActionLoading(threadId + "_" + status);
    try {
      await api.patch(`/api/chat/threads/${threadId}`, { status });
      toast.success(`Thread marked as ${status}`);
      await load();
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Something went wrong");
    } finally {
      setActionLoading(null);
    }
  }

  async function createThread() {
    if (!newThreadForm.customer_id.trim()) { toast.error("Customer ID is required"); return; }
    setActionLoading("create_thread");
    try {
      await api.post("/api/chat/threads", {
        customer_id: newThreadForm.customer_id,
        subject: newThreadForm.subject || null,
      });
      toast.success("Thread created");
      setShowNew(false);
      setNewThreadForm({ customer_id: "", subject: "" });
      await load();
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Something went wrong");
    } finally {
      setActionLoading(null);
    }
  }

  return (
    <div className="mx-auto max-w-4xl space-y-6 p-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div>
            <h1 className="text-xl font-semibold text-gray-900">Customer Chat</h1>
            <p className="text-sm text-muted-foreground mt-0.5">
              Manage inbound conversations from customers.
            </p>
          </div>
          {unreadCount > 0 && (
            <span className="inline-flex h-6 min-w-6 items-center justify-center rounded-full bg-red-500 text-white text-xs font-semibold px-1.5">
              {unreadCount}
            </span>
          )}
        </div>
        <Button onClick={() => setShowNew(true)} className="bg-[var(--vf-brand-primary)] hover:bg-[var(--vf-brand-primary-hover)] text-white gap-2">
          <PlusCircle className="h-4 w-4" /> New Thread
        </Button>
      </div>

      {/* Status filter tabs */}
      <div className="flex items-center gap-1 border-b">
        {STATUS_TABS.map((t) => (
          <button
            key={t.value}
            type="button"
            onClick={() => setStatusFilter(t.value)}
            className={`px-4 py-2.5 text-sm font-medium border-b-2 transition-colors ${
              statusFilter === t.value
                ? "border-[var(--vf-brand-primary)] text-[var(--vf-text-primary)]"
                : "border-transparent text-muted-foreground hover:text-gray-700"
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      {/* New thread form */}
      {showNew && (
        <div className="rounded-xl border border-[var(--vf-brand-primary)]/20 bg-white p-5 shadow-sm space-y-3">
          <h3 className="text-sm font-semibold text-gray-900">New Thread</h3>
          <div className="space-y-1">
            <label className="text-xs font-medium text-gray-700">Customer ID (UUID) *</label>
            <input
              value={newThreadForm.customer_id}
              onChange={(e) => setNewThreadForm((f) => ({ ...f, customer_id: e.target.value }))}
              placeholder="xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
              className="block w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-[var(--vf-brand-primary)]"
            />
          </div>
          <div className="space-y-1">
            <label className="text-xs font-medium text-gray-700">Subject (optional)</label>
            <input
              value={newThreadForm.subject}
              onChange={(e) => setNewThreadForm((f) => ({ ...f, subject: e.target.value }))}
              placeholder="Order inquiry, delivery issue…"
              className="block w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-[var(--vf-brand-primary)]"
            />
          </div>
          <div className="flex gap-2">
            <Button variant="outline" onClick={() => setShowNew(false)}>Cancel</Button>
            <Button
              disabled={actionLoading === "create_thread"}
              onClick={createThread}
              className="bg-[var(--vf-brand-primary)] hover:bg-[var(--vf-brand-primary-hover)] text-white"
            >
              {actionLoading === "create_thread" ? "Creating…" : "Create Thread"}
            </Button>
          </div>
        </div>
      )}

      {/* Thread list */}
      {loading && threads.length === 0 ? (
        <div className="text-center py-12">
          <RefreshCw className="h-6 w-6 animate-spin mx-auto text-muted-foreground" />
        </div>
      ) : threads.length === 0 ? (
        <div className="rounded-xl border bg-white shadow-sm py-12 text-center">
          <MessageCircle className="h-10 w-10 text-muted-foreground mx-auto mb-3" />
          <p className="text-gray-600 font-medium">No threads yet</p>
          <p className="text-sm text-muted-foreground mt-1">
            Customers can start conversations from the mobile app.
          </p>
        </div>
      ) : (
        <div className="rounded-xl border bg-white shadow-sm divide-y divide-gray-100">
          {threads.map((thread) => {
            const isExpanded = expandedThreadId === thread.id;
            const threadMessages = messages[thread.id] ?? [];
            return (
              <div key={thread.id}>
                {/* Thread row */}
                <button
                  type="button"
                  onClick={() => toggleThread(thread.id)}
                  className="w-full flex items-center gap-4 px-5 py-4 hover:bg-gray-50 transition-colors text-left"
                >
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-0.5">
                      <p className="text-sm font-medium text-gray-900">
                        {truncate(thread.customer_id, 18)}
                      </p>
                      {thread.unread_staff_count > 0 && (
                        <span className="inline-flex h-5 min-w-5 items-center justify-center rounded-full bg-red-500 text-white text-xs px-1">
                          {thread.unread_staff_count}
                        </span>
                      )}
                    </div>
                    <p className="text-xs text-muted-foreground">
                      {thread.subject ?? "No subject"} · {relativeTime(thread.last_message_at)}
                    </p>
                  </div>
                  <span className={styles[STATUS_MODULE[thread.status] ?? "statusClosed"]}>
                    {thread.status}
                  </span>
                  {isExpanded ? (
                    <ChevronUp className="h-4 w-4 text-muted-foreground flex-shrink-0" />
                  ) : (
                    <ChevronDown className="h-4 w-4 text-muted-foreground flex-shrink-0" />
                  )}
                </button>

                {/* Expanded messages */}
                {isExpanded && (
                  <div className="border-t border-gray-100 bg-gray-50 px-5 py-4 space-y-4">
                    {/* Message bubbles */}
                    <div className="space-y-3 max-h-80 overflow-y-auto">
                      {threadMessages.length === 0 ? (
                        <p className="text-sm text-muted-foreground text-center py-4">No messages yet.</p>
                      ) : (
                        threadMessages.map((msg) => (
                          <div
                            key={msg.id}
                            className={`flex flex-col ${msg.sender_type === "staff" ? "items-end" : "items-start"}`}
                          >
                            <span className="text-xs text-muted-foreground mb-1 px-1">
                              {msg.sender_type === "staff" ? "Staff" : "Customer"} · {relativeTime(msg.created_at)}
                            </span>
                            <div className={`flex items-end gap-2 ${msg.sender_type === "staff" ? "flex-row-reverse" : "flex-row"}`}>
                              <div
                                className={`max-w-xs rounded-xl px-3 py-2 text-sm ${
                                  msg.sender_type === "staff"
                                    ? "bg-gray-200 text-gray-900"
                                    : "bg-blue-600 text-white"
                                }`}
                              >
                                {msg.body}
                                {msg.attachment_url && (
                                  <a
                                    href={msg.attachment_url}
                                    target="_blank"
                                    rel="noreferrer"
                                    className="block mt-1 text-xs underline opacity-80"
                                  >
                                    Attachment
                                  </a>
                                )}
                              </div>
                              {msg.sender_type === "customer" && !msg.is_read && (
                                <button
                                  type="button"
                                  onClick={() => markRead(msg.id, thread.id)}
                                  title="Mark as read"
                                  className="text-muted-foreground hover:text-gray-700"
                                >
                                  <CheckCheck className="h-4 w-4" />
                                </button>
                              )}
                            </div>
                          </div>
                        ))
                      )}
                    </div>

                    {/* Reply box */}
                    <div className="space-y-2">
                      <textarea
                        value={newMsg}
                        onChange={(e) => setNewMsg(e.target.value)}
                        rows={2}
                        placeholder="Type a reply…"
                        className="block w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-[var(--vf-brand-primary)] bg-white"
                      />
                      {showAttachment && (
                        <div className="flex items-center gap-2">
                          <input
                            value={attachmentUrl}
                            onChange={(e) => setAttachmentUrl(e.target.value)}
                            placeholder="Attachment URL (optional)"
                            className="flex-1 rounded-md border border-gray-300 px-3 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-[var(--vf-brand-primary)] bg-white"
                          />
                          <button type="button" onClick={() => { setShowAttachment(false); setAttachmentUrl(""); }}>
                            <X className="h-4 w-4 text-muted-foreground" />
                          </button>
                        </div>
                      )}
                      <div className="flex items-center justify-between">
                        <div className="flex gap-2">
                          <button
                            type="button"
                            onClick={() => setShowAttachment((v) => !v)}
                            className="text-xs text-muted-foreground hover:text-gray-700 flex items-center gap-1"
                          >
                            <Paperclip className="h-3.5 w-3.5" /> Attachment
                          </button>
                        </div>
                        <div className="flex items-center gap-2">
                          {thread.status === "open" && (
                            <>
                              <Button
                                variant="outline"
                                size="sm"
                                disabled={actionLoading === thread.id + "_resolved"}
                                onClick={() => updateThreadStatus(thread.id, "resolved")}
                              >
                                {actionLoading === thread.id + "_resolved" ? (
                                  <RefreshCw className="h-3 w-3 animate-spin" />
                                ) : "Resolve"}
                              </Button>
                              <Button
                                variant="outline"
                                size="sm"
                                disabled={actionLoading === thread.id + "_closed"}
                                onClick={() => updateThreadStatus(thread.id, "closed")}
                                className="border-gray-300 text-gray-600"
                              >
                                {actionLoading === thread.id + "_closed" ? (
                                  <RefreshCw className="h-3 w-3 animate-spin" />
                                ) : "Close"}
                              </Button>
                            </>
                          )}
                          <Button
                            size="sm"
                            disabled={sendingMsg || !newMsg.trim()}
                            onClick={() => sendMessage(thread.id)}
                            className="bg-[var(--vf-brand-primary)] hover:bg-[var(--vf-brand-primary-hover)] text-white gap-1"
                          >
                            {sendingMsg ? (
                              <RefreshCw className="h-3.5 w-3.5 animate-spin" />
                            ) : (
                              <Send className="h-3.5 w-3.5" />
                            )}
                            Send
                          </Button>
                        </div>
                      </div>
                    </div>
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
