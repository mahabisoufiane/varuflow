"use client";
import { useState, useEffect, useCallback } from "react";
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

type StatementStatus = "pending" | "generating" | "ready" | "failed";
type StatementFormat = "pdf" | "csv" | "json";

interface Statement {
  id: string;
  customer_id: string;
  format: StatementFormat;
  status: StatementStatus;
  date_from: string;
  date_to: string;
  generated_at?: string;
  file_url?: string;
}

const formatBadge: Record<StatementFormat, string> = {
  pdf: "bg-blue-100 text-blue-800",
  csv: "bg-green-100 text-green-800",
  json: "bg-gray-100 text-gray-800",
};

const statusBadge: Record<StatementStatus, string> = {
  pending: "bg-yellow-100 text-yellow-800",
  generating: "bg-orange-100 text-orange-800",
  ready: "bg-green-100 text-green-800",
  failed: "bg-red-100 text-red-800",
};

export default function StatementsPage() {
  const params = useParams();
  const locale = params.locale as string;

  const [requests, setRequests] = useState<Statement[]>([]);
  const [customerFilter, setCustomerFilter] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  // Form state
  const [formCustomerId, setFormCustomerId] = useState("");
  const [formDateFrom, setFormDateFrom] = useState("");
  const [formDateTo, setFormDateTo] = useState("");
  const [formFormat, setFormFormat] = useState<StatementFormat>("pdf");
  const [submitting, setSubmitting] = useState(false);

  const fetchStatements = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const query = customerFilter ? `?customer_id=${encodeURIComponent(customerFilter)}` : "";
      const res = await fetch(`${API}/api/statements${query}`, {
        headers: { Authorization: `Bearer ${getToken()}` },
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      setRequests(data);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to load statements");
    } finally {
      setLoading(false);
    }
  }, [customerFilter]);

  useEffect(() => {
    fetchStatements();
  }, [fetchStatements]);

  // Poll every 3 seconds if any statement is generating
  useEffect(() => {
    const hasGenerating = requests.some((r) => r.status === "generating");
    if (!hasGenerating) return;
    const interval = setInterval(fetchStatements, 3000);
    return () => clearInterval(interval);
  }, [requests, fetchStatements]);

  async function handleRequest(e: React.FormEvent) {
    e.preventDefault();
    setSubmitting(true);
    setError("");
    try {
      const res = await fetch(`${API}/api/statements`, {
        method: "POST",
        headers: {
          Authorization: `Bearer ${getToken()}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          customer_id: formCustomerId,
          date_from: formDateFrom,
          date_to: formDateTo,
          format: formFormat,
        }),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      await fetchStatements();
      setFormCustomerId("");
      setFormDateFrom("");
      setFormDateTo("");
      setFormFormat("pdf");
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to request statement");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="p-6 space-y-6">
      <h1 className="text-2xl font-bold">Customer Statements</h1>

      <Card>
        <CardHeader>
          <CardTitle>Request Statement</CardTitle>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleRequest} className="space-y-3">
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <Input
                placeholder="Customer ID"
                value={formCustomerId}
                onChange={(e) => setFormCustomerId(e.target.value)}
                required
              />
              <select
                className="border rounded px-3 py-2 text-sm bg-background"
                value={formFormat}
                onChange={(e) => setFormFormat(e.target.value as StatementFormat)}
              >
                <option value="pdf">PDF</option>
                <option value="csv">CSV</option>
                <option value="json">JSON</option>
              </select>
              <Input
                type="date"
                placeholder="Date From"
                value={formDateFrom}
                onChange={(e) => setFormDateFrom(e.target.value)}
                required
              />
              <Input
                type="date"
                placeholder="Date To"
                value={formDateTo}
                onChange={(e) => setFormDateTo(e.target.value)}
                required
              />
            </div>
            {error && <p className="text-red-500 text-sm">{error}</p>}
            <Button type="submit" disabled={submitting}>
              {submitting ? "Requesting…" : "Request Statement"}
            </Button>
          </form>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Statements</CardTitle>
          <div className="flex gap-2 mt-2">
            <Input
              placeholder="Filter by customer ID"
              value={customerFilter}
              onChange={(e) => setCustomerFilter(e.target.value)}
              className="max-w-xs"
            />
            <Button variant="outline" onClick={fetchStatements}>
              Search
            </Button>
          </div>
        </CardHeader>
        <CardContent>
          {loading ? (
            <p className="text-muted-foreground">Loading…</p>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Customer ID</TableHead>
                  <TableHead>Format</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Date From</TableHead>
                  <TableHead>Date To</TableHead>
                  <TableHead>Generated At</TableHead>
                  <TableHead>Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {requests.length === 0 && (
                  <TableRow>
                    <TableCell colSpan={7} className="text-center text-muted-foreground">
                      No statements found.
                    </TableCell>
                  </TableRow>
                )}
                {requests.map((row) => (
                  <TableRow key={row.id}>
                    <TableCell className="font-mono text-xs">{row.customer_id}</TableCell>
                    <TableCell>
                      <span
                        className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${formatBadge[row.format]}`}
                      >
                        {row.format.toUpperCase()}
                      </span>
                    </TableCell>
                    <TableCell>
                      <span
                        className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${statusBadge[row.status]}`}
                      >
                        {row.status}
                      </span>
                    </TableCell>
                    <TableCell>{row.date_from}</TableCell>
                    <TableCell>{row.date_to}</TableCell>
                    <TableCell>{row.generated_at ?? "—"}</TableCell>
                    <TableCell>
                      {row.status === "ready" && row.file_url ? (
                        <a
                          href={row.file_url}
                          target="_blank"
                          rel="noreferrer"
                          className="text-sm underline text-blue-600"
                        >
                          Download
                        </a>
                      ) : (
                        <span className="text-muted-foreground text-xs">—</span>
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
