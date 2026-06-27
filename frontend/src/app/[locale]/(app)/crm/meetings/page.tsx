"use client";

import { useCallback, useEffect, useState } from "react";
import { Calendar, Plus, Loader2, X, Copy, CheckCircle2, ToggleLeft, ToggleRight } from "lucide-react";
import { toast } from "sonner";
import { api } from "@/lib/api-client";

interface MeetingLink {
  id: string;
  slug: string;
  title: string;
  description: string | null;
  duration_minutes: number;
  location: string | null;
  staff_id: string | null;
  buffer_minutes: number;
  min_notice_hours: number;
  is_active: boolean;
}

export default function CrmMeetingsPage() {
  const [links, setLinks] = useState<MeetingLink[]>([]);
  const [loading, setLoading] = useState(true);
  const [selected, setSelected] = useState<MeetingLink | null>(null);
  const [showNew, setShowNew] = useState(false);
  const [form, setForm] = useState({
    title: "", slug: "", description: "", duration_minutes: "30",
    location: "", buffer_minutes: "0", min_notice_hours: "1",
  });
  const [saving, setSaving] = useState(false);
  const [copied, setCopied] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const data = await api.get<MeetingLink[]>("/api/crm/meeting-links");
      setLinks(data);
    } catch {
      toast.error("Failed to load meeting links");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  async function handleCreate() {
    if (!form.title.trim()) return;
    setSaving(true);
    try {
      await api.post("/api/crm/meeting-links", {
        title: form.title,
        slug: form.slug || undefined,
        description: form.description || undefined,
        duration_minutes: parseInt(form.duration_minutes) || 30,
        location: form.location || undefined,
        buffer_minutes: parseInt(form.buffer_minutes) || 0,
        min_notice_hours: parseInt(form.min_notice_hours) || 1,
      });
      setShowNew(false);
      setForm({ title: "", slug: "", description: "", duration_minutes: "30", location: "", buffer_minutes: "0", min_notice_hours: "1" });
      toast.success("Meeting link created");
      load();
    } catch {
      toast.error("Failed to create meeting link");
    } finally {
      setSaving(false);
    }
  }

  async function toggleActive(link: MeetingLink) {
    try {
      await api.patch(`/api/crm/meeting-links/${link.id}`, { is_active: !link.is_active });
      setLinks((prev) => prev.map((l) => l.id === link.id ? { ...l, is_active: !link.is_active } : l));
      if (selected?.id === link.id) setSelected((l) => l ? { ...l, is_active: !link.is_active } : l);
    } catch {
      toast.error("Failed to update link");
    }
  }

  function copyLink(slug: string) {
    const url = `${window.location.origin}/meet/${slug}`;
    navigator.clipboard.writeText(url).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    });
  }

  const publicBase = typeof window !== "undefined" ? window.location.origin : "";

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Calendar className="h-5 w-5 vf-text-m" />
          <h1 className="text-[15px] font-semibold vf-text-1">Meeting Links</h1>
        </div>
        <button
          onClick={() => setShowNew(!showNew)}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-indigo-600 text-white text-xs font-medium hover:bg-indigo-700 transition-colors"
        >
          <Plus className="h-3.5 w-3.5" /> New Link
        </button>
      </div>

      {/* Create form */}
      {showNew && (
        <div className="vf-card p-5 space-y-3 max-w-lg">
          <div className="flex items-center justify-between">
            <span className="text-sm font-medium vf-text-1">New meeting link</span>
            <button onClick={() => setShowNew(false)}><X className="h-4 w-4 vf-text-m" /></button>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div className="col-span-2">
              <label className="text-xs vf-text-m mb-1 block">Title *</label>
              <input type="text" value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })}
                className="w-full rounded-lg px-3 py-2 text-sm vf-input" placeholder="30-min intro call" />
            </div>
            <div className="col-span-2">
              <label className="text-xs vf-text-m mb-1 block">Slug (optional)</label>
              <input type="text" value={form.slug} onChange={(e) => setForm({ ...form, slug: e.target.value.toLowerCase().replace(/[^a-z0-9-]/g, "-") })}
                className="w-full rounded-lg px-3 py-2 text-sm vf-input" placeholder="auto-generated" />
            </div>
            <div>
              <label className="text-xs vf-text-m mb-1 block">Duration (min)</label>
              <input type="number" value={form.duration_minutes} onChange={(e) => setForm({ ...form, duration_minutes: e.target.value })}
                className="w-full rounded-lg px-3 py-2 text-sm vf-input" />
            </div>
            <div>
              <label className="text-xs vf-text-m mb-1 block">Location</label>
              <input type="text" value={form.location} onChange={(e) => setForm({ ...form, location: e.target.value })}
                className="w-full rounded-lg px-3 py-2 text-sm vf-input" placeholder="Zoom / Google Meet" />
            </div>
            <div>
              <label className="text-xs vf-text-m mb-1 block">Buffer (min)</label>
              <input type="number" value={form.buffer_minutes} onChange={(e) => setForm({ ...form, buffer_minutes: e.target.value })}
                className="w-full rounded-lg px-3 py-2 text-sm vf-input" />
            </div>
            <div>
              <label className="text-xs vf-text-m mb-1 block">Min notice (hours)</label>
              <input type="number" value={form.min_notice_hours} onChange={(e) => setForm({ ...form, min_notice_hours: e.target.value })}
                className="w-full rounded-lg px-3 py-2 text-sm vf-input" />
            </div>
            <div className="col-span-2">
              <label className="text-xs vf-text-m mb-1 block">Description</label>
              <textarea value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })}
                rows={2} className="w-full rounded-lg px-3 py-2 text-sm vf-input resize-none" />
            </div>
          </div>
          <button onClick={handleCreate} disabled={saving}
            className="w-full flex items-center justify-center gap-2 py-2 rounded-lg bg-indigo-600 text-white text-sm font-medium hover:bg-indigo-700 disabled:opacity-50 transition-colors">
            {saving && <Loader2 className="h-3.5 w-3.5 animate-spin" />}
            Create meeting link
          </button>
        </div>
      )}

      {/* Links list */}
      {loading ? (
        <div className="flex justify-center py-12"><Loader2 className="h-6 w-6 animate-spin text-gray-400" /></div>
      ) : links.length === 0 ? (
        <div className="vf-card p-8 text-center text-sm vf-text-m">No meeting links yet.</div>
      ) : (
        <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {links.map((link) => (
            <div key={link.id} className="vf-card p-4 space-y-3">
              <div className="flex items-start justify-between gap-2">
                <div className="min-w-0">
                  <p className="text-[13px] font-semibold vf-text-1 truncate">{link.title}</p>
                  <p className="text-[11px] vf-text-m mt-0.5">{link.duration_minutes} min{link.location ? ` · ${link.location}` : ""}</p>
                </div>
                <button onClick={() => toggleActive(link)} className="shrink-0">
                  {link.is_active
                    ? <ToggleRight className="h-5 w-5 text-emerald-500" />
                    : <ToggleLeft className="h-5 w-5 vf-text-m" />}
                </button>
              </div>
              {link.description && (
                <p className="text-xs vf-text-m line-clamp-2">{link.description}</p>
              )}
              <div className="flex items-center gap-2">
                <code className="flex-1 text-[10px] font-mono bg-[var(--vf-bg-elevated)] px-2 py-1 rounded truncate vf-text-m">
                  {publicBase}/meet/{link.slug}
                </code>
                <button
                  onClick={() => copyLink(link.slug)}
                  className="shrink-0 p-1.5 rounded vf-btn-ghost"
                  title="Copy link"
                >
                  {copied ? <CheckCircle2 className="h-3.5 w-3.5 text-emerald-500" /> : <Copy className="h-3.5 w-3.5 vf-text-m" />}
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
