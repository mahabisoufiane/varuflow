"use client";
import { useState, useEffect } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { api } from "@/lib/api-client";
import styles from "./page.module.scss";

type SessionStatus = "all" | "open" | "in_progress" | "resolved";

interface ChatSession {
  id: string;
  visitor_name: string | null;
  visitor_email: string | null;
  status: "open" | "in_progress" | "resolved";
  page_url: string | null;
  created_at: string;
}

interface ChatMessage {
  id: string;
  sender_type: "visitor" | "staff" | "bot";
  sender_name: string | null;
  body: string;
  created_at: string;
}

const STATUS_BADGE: Record<string, string> = {
  open: "bg-green-100 text-green-800",
  in_progress: "bg-blue-100 text-blue-800",
  resolved: "bg-gray-100 text-gray-600",
};

const STATUS_MODULE: Record<string, keyof typeof styles> = {
  open:        "statusOpen",
  in_progress: "statusInProgress",
  resolved:    "statusResolved",
};

const SENDER_BADGE: Record<string, string> = {
  visitor: "bg-purple-100 text-purple-800",
  staff: "bg-blue-100 text-blue-800",
  bot: "bg-gray-100 text-gray-600",
};

const SENDER_MODULE: Record<string, keyof typeof styles> = {
  visitor: "senderVisitor",
  staff:   "senderStaff",
  bot:     "senderBot",
};

function domain(url: string | null) {
  if (!url) return "—";
  try {
    return new URL(url).hostname;
  } catch {
    return url;
  }
}

export default function LiveChatPage() {
  const [sessions, setSessions] = useState<ChatSession[]>([]);
  const [statusFilter, setStatusFilter] = useState<SessionStatus>("all");
  const [selectedSession, setSelectedSession] = useState<ChatSession | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [loadingSessions, setLoadingSessions] = useState(false);
  const [loadingMessages, setLoadingMessages] = useState(false);
  const [error, setError] = useState("");

  const [replyText, setReplyText] = useState("");
  const [replySending, setReplySending] = useState(false);
  const [resolving, setResolving] = useState(false);

  async function loadSessions(status: SessionStatus) {
    setLoadingSessions(true);
    setError("");
    try {
      const qs = status !== "all" ? `?status=${status}` : "";
      const data = await api.get<ChatSession[] | { items: ChatSession[] }>(`/api/live-chat/sessions${qs}`);
      setSessions(Array.isArray(data) ? data : data.items ?? []);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to load sessions");
    } finally {
      setLoadingSessions(false);
    }
  }

  async function loadMessages(sessionId: string) {
    setLoadingMessages(true);
    try {
      const data = await api.get<ChatMessage[] | { items: ChatMessage[] }>(`/api/live-chat/sessions/${sessionId}/messages`);
      setMessages(Array.isArray(data) ? data : data.items ?? []);
    } catch {
      setMessages([]);
    } finally {
      setLoadingMessages(false);
    }
  }

  useEffect(() => {
    loadSessions(statusFilter);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [statusFilter]);

  function selectSession(s: ChatSession) {
    setSelectedSession(s);
    setReplyText("");
    loadMessages(s.id);
  }

  async function handleSendReply() {
    if (!selectedSession || !replyText.trim()) return;
    setReplySending(true);
    try {
      await api.post(`/api/live-chat/sessions/${selectedSession.id}/messages`, {
        sender_type: "staff",
        body: replyText,
      });
      setReplyText("");
      loadMessages(selectedSession.id);
    } catch {
      setError("Failed to send message");
    } finally {
      setReplySending(false);
    }
  }

  async function handleResolve() {
    if (!selectedSession) return;
    setResolving(true);
    try {
      await api.post(`/api/live-chat/sessions/${selectedSession.id}/resolve`, {});
      loadSessions(statusFilter);
      setSelectedSession((s) => s ? { ...s, status: "resolved" } : null);
    } catch {
      setError("Failed to resolve session");
    } finally {
      setResolving(false);
    }
  }

  const STATUS_TABS: SessionStatus[] = ["all", "open", "in_progress", "resolved"];

  return (
    <div className="p-6 space-y-4">
      <h1 className="text-2xl font-bold">Live Chat Sessions</h1>

      {error && <p className="text-red-500 text-sm">{error}</p>}

      {/* Status tabs */}
      <div className="flex gap-2 flex-wrap">
        {STATUS_TABS.map((s) => (
          <Button
            key={s}
            variant={statusFilter === s ? "default" : "outline"}
            size="sm"
            onClick={() => setStatusFilter(s)}
          >
            {s === "all" ? "All" : s.replace("_", " ")}
          </Button>
        ))}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 h-[600px]">
        {/* Left: session list */}
        <Card className="overflow-y-auto">
          <CardContent className="pt-4 space-y-2">
            {loadingSessions && <p className="text-muted-foreground">Loading...</p>}
            {!loadingSessions && sessions.length === 0 && (
              <p className="text-muted-foreground text-center py-8">No sessions found</p>
            )}
            {sessions.map((s) => (
              <button
                key={s.id}
                className={`w-full text-left rounded-lg border p-3 space-y-1 transition-colors hover:bg-muted ${selectedSession?.id === s.id ? "border-primary bg-muted" : ""}`}
                onClick={() => selectSession(s)}
              >
                <div className="flex items-center justify-between">
                  <span className="font-medium text-sm">
                    {s.visitor_name ?? "Anonymous"}
                  </span>
                  <span className={styles[STATUS_MODULE[s.status] ?? "statusResolved"]}>
                    {s.status}
                  </span>
                </div>
                {s.visitor_email && (
                  <p className="text-xs text-muted-foreground">{s.visitor_email}</p>
                )}
                <p className="text-xs text-muted-foreground">{domain(s.page_url)}</p>
                <p className="text-xs text-muted-foreground">
                  {new Date(s.created_at).toLocaleString()}
                </p>
              </button>
            ))}
          </CardContent>
        </Card>

        {/* Right: messages */}
        <Card className="flex flex-col overflow-hidden">
          {!selectedSession ? (
            <CardContent className="flex items-center justify-center h-full text-muted-foreground">
              Select a session to view messages
            </CardContent>
          ) : (
            <>
              <CardHeader className="pb-2 border-b">
                <div className="flex items-center justify-between">
                  <CardTitle className="text-base">
                    {selectedSession.visitor_name ?? "Anonymous"}
                  </CardTitle>
                  {selectedSession.status !== "resolved" && (
                    <Button size="sm" variant="outline" onClick={handleResolve} disabled={resolving}>
                      {resolving ? "Resolving…" : "Resolve"}
                    </Button>
                  )}
                </div>
              </CardHeader>
              <CardContent className="flex-1 overflow-y-auto pt-4 space-y-3">
                {loadingMessages && <p className="text-muted-foreground">Loading...</p>}
                {messages.map((m) => (
                  <div key={m.id} className="space-y-1">
                    <div className="flex items-center gap-2">
                      <span className={styles[SENDER_MODULE[m.sender_type] ?? "senderBot"]}>
                        {m.sender_type}
                      </span>
                      <span className="text-xs text-muted-foreground">{m.sender_name}</span>
                      <span className="text-xs text-muted-foreground ml-auto">
                        {new Date(m.created_at).toLocaleTimeString()}
                      </span>
                    </div>
                    <p className="text-sm bg-muted rounded-md px-3 py-2">{m.body}</p>
                  </div>
                ))}
              </CardContent>
              {selectedSession.status !== "resolved" && (
                <div className="p-3 border-t flex gap-2">
                  <textarea
                    className="flex-1 min-h-[60px] rounded-md border border-input bg-background px-3 py-2 text-sm resize-none"
                    value={replyText}
                    onChange={(e) => setReplyText(e.target.value)}
                    placeholder="Reply as staff…"
                  />
                  <Button
                    size="sm"
                    onClick={handleSendReply}
                    disabled={replySending || !replyText.trim()}
                    className="self-end"
                  >
                    {replySending ? "…" : "Send as Staff"}
                  </Button>
                </div>
              )}
            </>
          )}
        </Card>
      </div>
    </div>
  );
}
