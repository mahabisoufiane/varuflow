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

const STATUS_TABS = ["all", "pending", "clear", "flagged", "expired"] as const;
type Status = (typeof STATUS_TABS)[number];

function statusClass(status: string) {
  const map: Record<string, string> = {
    pending: "bg-yellow-100 text-yellow-800",
    clear: "bg-green-100 text-green-800",
    flagged: "bg-red-100 text-red-800",
    expired: "bg-gray-100 text-gray-800",
  };
  return map[status] ?? "bg-gray-100 text-gray-800";
}

interface BackgroundCheck {
  id: string;
  staff_id: string;
  check_type: string;
  provider: string;
  status: string;
  issued_date?: string;
  expiry_date?: string;
  badge_visible: boolean;
  reference_number?: string;
}

export default function BackgroundChecksPage() {
  const [checks, setChecks] = useState<BackgroundCheck[]>([]);
  const [staffFilter, setStaffFilter] = useState("");
  const [statusFilter, setStatusFilter] = useState<Status>("all");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  // Add check form
  const [fStaffId, setFStaffId] = useState("");
  const [fCheckType, setFCheckType] = useState("dbs");
  const [fProvider, setFProvider] = useState("");
  const [fIssued, setFIssued] = useState("");
  const [fExpiry, setFExpiry] = useState("");
  const [fRef, setFRef] = useState("");
  const [formLoading, setFormLoading] = useState(false);
  const [formError, setFormError] = useState("");

  async function fetchChecks() {
    setLoading(true);
    setError("");
    try {
      const params = new URLSearchParams();
      if (staffFilter) params.set("staff_id", staffFilter);
      if (statusFilter !== "all") params.set("status", statusFilter);
      setChecks(await api.get<BackgroundCheck[]>(`/api/background-checks?${params}`));
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to load checks");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    fetchChecks();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [statusFilter]);

  async function handleAction(id: string, action: "clear" | "flag") {
    try {
      await api.post(`/api/background-checks/${id}/${action}`, {});
      fetchChecks();
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
        staff_id: fStaffId,
        check_type: fCheckType,
        provider: fProvider,
        issued_date: fIssued,
        expiry_date: fExpiry,
        reference_number: fRef,
      };
      await api.post<BackgroundCheck>("/api/background-checks", body);
      setFStaffId("");
      setFProvider("");
      setFIssued("");
      setFExpiry("");
      setFRef("");
      fetchChecks();
    } catch (e: unknown) {
      setFormError(e instanceof Error ? e.message : "Failed to add check");
    } finally {
      setFormLoading(false);
    }
  }

  return (
    <div className="p-6 space-y-6">
      <h1 className="text-2xl font-bold">Staff Background Checks</h1>

      {/* Status tabs + staff filter */}
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
          placeholder="Filter by staff ID"
          value={staffFilter}
          onChange={(e) => setStaffFilter(e.target.value)}
          className="w-56"
        />
        <Button size="sm" onClick={fetchChecks}>
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
                  <TableHead>Staff ID</TableHead>
                  <TableHead>Check Type</TableHead>
                  <TableHead>Provider</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Issued</TableHead>
                  <TableHead>Expiry</TableHead>
                  <TableHead>Badge Visible</TableHead>
                  <TableHead>Reference</TableHead>
                  <TableHead>Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {checks.length === 0 && (
                  <TableRow>
                    <TableCell colSpan={9} className="text-center text-muted-foreground">
                      No checks found.
                    </TableCell>
                  </TableRow>
                )}
                {checks.map((c) => (
                  <TableRow key={c.id}>
                    <TableCell className="font-mono text-xs">{c.staff_id.slice(0, 8)}…</TableCell>
                    <TableCell>{c.check_type}</TableCell>
                    <TableCell>{c.provider}</TableCell>
                    <TableCell>
                      <span
                        className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${statusClass(c.status)}`}
                      >
                        {c.status}
                      </span>
                    </TableCell>
                    <TableCell className="text-xs">{c.issued_date ?? "—"}</TableCell>
                    <TableCell className="text-xs">{c.expiry_date ?? "—"}</TableCell>
                    <TableCell className="text-center">{c.badge_visible ? "✓" : "—"}</TableCell>
                    <TableCell className="text-xs">{c.reference_number ?? "—"}</TableCell>
                    <TableCell className="space-x-2">
                      {c.status !== "clear" && (
                        <Button size="sm" variant="outline" onClick={() => handleAction(c.id, "clear")}>
                          Clear
                        </Button>
                      )}
                      {c.status !== "flagged" && (
                        <Button size="sm" variant="outline" onClick={() => handleAction(c.id, "flag")}>
                          Flag
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

      {/* Add Check Form */}
      <Card>
        <CardHeader>
          <CardTitle>Add Check</CardTitle>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleCreate} className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div className="space-y-1">
              <label className="text-sm font-medium">Staff ID *</label>
              <Input required value={fStaffId} onChange={(e) => setFStaffId(e.target.value)} placeholder="staff UUID" />
            </div>
            <div className="space-y-1">
              <label className="text-sm font-medium">Check Type *</label>
              <select
                required
                value={fCheckType}
                onChange={(e) => setFCheckType(e.target.value)}
                className="w-full border rounded-md px-3 py-2 text-sm bg-background"
              >
                <option value="dbs">DBS</option>
                <option value="dbs_enhanced">DBS Enhanced</option>
                <option value="criminal">Criminal</option>
                <option value="custom">Custom</option>
              </select>
            </div>
            <div className="space-y-1">
              <label className="text-sm font-medium">Provider *</label>
              <Input required value={fProvider} onChange={(e) => setFProvider(e.target.value)} placeholder="e.g. GBGroup" />
            </div>
            <div className="space-y-1">
              <label className="text-sm font-medium">Issued Date *</label>
              <Input required type="date" value={fIssued} onChange={(e) => setFIssued(e.target.value)} />
            </div>
            <div className="space-y-1">
              <label className="text-sm font-medium">Expiry Date *</label>
              <Input required type="date" value={fExpiry} onChange={(e) => setFExpiry(e.target.value)} />
            </div>
            <div className="space-y-1">
              <label className="text-sm font-medium">Reference Number</label>
              <Input value={fRef} onChange={(e) => setFRef(e.target.value)} placeholder="optional reference" />
            </div>
            {formError && <p className="text-red-500 text-sm col-span-2">{formError}</p>}
            <div className="col-span-2">
              <Button type="submit" disabled={formLoading}>
                {formLoading ? "Saving…" : "Add Check"}
              </Button>
            </div>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}
