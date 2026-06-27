"use client";
import { useState } from "react";
import { useParams } from "next/navigation";
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

const API = process.env.NEXT_PUBLIC_API_URL;

function getToken() {
  return typeof window !== "undefined"
    ? localStorage.getItem("auth_token") ?? ""
    : "";
}

interface PriceOverride {
  id: string;
  product_id: string;
  override_price: number;
  notes?: string;
  created_at: string;
}

interface PricingSummary {
  count: number;
  avg_discount: number;
}

function truncate(str: string, len = 12) {
  return str.length > len ? str.slice(0, len) + "…" : str;
}

export default function NegotiatedPricingPage() {
  const { locale } = useParams<{ locale: string }>();

  const [customerIdInput, setCustomerIdInput] = useState("");
  const [customerId, setCustomerId] = useState("");
  const [overrides, setOverrides] = useState<PriceOverride[]>([]);
  const [summary, setSummary] = useState<PricingSummary | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  async function loadPricing() {
    if (!customerIdInput.trim()) return;
    const id = customerIdInput.trim();
    setCustomerId(id);
    setLoading(true);
    setError("");
    try {
      const [overridesRes, summaryRes] = await Promise.all([
        fetch(`${API}/api/negotiated-pricing/${id}`, {
          headers: { Authorization: `Bearer ${getToken()}` },
        }),
        fetch(`${API}/api/negotiated-pricing/${id}/summary`, {
          headers: { Authorization: `Bearer ${getToken()}` },
        }),
      ]);
      if (!overridesRes.ok) throw new Error(`Error ${overridesRes.status}`);
      if (!summaryRes.ok) throw new Error(`Error ${summaryRes.status}`);
      const [overridesData, summaryData] = await Promise.all([
        overridesRes.json(),
        summaryRes.json(),
      ]);
      setOverrides(overridesData);
      setSummary(summaryData);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to load pricing data");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="p-6 space-y-6 max-w-4xl mx-auto">
      <h1 className="text-2xl font-bold">Negotiated Pricing</h1>

      {/* Customer lookup */}
      <Card>
        <CardHeader>
          <CardTitle>Load Customer Pricing</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex gap-2">
            <Input
              placeholder="Customer ID"
              value={customerIdInput}
              onChange={(e) => setCustomerIdInput(e.target.value)}
              className="max-w-sm"
            />
            <Button onClick={loadPricing} disabled={loading}>
              {loading ? "Loading…" : "Load"}
            </Button>
          </div>
          {error && <p className="text-red-500 text-sm mt-2">{error}</p>}
        </CardContent>
      </Card>

      {/* Summary card */}
      {customerId && summary && (
        <Card>
          <CardContent className="pt-4">
            <p className="text-sm text-muted-foreground">
              <span className="font-semibold text-foreground">
                {summary.count}
              </span>{" "}
              custom price override{summary.count !== 1 ? "s" : ""}, avg{" "}
              <span className="font-semibold text-foreground">
                {summary.avg_discount.toFixed(1)}%
              </span>{" "}
              below standard pricing
            </p>
          </CardContent>
        </Card>
      )}

      {/* Overrides table */}
      {customerId && (
        <Card>
          <CardHeader>
            <CardTitle>Price Overrides</CardTitle>
          </CardHeader>
          <CardContent>
            {loading ? (
              <p className="text-muted-foreground">Loading...</p>
            ) : overrides.length === 0 ? (
              <p className="text-muted-foreground text-sm">
                No price overrides for this customer.
              </p>
            ) : (
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Product ID</TableHead>
                    <TableHead>Override Price</TableHead>
                    <TableHead>Notes</TableHead>
                    <TableHead>Created At</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {overrides.map((ov) => (
                    <TableRow key={ov.id}>
                      <TableCell className="font-mono text-xs">
                        {truncate(ov.product_id)}
                      </TableCell>
                      <TableCell className="font-medium">
                        {ov.override_price.toLocaleString()}
                      </TableCell>
                      <TableCell className="text-sm text-muted-foreground">
                        {ov.notes ?? "—"}
                      </TableCell>
                      <TableCell className="text-sm text-muted-foreground">
                        {new Date(ov.created_at).toLocaleDateString()}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            )}
          </CardContent>
        </Card>
      )}
    </div>
  );
}
