"use client";
import { useState, useEffect } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { api } from "@/lib/api-client";

interface VoiceResult {
  result_text: string;
  result_data?: unknown;
}

interface VoiceHistoryItem {
  id: string;
  transcript: string;
  parsed_intent: unknown;
  result_text: string;
  created_at: string;
}

const SUGGESTED_QUERIES = [
  "Revenue this month",
  "Invoices this week",
  "New customers this month",
  "Refunds this month",
];

export default function VoiceReportsPage() {
  const [transcript, setTranscript] = useState("");
  const [result, setResult] = useState<VoiceResult | null>(null);
  const [history, setHistory] = useState<VoiceHistoryItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [error, setError] = useState("");

  async function fetchHistory() {
    setHistoryLoading(true);
    try {
      setHistory(await api.get<VoiceHistoryItem[]>("/api/voice/history"));
    } catch {
      // non-critical, history can fail silently
    } finally {
      setHistoryLoading(false);
    }
  }

  useEffect(() => {
    fetchHistory();
  }, []);

  async function submitQuery(queryText?: string) {
    const text = queryText ?? transcript;
    if (!text.trim()) return;
    setLoading(true);
    setError("");
    setResult(null);
    try {
      const data = await api.post<VoiceResult>("/api/voice/query", { transcript: text });
      setResult(data);
      if (queryText) setTranscript(queryText);
      await fetchHistory();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Query failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="p-6 space-y-6">
      <h1 className="text-2xl font-bold">Voice Reports</h1>

      <Card>
        <CardHeader>
          <CardTitle>Ask a Question</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex gap-2">
            <Input
              className="flex-1 text-base"
              placeholder="e.g. What's my revenue this month?"
              value={transcript}
              onChange={(e) => setTranscript(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && submitQuery()}
            />
            <Button onClick={() => submitQuery()} disabled={loading || !transcript.trim()}>
              {loading ? "Submitting…" : "Submit"}
            </Button>
          </div>

          <div className="flex flex-wrap gap-2">
            {SUGGESTED_QUERIES.map((q) => (
              <button
                key={q}
                onClick={() => submitQuery(q)}
                disabled={loading}
                className="px-3 py-1 rounded-full border text-sm hover:bg-muted transition-colors disabled:opacity-50"
              >
                {q}
              </button>
            ))}
          </div>

          {error && <p className="text-red-500 text-sm">{error}</p>}

          {result && (
            <div className="space-y-3">
              <Card className="bg-muted">
                <CardContent className="pt-4">
                  <p className="text-lg font-medium">{result.result_text}</p>
                </CardContent>
              </Card>
              {result.result_data !== undefined && (
                <pre className="bg-gray-900 text-green-400 text-xs p-4 rounded-lg overflow-auto max-h-64">
                  {JSON.stringify(result.result_data, null, 2)}
                </pre>
              )}
            </div>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Query History</CardTitle>
        </CardHeader>
        <CardContent>
          {historyLoading ? (
            <p className="text-muted-foreground">Loading…</p>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Transcript</TableHead>
                  <TableHead>Parsed Intent</TableHead>
                  <TableHead>Result Text</TableHead>
                  <TableHead>Created At</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {history.length === 0 && (
                  <TableRow>
                    <TableCell colSpan={4} className="text-center text-muted-foreground">
                      No history yet.
                    </TableCell>
                  </TableRow>
                )}
                {history.map((item) => (
                  <TableRow key={item.id}>
                    <TableCell className="max-w-xs truncate">{item.transcript}</TableCell>
                    <TableCell>
                      <code className="text-xs bg-muted px-1 py-0.5 rounded">
                        {JSON.stringify(item.parsed_intent)}
                      </code>
                    </TableCell>
                    <TableCell className="max-w-xs truncate">{item.result_text}</TableCell>
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
