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

interface DescriptionResult {
  id: string;
  generated_text: string;
  product_id?: string;
}

interface DescriptionHistoryItem {
  id: string;
  product_id?: string;
  generated_text: string;
  accepted: boolean;
  created_at: string;
}

export default function ProductDescriptionsPage() {
  const [productId, setProductId] = useState("");
  const [name, setName] = useState("");
  const [category, setCategory] = useState("");
  const [features, setFeatures] = useState("");
  const [tone, setTone] = useState("professional");
  const [generated, setGenerated] = useState<DescriptionResult | null>(null);
  const [history, setHistory] = useState<DescriptionHistoryItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [error, setError] = useState("");

  async function fetchHistory() {
    setHistoryLoading(true);
    try {
      setHistory(await api.get<DescriptionHistoryItem[]>("/api/ai/product-descriptions"));
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
    setGenerated(null);
    try {
      setGenerated(await api.post<DescriptionResult>("/api/ai/product-descriptions/generate", {
        product_id: productId || undefined,
        name,
        category,
        features: features.split(",").map((f) => f.trim()).filter(Boolean),
        tone,
      }));
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Generation failed");
    } finally {
      setLoading(false);
    }
  }

  async function handleAccept() {
    if (!generated) return;
    try {
      await api.post(`/api/ai/product-descriptions/${generated.id}/accept`, { apply_to_product: !!generated.product_id });
      setGenerated(null);
      await fetchHistory();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Accept failed");
    }
  }

  async function handleReject() {
    if (!generated) return;
    try {
      await api.post(`/api/ai/product-descriptions/${generated.id}/reject`, {});
    } catch {
      // ignore
    } finally {
      setGenerated(null);
    }
  }

  return (
    <div className="p-6 space-y-6">
      <h1 className="text-2xl font-bold">AI Product Descriptions</h1>

      <Card>
        <CardHeader>
          <CardTitle>Generate Description</CardTitle>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleGenerate} className="space-y-3">
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <Input
                placeholder="Product ID (optional UUID)"
                value={productId}
                onChange={(e) => setProductId(e.target.value)}
              />
              <Input
                placeholder="Product name"
                value={name}
                onChange={(e) => setName(e.target.value)}
                required
              />
              <Input
                placeholder="Category"
                value={category}
                onChange={(e) => setCategory(e.target.value)}
                required
              />
              <select
                className="border rounded px-3 py-2 text-sm bg-background"
                value={tone}
                onChange={(e) => setTone(e.target.value)}
              >
                <option value="professional">Professional</option>
                <option value="friendly">Friendly</option>
                <option value="casual">Casual</option>
                <option value="technical">Technical</option>
              </select>
            </div>
            <textarea
              className="w-full border rounded px-3 py-2 text-sm bg-background min-h-[80px] resize-y"
              placeholder="Features (comma-separated, e.g. waterproof, lightweight, foldable)"
              value={features}
              onChange={(e) => setFeatures(e.target.value)}
            />
            {error && <p className="text-red-500 text-sm">{error}</p>}
            <Button type="submit" disabled={loading}>
              {loading ? "Generating…" : "Generate"}
            </Button>
          </form>
        </CardContent>
      </Card>

      {generated && (
        <Card className="border-2 border-blue-200">
          <CardHeader>
            <CardTitle>Generated Description</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <p className="text-sm leading-relaxed">{generated.generated_text}</p>
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
        </CardHeader>
        <CardContent>
          {historyLoading ? (
            <p className="text-muted-foreground">Loading…</p>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Product ID</TableHead>
                  <TableHead>Snippet</TableHead>
                  <TableHead>Accepted</TableHead>
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
                    <TableCell className="font-mono text-xs">{item.product_id ?? "—"}</TableCell>
                    <TableCell className="max-w-xs truncate text-sm">
                      {item.generated_text.slice(0, 50)}…
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
