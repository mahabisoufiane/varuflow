"use client";
import { useState } from "react";
import { api } from "@/lib/api-client";
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

type ExportTarget = "csv" | "splitwise" | "personal_capital" | "ynab";

interface ReceiptExport {
  id: string;
  invoice_id: string;
  export_target: ExportTarget;
  exported_at: string;
  ref?: string;
}

const targetBadgeClass: Record<ExportTarget, string> = {
  csv: "bg-gray-100 text-gray-800",
  splitwise: "bg-green-100 text-green-800",
  personal_capital: "bg-blue-100 text-blue-800",
  ynab: "bg-purple-100 text-purple-800",
};

function truncate(str: string, len = 8) {
  return str.length > len ? str.slice(0, len) + "…" : str;
}

export default function ReceiptExportsPage() {
  const [customerIdInput, setCustomerIdInput] = useState("");
  const [customerId, setCustomerId] = useState("");
  const [exports, setExports] = useState<ReceiptExport[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  // Log export form
  const [invoiceId, setInvoiceId] = useState("");
  const [exportTarget, setExportTarget] = useState<ExportTarget>("csv");
  const [formLoading, setFormLoading] = useState(false);
  const [formError, setFormError] = useState("");

  async function loadExports() {
    if (!customerIdInput.trim()) return;
    const cid = customerIdInput.trim();
    setCustomerId(cid);
    setLoading(true);
    setError("");
    try {
      const data = await api.get<ReceiptExport[]>(`/api/receipt-exports?customer_id=${encodeURIComponent(cid)}`);
      setExports(data);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to load exports");
    } finally {
      setLoading(false);
    }
  }

  async function handleLogExport(e: React.FormEvent) {
    e.preventDefault();
    if (!customerId) { setFormError("Load a customer first"); return; }
    setFormLoading(true);
    setFormError("");
    try {
      await api.post("/api/receipt-exports", {
        customer_id: customerId,
        invoice_id: invoiceId,
        export_target: exportTarget,
      });
      setInvoiceId("");
      setExportTarget("csv");
      await loadExports();
    } catch (e: unknown) {
      setFormError(e instanceof Error ? e.message : "Failed to log export");
    } finally {
      setFormLoading(false);
    }
  }

  async function handleDelete(id: string) {
    setError("");
    try {
      await api.delete(`/api/receipt-exports/${id}`);
      setExports((prev) => prev.filter((ex) => ex.id !== id));
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to delete export");
    }
  }

  return (
    <div className="p-6 space-y-6 max-w-5xl mx-auto">
      <h1 className="text-2xl font-bold">Receipt Exports</h1>

      {/* Customer lookup */}
      <Card>
        <CardHeader>
          <CardTitle>Load Customer Exports</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex gap-2">
            <Input
              placeholder="Customer ID"
              value={customerIdInput}
              onChange={(e) => setCustomerIdInput(e.target.value)}
              className="max-w-sm"
            />
            <Button onClick={loadExports} disabled={loading}>
              {loading ? "Loading…" : "Load"}
            </Button>
          </div>
          {error && <p className="text-red-500 text-sm mt-2">{error}</p>}
        </CardContent>
      </Card>

      {/* Exports table */}
      {customerId && (
        <Card>
          <CardHeader>
            <CardTitle>Export History</CardTitle>
          </CardHeader>
          <CardContent>
            {loading ? (
              <p className="text-muted-foreground">Loading...</p>
            ) : exports.length === 0 ? (
              <p className="text-muted-foreground text-sm">No exports found.</p>
            ) : (
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Invoice ID</TableHead>
                    <TableHead>Export Target</TableHead>
                    <TableHead>Exported At</TableHead>
                    <TableHead>Ref</TableHead>
                    <TableHead>Actions</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {exports.map((ex) => (
                    <TableRow key={ex.id}>
                      <TableCell className="font-mono text-xs">
                        {truncate(ex.invoice_id, 12)}
                      </TableCell>
                      <TableCell>
                        <span
                          className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${targetBadgeClass[ex.export_target]}`}
                        >
                          {ex.export_target}
                        </span>
                      </TableCell>
                      <TableCell className="text-sm">
                        {new Date(ex.exported_at).toLocaleString()}
                      </TableCell>
                      <TableCell className="text-sm text-muted-foreground">
                        {ex.ref ?? "—"}
                      </TableCell>
                      <TableCell>
                        <Button
                          size="sm"
                          variant="destructive"
                          onClick={() => handleDelete(ex.id)}
                        >
                          Delete
                        </Button>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            )}
          </CardContent>
        </Card>
      )}

      {/* Log export form */}
      <Card>
        <CardHeader>
          <CardTitle>Log Export</CardTitle>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleLogExport} className="space-y-3">
            <div>
              <label className="text-sm font-medium">Invoice ID (UUID)</label>
              <Input
                value={invoiceId}
                onChange={(e) => setInvoiceId(e.target.value)}
                placeholder="xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
                required
              />
            </div>
            <div>
              <label className="text-sm font-medium">Export Target</label>
              <select
                className="flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm shadow-sm focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
                value={exportTarget}
                onChange={(e) => setExportTarget(e.target.value as ExportTarget)}
              >
                <option value="csv">CSV</option>
                <option value="splitwise">Splitwise</option>
                <option value="personal_capital">Personal Capital</option>
                <option value="ynab">YNAB</option>
              </select>
            </div>
            {formError && <p className="text-red-500 text-sm">{formError}</p>}
            <Button type="submit" disabled={formLoading}>
              {formLoading ? "Logging…" : "Log Export"}
            </Button>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}
