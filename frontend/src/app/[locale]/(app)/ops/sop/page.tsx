"use client";

import { useEffect, useState } from "react";
import { useRouter, useParams } from "next/navigation";
import { createClient } from "@/lib/supabase/client";
import { PlusCircle, RefreshCw, BookOpen, ChevronDown, ChevronRight, Trash2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { toast } from "sonner";
import styles from "./page.module.scss";

interface SopVersion {
  version: number;
  change_notes: string | null;
  created_at: string;
}

interface Sop {
  id: string;
  title: string;
  slug: string;
  category: string | null;
  status: string;
  version: number;
  content_markdown: string;
  updated_at: string;
  versions?: SopVersion[];
}

const STATUS_CONFIG: Record<string, { label: string; color: string }> = {
  draft:     { label: "Draft",     color: "bg-gray-100 text-gray-600"   },
  published: { label: "Published", color: "bg-green-100 text-green-700" },
  archived:  { label: "Archived",  color: "bg-gray-100 text-gray-500"   },
};

const STATUS_MODULE: Record<string, keyof typeof styles> = {
  draft:     "statusDraft",
  published: "statusPublished",
  archived:  "statusArchived",
};

const ALL_STATUSES = ["all", "draft", "published", "archived"] as const;
type StatusFilter = typeof ALL_STATUSES[number];

export default function SopPage() {
  const router = useRouter();
  const params = useParams<{ locale: string }>();
  const locale = params?.locale ?? "en";
  const supabase = createClient();

  const [sops, setSops] = useState<Sop[]>([]);
  const [categories, setCategories] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);
  const [statusFilter, setStatusFilter] = useState<StatusFilter>("all");
  const [categoryFilter, setCategoryFilter] = useState<string>("all");
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [editContent, setEditContent] = useState<Record<string, string>>({});
  const [actionLoading, setActionLoading] = useState<string | null>(null);

  const [showNew, setShowNew] = useState(false);
  const [newForm, setNewForm] = useState({ title: "", slug: "", category: "", content_markdown: "" });

  async function getToken() {
    const { data: { session } } = await supabase.auth.getSession();
    return session?.access_token ?? null;
  }
  function apiUrl(p: string) { return `${process.env.NEXT_PUBLIC_API_URL}${p}`; }

  async function load() {
    setLoading(true);
    try {
      const token = await getToken();
      if (!token) { router.push(`/${locale}/auth/login`); return; }

      const [sopsRes, catRes] = await Promise.all([
        fetch(apiUrl("/api/sop"), { headers: { Authorization: `Bearer ${token}` } }),
        fetch(apiUrl("/api/sop/categories"), { headers: { Authorization: `Bearer ${token}` } }),
      ]);
      if (sopsRes.status === 401) { router.push(`/${locale}/auth/login`); return; }
      if (sopsRes.ok) setSops(await sopsRes.json());
      if (catRes.ok) setCategories(await catRes.json());
    } catch {
      toast.error("Failed to load SOPs");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { load(); }, []);  // eslint-disable-line react-hooks/exhaustive-deps

  async function createSop() {
    if (!newForm.title.trim()) { toast.error("Title is required"); return; }
    setActionLoading("create");
    try {
      const token = await getToken();
      if (!token) return;
      const res = await fetch(apiUrl("/api/sop"), {
        method: "POST",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
        body: JSON.stringify({
          title: newForm.title,
          slug: newForm.slug || newForm.title.toLowerCase().replace(/\s+/g, "-"),
          category: newForm.category || null,
          content_markdown: newForm.content_markdown,
        }),
      });
      if (!res.ok) {
        const b = await res.json().catch(() => ({}));
        toast.error(b.detail ?? "Failed to create SOP");
        return;
      }
      toast.success("SOP created");
      setShowNew(false);
      setNewForm({ title: "", slug: "", category: "", content_markdown: "" });
      await load();
    } catch {
      toast.error("Something went wrong");
    } finally {
      setActionLoading(null);
    }
  }

  async function publishSop(id: string) {
    setActionLoading(id + "_publish");
    try {
      const token = await getToken();
      if (!token) return;
      const res = await fetch(apiUrl(`/api/sop/${id}/publish`), {
        method: "POST",
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) {
        const b = await res.json().catch(() => ({}));
        toast.error(b.detail ?? "Failed to publish");
        return;
      }
      toast.success("SOP published");
      await load();
    } catch {
      toast.error("Something went wrong");
    } finally {
      setActionLoading(null);
    }
  }

  async function archiveSop(id: string) {
    setActionLoading(id + "_archive");
    try {
      const token = await getToken();
      if (!token) return;
      const res = await fetch(apiUrl(`/api/sop/${id}/archive`), {
        method: "POST",
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) {
        const b = await res.json().catch(() => ({}));
        toast.error(b.detail ?? "Failed to archive");
        return;
      }
      toast.success("SOP archived");
      await load();
    } catch {
      toast.error("Something went wrong");
    } finally {
      setActionLoading(null);
    }
  }

  async function deleteSop(id: string) {
    setActionLoading(id + "_delete");
    try {
      const token = await getToken();
      if (!token) return;
      const res = await fetch(apiUrl(`/api/sop/${id}`), {
        method: "DELETE",
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) {
        const b = await res.json().catch(() => ({}));
        toast.error(b.detail ?? "Failed to delete");
        return;
      }
      toast.success("SOP deleted");
      await load();
    } catch {
      toast.error("Something went wrong");
    } finally {
      setActionLoading(null);
    }
  }

  async function saveSop(id: string) {
    const content = editContent[id];
    if (content === undefined) return;
    setActionLoading(id + "_save");
    try {
      const token = await getToken();
      if (!token) return;
      const res = await fetch(apiUrl(`/api/sop/${id}`), {
        method: "PATCH",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
        body: JSON.stringify({ content_markdown: content }),
      });
      if (!res.ok) {
        const b = await res.json().catch(() => ({}));
        toast.error(b.detail ?? "Failed to save");
        return;
      }
      toast.success("SOP saved (new version created)");
      setEditContent((prev) => { const n = { ...prev }; delete n[id]; return n; });
      await load();
    } catch {
      toast.error("Something went wrong");
    } finally {
      setActionLoading(null);
    }
  }

  const filtered = sops.filter((s) => {
    if (statusFilter !== "all" && s.status !== statusFilter) return false;
    if (categoryFilter !== "all" && s.category !== categoryFilter) return false;
    return true;
  });

  return (
    <div className="mx-auto max-w-4xl space-y-6 p-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-gray-900">SOP Library</h1>
          <p className="text-sm text-muted-foreground mt-0.5">Company procedures and process documentation.</p>
        </div>
        <Button onClick={() => setShowNew(true)} className="bg-[#1a2332] hover:bg-[#2a3342] text-white gap-2">
          <PlusCircle className="h-4 w-4" /> New SOP
        </Button>
      </div>

      {/* Filters */}
      <div className="flex items-center gap-3 flex-wrap">
        <select
          value={categoryFilter}
          onChange={(e) => setCategoryFilter(e.target.value)}
          className="rounded-md border border-gray-300 px-3 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-[#1a2332]"
        >
          <option value="all">All Categories</option>
          {categories.map((c) => (
            <option key={c} value={c}>{c}</option>
          ))}
        </select>
        <div className="flex items-center gap-1 border-b">
          {ALL_STATUSES.map((s) => (
            <button
              key={s}
              type="button"
              onClick={() => setStatusFilter(s)}
              className={`px-3 py-1.5 text-sm font-medium border-b-2 transition-colors capitalize ${
                statusFilter === s
                  ? "border-[#1a2332] text-[#1a2332]"
                  : "border-transparent text-muted-foreground hover:text-gray-700"
              }`}
            >
              {s === "all" ? "All" : s.charAt(0).toUpperCase() + s.slice(1)}
            </button>
          ))}
        </div>
      </div>

      {/* New SOP form */}
      {showNew && (
        <div className="rounded-xl border border-[#1a2332]/20 bg-white p-5 shadow-sm space-y-3">
          <h3 className="text-sm font-semibold text-gray-900">Create SOP</h3>
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1">
              <label className="text-xs font-medium text-gray-700">Title *</label>
              <input
                value={newForm.title}
                onChange={(e) => {
                  const title = e.target.value;
                  setNewForm((f) => ({
                    ...f,
                    title,
                    slug: f.slug === "" || f.slug === f.title.toLowerCase().replace(/\s+/g, "-")
                      ? title.toLowerCase().replace(/\s+/g, "-")
                      : f.slug,
                  }));
                }}
                placeholder="Customer Onboarding Process"
                className="block w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-[#1a2332]"
              />
            </div>
            <div className="space-y-1">
              <label className="text-xs font-medium text-gray-700">Slug (auto-filled)</label>
              <input
                value={newForm.slug}
                onChange={(e) => setNewForm((f) => ({ ...f, slug: e.target.value }))}
                placeholder="customer-onboarding-process"
                className="block w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-[#1a2332]"
              />
            </div>
          </div>
          <div className="space-y-1">
            <label className="text-xs font-medium text-gray-700">Category</label>
            <input
              value={newForm.category}
              onChange={(e) => setNewForm((f) => ({ ...f, category: e.target.value }))}
              placeholder="Operations, HR, Sales…"
              className="block w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-[#1a2332]"
            />
          </div>
          <div className="space-y-1">
            <label className="text-xs font-medium text-gray-700">Content</label>
            <textarea
              value={newForm.content_markdown}
              onChange={(e) => setNewForm((f) => ({ ...f, content_markdown: e.target.value }))}
              rows={12}
              placeholder="Write the procedure steps here…"
              className="block w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-[#1a2332]"
            />
          </div>
          <div className="flex gap-2">
            <Button variant="outline" onClick={() => setShowNew(false)}>Cancel</Button>
            <Button
              disabled={actionLoading === "create"}
              onClick={createSop}
              className="bg-[#1a2332] hover:bg-[#2a3342] text-white"
            >
              {actionLoading === "create" ? "Creating…" : "Create SOP"}
            </Button>
          </div>
        </div>
      )}

      {/* List */}
      {loading && sops.length === 0 ? (
        <div className="text-center py-12">
          <RefreshCw className="h-6 w-6 animate-spin mx-auto text-muted-foreground" />
        </div>
      ) : filtered.length === 0 ? (
        <div className="rounded-xl border bg-white shadow-sm py-12 text-center">
          <BookOpen className="h-10 w-10 text-muted-foreground mx-auto mb-3" />
          <p className="text-gray-600 font-medium">No SOPs found</p>
        </div>
      ) : (
        <div className="rounded-xl border bg-white shadow-sm divide-y divide-gray-100">
          {filtered.map((sop) => {
            const cfg = STATUS_CONFIG[sop.status] ?? STATUS_CONFIG.draft;
            const isExpanded = expandedId === sop.id;
            const currentEdit = editContent[sop.id] ?? sop.content_markdown;

            return (
              <div key={sop.id}>
                <div className="flex items-center gap-4 px-5 py-4">
                  <button
                    type="button"
                    onClick={() => setExpandedId(isExpanded ? null : sop.id)}
                    className="flex-1 min-w-0 text-left"
                  >
                    <div className="flex items-center gap-2">
                      {isExpanded
                        ? <ChevronDown className="h-4 w-4 text-muted-foreground flex-shrink-0" />
                        : <ChevronRight className="h-4 w-4 text-muted-foreground flex-shrink-0" />}
                      <span className="text-sm font-medium text-gray-900">{sop.title}</span>
                      {sop.category && (
                        <span className="rounded-full bg-purple-100 text-purple-700 px-2 py-0.5 text-xs">
                          {sop.category}
                        </span>
                      )}
                      <span className="rounded-full bg-blue-50 text-blue-600 px-2 py-0.5 text-xs font-mono">
                        V{sop.version}
                      </span>
                    </div>
                    <p className="text-xs text-muted-foreground mt-0.5 pl-6">
                      Updated {new Date(sop.updated_at).toLocaleDateString()}
                    </p>
                  </button>

                  <span className={styles[STATUS_MODULE[sop.status] ?? "statusDraft"]}>
                    {cfg.label}
                  </span>

                  <div className="flex items-center gap-2 flex-shrink-0">
                    {sop.status === "draft" && (
                      <>
                        <Button
                          size="sm"
                          disabled={actionLoading === sop.id + "_publish"}
                          onClick={() => publishSop(sop.id)}
                          className="bg-green-600 hover:bg-green-700 text-white"
                        >
                          {actionLoading === sop.id + "_publish"
                            ? <RefreshCw className="h-3 w-3 animate-spin" />
                            : "Publish"}
                        </Button>
                        <Button
                          variant="ghost"
                          size="sm"
                          disabled={actionLoading === sop.id + "_delete"}
                          onClick={() => deleteSop(sop.id)}
                          className="text-red-600 hover:text-red-700 hover:bg-red-50"
                        >
                          <Trash2 className="h-4 w-4" />
                        </Button>
                      </>
                    )}
                    {sop.status === "published" && (
                      <Button
                        variant="outline"
                        size="sm"
                        disabled={actionLoading === sop.id + "_archive"}
                        onClick={() => archiveSop(sop.id)}
                      >
                        {actionLoading === sop.id + "_archive"
                          ? <RefreshCw className="h-3 w-3 animate-spin" />
                          : "Archive"}
                      </Button>
                    )}
                  </div>
                </div>

                {isExpanded && (
                  <div className="border-t border-gray-100 bg-gray-50 px-5 py-4 space-y-4">
                    <div className="space-y-2">
                      <p className="text-xs font-semibold text-gray-700 uppercase tracking-wide">Content</p>
                      <pre className="whitespace-pre-wrap text-sm text-gray-700 bg-white rounded-md border border-gray-200 p-3">
                        {sop.content_markdown}
                      </pre>
                    </div>

                    {sop.versions && sop.versions.length > 0 && (
                      <div className="space-y-2">
                        <p className="text-xs font-semibold text-gray-700 uppercase tracking-wide">Version History</p>
                        <div className="space-y-1">
                          {sop.versions.map((v) => (
                            <div key={v.version} className="flex items-start gap-3 text-sm">
                              <span className="font-mono text-xs bg-blue-50 text-blue-600 rounded px-1.5 py-0.5 flex-shrink-0">
                                V{v.version}
                              </span>
                              <span className="text-gray-600 flex-1">{v.change_notes ?? "—"}</span>
                              <span className="text-xs text-muted-foreground flex-shrink-0">
                                {new Date(v.created_at).toLocaleDateString()}
                              </span>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}

                    <div className="space-y-2">
                      <p className="text-xs font-semibold text-gray-700 uppercase tracking-wide">Edit Content</p>
                      <textarea
                        value={currentEdit}
                        onChange={(e) => setEditContent((prev) => ({ ...prev, [sop.id]: e.target.value }))}
                        rows={10}
                        className="block w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-[#1a2332]"
                      />
                      <Button
                        disabled={
                          actionLoading === sop.id + "_save" ||
                          currentEdit === sop.content_markdown
                        }
                        onClick={() => saveSop(sop.id)}
                        className="bg-[#1a2332] hover:bg-[#2a3342] text-white"
                      >
                        {actionLoading === sop.id + "_save"
                          ? <><RefreshCw className="h-3 w-3 animate-spin mr-2" />Saving…</>
                          : "Save (creates new version)"}
                      </Button>
                    </div>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
