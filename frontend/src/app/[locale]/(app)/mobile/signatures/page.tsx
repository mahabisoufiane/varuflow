"use client";

import { useState, useEffect, useRef, useCallback } from "react";
import { toast } from "sonner";
import {
  PenLine, Trash2, FileText, MapPin, Plus, ChevronDown, ChevronUp,
  RefreshCw, WifiOff, Wifi, Download, Eye, EyeOff,
} from "lucide-react";

// ─── Types ───────────────────────────────────────────────────────────────────

interface Sig {
  id: string;
  signer_name: string;
  signer_role?: string;
  document_type: string;
  ref_id?: string;
  svg_data: string;  // actually base64 PNG data URL
  ip_address?: string;
  signed_at: string;
}

interface OfflineSig {
  local_id: string;
  signer_name: string;
  signer_role: string;
  document_type: string;
  ref_id: string;
  svg_data: string; // base64 PNG
  gps_lat?: number;
  gps_lng?: number;
  saved_at: string;
}

const DOC_TYPES = ["delivery_note", "contract", "invoice", "expense", "work_order", "other"] as const;
const OFFLINE_KEY = "varuflow_offline_sigs";

function loadOffline(): OfflineSig[] {
  try { return JSON.parse(localStorage.getItem(OFFLINE_KEY) || "[]"); }
  catch { return []; }
}
function saveOffline(items: OfflineSig[]) {
  localStorage.setItem(OFFLINE_KEY, JSON.stringify(items));
}

// ─── Signature Canvas ─────────────────────────────────────────────────────────

function SignaturePad({ onCapture }: { onCapture: (dataUrl: string) => void }) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const drawing = useRef(false);
  // Undo stack: snapshots of canvas ImageData after each lift
  const undoStack = useRef<ImageData[]>([]);

  function c() { return canvasRef.current?.getContext("2d") ?? null; }

  function toInternalCoords(e: React.PointerEvent) {
    const rect = canvasRef.current!.getBoundingClientRect();
    const scaleX = canvasRef.current!.width / rect.width;
    const scaleY = canvasRef.current!.height / rect.height;
    return { x: (e.clientX - rect.left) * scaleX, y: (e.clientY - rect.top) * scaleY };
  }

  function onDown(e: React.PointerEvent) {
    e.preventDefault();
    (e.target as HTMLElement).setPointerCapture(e.pointerId);
    drawing.current = true;
    const ctx = c()!;
    // Snapshot before new stroke for undo
    undoStack.current.push(ctx.getImageData(0, 0, canvasRef.current!.width, canvasRef.current!.height));
    const { x, y } = toInternalCoords(e);
    ctx.beginPath();
    ctx.moveTo(x, y);
    ctx.lineWidth = e.pointerType === "pen" ? e.pressure * 4 + 1 : 2.5;
    ctx.strokeStyle = "#1e293b";
    ctx.lineCap = "round";
    ctx.lineJoin = "round";
  }

  function onMove(e: React.PointerEvent) {
    e.preventDefault();
    if (!drawing.current) return;
    const ctx = c()!;
    const { x, y } = toInternalCoords(e);
    // Pressure-sensitive width for stylus
    if (e.pointerType === "pen") {
      ctx.lineWidth = Math.max(1, e.pressure * 4 + 0.5);
    }
    ctx.lineTo(x, y);
    ctx.stroke();
    ctx.beginPath();
    ctx.moveTo(x, y);
  }

  function onUp() { drawing.current = false; }

  function undo() {
    if (!undoStack.current.length) return;
    c()!.putImageData(undoStack.current.pop()!, 0, 0);
  }

  function clear() {
    const canvas = canvasRef.current!;
    c()!.clearRect(0, 0, canvas.width, canvas.height);
    undoStack.current = [];
  }

  function capture() {
    const data = canvasRef.current!.toDataURL("image/png");
    onCapture(data);
    toast.success("Signature captured");
  }

  return (
    <div className="space-y-2">
      <canvas
        ref={canvasRef}
        width={640} height={220}
        className="w-full rounded-xl border-2 border-gray-300 bg-white"
        style={{ touchAction: "none", cursor: "crosshair" }}
        onPointerDown={onDown}
        onPointerMove={onMove}
        onPointerUp={onUp}
        onPointerLeave={onUp}
        onPointerCancel={onUp}
      />
      <p className="text-xs text-center text-gray-400">Draw your signature above (finger, stylus, or mouse)</p>
      <div className="grid grid-cols-3 gap-2">
        <button onClick={undo} className="rounded-lg border border-gray-300 py-2 text-sm text-gray-600 hover:bg-gray-50">← Undo</button>
        <button onClick={clear} className="rounded-lg border border-gray-300 py-2 text-sm text-gray-600 hover:bg-gray-50">Clear</button>
        <button onClick={capture} className="rounded-lg bg-indigo-600 py-2 text-sm font-medium text-white hover:bg-indigo-700">
          Capture
        </button>
      </div>
    </div>
  );
}

// ─── Main Page ────────────────────────────────────────────────────────────────

export default function SignaturesPage() {
  const apiBase = process.env.NEXT_PUBLIC_API_URL!;
  const [sigs, setSigs] = useState<Sig[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [showCreate, setShowCreate] = useState(false);
  const [expanded, setExpanded] = useState<string | null>(null);
  const [offline, setOffline] = useState<OfflineSig[]>([]);
  const [syncing, setSyncing] = useState(false);
  const [isOnline, setIsOnline] = useState(true);
  const [showPreviews, setShowPreviews] = useState<Set<string>>(new Set());

  // Form
  const [formName, setFormName] = useState("");
  const [formRole, setFormRole] = useState("");
  const [formDocType, setFormDocType] = useState<string>("delivery_note");
  const [formRefId, setFormRefId] = useState("");
  const [captured, setCaptured] = useState<string | null>(null);
  const [gps, setGps] = useState<{ lat: number; lng: number } | null>(null);
  const [gpsLoading, setGpsLoading] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  const fetch_ = useCallback((url: string, opts?: RequestInit) =>
    fetch(`${apiBase}${url}`, { credentials: "include", ...opts }), [apiBase]);

  useEffect(() => {
    setIsOnline(navigator.onLine);
    const up = () => { setIsOnline(true); };
    const dn = () => setIsOnline(false);
    window.addEventListener("online", up);
    window.addEventListener("offline", dn);
    return () => { window.removeEventListener("online", up); window.removeEventListener("offline", dn); };
  }, []);

  useEffect(() => {
    setOffline(loadOffline());
  }, []);

  useEffect(() => {
    if (isOnline) load(1);
  }, [isOnline]);

  async function load(p: number) {
    try {
      const res = await fetch_(`/api/mobile/signatures?page=${p}&limit=20`);
      if (res.ok) {
        const j = await res.json();
        setSigs(j.signatures);
        setTotal(j.total);
        setPage(p);
      }
    } catch { /* offline — silent */ }
  }

  function getGps() {
    setGpsLoading(true);
    navigator.geolocation.getCurrentPosition(
      pos => { setGps({ lat: pos.coords.latitude, lng: pos.coords.longitude }); setGpsLoading(false); },
      () => { toast.error("GPS not available"); setGpsLoading(false); },
    );
  }

  async function submit() {
    if (!formName.trim()) { toast.error("Signer name is required"); return; }
    if (!captured) { toast.error("Please capture a signature first"); return; }

    if (!isOnline) {
      const items = loadOffline();
      items.push({
        local_id: crypto.randomUUID(),
        signer_name: formName, signer_role: formRole,
        document_type: formDocType, ref_id: formRefId,
        svg_data: captured,
        gps_lat: gps?.lat, gps_lng: gps?.lng,
        saved_at: new Date().toISOString(),
      });
      saveOffline(items);
      setOffline(items);
      toast.success("Saved offline — will sync when connected");
      resetForm();
      return;
    }

    setSubmitting(true);
    try {
      const res = await fetch_("/api/mobile/signatures", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          signer_name: formName,
          signer_role: formRole || undefined,
          document_type: formDocType,
          ref_id: formRefId || undefined,
          svg_data: captured,
        }),
      });
      if (res.ok) {
        toast.success("Signature saved");
        resetForm();
        await load(1);
      } else {
        toast.error("Failed to save");
      }
    } finally {
      setSubmitting(false);
    }
  }

  function resetForm() {
    setFormName(""); setFormRole(""); setFormDocType("delivery_note");
    setFormRefId(""); setCaptured(null); setGps(null); setShowCreate(false);
  }

  async function syncOffline() {
    const pending = loadOffline();
    if (!pending.length) { toast.info("Nothing to sync"); return; }
    setSyncing(true);
    let count = 0;
    const remaining: OfflineSig[] = [];
    for (const item of pending) {
      try {
        const res = await fetch_("/api/mobile/signatures", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            signer_name: item.signer_name, signer_role: item.signer_role || undefined,
            document_type: item.document_type, ref_id: item.ref_id || undefined,
            svg_data: item.svg_data,
          }),
        });
        if (res.ok) { count++; } else { remaining.push(item); }
      } catch { remaining.push(item); }
    }
    saveOffline(remaining);
    setOffline(remaining);
    toast.success(`Synced ${count} signature${count !== 1 ? "s" : ""}`);
    setSyncing(false);
    await load(1);
  }

  async function deleteSig(id: string) {
    await fetch_(`/api/mobile/signatures/${id}`, { method: "DELETE" });
    toast.success("Deleted");
    await load(page);
  }

  function togglePreview(id: string) {
    setShowPreviews(prev => {
      const next = new Set(prev);
      next.has(id) ? next.delete(id) : next.add(id);
      return next;
    });
  }

  const docLabel = (t: string) => t.replace(/_/g, " ");

  return (
    <div className="space-y-6 max-w-2xl mx-auto">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-gray-900">Digital Signatures</h1>
          <p className="mt-1 text-sm text-gray-500">Touch-based signature capture for deliveries, contracts, and approvals.</p>
        </div>
        <div className="flex items-center gap-2">
          {offline.length > 0 && (
            <button onClick={syncOffline} disabled={syncing || !isOnline}
              className="flex items-center gap-1.5 rounded-lg bg-amber-500 px-3 py-2 text-sm font-medium text-white hover:bg-amber-600 disabled:opacity-50">
              {syncing ? <RefreshCw className="h-3.5 w-3.5 animate-spin" /> : <Wifi className="h-3.5 w-3.5" />}
              Sync {offline.length}
            </button>
          )}
          <button onClick={() => setShowCreate(v => !v)} className="btn-primary flex items-center gap-2">
            <Plus className="h-4 w-4" /> Capture
          </button>
        </div>
      </div>

      {!isOnline && (
        <div className="flex items-center gap-2 rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-700">
          <WifiOff className="h-4 w-4 flex-shrink-0" />
          Offline — signatures are saved locally and uploaded when you reconnect.
        </div>
      )}

      {/* Capture panel */}
      {showCreate && (
        <div className="rounded-xl border border-blue-200 bg-blue-50 p-5 space-y-4">
          <h2 className="font-semibold text-gray-900">New Signature</h2>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div>
              <label className="text-xs font-medium text-gray-700 mb-1 block">Signer name *</label>
              <input className="input w-full" placeholder="Full name" value={formName}
                onChange={e => setFormName(e.target.value)} />
            </div>
            <div>
              <label className="text-xs font-medium text-gray-700 mb-1 block">Role (optional)</label>
              <input className="input w-full" placeholder="e.g. Warehouse manager" value={formRole}
                onChange={e => setFormRole(e.target.value)} />
            </div>
            <div>
              <label className="text-xs font-medium text-gray-700 mb-1 block">Attach to</label>
              <select className="input w-full" value={formDocType} onChange={e => setFormDocType(e.target.value)}>
                {DOC_TYPES.map(t => <option key={t} value={t}>{docLabel(t)}</option>)}
              </select>
            </div>
            <div>
              <label className="text-xs font-medium text-gray-700 mb-1 block">Reference ID (optional)</label>
              <input className="input w-full" placeholder="Invoice / order / job ID" value={formRefId}
                onChange={e => setFormRefId(e.target.value)} />
            </div>
          </div>

          <div className="flex items-center gap-2">
            <button onClick={getGps} disabled={gpsLoading}
              className="flex items-center gap-1.5 rounded-lg border border-gray-300 px-3 py-2 text-xs text-gray-600 hover:bg-white disabled:opacity-50">
              <MapPin className="h-3.5 w-3.5" />
              {gpsLoading ? "Getting GPS…" : gps ? `GPS: ${gps.lat.toFixed(5)}, ${gps.lng.toFixed(5)}` : "Add GPS location (optional)"}
            </button>
            {gps && <button onClick={() => setGps(null)} className="text-xs text-red-500 hover:underline">Clear</button>}
          </div>

          <div>
            <label className="text-xs font-medium text-gray-700 mb-2 block">Signature *</label>
            <SignaturePad onCapture={data => setCaptured(data)} />
          </div>

          {captured && (
            <div className="space-y-1">
              <p className="text-xs font-medium text-green-600">✓ Signature captured</p>
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img src={captured} alt="Preview" className="h-16 w-full object-contain rounded-lg border border-gray-200 bg-white" />
            </div>
          )}

          <div className="flex gap-2 pt-1">
            <button onClick={resetForm} className="btn-secondary">Cancel</button>
            <button onClick={submit} disabled={submitting}
              className="btn-primary flex items-center gap-1.5 disabled:opacity-50">
              {submitting && <RefreshCw className="h-3.5 w-3.5 animate-spin" />}
              {isOnline ? "Save Signature" : "Save Offline"}
            </button>
          </div>
        </div>
      )}

      {/* Offline queue */}
      {offline.length > 0 && (
        <div className="rounded-xl border border-amber-200 bg-amber-50 p-4 space-y-2">
          <p className="text-sm font-semibold text-amber-800">Pending upload ({offline.length})</p>
          {offline.map(s => (
            <div key={s.local_id} className="flex items-center justify-between rounded-lg bg-white/60 px-3 py-2">
              <div>
                <p className="text-sm font-medium text-gray-900">{s.signer_name}</p>
                <p className="text-xs text-gray-500">{docLabel(s.document_type)} · {new Date(s.saved_at).toLocaleTimeString()}</p>
              </div>
              <button onClick={() => { const u = loadOffline().filter(x => x.local_id !== s.local_id); saveOffline(u); setOffline(u); }}
                className="text-red-400 hover:text-red-600"><Trash2 className="h-4 w-4" /></button>
            </div>
          ))}
        </div>
      )}

      {/* Server-side list */}
      <div className="space-y-2">
        <div className="flex items-center justify-between">
          <p className="text-sm font-semibold text-gray-700">Signatures ({total})</p>
          {total > 20 && (
            <div className="flex gap-2 text-xs">
              <button onClick={() => load(page - 1)} disabled={page <= 1} className="text-blue-600 hover:underline disabled:opacity-30">← Prev</button>
              <span className="text-gray-400">Page {page}</span>
              <button onClick={() => load(page + 1)} disabled={page * 20 >= total} className="text-blue-600 hover:underline disabled:opacity-30">Next →</button>
            </div>
          )}
        </div>

        {sigs.length === 0 && !offline.length && (
          <p className="text-sm text-gray-400 text-center py-12">No signatures captured yet.</p>
        )}

        {sigs.map(s => (
          <div key={s.id} className="rounded-xl border border-gray-200 bg-white overflow-hidden">
            <button onClick={() => setExpanded(expanded === s.id ? null : s.id)}
              className="w-full flex items-center justify-between p-4 text-left hover:bg-gray-50">
              <div className="flex items-center gap-3">
                <PenLine className="h-4 w-4 text-indigo-500 flex-shrink-0" />
                <div>
                  <p className="font-medium text-sm text-gray-900">{s.signer_name}</p>
                  <p className="text-xs text-gray-500">
                    {docLabel(s.document_type)}{s.signer_role && ` · ${s.signer_role}`} · {new Date(s.signed_at).toLocaleString()}
                  </p>
                </div>
              </div>
              {expanded === s.id ? <ChevronUp className="h-4 w-4 text-gray-400" /> : <ChevronDown className="h-4 w-4 text-gray-400" />}
            </button>

            {expanded === s.id && (
              <div className="border-t border-gray-100 p-4 space-y-3">
                {/* Signature preview toggle */}
                <button onClick={() => togglePreview(s.id)}
                  className="flex items-center gap-1.5 text-xs text-gray-500 hover:text-gray-700">
                  {showPreviews.has(s.id) ? <EyeOff className="h-3.5 w-3.5" /> : <Eye className="h-3.5 w-3.5" />}
                  {showPreviews.has(s.id) ? "Hide signature" : "Show signature"}
                </button>
                {showPreviews.has(s.id) && (
                  s.svg_data.startsWith("data:image/")
                    ? (
                      // eslint-disable-next-line @next/next/no-img-element
                      <img src={s.svg_data} alt="Signature" className="h-24 w-full object-contain rounded-lg border border-gray-200 bg-white" />
                    )
                    : (
                      <div className="rounded-lg bg-gray-50 p-2" dangerouslySetInnerHTML={{ __html: s.svg_data }} />
                    )
                )}

                <div className="grid grid-cols-2 gap-1 text-xs text-gray-400">
                  {s.ref_id && <span>Ref: {s.ref_id}</span>}
                  {s.ip_address && <span>IP: {s.ip_address}</span>}
                </div>

                <div className="flex gap-2">
                  <a href={`${apiBase}/api/mobile/signatures/${s.id}/pdf`} target="_blank" rel="noopener noreferrer"
                    className="flex-1 flex items-center justify-center gap-1.5 rounded-lg border border-blue-200 py-2 text-xs font-medium text-blue-600 hover:bg-blue-50">
                    <FileText className="h-3.5 w-3.5" /> PDF
                  </a>
                  {s.svg_data.startsWith("data:image/") && (
                    <a href={s.svg_data} download={`sig-${s.id}.png`}
                      className="flex-1 flex items-center justify-center gap-1.5 rounded-lg border border-gray-200 py-2 text-xs font-medium text-gray-600 hover:bg-gray-50">
                      <Download className="h-3.5 w-3.5" /> PNG
                    </a>
                  )}
                  <button onClick={() => deleteSig(s.id)}
                    className="flex items-center justify-center gap-1 rounded-lg border border-red-200 px-3 py-2 text-xs text-red-500 hover:bg-red-50">
                    <Trash2 className="h-3.5 w-3.5" />
                  </button>
                </div>
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
