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

function purchaseStatusClass(status: string) {
  const map: Record<string, string> = {
    active: "bg-green-100 text-green-800",
    claimed: "bg-orange-100 text-orange-800",
    expired: "bg-gray-100 text-gray-800",
    refunded: "bg-red-100 text-red-800",
  };
  return map[status] ?? "bg-gray-100 text-gray-800";
}

interface InsuranceAddon {
  id: string;
  name: string;
  service_id?: string;
  price: number;
  active: boolean;
  coverage_description: string;
}

interface InsurancePurchase {
  id: string;
  customer_id: string;
  addon_id: string;
  addon_name?: string;
  amount_paid: number;
  status: string;
  policy_ref?: string;
  expires_at?: string;
}

export default function InsurancePage() {
  const [addons, setAddons] = useState<InsuranceAddon[]>([]);
  const [addonsLoading, setAddonsLoading] = useState(false);
  const [addonsError, setAddonsError] = useState("");

  const [purchases, setPurchases] = useState<InsurancePurchase[]>([]);
  const [customerFilter, setCustomerFilter] = useState("");
  const [purchasesLoading, setPurchasesLoading] = useState(false);
  const [purchasesError, setPurchasesError] = useState("");

  // Add addon form
  const [fName, setFName] = useState("");
  const [fServiceId, setFServiceId] = useState("");
  const [fPrice, setFPrice] = useState("");
  const [fDescription, setFDescription] = useState("");
  const [fCoverage, setFCoverage] = useState("");
  const [addonFormLoading, setAddonFormLoading] = useState(false);
  const [addonFormError, setAddonFormError] = useState("");

  async function fetchAddons() {
    setAddonsLoading(true);
    setAddonsError("");
    try {
      setAddons(await api.get<InsuranceAddon[]>("/api/insurance/addons"));
    } catch (e: unknown) {
      setAddonsError(e instanceof Error ? e.message : "Failed to load add-ons");
    } finally {
      setAddonsLoading(false);
    }
  }

  async function fetchPurchases() {
    setPurchasesLoading(true);
    setPurchasesError("");
    try {
      const params = new URLSearchParams();
      if (customerFilter) params.set("customer_id", customerFilter);
      setPurchases(await api.get<InsurancePurchase[]>(`/api/insurance/purchases?${params}`));
    } catch (e: unknown) {
      setPurchasesError(e instanceof Error ? e.message : "Failed to load purchases");
    } finally {
      setPurchasesLoading(false);
    }
  }

  useEffect(() => {
    fetchAddons();
    fetchPurchases();
  }, []);

  async function toggleAddon(id: string, active: boolean) {
    try {
      await api.patch<InsuranceAddon>(`/api/insurance/addons/${id}`, { active: !active });
      fetchAddons();
    } catch (e: unknown) {
      setAddonsError(e instanceof Error ? e.message : "Action failed");
    }
  }

  async function handleAddonCreate(e: React.FormEvent) {
    e.preventDefault();
    setAddonFormLoading(true);
    setAddonFormError("");
    try {
      const body: Record<string, string | number> = {
        name: fName,
        price: parseFloat(fPrice),
        description: fDescription,
        coverage_description: fCoverage,
      };
      if (fServiceId) body.service_id = fServiceId;
      await api.post<InsuranceAddon>("/api/insurance/addons", body);
      setFName(""); setFServiceId(""); setFPrice(""); setFDescription(""); setFCoverage("");
      fetchAddons();
    } catch (e: unknown) {
      setAddonFormError(e instanceof Error ? e.message : "Failed to create add-on");
    } finally {
      setAddonFormLoading(false);
    }
  }

  async function handlePurchaseAction(id: string, action: "claim" | "refund") {
    try {
      await api.post(`/api/insurance/purchases/${id}/${action}`, {});
      fetchPurchases();
    } catch (e: unknown) {
      setPurchasesError(e instanceof Error ? e.message : "Action failed");
    }
  }

  return (
    <div className="p-6 space-y-8">
      <h1 className="text-2xl font-bold">Insurance Add-ons</h1>

      {/* Add-on Definitions */}
      <section className="space-y-4">
        <h2 className="text-xl font-semibold">Add-on Definitions</h2>
        {addonsError && <p className="text-red-500 text-sm">{addonsError}</p>}
        {addonsLoading ? (
          <p className="text-muted-foreground">Loading...</p>
        ) : (
          <Card>
            <CardContent className="p-0">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Name</TableHead>
                    <TableHead>Service ID</TableHead>
                    <TableHead>Price</TableHead>
                    <TableHead>Active</TableHead>
                    <TableHead>Coverage Description</TableHead>
                    <TableHead>Actions</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {addons.length === 0 && (
                    <TableRow>
                      <TableCell colSpan={6} className="text-center text-muted-foreground">
                        No add-ons defined.
                      </TableCell>
                    </TableRow>
                  )}
                  {addons.map((a) => (
                    <TableRow key={a.id}>
                      <TableCell className="font-medium">{a.name}</TableCell>
                      <TableCell className="text-xs">{a.service_id ?? "—"}</TableCell>
                      <TableCell>{(a.price / 100).toFixed(2)}</TableCell>
                      <TableCell>
                        <Badge variant={a.active ? "default" : "secondary"}>
                          {a.active ? "Active" : "Inactive"}
                        </Badge>
                      </TableCell>
                      <TableCell className="text-xs max-w-xs truncate" title={a.coverage_description}>
                        {a.coverage_description.length > 80
                          ? a.coverage_description.slice(0, 80) + "…"
                          : a.coverage_description}
                      </TableCell>
                      <TableCell>
                        <Button size="sm" variant="outline" onClick={() => toggleAddon(a.id, a.active)}>
                          {a.active ? "Deactivate" : "Activate"}
                        </Button>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </CardContent>
          </Card>
        )}

        <Card>
          <CardHeader>
            <CardTitle>Add Insurance Option</CardTitle>
          </CardHeader>
          <CardContent>
            <form onSubmit={handleAddonCreate} className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div className="space-y-1">
                <label className="text-sm font-medium">Name *</label>
                <Input required value={fName} onChange={(e) => setFName(e.target.value)} placeholder="e.g. Basic Cover" />
              </div>
              <div className="space-y-1">
                <label className="text-sm font-medium">Service ID (optional)</label>
                <Input value={fServiceId} onChange={(e) => setFServiceId(e.target.value)} placeholder="service UUID" />
              </div>
              <div className="space-y-1">
                <label className="text-sm font-medium">Price (in cents) *</label>
                <Input required type="number" min="0" value={fPrice} onChange={(e) => setFPrice(e.target.value)} placeholder="e.g. 999" />
              </div>
              <div className="space-y-1">
                <label className="text-sm font-medium">Description *</label>
                <Input required value={fDescription} onChange={(e) => setFDescription(e.target.value)} placeholder="Short description" />
              </div>
              <div className="space-y-1 sm:col-span-2">
                <label className="text-sm font-medium">Coverage Description *</label>
                <Input required value={fCoverage} onChange={(e) => setFCoverage(e.target.value)} placeholder="What is covered" />
              </div>
              {addonFormError && <p className="text-red-500 text-sm col-span-2">{addonFormError}</p>}
              <div className="col-span-2">
                <Button type="submit" disabled={addonFormLoading}>
                  {addonFormLoading ? "Saving…" : "Add Insurance Option"}
                </Button>
              </div>
            </form>
          </CardContent>
        </Card>
      </section>

      {/* Customer Purchases */}
      <section className="space-y-4">
        <h2 className="text-xl font-semibold">Customer Purchases</h2>
        <div className="flex gap-2 items-center">
          <Input
            placeholder="Filter by customer ID"
            value={customerFilter}
            onChange={(e) => setCustomerFilter(e.target.value)}
            className="w-56"
          />
          <Button size="sm" onClick={fetchPurchases}>
            Search
          </Button>
        </div>
        {purchasesError && <p className="text-red-500 text-sm">{purchasesError}</p>}
        {purchasesLoading ? (
          <p className="text-muted-foreground">Loading...</p>
        ) : (
          <Card>
            <CardContent className="p-0">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Customer ID</TableHead>
                    <TableHead>Addon Name</TableHead>
                    <TableHead>Amount Paid</TableHead>
                    <TableHead>Status</TableHead>
                    <TableHead>Policy Ref</TableHead>
                    <TableHead>Expires At</TableHead>
                    <TableHead>Actions</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {purchases.length === 0 && (
                    <TableRow>
                      <TableCell colSpan={7} className="text-center text-muted-foreground">
                        No purchases found.
                      </TableCell>
                    </TableRow>
                  )}
                  {purchases.map((p) => (
                    <TableRow key={p.id}>
                      <TableCell className="font-mono text-xs">{p.customer_id}</TableCell>
                      <TableCell>{p.addon_name ?? p.addon_id}</TableCell>
                      <TableCell>{(p.amount_paid / 100).toFixed(2)}</TableCell>
                      <TableCell>
                        <span
                          className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${purchaseStatusClass(p.status)}`}
                        >
                          {p.status}
                        </span>
                      </TableCell>
                      <TableCell className="text-xs">{p.policy_ref ?? "—"}</TableCell>
                      <TableCell className="text-xs">
                        {p.expires_at ? new Date(p.expires_at).toLocaleDateString() : "—"}
                      </TableCell>
                      <TableCell className="space-x-2">
                        {p.status === "active" && (
                          <Button size="sm" variant="outline" onClick={() => handlePurchaseAction(p.id, "claim")}>
                            Claim
                          </Button>
                        )}
                        {p.status !== "refunded" && (
                          <Button size="sm" variant="outline" onClick={() => handlePurchaseAction(p.id, "refund")}>
                            Refund
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
      </section>
    </div>
  );
}
