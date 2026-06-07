"use client";
import { useState } from "react";
import { api } from "@/lib/api-client";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";

interface CalendarConfig {
  provider: string;
  sync_enabled: boolean;
  calendar_id?: string;
  token_expiry?: string;
}

export default function CalendarSyncPage() {
  const [customerIdInput, setCustomerIdInput] = useState("");
  const [customerId, setCustomerId] = useState("");
  const [configs, setConfigs] = useState<CalendarConfig[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  // iCal form
  const [icalCalendarId, setIcalCalendarId] = useState("");
  const [icalSyncEnabled, setIcalSyncEnabled] = useState(true);
  const [icalLoading, setIcalLoading] = useState(false);
  const [icalError, setIcalError] = useState("");

  // iCal feed URL
  const [icalFeedUrl, setIcalFeedUrl] = useState("");
  const [icalFeedLoading, setIcalFeedLoading] = useState(false);

  // Google form
  const [googleCalendarId, setGoogleCalendarId] = useState("");
  const [googleSyncEnabled, setGoogleSyncEnabled] = useState(true);
  const [googleLoading, setGoogleLoading] = useState(false);
  const [googleError, setGoogleError] = useState("");

  async function loadConfigs() {
    if (!customerIdInput.trim()) return;
    const cid = customerIdInput.trim();
    setCustomerId(cid);
    setLoading(true);
    setError("");
    try {
      const data = await api.get<CalendarConfig | CalendarConfig[]>(`/api/calendar-sync?customer_id=${encodeURIComponent(cid)}`);
      setConfigs(Array.isArray(data) ? data : [data]);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to load calendar configs");
    } finally {
      setLoading(false);
    }
  }

  async function handleConfigureIcal(e: React.FormEvent) {
    e.preventDefault();
    if (!customerId) { setIcalError("Load a customer first"); return; }
    setIcalLoading(true);
    setIcalError("");
    try {
      await api.put(`/api/calendar-sync/${customerId}/ical`, {
        calendar_id: icalCalendarId || undefined,
        sync_enabled: icalSyncEnabled,
      });
      await loadConfigs();
    } catch (e: unknown) {
      setIcalError(e instanceof Error ? e.message : "Failed to configure iCal");
    } finally {
      setIcalLoading(false);
    }
  }

  async function handleGetIcalFeed() {
    if (!customerId) return;
    setIcalFeedLoading(true);
    try {
      const data = await api.get<{ url?: string; ics_url?: string }>(`/api/calendar-sync/${customerId}/ics`);
      setIcalFeedUrl(data.url ?? data.ics_url ?? "");
    } catch (e: unknown) {
      setIcalError(e instanceof Error ? e.message : "Failed to get iCal feed URL");
    } finally {
      setIcalFeedLoading(false);
    }
  }

  async function handleConfigureGoogle(e: React.FormEvent) {
    e.preventDefault();
    if (!customerId) { setGoogleError("Load a customer first"); return; }
    setGoogleLoading(true);
    setGoogleError("");
    try {
      await api.put(`/api/calendar-sync/${customerId}/google`, {
        calendar_id: googleCalendarId || undefined,
        sync_enabled: googleSyncEnabled,
      });
      await loadConfigs();
    } catch (e: unknown) {
      setGoogleError(e instanceof Error ? e.message : "Failed to configure Google Calendar");
    } finally {
      setGoogleLoading(false);
    }
  }

  async function handleDelete(provider: string) {
    if (!customerId) return;
    setError("");
    try {
      await api.delete(`/api/calendar-sync/${customerId}/${provider}`);
      setConfigs((prev) => prev.filter((c) => c.provider !== provider));
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to delete config");
    }
  }

  return (
    <div className="p-6 space-y-6 max-w-3xl mx-auto">
      <h1 className="text-2xl font-bold">Calendar Sync</h1>

      {/* Customer lookup */}
      <Card>
        <CardHeader>
          <CardTitle>Load Customer Config</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex gap-2">
            <Input
              placeholder="Customer ID"
              value={customerIdInput}
              onChange={(e) => setCustomerIdInput(e.target.value)}
              className="max-w-sm"
            />
            <Button onClick={loadConfigs} disabled={loading}>
              {loading ? "Loading…" : "Load"}
            </Button>
          </div>
          {error && <p className="text-red-500 text-sm mt-2">{error}</p>}
        </CardContent>
      </Card>

      {/* Existing configs */}
      {configs.length > 0 && (
        <div className="space-y-3">
          <h2 className="text-lg font-semibold">Active Configurations</h2>
          {configs.map((cfg) => (
            <Card key={cfg.provider}>
              <CardContent className="pt-4">
                <div className="flex items-center justify-between">
                  <div className="space-y-1">
                    <div className="flex items-center gap-2">
                      <span className="font-medium capitalize">{cfg.provider}</span>
                      <Badge variant={cfg.sync_enabled ? "default" : "secondary"}>
                        {cfg.sync_enabled ? "Enabled" : "Disabled"}
                      </Badge>
                    </div>
                    {cfg.calendar_id && (
                      <p className="text-sm text-muted-foreground">
                        Calendar ID: {cfg.calendar_id}
                      </p>
                    )}
                    {cfg.token_expiry && (
                      <p className="text-sm text-muted-foreground">
                        Token expires: {new Date(cfg.token_expiry).toLocaleDateString()}
                      </p>
                    )}
                  </div>
                  <Button
                    size="sm"
                    variant="destructive"
                    onClick={() => handleDelete(cfg.provider)}
                  >
                    Delete
                  </Button>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      {/* Configure iCal */}
      <Card>
        <CardHeader>
          <CardTitle>Configure iCal</CardTitle>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleConfigureIcal} className="space-y-3">
            <div>
              <label className="text-sm font-medium">Calendar ID (optional)</label>
              <Input
                value={icalCalendarId}
                onChange={(e) => setIcalCalendarId(e.target.value)}
                placeholder="e.g. primary"
              />
            </div>
            <div className="flex items-center gap-2">
              <input
                type="checkbox"
                id="ical_sync"
                checked={icalSyncEnabled}
                onChange={(e) => setIcalSyncEnabled(e.target.checked)}
                className="h-4 w-4"
              />
              <label htmlFor="ical_sync" className="text-sm">
                Sync enabled
              </label>
            </div>
            {icalError && <p className="text-red-500 text-sm">{icalError}</p>}
            <div className="flex gap-2">
              <Button type="submit" disabled={icalLoading}>
                {icalLoading ? "Saving…" : "Save iCal Config"}
              </Button>
              <Button
                type="button"
                variant="outline"
                disabled={icalFeedLoading || !customerId}
                onClick={handleGetIcalFeed}
              >
                {icalFeedLoading ? "Fetching…" : "Get iCal Feed URL"}
              </Button>
            </div>
          </form>
          {icalFeedUrl && (
            <div className="mt-3">
              <label className="text-sm font-medium">iCal Feed URL</label>
              <div className="flex gap-2 mt-1">
                <Input value={icalFeedUrl} readOnly className="font-mono text-xs" />
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => navigator.clipboard.writeText(icalFeedUrl)}
                >
                  Copy
                </Button>
              </div>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Configure Google Calendar */}
      <Card>
        <CardHeader>
          <CardTitle>Configure Google Calendar</CardTitle>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleConfigureGoogle} className="space-y-3">
            <div>
              <label className="text-sm font-medium">Calendar ID (optional)</label>
              <Input
                value={googleCalendarId}
                onChange={(e) => setGoogleCalendarId(e.target.value)}
                placeholder="e.g. primary"
              />
            </div>
            <div className="flex items-center gap-2">
              <input
                type="checkbox"
                id="google_sync"
                checked={googleSyncEnabled}
                onChange={(e) => setGoogleSyncEnabled(e.target.checked)}
                className="h-4 w-4"
              />
              <label htmlFor="google_sync" className="text-sm">
                Sync enabled
              </label>
            </div>
            {googleError && (
              <p className="text-red-500 text-sm">{googleError}</p>
            )}
            <Button type="submit" disabled={googleLoading}>
              {googleLoading ? "Saving…" : "Save Google Config"}
            </Button>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}
