"use client";
import { useState, useEffect } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { api } from "@/lib/api-client";

interface ChatbotConfig {
  is_enabled: boolean;
  welcome_message: string;
  escalation_threshold: number;
  knowledge_base_enabled: boolean;
  handoff_email: string;
}

interface BotMessage {
  role: string;
  content: string;
}

interface BotConversation {
  id: string;
  visitor_id: string;
  messages: BotMessage[];
  escalated: boolean;
  created_at: string;
}

export default function ChatbotPage() {
  const [config, setConfig] = useState<ChatbotConfig | null>(null);
  const [configLoading, setConfigLoading] = useState(false);
  const [configError, setConfigError] = useState("");
  const [configSaving, setConfigSaving] = useState(false);
  const [configSuccess, setConfigSuccess] = useState(false);

  const [conversations, setConversations] = useState<BotConversation[]>([]);
  const [convoLoading, setConvoLoading] = useState(false);
  const [convoError, setConvoError] = useState("");
  const [expandedId, setExpandedId] = useState<string | null>(null);

  async function loadConfig() {
    setConfigLoading(true);
    setConfigError("");
    try {
      const data = await api.get<ChatbotConfig>("/api/chatbot/config");
      setConfig(data);
    } catch (e: unknown) {
      setConfigError(e instanceof Error ? e.message : "Failed to load config");
    } finally {
      setConfigLoading(false);
    }
  }

  async function loadConversations() {
    setConvoLoading(true);
    setConvoError("");
    try {
      const data = await api.get<BotConversation[] | { items: BotConversation[] }>("/api/chatbot/conversations");
      setConversations(Array.isArray(data) ? data : data.items ?? []);
    } catch (e: unknown) {
      setConvoError(e instanceof Error ? e.message : "Failed to load conversations");
    } finally {
      setConvoLoading(false);
    }
  }

  useEffect(() => {
    loadConfig();
    loadConversations();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function handleSaveConfig() {
    if (!config) return;
    setConfigSaving(true);
    setConfigError("");
    setConfigSuccess(false);
    try {
      await api.put("/api/chatbot/config", config);
      setConfigSuccess(true);
    } catch (e: unknown) {
      setConfigError(e instanceof Error ? e.message : "Failed to save config");
    } finally {
      setConfigSaving(false);
    }
  }

  return (
    <div className="p-6 space-y-6">
      <h1 className="text-2xl font-bold">Chatbot Configuration</h1>

      {/* Config section */}
      <Card>
        <CardHeader><CardTitle>Settings</CardTitle></CardHeader>
        <CardContent className="space-y-4">
          {configLoading && <p className="text-muted-foreground">Loading...</p>}
          {configError && <p className="text-red-500 text-sm">{configError}</p>}

          {config && !configLoading && (
            <>
              <label className="flex items-center gap-2 text-sm cursor-pointer">
                <input
                  type="checkbox"
                  checked={config.is_enabled}
                  onChange={(e) => setConfig((c) => c ? { ...c, is_enabled: e.target.checked } : c)}
                />
                Chatbot Enabled
              </label>

              <div>
                <label className="text-xs text-muted-foreground block mb-1">Welcome Message</label>
                <textarea
                  className="w-full min-h-[80px] rounded-md border border-input bg-background px-3 py-2 text-sm"
                  value={config.welcome_message}
                  onChange={(e) =>
                    setConfig((c) => c ? { ...c, welcome_message: e.target.value } : c)
                  }
                />
              </div>

              <div>
                <label className="text-xs text-muted-foreground block mb-1">
                  Escalation Threshold (messages before handoff)
                </label>
                <Input
                  type="number"
                  min="1"
                  value={config.escalation_threshold}
                  onChange={(e) =>
                    setConfig((c) =>
                      c ? { ...c, escalation_threshold: Number(e.target.value) } : c
                    )
                  }
                  className="w-32"
                />
              </div>

              <label className="flex items-center gap-2 text-sm cursor-pointer">
                <input
                  type="checkbox"
                  checked={config.knowledge_base_enabled}
                  onChange={(e) =>
                    setConfig((c) => c ? { ...c, knowledge_base_enabled: e.target.checked } : c)
                  }
                />
                Use Knowledge Base for answers
              </label>

              <div>
                <label className="text-xs text-muted-foreground block mb-1">Handoff Email</label>
                <Input
                  type="email"
                  value={config.handoff_email}
                  onChange={(e) =>
                    setConfig((c) => c ? { ...c, handoff_email: e.target.value } : c)
                  }
                  className="w-72"
                />
              </div>

              {configSuccess && (
                <p className="text-green-600 text-sm font-medium">Configuration saved</p>
              )}

              <Button onClick={handleSaveConfig} disabled={configSaving}>
                {configSaving ? "Saving…" : "Save"}
              </Button>
            </>
          )}
        </CardContent>
      </Card>

      {/* Conversations section */}
      <Card>
        <CardHeader><CardTitle>Conversations</CardTitle></CardHeader>
        <CardContent>
          {convoLoading && <p className="text-muted-foreground">Loading...</p>}
          {convoError && <p className="text-red-500 text-sm">{convoError}</p>}
          {!convoLoading && (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Visitor ID</TableHead>
                  <TableHead>Messages</TableHead>
                  <TableHead>Escalated</TableHead>
                  <TableHead>Created At</TableHead>
                  <TableHead></TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {conversations.length === 0 && (
                  <TableRow>
                    <TableCell colSpan={5} className="text-center text-muted-foreground py-8">
                      No conversations yet
                    </TableCell>
                  </TableRow>
                )}
                {conversations.map((c) => (
                  <>
                    <TableRow key={c.id} className="cursor-pointer hover:bg-muted/50">
                      <TableCell className="font-mono text-xs">
                        {c.visitor_id?.slice(0, 8)}…
                      </TableCell>
                      <TableCell>{c.messages?.length ?? 0}</TableCell>
                      <TableCell>
                        <Badge variant={c.escalated ? "destructive" : "secondary"}>
                          {c.escalated ? "Yes" : "No"}
                        </Badge>
                      </TableCell>
                      <TableCell className="text-sm">
                        {new Date(c.created_at).toLocaleString()}
                      </TableCell>
                      <TableCell>
                        <Button
                          size="sm"
                          variant="outline"
                          onClick={() => setExpandedId(expandedId === c.id ? null : c.id)}
                        >
                          {expandedId === c.id ? "Hide" : "View"}
                        </Button>
                      </TableCell>
                    </TableRow>
                    {expandedId === c.id && (
                      <TableRow key={`exp-${c.id}`}>
                        <TableCell colSpan={5} className="bg-muted/30">
                          <div className="p-3 space-y-2 max-h-[300px] overflow-y-auto">
                            {(c.messages ?? []).map((m, i) => (
                              <div
                                key={i}
                                className={`flex ${m.role === "user" ? "justify-start" : "justify-end"}`}
                              >
                                <div
                                  className={`rounded-lg px-3 py-2 text-sm max-w-[70%] ${m.role === "user" ? "bg-purple-100 text-purple-900" : "bg-blue-100 text-blue-900"}`}
                                >
                                  <span className="text-xs font-semibold block mb-0.5 capitalize">
                                    {m.role}
                                  </span>
                                  {m.content}
                                </div>
                              </div>
                            ))}
                          </div>
                        </TableCell>
                      </TableRow>
                    )}
                  </>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
