"use client";

import { useState, useEffect } from "react";
import { toast } from "sonner";

type TabId = "visma" | "bokio";
type Status = { connected: boolean; last_sync_at?: string; last_sync_status?: string };

export default function AccountingIntegrationPage() {
  const apiBase = process.env.NEXT_PUBLIC_API_URL!;
  const [tab, setTab] = useState<TabId>("visma");
  const [status, setStatus] = useState<Status>({ connected: false });
  const [loading, setLoading] = useState(false);
  const [syncing, setSyncing] = useState<string | null>(null);

  const [vismaKey, setVismaKey] = useState("");
  const [vismaCompany, setVismaCompany] = useState("");
  const [bokioKey, setBokioKey] = useState("");
  const [bokioWorkspace, setBokioWorkspace] = useState("");

  const fetch_ = (url: string, opts?: RequestInit) =>
    fetch(`${apiBase}${url}`, { credentials: "include", ...opts });

  async function loadStatus(provider: TabId) {
    setLoading(true);
    try {
      const res = await fetch_(`/api/integrations/${provider}/status`);
      if (res.ok) setStatus(await res.json());
    } catch {}
    setLoading(false);
  }

  useEffect(() => { loadStatus(tab); }, [tab]);

  async function connect() {
    setLoading(true);
    try {
      const body = tab === "visma"
        ? { api_key: vismaKey, company_id: vismaCompany }
        : { api_key: bokioKey, workspace_id: bokioWorkspace };
      const res = await fetch_(`/api/integrations/${tab}/connect`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      if (res.ok) {
        toast.success(`${tab === "visma" ? "Visma" : "Bokio"} connected`);
        await loadStatus(tab);
      } else {
        const err = await res.json();
        toast.error(err.detail || "Connection failed");
      }
    } catch {
      toast.error("Network error");
    }
    setLoading(false);
  }

  async function disconnect() {
    await fetch_(`/api/integrations/${tab}/disconnect`, { method: "DELETE" });
    toast.success("Disconnected");
    await loadStatus(tab);
  }

  async function sync(action: string) {
    setSyncing(action);
    try {
      const res = await fetch_(`/api/integrations/${tab}/${action}`, { method: "POST" });
      if (res.ok) {
        const data = await res.json();
        toast.success(data.message || `Synced: ${data.synced ?? 0} records`);
        await loadStatus(tab);
      } else {
        const err = await res.json();
        toast.error(err.detail || "Sync failed");
      }
    } catch {
      toast.error("Sync error");
    }
    setSyncing(null);
  }

  return (
    <div className="max-w-2xl space-y-6">
      <div>
        <h1 className="text-2xl font-semibold text-gray-900">Accounting Sync</h1>
        <p className="mt-1 text-sm text-gray-500">Push invoices and customers to your accounting software.</p>
      </div>

      <div className="flex gap-2 border-b border-gray-200">
        {(["visma", "bokio"] as TabId[]).map((t) => (
          <button key={t} onClick={() => setTab(t)}
            className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors ${
              tab === t ? "border-blue-600 text-blue-600" : "border-transparent text-gray-500 hover:text-gray-700"
            }`}>
            {t === "visma" ? "Visma eEkonomi" : "Bokio"}
          </button>
        ))}
      </div>

      <div className={`rounded-lg px-4 py-3 text-sm font-medium ${status.connected ? "bg-green-50 text-green-700" : "bg-gray-100 text-gray-500"}`}>
        {status.connected ? "Connected" : "Not connected"}
        {status.last_sync_at && <span className="ml-2 text-xs font-normal">Last sync: {new Date(status.last_sync_at).toLocaleString()}</span>}
      </div>

      {!status.connected ? (
        <div className="space-y-3">
          {tab === "visma" ? (
            <>
              <input className="input w-full" type="password" placeholder="API Key" value={vismaKey} onChange={e => setVismaKey(e.target.value)} />
              <input className="input w-full" placeholder="Company GUID" value={vismaCompany} onChange={e => setVismaCompany(e.target.value)} />
            </>
          ) : (
            <>
              <input className="input w-full" type="password" placeholder="API Key" value={bokioKey} onChange={e => setBokioKey(e.target.value)} />
              <input className="input w-full" placeholder="Workspace ID" value={bokioWorkspace} onChange={e => setBokioWorkspace(e.target.value)} />
              <p className="text-xs text-amber-600">Bokio Open API requires an invite from Bokio AB. Sync will return a stub response until approved.</p>
            </>
          )}
          <button onClick={connect} disabled={loading} className="btn-primary">
            {loading ? "Connecting…" : "Connect"}
          </button>
        </div>
      ) : (
        <div className="flex flex-wrap gap-3">
          <button onClick={() => sync("sync-invoices")} disabled={!!syncing} className="btn-primary">
            {syncing === "sync-invoices" ? "Syncing…" : "Sync Invoices"}
          </button>
          <button onClick={() => sync("sync-customers")} disabled={!!syncing} className="btn-secondary">
            {syncing === "sync-customers" ? "Syncing…" : "Sync Customers"}
          </button>
          <button onClick={disconnect} className="btn-danger-outline ml-auto">Disconnect</button>
        </div>
      )}
    </div>
  );
}
