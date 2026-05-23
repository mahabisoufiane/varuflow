"use client";
import { useState, useEffect } from "react";
import { useParams } from "next/navigation";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from "@/components/ui/table";

const API = process.env.NEXT_PUBLIC_API_URL;

interface Recommendation {
  id: string;
  customer_id: string;
  title: string;
  reason: string;
  score: number;
  shown: boolean;
  accepted: boolean | null;
}

export default function RecommendationsPage() {
  const { locale } = useParams<{ locale: string }>();
  const [items, setItems] = useState<Recommendation[]>([]);
  const [filterCustomerId, setFilterCustomerId] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [newForm, setNewForm] = useState({ customer_id: "", title: "", reason: "", score: "0" });
  const [creating, setCreating] = useState(false);

  const token = typeof window !== "undefined" ? localStorage.getItem("auth_token") : "";

  async function fetchItems() {
    setLoading(true);
    setError("");
    try {
      const params = new URLSearchParams({ limit: "50" });
      if (filterCustomerId) params.set("customer_id", filterCustomerId);
      const res = await fetch(`${API}/api/recommendations?${params}`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (res.status === 401) { setError("Unauthorized."); return; }
      if (!res.ok) { setError("Failed to load recommendations."); return; }
      setItems(await res.json());
    } catch {
      setError("Network error.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { fetchItems(); }, []);

  async function postAction(id: string, action: "shown" | "accept" | "reject") {
    try {
      const res = await fetch(`${API}/api/recommendations/${id}/${action}`, {
        method: "POST",
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) { setError(`Action failed: ${action}`); return; }
      fetchItems();
    } catch {
      setError("Network error.");
    }
  }

  async function deleteItem(id: string) {
    try {
      const res = await fetch(`${API}/api/recommendations/${id}`, {
        method: "DELETE",
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) { setError("Delete failed."); return; }
      setItems(items.filter((i) => i.id !== id));
    } catch {
      setError("Network error.");
    }
  }

  async function createItem() {
    setCreating(true);
    setError("");
    try {
      const res = await fetch(`${API}/api/recommendations`, {
        method: "POST",
        headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
        body: JSON.stringify({ ...newForm, score: parseFloat(newForm.score) }),
      });
      if (res.status === 401) { setError("Unauthorized."); return; }
      if (!res.ok) { setError("Failed to create recommendation."); return; }
      setNewForm({ customer_id: "", title: "", reason: "", score: "0" });
      fetchItems();
    } catch {
      setError("Network error.");
    } finally {
      setCreating(false);
    }
  }

  return (
    <div className="p-6 space-y-6">
      <h1 className="text-2xl font-bold">AI Recommendations</h1>
      <p className="text-muted-foreground">Browse and manage AI-generated recommendations for customers.</p>

      <Card>
        <CardHeader><CardTitle>Filter</CardTitle></CardHeader>
        <CardContent>
          <div className="flex gap-2">
            <Input
              placeholder="Customer ID (optional)"
              value={filterCustomerId}
              onChange={(e) => setFilterCustomerId(e.target.value)}
              className="max-w-sm"
            />
            <Button onClick={fetchItems} disabled={loading}>
              {loading ? "Loading..." : "Search"}
            </Button>
          </div>
          {error && <p className="text-red-500 text-sm mt-2">{error}</p>}
        </CardContent>
      </Card>

      {loading && <p className="text-muted-foreground">Loading...</p>}

      <Card>
        <CardHeader><CardTitle>Recommendations ({items.length})</CardTitle></CardHeader>
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Customer ID</TableHead>
                <TableHead>Title</TableHead>
                <TableHead>Reason</TableHead>
                <TableHead>Score</TableHead>
                <TableHead>Shown</TableHead>
                <TableHead>Accepted</TableHead>
                <TableHead>Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {items.map((item) => (
                <TableRow key={item.id}>
                  <TableCell className="font-mono text-xs">{item.customer_id}</TableCell>
                  <TableCell>{item.title}</TableCell>
                  <TableCell>{item.reason}</TableCell>
                  <TableCell>{item.score}</TableCell>
                  <TableCell>{item.shown ? "Yes" : "No"}</TableCell>
                  <TableCell>
                    {item.accepted === null ? "—" : item.accepted ? "Yes" : "No"}
                  </TableCell>
                  <TableCell>
                    <div className="flex gap-1 flex-wrap">
                      {!item.shown && (
                        <Button size="sm" variant="outline" onClick={() => postAction(item.id, "shown")}>
                          Mark Shown
                        </Button>
                      )}
                      {item.accepted === null && (
                        <>
                          <Button size="sm" variant="outline" onClick={() => postAction(item.id, "accept")}>
                            Accept
                          </Button>
                          <Button size="sm" variant="outline" onClick={() => postAction(item.id, "reject")}>
                            Reject
                          </Button>
                        </>
                      )}
                      <Button size="sm" variant="destructive" onClick={() => deleteItem(item.id)}>
                        Delete
                      </Button>
                    </div>
                  </TableCell>
                </TableRow>
              ))}
              {items.length === 0 && !loading && (
                <TableRow>
                  <TableCell colSpan={7} className="text-center text-muted-foreground">No recommendations found.</TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>
        </CardContent>
      </Card>

      <Card>
        <CardHeader><CardTitle>New Recommendation</CardTitle></CardHeader>
        <CardContent className="space-y-3">
          <Input placeholder="Customer ID" value={newForm.customer_id} onChange={(e) => setNewForm({ ...newForm, customer_id: e.target.value })} />
          <Input placeholder="Title" value={newForm.title} onChange={(e) => setNewForm({ ...newForm, title: e.target.value })} />
          <Input placeholder="Reason" value={newForm.reason} onChange={(e) => setNewForm({ ...newForm, reason: e.target.value })} />
          <Input type="number" placeholder="Score (0-1)" value={newForm.score} onChange={(e) => setNewForm({ ...newForm, score: e.target.value })} />
          <Button onClick={createItem} disabled={creating}>
            {creating ? "Creating..." : "Create Recommendation"}
          </Button>
        </CardContent>
      </Card>
    </div>
  );
}
