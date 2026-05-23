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

type PickupStatus = "all" | "pending" | "scheduled" | "collected" | "failed";

interface ReturnPickup {
  id: string;
  customer_id: string;
  invoice_id: string | null;
  courier_provider: string | null;
  courier_tracking_number: string | null;
  pickup_address_line1: string;
  pickup_address_city: string;
  pickup_postal_code: string;
  pickup_country: string;
  preferred_date: string;
  preferred_time_slot: string;
  status: "pending" | "scheduled" | "collected" | "failed";
  created_at: string;
}

const STATUS_BADGE: Record<string, string> = {
  pending: "bg-yellow-100 text-yellow-800",
  scheduled: "bg-blue-100 text-blue-800",
  collected: "bg-green-100 text-green-800",
  failed: "bg-red-100 text-red-800",
};

const STATUS_TABS: PickupStatus[] = ["all", "pending", "scheduled", "collected", "failed"];

export default function ReturnPickupsPage() {
  const params = useParams();

  const [items, setItems] = useState<ReturnPickup[]>([]);
  const [statusFilter, setStatusFilter] = useState<PickupStatus>("all");
  const [customerFilter, setCustomerFilter] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  // New pickup form
  const [newOpen, setNewOpen] = useState(false);
  const [newForm, setNewForm] = useState({
    customer_id: "",
    invoice_id: "",
    pickup_address_line1: "",
    pickup_address_city: "",
    pickup_postal_code: "",
    pickup_country: "",
    preferred_date: "",
    preferred_time_slot: "morning",
    courier_provider: "",
  });
  const [newError, setNewError] = useState("");
  const [newSaving, setNewSaving] = useState(false);

  // Schedule inline form
  const [scheduleId, setScheduleId] = useState<string | null>(null);
  const [scheduleForm, setScheduleForm] = useState({
    courier_provider: "",
    courier_tracking_number: "",
  });
  const [scheduleSaving, setScheduleSaving] = useState(false);
  const [scheduleError, setScheduleError] = useState("");

  const headers = {
    Authorization: `Bearer ${getToken()}`,
    "Content-Type": "application/json",
  };

  async function loadItems() {
    setLoading(true);
    setError("");
    try {
      const qs = new URLSearchParams();
      if (statusFilter !== "all") qs.set("status", statusFilter);
      if (customerFilter) qs.set("customer_id", customerFilter);
      const res = await fetch(`${API}/api/return-pickups?${qs}`, { headers });
      if (!res.ok) throw new Error("Failed to load pickups");
      const data = await res.json();
      setItems(Array.isArray(data) ? data : data.items ?? []);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to load pickups");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadItems();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [statusFilter]);

  async function handleCreate() {
    setNewSaving(true);
    setNewError("");
    try {
      const body: Record<string, unknown> = {
        customer_id: newForm.customer_id,
        pickup_address_line1: newForm.pickup_address_line1,
        pickup_address_city: newForm.pickup_address_city,
        pickup_postal_code: newForm.pickup_postal_code,
        pickup_country: newForm.pickup_country,
        preferred_date: newForm.preferred_date,
        preferred_time_slot: newForm.preferred_time_slot,
        courier_provider: newForm.courier_provider,
      };
      if (newForm.invoice_id) body.invoice_id = newForm.invoice_id;

      const res = await fetch(`${API}/api/return-pickups`, {
        method: "POST",
        headers,
        body: JSON.stringify(body),
      });
      if (!res.ok) throw new Error("Failed to create pickup");
      setNewOpen(false);
      setNewForm({
        customer_id: "",
        invoice_id: "",
        pickup_address_line1: "",
        pickup_address_city: "",
        pickup_postal_code: "",
        pickup_country: "",
        preferred_date: "",
        preferred_time_slot: "morning",
        courier_provider: "",
      });
      loadItems();
    } catch (e: unknown) {
      setNewError(e instanceof Error ? e.message : "Failed to create pickup");
    } finally {
      setNewSaving(false);
    }
  }

  async function handleSchedule(id: string) {
    setScheduleSaving(true);
    setScheduleError("");
    try {
      const res = await fetch(`${API}/api/return-pickups/${id}/schedule`, {
        method: "POST",
        headers,
        body: JSON.stringify(scheduleForm),
      });
      if (!res.ok) throw new Error("Failed to schedule pickup");
      setScheduleId(null);
      setScheduleForm({ courier_provider: "", courier_tracking_number: "" });
      loadItems();
    } catch (e: unknown) {
      setScheduleError(e instanceof Error ? e.message : "Failed to schedule");
    } finally {
      setScheduleSaving(false);
    }
  }

  async function handleCollect(id: string) {
    try {
      const res = await fetch(`${API}/api/return-pickups/${id}/collect`, {
        method: "POST",
        headers,
      });
      if (!res.ok) throw new Error();
      loadItems();
    } catch {
      setError("Failed to mark as collected");
    }
  }

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Returns Pickup Scheduling</h1>
        <Button onClick={() => setNewOpen(!newOpen)}>New Pickup Request</Button>
      </div>

      {/* Status tabs */}
      <div className="flex gap-2 flex-wrap">
        {STATUS_TABS.map((s) => (
          <Button
            key={s}
            variant={statusFilter === s ? "default" : "outline"}
            size="sm"
            onClick={() => setStatusFilter(s)}
          >
            {s === "all" ? "All" : s.charAt(0).toUpperCase() + s.slice(1)}
          </Button>
        ))}
      </div>

      {/* Customer filter */}
      <div className="flex gap-2 items-end">
        <div>
          <label className="text-xs text-muted-foreground block mb-1">Customer ID</label>
          <Input
            value={customerFilter}
            onChange={(e) => setCustomerFilter(e.target.value)}
            placeholder="UUID (optional)"
            className="w-56"
          />
        </div>
        <Button variant="outline" onClick={loadItems}>Apply</Button>
      </div>

      {/* New pickup form */}
      {newOpen && (
        <Card>
          <CardHeader><CardTitle>New Pickup Request</CardTitle></CardHeader>
          <CardContent className="space-y-3">
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <Input
                placeholder="Customer ID *"
                value={newForm.customer_id}
                onChange={(e) => setNewForm((f) => ({ ...f, customer_id: e.target.value }))}
              />
              <Input
                placeholder="Invoice ID (optional)"
                value={newForm.invoice_id}
                onChange={(e) => setNewForm((f) => ({ ...f, invoice_id: e.target.value }))}
              />
              <Input
                placeholder="Address Line 1 *"
                value={newForm.pickup_address_line1}
                onChange={(e) =>
                  setNewForm((f) => ({ ...f, pickup_address_line1: e.target.value }))
                }
              />
              <Input
                placeholder="City *"
                value={newForm.pickup_address_city}
                onChange={(e) =>
                  setNewForm((f) => ({ ...f, pickup_address_city: e.target.value }))
                }
              />
              <Input
                placeholder="Postal Code *"
                value={newForm.pickup_postal_code}
                onChange={(e) =>
                  setNewForm((f) => ({ ...f, pickup_postal_code: e.target.value }))
                }
              />
              <Input
                placeholder="Country (2 chars) *"
                maxLength={2}
                value={newForm.pickup_country}
                onChange={(e) =>
                  setNewForm((f) => ({ ...f, pickup_country: e.target.value.toUpperCase() }))
                }
              />
              <div>
                <label className="text-xs text-muted-foreground block mb-1">Preferred Date *</label>
                <Input
                  type="date"
                  value={newForm.preferred_date}
                  onChange={(e) => setNewForm((f) => ({ ...f, preferred_date: e.target.value }))}
                />
              </div>
              <div>
                <label className="text-xs text-muted-foreground block mb-1">Time Slot *</label>
                <select
                  value={newForm.preferred_time_slot}
                  onChange={(e) =>
                    setNewForm((f) => ({ ...f, preferred_time_slot: e.target.value }))
                  }
                  className="h-9 rounded-md border border-input bg-background px-3 py-1 text-sm w-full"
                >
                  <option value="morning">Morning</option>
                  <option value="afternoon">Afternoon</option>
                  <option value="evening">Evening</option>
                </select>
              </div>
              <Input
                placeholder="Courier Provider *"
                value={newForm.courier_provider}
                onChange={(e) => setNewForm((f) => ({ ...f, courier_provider: e.target.value }))}
              />
            </div>
            {newError && <p className="text-red-500 text-sm">{newError}</p>}
            <div className="flex gap-2">
              <Button onClick={handleCreate} disabled={newSaving}>
                {newSaving ? "Saving…" : "Create"}
              </Button>
              <Button variant="outline" onClick={() => setNewOpen(false)}>Cancel</Button>
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
                  <TableHead>Customer</TableHead>
                  <TableHead>Invoice</TableHead>
                  <TableHead>Courier</TableHead>
                  <TableHead>Address</TableHead>
                  <TableHead>Date</TableHead>
                  <TableHead>Slot</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Tracking</TableHead>
                  <TableHead>Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {items.length === 0 && (
                  <TableRow>
                    <TableCell colSpan={9} className="text-center text-muted-foreground py-8">
                      No pickups found
                    </TableCell>
                  </TableRow>
                )}
                {items.map((item) => (
                  <>
                    <TableRow key={item.id}>
                      <TableCell className="font-mono text-xs">
                        {item.customer_id.slice(0, 8)}…
                      </TableCell>
                      <TableCell className="font-mono text-xs">
                        {item.invoice_id ? item.invoice_id.slice(0, 8) + "…" : "—"}
                      </TableCell>
                      <TableCell>{item.courier_provider ?? "—"}</TableCell>
                      <TableCell className="text-sm">
                        {item.pickup_address_line1}, {item.pickup_address_city}
                      </TableCell>
                      <TableCell className="text-sm">{item.preferred_date}</TableCell>
                      <TableCell className="capitalize text-sm">
                        {item.preferred_time_slot}
                      </TableCell>
                      <TableCell>
                        <span
                          className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${STATUS_BADGE[item.status] ?? ""}`}
                        >
                          {item.status}
                        </span>
                      </TableCell>
                      <TableCell className="text-xs">
                        {item.courier_tracking_number ?? "—"}
                      </TableCell>
                      <TableCell>
                        <div className="flex gap-1">
                          {item.status === "pending" && (
                            <Button
                              size="sm"
                              variant="outline"
                              onClick={() => {
                                setScheduleId(scheduleId === item.id ? null : item.id);
                                setScheduleForm({ courier_provider: item.courier_provider ?? "", courier_tracking_number: "" });
                              }}
                            >
                              Schedule
                            </Button>
                          )}
                          {item.status === "scheduled" && (
                            <Button
                              size="sm"
                              variant="outline"
                              onClick={() => handleCollect(item.id)}
                            >
                              Collected
                            </Button>
                          )}
                        </div>
                      </TableCell>
                    </TableRow>
                    {scheduleId === item.id && (
                      <TableRow key={`sched-${item.id}`}>
                        <TableCell colSpan={9} className="bg-muted/30">
                          <div className="flex flex-wrap gap-2 p-2 items-end">
                            <div>
                              <label className="text-xs text-muted-foreground block mb-1">
                                Courier Provider
                              </label>
                              <Input
                                value={scheduleForm.courier_provider}
                                onChange={(e) =>
                                  setScheduleForm((f) => ({
                                    ...f,
                                    courier_provider: e.target.value,
                                  }))
                                }
                                placeholder="e.g. DHL"
                                className="w-40"
                              />
                            </div>
                            <div>
                              <label className="text-xs text-muted-foreground block mb-1">
                                Tracking Number
                              </label>
                              <Input
                                value={scheduleForm.courier_tracking_number}
                                onChange={(e) =>
                                  setScheduleForm((f) => ({
                                    ...f,
                                    courier_tracking_number: e.target.value,
                                  }))
                                }
                                placeholder="Tracking #"
                                className="w-48"
                              />
                            </div>
                            <Button
                              size="sm"
                              onClick={() => handleSchedule(item.id)}
                              disabled={scheduleSaving}
                            >
                              {scheduleSaving ? "Saving…" : "Confirm"}
                            </Button>
                            <Button
                              size="sm"
                              variant="outline"
                              onClick={() => setScheduleId(null)}
                            >
                              Cancel
                            </Button>
                            {scheduleError && (
                              <p className="text-red-500 text-sm w-full">{scheduleError}</p>
                            )}
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
