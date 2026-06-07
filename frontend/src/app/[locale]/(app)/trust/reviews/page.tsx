"use client";
import { useState, useEffect, useRef } from "react";
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
import { api } from "@/lib/api-client";

interface Review {
  id: string;
  customer_id: string;
  booking_id: string | null;
  reviewer_name: string;
  rating: number;
  body: string;
  is_verified: boolean;
  is_published: boolean;
  reply: string | null;
  service_id: string | null;
  created_at: string;
}

interface Summary {
  avg_rating: number;
  breakdown: Record<string, number>;
  total: number;
}

function Stars({ rating }: { rating: number }) {
  return (
    <span title={`${rating}/5`}>
      {"★".repeat(rating)}{"☆".repeat(5 - rating)} {rating}/5
    </span>
  );
}

export default function ReviewsPage() {
  const [reviews, setReviews] = useState<Review[]>([]);
  const [summary, setSummary] = useState<Summary | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const [serviceFilter, setServiceFilter] = useState("");
  const [ratingFilter, setRatingFilter] = useState("");
  const [isVerified, setIsVerified] = useState(false);
  const [isPublished, setIsPublished] = useState(true);

  // Add review form
  const [addOpen, setAddOpen] = useState(false);
  const [addForm, setAddForm] = useState({
    customer_id: "",
    booking_id: "",
    reviewer_name: "",
    rating: "5",
    body: "",
  });
  const [addError, setAddError] = useState("");
  const [addLoading, setAddLoading] = useState(false);

  // Reply modal
  const [replyId, setReplyId] = useState<string | null>(null);
  const [replyText, setReplyText] = useState("");
  const [replyLoading, setReplyLoading] = useState(false);

  async function loadData() {
    setLoading(true);
    setError("");
    try {
      const params = new URLSearchParams({ is_published: String(isPublished), limit: "50" });
      if (serviceFilter) params.set("service_id", serviceFilter);
      if (ratingFilter) params.set("rating", ratingFilter);
      if (isVerified) params.set("is_verified", "true");

      const [rData, sData] = await Promise.all([
        api.get<Review[] | { items?: Review[] }>(`/api/service-reviews?${params}`),
        api.get<Summary>(`/api/service-reviews/summary${serviceFilter ? `?service_id=${serviceFilter}` : ""}`).catch(() => null),
      ]);

      setReviews(Array.isArray(rData) ? rData : rData.items ?? []);
      if (sData) setSummary(sData);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to load reviews");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadData();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function handleAddReview() {
    setAddLoading(true);
    setAddError("");
    try {
      const body: Record<string, unknown> = {
        customer_id: addForm.customer_id,
        reviewer_name: addForm.reviewer_name,
        rating: Number(addForm.rating),
        body: addForm.body,
      };
      if (addForm.booking_id) body.booking_id = addForm.booking_id;

      await api.post<Review>("/api/service-reviews", body);
      setAddOpen(false);
      setAddForm({ customer_id: "", booking_id: "", reviewer_name: "", rating: "5", body: "" });
      loadData();
    } catch (e: unknown) {
      setAddError(e instanceof Error ? e.message : "Failed to add review");
    } finally {
      setAddLoading(false);
    }
  }

  async function handleReply(id: string) {
    setReplyLoading(true);
    try {
      await api.post(`/api/service-reviews/${id}/reply`, { reply: replyText });
      setReplyId(null);
      setReplyText("");
      loadData();
    } catch {
      // silently update error inline
    } finally {
      setReplyLoading(false);
    }
  }

  async function handleTogglePublish(review: Review) {
    try {
      await api.patch<unknown>(`/api/service-reviews/${review.id}/publish`, { is_published: !review.is_published });
      loadData();
    } catch {
      setError("Failed to update publish status");
    }
  }

  async function handleDelete(id: string) {
    if (!confirm("Delete this review?")) return;
    try {
      await api.delete(`/api/service-reviews/${id}`);
      loadData();
    } catch {
      setError("Failed to delete review");
    }
  }

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Verified Reviews</h1>
        <Button onClick={() => setAddOpen(!addOpen)}>Add Review</Button>
      </div>

      {/* Summary */}
      {summary && (
        <Card>
          <CardContent className="pt-4 space-y-2">
            <div className="flex items-center gap-4">
              <span className="text-5xl font-bold">{summary.avg_rating?.toFixed(1)}</span>
              <div className="space-y-1 flex-1">
                <p className="text-sm text-muted-foreground">{summary.total} reviews</p>
                {[5, 4, 3, 2, 1].map((n) => {
                  const count = summary.breakdown?.[String(n)] ?? 0;
                  const pct = summary.total ? Math.round((count / summary.total) * 100) : 0;
                  return (
                    <div key={n} className="flex items-center gap-2 text-sm">
                      <span className="w-4 text-right">{n}</span>
                      <div className="flex-1 h-2 bg-muted rounded-full overflow-hidden">
                        <div className="h-full bg-yellow-400" style={{ width: `${pct}%` }} />
                      </div>
                      <span className="w-8 text-muted-foreground">{count}</span>
                    </div>
                  );
                })}
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Filters */}
      <Card>
        <CardContent className="pt-4 flex flex-wrap gap-3 items-end">
          <div>
            <label className="text-xs text-muted-foreground block mb-1">Service ID</label>
            <Input
              value={serviceFilter}
              onChange={(e) => setServiceFilter(e.target.value)}
              placeholder="UUID"
              className="w-48"
            />
          </div>
          <div>
            <label className="text-xs text-muted-foreground block mb-1">Rating</label>
            <select
              value={ratingFilter}
              onChange={(e) => setRatingFilter(e.target.value)}
              className="h-9 rounded-md border border-input bg-background px-3 py-1 text-sm"
            >
              <option value="">All</option>
              {[1, 2, 3, 4, 5].map((n) => (
                <option key={n} value={n}>{n}</option>
              ))}
            </select>
          </div>
          <label className="flex items-center gap-2 text-sm cursor-pointer">
            <input type="checkbox" checked={isVerified} onChange={(e) => setIsVerified(e.target.checked)} />
            Verified only
          </label>
          <label className="flex items-center gap-2 text-sm cursor-pointer">
            <input type="checkbox" checked={isPublished} onChange={(e) => setIsPublished(e.target.checked)} />
            Published only
          </label>
          <Button onClick={loadData} variant="outline">Apply</Button>
        </CardContent>
      </Card>

      {/* Add form */}
      {addOpen && (
        <Card>
          <CardHeader><CardTitle>Add Review</CardTitle></CardHeader>
          <CardContent className="space-y-3">
            <Input
              placeholder="Customer ID *"
              value={addForm.customer_id}
              onChange={(e) => setAddForm((f) => ({ ...f, customer_id: e.target.value }))}
            />
            <Input
              placeholder="Booking ID (optional)"
              value={addForm.booking_id}
              onChange={(e) => setAddForm((f) => ({ ...f, booking_id: e.target.value }))}
            />
            <Input
              placeholder="Reviewer Name *"
              value={addForm.reviewer_name}
              onChange={(e) => setAddForm((f) => ({ ...f, reviewer_name: e.target.value }))}
            />
            <div>
              <label className="text-xs text-muted-foreground block mb-1">Rating</label>
              <select
                value={addForm.rating}
                onChange={(e) => setAddForm((f) => ({ ...f, rating: e.target.value }))}
                className="h-9 rounded-md border border-input bg-background px-3 py-1 text-sm"
              >
                {[1, 2, 3, 4, 5].map((n) => <option key={n} value={n}>{n}</option>)}
              </select>
            </div>
            <textarea
              className="w-full min-h-[80px] rounded-md border border-input bg-background px-3 py-2 text-sm"
              placeholder="Review body *"
              value={addForm.body}
              onChange={(e) => setAddForm((f) => ({ ...f, body: e.target.value }))}
            />
            {addError && <p className="text-red-500 text-sm">{addError}</p>}
            <div className="flex gap-2">
              <Button onClick={handleAddReview} disabled={addLoading}>
                {addLoading ? "Saving…" : "Submit"}
              </Button>
              <Button variant="outline" onClick={() => setAddOpen(false)}>Cancel</Button>
            </div>
          </CardContent>
        </Card>
      )}

      {error && <p className="text-red-500 text-sm">{error}</p>}
      {loading && <p className="text-muted-foreground">Loading...</p>}

      {!loading && (
        <Card>
          <CardContent className="pt-0">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Reviewer</TableHead>
                  <TableHead>Rating</TableHead>
                  <TableHead>Body</TableHead>
                  <TableHead>Booking</TableHead>
                  <TableHead>Published</TableHead>
                  <TableHead>Reply</TableHead>
                  <TableHead>Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {reviews.length === 0 && (
                  <TableRow>
                    <TableCell colSpan={7} className="text-center text-muted-foreground py-8">
                      No reviews found
                    </TableCell>
                  </TableRow>
                )}
                {reviews.map((r) => (
                  <>
                    <TableRow key={r.id}>
                      <TableCell className="font-medium">{r.reviewer_name}</TableCell>
                      <TableCell><Stars rating={r.rating} /></TableCell>
                      <TableCell className="max-w-[200px] truncate" title={r.body}>
                        {r.body.slice(0, 100)}{r.body.length > 100 ? "…" : ""}
                      </TableCell>
                      <TableCell>
                        {r.booking_id ? (
                          <Badge variant="outline">&#10003; Verified</Badge>
                        ) : (
                          <span className="text-muted-foreground">—</span>
                        )}
                      </TableCell>
                      <TableCell>
                        <Badge variant={r.is_published ? "default" : "secondary"}>
                          {r.is_published ? "Published" : "Hidden"}
                        </Badge>
                      </TableCell>
                      <TableCell className="max-w-[160px] truncate text-sm text-muted-foreground">
                        {r.reply ?? "—"}
                      </TableCell>
                      <TableCell>
                        <div className="flex gap-1 flex-wrap">
                          <Button
                            size="sm"
                            variant="outline"
                            onClick={() => {
                              setReplyId(replyId === r.id ? null : r.id);
                              setReplyText(r.reply ?? "");
                            }}
                          >
                            Reply
                          </Button>
                          <Button
                            size="sm"
                            variant="outline"
                            onClick={() => handleTogglePublish(r)}
                          >
                            {r.is_published ? "Unpublish" : "Publish"}
                          </Button>
                          <Button
                            size="sm"
                            variant="destructive"
                            onClick={() => handleDelete(r.id)}
                          >
                            Delete
                          </Button>
                        </div>
                      </TableCell>
                    </TableRow>
                    {replyId === r.id && (
                      <TableRow key={`reply-${r.id}`}>
                        <TableCell colSpan={7}>
                          <div className="flex gap-2 items-start p-2">
                            <textarea
                              className="flex-1 min-h-[60px] rounded-md border border-input bg-background px-3 py-2 text-sm"
                              value={replyText}
                              onChange={(e) => setReplyText(e.target.value)}
                              placeholder="Write a reply…"
                            />
                            <div className="flex flex-col gap-1">
                              <Button
                                size="sm"
                                onClick={() => handleReply(r.id)}
                                disabled={replyLoading}
                              >
                                {replyLoading ? "Saving…" : "Post"}
                              </Button>
                              <Button
                                size="sm"
                                variant="outline"
                                onClick={() => setReplyId(null)}
                              >
                                Cancel
                              </Button>
                            </div>
                          </div>
                        </TableCell>
                      </TableRow>
                    )}
                  </>
                ))}
              </TableBody>
            </Table>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
