"use client";
import { useState } from "react";
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

const API = process.env.NEXT_PUBLIC_API_URL;
function getToken() {
  return typeof window !== "undefined" ? localStorage.getItem("auth_token") ?? "" : "";
}

interface TranslationResult {
  id?: string;
  source_lang?: string;
  target_lang: string;
  translated_body: string;
  translated_by?: string;
  created_at?: string;
}

export default function TranslationPage() {
  const [messageId, setMessageId] = useState("");
  const [targetLang, setTargetLang] = useState("en");
  const [translation, setTranslation] = useState<TranslationResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const [lookupId, setLookupId] = useState("");
  const [history, setHistory] = useState<TranslationResult[]>([]);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [historyError, setHistoryError] = useState("");

  async function handleTranslate(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError("");
    setTranslation(null);
    try {
      const res = await fetch(`${API}/api/inbox/translate`, {
        method: "POST",
        headers: {
          Authorization: `Bearer ${getToken()}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ message_id: messageId, target_language: targetLang }),
      });
      if (!res.ok) throw new Error(`Error ${res.status}`);
      setTranslation(await res.json());
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Translation failed");
    } finally {
      setLoading(false);
    }
  }

  async function handleLookup(e: React.FormEvent) {
    e.preventDefault();
    setHistoryLoading(true);
    setHistoryError("");
    setHistory([]);
    try {
      const res = await fetch(`${API}/api/inbox/translate/${lookupId}`, {
        headers: { Authorization: `Bearer ${getToken()}` },
      });
      if (!res.ok) throw new Error(`Error ${res.status}`);
      const data = await res.json();
      setHistory(Array.isArray(data) ? data : [data]);
    } catch (e: unknown) {
      setHistoryError(e instanceof Error ? e.message : "Lookup failed");
    } finally {
      setHistoryLoading(false);
    }
  }

  return (
    <div className="p-6 space-y-6">
      <h1 className="text-2xl font-bold">Auto-Translation</h1>

      <div className="rounded-md border border-blue-200 bg-blue-50 px-4 py-3 text-sm text-blue-800">
        Translations are AI-generated (GPT-4o). Review before sending.
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Translate Message</CardTitle>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleTranslate} className="flex flex-wrap gap-4 items-end">
            <div className="space-y-1 flex-1 min-w-48">
              <label className="text-sm font-medium">Message ID (UUID) *</label>
              <Input
                required
                value={messageId}
                onChange={(e) => setMessageId(e.target.value)}
                placeholder="message UUID"
              />
            </div>
            <div className="space-y-1">
              <label className="text-sm font-medium">Target Language *</label>
              <select
                required
                value={targetLang}
                onChange={(e) => setTargetLang(e.target.value)}
                className="border rounded-md px-3 py-2 text-sm bg-background"
              >
                <option value="en">English</option>
                <option value="sv">Swedish</option>
                <option value="no">Norwegian</option>
                <option value="da">Danish</option>
                <option value="ar">Arabic</option>
              </select>
            </div>
            <Button type="submit" disabled={loading}>
              {loading ? "Translating…" : "Translate"}
            </Button>
          </form>
          {error && <p className="text-red-500 text-sm mt-2">{error}</p>}
          {translation && (
            <Card className="mt-4 bg-muted/30">
              <CardContent className="pt-4">
                <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide mb-1">
                  Translated ({translation.target_lang})
                </p>
                <p className="text-sm whitespace-pre-wrap">{translation.translated_body}</p>
              </CardContent>
            </Card>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Translation History</CardTitle>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleLookup} className="flex gap-3 items-end mb-4">
            <div className="space-y-1 flex-1 min-w-48">
              <label className="text-sm font-medium">Message ID</label>
              <Input
                required
                value={lookupId}
                onChange={(e) => setLookupId(e.target.value)}
                placeholder="message UUID"
              />
            </div>
            <Button type="submit" disabled={historyLoading}>
              {historyLoading ? "Loading…" : "Look Up"}
            </Button>
          </form>
          {historyError && <p className="text-red-500 text-sm">{historyError}</p>}
          {history.length > 0 && (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Source Lang</TableHead>
                  <TableHead>Target Lang</TableHead>
                  <TableHead>Translated Body</TableHead>
                  <TableHead>Translated By</TableHead>
                  <TableHead>Created At</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {history.map((h, i) => (
                  <TableRow key={h.id ?? i}>
                    <TableCell>{h.source_lang ?? "—"}</TableCell>
                    <TableCell>{h.target_lang}</TableCell>
                    <TableCell className="max-w-xs truncate text-xs" title={h.translated_body}>
                      {h.translated_body}
                    </TableCell>
                    <TableCell className="text-xs">{h.translated_by ?? "—"}</TableCell>
                    <TableCell className="text-xs">
                      {h.created_at ? new Date(h.created_at).toLocaleString() : "—"}
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
