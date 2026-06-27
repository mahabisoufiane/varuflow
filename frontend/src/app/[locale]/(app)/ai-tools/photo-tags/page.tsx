"use client";
import { useState, useEffect } from "react";
import { useParams } from "next/navigation";
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

const API = process.env.NEXT_PUBLIC_API_URL;
function getToken() {
  return typeof window !== "undefined" ? localStorage.getItem("auth_token") ?? "" : "";
}

interface PhotoTag {
  tag: string;
  category: string;
  confidence: number;
}

interface TagResult {
  id: string;
  tags: PhotoTag[];
  product_id?: string;
}

interface TagHistoryItem {
  id: string;
  product_id?: string;
  photo_url: string;
  tags: PhotoTag[];
  created_at: string;
}

export default function PhotoTagsPage() {
  const params = useParams();

  const [photoUrl, setPhotoUrl] = useState("");
  const [productId, setProductId] = useState("");
  const [tagResult, setTagResult] = useState<TagResult | null>(null);
  const [productIdFilter, setProductIdFilter] = useState("");
  const [history, setHistory] = useState<TagHistoryItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [error, setError] = useState("");

  async function fetchHistory(filter?: string) {
    setHistoryLoading(true);
    try {
      const query = filter ? `?product_id=${encodeURIComponent(filter)}` : "";
      const res = await fetch(`${API}/api/ai/photo-tags${query}`, {
        headers: { Authorization: `Bearer ${getToken()}` },
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      setHistory(await res.json());
    } catch {
      // non-critical
    } finally {
      setHistoryLoading(false);
    }
  }

  useEffect(() => {
    fetchHistory();
  }, []);

  async function handleAnalyze(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError("");
    setTagResult(null);
    try {
      const res = await fetch(`${API}/api/ai/photo-tags/analyze`, {
        method: "POST",
        headers: {
          Authorization: `Bearer ${getToken()}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          photo_url: photoUrl,
          product_id: productId || undefined,
        }),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      setTagResult(await res.json());
      await fetchHistory();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Analysis failed");
    } finally {
      setLoading(false);
    }
  }

  async function deleteTagEntry(id: string) {
    try {
      const res = await fetch(`${API}/api/ai/photo-tags/${id}`, {
        method: "DELETE",
        headers: { Authorization: `Bearer ${getToken()}` },
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      await fetchHistory(productIdFilter || undefined);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Delete failed");
    }
  }

  return (
    <div className="p-6 space-y-6">
      <h1 className="text-2xl font-bold">AI Photo Tagging</h1>

      <Card>
        <CardHeader>
          <CardTitle>Analyze Photo</CardTitle>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleAnalyze} className="space-y-3">
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <Input
                type="url"
                placeholder="Photo URL"
                value={photoUrl}
                onChange={(e) => setPhotoUrl(e.target.value)}
                required
              />
              <Input
                placeholder="Product ID (optional)"
                value={productId}
                onChange={(e) => setProductId(e.target.value)}
              />
            </div>
            {error && <p className="text-red-500 text-sm">{error}</p>}
            <Button type="submit" disabled={loading}>
              {loading ? "Analyzing…" : "Analyze Photo"}
            </Button>
          </form>
        </CardContent>
      </Card>

      {tagResult && tagResult.tags.length > 0 && (
        <Card className="border-2 border-blue-200">
          <CardHeader>
            <CardTitle>Detected Tags</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex flex-wrap gap-2">
              {tagResult.tags.map((t, i) => (
                <Badge key={i} variant="secondary" className="text-xs py-1">
                  {t.tag} ({t.category}) {Math.round(t.confidence * 100)}%
                </Badge>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      <Card>
        <CardHeader>
          <CardTitle>History</CardTitle>
          <div className="flex gap-2 mt-2">
            <Input
              placeholder="Filter by product ID"
              value={productIdFilter}
              onChange={(e) => setProductIdFilter(e.target.value)}
              className="max-w-xs"
            />
            <Button variant="outline" onClick={() => fetchHistory(productIdFilter || undefined)}>
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
                  <TableHead>Product ID</TableHead>
                  <TableHead>Photo URL</TableHead>
                  <TableHead>Tags Count</TableHead>
                  <TableHead>Created At</TableHead>
                  <TableHead>Actions</TableHead>
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
                    <TableCell className="font-mono text-xs">{item.product_id ?? "—"}</TableCell>
                    <TableCell className="max-w-xs truncate text-xs">
                      <a
                        href={item.photo_url}
                        target="_blank"
                        rel="noreferrer"
                        className="underline text-blue-600"
                      >
                        {item.photo_url}
                      </a>
                    </TableCell>
                    <TableCell>{item.tags?.length ?? 0}</TableCell>
                    <TableCell className="whitespace-nowrap text-xs">
                      {new Date(item.created_at).toLocaleString()}
                    </TableCell>
                    <TableCell>
                      <Button
                        variant="destructive"
                        size="sm"
                        onClick={() => deleteTagEntry(item.id)}
                      >
                        Delete
                      </Button>
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
