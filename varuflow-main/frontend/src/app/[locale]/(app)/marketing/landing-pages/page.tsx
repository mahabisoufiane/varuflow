"use client";

import { useEffect, useState } from "react";
import { useRouter, useParams } from "next/navigation";
import { createClient } from "@/lib/supabase/client";
import { PlusCircle, RefreshCw, ChevronDown, ChevronUp } from "lucide-react";
import { Button } from "@/components/ui/button";
import { toast } from "sonner";
import styles from "./page.module.scss";

interface LandingPage {
  id: string;
  title: string;
  slug: string;
  status: "draft" | "published";
  view_count: number;
  published_at: string | null;
  headline: string | null;
  subheadline: string | null;
  cta_text: string | null;
  cta_url: string | null;
  body_html: string | null;
}

const STATUS_COLOR: Record<string, string> = {
  draft: "bg-gray-100 text-gray-600",
  published: "bg-green-100 text-green-700",
};

const STATUS_MODULE: Record<string, keyof typeof styles> = {
  draft:     "statusDraft",
  published: "statusPublished",
};

function slugify(s: string) {
  return s.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "");
}

export default function LandingPagesPage() {
  const router = useRouter();
  const params = useParams<{ locale: string }>();
  const locale = params?.locale ?? "en";
  const supabase = createClient();

  const [pages, setPages] = useState<LandingPage[]>([]);
  const [loading, setLoading] = useState(true);
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [actionLoading, setActionLoading] = useState<string | null>(null);

  const [showNew, setShowNew] = useState(false);
  const [newForm, setNewForm] = useState({ title: "", slug: "", headline: "", subheadline: "", cta_text: "", cta_url: "", body_html: "" });

  const [editForm, setEditForm] = useState<Record<string, { headline: string; subheadline: string; cta_text: string; cta_url: string; body_html: string }>>({});

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
      const res = await fetch(apiUrl("/api/landing-pages"), { headers: { Authorization: `Bearer ${token}` } });
      if (res.status === 401) { router.push(`/${locale}/auth/login`); return; }
      if (res.ok) {
        const data: LandingPage[] = await res.json();
        setPages(data);
        const ef: typeof editForm = {};
        data.forEach((p) => {
          ef[p.id] = { headline: p.headline ?? "", subheadline: p.subheadline ?? "", cta_text: p.cta_text ?? "", cta_url: p.cta_url ?? "", body_html: p.body_html ?? "" };
        });
        setEditForm(ef);
      }
    } catch {
      toast.error("Failed to load landing pages");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { load(); }, []); // eslint-disable-line react-hooks/exhaustive-deps

  async function createPage() {
    if (!newForm.title.trim()) { toast.error("Title is required"); return; }
    setActionLoading("create");
    try {
      const token = await getToken();
      if (!token) return;
      const res = await fetch(apiUrl("/api/landing-pages"), {
        method: "POST",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
        body: JSON.stringify({
          title: newForm.title,
          slug: newForm.slug || slugify(newForm.title),
          headline: newForm.headline || null,
          subheadline: newForm.subheadline || null,
          cta_text: newForm.cta_text || null,
          cta_url: newForm.cta_url || null,
          body_html: newForm.body_html || null,
        }),
      });
      if (!res.ok) { const b = await res.json().catch(() => ({})); toast.error(b.detail ?? "Failed to create"); return; }
      toast.success("Landing page created");
      setShowNew(false);
      setNewForm({ title: "", slug: "", headline: "", subheadline: "", cta_text: "", cta_url: "", body_html: "" });
      await load();
    } catch { toast.error("Something went wrong"); }
    finally { setActionLoading(null); }
  }

  async function savePage(id: string) {
    const ef = editForm[id];
    if (!ef) return;
    setActionLoading(id + "_save");
    try {
      const token = await getToken();
      if (!token) return;
      const res = await fetch(apiUrl(`/api/landing-pages/${id}`), {
        method: "PATCH",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
        body: JSON.stringify({
          headline: ef.headline || null,
          subheadline: ef.subheadline || null,
          cta_text: ef.cta_text || null,
          cta_url: ef.cta_url || null,
          body_html: ef.body_html || null,
        }),
      });
      if (!res.ok) { const b = await res.json().catch(() => ({})); toast.error(b.detail ?? "Failed to save"); return; }
      toast.success("Saved");
      await load();
    } catch { toast.error("Something went wrong"); }
    finally { setActionLoading(null); }
  }

  async function publishPage(id: string) {
    setActionLoading(id + "_publish");
    try {
      const token = await getToken();
      if (!token) return;
      const res = await fetch(apiUrl(`/api/landing-pages/${id}/publish`), {
        method: "POST",
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) { const b = await res.json().catch(() => ({})); toast.error(b.detail ?? "Failed to publish"); return; }
      toast.success("Landing page published");
      await load();
    } catch { toast.error("Something went wrong"); }
    finally { setActionLoading(null); }
  }

  return (
    <div className="mx-auto max-w-4xl space-y-6 p-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-gray-900">Landing Pages</h1>
          <p className="text-sm text-muted-foreground mt-0.5">Campaign-specific landing pages with lead capture.</p>
        </div>
        <Button onClick={() => setShowNew(true)} className="bg-[var(--vf-brand-primary)] hover:bg-[var(--vf-brand-primary-hover)] text-white gap-2">
          <PlusCircle className="h-4 w-4" /> New Page
        </Button>
      </div>

      {showNew && (
        <div className="rounded-xl border border-[var(--vf-brand-primary)]/20 bg-white p-5 shadow-sm space-y-3">
          <h3 className="text-sm font-semibold text-gray-900">Create Landing Page</h3>
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1">
              <label className="text-xs font-medium text-gray-700">Title *</label>
              <input value={newForm.title}
                onChange={(e) => setNewForm((f) => ({ ...f, title: e.target.value, slug: slugify(e.target.value) }))}
                placeholder="Black Friday 2026"
                className="block w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-[var(--vf-brand-primary)]" />
            </div>
            <div className="space-y-1">
              <label className="text-xs font-medium text-gray-700">Slug</label>
              <input value={newForm.slug} onChange={(e) => setNewForm((f) => ({ ...f, slug: e.target.value }))}
                placeholder="black-friday-2026"
                className="block w-full rounded-md border border-gray-300 px-3 py-2 text-sm font-mono focus:outline-none focus:ring-1 focus:ring-[var(--vf-brand-primary)]" />
            </div>
            <div className="space-y-1">
              <label className="text-xs font-medium text-gray-700">Headline</label>
              <input value={newForm.headline} onChange={(e) => setNewForm((f) => ({ ...f, headline: e.target.value }))}
                className="block w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-[var(--vf-brand-primary)]" />
            </div>
            <div className="space-y-1">
              <label className="text-xs font-medium text-gray-700">Subheadline</label>
              <input value={newForm.subheadline} onChange={(e) => setNewForm((f) => ({ ...f, subheadline: e.target.value }))}
                className="block w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-[var(--vf-brand-primary)]" />
            </div>
            <div className="space-y-1">
              <label className="text-xs font-medium text-gray-700">CTA Text</label>
              <input value={newForm.cta_text} onChange={(e) => setNewForm((f) => ({ ...f, cta_text: e.target.value }))}
                placeholder="Get Started"
                className="block w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-[var(--vf-brand-primary)]" />
            </div>
            <div className="space-y-1">
              <label className="text-xs font-medium text-gray-700">CTA URL</label>
              <input value={newForm.cta_url} onChange={(e) => setNewForm((f) => ({ ...f, cta_url: e.target.value }))}
                placeholder="https://..."
                className="block w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-[var(--vf-brand-primary)]" />
            </div>
            <div className="space-y-1 col-span-2">
              <label className="text-xs font-medium text-gray-700">Body HTML</label>
              <textarea rows={4} value={newForm.body_html} onChange={(e) => setNewForm((f) => ({ ...f, body_html: e.target.value }))}
                className="block w-full rounded-md border border-gray-300 px-3 py-2 text-sm font-mono focus:outline-none focus:ring-1 focus:ring-[var(--vf-brand-primary)]" />
            </div>
          </div>
          <div className="flex gap-2">
            <Button variant="outline" onClick={() => setShowNew(false)}>Cancel</Button>
            <Button disabled={actionLoading === "create"} onClick={createPage}
              className="bg-[var(--vf-brand-primary)] hover:bg-[var(--vf-brand-primary-hover)] text-white">
              {actionLoading === "create" ? "Creating…" : "Create Page"}
            </Button>
          </div>
        </div>
      )}

      {loading && pages.length === 0 ? (
        <div className="text-center py-12"><RefreshCw className="h-6 w-6 animate-spin mx-auto text-muted-foreground" /></div>
      ) : (
        <div className="rounded-xl border bg-white shadow-sm divide-y divide-gray-100">
          {pages.length === 0 ? (
            <div className="py-12 text-center text-sm text-gray-500">No landing pages yet</div>
          ) : pages.map((p) => {
            const expanded = expandedId === p.id;
            const ef = editForm[p.id] ?? { headline: "", subheadline: "", cta_text: "", cta_url: "", body_html: "" };
            return (
              <div key={p.id}>
                <div className="flex items-center gap-4 px-5 py-4">
                  <div className="flex-1 min-w-0 cursor-pointer" onClick={() => setExpandedId(expanded ? null : p.id)}>
                    <p className="text-sm font-medium text-gray-900">{p.title}</p>
                    <p className="text-xs text-muted-foreground font-mono">/lp/{p.slug}</p>
                  </div>
                  <span className="text-xs text-muted-foreground">{p.view_count} views</span>
                  {p.published_at && (
                    <span className="text-xs text-muted-foreground">{new Date(p.published_at).toLocaleDateString()}</span>
                  )}
                  <span className={styles[STATUS_MODULE[p.status] ?? "statusDraft"]}>
                    {p.status}
                  </span>
                  <div className="flex items-center gap-2">
                    {p.status === "draft" && (
                      <Button size="sm" disabled={actionLoading === p.id + "_publish"}
                        onClick={() => publishPage(p.id)}
                        className="bg-green-600 hover:bg-green-700 text-white">
                        Publish
                      </Button>
                    )}
                    <button type="button" onClick={() => setExpandedId(expanded ? null : p.id)}>
                      {expanded ? <ChevronUp className="h-4 w-4 text-muted-foreground" /> : <ChevronDown className="h-4 w-4 text-muted-foreground" />}
                    </button>
                  </div>
                </div>
                {expanded && (
                  <div className="px-5 pb-5 space-y-3 bg-gray-50 border-t">
                    <div className="space-y-1">
                      <label className="text-xs font-medium text-gray-500">Slug (read-only)</label>
                      <p className="text-sm font-mono text-gray-600 bg-gray-100 rounded px-2 py-1">/lp/{p.slug}</p>
                    </div>
                    {[
                      { key: "headline" as const, label: "Headline" },
                      { key: "subheadline" as const, label: "Subheadline" },
                      { key: "cta_text" as const, label: "CTA Text" },
                      { key: "cta_url" as const, label: "CTA URL" },
                    ].map(({ key, label }) => (
                      <div key={key} className="space-y-1">
                        <label className="text-xs font-medium text-gray-700">{label}</label>
                        <input value={ef[key]}
                          onChange={(e) => setEditForm((f) => ({ ...f, [p.id]: { ...ef, [key]: e.target.value } }))}
                          className="block w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-[var(--vf-brand-primary)]" />
                      </div>
                    ))}
                    <div className="space-y-1">
                      <label className="text-xs font-medium text-gray-700">Body HTML</label>
                      <textarea rows={4} value={ef.body_html}
                        onChange={(e) => setEditForm((f) => ({ ...f, [p.id]: { ...ef, body_html: e.target.value } }))}
                        className="block w-full rounded-md border border-gray-300 px-3 py-2 text-sm font-mono focus:outline-none focus:ring-1 focus:ring-[var(--vf-brand-primary)]" />
                    </div>
                    <div className="flex justify-end">
                      <Button size="sm" disabled={actionLoading === p.id + "_save"} onClick={() => savePage(p.id)}
                        className="bg-[var(--vf-brand-primary)] hover:bg-[var(--vf-brand-primary-hover)] text-white">
                        {actionLoading === p.id + "_save" ? "Saving…" : "Save Changes"}
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
