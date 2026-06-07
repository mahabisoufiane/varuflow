"use client";

import { useState, useEffect, useRef } from "react";
import { toast } from "sonner";
import { api } from "@/lib/api-client";
import {
  Navigation, Plus, CheckCircle2, MapPin, Shuffle, AlertTriangle,
  Camera, FileSignature, Bell, BarChart2, ChevronLeft, ExternalLink,
  Clock, XCircle, RefreshCw,
} from "lucide-react";
import styles from "./page.module.scss";

// ─── Types ───────────────────────────────────────────────────────────────────

interface Stop {
  id: string;
  stop_type: string;
  label?: string;
  address?: string;
  lat?: number;
  lng?: number;
  sequence: number;
  status: string; // pending / visited / completed / skipped / exception
  scheduled_at?: string;
  arrived_at?: string;
  completed_at?: string;
  exception_type?: string;
  exception_reason?: string;
  reschedule_date?: string;
  pod_photo_url?: string;
  pod_signature_data?: Record<string, unknown> | null;
  notes?: string;
  ref_id?: string;
}

interface Route {
  id: string;
  name: string;
  driver_name?: string;
  route_date: string;
  status: string;
  stops: Stop[];
  total_km?: number;
  notification_threshold_minutes?: number;
  created_at: string;
}

interface ReportStop {
  stop_id: string;
  label: string;
  status: string;
  scheduled_at?: string;
  arrived_at?: string;
  delta_minutes?: number;
  on_time?: boolean;
  has_pod_photo: boolean;
  has_pod_signature: boolean;
  exception_type?: string;
}

interface Report {
  route_id: string;
  route_name: string;
  route_date: string;
  driver_name?: string;
  total_km?: number;
  summary: { completed: number; exceptions: number; skipped: number; pending: number; total: number };
  timing: ReportStop[];
}

// ─── Helpers ─────────────────────────────────────────────────────────────────

const stopBorder: Record<string, string> = {
  pending: "border-gray-200",
  visited: "border-blue-300 bg-blue-50",
  completed: "border-green-400 bg-green-50",
  skipped: "border-gray-200 opacity-50",
  exception: "border-red-300 bg-red-50",
};

const routeStatusColor: Record<string, string> = {
  draft: "bg-gray-100 text-gray-600",
  active: "bg-blue-100 text-blue-700",
  completed: "bg-green-100 text-green-700",
};

const ROUTE_STATUS_MODULE: Record<string, keyof typeof styles> = {
  draft:     "statusDraft",
  active:    "statusActive",
  completed: "statusCompleted",
};

const EXCEPTION_TYPES = ["no_answer", "wrong_address", "refused", "damaged", "other"] as const;

function mapsLink(address?: string, lat?: number, lng?: number): string {
  if (lat && lng) return `https://www.google.com/maps/dir/?api=1&destination=${lat},${lng}`;
  if (address) return `https://www.google.com/maps/dir/?api=1&destination=${encodeURIComponent(address)}`;
  return "#";
}

function wazeLink(address?: string, lat?: number, lng?: number): string {
  if (lat && lng) return `https://waze.com/ul?ll=${lat},${lng}&navigate=yes`;
  if (address) return `https://waze.com/ul?q=${encodeURIComponent(address)}&navigate=yes`;
  return "#";
}

function fmtTime(iso?: string) {
  if (!iso) return "—";
  return new Date(iso).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

// ─── Signature Canvas ─────────────────────────────────────────────────────────

function SignaturePad({ onDone }: { onDone: (data: string | null) => void }) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const drawing = useRef(false);

  function getPos(e: React.PointerEvent) {
    const rect = canvasRef.current!.getBoundingClientRect();
    return { x: e.clientX - rect.left, y: e.clientY - rect.top };
  }

  function onDown(e: React.PointerEvent) {
    drawing.current = true;
    const ctx = canvasRef.current!.getContext("2d")!;
    const { x, y } = getPos(e);
    ctx.beginPath();
    ctx.moveTo(x, y);
  }

  function onMove(e: React.PointerEvent) {
    if (!drawing.current) return;
    const ctx = canvasRef.current!.getContext("2d")!;
    const { x, y } = getPos(e);
    ctx.lineTo(x, y);
    ctx.stroke();
  }

  function onUp() { drawing.current = false; }

  function clear() {
    const canvas = canvasRef.current!;
    canvas.getContext("2d")!.clearRect(0, 0, canvas.width, canvas.height);
  }

  function save() {
    const data = canvasRef.current!.toDataURL("image/png");
    onDone(data);
  }

  return (
    <div className="space-y-2">
      <p className="text-xs text-gray-500">Sign in the box below</p>
      <canvas
        ref={canvasRef}
        width={320} height={160}
        className="w-full border-2 border-gray-300 rounded-lg bg-white touch-none cursor-crosshair"
        onPointerDown={onDown}
        onPointerMove={onMove}
        onPointerUp={onUp}
        onPointerLeave={onUp}
      />
      <div className="flex gap-2">
        <button onClick={clear} className="btn-secondary text-sm flex-1">Clear</button>
        <button onClick={save} className="btn-primary text-sm flex-1">Use Signature</button>
        <button onClick={() => onDone(null)} className="btn-secondary text-sm">Skip</button>
      </div>
    </div>
  );
}

// ─── Main Page ────────────────────────────────────────────────────────────────

export default function RoutesPage() {
  const [routes, setRoutes] = useState<Route[]>([]);
  const [selected, setSelected] = useState<Route | null>(null);
  const [showCreate, setShowCreate] = useState(false);
  const [optimizing, setOptimizing] = useState(false);
  const [report, setReport] = useState<Report | null>(null);
  const [loadingReport, setLoadingReport] = useState(false);

  // Create form
  const [form, setForm] = useState({
    name: "",
    driver_name: "",
    route_date: new Date().toISOString().split("T")[0],
    notification_threshold_minutes: 15,
  });

  // Complete stop modal
  const [completeStop, setCompleteStop] = useState<Stop | null>(null);
  const [podPhotoFile, setPodPhotoFile] = useState<File | null>(null);
  const [podPhotoPreview, setPodPhotoPreview] = useState<string | null>(null);
  const [sigStep, setSigStep] = useState(false);
  const [sigData, setSigData] = useState<string | null>(null);
  const [completingId, setCompletingId] = useState<string | null>(null);

  // Exception modal
  const [exceptionStop, setExceptionStop] = useState<Stop | null>(null);
  const [excForm, setExcForm] = useState({ exception_type: "no_answer", exception_reason: "", reschedule_date: "" });
  const [submittingExc, setSubmittingExc] = useState(false);

  // ── API helpers ──

  async function load() {
    try {
      const data = await api.get<{ routes?: Route[] }>("/api/mobile/routes?limit=50");
      setRoutes(data.routes ?? []);
    } catch { /* silent */ }
  }

  async function refreshSelected(routeId: string) {
    try {
      const data = await api.get<Route>(`/api/mobile/routes/${routeId}`);
      setSelected(data);
    } catch {}
  }

  useEffect(() => { load(); }, []);

  // ── Create route ──

  async function createRoute() {
    try {
      await api.post("/api/mobile/routes", { ...form, stops: [] });
      toast.success("Route created");
      setShowCreate(false);
      setForm({ name: "", driver_name: "", route_date: new Date().toISOString().split("T")[0], notification_threshold_minutes: 15 });
      await load();
    } catch {
      toast.error("Failed to create route");
    }
  }

  // ── Optimize ──

  async function optimizeRoute(routeId: string) {
    setOptimizing(true);
    try {
      const data = await api.post<Route>(`/api/mobile/routes/${routeId}/optimize`, {});
      toast.success("Route optimized");
      setSelected(data);
    } catch {
      toast.error("Optimization failed");
    } finally {
      setOptimizing(false);
    }
  }

  // ── Arrive ──

  async function markArrived(routeId: string, stopId: string) {
    try {
      await api.post(`/api/mobile/routes/${routeId}/stops/${stopId}/arrive`, {});
      toast.success("Marked as arrived");
      await refreshSelected(routeId);
    } catch {
      toast.error("Failed to mark arrived");
    }
  }

  // ── Complete stop ──

  function openComplete(stop: Stop) {
    setCompleteStop(stop);
    setPodPhotoFile(null);
    setPodPhotoPreview(null);
    setSigStep(false);
    setSigData(null);
  }

  function onPhotoChange(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    setPodPhotoFile(file);
    const reader = new FileReader();
    reader.onload = () => setPodPhotoPreview(reader.result as string);
    reader.readAsDataURL(file);
  }

  async function submitComplete() {
    if (!completeStop || !selected) return;
    setCompletingId(completeStop.id);
    try {
      // Upload photo if present
      let photoUrl: string | null = null;
      if (podPhotoFile) {
        const uploaded = await api.upload<{ url?: string }>("/api/mobile/upload-pod-photo", podPhotoFile);
        photoUrl = uploaded.url ?? null;
      }

      const body: Record<string, unknown> = {};
      if (photoUrl) body.pod_photo_url = photoUrl;
      if (sigData) body.pod_signature_data = { data_url: sigData, captured_at: new Date().toISOString() };

      await api.post(`/api/mobile/routes/${selected.id}/stops/${completeStop.id}/complete`, body);
      toast.success("Stop completed");
      setCompleteStop(null);
      await refreshSelected(selected.id);
    } catch {
      toast.error("Failed to complete stop");
    } finally {
      setCompletingId(null);
    }
  }

  // ── Exception ──

  function openException(stop: Stop) {
    setExceptionStop(stop);
    setExcForm({ exception_type: "no_answer", exception_reason: "", reschedule_date: "" });
  }

  async function submitException() {
    if (!exceptionStop || !selected) return;
    setSubmittingExc(true);
    try {
      await api.post(`/api/mobile/routes/${selected.id}/stops/${exceptionStop.id}/exception`, {
        exception_type: excForm.exception_type,
        exception_reason: excForm.exception_reason || undefined,
        reschedule_date: excForm.reschedule_date || undefined,
      });
      toast.success("Exception recorded");
      setExceptionStop(null);
      await refreshSelected(selected.id);
    } catch {
      toast.error("Failed to record exception");
    } finally {
      setSubmittingExc(false);
    }
  }

  // ── Notify customer ──

  async function notifyCustomer(routeId: string, stopId: string) {
    try {
      const j = await api.post<{ sent?: boolean; reason?: string }>(`/api/mobile/routes/${routeId}/stops/${stopId}/notify`, {});
      if (j.sent) {
        toast.success("Customer notified");
      } else {
        toast.info(j.reason || "Notification not sent");
      }
    } catch {
      toast.error("Failed to notify customer");
    }
  }

  // ── End-of-day report ──

  async function loadReport(routeId: string) {
    setLoadingReport(true);
    try {
      const data = await api.get<Report>(`/api/mobile/routes/${routeId}/report`);
      setReport(data);
    } catch {
      toast.error("Failed to load report");
    } finally {
      setLoadingReport(false);
    }
  }

  // ─── Render ───────────────────────────────────────────────────────────────

  // Report view
  if (report) {
    const pct = report.summary.total > 0
      ? Math.round((report.summary.completed / report.summary.total) * 100)
      : 0;
    return (
      <div className="space-y-6 max-w-2xl mx-auto">
        <div className="flex items-center gap-3">
          <button onClick={() => setReport(null)} className="text-sm text-blue-600 hover:underline flex items-center gap-1">
            <ChevronLeft className="h-4 w-4" /> Back
          </button>
          <h1 className="text-xl font-semibold text-gray-900">End-of-Day Report</h1>
        </div>

        <div className="rounded-xl border border-gray-200 bg-white p-5 space-y-1">
          <p className="font-semibold text-gray-900">{report.route_name}</p>
          {report.driver_name && <p className="text-sm text-gray-500">{report.driver_name}</p>}
          <p className="text-sm text-gray-400">{report.route_date}</p>
        </div>

        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          {[
            { label: "Completed", val: report.summary.completed, color: "text-green-600" },
            { label: "Exceptions", val: report.summary.exceptions, color: "text-red-500" },
            { label: "Skipped", val: report.summary.skipped, color: "text-gray-400" },
            { label: "Pending", val: report.summary.pending, color: "text-orange-500" },
          ].map(c => (
            <div key={c.label} className="rounded-xl border border-gray-200 bg-white p-4 text-center">
              <p className={`text-2xl font-bold ${c.color}`}>{c.val}</p>
              <p className="text-xs text-gray-500 mt-0.5">{c.label}</p>
            </div>
          ))}
        </div>

        <div className="grid grid-cols-2 gap-3">
          <div className="rounded-xl border border-gray-200 bg-white p-4 text-center">
            <p className="text-2xl font-bold text-blue-600">{report.total_km?.toFixed(1) ?? "—"} km</p>
            <p className="text-xs text-gray-500 mt-0.5">Total distance</p>
          </div>
          <div className="rounded-xl border border-gray-200 bg-white p-4 text-center">
            <p className="text-2xl font-bold text-indigo-600">{pct}%</p>
            <p className="text-xs text-gray-500 mt-0.5">Completion rate</p>
          </div>
        </div>

        <div className="rounded-xl border border-gray-200 bg-white overflow-hidden">
          <div className="px-4 py-3 border-b border-gray-100 bg-gray-50">
            <p className="text-sm font-medium text-gray-700">Stop Timing</p>
          </div>
          <div className="divide-y divide-gray-100">
            {report.timing.map((t, i) => (
              <div key={t.stop_id} className="px-4 py-3 flex items-center gap-3">
                <span className="text-xs font-bold text-gray-400 w-5 flex-shrink-0">{i + 1}</span>
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium text-gray-900 truncate">{t.label}</p>
                  <div className="flex flex-wrap gap-x-3 gap-y-0.5 mt-0.5">
                    <span className="text-xs text-gray-500">Sched: {fmtTime(t.scheduled_at)}</span>
                    <span className="text-xs text-gray-500">Arrived: {fmtTime(t.arrived_at)}</span>
                    {t.delta_minutes != null && (
                      <span className={`text-xs font-medium ${t.on_time ? "text-green-600" : "text-red-500"}`}>
                        {t.delta_minutes > 0 ? `+${t.delta_minutes}m late` : t.delta_minutes < 0 ? `${Math.abs(t.delta_minutes)}m early` : "on time"}
                      </span>
                    )}
                  </div>
                </div>
                <div className="flex items-center gap-1 flex-shrink-0">
                  {t.has_pod_photo && <Camera className="h-3.5 w-3.5 text-blue-400" />}
                  {t.has_pod_signature && <FileSignature className="h-3.5 w-3.5 text-indigo-400" />}
                  {t.exception_type && <AlertTriangle className="h-3.5 w-3.5 text-red-400" />}
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    );
  }

  // Route list
  if (!selected) {
    return (
      <div className="space-y-6">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-semibold text-gray-900">GPS Routes</h1>
            <p className="mt-1 text-sm text-gray-500">Plan and track delivery or field service routes.</p>
          </div>
          <button onClick={() => setShowCreate(true)} className="btn-primary flex items-center gap-2">
            <Plus className="h-4 w-4" /> New Route
          </button>
        </div>

        {showCreate && (
          <div className="rounded-xl border border-blue-200 bg-blue-50 p-4 space-y-3">
            <input className="input w-full" placeholder="Route name" value={form.name}
              onChange={e => setForm(f => ({ ...f, name: e.target.value }))} />
            <input className="input w-full" placeholder="Driver name (optional)" value={form.driver_name}
              onChange={e => setForm(f => ({ ...f, driver_name: e.target.value }))} />
            <input className="input w-full" type="date" value={form.route_date}
              onChange={e => setForm(f => ({ ...f, route_date: e.target.value }))} />
            <div className="flex items-center gap-2">
              <label className="text-xs text-gray-600 whitespace-nowrap">Notify customer when</label>
              <input className="input w-24" type="number" min={5} max={120} value={form.notification_threshold_minutes}
                onChange={e => setForm(f => ({ ...f, notification_threshold_minutes: Number(e.target.value) }))} />
              <span className="text-xs text-gray-600">min away</span>
            </div>
            <div className="flex gap-2">
              <button onClick={createRoute} className="btn-primary">Create</button>
              <button onClick={() => setShowCreate(false)} className="btn-secondary">Cancel</button>
            </div>
          </div>
        )}

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {routes.map(r => (
            <button key={r.id} onClick={() => setSelected(r)}
              className="text-left rounded-xl border border-gray-200 bg-white p-4 hover:border-blue-400 hover:shadow-md transition-all">
              <div className="flex items-start justify-between mb-2">
                <Navigation className="h-5 w-5 text-blue-500" />
                <span className={styles[ROUTE_STATUS_MODULE[r.status] ?? "statusDraft"]}>
                  {r.status}
                </span>
              </div>
              <p className="font-medium text-gray-900">{r.name}</p>
              {r.driver_name && <p className="text-xs text-gray-500">{r.driver_name}</p>}
              <p className="text-xs text-gray-400 mt-1">{r.route_date} · {r.stops.length} stop{r.stops.length !== 1 ? "s" : ""}</p>
              {r.total_km != null && <p className="text-xs text-blue-500 mt-0.5">{r.total_km} km</p>}
            </button>
          ))}
          {routes.length === 0 && (
            <p className="text-sm text-gray-400 col-span-full text-center py-10">No routes yet. Create one to get started.</p>
          )}
        </div>
      </div>
    );
  }

  // ── Stop detail view ──

  const completedCount = selected.stops.filter(s => s.status === "completed").length;
  const totalCount = selected.stops.length;

  return (
    <div className="space-y-4 max-w-2xl mx-auto">
      {/* Header */}
      <div className="flex items-center justify-between">
        <button onClick={() => { setSelected(null); load(); }}
          className="text-sm text-blue-600 hover:underline flex items-center gap-1">
          <ChevronLeft className="h-4 w-4" /> Routes
        </button>
        <div className="flex items-center gap-2">
          <button onClick={() => optimizeRoute(selected.id)} disabled={optimizing}
            className="btn-secondary flex items-center gap-1.5 text-sm">
            <Shuffle className="h-3.5 w-3.5" />{optimizing ? "…" : "Optimize"}
          </button>
          <button onClick={() => loadReport(selected.id)} disabled={loadingReport}
            className="btn-secondary flex items-center gap-1.5 text-sm">
            <BarChart2 className="h-3.5 w-3.5" />{loadingReport ? "…" : "Report"}
          </button>
        </div>
      </div>

      {/* Route summary */}
      <div className="rounded-xl border border-gray-200 bg-white p-4">
        <div className="flex items-start justify-between">
          <div>
            <h2 className="text-lg font-semibold text-gray-900">{selected.name}</h2>
            {selected.driver_name && <p className="text-sm text-gray-500">{selected.driver_name}</p>}
            <p className="text-sm text-gray-400">{selected.route_date}</p>
          </div>
          <span className={styles[ROUTE_STATUS_MODULE[selected.status] ?? "statusDraft"]}>
            {selected.status}
          </span>
        </div>
        {/* Progress bar */}
        <div className="mt-3">
          <div className="flex justify-between text-xs text-gray-500 mb-1">
            <span>{completedCount} / {totalCount} completed</span>
            {selected.total_km != null && <span>{selected.total_km} km</span>}
          </div>
          <div className="h-2 bg-gray-100 rounded-full overflow-hidden">
            <div
              className="h-2 bg-green-500 rounded-full transition-all"
              style={{ width: totalCount > 0 ? `${(completedCount / totalCount) * 100}%` : "0%" }}
            />
          </div>
        </div>
      </div>

      {/* Stop list */}
      <div className="space-y-3">
        {selected.stops.length === 0 ? (
          <p className="text-sm text-gray-400 text-center py-10">No stops added yet.</p>
        ) : (
          selected.stops.map((stop, i) => (
            <div key={stop.id}
              className={`rounded-xl border p-4 ${stopBorder[stop.status] || "border-gray-200"}`}>
              {/* Stop header */}
              <div className="flex items-start gap-3">
                <div className="flex h-8 w-8 items-center justify-center rounded-full bg-gray-200 text-sm font-bold text-gray-700 flex-shrink-0">
                  {i + 1}
                </div>
                <div className="flex-1 min-w-0">
                  <p className="font-medium text-gray-900 truncate">{stop.label || stop.stop_type}</p>
                  {stop.address && (
                    <p className="text-xs text-gray-500 flex items-center gap-1 mt-0.5">
                      <MapPin className="h-3 w-3 flex-shrink-0" />{stop.address}
                    </p>
                  )}

                  {/* Timing */}
                  <div className="flex flex-wrap gap-x-3 gap-y-0.5 mt-1">
                    {stop.scheduled_at && (
                      <span className="text-xs text-gray-400 flex items-center gap-0.5">
                        <Clock className="h-3 w-3" /> Sched {fmtTime(stop.scheduled_at)}
                      </span>
                    )}
                    {stop.arrived_at && (
                      <span className="text-xs text-blue-600">Arrived {fmtTime(stop.arrived_at)}</span>
                    )}
                    {stop.completed_at && (
                      <span className="text-xs text-green-600">Done {fmtTime(stop.completed_at)}</span>
                    )}
                  </div>

                  {/* Exception info */}
                  {stop.status === "exception" && (
                    <div className="mt-1 text-xs text-red-600">
                      <span className="font-medium">{stop.exception_type?.replace(/_/g, " ")}</span>
                      {stop.exception_reason && <span> — {stop.exception_reason}</span>}
                      {stop.reschedule_date && <span> (reschedule: {stop.reschedule_date})</span>}
                    </div>
                  )}

                  {/* POD indicators */}
                  {(stop.pod_photo_url || stop.pod_signature_data) && (
                    <div className="flex gap-2 mt-1">
                      {stop.pod_photo_url && <span className="text-xs text-blue-500 flex items-center gap-0.5"><Camera className="h-3 w-3" />Photo</span>}
                      {stop.pod_signature_data && <span className="text-xs text-indigo-500 flex items-center gap-0.5"><FileSignature className="h-3 w-3" />Signature</span>}
                    </div>
                  )}
                </div>
              </div>

              {/* Navigation links */}
              {(stop.address || (stop.lat && stop.lng)) && (
                <div className="flex gap-2 mt-3">
                  <a href={mapsLink(stop.address, stop.lat, stop.lng)} target="_blank" rel="noopener noreferrer"
                    className="flex-1 flex items-center justify-center gap-1.5 rounded-lg border border-blue-200 bg-blue-50 py-2 text-xs font-medium text-blue-700 hover:bg-blue-100 transition-colors">
                    <ExternalLink className="h-3.5 w-3.5" /> Google Maps
                  </a>
                  <a href={wazeLink(stop.address, stop.lat, stop.lng)} target="_blank" rel="noopener noreferrer"
                    className="flex-1 flex items-center justify-center gap-1.5 rounded-lg border border-cyan-200 bg-cyan-50 py-2 text-xs font-medium text-cyan-700 hover:bg-cyan-100 transition-colors">
                    <Navigation className="h-3.5 w-3.5" /> Waze
                  </a>
                </div>
              )}

              {/* Action buttons */}
              {(stop.status === "pending" || stop.status === "visited") && (
                <div className="grid grid-cols-2 gap-2 mt-3 sm:grid-cols-4">
                  {stop.status === "pending" && (
                    <button onClick={() => markArrived(selected.id, stop.id)}
                      className="col-span-2 sm:col-span-1 flex items-center justify-center gap-1.5 rounded-lg bg-blue-600 py-2.5 text-sm font-medium text-white hover:bg-blue-700 transition-colors">
                      <MapPin className="h-4 w-4" /> Arrive
                    </button>
                  )}
                  <button onClick={() => openComplete(stop)}
                    className="col-span-2 sm:col-span-1 flex items-center justify-center gap-1.5 rounded-lg bg-green-600 py-2.5 text-sm font-medium text-white hover:bg-green-700 transition-colors">
                    <CheckCircle2 className="h-4 w-4" /> Complete
                  </button>
                  <button onClick={() => openException(stop)}
                    className="flex items-center justify-center gap-1.5 rounded-lg border border-red-200 py-2.5 text-sm font-medium text-red-600 hover:bg-red-50 transition-colors">
                    <XCircle className="h-4 w-4" /> Exception
                  </button>
                  {stop.ref_id && (
                    <button onClick={() => notifyCustomer(selected.id, stop.id)}
                      className="flex items-center justify-center gap-1.5 rounded-lg border border-amber-200 py-2.5 text-sm font-medium text-amber-700 hover:bg-amber-50 transition-colors">
                      <Bell className="h-4 w-4" /> Notify
                    </button>
                  )}
                </div>
              )}
            </div>
          ))
        )}
      </div>

      {/* ── Complete stop modal ── */}
      {completeStop && (
        <div className="fixed inset-0 z-50 flex items-end sm:items-center justify-center bg-black/40 backdrop-blur-sm p-4">
          <div className="w-full max-w-md rounded-2xl bg-white p-5 space-y-4 shadow-2xl">
            <div className="flex items-center justify-between">
              <h3 className="font-semibold text-gray-900">Complete Stop</h3>
              <button onClick={() => setCompleteStop(null)} className="text-gray-400 hover:text-gray-600">✕</button>
            </div>
            <p className="text-sm text-gray-600">{completeStop.label || completeStop.stop_type}</p>

            {!sigStep ? (
              <>
                {/* Photo */}
                <div className="space-y-2">
                  <p className="text-sm font-medium text-gray-700">Proof of delivery photo</p>
                  {podPhotoPreview ? (
                    <div className="relative">
                      {/* eslint-disable-next-line @next/next/no-img-element */}
                      <img src={podPhotoPreview} alt="POD preview" className="w-full h-40 object-cover rounded-lg" />
                      <button onClick={() => { setPodPhotoFile(null); setPodPhotoPreview(null); }}
                        className="absolute top-2 right-2 rounded-full bg-white/80 p-1 text-gray-600 hover:bg-white">✕</button>
                    </div>
                  ) : (
                    <label className="flex flex-col items-center justify-center gap-2 rounded-xl border-2 border-dashed border-gray-300 py-6 cursor-pointer hover:border-blue-400 hover:bg-blue-50 transition-colors">
                      <Camera className="h-8 w-8 text-gray-400" />
                      <span className="text-sm text-gray-500">Take photo or choose file</span>
                      <input type="file" accept="image/*" capture="environment" className="hidden" onChange={onPhotoChange} />
                    </label>
                  )}
                </div>

                <div className="flex gap-2">
                  <button onClick={() => setSigStep(true)}
                    className="flex-1 flex items-center justify-center gap-1.5 rounded-lg border border-indigo-200 py-2.5 text-sm font-medium text-indigo-600 hover:bg-indigo-50">
                    <FileSignature className="h-4 w-4" /> Add Signature
                  </button>
                  <button onClick={submitComplete} disabled={!!completingId}
                    className="flex-1 flex items-center justify-center gap-1.5 rounded-lg bg-green-600 py-2.5 text-sm font-medium text-white hover:bg-green-700 disabled:opacity-50">
                    {completingId ? <RefreshCw className="h-4 w-4 animate-spin" /> : <CheckCircle2 className="h-4 w-4" />}
                    {completingId ? "Saving…" : "Confirm Complete"}
                  </button>
                </div>
              </>
            ) : (
              <SignaturePad onDone={data => {
                setSigData(data);
                setSigStep(false);
              }} />
            )}

            {sigData && !sigStep && (
              <p className="text-xs text-indigo-600 flex items-center gap-1">
                <FileSignature className="h-3.5 w-3.5" /> Signature captured
              </p>
            )}
          </div>
        </div>
      )}

      {/* ── Exception modal ── */}
      {exceptionStop && (
        <div className="fixed inset-0 z-50 flex items-end sm:items-center justify-center bg-black/40 backdrop-blur-sm p-4">
          <div className="w-full max-w-md rounded-2xl bg-white p-5 space-y-4 shadow-2xl">
            <div className="flex items-center justify-between">
              <h3 className="font-semibold text-gray-900">Record Exception</h3>
              <button onClick={() => setExceptionStop(null)} className="text-gray-400 hover:text-gray-600">✕</button>
            </div>
            <p className="text-sm text-gray-600">{exceptionStop.label || exceptionStop.stop_type}</p>

            <div className="space-y-3">
              <div>
                <label className="text-xs font-medium text-gray-700 mb-1 block">Reason</label>
                <select className="input w-full" value={excForm.exception_type}
                  onChange={e => setExcForm(f => ({ ...f, exception_type: e.target.value }))}>
                  {EXCEPTION_TYPES.map(t => (
                    <option key={t} value={t}>{t.replace(/_/g, " ")}</option>
                  ))}
                </select>
              </div>
              <div>
                <label className="text-xs font-medium text-gray-700 mb-1 block">Additional notes (optional)</label>
                <textarea className="input w-full" rows={2} value={excForm.exception_reason}
                  onChange={e => setExcForm(f => ({ ...f, exception_reason: e.target.value }))}
                  placeholder="What happened?" />
              </div>
              <div>
                <label className="text-xs font-medium text-gray-700 mb-1 block">Reschedule date (optional)</label>
                <input className="input w-full" type="date" value={excForm.reschedule_date}
                  onChange={e => setExcForm(f => ({ ...f, reschedule_date: e.target.value }))} />
              </div>
            </div>

            <div className="flex gap-2">
              <button onClick={() => setExceptionStop(null)} className="flex-1 btn-secondary">Cancel</button>
              <button onClick={submitException} disabled={submittingExc}
                className="flex-1 flex items-center justify-center gap-1.5 rounded-lg bg-red-600 py-2.5 text-sm font-medium text-white hover:bg-red-700 disabled:opacity-50">
                {submittingExc ? <RefreshCw className="h-4 w-4 animate-spin" /> : <AlertTriangle className="h-4 w-4" />}
                Record
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
