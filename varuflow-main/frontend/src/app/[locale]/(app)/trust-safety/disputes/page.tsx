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

const STATUS_TABS = ["all", "open", "in_review", "resolved", "escalated"] as const;
type DisputeStatus = (typeof STATUS_TABS)[number];

function disputeStatusClass(status: string) {
  const map: Record<string, keyof typeof pageStyles> = {
    open:      "statusOpen",
    in_review: "statusInReview",
    resolved:  "statusResolved",
    escalated: "statusEscalated",
    closed:    "statusClosed",
  };
  return pageStyles[map[status] ?? "statusClosed"];
}

function senderBadgeClass(senderType: string) {
  const map: Record<string, keyof typeof pageStyles> = {
    customer: "senderCustomer",
    staff:    "senderStaff",
    admin:    "senderAdmin",
  };
  return pageStyles[map[senderType] ?? "senderStaff"];
}

interface Dispute {
  id: string;
  customer_id: string;
  type: string;
  status: string;
  opened_by: string;
  created_at: string;
  description?: string;
  resolution_notes?: string;
}

interface DisputeMessage {
  id: string;
  sender_type: string;
  sender_name: string;
  body: string;
  created_at: string;
}

export default function DisputesPage() {
  const [disputes, setDisputes] = useState<Dispute[]>([]);
  const [statusFilter, setStatusFilter] = useState<DisputeStatus>("all");
  const [selectedDispute, setSelectedDispute] = useState<Dispute | null>(null);
  const [messages, setMessages] = useState<DisputeMessage[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  // Reply form
  const [replySenderType, setReplySenderType] = useState("staff");
  const [replySenderName, setReplySenderName] = useState("");
  const [replyBody, setReplyBody] = useState("");
  const [replyLoading, setReplyLoading] = useState(false);

  // New dispute form
  const [fCustomerId, setFCustomerId] = useState("");
  const [fType, setFType] = useState("billing");
  const [fDescription, setFDescription] = useState("");
  const [fOpenedBy, setFOpenedBy] = useState("customer");
  const [formLoading, setFormLoading] = useState(false);
  const [formError, setFormError] = useState("");

  async function fetchDisputes() {
    setLoading(true);
    setError("");
    try {
      const params = new URLSearchParams();
      if (statusFilter !== "all") params.set("status", statusFilter);
      setDisputes(await api.get<Dispute[]>(`/api/disputes?${params}`));
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to load disputes");
    } finally {
      setLoading(false);
    }
  }

  async function loadDetail(dispute: Dispute) {
    setSelectedDispute(dispute);
    try {
      const [detail, msgs] = await Promise.all([
        api.get<Dispute>(`/api/disputes/${dispute.id}`).catch(() => null),
        api.get<DisputeMessage[]>(`/api/disputes/${dispute.id}/messages`).catch(() => [] as DisputeMessage[]),
      ]);
      if (detail) setSelectedDispute(detail);
      setMessages(msgs);
    } catch {
      // non-fatal
    }
  }

  useEffect(() => {
    fetchDisputes();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [statusFilter]);

  async function handleReply(e: React.FormEvent) {
    e.preventDefault();
    if (!selectedDispute) return;
    setReplyLoading(true);
    try {
      await api.post(`/api/disputes/${selectedDispute.id}/messages`, { sender_type: replySenderType, sender_name: replySenderName, body: replyBody });
      setReplyBody("");
      loadDetail(selectedDispute);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to send reply");
    } finally {
      setReplyLoading(false);
    }
  }

  async function handleDisputeAction(action: "resolve" | "escalate" | "close") {
    if (!selectedDispute) return;
    try {
      await api.post(`/api/disputes/${selectedDispute.id}/${action}`, {});
      fetchDisputes();
      setSelectedDispute(null);
      setMessages([]);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Action failed");
    }
  }

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    setFormLoading(true);
    setFormError("");
    try {
      await api.post<Dispute>("/api/disputes", {
        customer_id: fCustomerId,
        type: fType,
        description: fDescription,
        opened_by: fOpenedBy,
      });
      setFCustomerId(""); setFDescription("");
      fetchDisputes();
    } catch (e: unknown) {
      setFormError(e instanceof Error ? e.message : "Failed to create dispute");
    } finally {
      setFormLoading(false);
    }
  }

  return (
    <div className="p-6 space-y-6">
      <h1 className="text-2xl font-bold">Dispute Resolution</h1>
      {error && <p className="text-red-500 text-sm">{error}</p>}

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Left: List */}
        <div className="space-y-4">
          <div className="flex flex-wrap gap-2">
            {STATUS_TABS.map((s) => (
              <Button
                key={s}
                size="sm"
                variant={statusFilter === s ? "default" : "outline"}
                onClick={() => setStatusFilter(s)}
              >
                {s === "in_review" ? "In Review" : s.charAt(0).toUpperCase() + s.slice(1)}
              </Button>
            ))}
          </div>

          {loading ? (
            <p className="text-muted-foreground">Loading...</p>
          ) : (
            <Card>
              <CardContent className="p-0">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Customer ID</TableHead>
                      <TableHead>Type</TableHead>
                      <TableHead>Status</TableHead>
                      <TableHead>Opened By</TableHead>
                      <TableHead>Created</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {disputes.length === 0 && (
                      <TableRow>
                        <TableCell colSpan={5} className="text-center text-muted-foreground">
                          No disputes found.
                        </TableCell>
                      </TableRow>
                    )}
                    {disputes.map((d) => (
                      <TableRow
                        key={d.id}
                        className="cursor-pointer hover:bg-muted/50"
                        onClick={() => loadDetail(d)}
                      >
                        <TableCell className="font-mono text-xs">{d.customer_id}</TableCell>
                        <TableCell>
                          <Badge variant="outline">{d.type}</Badge>
                        </TableCell>
                        <TableCell>
                          <span
                            className={disputeStatusClass(d.status)}
                          >
                            {d.status}
                          </span>
                        </TableCell>
                        <TableCell className="text-xs">{d.opened_by}</TableCell>
                        <TableCell className="text-xs">
                          {new Date(d.created_at).toLocaleDateString()}
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </CardContent>
            </Card>
          )}

          {/* New dispute form */}
          <Card>
            <CardHeader>
              <CardTitle className="text-base">New Dispute</CardTitle>
            </CardHeader>
            <CardContent>
              <form onSubmit={handleCreate} className="space-y-3">
                <div className="space-y-1">
                  <label className="text-sm font-medium">Customer ID *</label>
                  <Input required value={fCustomerId} onChange={(e) => setFCustomerId(e.target.value)} placeholder="customer UUID" />
                </div>
                <div className="space-y-1">
                  <label className="text-sm font-medium">Type *</label>
                  <select
                    required
                    value={fType}
                    onChange={(e) => setFType(e.target.value)}
                    className="w-full border rounded-md px-3 py-2 text-sm bg-background"
                  >
                    <option value="billing">Billing</option>
                    <option value="service">Service</option>
                    <option value="refund">Refund</option>
                    <option value="damage">Damage</option>
                    <option value="other">Other</option>
                  </select>
                </div>
                <div className="space-y-1">
                  <label className="text-sm font-medium">Description *</label>
                  <Input required value={fDescription} onChange={(e) => setFDescription(e.target.value)} placeholder="Describe the dispute" />
                </div>
                <div className="space-y-1">
                  <label className="text-sm font-medium">Opened By *</label>
                  <select
                    required
                    value={fOpenedBy}
                    onChange={(e) => setFOpenedBy(e.target.value)}
                    className="w-full border rounded-md px-3 py-2 text-sm bg-background"
                  >
                    <option value="customer">Customer</option>
                    <option value="staff">Staff</option>
                    <option value="admin">Admin</option>
                  </select>
                </div>
                {formError && <p className="text-red-500 text-sm">{formError}</p>}
                <Button type="submit" size="sm" disabled={formLoading}>
                  {formLoading ? "Creating…" : "Create Dispute"}
                </Button>
              </form>
            </CardContent>
          </Card>
        </div>

        {/* Right: Detail */}
        <div>
          {!selectedDispute ? (
            <div className="h-full flex items-center justify-center text-muted-foreground border rounded-lg p-8">
              Select a dispute to view details
            </div>
          ) : (
            <Card className="h-full flex flex-col">
              <CardHeader>
                <CardTitle className="text-base flex items-center justify-between">
                  Dispute Detail
                  <span
                    className={disputeStatusClass(selectedDispute.status)}
                  >
                    {selectedDispute.status}
                  </span>
                </CardTitle>
              </CardHeader>
              <CardContent className="flex-1 space-y-4">
                {selectedDispute.description && (
                  <div>
                    <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide">Description</p>
                    <p className="text-sm mt-1">{selectedDispute.description}</p>
                  </div>
                )}
                {selectedDispute.resolution_notes && (
                  <div>
                    <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide">Resolution Notes</p>
                    <p className="text-sm mt-1">{selectedDispute.resolution_notes}</p>
                  </div>
                )}

                {/* Messages */}
                <div className="space-y-2">
                  <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide">Messages</p>
                  {messages.length === 0 && (
                    <p className="text-sm text-muted-foreground">No messages yet.</p>
                  )}
                  {messages.map((m) => (
                    <div key={m.id} className="border rounded-md p-3 space-y-1">
                      <div className="flex items-center gap-2">
                        <span
                          className={senderBadgeClass(m.sender_type)}
                        >
                          {m.sender_type}
                        </span>
                        <span className="text-xs font-medium">{m.sender_name}</span>
                        <span className="text-xs text-muted-foreground ml-auto">
                          {new Date(m.created_at).toLocaleString()}
                        </span>
                      </div>
                      <p className="text-sm">{m.body}</p>
                    </div>
                  ))}
                </div>

                {/* Reply form */}
                <form onSubmit={handleReply} className="space-y-2 pt-2 border-t">
                  <div className="flex gap-2">
                    <select
                      value={replySenderType}
                      onChange={(e) => setReplySenderType(e.target.value)}
                      className="border rounded-md px-3 py-2 text-sm bg-background"
                    >
                      <option value="staff">Staff</option>
                      <option value="admin">Admin</option>
                      <option value="customer">Customer</option>
                    </select>
                    <Input
                      placeholder="Your name"
                      value={replySenderName}
                      onChange={(e) => setReplySenderName(e.target.value)}
                      required
                    />
                  </div>
                  <Input
                    placeholder="Reply message"
                    value={replyBody}
                    onChange={(e) => setReplyBody(e.target.value)}
                    required
                  />
                  <Button type="submit" size="sm" disabled={replyLoading}>
                    {replyLoading ? "Sending…" : "Send Reply"}
                  </Button>
                </form>

                {/* Action buttons */}
                <div className="flex flex-wrap gap-2 pt-2 border-t">
                  <Button size="sm" variant="outline" onClick={() => handleDisputeAction("resolve")}>
                    Resolve
                  </Button>
                  <Button size="sm" variant="outline" onClick={() => handleDisputeAction("escalate")}>
                    Escalate
                  </Button>
                  <Button size="sm" variant="outline" onClick={() => handleDisputeAction("close")}>
                    Close
                  </Button>
                </div>
              </CardContent>
            </Card>
          )}
        </div>
      </div>
    </div>
  );
}
