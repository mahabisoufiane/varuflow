"use client";
import { useState, useEffect } from "react";
import { useParams } from "next/navigation";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";

const API = process.env.NEXT_PUBLIC_API_URL;
function getToken() {
  return typeof window !== "undefined" ? localStorage.getItem("auth_token") ?? "" : "";
}

interface KPI {
  id: string;
  label: string;
  value: string | number;
  change_pct?: number;
}

interface KpiConfig {
  kpi_ids: string[];
  notification_deep_links_enabled: boolean;
  refresh_interval_minutes: number;
}

interface PushToken {
  id: string;
  token: string;
  platform: string;
  device_label: string;
}

export default function MobileDashboardPage() {
  const params = useParams();

  const [kpis, setKpis] = useState<KPI[]>([]);
  const [kpisLoading, setKpisLoading] = useState(false);
  const [kpisError, setKpisError] = useState("");

  const [config, setConfig] = useState<KpiConfig | null>(null);
  const [configLoading, setConfigLoading] = useState(false);
  const [configError, setConfigError] = useState("");

  // Config form
  const [kpiIds, setKpiIds] = useState("");
  const [notifEnabled, setNotifEnabled] = useState(false);
  const [refreshInterval, setRefreshInterval] = useState(5);
  const [savingConfig, setSavingConfig] = useState(false);

  // Push tokens
  const [pushTokens, setPushTokens] = useState<PushToken[]>([]);
  const [ptLoading, setPtLoading] = useState(false);
  const [ptError, setPtError] = useState("");
  const [ptToken, setPtToken] = useState("");
  const [ptPlatform, setPtPlatform] = useState("ios");
  const [ptLabel, setPtLabel] = useState("");
  const [ptSubmitting, setPtSubmitting] = useState(false);

  async function fetchKpis() {
    setKpisLoading(true);
    setKpisError("");
    try {
      const res = await fetch(`${API}/api/mobile/kpis`, {
        headers: { Authorization: `Bearer ${getToken()}` },
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      setKpis(await res.json());
    } catch (e: unknown) {
      setKpisError(e instanceof Error ? e.message : "Failed to load KPIs");
    } finally {
      setKpisLoading(false);
    }
  }

  async function fetchConfig() {
    setConfigLoading(true);
    setConfigError("");
    try {
      const res = await fetch(`${API}/api/mobile/kpi-config`, {
        headers: { Authorization: `Bearer ${getToken()}` },
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data: KpiConfig = await res.json();
      setConfig(data);
      setKpiIds(data.kpi_ids.join(", "));
      setNotifEnabled(data.notification_deep_links_enabled);
      setRefreshInterval(data.refresh_interval_minutes);
    } catch (e: unknown) {
      setConfigError(e instanceof Error ? e.message : "Failed to load config");
    } finally {
      setConfigLoading(false);
    }
  }

  async function fetchPushTokens() {
    setPtLoading(true);
    setPtError("");
    try {
      const res = await fetch(`${API}/api/mobile/push-tokens`, {
        headers: { Authorization: `Bearer ${getToken()}` },
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      setPushTokens(await res.json());
    } catch (e: unknown) {
      setPtError(e instanceof Error ? e.message : "Failed to load push tokens");
    } finally {
      setPtLoading(false);
    }
  }

  useEffect(() => {
    fetchKpis();
    fetchConfig();
    fetchPushTokens();
  }, []);

  async function saveConfig(e: React.FormEvent) {
    e.preventDefault();
    setSavingConfig(true);
    setConfigError("");
    try {
      const res = await fetch(`${API}/api/mobile/kpi-config`, {
        method: "PUT",
        headers: {
          Authorization: `Bearer ${getToken()}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          kpi_ids: kpiIds.split(",").map((s) => s.trim()).filter(Boolean),
          notification_deep_links_enabled: notifEnabled,
          refresh_interval_minutes: refreshInterval,
        }),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      await fetchConfig();
    } catch (e: unknown) {
      setConfigError(e instanceof Error ? e.message : "Failed to save config");
    } finally {
      setSavingConfig(false);
    }
  }

  async function registerToken(e: React.FormEvent) {
    e.preventDefault();
    setPtSubmitting(true);
    setPtError("");
    try {
      const res = await fetch(`${API}/api/mobile/push-tokens`, {
        method: "POST",
        headers: {
          Authorization: `Bearer ${getToken()}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ token: ptToken, platform: ptPlatform, device_label: ptLabel }),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      setPtToken("");
      setPtLabel("");
      await fetchPushTokens();
    } catch (e: unknown) {
      setPtError(e instanceof Error ? e.message : "Failed to register token");
    } finally {
      setPtSubmitting(false);
    }
  }

  async function deleteToken(id: string) {
    try {
      const res = await fetch(`${API}/api/mobile/push-tokens/${id}`, {
        method: "DELETE",
        headers: { Authorization: `Bearer ${getToken()}` },
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      await fetchPushTokens();
    } catch (e: unknown) {
      setPtError(e instanceof Error ? e.message : "Failed to delete token");
    }
  }

  return (
    <div className="p-6 space-y-6">
      <h1 className="text-2xl font-bold">Mobile Dashboard KPIs</h1>

      {/* Live KPIs */}
      <Card>
        <CardHeader className="flex flex-row items-center justify-between">
          <CardTitle>Live KPIs</CardTitle>
          <Button variant="outline" size="sm" onClick={fetchKpis} disabled={kpisLoading}>
            {kpisLoading ? "Refreshing…" : "Refresh"}
          </Button>
        </CardHeader>
        <CardContent>
          {kpisError && <p className="text-red-500 text-sm">{kpisError}</p>}
          {kpisLoading && !kpis.length ? (
            <p className="text-muted-foreground">Loading…</p>
          ) : (
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
              {kpis.map((kpi) => (
                <div key={kpi.id} className="border rounded-lg p-4 space-y-1">
                  <p className="text-xs text-muted-foreground uppercase tracking-wide">{kpi.label}</p>
                  <p className="text-2xl font-bold">{kpi.value}</p>
                  {kpi.change_pct !== undefined && (
                    <p
                      className={`text-sm font-medium ${
                        kpi.change_pct >= 0 ? "text-green-600" : "text-red-600"
                      }`}
                    >
                      {kpi.change_pct >= 0 ? "+" : ""}
                      {kpi.change_pct}%
                    </p>
                  )}
                </div>
              ))}
              {kpis.length === 0 && (
                <p className="text-muted-foreground col-span-4">No KPIs configured.</p>
              )}
            </div>
          )}
        </CardContent>
      </Card>

      {/* KPI Config */}
      <Card>
        <CardHeader>
          <CardTitle>KPI Configuration</CardTitle>
        </CardHeader>
        <CardContent>
          {configLoading ? (
            <p className="text-muted-foreground">Loading…</p>
          ) : (
            <form onSubmit={saveConfig} className="space-y-4">
              <div>
                <label className="text-sm font-medium block mb-1">KPI IDs (comma-separated)</label>
                <Input
                  value={kpiIds}
                  onChange={(e) => setKpiIds(e.target.value)}
                  placeholder="revenue_mtd, invoices_week, new_customers"
                />
              </div>
              <div className="flex items-center gap-2">
                <input
                  type="checkbox"
                  id="notif"
                  checked={notifEnabled}
                  onChange={(e) => setNotifEnabled(e.target.checked)}
                  className="h-4 w-4"
                />
                <label htmlFor="notif" className="text-sm">
                  Enable notification deep links
                </label>
              </div>
              <div>
                <label className="text-sm font-medium block mb-1">Refresh interval (minutes)</label>
                <Input
                  type="number"
                  min={1}
                  value={refreshInterval}
                  onChange={(e) => setRefreshInterval(Number(e.target.value))}
                  className="max-w-xs"
                />
              </div>
              {configError && <p className="text-red-500 text-sm">{configError}</p>}
              <Button type="submit" disabled={savingConfig}>
                {savingConfig ? "Saving…" : "Save Config"}
              </Button>
            </form>
          )}
        </CardContent>
      </Card>

      {/* Push Tokens */}
      <Card>
        <CardHeader>
          <CardTitle>Push Tokens</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <form onSubmit={registerToken} className="space-y-3">
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
              <Input
                placeholder="Device token"
                value={ptToken}
                onChange={(e) => setPtToken(e.target.value)}
                required
              />
              <select
                className="border rounded px-3 py-2 text-sm bg-background"
                value={ptPlatform}
                onChange={(e) => setPtPlatform(e.target.value)}
              >
                <option value="ios">iOS</option>
                <option value="android">Android</option>
                <option value="web">Web</option>
              </select>
              <Input
                placeholder="Device label"
                value={ptLabel}
                onChange={(e) => setPtLabel(e.target.value)}
              />
            </div>
            {ptError && <p className="text-red-500 text-sm">{ptError}</p>}
            <Button type="submit" disabled={ptSubmitting}>
              {ptSubmitting ? "Registering…" : "Register Token"}
            </Button>
          </form>

          {ptLoading ? (
            <p className="text-muted-foreground">Loading…</p>
          ) : (
            <div className="space-y-2">
              {pushTokens.length === 0 && (
                <p className="text-muted-foreground text-sm">No push tokens registered.</p>
              )}
              {pushTokens.map((pt) => (
                <div
                  key={pt.id}
                  className="flex items-center justify-between border rounded p-3 text-sm"
                >
                  <div>
                    <span className="font-mono text-xs break-all">{pt.token}</span>
                    <div className="flex gap-2 mt-1">
                      <Badge variant="outline">{pt.platform}</Badge>
                      {pt.device_label && (
                        <span className="text-muted-foreground">{pt.device_label}</span>
                      )}
                    </div>
                  </div>
                  <Button
                    variant="destructive"
                    size="sm"
                    onClick={() => deleteToken(pt.id)}
                  >
                    Delete
                  </Button>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
