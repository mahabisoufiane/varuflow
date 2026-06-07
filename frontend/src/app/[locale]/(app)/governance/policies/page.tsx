"use client";

import { useState, useEffect } from "react";
import { toast } from "sonner";
import { BookOpen, Plus, Edit3, Eye, EyeOff, X, Check, ChevronRight } from "lucide-react";
import { api } from "@/lib/api-client";

interface PolicyDoc {
  id: string; title: string; category: string; is_published: boolean;
  version: number; created_at: string | null; updated_at: string | null;
  content?: string;
}
interface Category { value: string; label: string }

const CATEGORY_COLORS: Record<string, string> = {
  hr: "bg-blue-50 text-blue-700 border-blue-200",
  finance: "bg-green-50 text-green-700 border-green-200",
  it: "bg-indigo-50 text-indigo-700 border-indigo-200",
  legal: "bg-orange-50 text-orange-700 border-orange-200",
  operations: "bg-teal-50 text-teal-700 border-teal-200",
  security: "bg-red-50 text-red-700 border-red-200",
  other: "bg-gray-100 text-gray-600 border-gray-200",
};

// Minimal markdown renderer: bold, headers, bullets
function MarkdownView({ content }: { content: string }) {
  const lines = content.split("\n");
  return (
    <div className="prose prose-sm max-w-none text-gray-700 space-y-1">
      {lines.map((line, i) => {
        if (line.startsWith("## ")) return <h2 key={i} className="text-base font-semibold text-gray-900 mt-3">{line.slice(3)}</h2>;
        if (line.startsWith("# "))  return <h1 key={i} className="text-lg font-bold text-gray-900 mt-4">{line.slice(2)}</h1>;
        if (line.startsWith("- "))  return <p key={i} className="flex gap-2"><span className="text-gray-400 flex-shrink-0">•</span>{line.slice(2)}</p>;
        if (line === "")            return <div key={i} className="h-1" />;
        return <p key={i}>{line}</p>;
      })}
    </div>
  );
}

export default function PoliciesPage() {
  const [docs, setDocs] = useState<PolicyDoc[]>([]);
  const [categories, setCategories] = useState<Category[]>([]);
  const [loading, setLoading] = useState(true);
  const [activeDoc, setActiveDoc] = useState<PolicyDoc | null>(null);
  const [editing, setEditing] = useState(false);
  const [filterCat, setFilterCat] = useState("");
  const [showForm, setShowForm] = useState(false);
  const [newDoc, setNewDoc] = useState({ title: "", category: "hr", content: "", is_published: false });
  const [editDoc, setEditDoc] = useState<PolicyDoc | null>(null);

  useEffect(() => {
    Promise.all([
      api.get<PolicyDoc[]>("/api/governance/policies").then(setDocs).catch(() => {}),
      api.get<Category[]>("/api/governance/policies/categories").then(setCategories).catch(() => {}),
    ]).finally(() => setLoading(false));
  }, []);

  async function openDoc(doc: PolicyDoc) {
    try {
      const full = await api.get<PolicyDoc>(`/api/governance/policies/${doc.id}`);
      setActiveDoc(full);
      setEditing(false);
    } catch {
      toast.error("Failed to load");
    }
  }

  async function createDoc() {
    if (!newDoc.title) { toast.error("Title is required"); return; }
    try {
      const created = await api.post<PolicyDoc>("/api/governance/policies", newDoc);
      setDocs(prev => [...prev, created]);
      setShowForm(false);
      toast.success("Policy created");
      openDoc(created);
    } catch {
      toast.error("Failed to create");
    }
  }

  async function saveEdit() {
    if (!editDoc) return;
    try {
      const updated = await api.patch<PolicyDoc>(`/api/governance/policies/${editDoc.id}`, {
        title: editDoc.title, category: editDoc.category,
        content: editDoc.content || "", is_published: editDoc.is_published,
      });
      setDocs(prev => prev.map(d => d.id === updated.id ? updated : d));
      setActiveDoc(updated);
      setEditing(false);
      setEditDoc(null);
      toast.success("Policy saved");
    } catch {
      toast.error("Failed to save");
    }
  }

  async function togglePublish(doc: PolicyDoc) {
    try {
      const updated = await api.patch<PolicyDoc>(`/api/governance/policies/${doc.id}`, { is_published: !doc.is_published });
      setDocs(prev => prev.map(d => d.id === updated.id ? updated : d));
      if (activeDoc?.id === updated.id) setActiveDoc(updated);
      toast.success(updated.is_published ? "Published" : "Unpublished");
    } catch {
      toast.error("Failed");
    }
  }

  async function deleteDoc(id: string) {
    try {
      await api.delete(`/api/governance/policies/${id}`);
    } catch {}
    setDocs(prev => prev.filter(d => d.id !== id));
    if (activeDoc?.id === id) setActiveDoc(null);
    toast.success("Deleted");
  }

  const filtered = filterCat ? docs.filter(d => d.category === filterCat) : docs;
  const catMap = Object.fromEntries(categories.map(c => [c.value, c.label]));

  if (loading) return <div className="animate-pulse space-y-4">{[1,2,3].map(i => <div key={i} className="h-16 rounded-xl bg-gray-100" />)}</div>;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <h1 className="text-2xl font-semibold text-gray-900">Company Policies</h1>
          <p className="mt-1 text-sm text-gray-500">Publish HR, finance and legal policies so every staff member can access them in-app.</p>
        </div>
        <button onClick={() => setShowForm(true)} className="btn-primary flex items-center gap-2">
          <Plus className="h-4 w-4" /> New Policy
        </button>
      </div>

      {/* Category filter */}
      <div className="flex gap-2 flex-wrap">
        <button onClick={() => setFilterCat("")} className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-all ${!filterCat ? "bg-blue-500 text-white" : "bg-gray-100 text-gray-700 hover:bg-gray-200"}`}>All</button>
        {categories.map(c => (
          <button key={c.value} onClick={() => setFilterCat(c.value)}
            className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-all ${filterCat === c.value ? "bg-blue-500 text-white" : "bg-gray-100 text-gray-700 hover:bg-gray-200"}`}>
            {c.label}
          </button>
        ))}
      </div>

      {/* New doc form */}
      {showForm && (
        <div className="rounded-xl border border-blue-200 bg-blue-50 p-5 space-y-3">
          <p className="text-sm font-semibold text-blue-800">New Policy Document</p>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <input className="input sm:col-span-2" placeholder="Policy title *" value={newDoc.title} onChange={e => setNewDoc(p => ({ ...p, title: e.target.value }))} />
            <select className="input" value={newDoc.category} onChange={e => setNewDoc(p => ({ ...p, category: e.target.value }))}>
              {categories.map(c => <option key={c.value} value={c.value}>{c.label}</option>)}
            </select>
            <label className="flex items-center gap-2 text-sm text-gray-700 cursor-pointer p-2">
              <input type="checkbox" checked={newDoc.is_published} onChange={e => setNewDoc(p => ({ ...p, is_published: e.target.checked }))} className="rounded" />
              Publish immediately (visible to all staff)
            </label>
            <textarea className="input sm:col-span-2 text-sm" rows={4} placeholder="Policy content (supports basic markdown: # Heading, - bullet, **bold**)" value={newDoc.content} onChange={e => setNewDoc(p => ({ ...p, content: e.target.value }))} />
          </div>
          <div className="flex gap-2">
            <button onClick={createDoc} className="btn-primary text-sm">Create</button>
            <button onClick={() => setShowForm(false)} className="btn-secondary text-sm">Cancel</button>
          </div>
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* List */}
        <div className="space-y-2 lg:col-span-1">
          {filtered.length === 0 && (
            <div className="text-center py-10 text-gray-400">
              <BookOpen className="h-8 w-8 mx-auto mb-2 opacity-40" />
              <p>No policies yet.</p>
            </div>
          )}
          {filtered.map(doc => (
            <button key={doc.id} onClick={() => openDoc(doc)}
              className={`w-full rounded-xl border p-4 flex items-center gap-3 text-left transition-all ${
                activeDoc?.id === doc.id ? "border-blue-400 bg-blue-50" : "border-gray-200 bg-white hover:border-gray-300"
              }`}>
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 flex-wrap">
                  <span className="font-medium text-gray-900 text-sm">{doc.title}</span>
                  {!doc.is_published && <EyeOff className="h-3 w-3 text-gray-400" />}
                </div>
                <div className="flex items-center gap-2 mt-0.5">
                  <span className={`text-xs px-1.5 py-0.5 rounded border ${CATEGORY_COLORS[doc.category] || CATEGORY_COLORS.other}`}>
                    {catMap[doc.category] || doc.category}
                  </span>
                  <span className="text-xs text-gray-400">v{doc.version}</span>
                </div>
              </div>
              <ChevronRight className="h-4 w-4 text-gray-400 flex-shrink-0" />
            </button>
          ))}
        </div>

        {/* Detail / editor */}
        {activeDoc && (
          <div className="lg:col-span-2 rounded-xl border border-gray-200 bg-white overflow-hidden">
            <div className="border-b border-gray-100 p-4 flex items-center justify-between gap-3">
              {editing && editDoc ? (
                <input className="input flex-1 font-semibold" value={editDoc.title} onChange={e => setEditDoc(p => p ? { ...p, title: e.target.value } : p)} />
              ) : (
                <div>
                  <h2 className="font-semibold text-gray-900">{activeDoc.title}</h2>
                  <p className="text-xs text-gray-400">v{activeDoc.version} · {activeDoc.updated_at ? new Date(activeDoc.updated_at).toLocaleDateString("sv-SE") : "—"}</p>
                </div>
              )}
              <div className="flex items-center gap-2 flex-shrink-0">
                <button onClick={() => togglePublish(activeDoc)}
                  className={`flex items-center gap-1 text-xs px-2 py-1.5 rounded-lg ${activeDoc.is_published ? "bg-green-100 text-green-700" : "bg-gray-100 text-gray-600"} hover:opacity-80`}>
                  {activeDoc.is_published ? <><Eye className="h-3 w-3" /> Published</> : <><EyeOff className="h-3 w-3" /> Draft</>}
                </button>
                {!editing ? (
                  <button onClick={() => { setEditing(true); setEditDoc({ ...activeDoc }); }}
                    className="p-1.5 rounded-lg hover:bg-gray-100 text-gray-500">
                    <Edit3 className="h-4 w-4" />
                  </button>
                ) : (
                  <>
                    <button onClick={saveEdit} className="p-1.5 rounded-lg bg-green-100 text-green-700 hover:bg-green-200"><Check className="h-4 w-4" /></button>
                    <button onClick={() => { setEditing(false); setEditDoc(null); }} className="p-1.5 rounded-lg hover:bg-gray-100 text-gray-500"><X className="h-4 w-4" /></button>
                  </>
                )}
                <button onClick={() => deleteDoc(activeDoc.id)} className="p-1.5 rounded-lg hover:bg-red-50 text-gray-400 hover:text-red-500">
                  <X className="h-4 w-4" />
                </button>
              </div>
            </div>

            <div className="p-5">
              {editing && editDoc ? (
                <textarea
                  className="input w-full text-sm font-mono"
                  rows={20}
                  value={editDoc.content || ""}
                  onChange={e => setEditDoc(p => p ? { ...p, content: e.target.value } : p)}
                  placeholder="Write policy content in markdown…"
                />
              ) : (
                <MarkdownView content={activeDoc.content || "*No content yet. Click edit to add content.*"} />
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
