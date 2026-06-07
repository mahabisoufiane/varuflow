"use client";
import { useState } from "react";
import { api } from "@/lib/api-client";
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

type WalletProvider = "apple_pay" | "google_pay";
type WalletStatus = "pending" | "completed" | "failed";

interface WalletPayment {
  id: string;
  provider: WalletProvider;
  amount: number;
  currency: string;
  status: WalletStatus;
  completed_at?: string;
  session_id?: string;
  customer_id: string;
  invoice_id?: string;
}

const statusClass: Record<WalletStatus, string> = {
  pending: "bg-yellow-100 text-yellow-800",
  completed: "bg-green-100 text-green-800",
  failed: "bg-red-100 text-red-800",
};

function truncate(str: string, len = 12) {
  return str.length > len ? str.slice(0, len) + "…" : str;
}

export default function WalletPaymentsPage() {
  const [customerIdInput, setCustomerIdInput] = useState("");
  const [statusFilter, setStatusFilter] = useState("all");
  const [items, setItems] = useState<WalletPayment[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  // Initiate session form
  const [formCustomerId, setFormCustomerId] = useState("");
  const [formInvoiceId, setFormInvoiceId] = useState("");
  const [formAmount, setFormAmount] = useState("");
  const [formCurrency, setFormCurrency] = useState("SEK");
  const [formProvider, setFormProvider] = useState<WalletProvider>("apple_pay");
  const [formLoading, setFormLoading] = useState(false);
  const [formError, setFormError] = useState("");

  async function loadPayments() {
    setLoading(true);
    setError("");
    try {
      const params = new URLSearchParams();
      if (customerIdInput.trim()) params.set("customer_id", customerIdInput.trim());
      if (statusFilter !== "all") params.set("status", statusFilter);
      const data = await api.get<WalletPayment[]>(`/api/wallet-payments?${params}`);
      setItems(data);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to load payments");
    } finally {
      setLoading(false);
    }
  }

  async function handleInitiate(e: React.FormEvent) {
    e.preventDefault();
    setFormLoading(true);
    setFormError("");
    try {
      const body: Record<string, unknown> = {
        customer_id: formCustomerId,
        amount: parseFloat(formAmount),
        currency: formCurrency,
        provider: formProvider,
      };
      if (formInvoiceId.trim()) body.invoice_id = formInvoiceId.trim();
      await api.post("/api/wallet-payments", body);
      setFormCustomerId("");
      setFormInvoiceId("");
      setFormAmount("");
      setFormCurrency("SEK");
      setFormProvider("apple_pay");
      await loadPayments();
    } catch (e: unknown) {
      setFormError(e instanceof Error ? e.message : "Failed to initiate session");
    } finally {
      setFormLoading(false);
    }
  }

  async function handleStatusChange(id: string, action: "complete" | "fail") {
    setError("");
    try {
      const endpoint = action === "complete" ? "mark-complete" : "mark-failed";
      await api.post(`/api/wallet-payments/${id}/${endpoint}`, {});
      await loadPayments();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : `Failed to mark ${action}`);
    }
  }

  const statuses = ["all", "pending", "completed", "failed"];

  return (
    <div className="p-6 space-y-6 max-w-5xl mx-auto">
      <h1 className="text-2xl font-bold">Wallet Payments (Apple / Google Pay)</h1>

      {/* Filters */}
      <Card>
        <CardHeader>
          <CardTitle>Filter Payments</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="flex gap-2 flex-wrap items-end">
            <div>
              <label className="text-sm font-medium">Customer ID</label>
              <Input
                placeholder="Optional"
                value={customerIdInput}
                onChange={(e) => setCustomerIdInput(e.target.value)}
                className="max-w-xs"
              />
            </div>
            <div className="flex gap-1">
              {statuses.map((s) => (
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
            <Button onClick={loadPayments} disabled={loading}>
              {loading ? "Loading…" : "Search"}
            </Button>
          </div>
          {error && <p className="text-red-500 text-sm">{error}</p>}
        </CardContent>
      </Card>

      {/* Payments table */}
      {items.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle>Payments</CardTitle>
          </CardHeader>
          <CardContent>
            {loading ? (
              <p className="text-muted-foreground">Loading...</p>
            ) : (
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Provider</TableHead>
                    <TableHead>Amount</TableHead>
                    <TableHead>Currency</TableHead>
                    <TableHead>Status</TableHead>
                    <TableHead>Completed At</TableHead>
                    <TableHead>Session ID</TableHead>
                    <TableHead>Actions</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {items.map((item) => (
                    <TableRow key={item.id}>
                      <TableCell>
                        <Badge variant="outline">
                          {item.provider === "apple_pay" ? "Apple Pay" : "Google Pay"}
                        </Badge>
                      </TableCell>
                      <TableCell>{item.amount.toLocaleString()}</TableCell>
                      <TableCell>{item.currency}</TableCell>
                      <TableCell>
                        <span
                          className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${statusClass[item.status]}`}
                        >
                          {item.status}
                        </span>
                      </TableCell>
                      <TableCell className="text-sm text-muted-foreground">
                        {item.completed_at
                          ? new Date(item.completed_at).toLocaleString()
                          : "—"}
                      </TableCell>
                      <TableCell className="font-mono text-xs text-muted-foreground">
                        {item.session_id ? truncate(item.session_id) : "—"}
                      </TableCell>
                      <TableCell>
                        {item.status === "pending" && (
                          <div className="flex gap-2">
                            <Button
                              size="sm"
                              variant="outline"
                              onClick={() => handleStatusChange(item.id, "complete")}
                            >
                              Mark Complete
                            </Button>
                            <Button
                              size="sm"
                              variant="destructive"
                              onClick={() => handleStatusChange(item.id, "fail")}
                            >
                              Mark Failed
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
      )}

      {/* Initiate session form */}
      <Card>
        <CardHeader>
          <CardTitle>Initiate Payment Session</CardTitle>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleInitiate} className="space-y-3">
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="text-sm font-medium">Customer ID</label>
                <Input
                  value={formCustomerId}
                  onChange={(e) => setFormCustomerId(e.target.value)}
                  placeholder="Customer ID"
                  required
                />
              </div>
              <div>
                <label className="text-sm font-medium">Invoice ID (optional)</label>
                <Input
                  value={formInvoiceId}
                  onChange={(e) => setFormInvoiceId(e.target.value)}
                  placeholder="UUID"
                />
              </div>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="text-sm font-medium">Amount</label>
                <Input
                  type="number"
                  step="0.01"
                  min="0"
                  value={formAmount}
                  onChange={(e) => setFormAmount(e.target.value)}
                  placeholder="0.00"
                  required
                />
              </div>
              <div>
                <label className="text-sm font-medium">Currency</label>
                <Input
                  value={formCurrency}
                  onChange={(e) => setFormCurrency(e.target.value)}
                  placeholder="SEK"
                  maxLength={3}
                  required
                />
              </div>
            </div>
            <div>
              <label className="text-sm font-medium">Provider</label>
              <select
                className="flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm shadow-sm focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
                value={formProvider}
                onChange={(e) => setFormProvider(e.target.value as WalletProvider)}
              >
                <option value="apple_pay">Apple Pay</option>
                <option value="google_pay">Google Pay</option>
              </select>
            </div>
            {formError && <p className="text-red-500 text-sm">{formError}</p>}
            <Button type="submit" disabled={formLoading}>
              {formLoading ? "Initiating…" : "Initiate Session"}
            </Button>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}
