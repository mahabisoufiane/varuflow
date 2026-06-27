"use client";
import { useState, useEffect } from "react";
import { useParams, useRouter } from "next/navigation";
import { api } from "@/lib/api-client";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import styles from "./page.module.scss";

const CHANNELS = ["all", "email", "whatsapp", "sms", "in_app", "contact_form"] as const;
type Channel = (typeof CHANNELS)[number];

function channelLabel(c: Channel) {
  const map: Record<Channel, string> = {
    all: "All",
    email: "Email",
    whatsapp: "WhatsApp",
    sms: "SMS",
    in_app: "In-App",
    contact_form: "Contact Form",
  };
  return map[c];
}

function sentimentClass(s: string): keyof typeof styles {
  const map: Record<string, keyof typeof styles> = {
    positive: "sentimentPositive",
    neutral:  "sentimentNeutral",
    negative: "sentimentNegative",
  };
  return map[s] ?? "sentimentNeutral";
}

function directionClass(d: string): keyof typeof styles {
  return d === "inbound" ? "directionInbound" : "directionOutbound";
}

interface Thread {
  id: string;
  subject?: string;
  customer_id: string;
  channel: string;
  last_message_at: string;
  is_read: boolean;
  sentiment?: string;
}

interface Message {
  id: string;
  direction: string;
  sender_name?: string;
  body: string;
  created_at: string;
}

export default function InboxPage() {
  const params = useParams();
  const router = useRouter();
  const locale = params.locale as string;

  const [threads, setThreads] = useState<Thread[]>([]);
  const [channelFilter, setChannelFilter] = useState<Channel>("all");
  const [unreadCount, setUnreadCount] = useState<number | null>(null);
  const [selectedThread, setSelectedThread] = useState<Thread | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [replyBody, setReplyBody] = useState("");
  const [replyLoading, setReplyLoading] = useState(false);

  async function fetchThreads() {
    setLoading(true);
    setError("");
    try {
      const qp = new URLSearchParams({ limit: "50" });
      if (channelFilter !== "all") qp.set("channel", channelFilter);
      const data = await api.get<Thread[]>(`/api/inbox/threads?${qp}`);
      setThreads(data);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to load threads");
    } finally {
      setLoading(false);
    }
  }

  async function fetchUnreadCount() {
    try {
      const data = await api.get<{ count?: number } | number>("/api/inbox/unread-count");
      setUnreadCount((data as any).count ?? data);
    } catch {
      // non-fatal
    }
  }

  async function loadMessages(thread: Thread) {
    setSelectedThread(thread);
    try {
      const data = await api.get<Message[]>(`/api/inbox/threads/${thread.id}/messages`);
      setMessages(data);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to load messages");
    }
  }

  useEffect(() => {
    fetchThreads();
    fetchUnreadCount();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [channelFilter]);

  async function handleReply(e: React.FormEvent) {
    e.preventDefault();
    if (!selectedThread) return;
    setReplyLoading(true);
    try {
      await api.post(`/api/inbox/threads/${selectedThread.id}/messages`, {
        body: replyBody,
        direction: "outbound",
      });
      setReplyBody("");
      loadMessages(selectedThread);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to send reply");
    } finally {
      setReplyLoading(false);
    }
  }

  async function markRead(msgId: string) {
    try {
      await api.post(`/api/inbox/messages/${msgId}/read`, {});
      if (selectedThread) loadMessages(selectedThread);
      fetchUnreadCount();
    } catch {
      // non-fatal
    }
  }

  async function archiveThread() {
    if (!selectedThread) return;
    try {
      await api.post(`/api/inbox/threads/${selectedThread.id}/archive`, {});
      setSelectedThread(null);
      setMessages([]);
      fetchThreads();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Archive failed");
    }
  }

  return (
    <div className="p-6 space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Unified Inbox</h1>
        {unreadCount !== null && (
          <Badge variant="destructive">{unreadCount} unread</Badge>
        )}
      </div>

      {error && <p className="text-red-500 text-sm">{error}</p>}

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 h-[calc(100vh-180px)]">
        {/* Left: Thread list */}
        <div className="flex flex-col gap-3 overflow-hidden">
          <div className="flex flex-wrap gap-2">
            {CHANNELS.map((c) => (
              <Button
                key={c}
                size="sm"
                variant={channelFilter === c ? "default" : "outline"}
                onClick={() => setChannelFilter(c)}
              >
                {channelLabel(c)}
              </Button>
            ))}
          </div>
          {loading ? (
            <p className="text-muted-foreground">Loading...</p>
          ) : (
            <div className="overflow-y-auto flex-1 space-y-2 pr-1">
              {threads.length === 0 && (
                <p className="text-muted-foreground text-sm">No threads found.</p>
              )}
              {threads.map((t) => (
                <div
                  key={t.id}
                  className={`border rounded-lg p-3 cursor-pointer hover:bg-muted/50 transition-colors ${selectedThread?.id === t.id ? "border-primary bg-muted/30" : ""}`}
                  onClick={() => loadMessages(t)}
                >
                  <div className="flex items-start justify-between gap-2">
                    <div className="flex items-center gap-2 min-w-0">
                      {!t.is_read && (
                        <span className="w-2 h-2 rounded-full bg-blue-500 shrink-0" />
                      )}
                      <span className="font-medium text-sm truncate">
                        {t.subject || "(no subject)"}
                      </span>
                    </div>
                    <span className="text-xs text-muted-foreground shrink-0">
                      {new Date(t.last_message_at).toLocaleDateString()}
                    </span>
                  </div>
                  <div className="flex items-center gap-2 mt-1 flex-wrap">
                    <span className="text-xs text-muted-foreground font-mono">{t.customer_id.slice(0, 8)}…</span>
                    <Badge variant="outline" className="text-xs">{t.channel}</Badge>
                    {t.sentiment && (
                      <span
                        className={styles[sentimentClass(t.sentiment)]}
                      >
                        {t.sentiment}
                      </span>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Right: Messages */}
        <div>
          {!selectedThread ? (
            <div className="h-full flex items-center justify-center text-muted-foreground border rounded-lg">
              Select a thread to view messages
            </div>
          ) : (
            <Card className="h-full flex flex-col">
              <div className="flex items-center justify-between p-4 border-b gap-2 flex-wrap">
                <div>
                  <p className="font-semibold text-sm">{selectedThread.subject || "(no subject)"}</p>
                  <p className="text-xs text-muted-foreground">{selectedThread.customer_id}</p>
                </div>
                <div className="flex gap-2 flex-wrap">
                  <Button size="sm" variant="outline" onClick={archiveThread}>
                    Archive
                  </Button>
                  <Button
                    size="sm"
                    variant="ghost"
                    onClick={() => router.push(`/${locale}/inbox/sentiment`)}
                  >
                    Analyze Sentiment
                  </Button>
                  <Button
                    size="sm"
                    variant="ghost"
                    onClick={() => router.push(`/${locale}/inbox/translation`)}
                  >
                    Translate
                  </Button>
                </div>
              </div>
              <CardContent className="flex-1 overflow-y-auto space-y-3 py-4">
                {messages.map((m) => (
                  <div key={m.id} className="space-y-1">
                    <div className="flex items-center gap-2">
                      <span
                        className={styles[directionClass(m.direction)]}
                      >
                        {m.direction}
                      </span>
                      {m.sender_name && (
                        <span className="text-xs font-medium">{m.sender_name}</span>
                      )}
                      <span className="text-xs text-muted-foreground ml-auto">
                        {new Date(m.created_at).toLocaleString()}
                      </span>
                      {!selectedThread.is_read && (
                        <Button
                          size="sm"
                          variant="ghost"
                          className="text-xs h-6 px-2"
                          onClick={() => markRead(m.id)}
                        >
                          Mark read
                        </Button>
                      )}
                    </div>
                    <p className="text-sm border rounded-md p-2 bg-muted/20">{m.body}</p>
                  </div>
                ))}
              </CardContent>
              <div className="p-4 border-t">
                <form onSubmit={handleReply} className="flex gap-2">
                  <Input
                    placeholder="Write a reply…"
                    value={replyBody}
                    onChange={(e) => setReplyBody(e.target.value)}
                    required
                    className="flex-1"
                  />
                  <Button type="submit" disabled={replyLoading}>
                    {replyLoading ? "Sending…" : "Send"}
                  </Button>
                </form>
              </div>
            </Card>
          )}
        </div>
      </div>
    </div>
  );
}
