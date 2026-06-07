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

interface Address {
  id: string;
  label: string;
  line1: string;
  line2?: string;
  city: string;
  postal_code: string;
  country: string;
  is_default: boolean;
}

export default function AddressesPage() {
  const [customerId, setCustomerId] = useState("");
  const [customerIdInput, setCustomerIdInput] = useState("");
  const [addresses, setAddresses] = useState<Address[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  // New address form state
  const [newLabel, setNewLabel] = useState("home");
  const [newLine1, setNewLine1] = useState("");
  const [newLine2, setNewLine2] = useState("");
  const [newCity, setNewCity] = useState("");
  const [newPostalCode, setNewPostalCode] = useState("");
  const [newCountry, setNewCountry] = useState("");
  const [newIsDefault, setNewIsDefault] = useState(false);
  const [formError, setFormError] = useState("");
  const [formLoading, setFormLoading] = useState(false);

  async function loadAddresses() {
    if (!customerIdInput.trim()) return;
    const cid = customerIdInput.trim();
    setCustomerId(cid);
    setLoading(true);
    setError("");
    try {
      const data = await api.get<Address[]>(`/api/addresses?customer_id=${encodeURIComponent(cid)}`);
      setAddresses(data);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to load addresses");
    } finally {
      setLoading(false);
    }
  }

  async function handleSetDefault(id: string) {
    setError("");
    try {
      await api.post(`/api/addresses/${id}/set-default`, {});
      await loadAddresses();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to set default");
    }
  }

  async function handleDelete(id: string) {
    setError("");
    try {
      await api.delete(`/api/addresses/${id}`);
      setAddresses((prev) => prev.filter((a) => a.id !== id));
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to delete address");
    }
  }

  async function handleAddAddress(e: React.FormEvent) {
    e.preventDefault();
    setFormError("");
    if (!customerId) {
      setFormError("Load a customer first");
      return;
    }
    setFormLoading(true);
    try {
      await api.post("/api/addresses", {
        customer_id: customerId,
        label: newLabel || "home",
        line1: newLine1,
        line2: newLine2 || undefined,
        city: newCity,
        postal_code: newPostalCode,
        country: newCountry,
        is_default: newIsDefault,
      });
      setNewLabel("home");
      setNewLine1("");
      setNewLine2("");
      setNewCity("");
      setNewPostalCode("");
      setNewCountry("");
      setNewIsDefault(false);
      await loadAddresses();
    } catch (e: unknown) {
      setFormError(e instanceof Error ? e.message : "Failed to add address");
    } finally {
      setFormLoading(false);
    }
  }

  return (
    <div className="p-6 space-y-6 max-w-4xl mx-auto">
      <h1 className="text-2xl font-bold">Address Book</h1>

      {/* Customer lookup */}
      <Card>
        <CardHeader>
          <CardTitle>Load Customer Addresses</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex gap-2">
            <Input
              placeholder="Customer ID"
              value={customerIdInput}
              onChange={(e) => setCustomerIdInput(e.target.value)}
              className="max-w-sm"
            />
            <Button onClick={loadAddresses} disabled={loading}>
              {loading ? "Loading…" : "Load"}
            </Button>
          </div>
          {error && <p className="text-red-500 text-sm mt-2">{error}</p>}
        </CardContent>
      </Card>

      {/* Addresses table */}
      {customerId && (
        <Card>
          <CardHeader>
            <CardTitle>Addresses</CardTitle>
          </CardHeader>
          <CardContent>
            {loading ? (
              <p className="text-muted-foreground">Loading...</p>
            ) : addresses.length === 0 ? (
              <p className="text-muted-foreground text-sm">No addresses found.</p>
            ) : (
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Label</TableHead>
                    <TableHead>Line 1</TableHead>
                    <TableHead>City</TableHead>
                    <TableHead>Country</TableHead>
                    <TableHead>Default</TableHead>
                    <TableHead>Actions</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {addresses.map((addr) => (
                    <TableRow key={addr.id}>
                      <TableCell className="capitalize">{addr.label}</TableCell>
                      <TableCell>{addr.line1}</TableCell>
                      <TableCell>{addr.city}</TableCell>
                      <TableCell>{addr.country.toUpperCase()}</TableCell>
                      <TableCell>
                        {addr.is_default && (
                          <Badge variant="secondary">Default</Badge>
                        )}
                      </TableCell>
                      <TableCell>
                        <div className="flex gap-2">
                          {!addr.is_default && (
                            <Button
                              size="sm"
                              variant="outline"
                              onClick={() => handleSetDefault(addr.id)}
                            >
                              Set Default
                            </Button>
                          )}
                          <Button
                            size="sm"
                            variant="destructive"
                            onClick={() => handleDelete(addr.id)}
                          >
                            Delete
                          </Button>
                        </div>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            )}
          </CardContent>
        </Card>
      )}

      {/* Add address form */}
      <Card>
        <CardHeader>
          <CardTitle>Add Address</CardTitle>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleAddAddress} className="space-y-3">
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="text-sm font-medium">Label</label>
                <Input
                  value={newLabel}
                  onChange={(e) => setNewLabel(e.target.value)}
                  placeholder="home"
                />
              </div>
              <div>
                <label className="text-sm font-medium">Country (2-char)</label>
                <Input
                  value={newCountry}
                  onChange={(e) => setNewCountry(e.target.value)}
                  placeholder="SE"
                  maxLength={2}
                  required
                />
              </div>
            </div>
            <div>
              <label className="text-sm font-medium">Line 1</label>
              <Input
                value={newLine1}
                onChange={(e) => setNewLine1(e.target.value)}
                placeholder="Street address"
                required
              />
            </div>
            <div>
              <label className="text-sm font-medium">Line 2 (optional)</label>
              <Input
                value={newLine2}
                onChange={(e) => setNewLine2(e.target.value)}
                placeholder="Apt, suite, etc."
              />
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="text-sm font-medium">City</label>
                <Input
                  value={newCity}
                  onChange={(e) => setNewCity(e.target.value)}
                  placeholder="City"
                  required
                />
              </div>
              <div>
                <label className="text-sm font-medium">Postal Code</label>
                <Input
                  value={newPostalCode}
                  onChange={(e) => setNewPostalCode(e.target.value)}
                  placeholder="12345"
                  required
                />
              </div>
            </div>
            <div className="flex items-center gap-2">
              <input
                type="checkbox"
                id="is_default"
                checked={newIsDefault}
                onChange={(e) => setNewIsDefault(e.target.checked)}
                className="h-4 w-4"
              />
              <label htmlFor="is_default" className="text-sm">
                Set as default address
              </label>
            </div>
            {formError && (
              <p className="text-red-500 text-sm">{formError}</p>
            )}
            <Button type="submit" disabled={formLoading}>
              {formLoading ? "Adding…" : "Add Address"}
            </Button>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}
