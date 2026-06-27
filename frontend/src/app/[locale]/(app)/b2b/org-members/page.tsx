"use client";
import { useState } from "react";
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
  return typeof window !== "undefined"
    ? localStorage.getItem("auth_token") ?? ""
    : "";
}

type MemberRole = "admin" | "approver" | "requester";

interface OrgMember {
  id: string;
  member_email: string;
  member_name?: string;
  role: MemberRole;
  is_active: boolean;
  joined_at: string;
}

interface Approval {
  id: string;
  po_id: string;
  requested_by: string;
  status: string;
  reviewed_by?: string;
  reviewed_at?: string;
}

const roleBadgeVariant: Record<MemberRole, "default" | "secondary" | "outline"> = {
  admin: "default",
  approver: "secondary",
  requester: "outline",
};

function truncate(str: string, len = 8) {
  return str.length > len ? str.slice(0, len) + "…" : str;
}

export default function OrgMembersPage() {
  const { locale } = useParams<{ locale: string }>();

  const [customerIdInput, setCustomerIdInput] = useState("");
  const [customerId, setCustomerId] = useState("");

  // Members
  const [members, setMembers] = useState<OrgMember[]>([]);
  const [membersLoading, setMembersLoading] = useState(false);
  const [membersError, setMembersError] = useState("");

  // Invite form
  const [inviteEmail, setInviteEmail] = useState("");
  const [inviteName, setInviteName] = useState("");
  const [inviteRole, setInviteRole] = useState<MemberRole>("requester");
  const [inviteLoading, setInviteLoading] = useState(false);
  const [inviteError, setInviteError] = useState("");

  // Approvals
  const [approvals, setApprovals] = useState<Approval[]>([]);
  const [approvalsLoading, setApprovalsLoading] = useState(false);
  const [approvalsError, setApprovalsError] = useState("");

  async function loadAll() {
    if (!customerIdInput.trim()) return;
    const id = customerIdInput.trim();
    setCustomerId(id);
    await Promise.all([loadMembers(id), loadApprovals(id)]);
  }

  async function loadMembers(id: string) {
    setMembersLoading(true);
    setMembersError("");
    try {
      const res = await fetch(`${API}/api/customer-org/${id}/members`, {
        headers: { Authorization: `Bearer ${getToken()}` },
      });
      if (!res.ok) throw new Error(`Error ${res.status}`);
      setMembers(await res.json());
    } catch (e: unknown) {
      setMembersError(e instanceof Error ? e.message : "Failed to load members");
    } finally {
      setMembersLoading(false);
    }
  }

  async function loadApprovals(id: string) {
    setApprovalsLoading(true);
    setApprovalsError("");
    try {
      const res = await fetch(`${API}/api/customer-org/${id}/approvals`, {
        headers: { Authorization: `Bearer ${getToken()}` },
      });
      if (!res.ok) throw new Error(`Error ${res.status}`);
      setApprovals(await res.json());
    } catch (e: unknown) {
      setApprovalsError(e instanceof Error ? e.message : "Failed to load approvals");
    } finally {
      setApprovalsLoading(false);
    }
  }

  async function handleInvite(e: React.FormEvent) {
    e.preventDefault();
    if (!customerId) { setInviteError("Load a customer first"); return; }
    setInviteLoading(true);
    setInviteError("");
    try {
      const res = await fetch(`${API}/api/customer-org/${customerId}/members`, {
        method: "POST",
        headers: {
          Authorization: `Bearer ${getToken()}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          member_email: inviteEmail,
          member_name: inviteName || undefined,
          role: inviteRole,
        }),
      });
      if (!res.ok) throw new Error(`Error ${res.status}`);
      setInviteEmail("");
      setInviteName("");
      setInviteRole("requester");
      await loadMembers(customerId);
    } catch (e: unknown) {
      setInviteError(e instanceof Error ? e.message : "Failed to invite member");
    } finally {
      setInviteLoading(false);
    }
  }

  async function handleDeactivate(memberId: string) {
    if (!customerId) return;
    setMembersError("");
    try {
      const res = await fetch(
        `${API}/api/customer-org/${customerId}/members/${memberId}/deactivate`,
        {
          method: "POST",
          headers: { Authorization: `Bearer ${getToken()}` },
        }
      );
      if (!res.ok) throw new Error(`Error ${res.status}`);
      await loadMembers(customerId);
    } catch (e: unknown) {
      setMembersError(e instanceof Error ? e.message : "Failed to deactivate member");
    }
  }

  async function handleApprovalAction(
    approvalId: string,
    action: "approve" | "reject"
  ) {
    if (!customerId) return;
    setApprovalsError("");
    try {
      const res = await fetch(
        `${API}/api/customer-org/${customerId}/approvals/${approvalId}/${action}`,
        {
          method: "POST",
          headers: { Authorization: `Bearer ${getToken()}` },
        }
      );
      if (!res.ok) throw new Error(`Error ${res.status}`);
      await loadApprovals(customerId);
    } catch (e: unknown) {
      setApprovalsError(e instanceof Error ? e.message : `Failed to ${action}`);
    }
  }

  return (
    <div className="p-6 space-y-6 max-w-5xl mx-auto">
      <h1 className="text-2xl font-bold">Customer Org Members &amp; Approvals</h1>

      {/* Customer lookup */}
      <Card>
        <CardHeader>
          <CardTitle>Load Customer Org</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex gap-2">
            <Input
              placeholder="Customer ID"
              value={customerIdInput}
              onChange={(e) => setCustomerIdInput(e.target.value)}
              className="max-w-sm"
            />
            <Button
              onClick={loadAll}
              disabled={membersLoading || approvalsLoading}
            >
              {membersLoading || approvalsLoading ? "Loading…" : "Load"}
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* Members section */}
      <Card>
        <CardHeader>
          <CardTitle>Members</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          {membersError && (
            <p className="text-red-500 text-sm">{membersError}</p>
          )}
          {membersLoading ? (
            <p className="text-muted-foreground">Loading...</p>
          ) : members.length === 0 ? (
            <p className="text-muted-foreground text-sm">No members found.</p>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Email</TableHead>
                  <TableHead>Name</TableHead>
                  <TableHead>Role</TableHead>
                  <TableHead>Active</TableHead>
                  <TableHead>Joined At</TableHead>
                  <TableHead>Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {members.map((m) => (
                  <TableRow key={m.id}>
                    <TableCell className="text-sm">{m.member_email}</TableCell>
                    <TableCell className="text-sm">
                      {m.member_name ?? "—"}
                    </TableCell>
                    <TableCell>
                      <Badge variant={roleBadgeVariant[m.role]}>
                        {m.role}
                      </Badge>
                    </TableCell>
                    <TableCell>
                      <span
                        className={`text-xs font-medium ${m.is_active ? "text-green-700" : "text-muted-foreground"}`}
                      >
                        {m.is_active ? "Yes" : "No"}
                      </span>
                    </TableCell>
                    <TableCell className="text-sm text-muted-foreground">
                      {new Date(m.joined_at).toLocaleDateString()}
                    </TableCell>
                    <TableCell>
                      {m.is_active && (
                        <Button
                          size="sm"
                          variant="destructive"
                          onClick={() => handleDeactivate(m.id)}
                        >
                          Deactivate
                        </Button>
                      )}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}

          {/* Invite form */}
          <div className="pt-4 border-t">
            <h3 className="text-sm font-semibold mb-3">Invite Member</h3>
            <form onSubmit={handleInvite} className="space-y-3">
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="text-sm font-medium">Email</label>
                  <Input
                    type="email"
                    value={inviteEmail}
                    onChange={(e) => setInviteEmail(e.target.value)}
                    placeholder="member@example.com"
                    required
                  />
                </div>
                <div>
                  <label className="text-sm font-medium">Name (optional)</label>
                  <Input
                    value={inviteName}
                    onChange={(e) => setInviteName(e.target.value)}
                    placeholder="Full name"
                  />
                </div>
              </div>
              <div>
                <label className="text-sm font-medium">Role</label>
                <select
                  className="flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm shadow-sm focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
                  value={inviteRole}
                  onChange={(e) => setInviteRole(e.target.value as MemberRole)}
                >
                  <option value="requester">Requester</option>
                  <option value="approver">Approver</option>
                  <option value="admin">Admin</option>
                </select>
              </div>
              {inviteError && (
                <p className="text-red-500 text-sm">{inviteError}</p>
              )}
              <Button type="submit" disabled={inviteLoading}>
                {inviteLoading ? "Inviting…" : "Invite Member"}
              </Button>
            </form>
          </div>
        </CardContent>
      </Card>

      {/* Approvals section */}
      <Card>
        <CardHeader>
          <CardTitle>Approval Requests</CardTitle>
        </CardHeader>
        <CardContent>
          {approvalsError && (
            <p className="text-red-500 text-sm">{approvalsError}</p>
          )}
          {approvalsLoading ? (
            <p className="text-muted-foreground">Loading...</p>
          ) : approvals.length === 0 ? (
            <p className="text-muted-foreground text-sm">No approval requests.</p>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>PO ID</TableHead>
                  <TableHead>Requested By</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Reviewed By</TableHead>
                  <TableHead>Reviewed At</TableHead>
                  <TableHead>Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {approvals.map((appr) => (
                  <TableRow key={appr.id}>
                    <TableCell className="font-mono text-xs">
                      {truncate(appr.po_id)}
                    </TableCell>
                    <TableCell className="text-sm">
                      {appr.requested_by}
                    </TableCell>
                    <TableCell>
                      <Badge
                        variant={
                          appr.status === "approved"
                            ? "default"
                            : appr.status === "rejected"
                            ? "destructive"
                            : "secondary"
                        }
                      >
                        {appr.status}
                      </Badge>
                    </TableCell>
                    <TableCell className="text-sm text-muted-foreground">
                      {appr.reviewed_by ?? "—"}
                    </TableCell>
                    <TableCell className="text-sm text-muted-foreground">
                      {appr.reviewed_at
                        ? new Date(appr.reviewed_at).toLocaleString()
                        : "—"}
                    </TableCell>
                    <TableCell>
                      {appr.status === "pending" && (
                        <div className="flex gap-2">
                          <Button
                            size="sm"
                            variant="outline"
                            onClick={() =>
                              handleApprovalAction(appr.id, "approve")
                            }
                          >
                            Approve
                          </Button>
                          <Button
                            size="sm"
                            variant="destructive"
                            onClick={() =>
                              handleApprovalAction(appr.id, "reject")
                            }
                          >
                            Reject
                          </Button>
                        </div>
                      )}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
