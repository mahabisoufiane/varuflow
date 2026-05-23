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

const API = process.env.NEXT_PUBLIC_API_URL;
function getToken() {
  return typeof window !== "undefined" ? localStorage.getItem("auth_token") ?? "" : "";
}

const STATUS_TABS = ["all", "pending", "submitted", "approved", "rejected"] as const;
type Status = (typeof STATUS_TABS)[number];

function statusBadgeVariant(status: string) {
  const map: Record<string, string> = {
    pending: "bg-yellow-100 text-yellow-800",
    submitted: "bg-blue-100 text-blue-800",
    approved: "bg-green-100 text-green-800",
    rejected: "bg-red-100 text-red-800",
  };
  return map[status] ?? "bg-gray-100 text-gray-800";
}

interface Verification {
  id: string;
  customer_id: string;
  booking_id?: string;
  provider: string;
  status: string;
  document_type: string;
  verified_at?: string;
}

export default function IdentityVerificationPage() {
  const [verifications, setVerifications] = useState<Verification[]>([]);
  const [statusFilter, setStatusFilter] = useState<Status>("all");
  const [customerFilter, setCustomerFilter] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  // New verification form
  const [formCustomerId, setFormCustomerId] = useState("");
  const [formBookingId, setFormBookingId] = useState("");
  const [formProvider, setFormProvider] = useState("manual");
  const [formDocType, setFormDocType] = useState("");
  const [formLoading, setFormLoading] = useState(false);
  const [formError, setFormError] = useState("");

  async function fetchVerifications() {
    setLoading(true);
    setError("");
    try {
      const params = new URLSearchParams();
      if (customerFilter) params.set("customer_id", customerFilter);
      if (statusFilter !== "all") params.set("status", statusFilter);
      const res = await fetch(`${API}/api/identity-verification?${params}`, {
        headers: { Authorization: `Bearer ${getToken()}` },
      });
      if (!res.ok) throw new Error(`Error ${res.status}`);
      const data = await res.json();
      setVerifications(data);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to load verifications");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    fetchVerifications();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [statusFilter]);

  async function handleAction(id: string, action: "approve" | "reject") {
    try {
      const res = await fetch(`${API}/api/identity-verification/${id}/${action}`, {
        method: "POST",
        headers: { Authorization: `Bearer ${getToken()}` },
      });
      if (!res.ok) throw new Error(`Error ${res.status}`);
      fetchVerifications();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Action failed");
    }
  }

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    setFormLoading(true);
    setFormError("");
    try {
      const body: Record<string, string> = {
        customer_id: formCustomerId,
        provider: formProvider,
        document_type: formDocType,
      };
      if (formBookingId) body.booking_id = formBookingId;
      const res = await fetch(`${API}/api/identity-verification`, {
        method: "POST",
        headers: {
          Authorization: `Bearer ${getToken()}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify(body),
      });
      if (!res.ok) throw new Error(`Error ${res.status}`);
      setFormCustomerId("");
      setFormBookingId("");
      setFormProvider("manual");
      setFormDocType("");
      fetchVerifications();
    } catch (e: unknown) {
      setFormError(e instanceof Error ? e.message : "Failed to create verification");
    } finally {
      setFormLoading(false);
    }
  }

  return (
    <div className="p-6 space-y-6">
      <h1 className="text-2xl font-bold">Identity Verification</h1>

      {/* Filters */}
      <div className="flex flex-wrap gap-2 items-center">
        {STATUS_TABS.map((s) => (
          <Button
            key={s}
            size="sm"
            variant={statusFilter === s ? "default" : "outline"}
            onClick={() => setStatusFilter(s)}
          >
            {s.charAt(0).toUpperCase() + s.slice(1)}
          </Button>
        ))}
        <Input
          placeholder="Filter by customer ID"
          value={customerFilter}
          onChange={(e) => setCustomerFilter(e.target.value)}
          className="w-56"
        />
        <Button size="sm" onClick={fetchVerifications}>
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
                  <TableHead>Booking ID</TableHead>
                  <TableHead>Provider</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Document Type</TableHead>
                  <TableHead>Verified At</TableHead>
                  <TableHead>Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {verifications.length === 0 && (
                  <TableRow>
                    <TableCell colSpan={7} className="text-center text-muted-foreground">
                      No verifications found.
                    </TableCell>
                  </TableRow>
                )}
                {verifications.map((v) => (
                  <TableRow key={v.id}>
                    <TableCell className="font-mono text-xs">{v.customer_id}</TableCell>
                    <TableCell className="font-mono text-xs">
                      {v.booking_id ? v.booking_id.slice(0, 8) + "…" : "—"}
                    </TableCell>
                    <TableCell>
                      <Badge variant="outline">{v.provider}</Badge>
                    </TableCell>
                    <TableCell>
                      <span
                        className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${statusBadgeVariant(v.status)}`}
                      >
                        {v.status}
                      </span>
                    </TableCell>
                    <TableCell>{v.document_type}</TableCell>
                    <TableCell className="text-xs">
                      {v.verified_at ? new Date(v.verified_at).toLocaleString() : "—"}
                    </TableCell>
                    <TableCell className="space-x-2">
                      {v.status !== "approved" && (
                        <Button size="sm" variant="outline" onClick={() => handleAction(v.id, "approve")}>
                          Approve
                        </Button>
                      )}
                      {v.status !== "rejected" && (
                        <Button size="sm" variant="outline" onClick={() => handleAction(v.id, "reject")}>
                          Reject
                        </Button>
                      )}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </CardContent>
        </Card>
      )}

      {/* New Verification Form */}
      <Card>
        <CardHeader>
          <CardTitle>New Verification</CardTitle>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleCreate} className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div className="space-y-1">
              <label className="text-sm font-medium">Customer ID *</label>
              <Input
                required
                value={formCustomerId}
                onChange={(e) => setFormCustomerId(e.target.value)}
                placeholder="customer UUID"
              />
            </div>
            <div className="space-y-1">
              <label className="text-sm font-medium">Booking ID (optional)</label>
              <Input
                value={formBookingId}
                onChange={(e) => setFormBookingId(e.target.value)}
                placeholder="booking UUID"
              />
            </div>
            <div className="space-y-1">
              <label className="text-sm font-medium">Provider *</label>
              <select
                required
                value={formProvider}
                onChange={(e) => setFormProvider(e.target.value)}
                className="w-full border rounded-md px-3 py-2 text-sm bg-background"
              >
                <option value="manual">Manual</option>
                <option value="stripe_identity">Stripe Identity</option>
                <option value="jumio">Jumio</option>
                <option value="onfido">Onfido</option>
              </select>
            </div>
            <div className="space-y-1">
              <label className="text-sm font-medium">Document Type *</label>
              <Input
                required
                value={formDocType}
                onChange={(e) => setFormDocType(e.target.value)}
                placeholder="e.g. passport, driving_license"
              />
            </div>
            {formError && <p className="text-red-500 text-sm col-span-2">{formError}</p>}
            <div className="col-span-2">
              <Button type="submit" disabled={formLoading}>
                {formLoading ? "Submitting…" : "Create Verification"}
              </Button>
            </div>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}
