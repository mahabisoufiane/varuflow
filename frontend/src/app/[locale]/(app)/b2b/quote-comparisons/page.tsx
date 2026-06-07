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
import { api } from "@/lib/api-client";

interface QuoteComparison {
  id: string;
  title: string;
  customer_id?: string;
  quote_ids: string[];
  notes?: string;
  created_at: string;
}

function truncate(str: string, len = 10) {
  return str.length > len ? str.slice(0, len) + "…" : str;
}

export default function QuoteComparisonsPage() {
  const [customerFilter, setCustomerFilter] = useState("");
  const [items, setItems] = useState<QuoteComparison[]>([]);
  const [listLoading, setListLoading] = useState(false);
  const [listError, setListError] = useState("");

  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [detail, setDetail] = useState<QuoteComparison | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [detailError, setDetailError] = useState("");

  // New comparison form
  const [newTitle, setNewTitle] = useState("");
  const [newCustomerId, setNewCustomerId] = useState("");
  const [newQuoteIds, setNewQuoteIds] = useState("");
  const [newNotes, setNewNotes] = useState("");
  const [createLoading, setCreateLoading] = useState(false);
  const [createError, setCreateError] = useState("");

  // Edit form (shown when detail is loaded)
  const [editQuoteIds, setEditQuoteIds] = useState("");
  const [editNotes, setEditNotes] = useState("");
  const [editLoading, setEditLoading] = useState(false);
  const [editError, setEditError] = useState("");

  async function loadList() {
    setListLoading(true);
    setListError("");
    try {
      const params = new URLSearchParams();
      if (customerFilter.trim()) params.set("customer_id", customerFilter.trim());
      const data = await api.get<QuoteComparison[]>(`/api/quote-comparisons?${params}`);
      setItems(data);
    } catch (e: unknown) {
      setListError(e instanceof Error ? e.message : "Failed to load comparisons");
    } finally {
      setListLoading(false);
    }
  }

  async function loadDetail(id: string) {
    setSelectedId(id);
    setDetail(null);
    setDetailLoading(true);
    setDetailError("");
    setEditError("");
    try {
      const data = await api.get<QuoteComparison>(`/api/quote-comparisons/${id}`);
      setDetail(data);
      setEditQuoteIds(data.quote_ids.join(", "));
      setEditNotes(data.notes ?? "");
    } catch (e: unknown) {
      setDetailError(e instanceof Error ? e.message : "Failed to load detail");
    } finally {
      setDetailLoading(false);
    }
  }

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    setCreateLoading(true);
    setCreateError("");
    try {
      const quoteIds = newQuoteIds
        .split(",")
        .map((s) => s.trim())
        .filter(Boolean);
      const body: Record<string, unknown> = {
        title: newTitle,
        quote_ids: quoteIds,
      };
      if (newCustomerId.trim()) body.customer_id = newCustomerId.trim();
      if (newNotes.trim()) body.notes = newNotes.trim();
      await api.post("/api/quote-comparisons", body);
      setNewTitle("");
      setNewCustomerId("");
      setNewQuoteIds("");
      setNewNotes("");
      await loadList();
    } catch (e: unknown) {
      setCreateError(e instanceof Error ? e.message : "Failed to create comparison");
    } finally {
      setCreateLoading(false);
    }
  }

  async function handleEdit(e: React.FormEvent) {
    e.preventDefault();
    if (!selectedId) return;
    setEditLoading(true);
    setEditError("");
    try {
      const quoteIds = editQuoteIds
        .split(",")
        .map((s) => s.trim())
        .filter(Boolean);
      await api.patch(`/api/quote-comparisons/${selectedId}`, {
        quote_ids: quoteIds,
        notes: editNotes || undefined,
      });
      await loadDetail(selectedId);
    } catch (e: unknown) {
      setEditError(e instanceof Error ? e.message : "Failed to update comparison");
    } finally {
      setEditLoading(false);
    }
  }

  async function handleDelete(id: string) {
    setDetailError("");
    try {
      await api.delete(`/api/quote-comparisons/${id}`);
      setSelectedId(null);
      setDetail(null);
      setItems((prev) => prev.filter((item) => item.id !== id));
    } catch (e: unknown) {
      setDetailError(e instanceof Error ? e.message : "Failed to delete comparison");
    }
  }

  return (
    <div className="p-6 space-y-6 max-w-6xl mx-auto">
      <h1 className="text-2xl font-bold">Quote Comparison</h1>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Left panel — list */}
        <div className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Comparisons</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              <div className="flex gap-2">
                <Input
                  placeholder="Filter by customer ID"
                  value={customerFilter}
                  onChange={(e) => setCustomerFilter(e.target.value)}
                />
                <Button onClick={loadList} disabled={listLoading}>
                  {listLoading ? "Loading…" : "Search"}
                </Button>
              </div>
              {listError && (
                <p className="text-red-500 text-sm">{listError}</p>
              )}
              {listLoading ? (
                <p className="text-muted-foreground">Loading...</p>
              ) : items.length === 0 ? (
                <p className="text-muted-foreground text-sm">
                  No comparisons found.
                </p>
              ) : (
                <ul className="space-y-2">
                  {items.map((item) => (
                    <li
                      key={item.id}
                      className={`rounded-md border p-3 cursor-pointer hover:border-primary transition-colors ${selectedId === item.id ? "border-primary bg-accent" : ""}`}
                      onClick={() => loadDetail(item.id)}
                    >
                      <div className="font-medium text-sm">{item.title}</div>
                      <div className="text-xs text-muted-foreground mt-0.5">
                        {item.quote_ids.length} quote
                        {item.quote_ids.length !== 1 ? "s" : ""} ·{" "}
                        {new Date(item.created_at).toLocaleDateString()}
                      </div>
                    </li>
                  ))}
                </ul>
              )}
            </CardContent>
          </Card>

          {/* New comparison form */}
          <Card>
            <CardHeader>
              <CardTitle>New Comparison</CardTitle>
            </CardHeader>
            <CardContent>
              <form onSubmit={handleCreate} className="space-y-3">
                <div>
                  <label className="text-sm font-medium">Title</label>
                  <Input
                    value={newTitle}
                    onChange={(e) => setNewTitle(e.target.value)}
                    placeholder="Q3 Supplier Comparison"
                    required
                  />
                </div>
                <div>
                  <label className="text-sm font-medium">
                    Customer ID (optional)
                  </label>
                  <Input
                    value={newCustomerId}
                    onChange={(e) => setNewCustomerId(e.target.value)}
                    placeholder="UUID"
                  />
                </div>
                <div>
                  <label className="text-sm font-medium">
                    Quote IDs (comma-separated UUIDs)
                  </label>
                  <Input
                    value={newQuoteIds}
                    onChange={(e) => setNewQuoteIds(e.target.value)}
                    placeholder="uuid1, uuid2, uuid3"
                    required
                  />
                </div>
                <div>
                  <label className="text-sm font-medium">Notes (optional)</label>
                  <Input
                    value={newNotes}
                    onChange={(e) => setNewNotes(e.target.value)}
                    placeholder="Additional notes"
                  />
                </div>
                {createError && (
                  <p className="text-red-500 text-sm">{createError}</p>
                )}
                <Button type="submit" disabled={createLoading}>
                  {createLoading ? "Creating…" : "Create Comparison"}
                </Button>
              </form>
            </CardContent>
          </Card>
        </div>

        {/* Right panel — detail */}
        <div>
          {!selectedId && (
            <div className="rounded-md border border-dashed p-8 text-center text-muted-foreground text-sm">
              Select a comparison to view details
            </div>
          )}
          {selectedId && detailLoading && (
            <p className="text-muted-foreground">Loading...</p>
          )}
          {selectedId && detailError && (
            <p className="text-red-500 text-sm">{detailError}</p>
          )}
          {selectedId && detail && (
            <div className="space-y-4">
              <Card>
                <CardHeader>
                  <div className="flex items-start justify-between">
                    <div>
                      <CardTitle>{detail.title}</CardTitle>
                      {detail.notes && (
                        <p className="text-sm text-muted-foreground mt-1">
                          {detail.notes}
                        </p>
                      )}
                    </div>
                    <Button
                      size="sm"
                      variant="destructive"
                      onClick={() => handleDelete(detail.id)}
                    >
                      Delete
                    </Button>
                  </div>
                </CardHeader>
                <CardContent>
                  <h3 className="text-sm font-semibold mb-2">Quotes</h3>
                  {detail.quote_ids.length === 0 ? (
                    <p className="text-muted-foreground text-sm">No quotes.</p>
                  ) : (
                    <Table>
                      <TableHeader>
                        <TableRow>
                          <TableHead>#</TableHead>
                          <TableHead>Quote ID</TableHead>
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        {detail.quote_ids.map((qid, idx) => (
                          <TableRow key={qid}>
                            <TableCell className="text-muted-foreground text-sm">
                              {idx + 1}
                            </TableCell>
                            <TableCell className="font-mono text-xs">
                              {truncate(qid, 20)}
                            </TableCell>
                          </TableRow>
                        ))}
                      </TableBody>
                    </Table>
                  )}
                </CardContent>
              </Card>

              {/* Edit form */}
              <Card>
                <CardHeader>
                  <CardTitle>Edit Comparison</CardTitle>
                </CardHeader>
                <CardContent>
                  <form onSubmit={handleEdit} className="space-y-3">
                    <div>
                      <label className="text-sm font-medium">
                        Quote IDs (comma-separated)
                      </label>
                      <Input
                        value={editQuoteIds}
                        onChange={(e) => setEditQuoteIds(e.target.value)}
                        required
                      />
                    </div>
                    <div>
                      <label className="text-sm font-medium">Notes</label>
                      <Input
                        value={editNotes}
                        onChange={(e) => setEditNotes(e.target.value)}
                        placeholder="Additional notes"
                      />
                    </div>
                    {editError && (
                      <p className="text-red-500 text-sm">{editError}</p>
                    )}
                    <Button type="submit" disabled={editLoading}>
                      {editLoading ? "Saving…" : "Save Changes"}
                    </Button>
                  </form>
                </CardContent>
              </Card>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
