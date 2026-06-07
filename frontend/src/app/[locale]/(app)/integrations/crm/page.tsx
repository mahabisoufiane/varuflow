"use client";

import { useState, useEffect } from "react";
import { toast } from "sonner";
import { api } from "@/lib/api-client";

type TabId = "hubspot" | "salesforce";
type Status = { connected: boolean; last_sync_at?: string; last_sync_status?: string };

export default function CrmIntegrationPage() {
  const [tab, setTab] = useState<TabId>("hubspot");
  const [status, setStatus] = useState<Status>({ connected: false });
  const [loading, setLoading] = useState(false);
  const [syncing, setSyncing] = useState<string | null>(null);

  const [hubToken, setHubToken] = useState("");
  const [sfInstance, setSfInstance] = useState("");
  const [sfToken, setSfToken] = useState("");
  const [sfRefresh, setSfRefresh] = useState("");

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
      const body = tab === "hubspot"
        ? { access_token: hubToken }
        : { instance_url: sfInstance, access_token: sfToken, refresh_token: sfRefresh || undefined };
      await api.post(`/api/integrations/${tab}/connect`, body);
      toast.success(`${tab === "hubspot" ? "HubSpot" : "Salesforce"} connected`);
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

  async function sync(action: string) {
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

  const actions = tab === "hubspot"
    ? [
        { key: "sync-customers", label: "Push Customers" },
        { key: "sync-deals", label: "Push Deals" },
        { key: "pull-contacts", label: "Pull Contacts" },
      ]
    : [
        { key: "sync-customers", label: "Push Accounts" },
        { key: "sync-deals", label: "Push Opportunities" },
      ];

  return (
    <div className="max-w-2xl space-y-6">
      <div>
        <h1 className="text-2xl font-semibold text-gray-900">CRM Sync</h1>
        <p className="mt-1 text-sm text-gray-500">Sync customers and deals between Varuflow and your CRM.</p>
      </div>

      <div className="flex gap-2 border-b border-gray-200">
        {(["hubspot", "salesforce"] as TabId[]).map((t) => (
          <button key={t} onClick={() => setTab(t)}
            className={`px-4 py-2 text-sm font-medium capitalize border-b-2 transition-colors ${
              tab === t ? "border-blue-600 text-blue-600" : "border-transparent text-gray-500 hover:text-gray-700"
            }`}>
            {t === "hubspot" ? "HubSpot" : "Salesforce"}
          </button>
        ))}
      </div>

      <div className={`rounded-lg px-4 py-3 text-sm font-medium ${status.connected ? "bg-green-50 text-green-700" : "bg-gray-100 text-gray-500"}`}>
        {status.connected ? "Connected" : "Not connected"}
        {status.last_sync_at && <span className="ml-2 text-xs font-normal">Last sync: {new Date(status.last_sync_at).toLocaleString()}</span>}
      </div>

      {!status.connected ? (
        <div className="space-y-3">
          {tab === "hubspot" ? (
            <input className="input w-full" type="password" placeholder="Private App Token" value={hubToken} onChange={e => setHubToken(e.target.value)} />
          ) : (
            <>
              <input className="input w-full" placeholder="Instance URL (https://myorg.salesforce.com)" value={sfInstance} onChange={e => setSfInstance(e.target.value)} />
              <input className="input w-full" type="password" placeholder="Access Token" value={sfToken} onChange={e => setSfToken(e.target.value)} />
              <input className="input w-full" type="password" placeholder="Refresh Token (optional)" value={sfRefresh} onChange={e => setSfRefresh(e.target.value)} />
            </>
          )}
          <button onClick={connect} disabled={loading} className="btn-primary">
            {loading ? "Connecting…" : "Connect"}
          </button>
        </div>
      ) : (
        <div className="flex flex-wrap gap-3">
          {actions.map(a => (
            <button key={a.key} onClick={() => sync(a.key)} disabled={!!syncing} className="btn-secondary">
              {syncing === a.key ? "Syncing…" : a.label}
            </button>
          ))}
          <button onClick={disconnect} className="btn-danger-outline ml-auto">Disconnect</button>
        </div>
      )}
    </div>
  );
}
