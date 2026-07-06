"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api-client";
import { RefreshCw, MapPin, Navigation, Copy, Square } from "lucide-react";
import { Button } from "@/components/ui/button";
import { toast } from "sonner";
import styles from "./page.module.scss";

interface TrackingSession {
  id: string;
  token: string;
  staff_user_id: string;
  customer_id: string | null;
  appointment_id: string | null;
  status: string;
  eta_minutes: number | null;
  current_lat: number | null;
  current_lng: number | null;
  destination_lat: number | null;
  destination_lng: number | null;
  last_updated: string | null;
  created_at: string;
}

function relativeTime(dateStr: string | null): string {
  if (!dateStr) return "never";
  const diff = Math.floor((Date.now() - new Date(dateStr).getTime()) / 1000);
  if (diff < 60) return `${diff}s ago`;
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
  return `${Math.floor(diff / 3600)}h ago`;
}

export default function TrackingPage() {
  const [sessions, setSessions] = useState<TrackingSession[]>([]);
  const [loading, setLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState<string | null>(null);
  const [expandedLocation, setExpandedLocation] = useState<string | null>(null);
  const [locationForm, setLocationForm] = useState<Record<string, { lat: string; lng: string; eta: string }>>({});

  const [startForm, setStartForm] = useState({
    appointment_id: "",
    customer_id: "",
    destination_lat: "",
    destination_lng: "",
  });

  async function load() {
    setLoading(true);
    try {
      const data = await api.get<TrackingSession[]>("/api/tracking");
      setSessions(data);
    } catch {
      toast.error("Failed to load tracking sessions");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { load(); }, []); // eslint-disable-line react-hooks/exhaustive-deps

  async function startSession() {
    setActionLoading("start");
    try {
      const body: Record<string, unknown> = {
        appointment_id: startForm.appointment_id || null,
        customer_id: startForm.customer_id || null,
        destination_lat: startForm.destination_lat ? parseFloat(startForm.destination_lat) : null,
        destination_lng: startForm.destination_lng ? parseFloat(startForm.destination_lng) : null,
      };
      await api.post("/api/tracking", body);
      toast.success("Tracking session started");
      setStartForm({ appointment_id: "", customer_id: "", destination_lat: "", destination_lng: "" });
      await load();
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Something went wrong");
    } finally {
      setActionLoading(null);
    }
  }

  async function updateLocation(id: string) {
    const lf = locationForm[id];
    if (!lf) return;
    setActionLoading("loc_" + id);
    try {
      await api.patch(`/api/tracking/${id}/location`, {
        lat: parseFloat(lf.lat),
        lng: parseFloat(lf.lng),
        eta_minutes: lf.eta ? parseInt(lf.eta) : null,
      });
      toast.success("Location updated");
      setExpandedLocation(null);
      await load();
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Something went wrong");
    } finally {
      setActionLoading(null);
    }
  }

  async function endSession(id: string) {
    setActionLoading("end_" + id);
    try {
      await api.post(`/api/tracking/${id}/end`, {});
      toast.success("Session ended");
      await load();
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Something went wrong");
    } finally {
      setActionLoading(null);
    }
  }

  function copyShareLink(token: string) {
    navigator.clipboard.writeText(`/tracking/${token}`).then(() => {
      toast.success("Link copied");
    }).catch(() => {
      toast.error("Failed to copy link");
    });
  }

  function initLocationForm(s: TrackingSession) {
    setLocationForm((f) => ({
      ...f,
      [s.id]: {
        lat: s.current_lat?.toString() ?? "",
        lng: s.current_lng?.toString() ?? "",
        eta: s.eta_minutes?.toString() ?? "",
      },
    }));
    setExpandedLocation(s.id);
  }

  return (
    <div className="mx-auto max-w-4xl space-y-6 p-6">
      {/* Header */}
      <div>
        <h1 className="text-xl font-semibold text-gray-900">Live Tracking</h1>
        <p className="text-sm text-muted-foreground mt-0.5">
          Manage real-time tracking sessions for your staff.
        </p>
      </div>

      {/* Info banner */}
      <div className="rounded-lg bg-blue-50 border border-blue-200 px-4 py-3 text-sm text-blue-800 flex items-start gap-2">
        <Navigation className="h-4 w-4 flex-shrink-0 mt-0.5" />
        Share a live tracking link with customers so they can follow your staff&apos;s location in real time.
      </div>

      {/* Start new session form */}
      <div className="rounded-xl border border-[var(--vf-brand-primary)]/20 bg-white p-5 shadow-sm space-y-4">
        <h3 className="text-sm font-semibold text-gray-900">Start New Session</h3>
        <div className="grid grid-cols-2 gap-3">
          <div className="space-y-1">
            <label className="text-xs font-medium text-gray-700">Appointment ID (optional)</label>
            <input
              value={startForm.appointment_id}
              onChange={(e) => setStartForm((f) => ({ ...f, appointment_id: e.target.value }))}
              placeholder="UUID"
              className="block w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-[var(--vf-brand-primary)]"
            />
          </div>
          <div className="space-y-1">
            <label className="text-xs font-medium text-gray-700">Customer ID (optional)</label>
            <input
              value={startForm.customer_id}
              onChange={(e) => setStartForm((f) => ({ ...f, customer_id: e.target.value }))}
              placeholder="UUID"
              className="block w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-[var(--vf-brand-primary)]"
            />
          </div>
          <div className="space-y-1">
            <label className="text-xs font-medium text-gray-700">Destination Lat (optional)</label>
            <input
              type="number"
              step="any"
              value={startForm.destination_lat}
              onChange={(e) => setStartForm((f) => ({ ...f, destination_lat: e.target.value }))}
              placeholder="59.3293"
              className="block w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-[var(--vf-brand-primary)]"
            />
          </div>
          <div className="space-y-1">
            <label className="text-xs font-medium text-gray-700">Destination Lng (optional)</label>
            <input
              type="number"
              step="any"
              value={startForm.destination_lng}
              onChange={(e) => setStartForm((f) => ({ ...f, destination_lng: e.target.value }))}
              placeholder="18.0686"
              className="block w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-[var(--vf-brand-primary)]"
            />
          </div>
        </div>
        <Button disabled={actionLoading === "start"} onClick={startSession}
          className="bg-[var(--vf-brand-primary)] hover:bg-[var(--vf-brand-primary-hover)] text-white gap-2">
          {actionLoading === "start" ? <RefreshCw className="h-4 w-4 animate-spin" /> : <Navigation className="h-4 w-4" />}
          Start Tracking
        </Button>
      </div>

      {/* Active sessions */}
      {loading && sessions.length === 0 ? (
        <div className="text-center py-12">
          <RefreshCw className="h-6 w-6 animate-spin mx-auto text-muted-foreground" />
        </div>
      ) : sessions.length === 0 ? (
        <div className="rounded-xl border bg-white shadow-sm py-12 text-center">
          <MapPin className="h-10 w-10 text-muted-foreground mx-auto mb-3" />
          <p className="text-gray-600 font-medium">No active tracking sessions</p>
        </div>
      ) : (
        <div className="space-y-3">
          {sessions.map((s) => (
            <div key={s.id} className="rounded-xl border bg-white shadow-sm p-5 space-y-3">
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className={styles[s.status === "active" ? "statusActive" : "statusInactive"]}>
                      {s.status === "active" && <span className="h-1.5 w-1.5 rounded-full bg-green-500 animate-pulse" />}
                      {s.status}
                    </span>
                    {s.eta_minutes != null && (
                      <span className="rounded-full bg-blue-100 text-blue-700 px-2.5 py-0.5 text-xs font-medium">
                        ETA {s.eta_minutes} min
                      </span>
                    )}
                  </div>
                  <p className="text-sm text-gray-700 mt-1">
                    Staff: <span className="font-mono text-xs">{s.staff_user_id.slice(0, 8)}…</span>
                  </p>
                  {s.customer_id && (
                    <p className="text-sm text-gray-700">
                      Customer: <span className="font-mono text-xs">{s.customer_id.slice(0, 8)}…</span>
                    </p>
                  )}
                  <p className="text-xs text-muted-foreground mt-0.5">
                    Last updated: {relativeTime(s.last_updated)}
                  </p>
                </div>
                <div className="flex items-center gap-2 flex-shrink-0">
                  <Button variant="outline" size="sm" onClick={() => copyShareLink(s.token)} className="gap-1">
                    <Copy className="h-3 w-3" /> Copy Share Link
                  </Button>
                  {s.status === "active" && (
                    <Button variant="outline" size="sm"
                      disabled={actionLoading === "end_" + s.id}
                      onClick={() => endSession(s.id)}
                      className="gap-1 text-red-600 border-red-200 hover:bg-red-50"
                    >
                      {actionLoading === "end_" + s.id
                        ? <RefreshCw className="h-3 w-3 animate-spin" />
                        : <Square className="h-3 w-3" />}
                      End Session
                    </Button>
                  )}
                </div>
              </div>

              {/* Current position */}
              {s.current_lat != null && s.current_lng != null && (
                <div className="rounded-lg bg-gray-50 border px-3 py-2 text-xs text-gray-700">
                  <MapPin className="h-3 w-3 inline-block mr-1 text-blue-600" />
                  Lat {s.current_lat.toFixed(6)}, Lng {s.current_lng.toFixed(6)}
                  <span className="text-muted-foreground ml-2">· Last updated {relativeTime(s.last_updated)}</span>
                </div>
              )}

              {/* Update location inline form */}
              {s.status === "active" && (
                <>
                  {expandedLocation === s.id ? (
                    <div className="rounded-lg border bg-blue-50 p-3 space-y-2">
                      <h4 className="text-xs font-semibold text-gray-700">Update Location</h4>
                      <div className="grid grid-cols-3 gap-2">
                        <div className="space-y-1">
                          <label className="text-xs text-gray-600">Latitude</label>
                          <input
                            type="number" step="any"
                            value={locationForm[s.id]?.lat ?? ""}
                            onChange={(e) => setLocationForm((f) => ({ ...f, [s.id]: { ...f[s.id], lat: e.target.value } }))}
                            className="block w-full rounded-md border border-gray-300 px-2 py-1.5 text-xs focus:outline-none focus:ring-1 focus:ring-[var(--vf-brand-primary)]"
                          />
                        </div>
                        <div className="space-y-1">
                          <label className="text-xs text-gray-600">Longitude</label>
                          <input
                            type="number" step="any"
                            value={locationForm[s.id]?.lng ?? ""}
                            onChange={(e) => setLocationForm((f) => ({ ...f, [s.id]: { ...f[s.id], lng: e.target.value } }))}
                            className="block w-full rounded-md border border-gray-300 px-2 py-1.5 text-xs focus:outline-none focus:ring-1 focus:ring-[var(--vf-brand-primary)]"
                          />
                        </div>
                        <div className="space-y-1">
                          <label className="text-xs text-gray-600">ETA (min)</label>
                          <input
                            type="number"
                            value={locationForm[s.id]?.eta ?? ""}
                            onChange={(e) => setLocationForm((f) => ({ ...f, [s.id]: { ...f[s.id], eta: e.target.value } }))}
                            className="block w-full rounded-md border border-gray-300 px-2 py-1.5 text-xs focus:outline-none focus:ring-1 focus:ring-[var(--vf-brand-primary)]"
                          />
                        </div>
                      </div>
                      <div className="flex gap-2">
                        <Button size="sm" disabled={actionLoading === "loc_" + s.id} onClick={() => updateLocation(s.id)}
                          className="bg-[var(--vf-brand-primary)] hover:bg-[var(--vf-brand-primary-hover)] text-white gap-1">
                          {actionLoading === "loc_" + s.id ? <RefreshCw className="h-3 w-3 animate-spin" /> : null}
                          Save
                        </Button>
                        <Button size="sm" variant="outline" onClick={() => setExpandedLocation(null)}>Cancel</Button>
                      </div>
                    </div>
                  ) : (
                    <Button variant="outline" size="sm" onClick={() => initLocationForm(s)} className="gap-1">
                      <MapPin className="h-3 w-3" /> Update Location
                    </Button>
                  )}
                </>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
