"use client";

import { useEffect, useState } from "react";
import { useRouter, useParams } from "next/navigation";
import { createClient } from "@/lib/supabase/client";
import { PlusCircle, RefreshCw, ChevronDown, ChevronUp } from "lucide-react";
import { Button } from "@/components/ui/button";
import { toast } from "sonner";
import styles from "./page.module.scss";

interface BoardPack {
  id: string;
  title: string;
  meeting_date: string;
  financial_period: string | null;
  status: "draft" | "published";
  executive_summary: string | null;
  agenda: string | null;
  notes: string | null;
  kpi_snapshot: Record<string, unknown> | null;
}

const STATUS_COLOR: Record<string, string> = {
  draft: "bg-gray-100 text-gray-600",
  published: "bg-green-100 text-green-700",
};

const STATUS_MODULE: Record<string, keyof typeof styles> = {
  draft:     "statusDraft",
  published: "statusPublished",
};

export default function BoardPacksPage() {
  const router = useRouter();
  const params = useParams<{ locale: string }>();
  const locale = params?.locale ?? "en";
  const supabase = createClient();

  const [packs, setPacks] = useState<BoardPack[]>([]);
  const [loading, setLoading] = useState(true);
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [actionLoading, setActionLoading] = useState<string | null>(null);
  const [showNew, setShowNew] = useState(false);
  const [newForm, setNewForm] = useState({
    title: "", meeting_date: "", financial_period: "",
    agenda: "", executive_summary: "", notes: "",
  });
  const [editForm, setEditForm] = useState<Record<string, { agenda: string; executive_summary: string }>>({});

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
      const res = await fetch(apiUrl("/api/board-packs"), { headers: { Authorization: `Bearer ${token}` } });
      if (res.status === 401) { router.push(`/${locale}/auth/login`); return; }
      if (res.ok) {
        const data: BoardPack[] = await res.json();
        setPacks(data);
        const ef: Record<string, { agenda: string; executive_summary: string }> = {};
        data.forEach((p) => { ef[p.id] = { agenda: p.agenda ?? "", executive_summary: p.executive_summary ?? "" }; });
        setEditForm(ef);
      }
    } catch {
      toast.error("Failed to load board packs");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { load(); }, []); // eslint-disable-line react-hooks/exhaustive-deps

  async function createPack() {
    if (!newForm.title.trim() || !newForm.meeting_date) { toast.error("Title and meeting date are required"); return; }
    setActionLoading("create");
    try {
      const token = await getToken();
      if (!token) return;
      const res = await fetch(apiUrl("/api/board-packs"), {
        method: "POST",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
        body: JSON.stringify({
          title: newForm.title,
          meeting_date: newForm.meeting_date,
          financial_period: newForm.financial_period || null,
          agenda: newForm.agenda || null,
          executive_summary: newForm.executive_summary || null,
          notes: newForm.notes || null,
        }),
      });
      if (!res.ok) { const b = await res.json().catch(() => ({})); toast.error(b.detail ?? "Failed to create"); return; }
      toast.success("Board pack created");
      setShowNew(false);
      setNewForm({ title: "", meeting_date: "", financial_period: "", agenda: "", executive_summary: "", notes: "" });
      await load();
    } catch { toast.error("Something went wrong"); }
    finally { setActionLoading(null); }
  }

  async function savePack(id: string) {
    const ef = editForm[id];
    if (!ef) return;
    setActionLoading(id + "_save");
    try {
      const token = await getToken();
      if (!token) return;
      const res = await fetch(apiUrl(`/api/board-packs/${id}`), {
        method: "PATCH",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
        body: JSON.stringify({ agenda: ef.agenda || null, executive_summary: ef.executive_summary || null }),
      });
      if (!res.ok) { const b = await res.json().catch(() => ({})); toast.error(b.detail ?? "Failed to save"); return; }
      toast.success("Saved");
      await load();
    } catch { toast.error("Something went wrong"); }
    finally { setActionLoading(null); }
  }

  async function autoPopulate(id: string) {
    setActionLoading(id + "_kpi");
    try {
      const token = await getToken();
      if (!token) return;
      const res = await fetch(apiUrl(`/api/board-packs/${id}/auto-populate`), {
        method: "POST",
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) { const b = await res.json().catch(() => ({})); toast.error(b.detail ?? "Failed to auto-populate"); return; }
      toast.success("KPIs populated");
      await load();
    } catch { toast.error("Something went wrong"); }
    finally { setActionLoading(null); }
  }

  async function publishPack(id: string) {
    setActionLoading(id + "_publish");
    try {
      const token = await getToken();
      if (!token) return;
      const res = await fetch(apiUrl(`/api/board-packs/${id}/publish`), {
        method: "POST",
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) { const b = await res.json().catch(() => ({})); toast.error(b.detail ?? "Failed to publish"); return; }
      toast.success("Board pack published");
      await load();
    } catch { toast.error("Something went wrong"); }
    finally { setActionLoading(null); }
  }

  return (
    <div className="mx-auto max-w-4xl space-y-6 p-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-gray-900">Board Packs</h1>
          <p className="text-sm text-muted-foreground mt-0.5">Board meeting packs with auto-populated financials.</p>
        </div>
        <Button onClick={() => setShowNew(true)} className="bg-[#1a2332] hover:bg-[#2a3342] text-white gap-2">
          <PlusCircle className="h-4 w-4" /> New Pack
        </Button>
      </div>

      {showNew && (
        <div className="rounded-xl border border-[#1a2332]/20 bg-white p-5 shadow-sm space-y-3">
          <h3 className="text-sm font-semibold text-gray-900">Create Board Pack</h3>
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1 col-span-2">
              <label className="text-xs font-medium text-gray-700">Title *</label>
              <input value={newForm.title} onChange={(e) => setNewForm((f) => ({ ...f, title: e.target.value }))}
                placeholder="Q1 2026 Board Meeting"
                className="block w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-[#1a2332]" />
            </div>
            <div className="space-y-1">
              <label className="text-xs font-medium text-gray-700">Meeting Date *</label>
              <input type="date" value={newForm.meeting_date} onChange={(e) => setNewForm((f) => ({ ...f, meeting_date: e.target.value }))}
                className="block w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-[#1a2332]" />
            </div>
            <div className="space-y-1">
              <label className="text-xs font-medium text-gray-700">Financial Period</label>
              <input value={newForm.financial_period} onChange={(e) => setNewForm((f) => ({ ...f, financial_period: e.target.value }))}
                placeholder="Q1 2026"
                className="block w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-[#1a2332]" />
            </div>
            {[
              { key: "executive_summary" as const, label: "Executive Summary" },
              { key: "agenda" as const, label: "Agenda" },
              { key: "notes" as const, label: "Notes" },
            ].map(({ key, label }) => (
              <div key={key} className="space-y-1 col-span-2">
                <label className="text-xs font-medium text-gray-700">{label}</label>
                <textarea rows={2} value={newForm[key]} onChange={(e) => setNewForm((f) => ({ ...f, [key]: e.target.value }))}
                  className="block w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-[#1a2332]" />
              </div>
            ))}
          </div>
          <div className="flex gap-2">
            <Button variant="outline" onClick={() => setShowNew(false)}>Cancel</Button>
            <Button disabled={actionLoading === "create"} onClick={createPack}
              className="bg-[#1a2332] hover:bg-[#2a3342] text-white">
              {actionLoading === "create" ? "Creating…" : "Create Pack"}
            </Button>
          </div>
        </div>
      )}

      {loading && packs.length === 0 ? (
        <div className="text-center py-12"><RefreshCw className="h-6 w-6 animate-spin mx-auto text-muted-foreground" /></div>
      ) : (
        <div className="rounded-xl border bg-white shadow-sm divide-y divide-gray-100">
          {packs.length === 0 ? (
            <div className="py-12 text-center text-sm text-gray-500">No board packs yet</div>
          ) : packs.map((p) => {
            const expanded = expandedId === p.id;
            const ef = editForm[p.id] ?? { agenda: "", executive_summary: "" };
            return (
              <div key={p.id}>
                <div className="flex items-center gap-4 px-5 py-4">
                  <div className="flex-1 min-w-0 cursor-pointer" onClick={() => setExpandedId(expanded ? null : p.id)}>
                    <p className="text-sm font-medium text-gray-900">{p.title}</p>
                    <p className="text-xs text-muted-foreground">
                      {new Date(p.meeting_date).toLocaleDateString()}
                      {p.financial_period && ` · ${p.financial_period}`}
                    </p>
                  </div>
                  <span className={styles[STATUS_MODULE[p.status] ?? "statusDraft"]}>
                    {p.status}
                  </span>
                  <div className="flex items-center gap-2">
                    <Button size="sm" variant="outline" disabled={actionLoading === p.id + "_kpi"}
                      onClick={() => autoPopulate(p.id)}>
                      {actionLoading === p.id + "_kpi" ? <RefreshCw className="h-3 w-3 animate-spin" /> : "Auto-Populate KPIs"}
                    </Button>
                    {p.status === "draft" && (
                      <Button size="sm" disabled={actionLoading === p.id + "_publish"}
                        onClick={() => publishPack(p.id)}
                        className="bg-green-600 hover:bg-green-700 text-white">
                        {actionLoading === p.id + "_publish" ? "Publishing…" : "Publish"}
                      </Button>
                    )}
                    <button type="button" onClick={() => setExpandedId(expanded ? null : p.id)}>
                      {expanded ? <ChevronUp className="h-4 w-4 text-muted-foreground" /> : <ChevronDown className="h-4 w-4 text-muted-foreground" />}
                    </button>
                  </div>
                </div>
                {expanded && (
                  <div className="px-5 pb-5 space-y-3 bg-gray-50 border-t">
                    {[
                      { key: "executive_summary" as const, label: "Executive Summary" },
                      { key: "agenda" as const, label: "Agenda" },
                    ].map(({ key, label }) => (
                      <div key={key} className="space-y-1">
                        <label className="text-xs font-medium text-gray-700">{label}</label>
                        <textarea rows={3} value={ef[key]}
                          onChange={(e) => setEditForm((f) => ({ ...f, [p.id]: { ...ef, [key]: e.target.value } }))}
                          className="block w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-[#1a2332]" />
                      </div>
                    ))}
                    {p.kpi_snapshot && (
                      <div className="rounded-md bg-white border p-3">
                        <p className="text-xs font-semibold text-gray-700 mb-2">KPI Snapshot</p>
                        <pre className="text-xs text-gray-600 overflow-x-auto">{JSON.stringify(p.kpi_snapshot, null, 2)}</pre>
                      </div>
                    )}
                    <div className="flex justify-end">
                      <Button size="sm" disabled={actionLoading === p.id + "_save"} onClick={() => savePack(p.id)}
                        className="bg-[#1a2332] hover:bg-[#2a3342] text-white">
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
