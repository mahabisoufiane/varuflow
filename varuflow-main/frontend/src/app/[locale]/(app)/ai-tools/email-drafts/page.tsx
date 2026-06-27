"use client";
import { useState, useEffect } from "react";
import { api } from "@/lib/api-client";
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

interface DraftResult {
  id: string;
  draft_text: string;
}

interface DraftHistoryItem {
  id: string;
  message_id: string;
  tone: string;
  draft_text: string;
  accepted: boolean;
  created_at: string;
}

export default function EmailDraftsPage() {
  const [messageId, setMessageId] = useState("");
  const [tone, setTone] = useState("professional");
  const [draft, setDraft] = useState<DraftResult | null>(null);
  const [messageIdFilter, setMessageIdFilter] = useState("");
  const [history, setHistory] = useState<DraftHistoryItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [error, setError] = useState("");

  async function fetchHistory(filter?: string) {
    setHistoryLoading(true);
    try {
      const query = filter ? `?message_id=${encodeURIComponent(filter)}` : "";
      setHistory(await api.get<DraftHistoryItem[]>(`/api/ai/email-drafts${query}`));
    } catch {
      // non-critical
    } finally {
      setHistoryLoading(false);
    }
  }

  useEffect(() => {
    fetchHistory();
  }, []);

  async function handleGenerate(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError("");
    setDraft(null);
    try {
      setDraft(await api.post<DraftResult>("/api/ai/email-drafts/generate", { message_id: messageId, tone }));
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Generation failed");
    } finally {
      setLoading(false);
    }
  }

  async function handleAccept() {
    if (!draft) return;
    try {
      await api.post(`/api/ai/email-drafts/${draft.id}/accept`, {});
      setDraft(null);
      await fetchHistory();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Accept failed");
    }
  }

  async function handleReject() {
    if (!draft) return;
    try {
      await api.post(`/api/ai/email-drafts/${draft.id}/reject`, {});
    } catch {
      // ignore
    } finally {
      setDraft(null);
    }
  }

  return (
    <div className="p-6 space-y-6">
      <h1 className="text-2xl font-bold">AI Email Reply Drafts</h1>

      <Card>
        <CardHeader>
          <CardTitle>Generate Draft</CardTitle>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleGenerate} className="space-y-3">
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <Input
                placeholder="Message ID (UUID)"
                value={messageId}
                onChange={(e) => setMessageId(e.target.value)}
                required
              />
              <select
                className="border rounded px-3 py-2 text-sm bg-background"
                value={tone}
                onChange={(e) => setTone(e.target.value)}
              >
                <option value="professional">Professional</option>
                <option value="friendly">Friendly</option>
                <option value="brief">Brief</option>
              </select>
            </div>
            {error && <p className="text-red-500 text-sm">{error}</p>}
            <Button type="submit" disabled={loading}>
              {loading ? "Generating…" : "Generate Draft"}
            </Button>
          </form>
        </CardContent>
      </Card>

      {draft && (
        <Card className="border-2 border-blue-200">
          <CardHeader>
            <CardTitle>Draft Reply</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <p className="text-sm leading-relaxed whitespace-pre-wrap">{draft.draft_text}</p>
            <div className="flex gap-2">
              <Button onClick={handleAccept}>Accept</Button>
              <Button variant="outline" onClick={handleReject}>
                Reject
              </Button>
            </div>
          </CardContent>
        </Card>
      )}

      <Card>
        <CardHeader>
          <CardTitle>History</CardTitle>
          <div className="flex gap-2 mt-2">
            <Input
              placeholder="Filter by message ID"
              value={messageIdFilter}
              onChange={(e) => setMessageIdFilter(e.target.value)}
              className="max-w-xs"
            />
            <Button variant="outline" onClick={() => fetchHistory(messageIdFilter)}>
              Search
            </Button>
          </div>
        </CardHeader>
        <CardContent>
          {historyLoading ? (
            <p className="text-muted-foreground">Loading…</p>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Message ID</TableHead>
                  <TableHead>Tone</TableHead>
                  <TableHead>Draft Snippet</TableHead>
                  <TableHead>Accepted</TableHead>
                  <TableHead>Created At</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {history.length === 0 && (
                  <TableRow>
                    <TableCell colSpan={5} className="text-center text-muted-foreground">
                      No history yet.
                    </TableCell>
                  </TableRow>
                )}
                {history.map((item) => (
                  <TableRow key={item.id}>
                    <TableCell className="font-mono text-xs">{item.message_id}</TableCell>
                    <TableCell>
                      <Badge variant="outline">{item.tone}</Badge>
                    </TableCell>
                    <TableCell className="max-w-xs truncate text-sm">
                      {item.draft_text.slice(0, 80)}…
                    </TableCell>
                    <TableCell>
                      <Badge variant={item.accepted ? "default" : "outline"}>
                        {item.accepted ? "Yes" : "No"}
                      </Badge>
                    </TableCell>
                    <TableCell className="whitespace-nowrap text-xs">
                      {new Date(item.created_at).toLocaleString()}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
