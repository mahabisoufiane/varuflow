"use client";
import { useState, useEffect } from "react";
import { useParams } from "next/navigation";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from "@/components/ui/table";

const API = process.env.NEXT_PUBLIC_API_URL;

interface BirthdayVoucher {
  id: string;
  customer_id: string;
  voucher_code: string;
  discount_type: string;
  discount_value: number;
  valid_from: string;
  valid_until: string;
  redeemed: boolean;
  generated_for_year: number;
}

export default function BirthdayVouchersPage() {
  const { locale } = useParams<{ locale: string }>();
  const [items, setItems] = useState<BirthdayVoucher[]>([]);
  const [filterCustomerId, setFilterCustomerId] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [newForm, setNewForm] = useState({
    customer_id: "", discount_type: "pct", discount_value: "",
    valid_from: "", valid_until: "", generated_for_year: new Date().getFullYear().toString(),
  });
  const [creating, setCreating] = useState(false);

  const token = typeof window !== "undefined" ? localStorage.getItem("auth_token") : "";

  async function fetchItems() {
    setLoading(true);
    setError("");
    try {
      const params = new URLSearchParams();
      if (filterCustomerId) params.set("customer_id", filterCustomerId);
      const res = await fetch(`${API}/api/birthday-vouchers?${params}`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (res.status === 401) { setError("Unauthorized."); return; }
      if (!res.ok) { setError("Failed to load vouchers."); return; }
      setItems(await res.json());
    } catch {
      setError("Network error.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { fetchItems(); }, []);

  async function createVoucher() {
    setCreating(true);
    setError("");
    try {
      const res = await fetch(`${API}/api/birthday-vouchers`, {
        method: "POST",
        headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
        body: JSON.stringify({
          ...newForm,
          discount_value: parseFloat(newForm.discount_value) || 0,
          generated_for_year: parseInt(newForm.generated_for_year),
        }),
      });
      if (res.status === 401) { setError("Unauthorized."); return; }
      if (!res.ok) { setError("Failed to generate voucher."); return; }
      setNewForm({ customer_id: "", discount_type: "pct", discount_value: "", valid_from: "", valid_until: "", generated_for_year: new Date().getFullYear().toString() });
      fetchItems();
    } catch {
      setError("Network error.");
    } finally {
      setCreating(false);
    }
  }

  async function redeemVoucher(id: string) {
    setError("");
    try {
      const res = await fetch(`${API}/api/birthday-vouchers/${id}/redeem`, {
        method: "POST",
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) { setError("Redeem failed."); return; }
      fetchItems();
    } catch {
      setError("Network error.");
    }
  }

  return (
    <div className="p-6 space-y-6">
      <h1 className="text-2xl font-bold">Birthday Vouchers</h1>
      <p className="text-muted-foreground">Generate and track birthday voucher codes for customers.</p>

      <Card>
        <CardHeader><CardTitle>Filter</CardTitle></CardHeader>
        <CardContent>
          <div className="flex gap-2">
            <Input
              placeholder="Customer ID (optional)"
              value={filterCustomerId}
              onChange={(e) => setFilterCustomerId(e.target.value)}
              className="max-w-sm"
            />
            <Button onClick={fetchItems} disabled={loading}>
              {loading ? "Loading..." : "Search"}
            </Button>
          </div>
          {error && <p className="text-red-500 text-sm mt-2">{error}</p>}
        </CardContent>
      </Card>

      {loading && <p className="text-muted-foreground">Loading...</p>}

      <Card>
        <CardHeader><CardTitle>Vouchers ({items.length})</CardTitle></CardHeader>
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Voucher Code</TableHead>
                <TableHead>Discount Type</TableHead>
                <TableHead>Value</TableHead>
                <TableHead>Valid From</TableHead>
                <TableHead>Valid Until</TableHead>
                <TableHead>Year</TableHead>
                <TableHead>Redeemed</TableHead>
                <TableHead>Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {items.map((item) => (
                <TableRow key={item.id}>
                  <TableCell className="font-mono font-bold">{item.voucher_code}</TableCell>
                  <TableCell>{item.discount_type === "pct" ? "Percent" : "Fixed"}</TableCell>
                  <TableCell>{item.discount_type === "pct" ? `${item.discount_value}%` : `${item.discount_value} kr`}</TableCell>
                  <TableCell>{item.valid_from}</TableCell>
                  <TableCell>{item.valid_until}</TableCell>
                  <TableCell>{item.generated_for_year}</TableCell>
                  <TableCell>
                    <Badge variant={item.redeemed ? "secondary" : "default"}>
                      {item.redeemed ? "Redeemed" : "Active"}
                    </Badge>
                  </TableCell>
                  <TableCell>
                    {!item.redeemed && (
                      <Button size="sm" variant="outline" onClick={() => redeemVoucher(item.id)}>
                        Redeem
                      </Button>
                    )}
                  </TableCell>
                </TableRow>
              ))}
              {items.length === 0 && !loading && (
                <TableRow>
                  <TableCell colSpan={8} className="text-center text-muted-foreground">No vouchers found.</TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>
        </CardContent>
      </Card>

      <Card>
        <CardHeader><CardTitle>Generate Voucher</CardTitle></CardHeader>
        <CardContent className="space-y-3">
          <Input placeholder="Customer ID" value={newForm.customer_id} onChange={(e) => setNewForm({ ...newForm, customer_id: e.target.value })} />
          <select
            className="w-full border rounded px-3 py-2 text-sm bg-background"
            value={newForm.discount_type}
            onChange={(e) => setNewForm({ ...newForm, discount_type: e.target.value })}
          >
            <option value="pct">Percent</option>
            <option value="fixed">Fixed Amount</option>
          </select>
          <Input type="number" placeholder="Discount Value" value={newForm.discount_value} onChange={(e) => setNewForm({ ...newForm, discount_value: e.target.value })} />
          <div className="grid grid-cols-2 gap-2">
            <div>
              <label className="text-xs text-muted-foreground">Valid From</label>
              <Input type="date" value={newForm.valid_from} onChange={(e) => setNewForm({ ...newForm, valid_from: e.target.value })} />
            </div>
            <div>
              <label className="text-xs text-muted-foreground">Valid Until</label>
              <Input type="date" value={newForm.valid_until} onChange={(e) => setNewForm({ ...newForm, valid_until: e.target.value })} />
            </div>
          </div>
          <Input type="number" placeholder="Generated For Year" value={newForm.generated_for_year} onChange={(e) => setNewForm({ ...newForm, generated_for_year: e.target.value })} />
          <Button onClick={createVoucher} disabled={creating}>
            {creating ? "Generating..." : "Generate Voucher"}
          </Button>
        </CardContent>
      </Card>
    </div>
  );
}
