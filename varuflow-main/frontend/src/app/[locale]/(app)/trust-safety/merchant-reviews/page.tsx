"use client";
import { useState, useEffect } from "react";
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
import pageStyles from "./page.module.scss";

const TAG_COLORS: Record<string, string> = {
  no_show: "bg-red-100 text-red-800",
  late_payer: "bg-orange-100 text-orange-800",
  great_client: "bg-green-100 text-green-800",
};

const TAG_MODULE: Record<string, keyof typeof pageStyles> = {
  no_show:     "tagNoShow",
  late_payer:  "tagLatePayment",
  great_client:"tagGreatClient",
};

function tagClass(tag: string) {
  return pageStyles[TAG_MODULE[tag] ?? "tagNoShow"];
}

interface MerchantReview {
  id: string;
  customer_id: string;
  staff_user_id: string;
  rating: number;
  tags: string[];
  is_private: boolean;
  shared_with_network: boolean;
  body?: string;
}

export default function MerchantReviewsPage() {
  const [reviews, setReviews] = useState<MerchantReview[]>([]);
  const [customerFilter, setCustomerFilter] = useState("");
  const [networkMode, setNetworkMode] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  // Form
  const [fCustomerId, setFCustomerId] = useState("");
  const [fBookingId, setFBookingId] = useState("");
  const [fRating, setFRating] = useState("5");
  const [fBody, setFBody] = useState("");
  const [fTags, setFTags] = useState("");
  const [fIsPrivate, setFIsPrivate] = useState(false);
  const [fShared, setFShared] = useState(false);
  const [formLoading, setFormLoading] = useState(false);
  const [formError, setFormError] = useState("");

  async function fetchReviews() {
    setLoading(true);
    setError("");
    try {
      const params = new URLSearchParams();
      if (customerFilter) params.set("customer_id", customerFilter);
      const endpoint = networkMode
        ? `/api/merchant-reviews/network?${params}`
        : `/api/merchant-reviews?${params}`;
      setReviews(await api.get<MerchantReview[]>(endpoint));
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to load reviews");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    fetchReviews();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [networkMode]);

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    setFormLoading(true);
    setFormError("");
    try {
      const body: Record<string, unknown> = {
        customer_id: fCustomerId,
        rating: parseInt(fRating, 10),
        body: fBody,
        tags: fTags
          .split(",")
          .map((t) => t.trim())
          .filter(Boolean),
        is_private: fIsPrivate,
        shared_with_network: fShared,
      };
      if (fBookingId) body.booking_id = fBookingId;
      await api.post<MerchantReview>("/api/merchant-reviews", body);
      setFCustomerId(""); setFBookingId(""); setFBody(""); setFTags(""); setFIsPrivate(false); setFShared(false); setFRating("5");
      fetchReviews();
    } catch (e: unknown) {
      setFormError(e instanceof Error ? e.message : "Failed to create review");
    } finally {
      setFormLoading(false);
    }
  }

  return (
    <div className="p-6 space-y-6">
      <h1 className="text-2xl font-bold">Merchant Reviews of Customers</h1>

      {/* Filters & toggle */}
      <div className="flex flex-wrap gap-2 items-center">
        <Button
          size="sm"
          variant={!networkMode ? "default" : "outline"}
          onClick={() => setNetworkMode(false)}
        >
          Own Reviews
        </Button>
        <Button
          size="sm"
          variant={networkMode ? "default" : "outline"}
          onClick={() => setNetworkMode(true)}
        >
          Network Reviews
        </Button>
        <Input
          placeholder="Filter by customer ID"
          value={customerFilter}
          onChange={(e) => setCustomerFilter(e.target.value)}
          className="w-56"
        />
        <Button size="sm" onClick={fetchReviews}>
          Search
        </Button>
      </div>

      {error && <p className="text-red-500 text-sm">{error}</p>}
      {loading ? (
        <p className="text-muted-foreground">Loading...</p>
      ) : (
        <Card>
          <CardContent className="p-0">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Customer ID</TableHead>
                  <TableHead>Staff User ID</TableHead>
                  <TableHead>Rating</TableHead>
                  <TableHead>Tags</TableHead>
                  <TableHead>Private</TableHead>
                  <TableHead>Shared with Network</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {reviews.length === 0 && (
                  <TableRow>
                    <TableCell colSpan={6} className="text-center text-muted-foreground">
                      No reviews found.
                    </TableCell>
                  </TableRow>
                )}
                {reviews.map((r) => (
                  <TableRow key={r.id}>
                    <TableCell className="font-mono text-xs">{r.customer_id}</TableCell>
                    <TableCell className="font-mono text-xs">{r.staff_user_id}</TableCell>
                    <TableCell className="text-sm">{r.rating}/5</TableCell>
                    <TableCell>
                      <div className="flex flex-wrap gap-1">
                        {r.tags.slice(0, 3).map((tag) => (
                          <span
                            key={tag}
                            className={tagClass(tag)}
                          >
                            {tag}
                          </span>
                        ))}
                        {r.tags.length > 3 && (
                          <span className="text-xs text-muted-foreground">+{r.tags.length - 3}</span>
                        )}
                      </div>
                    </TableCell>
                    <TableCell>
                      <Badge variant={r.is_private ? "default" : "secondary"}>
                        {r.is_private ? "Private" : "Public"}
                      </Badge>
                    </TableCell>
                    <TableCell>
                      <Badge variant={r.shared_with_network ? "default" : "secondary"}>
                        {r.shared_with_network ? "Shared" : "Not shared"}
                      </Badge>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </CardContent>
        </Card>
      )}

      {/* Add Review Form */}
      <Card>
        <CardHeader>
          <CardTitle>Add Review</CardTitle>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleCreate} className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div className="space-y-1">
              <label className="text-sm font-medium">Customer ID *</label>
              <Input required value={fCustomerId} onChange={(e) => setFCustomerId(e.target.value)} placeholder="customer UUID" />
            </div>
            <div className="space-y-1">
              <label className="text-sm font-medium">Booking ID (optional)</label>
              <Input value={fBookingId} onChange={(e) => setFBookingId(e.target.value)} placeholder="booking UUID" />
            </div>
            <div className="space-y-1">
              <label className="text-sm font-medium">Rating (1–5) *</label>
              <select
                required
                value={fRating}
                onChange={(e) => setFRating(e.target.value)}
                className="w-full border rounded-md px-3 py-2 text-sm bg-background"
              >
                {[1, 2, 3, 4, 5].map((n) => (
                  <option key={n} value={String(n)}>
                    {n}
                  </option>
                ))}
              </select>
            </div>
            <div className="space-y-1">
              <label className="text-sm font-medium">Tags (comma-separated)</label>
              <Input
                value={fTags}
                onChange={(e) => setFTags(e.target.value)}
                placeholder="e.g. great_client, late_payer"
              />
            </div>
            <div className="space-y-1 sm:col-span-2">
              <label className="text-sm font-medium">Body</label>
              <Input value={fBody} onChange={(e) => setFBody(e.target.value)} placeholder="Review notes" />
            </div>
            <div className="flex items-center gap-4">
              <label className="flex items-center gap-2 text-sm">
                <input
                  type="checkbox"
                  checked={fIsPrivate}
                  onChange={(e) => setFIsPrivate(e.target.checked)}
                />
                Private
              </label>
              <label className="flex items-center gap-2 text-sm">
                <input
                  type="checkbox"
                  checked={fShared}
                  onChange={(e) => setFShared(e.target.checked)}
                />
                Share with Network
              </label>
            </div>
            {formError && <p className="text-red-500 text-sm col-span-2">{formError}</p>}
            <div className="col-span-2">
              <Button type="submit" disabled={formLoading}>
                {formLoading ? "Saving…" : "Add Review"}
              </Button>
            </div>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}
