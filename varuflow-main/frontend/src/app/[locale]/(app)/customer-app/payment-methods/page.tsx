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

interface PaymentMethod {
  id: string;
  customer_id: string;
  provider: string;
  card_brand: string;
  last_four: string;
  exp_month: number;
  exp_year: number;
  is_default: boolean;
  is_active: boolean;
  nickname: string | null;
}

export default function PaymentMethodsPage() {
  const { locale } = useParams<{ locale: string }>();
  const [items, setItems] = useState<PaymentMethod[]>([]);
  const [filterCustomerId, setFilterCustomerId] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const token = typeof window !== "undefined" ? localStorage.getItem("auth_token") : "";

  async function fetchItems() {
    setLoading(true);
    setError("");
    try {
      const params = new URLSearchParams();
      if (filterCustomerId) params.set("customer_id", filterCustomerId);
      const res = await fetch(`${API}/api/payment-methods?${params}`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (res.status === 401) { setError("Unauthorized."); return; }
      if (!res.ok) { setError("Failed to load payment methods."); return; }
      setItems(await res.json());
    } catch {
      setError("Network error.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { fetchItems(); }, []);

  async function setDefault(id: string) {
    setError("");
    try {
      const res = await fetch(`${API}/api/payment-methods/${id}/set-default`, {
        method: "POST",
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) { setError("Failed to set default."); return; }
      fetchItems();
    } catch {
      setError("Network error.");
    }
  }

  async function deleteItem(id: string) {
    setError("");
    try {
      const res = await fetch(`${API}/api/payment-methods/${id}`, {
        method: "DELETE",
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) { setError("Delete failed."); return; }
      setItems(items.filter((i) => i.id !== id));
    } catch {
      setError("Network error.");
    }
  }

  return (
    <div className="p-6 space-y-6">
      <h1 className="text-2xl font-bold">Saved Payment Methods</h1>
      <p className="text-muted-foreground">View and manage saved payment methods for customers.</p>

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
        <CardHeader><CardTitle>Payment Methods ({items.length})</CardTitle></CardHeader>
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Provider</TableHead>
                <TableHead>Card Brand</TableHead>
                <TableHead>Last 4</TableHead>
                <TableHead>Exp</TableHead>
                <TableHead>Default</TableHead>
                <TableHead>Active</TableHead>
                <TableHead>Nickname</TableHead>
                <TableHead>Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {items.map((item) => (
                <TableRow key={item.id}>
                  <TableCell>{item.provider}</TableCell>
                  <TableCell>{item.card_brand}</TableCell>
                  <TableCell>•••• {item.last_four}</TableCell>
                  <TableCell>{item.exp_month}/{item.exp_year}</TableCell>
                  <TableCell>
                    {item.is_default && <Badge>Default</Badge>}
                  </TableCell>
                  <TableCell>
                    <Badge variant={item.is_active ? "default" : "secondary"}>
                      {item.is_active ? "Active" : "Inactive"}
                    </Badge>
                  </TableCell>
                  <TableCell>{item.nickname ?? "—"}</TableCell>
                  <TableCell>
                    <div className="flex gap-1">
                      {!item.is_default && (
                        <Button size="sm" variant="outline" onClick={() => setDefault(item.id)}>
                          Set Default
                        </Button>
                      )}
                      <Button size="sm" variant="destructive" onClick={() => deleteItem(item.id)}>
                        Delete
                      </Button>
                    </div>
                  </TableCell>
                </TableRow>
              ))}
              {items.length === 0 && !loading && (
                <TableRow>
                  <TableCell colSpan={8} className="text-center text-muted-foreground">No payment methods found.</TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>
        </CardContent>
      </Card>
    </div>
  );
}
