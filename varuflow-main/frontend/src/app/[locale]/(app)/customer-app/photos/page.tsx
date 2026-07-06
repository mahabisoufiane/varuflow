"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api-client";
import { RefreshCw, Trash2, Camera, Eye, ChevronDown, ChevronUp } from "lucide-react";
import { Button } from "@/components/ui/button";
import { toast } from "sonner";

interface Photo {
  id: string;
  sent_by: string;
  appointment_id: string | null;
  customer_id: string | null;
  photo_url: string;
  caption: string | null;
  is_viewed: boolean;
  created_at: string;
}

function relativeTime(dateStr: string): string {
  const diff = Math.floor((Date.now() - new Date(dateStr).getTime()) / 1000);
  if (diff < 60) return `${diff}s ago`;
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
  return `${Math.floor(diff / 86400)}d ago`;
}

export default function PhotosPage() {
  const [photos, setPhotos] = useState<Photo[]>([]);
  const [loading, setLoading] = useState(true);
  const [tab, setTab] = useState<"all" | "unviewed">("all");
  const [expanded, setExpanded] = useState<string | null>(null);
  const [actionLoading, setActionLoading] = useState<string | null>(null);
  const [imgErrors, setImgErrors] = useState<Record<string, boolean>>({});

  const [form, setForm] = useState({
    appointment_id: "",
    customer_id: "",
    photo_url: "",
    caption: "",
  });

  async function load() {
    setLoading(true);
    try {
      const data = await api.get<Photo[]>("/api/photos");
      setPhotos(data);
    } catch {
      toast.error("Failed to load photos");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { load(); }, []); // eslint-disable-line react-hooks/exhaustive-deps

  async function sendPhoto() {
    if (!form.photo_url.trim()) { toast.error("Photo URL is required"); return; }
    setActionLoading("send");
    try {
      await api.post("/api/photos", {
        appointment_id: form.appointment_id || null,
        customer_id: form.customer_id || null,
        photo_url: form.photo_url,
        caption: form.caption || null,
      });
      toast.success("Photo sent");
      setForm({ appointment_id: "", customer_id: "", photo_url: "", caption: "" });
      await load();
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Something went wrong");
    } finally {
      setActionLoading(null);
    }
  }

  async function markViewed(id: string) {
    setActionLoading("view_" + id);
    try {
      await api.patch(`/api/photos/${id}/view`, {});
      await load();
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Something went wrong");
    } finally {
      setActionLoading(null);
    }
  }

  async function deletePhoto(id: string) {
    setActionLoading("del_" + id);
    try {
      await api.delete(`/api/photos/${id}`);
      toast.success("Photo deleted");
      setExpanded(null);
      await load();
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Something went wrong");
    } finally {
      setActionLoading(null);
    }
  }

  const unviewedCount = photos.filter((p) => !p.is_viewed).length;
  const displayed = tab === "unviewed" ? photos.filter((p) => !p.is_viewed) : photos;

  return (
    <div className="mx-auto max-w-4xl space-y-6 p-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-xl font-semibold text-gray-900">Photo Updates</h1>
            {unviewedCount > 0 && (
              <span className="inline-flex items-center justify-center h-5 min-w-5 rounded-full bg-amber-500 text-white text-xs px-1.5">
                {unviewedCount}
              </span>
            )}
          </div>
          <p className="text-sm text-muted-foreground mt-0.5">
            Send visual service progress updates to customers.
          </p>
        </div>
      </div>

      {/* Send photo form */}
      <div className="rounded-xl border border-[var(--vf-brand-primary)]/20 bg-white p-5 shadow-sm space-y-4">
        <h3 className="text-sm font-semibold text-gray-900">Send Photo</h3>
        <div className="grid grid-cols-2 gap-3">
          <div className="space-y-1">
            <label className="text-xs font-medium text-gray-700">Appointment ID (optional)</label>
            <input
              value={form.appointment_id}
              onChange={(e) => setForm((f) => ({ ...f, appointment_id: e.target.value }))}
              placeholder="UUID"
              className="block w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-[var(--vf-brand-primary)]"
            />
          </div>
          <div className="space-y-1">
            <label className="text-xs font-medium text-gray-700">Customer ID (optional)</label>
            <input
              value={form.customer_id}
              onChange={(e) => setForm((f) => ({ ...f, customer_id: e.target.value }))}
              placeholder="UUID"
              className="block w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-[var(--vf-brand-primary)]"
            />
          </div>
        </div>
        <div className="space-y-1">
          <label className="text-xs font-medium text-gray-700">Photo URL *</label>
          <input
            value={form.photo_url}
            onChange={(e) => setForm((f) => ({ ...f, photo_url: e.target.value }))}
            placeholder="https://…"
            className="block w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-[var(--vf-brand-primary)]"
          />
        </div>
        <div className="space-y-1">
          <label className="text-xs font-medium text-gray-700">Caption</label>
          <textarea
            rows={2}
            value={form.caption}
            onChange={(e) => setForm((f) => ({ ...f, caption: e.target.value }))}
            placeholder="Work in progress on the rear bumper…"
            className="block w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-[var(--vf-brand-primary)]"
          />
        </div>
        <Button disabled={actionLoading === "send"} onClick={sendPhoto}
          className="bg-[var(--vf-brand-primary)] hover:bg-[var(--vf-brand-primary-hover)] text-white gap-2">
          {actionLoading === "send" ? <RefreshCw className="h-4 w-4 animate-spin" /> : <Camera className="h-4 w-4" />}
          Send Photo
        </Button>
      </div>

      {/* Filter tabs */}
      <div className="flex items-center gap-1 border-b">
        {(["all", "unviewed"] as const).map((t) => (
          <button key={t} type="button" onClick={() => setTab(t)}
            className={`px-4 py-2.5 text-sm font-medium border-b-2 transition-colors capitalize ${
              tab === t ? "border-[var(--vf-brand-primary)] text-[var(--vf-text-primary)]" : "border-transparent text-muted-foreground hover:text-gray-700"
            }`}>
            {t === "unviewed" ? `Unviewed (${unviewedCount})` : "All"}
          </button>
        ))}
      </div>

      {/* Photos list */}
      {loading && photos.length === 0 ? (
        <div className="text-center py-12">
          <RefreshCw className="h-6 w-6 animate-spin mx-auto text-muted-foreground" />
        </div>
      ) : displayed.length === 0 ? (
        <div className="rounded-xl border bg-white shadow-sm py-12 text-center">
          <Camera className="h-10 w-10 text-muted-foreground mx-auto mb-3" />
          <p className="text-gray-600 font-medium">
            {tab === "unviewed"
              ? "No unviewed photos"
              : "No photo updates yet — use this to send visual progress updates to customers."}
          </p>
        </div>
      ) : (
        <div className="rounded-xl border bg-white shadow-sm divide-y divide-gray-100">
          {displayed.map((photo) => (
            <div key={photo.id}>
              {/* Summary row */}
              <div className="flex items-center gap-4 px-5 py-4">
                {/* Thumbnail */}
                <div className="flex-shrink-0">
                  {imgErrors[photo.id] ? (
                    <div className="h-20 w-20 rounded-md bg-gray-100 flex items-center justify-center">
                      <Camera className="h-6 w-6 text-gray-400" />
                    </div>
                  ) : (
                    // eslint-disable-next-line @next/next/no-img-element
                    <img
                      src={photo.photo_url}
                      alt="Service photo"
                      className="h-20 w-20 rounded-md object-cover border"
                      onError={() => setImgErrors((e) => ({ ...e, [photo.id]: true }))}
                    />
                  )}
                </div>

                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-0.5">
                    <span className={`h-2 w-2 rounded-full flex-shrink-0 ${photo.is_viewed ? "bg-green-400" : "bg-amber-400"}`} />
                    <span className="text-xs text-muted-foreground">{photo.is_viewed ? "Viewed" : "Unviewed"}</span>
                  </div>
                  <p className="text-xs text-muted-foreground">
                    From: <span className="font-mono">{photo.sent_by.slice(0, 8)}…</span>
                    {photo.appointment_id && ` · Appt: ${photo.appointment_id.slice(0, 8)}…`}
                  </p>
                  {photo.caption && (
                    <p className="text-sm text-gray-700 truncate mt-0.5">{photo.caption}</p>
                  )}
                  <p className="text-xs text-muted-foreground mt-0.5">{relativeTime(photo.created_at)}</p>
                </div>

                <button
                  type="button"
                  onClick={() => setExpanded(expanded === photo.id ? null : photo.id)}
                  className="flex-shrink-0 text-muted-foreground hover:text-gray-700 p-1"
                >
                  {expanded === photo.id ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
                </button>
              </div>

              {/* Expanded detail */}
              {expanded === photo.id && (
                <div className="px-5 pb-5 space-y-3 bg-gray-50 border-t">
                  {/* eslint-disable-next-line @next/next/no-img-element */}
                  <img
                    src={photo.photo_url}
                    className="w-full max-w-sm rounded-lg mt-3"
                    alt="Service photo"
                  />
                  {photo.caption && (
                    <p className="text-sm text-gray-700">{photo.caption}</p>
                  )}
                  <div className="flex items-center gap-2">
                    {!photo.is_viewed && (
                      <Button size="sm" variant="outline"
                        disabled={actionLoading === "view_" + photo.id}
                        onClick={() => markViewed(photo.id)}
                        className="gap-1"
                      >
                        {actionLoading === "view_" + photo.id
                          ? <RefreshCw className="h-3 w-3 animate-spin" />
                          : <Eye className="h-3 w-3" />}
                        Mark Viewed
                      </Button>
                    )}
                    <Button size="sm" variant="ghost"
                      disabled={actionLoading === "del_" + photo.id}
                      onClick={() => deletePhoto(photo.id)}
                      className="gap-1 text-red-500 hover:text-red-700 hover:bg-red-50"
                    >
                      {actionLoading === "del_" + photo.id
                        ? <RefreshCw className="h-3 w-3 animate-spin" />
                        : <Trash2 className="h-3 w-3" />}
                      Delete
                    </Button>
                  </div>
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
