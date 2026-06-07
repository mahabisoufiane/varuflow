"use client";
import { useState } from "react";
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

type POStatus = "draft" | "submitted" | "confirmed" | "rejected" | "fulfilled";

interface BuyerPO {
  id: string;
  buyer_po_number: string;
  buyer_org_name: string;
  status: POStatus;
  requested_delivery_date?: string;
  confirmed_at?: string;
  customer_id: string;
}

const statusClass: Record<POStatus, string> = {
  draft: "bg-gray-100 text-gray-800",
  submitted: "bg-yellow-100 text-yellow-800",
  confirmed: "bg-blue-100 text-blue-800",
  fulfilled: "bg-green-100 text-green-800",
  rejected: "bg-red-100 text-red-800",
};

const ALL_STATUSES: POStatus[] = ["draft", "submitted", "confirmed", "rejected", "fulfilled"];

export default function BuyerPOsPage() {
  const [customerIdFilter, setCustomerIdFilter] = useState("");
  const [statusFilter, setStatusFilter] = useState("all");
  const [items, setItems] = useState<BuyerPO[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [showDeprecation, setShowDeprecation] = useState(true);

  // New PO form
  const [showForm, setShowForm] = useState(false);
  const [newCustomerId, setNewCustomerId] = useState("");
  const [newPONumber, setNewPONumber] = useState("");
  const [newOrgName, setNewOrgName] = useState("");
  const [newDeliveryDate, setNewDeliveryDate] = useState("");
  const [formLoading, setFormLoading] = useState(false);
  const [formError, setFormError] = useState("");

  async function loadPOs() {
    setLoading(true);
    setError("");
    try {
      const params = new URLSearchParams();
      if (customerIdFilter.trim()) params.set("customer_id", customerIdFilter.trim());
      if (statusFilter !== "all") params.set("status", statusFilter);
      const data = await api.get<BuyerPO[]>(`/api/buyer-pos?${params}`);
      setItems(data);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to load POs");
    } finally {
      setLoading(false);
    }
  }

  async function handleAction(id: string, action: "confirm" | "reject" | "fulfill") {
    setError("");
    try {
      await api.post(`/api/buyer-pos/${id}/${action}`, {});
      await loadPOs();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : `Failed to ${action} PO`);
    }
  }

  async function handleCreatePO(e: React.FormEvent) {
    e.preventDefault();
    setFormLoading(true);
    setFormError("");
    try {
      const body: Record<string, unknown> = {
        customer_id: newCustomerId,
        buyer_po_number: newPONumber,
        buyer_org_name: newOrgName,
      };
      if (newDeliveryDate) body.requested_delivery_date = newDeliveryDate;
      await api.post("/api/buyer-pos", body);
      setNewCustomerId("");
      setNewPONumber("");
      setNewOrgName("");
      setNewDeliveryDate("");
      setShowForm(false);
      await loadPOs();
    } catch (e: unknown) {
      setFormError(e instanceof Error ? e.message : "Failed to create PO");
    } finally {
      setFormLoading(false);
    }
  }

  return (
    <div className="p-6 space-y-6 max-w-6xl mx-auto">
      {showDeprecation && (
        <div className="flex items-start gap-3 rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm">
          <div className="flex-1">
            <p className="font-medium text-amber-800">This module is being replaced</p>
            <p className="text-amber-700 mt-0.5">
              Customer ordering now happens through the{" "}
              <a href="/portal/catalogue" className="underline font-medium">Customer Portal</a>.
              Customers receive a magic link to browse products and place orders directly.
            </p>
          </div>
          <button onClick={() => setShowDeprecation(false)} className="text-amber-400 hover:text-amber-600 text-lg leading-none">×</button>
        </div>
      )}
      <h1 className="text-2xl font-bold">Buyer Purchase Orders</h1>

      {/* Filters */}
      <Card>
        <CardHeader>
          <CardTitle>Filter POs</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="flex gap-2 flex-wrap items-end">
            <div>
              <label className="text-sm font-medium">Customer ID</label>
              <Input
                placeholder="Optional"
                value={customerIdFilter}
                onChange={(e) => setCustomerIdFilter(e.target.value)}
                className="max-w-xs"
              />
            </div>
            <div className="flex gap-1 flex-wrap">
              <Button
                size="sm"
                variant={statusFilter === "all" ? "default" : "outline"}
                onClick={() => setStatusFilter("all")}
              >
                All
              </Button>
              {ALL_STATUSES.map((s) => (
                <Button
                  key={s}
                  size="sm"
                  variant={statusFilter === s ? "default" : "outline"}
                  onClick={() => setStatusFilter(s)}
                >
                  {s.charAt(0).toUpperCase() + s.slice(1)}
                </Button>
              ))}
            </div>
            <Button onClick={loadPOs} disabled={loading}>
              {loading ? "Loading…" : "Search"}
            </Button>
          </div>
          {error && <p className="text-red-500 text-sm">{error}</p>}
        </CardContent>
      </Card>

      {/* POs table */}
      {items.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle>Purchase Orders</CardTitle>
          </CardHeader>
          <CardContent>
            {loading ? (
              <p className="text-muted-foreground">Loading...</p>
            ) : (
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>PO Number</TableHead>
                    <TableHead>Buyer Org</TableHead>
                    <TableHead>Status</TableHead>
                    <TableHead>Delivery Date</TableHead>
                    <TableHead>Confirmed At</TableHead>
                    <TableHead>Actions</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {items.map((po) => (
                    <TableRow key={po.id}>
                      <TableCell className="font-mono text-sm">
                        {po.buyer_po_number}
                      </TableCell>
                      <TableCell>{po.buyer_org_name}</TableCell>
                      <TableCell>
                        <span
                          className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${statusClass[po.status]}`}
                        >
                          {po.status}
                        </span>
                      </TableCell>
                      <TableCell className="text-sm text-muted-foreground">
                        {po.requested_delivery_date
                          ? new Date(po.requested_delivery_date).toLocaleDateString()
                          : "—"}
                      </TableCell>
                      <TableCell className="text-sm text-muted-foreground">
                        {po.confirmed_at
                          ? new Date(po.confirmed_at).toLocaleString()
                          : "—"}
                      </TableCell>
                      <TableCell>
                        <div className="flex gap-2">
                          {po.status === "submitted" && (
                            <>
                              <Button
                                size="sm"
                                variant="outline"
                                onClick={() => handleAction(po.id, "confirm")}
                              >
                                Confirm
                              </Button>
                              <Button
                                size="sm"
                                variant="destructive"
                                onClick={() => handleAction(po.id, "reject")}
                              >
                                Reject
                              </Button>
                            </>
                          )}
                          {po.status === "confirmed" && (
                            <Button
                              size="sm"
                              onClick={() => handleAction(po.id, "fulfill")}
                            >
                              Fulfill
                            </Button>
                          )}
                        </div>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            )}
          </CardContent>
        </Card>
      )}

      {/* New PO */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <CardTitle>New Purchase Order</CardTitle>
            <Button
              size="sm"
              variant="outline"
              onClick={() => setShowForm((v) => !v)}
            >
              {showForm ? "Hide" : "Show Form"}
            </Button>
          </div>
        </CardHeader>
        {showForm && (
          <CardContent>
            <form onSubmit={handleCreatePO} className="space-y-3">
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="text-sm font-medium">Customer ID</label>
                  <Input
                    value={newCustomerId}
                    onChange={(e) => setNewCustomerId(e.target.value)}
                    placeholder="Customer ID"
                    required
                  />
                </div>
                <div>
                  <label className="text-sm font-medium">PO Number</label>
                  <Input
                    value={newPONumber}
                    onChange={(e) => setNewPONumber(e.target.value)}
                    placeholder="PO-2024-001"
                    required
                  />
                </div>
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="text-sm font-medium">Buyer Org Name</label>
                  <Input
                    value={newOrgName}
                    onChange={(e) => setNewOrgName(e.target.value)}
                    placeholder="Acme Corp"
                    required
                  />
                </div>
                <div>
                  <label className="text-sm font-medium">
                    Requested Delivery Date
                  </label>
                  <Input
                    type="date"
                    value={newDeliveryDate}
                    onChange={(e) => setNewDeliveryDate(e.target.value)}
                  />
                </div>
              </div>
              {formError && <p className="text-red-500 text-sm">{formError}</p>}
              <Button type="submit" disabled={formLoading}>
                {formLoading ? "Creating…" : "Create PO"}
              </Button>
            </form>
          </CardContent>
        )}
      </Card>
    </div>
  );
}
