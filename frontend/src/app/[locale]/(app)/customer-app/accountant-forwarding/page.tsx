"use client";
import { useState } from "react";
import { useParams } from "next/navigation";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";

const API = process.env.NEXT_PUBLIC_API_URL;

function getToken() {
  return typeof window !== "undefined"
    ? localStorage.getItem("auth_token") ?? ""
    : "";
}

interface ForwardingConfig {
  customer_id: string;
  accountant_email: string;
  is_active: boolean;
}

export default function AccountantForwardingPage() {
  const { locale } = useParams<{ locale: string }>();

  const [customerIdInput, setCustomerIdInput] = useState("");
  const [customerId, setCustomerId] = useState("");
  const [config, setConfig] = useState<ForwardingConfig | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const [emailInput, setEmailInput] = useState("");
  const [formLoading, setFormLoading] = useState(false);
  const [formError, setFormError] = useState("");

  async function loadConfig() {
    if (!customerIdInput.trim()) return;
    setCustomerId(customerIdInput.trim());
    setLoading(true);
    setError("");
    setConfig(null);
    try {
      const res = await fetch(
        `${API}/api/accountant-forwarding/${encodeURIComponent(customerIdInput.trim())}`,
        { headers: { Authorization: `Bearer ${getToken()}` } }
      );
      if (res.status === 404) {
        setConfig(null);
      } else if (!res.ok) {
        throw new Error(`Error ${res.status}`);
      } else {
        const data = await res.json();
        setConfig(data);
      }
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to load config");
    } finally {
      setLoading(false);
    }
  }

  async function handleConfigure(e: React.FormEvent) {
    e.preventDefault();
    if (!customerId) { setFormError("Load a customer first"); return; }
    setFormLoading(true);
    setFormError("");
    try {
      const res = await fetch(
        `${API}/api/accountant-forwarding/${customerId}`,
        {
          method: "PUT",
          headers: {
            Authorization: `Bearer ${getToken()}`,
            "Content-Type": "application/json",
          },
          body: JSON.stringify({ accountant_email: emailInput, is_active: true }),
        }
      );
      if (!res.ok) throw new Error(`Error ${res.status}`);
      const data = await res.json();
      setConfig(data);
      setEmailInput("");
    } catch (e: unknown) {
      setFormError(e instanceof Error ? e.message : "Failed to configure forwarding");
    } finally {
      setFormLoading(false);
    }
  }

  async function handleDeactivate() {
    if (!customerId) return;
    setError("");
    try {
      const res = await fetch(
        `${API}/api/accountant-forwarding/${customerId}`,
        {
          method: "DELETE",
          headers: { Authorization: `Bearer ${getToken()}` },
        }
      );
      if (!res.ok) throw new Error(`Error ${res.status}`);
      setConfig((prev) => prev ? { ...prev, is_active: false } : null);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to deactivate");
    }
  }

  async function handleReactivate() {
    if (!customerId || !config) return;
    setError("");
    try {
      const res = await fetch(
        `${API}/api/accountant-forwarding/${customerId}`,
        {
          method: "PUT",
          headers: {
            Authorization: `Bearer ${getToken()}`,
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            accountant_email: config.accountant_email,
            is_active: true,
          }),
        }
      );
      if (!res.ok) throw new Error(`Error ${res.status}`);
      const data = await res.json();
      setConfig(data);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to reactivate");
    }
  }

  return (
    <div className="p-6 space-y-6 max-w-2xl mx-auto">
      <h1 className="text-2xl font-bold">Invoice Forwarding</h1>

      {/* Info banner */}
      <div className="rounded-md border border-blue-200 bg-blue-50 px-4 py-3 text-sm text-blue-800">
        All invoices for this customer will be BCC&apos;d to the configured accountant email.
      </div>

      {/* Customer lookup */}
      <Card>
        <CardHeader>
          <CardTitle>Load Customer</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex gap-2">
            <Input
              placeholder="Customer ID"
              value={customerIdInput}
              onChange={(e) => setCustomerIdInput(e.target.value)}
              className="max-w-sm"
            />
            <Button onClick={loadConfig} disabled={loading}>
              {loading ? "Loading…" : "Load"}
            </Button>
          </div>
          {error && <p className="text-red-500 text-sm mt-2">{error}</p>}
        </CardContent>
      </Card>

      {/* Existing config */}
      {customerId && config && (
        <Card>
          <CardHeader>
            <CardTitle>Current Configuration</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <div className="flex items-center gap-3">
              <span className="text-sm font-medium">Accountant Email:</span>
              <span className="text-sm">{config.accountant_email}</span>
              <Badge variant={config.is_active ? "default" : "secondary"}>
                {config.is_active ? "Active" : "Inactive"}
              </Badge>
            </div>
            <div className="flex gap-2">
              {config.is_active ? (
                <Button variant="destructive" size="sm" onClick={handleDeactivate}>
                  Deactivate
                </Button>
              ) : (
                <Button size="sm" onClick={handleReactivate}>
                  Reactivate
                </Button>
              )}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Configure form (shown when not yet configured, or always available to update) */}
      {customerId && !config && (
        <Card>
          <CardHeader>
            <CardTitle>Configure Forwarding</CardTitle>
          </CardHeader>
          <CardContent>
            <form onSubmit={handleConfigure} className="space-y-3">
              <div>
                <label className="text-sm font-medium">Accountant Email</label>
                <Input
                  type="email"
                  value={emailInput}
                  onChange={(e) => setEmailInput(e.target.value)}
                  placeholder="accountant@example.com"
                  required
                />
              </div>
              {formError && (
                <p className="text-red-500 text-sm">{formError}</p>
              )}
              <Button type="submit" disabled={formLoading}>
                {formLoading ? "Saving…" : "Save Configuration"}
              </Button>
            </form>
          </CardContent>
        </Card>
      )}

      {customerId && config && (
        <Card>
          <CardHeader>
            <CardTitle>Update Email</CardTitle>
          </CardHeader>
          <CardContent>
            <form onSubmit={handleConfigure} className="space-y-3">
              <div>
                <label className="text-sm font-medium">New Accountant Email</label>
                <Input
                  type="email"
                  value={emailInput}
                  onChange={(e) => setEmailInput(e.target.value)}
                  placeholder="accountant@example.com"
                  required
                />
              </div>
              {formError && (
                <p className="text-red-500 text-sm">{formError}</p>
              )}
              <Button type="submit" disabled={formLoading}>
                {formLoading ? "Saving…" : "Update"}
              </Button>
            </form>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
