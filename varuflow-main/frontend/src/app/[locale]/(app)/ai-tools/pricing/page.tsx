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

interface PriceSuggestion {
  id: string;
  suggested_price: number;
  reasoning: string;
}

interface PriceHistoryItem {
  id: string;
  product_id?: string;
  cost_price: number;
  suggested_price: number;
  reasoning: string;
  accepted: boolean;
  accepted_price?: number;
  created_at: string;
}

export default function PricingPage() {
  const params = useParams();

  const [productId, setProductId] = useState("");
  const [productName, setProductName] = useState("");
  const [category, setCategory] = useState("");
  const [costPrice, setCostPrice] = useState("");
  const [targetMargin, setTargetMargin] = useState("");
  const [currentPrice, setCurrentPrice] = useState("");
  const [suggestion, setSuggestion] = useState<PriceSuggestion | null>(null);
  const [acceptedPrice, setAcceptedPrice] = useState("");
  const [history, setHistory] = useState<PriceHistoryItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [error, setError] = useState("");

  async function fetchHistory() {
    setHistoryLoading(true);
    try {
      const res = await fetch(`${API}/api/ai/pricing`, {
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

  async function handleSuggest(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError("");
    setSuggestion(null);
    try {
      const res = await fetch(`${API}/api/ai/pricing/suggest`, {
        method: "POST",
        headers: {
          Authorization: `Bearer ${getToken()}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          product_id: productId || undefined,
          product_name: productName,
          category,
          cost_price: parseFloat(costPrice),
          target_margin_pct: targetMargin ? parseFloat(targetMargin) : undefined,
          current_price: currentPrice ? parseFloat(currentPrice) : undefined,
        }),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      setSuggestion(await res.json());
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Suggestion failed");
    } finally {
      setLoading(false);
    }
  }

  async function handleAccept() {
    if (!suggestion) return;
    try {
      const res = await fetch(`${API}/api/ai/pricing/${suggestion.id}/accept`, {
        method: "POST",
        headers: {
          Authorization: `Bearer ${getToken()}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          accepted_price: acceptedPrice ? parseFloat(acceptedPrice) : suggestion.suggested_price,
        }),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      setSuggestion(null);
      setAcceptedPrice("");
      await fetchHistory();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Accept failed");
    }
  }

  async function handleReject() {
    if (!suggestion) return;
    try {
      await fetch(`${API}/api/ai/pricing/${suggestion.id}/reject`, {
        method: "POST",
        headers: { Authorization: `Bearer ${getToken()}` },
      });
    } catch {
      // ignore
    } finally {
      setSuggestion(null);
    }
  }

  return (
    <div className="p-6 space-y-6">
      <h1 className="text-2xl font-bold">AI Price Suggestions</h1>

      <Card>
        <CardHeader>
          <CardTitle>Get Price Suggestion</CardTitle>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSuggest} className="space-y-3">
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
              <Input
                placeholder="Product ID (optional)"
                value={productId}
                onChange={(e) => setProductId(e.target.value)}
              />
              <Input
                placeholder="Product name"
                value={productName}
                onChange={(e) => setProductName(e.target.value)}
                required
              />
              <Input
                placeholder="Category"
                value={category}
                onChange={(e) => setCategory(e.target.value)}
                required
              />
              <Input
                type="number"
                step="0.01"
                placeholder="Cost price"
                value={costPrice}
                onChange={(e) => setCostPrice(e.target.value)}
                required
              />
              <Input
                type="number"
                step="0.1"
                placeholder="Target margin % (optional)"
                value={targetMargin}
                onChange={(e) => setTargetMargin(e.target.value)}
              />
              <Input
                type="number"
                step="0.01"
                placeholder="Current price (optional)"
                value={currentPrice}
                onChange={(e) => setCurrentPrice(e.target.value)}
              />
            </div>
            {error && <p className="text-red-500 text-sm">{error}</p>}
            <Button type="submit" disabled={loading}>
              {loading ? "Calculating…" : "Get Price Suggestion"}
            </Button>
          </form>
        </CardContent>
      </Card>

      {suggestion && (
        <Card className="border-2 border-blue-200">
          <CardHeader>
            <CardTitle>Suggested Price</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <p className="text-4xl font-bold">
              {suggestion.suggested_price.toLocaleString("sv-SE", {
                style: "currency",
                currency: "SEK",
              })}
            </p>
            <p className="text-sm text-muted-foreground">{suggestion.reasoning}</p>
            <div className="flex items-center gap-3 flex-wrap">
              <Input
                type="number"
                step="0.01"
                placeholder={`Override price (default: ${suggestion.suggested_price})`}
                value={acceptedPrice}
                onChange={(e) => setAcceptedPrice(e.target.value)}
                className="max-w-xs"
              />
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
                  <TableHead>Cost Price</TableHead>
                  <TableHead>Suggested Price</TableHead>
                  <TableHead>Reasoning</TableHead>
                  <TableHead>Accepted</TableHead>
                  <TableHead>Accepted Price</TableHead>
                  <TableHead>Created At</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {history.length === 0 && (
                  <TableRow>
                    <TableCell colSpan={7} className="text-center text-muted-foreground">
                      No history yet.
                    </TableCell>
                  </TableRow>
                )}
                {history.map((item) => (
                  <TableRow key={item.id}>
                    <TableCell className="font-mono text-xs">{item.product_id ?? "—"}</TableCell>
                    <TableCell>{item.cost_price}</TableCell>
                    <TableCell className="font-medium">{item.suggested_price}</TableCell>
                    <TableCell className="max-w-xs truncate text-xs" title={item.reasoning}>
                      {item.reasoning.slice(0, 60)}…
                    </TableCell>
                    <TableCell>
                      <Badge variant={item.accepted ? "default" : "outline"}>
                        {item.accepted ? "Yes" : "No"}
                      </Badge>
                    </TableCell>
                    <TableCell>{item.accepted_price ?? "—"}</TableCell>
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
