"use client";
import { useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";

const API = process.env.NEXT_PUBLIC_API_URL;
function getToken() {
  return typeof window !== "undefined" ? localStorage.getItem("auth_token") ?? "" : "";
}

function toneBadgeClass(tone: string) {
  const map: Record<string, string> = {
    professional: "bg-blue-100 text-blue-800",
    friendly: "bg-green-100 text-green-800",
    brief: "bg-gray-100 text-gray-800",
  };
  return map[tone] ?? "bg-gray-100 text-gray-800";
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
      const res = await fetch(`${API}/api/inbox/smart-reply`, {
        method: "POST",
        headers: {
          Authorization: `Bearer ${getToken()}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ message_id: messageId }),
      });
      if (!res.ok) throw new Error(`Error ${res.status}`);
      const data = await res.json();
      setSuggestions(data.suggestions ?? data);
      setLogId(data.log_id ?? null);
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
      const res = await fetch(`${API}/api/inbox/smart-reply/${logId}/accept`, {
        method: "POST",
        headers: {
          Authorization: `Bearer ${getToken()}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ index }),
      });
      if (!res.ok) throw new Error(`Error ${res.status}`);
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
                    className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${toneBadgeClass(s.tone)}`}
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
