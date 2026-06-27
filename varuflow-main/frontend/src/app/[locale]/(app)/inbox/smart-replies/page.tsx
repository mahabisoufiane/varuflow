"use client";
import { useState } from "react";
import { api } from "@/lib/api-client";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import styles from "./page.module.scss";

function toneBadgeClass(tone: string): keyof typeof styles {
  const map: Record<string, keyof typeof styles> = {
    professional: "toneProfessional",
    friendly:     "toneFriendly",
    brief:        "toneBrief",
  };
  return map[tone] ?? "toneBrief";
}

interface SmartReplySuggestion {
  tone: string;
  reply: string;
  index: number;
}

export default function SmartRepliesPage() {
  const [messageId, setMessageId] = useState("");
  const [suggestions, setSuggestions] = useState<SmartReplySuggestion[]>([]);
  const [logId, setLogId] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [accepted, setAccepted] = useState<number | null>(null);
  const [acceptLoading, setAcceptLoading] = useState<number | null>(null);

  async function handleGetSuggestions(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError("");
    setSuggestions([]);
    setLogId(null);
    setAccepted(null);
    try {
      const data = await api.post<{ suggestions?: SmartReplySuggestion[]; log_id?: string } & SmartReplySuggestion[]>(
        "/api/inbox/smart-reply",
        { message_id: messageId }
      );
      setSuggestions((data as any).suggestions ?? data);
      setLogId((data as any).log_id ?? null);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to get suggestions");
    } finally {
      setLoading(false);
    }
  }

  async function handleAccept(index: number) {
    if (!logId) return;
    setAcceptLoading(index);
    try {
      await api.post(`/api/inbox/smart-reply/${logId}/accept`, { index });
      setAccepted(index);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to accept reply");
    } finally {
      setAcceptLoading(null);
    }
  }

  return (
    <div className="p-6 space-y-6">
      <h1 className="text-2xl font-bold">Smart Reply Suggestions</h1>

      <p className="text-sm text-muted-foreground">
        AI suggests 3 reply options based on message context.
      </p>

      <Card>
        <CardHeader>
          <CardTitle>Get Suggestions</CardTitle>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleGetSuggestions} className="flex gap-3 items-end">
            <div className="space-y-1 flex-1 min-w-48">
              <label className="text-sm font-medium">Message ID (UUID) *</label>
              <Input
                required
                value={messageId}
                onChange={(e) => setMessageId(e.target.value)}
                placeholder="message UUID"
              />
            </div>
            <Button type="submit" disabled={loading}>
              {loading ? "Generating…" : "Get Suggestions"}
            </Button>
          </form>
          {error && <p className="text-red-500 text-sm mt-2">{error}</p>}
        </CardContent>
      </Card>

      {suggestions.length > 0 && (
        <div className="space-y-4">
          {suggestions.map((s, i) => (
            <Card key={i}>
              <CardContent className="pt-4 space-y-3">
                <div className="flex items-center gap-2">
                  <span
                    className={styles[toneBadgeClass(s.tone)]}
                  >
                    {s.tone}
                  </span>
                  {accepted === (s.index ?? i) && (
                    <Badge variant="default">Reply accepted</Badge>
                  )}
                </div>
                <p className="text-sm whitespace-pre-wrap">{s.reply}</p>
                {accepted !== (s.index ?? i) && (
                  <Button
                    size="sm"
                    variant="outline"
                    disabled={acceptLoading === (s.index ?? i) || !logId}
                    onClick={() => handleAccept(s.index ?? i)}
                  >
                    {acceptLoading === (s.index ?? i) ? "Accepting…" : "Use This Reply"}
                  </Button>
                )}
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
