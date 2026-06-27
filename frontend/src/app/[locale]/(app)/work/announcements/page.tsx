"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api-client";
import { Pin, Plus, Eye, CheckSquare, Trash2, AlertCircle, Megaphone } from "lucide-react";

interface Announcement {
  id: string;
  title: string;
  body: string;
  author_id: string | null;
  category: string;
  target_role: string | null;
  is_pinned: boolean;
  acknowledgement_required: boolean;
  emoji_reactions: Record<string, number>;
  published_at: string | null;
  expires_at: string | null;
  created_at: string;
  read_at: string | null;
  acknowledged_at: string | null;
  read_count: number;
}

const CATEGORIES = ["general", "HR update", "policy", "operational", "celebration"];
const ALLOWED_EMOJIS = ["👍", "❤️", "🎉", "👀", "✅", "🙏"];

const CATEGORY_COLORS: Record<string, string> = {
  "HR update": "bg-blue-100 text-blue-700",
  policy: "bg-yellow-100 text-yellow-700",
  operational: "bg-gray-100 text-gray-700",
  celebration: "bg-pink-100 text-pink-700",
  general: "bg-indigo-100 text-indigo-700",
};

export default function AnnouncementsPage() {
  const router = useRouter();
  const [items, setItems] = useState<Announcement[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [role, setRole] = useState<string>("MEMBER");

  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState({
    title: "",
    body: "",
    category: "general",
    target_role: "",
    is_pinned: false,
    acknowledgement_required: false,
    expires_at: "",
  });
  const [saving, setSaving] = useState(false);

  const [receiptsFor, setReceiptsFor] = useState<Announcement | null>(null);
  const [receipts, setReceipts] = useState<{ staff_id: string; read_at: string | null; acknowledged_at: string | null }[]>([]);

  async function load() {
    setLoading(true);
    try {
      const [data, meData] = await Promise.all([
        api.get("/api/announcements"),
        api.get("/api/auth/me").catch(() => null),
      ]);
      setItems(Array.isArray(data) ? data : []);
      if (meData?.role) setRole(meData.role);
    } catch (e: any) {
      if (e?.status === 401) { router.push("/auth/login"); return; }
      setError("Failed to load announcements");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { load(); }, []);

  async function markRead(id: string) {
    try { await api.post(`/api/announcements/${id}/read`, {}); } catch {}
    setItems(prev =>
      prev.map(a =>
        a.id === id
          ? { ...a, read_at: new Date().toISOString() }
          : a
      )
    );
  }

  async function acknowledge(id: string) {
    try { await api.post(`/api/announcements/${id}/acknowledge`, {}); } catch {}
    setItems(prev =>
      prev.map(a =>
        a.id === id
          ? { ...a, read_at: a.read_at ?? new Date().toISOString(), acknowledged_at: new Date().toISOString() }
          : a
      )
    );
  }

  async function react(id: string, emoji: string) {
    try {
      const data = await api.post(`/api/announcements/${id}/react`, { emoji });
      setItems(prev => prev.map(a => a.id === id ? { ...a, emoji_reactions: data.emoji_reactions } : a));
    } catch {}
  }

  async function deleteAnn(id: string) {
    if (!confirm("Delete this announcement?")) return;
    try {
      await api.delete(`/api/announcements/${id}`);
      setItems(prev => prev.filter(a => a.id !== id));
    } catch { alert("Delete failed"); }
  }

  async function create() {
    if (!form.title.trim() || !form.body.trim()) { alert("Title and body are required"); return; }
    setSaving(true);
    try {
      const body: Record<string, unknown> = {
        title: form.title,
        body: form.body,
        category: form.category,
        is_pinned: form.is_pinned,
        acknowledgement_required: form.acknowledgement_required,
      };
      if (form.target_role) body.target_role = form.target_role;
      if (form.expires_at) body.expires_at = form.expires_at;
      const data = await api.post("/api/announcements", body);
      setItems(prev => [data, ...prev]);
      setShowForm(false);
      setForm({ title: "", body: "", category: "general", target_role: "", is_pinned: false, acknowledgement_required: false, expires_at: "" });
    } catch { alert("Save failed"); }
    finally { setSaving(false); }
  }

  async function loadReceipts(ann: Announcement) {
    setReceiptsFor(ann);
    try {
      const data = await api.get(`/api/announcements/${ann.id}/reads`);
      setReceipts(data);
    } catch { setReceipts([]); }
  }

  const isManager = role === "OWNER" || role === "ADMIN";

  if (loading) return <div className="p-8 text-center text-gray-400">Loading…</div>;

  return (
    <div className="p-6 max-w-3xl mx-auto space-y-6">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Megaphone className="w-5 h-5 text-indigo-600" />
          <h1 className="text-xl font-bold text-gray-900">Announcements</h1>
        </div>
        {isManager && (
          <button onClick={() => setShowForm(v => !v)} className="btn-primary flex items-center gap-1 text-sm">
            <Plus className="w-4 h-4" /> Post
          </button>
        )}
      </div>

      {error && (
        <div className="rounded bg-red-50 border border-red-200 text-red-700 text-sm p-3 flex gap-2">
          <AlertCircle className="w-4 h-4 mt-0.5 shrink-0" />{error}
        </div>
      )}

      {showForm && (
        <div className="rounded-xl border bg-white shadow-sm p-5 space-y-4">
          <h2 className="font-semibold text-gray-800">New Announcement</h2>
          <div className="space-y-3">
            <input
              className="input w-full"
              placeholder="Title *"
              value={form.title}
              onChange={e => setForm(f => ({ ...f, title: e.target.value }))}
            />
            <textarea
              className="input w-full min-h-[120px]"
              placeholder="Body *"
              value={form.body}
              onChange={e => setForm(f => ({ ...f, body: e.target.value }))}
            />
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="text-xs text-gray-500 mb-1 block">Category</label>
                <select className="input w-full" value={form.category} onChange={e => setForm(f => ({ ...f, category: e.target.value }))}>
                  {CATEGORIES.map(c => <option key={c}>{c}</option>)}
                </select>
              </div>
              <div>
                <label className="text-xs text-gray-500 mb-1 block">Visible to</label>
                <select className="input w-full" value={form.target_role} onChange={e => setForm(f => ({ ...f, target_role: e.target.value }))}>
                  <option value="">All staff</option>
                  <option value="OWNER">Owner only</option>
                  <option value="ADMIN">Admin / Manager</option>
                  <option value="MEMBER">Member</option>
                </select>
              </div>
            </div>
            <div>
              <label className="text-xs text-gray-500 mb-1 block">Expires on (optional)</label>
              <input
                type="date"
                className="input"
                value={form.expires_at}
                onChange={e => setForm(f => ({ ...f, expires_at: e.target.value }))}
              />
            </div>
            <div className="flex gap-6">
              <label className="flex items-center gap-2 text-sm cursor-pointer">
                <input type="checkbox" checked={form.is_pinned} onChange={e => setForm(f => ({ ...f, is_pinned: e.target.checked }))} />
                Pin to top
              </label>
              <label className="flex items-center gap-2 text-sm cursor-pointer">
                <input type="checkbox" checked={form.acknowledgement_required} onChange={e => setForm(f => ({ ...f, acknowledgement_required: e.target.checked }))} />
                Require acknowledgement
              </label>
            </div>
          </div>
          <div className="flex gap-3">
            <button onClick={create} disabled={saving} className="btn-primary text-sm">
              {saving ? "Publishing…" : "Publish"}
            </button>
            <button onClick={() => setShowForm(false)} className="btn-secondary text-sm">Cancel</button>
          </div>
        </div>
      )}

      {items.length === 0 && !showForm && (
        <div className="text-center py-16 text-gray-400">
          <Megaphone className="w-10 h-10 mx-auto mb-3 opacity-30" />
          <p>No announcements yet.</p>
        </div>
      )}

      {items.map(ann => (
        <div
          key={ann.id}
          className={`rounded-xl border bg-white shadow-sm p-5 space-y-3 ${ann.is_pinned ? "border-indigo-300 ring-1 ring-indigo-200" : "border-gray-200"}`}
          onMouseEnter={() => { if (!ann.read_at) markRead(ann.id); }}
        >
          {/* Header */}
          <div className="flex items-start justify-between gap-3">
            <div className="flex items-start gap-2 flex-1 min-w-0">
              {ann.is_pinned && <Pin className="w-4 h-4 text-indigo-500 mt-0.5 shrink-0" />}
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 flex-wrap">
                  <span className="font-semibold text-gray-900">{ann.title}</span>
                  <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${CATEGORY_COLORS[ann.category] ?? "bg-gray-100 text-gray-600"}`}>
                    {ann.category}
                  </span>
                  {ann.target_role && (
                    <span className="text-xs px-2 py-0.5 rounded-full bg-purple-100 text-purple-700 font-medium">
                      {ann.target_role} only
                    </span>
                  )}
                  {!ann.read_at && (
                    <span className="text-xs px-2 py-0.5 rounded-full bg-blue-500 text-white font-medium">New</span>
                  )}
                </div>
                <p className="text-xs text-gray-400 mt-0.5">
                  {ann.published_at
                    ? new Date(ann.published_at).toLocaleDateString()
                    : new Date(ann.created_at).toLocaleDateString()}
                  {ann.expires_at ? ` · Expires ${new Date(ann.expires_at).toLocaleDateString()}` : ""}
                </p>
              </div>
            </div>
            {isManager && (
              <div className="flex items-center gap-1 shrink-0">
                <button
                  onClick={() => loadReceipts(ann)}
                  title="Read receipts"
                  className="p-1.5 text-gray-400 hover:text-indigo-600 rounded hover:bg-indigo-50"
                >
                  <Eye className="w-4 h-4" />
                </button>
                <button
                  onClick={() => deleteAnn(ann.id)}
                  title="Delete"
                  className="p-1.5 text-gray-400 hover:text-red-500 rounded hover:bg-red-50"
                >
                  <Trash2 className="w-4 h-4" />
                </button>
              </div>
            )}
          </div>

          {/* Body */}
          <p className="text-sm text-gray-700 whitespace-pre-wrap">{ann.body}</p>

          {/* Footer: reactions + status */}
          <div className="flex items-center gap-3 flex-wrap pt-2 border-t border-gray-100">
            <div className="flex gap-1">
              {ALLOWED_EMOJIS.map(emoji => (
                <button
                  key={emoji}
                  onClick={() => react(ann.id, emoji)}
                  className="text-sm px-1.5 py-0.5 rounded hover:bg-gray-100 border border-transparent hover:border-gray-200 transition-colors"
                  title={`React ${emoji}`}
                >
                  {emoji}
                  {(ann.emoji_reactions?.[emoji] ?? 0) > 0 && (
                    <span className="ml-0.5 text-xs text-gray-500">{ann.emoji_reactions[emoji]}</span>
                  )}
                </button>
              ))}
            </div>

            <div className="flex-1" />

            <div className="flex items-center gap-3 text-xs">
              {ann.read_at ? (
                <span className="text-green-600 flex items-center gap-1">
                  <Eye className="w-3 h-3" /> Read
                </span>
              ) : (
                <span className="text-gray-400">Unread</span>
              )}
              {ann.acknowledgement_required && (
                ann.acknowledged_at ? (
                  <span className="text-green-600 flex items-center gap-1">
                    <CheckSquare className="w-3 h-3" /> Acknowledged
                  </span>
                ) : (
                  <button
                    onClick={() => acknowledge(ann.id)}
                    className="flex items-center gap-1 px-2 py-1 rounded bg-amber-50 border border-amber-300 text-amber-700 hover:bg-amber-100 font-medium"
                  >
                    <CheckSquare className="w-3 h-3" /> I have read this
                  </button>
                )
              )}
            </div>

            {isManager && (
              <span className="text-xs text-gray-400">{ann.read_count} read</span>
            )}
          </div>
        </div>
      ))}

      {/* Read receipts modal */}
      {receiptsFor && (
        <div
          className="fixed inset-0 z-50 bg-black/40 flex items-center justify-center p-4"
          onClick={() => setReceiptsFor(null)}
        >
          <div
            className="bg-white rounded-xl shadow-xl w-full max-w-md p-6 space-y-4"
            onClick={e => e.stopPropagation()}
          >
            <h2 className="font-semibold text-gray-900">Read receipts — {receiptsFor.title}</h2>
            {receipts.length === 0 ? (
              <p className="text-gray-400 text-sm">No reads recorded yet.</p>
            ) : (
              <div className="divide-y max-h-72 overflow-y-auto text-sm">
                {receipts.map((r, i) => (
                  <div key={i} className="py-2 flex justify-between items-center">
                    <span className="text-gray-700 font-mono text-xs">{r.staff_id.slice(0, 8)}…</span>
                    <div className="text-xs text-gray-400 text-right space-y-0.5">
                      <div>{r.read_at ? `Read ${new Date(r.read_at).toLocaleString()}` : "Not read"}</div>
                      {receiptsFor.acknowledgement_required && (
                        <div>{r.acknowledged_at ? `Acked ${new Date(r.acknowledged_at).toLocaleString()}` : "Not acknowledged"}</div>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            )}
            <button onClick={() => setReceiptsFor(null)} className="btn-secondary text-sm w-full">Close</button>
          </div>
        </div>
      )}
    </div>
  );
}
