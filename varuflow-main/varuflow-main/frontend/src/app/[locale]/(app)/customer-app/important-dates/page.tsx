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

interface ImportantDate {
  id: string;
  customer_id: string;
  label: string;
  date: string;
  send_greeting: boolean;
  send_discount: boolean;
  discount_pct: number | null;
  last_triggered: string | null;
}

export default function ImportantDatesPage() {
  const { locale } = useParams<{ locale: string }>();
  const [items, setItems] = useState<ImportantDate[]>([]);
  const [filterCustomerId, setFilterCustomerId] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [newForm, setNewForm] = useState({
    customer_id: "", label: "birthday", date: "",
    send_greeting: false, send_discount: false, discount_pct: "",
  });
  const [creating, setCreating] = useState(false);

  const token = typeof window !== "undefined" ? localStorage.getItem("auth_token") : "";

  async function fetchItems() {
    setLoading(true);
    setError("");
    try {
      const params = new URLSearchParams({ upcoming_days: "30" });
      if (filterCustomerId) params.set("customer_id", filterCustomerId);
      const res = await fetch(`${API}/api/important-dates?${params}`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (res.status === 401) { setError("Unauthorized."); return; }
      if (!res.ok) { setError("Failed to load dates."); return; }
      setItems(await res.json());
    } catch {
      setError("Network error.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { fetchItems(); }, []);

  async function deleteItem(id: string) {
    try {
      const res = await fetch(`${API}/api/important-dates/${id}`, {
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
      const body: Record<string, unknown> = {
        customer_id: newForm.customer_id,
        label: newForm.label,
        date: newForm.date,
        send_greeting: newForm.send_greeting,
        send_discount: newForm.send_discount,
      };
      if (newForm.discount_pct) body.discount_pct = parseFloat(newForm.discount_pct);
      const res = await fetch(`${API}/api/important-dates`, {
        method: "POST",
        headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      if (res.status === 401) { setError("Unauthorized."); return; }
      if (!res.ok) { setError("Failed to create date."); return; }
      setNewForm({ customer_id: "", label: "birthday", date: "", send_greeting: false, send_discount: false, discount_pct: "" });
      fetchItems();
    } catch {
      setError("Network error.");
    } finally {
      setCreating(false);
    }
  }

  return (
    <div className="p-6 space-y-6">
      <h1 className="text-2xl font-bold">Important Dates</h1>
      <p className="text-muted-foreground">Manage customer birthdays, anniversaries, and other key dates.</p>

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
        <CardHeader><CardTitle>Dates ({items.length})</CardTitle></CardHeader>
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Customer ID</TableHead>
                <TableHead>Label</TableHead>
                <TableHead>Date</TableHead>
                <TableHead>Greeting</TableHead>
                <TableHead>Discount</TableHead>
                <TableHead>Discount %</TableHead>
                <TableHead>Last Triggered</TableHead>
                <TableHead>Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {items.map((item) => (
                <TableRow key={item.id}>
                  <TableCell className="font-mono text-xs">{item.customer_id}</TableCell>
                  <TableCell className="capitalize">{item.label}</TableCell>
                  <TableCell>{item.date}</TableCell>
                  <TableCell>{item.send_greeting ? "Yes" : "No"}</TableCell>
                  <TableCell>{item.send_discount ? "Yes" : "No"}</TableCell>
                  <TableCell>{item.discount_pct ?? "—"}</TableCell>
                  <TableCell>{item.last_triggered ?? "—"}</TableCell>
                  <TableCell>
                    <Button size="sm" variant="destructive" onClick={() => deleteItem(item.id)}>Delete</Button>
                  </TableCell>
                </TableRow>
              ))}
              {items.length === 0 && !loading && (
                <TableRow>
                  <TableCell colSpan={8} className="text-center text-muted-foreground">No dates found.</TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>
        </CardContent>
      </Card>

      <Card>
        <CardHeader><CardTitle>Add Date</CardTitle></CardHeader>
        <CardContent className="space-y-3">
          <Input placeholder="Customer ID" value={newForm.customer_id} onChange={(e) => setNewForm({ ...newForm, customer_id: e.target.value })} />
          <select
            className="w-full border rounded px-3 py-2 text-sm bg-background"
            value={newForm.label}
            onChange={(e) => setNewForm({ ...newForm, label: e.target.value })}
          >
            <option value="birthday">Birthday</option>
            <option value="anniversary">Anniversary</option>
            <option value="other">Other</option>
          </select>
          <Input type="date" value={newForm.date} onChange={(e) => setNewForm({ ...newForm, date: e.target.value })} />
          <div className="flex gap-4">
            <label className="flex items-center gap-2 text-sm">
              <input type="checkbox" checked={newForm.send_greeting} onChange={(e) => setNewForm({ ...newForm, send_greeting: e.target.checked })} />
              Send Greeting
            </label>
            <label className="flex items-center gap-2 text-sm">
              <input type="checkbox" checked={newForm.send_discount} onChange={(e) => setNewForm({ ...newForm, send_discount: e.target.checked })} />
              Send Discount
            </label>
          </div>
          {newForm.send_discount && (
            <Input type="number" placeholder="Discount %" value={newForm.discount_pct} onChange={(e) => setNewForm({ ...newForm, discount_pct: e.target.value })} />
          )}
          <Button onClick={createItem} disabled={creating}>
            {creating ? "Adding..." : "Add Date"}
          </Button>
        </CardContent>
      </Card>
    </div>
  );
}
