"use client";
import { useState, useEffect } from "react";
import { useParams, useRouter } from "next/navigation";
import { api } from "@/lib/api-client";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import styles from "./page.module.scss";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";

function sentimentClass(s: string): keyof typeof styles {
  const map: Record<string, keyof typeof styles> = {
    positive: "sentimentPositive",
    neutral:  "sentimentNeutral",
    negative: "sentimentNegative",
  };
  return map[s] ?? "sentimentNeutral";
}

interface SentimentResult {
  sentiment: string;
  confidence: number;
  flagged: boolean;
}

interface FlaggedThread {
  thread_id: string;
  customer_id: string;
  sentiment: string;
  flagged: boolean;
  channel: string;
  last_message_at: string;
}

export default function SentimentPage() {
  const params = useParams();
  const router = useRouter();
  const locale = params.locale as string;

  const [analyzeId, setAnalyzeId] = useState("");
  const [result, setResult] = useState<SentimentResult | null>(null);
  const [analyzeLoading, setAnalyzeLoading] = useState(false);
  const [analyzeError, setAnalyzeError] = useState("");

  const [flagged, setFlagged] = useState<FlaggedThread[]>([]);
  const [flaggedLoading, setFlaggedLoading] = useState(false);
  const [flaggedError, setFlaggedError] = useState("");

  async function handleAnalyze(e: React.FormEvent) {
    e.preventDefault();
    setAnalyzeLoading(true);
    setAnalyzeError("");
    setResult(null);
    try {
      const data = await api.post<SentimentResult>("/api/inbox/sentiment/analyze", {
        message_id: analyzeId,
      });
      setResult(data);
    } catch (e: unknown) {
      setAnalyzeError(e instanceof Error ? e.message : "Analysis failed");
    } finally {
      setAnalyzeLoading(false);
    }
  }

  async function fetchFlagged() {
    setFlaggedLoading(true);
    setFlaggedError("");
    try {
      const data = await api.get<FlaggedThread[]>("/api/inbox/sentiment/flagged");
      setFlagged(data);
    } catch (e: unknown) {
      setFlaggedError(e instanceof Error ? e.message : "Failed to load flagged threads");
    } finally {
      setFlaggedLoading(false);
    }
  }

  useEffect(() => {
    fetchFlagged();
  }, []);

  return (
    <div className="p-6 space-y-6">
      <h1 className="text-2xl font-bold">Sentiment Analysis</h1>

      {/* Analyze section */}
      <Card>
        <CardHeader>
          <CardTitle>Analyze Message</CardTitle>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleAnalyze} className="flex gap-3 items-end">
            <div className="space-y-1 flex-1 min-w-48">
              <label className="text-sm font-medium">Message ID (UUID) *</label>
              <Input
                required
                value={analyzeId}
                onChange={(e) => setAnalyzeId(e.target.value)}
                placeholder="message UUID"
              />
            </div>
            <Button type="submit" disabled={analyzeLoading}>
              {analyzeLoading ? "Analyzing…" : "Analyze"}
            </Button>
          </form>
          {analyzeError && <p className="text-red-500 text-sm mt-2">{analyzeError}</p>}
          {result && (
            <Card className="mt-4 bg-muted/30">
              <CardContent className="pt-4">
                <div className="flex flex-wrap items-center gap-3">
                  <span
                    className={styles[sentimentClass(result.sentiment)]}
                  >
                    {result.sentiment}
                  </span>
                  <span className="text-sm text-muted-foreground">
                    Confidence: {(result.confidence * 100).toFixed(1)}%
                  </span>
                  {result.flagged && (
                    <Badge variant="destructive">Flagged</Badge>
                  )}
                </div>
              </CardContent>
            </Card>
          )}
        </CardContent>
      </Card>

      {/* Flagged conversations */}
      <section className="space-y-3">
        <h2 className="text-xl font-semibold">Flagged Conversations</h2>
        {flaggedError && <p className="text-red-500 text-sm">{flaggedError}</p>}
        {flaggedLoading ? (
          <p className="text-muted-foreground">Loading...</p>
        ) : (
          <Card>
            <CardContent className="p-0">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Thread ID</TableHead>
                    <TableHead>Customer ID</TableHead>
                    <TableHead>Sentiment</TableHead>
                    <TableHead>Flagged</TableHead>
                    <TableHead>Channel</TableHead>
                    <TableHead>Last Message At</TableHead>
                    <TableHead>Actions</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {flagged.length === 0 && (
                    <TableRow>
                      <TableCell colSpan={7} className="text-center text-muted-foreground">
                        No flagged conversations.
                      </TableCell>
                    </TableRow>
                  )}
                  {flagged.map((f) => (
                    <TableRow key={f.thread_id}>
                      <TableCell className="font-mono text-xs">
                        {f.thread_id.slice(0, 8)}…
                      </TableCell>
                      <TableCell className="font-mono text-xs">{f.customer_id}</TableCell>
                      <TableCell>
                        <span
                          className={styles[sentimentClass(f.sentiment)]}
                        >
                          {f.sentiment}
                        </span>
                      </TableCell>
                      <TableCell>
                        <Badge variant={f.flagged ? "destructive" : "secondary"}>
                          {f.flagged ? "Yes" : "No"}
                        </Badge>
                      </TableCell>
                      <TableCell className="text-xs">{f.channel}</TableCell>
                      <TableCell className="text-xs">
                        {new Date(f.last_message_at).toLocaleString()}
                      </TableCell>
                      <TableCell>
                        <Button
                          size="sm"
                          variant="outline"
                          onClick={() => router.push(`/${locale}/inbox`)}
                        >
                          View Thread
                        </Button>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </CardContent>
          </Card>
        )}
      </section>
    </div>
  );
}
