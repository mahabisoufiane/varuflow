"use client";

import { useState, useEffect } from "react";
import { toast } from "sonner";
import { api } from "@/lib/api-client";

type TabId = "shopify" | "woocommerce";
type Status = { connected: boolean; store_url?: string; last_sync_at?: string; last_sync_status?: string };

export default function ShopifyIntegrationPage() {
  const [tab, setTab] = useState<TabId>("shopify");
  const [status, setStatus] = useState<Status>({ connected: false });
  const [loading, setLoading] = useState(false);
  const [syncing, setSyncing] = useState<string | null>(null);

  // Shopify form
  const [shopStore, setShopStore] = useState("");
  const [shopToken, setShopToken] = useState("");
  // WooCommerce form
  const [wooStore, setWooStore] = useState("");
  const [wooKey, setWooKey] = useState("");
  const [wooSecret, setWooSecret] = useState("");

  async function loadStatus(provider: TabId) {
    setLoading(true);
    try {
      const data = await api.get<Status>(`/api/integrations/${provider}/status`);
      setStatus(data);
    } catch {}
    setLoading(false);
  }

  useEffect(() => { loadStatus(tab); }, [tab]);

  async function connect() {
    setLoading(true);
    try {
      const body = tab === "shopify"
        ? { store_url: shopStore, access_token: shopToken }
        : { store_url: wooStore, consumer_key: wooKey, consumer_secret: wooSecret };
      await api.post(`/api/integrations/${tab}/connect`, body);
      toast.success(`${tab === "shopify" ? "Shopify" : "WooCommerce"} connected`);
      await loadStatus(tab);
    } catch (err: any) {
      toast.error(err.message || "Connection failed");
    }
    setLoading(false);
  }

  async function disconnect() {
    await api.delete(`/api/integrations/${tab}/disconnect`).catch(() => {});
    toast.success("Disconnected");
    await loadStatus(tab);
  }

  async function sync(action: "sync-orders" | "sync-inventory") {
    setSyncing(action);
    try {
      const data = await api.post<{ message?: string }>(`/api/integrations/${tab}/${action}`, {});
      toast.success(data.message || "Sync complete");
      await loadStatus(tab);
    } catch (err: any) {
      toast.error(err.message || "Sync failed");
    }
    setSyncing(null);
  }

  return (
    <div className="max-w-2xl space-y-6">
      <div>
        <h1 className="text-2xl font-semibold text-gray-900">E-commerce Sync</h1>
        <p className="mt-1 text-sm text-gray-500">Import orders as invoices and push inventory levels.</p>
      </div>

      {/* Tabs */}
      <div className="flex gap-2 border-b border-gray-200">
        {(["shopify", "woocommerce"] as TabId[]).map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={`px-4 py-2 text-sm font-medium capitalize border-b-2 transition-colors ${
              tab === t ? "border-blue-600 text-blue-600" : "border-transparent text-gray-500 hover:text-gray-700"
            }`}
          >
            {t === "shopify" ? "Shopify" : "WooCommerce"}
          </button>
        ))}
      </div>

      {/* Status */}
      <div className={`rounded-lg px-4 py-3 text-sm font-medium ${status.connected ? "bg-green-50 text-green-700" : "bg-gray-100 text-gray-500"}`}>
        {status.connected ? `Connected — ${status.store_url}` : "Not connected"}
        {status.last_sync_at && <span className="ml-2 text-xs font-normal">Last sync: {new Date(status.last_sync_at).toLocaleString()}</span>}
      </div>

      {/* Connect form */}
      {!status.connected ? (
        <div className="space-y-3">
          {tab === "shopify" ? (
            <>
              <input className="input w-full" placeholder="my-store.myshopify.com" value={shopStore} onChange={e => setShopStore(e.target.value)} />
              <input className="input w-full" type="password" placeholder="Access token (shpat_...)" value={shopToken} onChange={e => setShopToken(e.target.value)} />
            </>
          ) : (
            <>
              <input className="input w-full" placeholder="https://mystore.com" value={wooStore} onChange={e => setWooStore(e.target.value)} />
              <input className="input w-full" placeholder="Consumer key (ck_...)" value={wooKey} onChange={e => setWooKey(e.target.value)} />
              <input className="input w-full" type="password" placeholder="Consumer secret (cs_...)" value={wooSecret} onChange={e => setWooSecret(e.target.value)} />
            </>
          )}
          <button onClick={connect} disabled={loading} className="btn-primary">
            {loading ? "Connecting…" : "Connect"}
          </button>
        </div>
      ) : (
        <div className="flex flex-wrap gap-3">
          <button
            onClick={() => sync("sync-orders")}
            disabled={!!syncing}
            className="btn-primary"
          >
            {syncing === "sync-orders" ? "Syncing…" : "Sync Orders"}
          </button>
          <button
            onClick={() => sync("sync-inventory")}
            disabled={!!syncing}
            className="btn-secondary"
          >
            {syncing === "sync-inventory" ? "Syncing…" : "Push Inventory"}
          </button>
          <button onClick={disconnect} className="btn-danger-outline ml-auto">
            Disconnect
          </button>
        </div>
      )}

      {status.last_sync_status && (
        <p className="text-xs text-gray-500">
          Last sync status: <span className={status.last_sync_status === "success" ? "text-green-600" : "text-amber-600"}>{status.last_sync_status}</span>
        </p>
      )}
    </div>
  );
}
