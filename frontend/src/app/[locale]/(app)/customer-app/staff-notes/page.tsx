"use client";
import { useState, useEffect } from "react";
import { useParams } from "next/navigation";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";

const API = process.env.NEXT_PUBLIC_API_URL;

interface StaffNote {
  id: string;
  customer_id: string;
  note_text: string;
  is_visible_to_customer: boolean;
  confirmed_by_customer_at: string | null;
  created_at: string;
}

export default function StaffNotesPage() {
  const { locale } = useParams<{ locale: string }>();
  const [items, setItems] = useState<StaffNote[]>([]);
  const [filterCustomerId, setFilterCustomerId] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [newNoteCustomerId, setNewNoteCustomerId] = useState("");
  const [newNoteText, setNewNoteText] = useState("");
  const [newNoteVisible, setNewNoteVisible] = useState(false);
  const [posting, setPosting] = useState(false);

  const token = typeof window !== "undefined" ? localStorage.getItem("auth_token") : "";

  async function fetchItems() {
    setLoading(true);
    setError("");
    try {
      const params = new URLSearchParams();
      if (filterCustomerId) params.set("customer_id", filterCustomerId);
      const res = await fetch(`${API}/api/staff-notes?${params}`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (res.status === 401) { setError("Unauthorized."); return; }
      if (!res.ok) { setError("Failed to load notes."); return; }
      setItems(await res.json());
    } catch {
      setError("Network error.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { fetchItems(); }, []);

  async function postNote() {
    if (!newNoteText.trim() || !newNoteCustomerId.trim()) return;
    setPosting(true);
    setError("");
    try {
      const res = await fetch(`${API}/api/staff-notes`, {
        method: "POST",
        headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
        body: JSON.stringify({
          customer_id: newNoteCustomerId,
          note_text: newNoteText,
          is_visible_to_customer: newNoteVisible,
        }),
      });
      if (res.status === 401) { setError("Unauthorized."); return; }
      if (!res.ok) { setError("Failed to post note."); return; }
      setNewNoteText("");
      setNewNoteVisible(false);
      fetchItems();
    } catch {
      setError("Network error.");
    } finally {
      setPosting(false);
    }
  }

  async function deleteNote(id: string) {
    setError("");
    try {
      const res = await fetch(`${API}/api/staff-notes/${id}`, {
        method: "DELETE",
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) { setError("Delete failed."); return; }
      setItems(items.filter((i) => i.id !== id));
    } catch {
      setError("Network error.");
    }
  }

  return (
    <div className="p-6 space-y-6">
      <h1 className="text-2xl font-bold">Staff Notes</h1>
      <p className="text-muted-foreground">Internal staff notes about customers (some visible to customer).</p>

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

      <div className="grid gap-4">
        {items.map((note) => (
          <Card key={note.id}>
            <CardContent className="pt-4 space-y-2">
              <div className="flex items-start justify-between gap-4">
                <div className="space-y-1 flex-1">
                  <div className="flex items-center gap-2">
                    <span className="text-xs text-muted-foreground font-mono">{note.customer_id}</span>
                    <Badge variant={note.is_visible_to_customer ? "default" : "secondary"}>
                      {note.is_visible_to_customer ? "Visible" : "Internal"}
                    </Badge>
                    {note.confirmed_by_customer_at && (
                      <Badge variant="outline">Confirmed {note.confirmed_by_customer_at}</Badge>
                    )}
                  </div>
                  <p className="text-sm">{note.note_text}</p>
                  <p className="text-xs text-muted-foreground">{note.created_at}</p>
                </div>
                <Button size="sm" variant="destructive" onClick={() => deleteNote(note.id)}>
                  Delete
                </Button>
              </div>
            </CardContent>
          </Card>
        ))}
        {items.length === 0 && !loading && (
          <p className="text-muted-foreground text-sm">No notes found.</p>
        )}
      </div>

      <Card>
        <CardHeader><CardTitle>Add Note</CardTitle></CardHeader>
        <CardContent className="space-y-3">
          <Input
            placeholder="Customer ID"
            value={newNoteCustomerId}
            onChange={(e) => setNewNoteCustomerId(e.target.value)}
          />
          <textarea
            className="w-full border rounded px-3 py-2 text-sm bg-background min-h-[100px]"
            placeholder="Note text..."
            value={newNoteText}
            onChange={(e) => setNewNoteText(e.target.value)}
          />
          <label className="flex items-center gap-2 text-sm">
            <input
              type="checkbox"
              checked={newNoteVisible}
              onChange={(e) => setNewNoteVisible(e.target.checked)}
            />
            Visible to customer
          </label>
          <Button onClick={postNote} disabled={posting}>
            {posting ? "Posting..." : "Post Note"}
          </Button>
        </CardContent>
      </Card>
    </div>
  );
}
