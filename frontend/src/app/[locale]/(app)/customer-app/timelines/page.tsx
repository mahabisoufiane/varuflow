"use client";

import { useEffect, useState } from "react";
import { useRouter, useParams } from "next/navigation";
import { createClient } from "@/lib/supabase/client";
import { RefreshCw, Trash2, PlusCircle, CheckCircle2, Clock, SkipForward, Play } from "lucide-react";
import { Button } from "@/components/ui/button";
import { toast } from "sonner";

interface TimelineEvent {
  id: string;
  stage: string;
  label: string;
  description: string | null;
  status: string;
  sort_order: number;
  completed_at: string | null;
}

interface Timeline {
  id: string;
  title: string;
  appointment_id: string | null;
  created_at: string;
  events: TimelineEvent[];
}

const EVENT_STATUS_CONFIG: Record<string, { dot: string; label: string }> = {
  pending:     { dot: "bg-gray-300",          label: "Pending"      },
  in_progress: { dot: "bg-blue-500 animate-pulse", label: "In Progress" },
  completed:   { dot: "bg-green-500",          label: "Completed"    },
  skipped:     { dot: "bg-gray-200",           label: "Skipped"      },
};

export default function TimelinesPage() {
  const router = useRouter();
  const params = useParams<{ locale: string }>();
  const locale = params?.locale ?? "en";
  const supabase = createClient();

  const [timelines, setTimelines] = useState<Timeline[]>([]);
  const [selected, setSelected] = useState<Timeline | null>(null);
  const [loading, setLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState<string | null>(null);
  const [editingTitle, setEditingTitle] = useState(false);
  const [titleDraft, setTitleDraft] = useState("");

  const [createForm, setCreateForm] = useState({ title: "", appointment_id: "" });
  const [stageForm, setStageForm] = useState({ stage: "", label: "", description: "" });

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
      const res = await fetch(apiUrl("/api/timelines"), { headers: { Authorization: `Bearer ${token}` } });
      if (res.status === 401) { router.push(`/${locale}/auth/login`); return; }
      if (res.ok) {
        const data: Timeline[] = await res.json();
        setTimelines(data);
        if (selected) {
          const updated = data.find((t) => t.id === selected.id);
          setSelected(updated ?? null);
        }
      }
    } catch {
      toast.error("Failed to load timelines");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { load(); }, []); // eslint-disable-line react-hooks/exhaustive-deps

  async function createTimeline() {
    if (!createForm.title.trim()) { toast.error("Title is required"); return; }
    setActionLoading("create");
    try {
      const token = await getToken();
      if (!token) return;
      const res = await fetch(apiUrl("/api/timelines"), {
        method: "POST",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
        body: JSON.stringify({ title: createForm.title, appointment_id: createForm.appointment_id || null }),
      });
      if (!res.ok) {
        const b = await res.json().catch(() => ({}));
        toast.error(b.detail ?? "Failed to create timeline");
        return;
      }
      const created: Timeline = await res.json();
      toast.success("Timeline created");
      setCreateForm({ title: "", appointment_id: "" });
      await load();
      setSelected(created);
    } catch {
      toast.error("Something went wrong");
    } finally {
      setActionLoading(null);
    }
  }

  async function saveTitle() {
    if (!selected || !titleDraft.trim()) return;
    setActionLoading("title");
    try {
      const token = await getToken();
      if (!token) return;
      const res = await fetch(apiUrl(`/api/timelines/${selected.id}`), {
        method: "PATCH",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
        body: JSON.stringify({ title: titleDraft }),
      });
      if (!res.ok) {
        const b = await res.json().catch(() => ({}));
        toast.error(b.detail ?? "Failed to update title");
        return;
      }
      toast.success("Title updated");
      setEditingTitle(false);
      await load();
    } catch {
      toast.error("Something went wrong");
    } finally {
      setActionLoading(null);
    }
  }

  async function deleteTimeline() {
    if (!selected) return;
    setActionLoading("del_timeline");
    try {
      const token = await getToken();
      if (!token) return;
      const res = await fetch(apiUrl(`/api/timelines/${selected.id}`), {
        method: "DELETE",
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) {
        const b = await res.json().catch(() => ({}));
        toast.error(b.detail ?? "Failed to delete");
        return;
      }
      toast.success("Timeline deleted");
      setSelected(null);
      await load();
    } catch {
      toast.error("Something went wrong");
    } finally {
      setActionLoading(null);
    }
  }

  async function addStage() {
    if (!selected) return;
    if (!stageForm.stage.trim() || !stageForm.label.trim()) {
      toast.error("Stage and label are required");
      return;
    }
    setActionLoading("add_stage");
    try {
      const token = await getToken();
      if (!token) return;
      const res = await fetch(apiUrl(`/api/timelines/${selected.id}/events`), {
        method: "POST",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
        body: JSON.stringify({ stage: stageForm.stage, label: stageForm.label, description: stageForm.description || null }),
      });
      if (!res.ok) {
        const b = await res.json().catch(() => ({}));
        toast.error(b.detail ?? "Failed to add stage");
        return;
      }
      toast.success("Stage added");
      setStageForm({ stage: "", label: "", description: "" });
      await load();
    } catch {
      toast.error("Something went wrong");
    } finally {
      setActionLoading(null);
    }
  }

  async function updateEventStatus(eventId: string, status: string) {
    if (!selected) return;
    setActionLoading("evt_" + eventId);
    try {
      const token = await getToken();
      if (!token) return;
      const res = await fetch(apiUrl(`/api/timelines/${selected.id}/events/${eventId}`), {
        method: "PATCH",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
        body: JSON.stringify({ status }),
      });
      if (!res.ok) {
        const b = await res.json().catch(() => ({}));
        toast.error(b.detail ?? "Failed to update event");
        return;
      }
      await load();
    } catch {
      toast.error("Something went wrong");
    } finally {
      setActionLoading(null);
    }
  }

  async function deleteEvent(eventId: string) {
    if (!selected) return;
    setActionLoading("del_evt_" + eventId);
    try {
      const token = await getToken();
      if (!token) return;
      const res = await fetch(apiUrl(`/api/timelines/${selected.id}/events/${eventId}`), {
        method: "DELETE",
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) {
        const b = await res.json().catch(() => ({}));
        toast.error(b.detail ?? "Failed to delete event");
        return;
      }
      toast.success("Event removed");
      await load();
    } catch {
      toast.error("Something went wrong");
    } finally {
      setActionLoading(null);
    }
  }

  const sortedEvents = selected?.events?.slice().sort((a, b) => a.sort_order - b.sort_order) ?? [];

  return (
    <div className="mx-auto max-w-6xl p-6">
      <div className="mb-6">
        <h1 className="text-xl font-semibold text-gray-900">Service Timelines</h1>
        <p className="text-sm text-muted-foreground mt-0.5">
          Build behind-the-scenes service timelines to track progress through each appointment stage.
        </p>
      </div>

      <div className="grid grid-cols-5 gap-6">
        {/* Left panel */}
        <div className="col-span-2 space-y-4">
          {/* Create form */}
          <div className="rounded-xl border border-[#1a2332]/20 bg-white p-4 shadow-sm space-y-3">
            <h3 className="text-sm font-semibold text-gray-900">New Timeline</h3>
            <div className="space-y-1">
              <label className="text-xs font-medium text-gray-700">Title *</label>
              <input
                value={createForm.title}
                onChange={(e) => setCreateForm((f) => ({ ...f, title: e.target.value }))}
                placeholder="Customer visit Apr 12"
                className="block w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-[#1a2332]"
              />
            </div>
            <div className="space-y-1">
              <label className="text-xs font-medium text-gray-700">Appointment ID (optional)</label>
              <input
                value={createForm.appointment_id}
                onChange={(e) => setCreateForm((f) => ({ ...f, appointment_id: e.target.value }))}
                placeholder="UUID"
                className="block w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-[#1a2332]"
              />
            </div>
            <Button
              disabled={actionLoading === "create"}
              onClick={createTimeline}
              className="w-full bg-[#1a2332] hover:bg-[#2a3342] text-white gap-2"
            >
              {actionLoading === "create" ? <RefreshCw className="h-4 w-4 animate-spin" /> : <PlusCircle className="h-4 w-4" />}
              Create Timeline
            </Button>
          </div>

          {/* Timeline list */}
          {loading && timelines.length === 0 ? (
            <div className="text-center py-8">
              <RefreshCw className="h-5 w-5 animate-spin mx-auto text-muted-foreground" />
            </div>
          ) : (
            <div className="rounded-xl border bg-white shadow-sm divide-y divide-gray-100">
              {timelines.length === 0 ? (
                <p className="py-8 text-center text-sm text-muted-foreground">No timelines yet</p>
              ) : (
                timelines.map((t) => (
                  <button
                    key={t.id}
                    type="button"
                    onClick={() => setSelected(t)}
                    className={`w-full text-left px-4 py-3 hover:bg-gray-50 transition-colors ${
                      selected?.id === t.id ? "bg-blue-50 border-l-2 border-l-blue-600" : ""
                    }`}
                  >
                    <p className="text-sm font-medium text-gray-900 truncate">{t.title}</p>
                    {t.appointment_id && (
                      <p className="text-xs text-muted-foreground">Appt: {t.appointment_id.slice(0, 8)}…</p>
                    )}
                    <p className="text-xs text-muted-foreground">{new Date(t.created_at).toLocaleDateString()}</p>
                  </button>
                ))
              )}
            </div>
          )}
        </div>

        {/* Right panel */}
        <div className="col-span-3">
          {!selected ? (
            <div className="rounded-xl border bg-white shadow-sm flex items-center justify-center h-64">
              <p className="text-muted-foreground text-sm">Select a timeline to view details</p>
            </div>
          ) : (
            <div className="rounded-xl border bg-white shadow-sm p-5 space-y-5">
              {/* Title + delete */}
              <div className="flex items-center justify-between gap-3">
                {editingTitle ? (
                  <div className="flex items-center gap-2 flex-1">
                    <input
                      value={titleDraft}
                      onChange={(e) => setTitleDraft(e.target.value)}
                      className="flex-1 rounded-md border border-gray-300 px-3 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-[#1a2332]"
                    />
                    <Button size="sm" onClick={saveTitle} disabled={actionLoading === "title"}
                      className="bg-[#1a2332] hover:bg-[#2a3342] text-white">
                      {actionLoading === "title" ? <RefreshCw className="h-3 w-3 animate-spin" /> : "Save"}
                    </Button>
                    <Button size="sm" variant="outline" onClick={() => setEditingTitle(false)}>Cancel</Button>
                  </div>
                ) : (
                  <button
                    type="button"
                    onClick={() => { setTitleDraft(selected.title); setEditingTitle(true); }}
                    className="text-base font-semibold text-gray-900 hover:text-blue-600 transition-colors text-left"
                  >
                    {selected.title}
                  </button>
                )}
                <Button variant="ghost" size="sm"
                  disabled={actionLoading === "del_timeline"}
                  onClick={deleteTimeline}
                  className="text-red-500 hover:text-red-700 hover:bg-red-50 flex-shrink-0"
                >
                  {actionLoading === "del_timeline"
                    ? <RefreshCw className="h-4 w-4 animate-spin" />
                    : <Trash2 className="h-4 w-4" />}
                </Button>
              </div>

              <p className="text-xs text-muted-foreground">
                Setting In Progress auto-completes all prior stages.
              </p>

              {/* Events vertical timeline */}
              {sortedEvents.length === 0 ? (
                <p className="text-sm text-muted-foreground py-4 text-center">No stages yet — add one below.</p>
              ) : (
                <div className="space-y-0">
                  {sortedEvents.map((evt, idx) => {
                    const cfg = EVENT_STATUS_CONFIG[evt.status] ?? EVENT_STATUS_CONFIG.pending;
                    const isLast = idx === sortedEvents.length - 1;
                    return (
                      <div key={evt.id} className="flex gap-3">
                        <div className="flex flex-col items-center flex-shrink-0">
                          <div className={`h-3 w-3 rounded-full mt-1 ${cfg.dot}`} />
                          {!isLast && <div className="w-px flex-1 bg-gray-200 my-1" />}
                        </div>
                        <div className={`pb-4 flex-1 min-w-0 ${evt.status === "skipped" ? "opacity-50" : ""}`}>
                          <div className="flex items-start justify-between gap-2">
                            <div className="min-w-0">
                              <div className="flex items-center gap-2 flex-wrap">
                                <span className={`text-sm font-medium ${evt.status === "skipped" ? "line-through text-gray-400" : "text-gray-900"}`}>
                                  {evt.label}
                                </span>
                                <span className="rounded-full bg-purple-100 text-purple-700 px-2 py-0.5 text-xs">{evt.stage}</span>
                                <span className="text-xs text-muted-foreground">{cfg.label}</span>
                              </div>
                              {evt.description && (
                                <p className="text-xs text-muted-foreground mt-0.5">{evt.description}</p>
                              )}
                              {evt.completed_at && (
                                <p className="text-xs text-green-600 mt-0.5">
                                  Completed {new Date(evt.completed_at).toLocaleString()}
                                </p>
                              )}
                            </div>
                            <div className="flex items-center gap-1 flex-shrink-0">
                              {(evt.status === "pending" || evt.status === "skipped") && (
                                <Button variant="ghost" size="sm" title="Mark In Progress"
                                  disabled={actionLoading === "evt_" + evt.id}
                                  onClick={() => updateEventStatus(evt.id, "in_progress")}
                                  className="h-7 px-2 text-blue-600 hover:bg-blue-50"
                                >
                                  <Play className="h-3 w-3" />
                                </Button>
                              )}
                              {(evt.status === "pending" || evt.status === "in_progress") && (
                                <Button variant="ghost" size="sm" title="Mark Complete"
                                  disabled={actionLoading === "evt_" + evt.id}
                                  onClick={() => updateEventStatus(evt.id, "completed")}
                                  className="h-7 px-2 text-green-600 hover:bg-green-50"
                                >
                                  <CheckCircle2 className="h-3 w-3" />
                                </Button>
                              )}
                              {evt.status !== "skipped" && evt.status !== "completed" && (
                                <Button variant="ghost" size="sm" title="Skip"
                                  disabled={actionLoading === "evt_" + evt.id}
                                  onClick={() => updateEventStatus(evt.id, "skipped")}
                                  className="h-7 px-2 text-gray-500 hover:bg-gray-50"
                                >
                                  <SkipForward className="h-3 w-3" />
                                </Button>
                              )}
                              <Button variant="ghost" size="sm"
                                disabled={actionLoading === "del_evt_" + evt.id}
                                onClick={() => deleteEvent(evt.id)}
                                className="h-7 px-2 text-red-400 hover:text-red-600 hover:bg-red-50"
                              >
                                {actionLoading === "del_evt_" + evt.id
                                  ? <RefreshCw className="h-3 w-3 animate-spin" />
                                  : <Trash2 className="h-3 w-3" />}
                              </Button>
                            </div>
                          </div>
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}

              {/* Add stage form */}
              <div className="border-t pt-4 space-y-3">
                <h4 className="text-xs font-semibold text-gray-700 uppercase tracking-wide">Add Stage</h4>
                <div className="grid grid-cols-2 gap-2">
                  <div className="space-y-1">
                    <label className="text-xs font-medium text-gray-700">Stage *</label>
                    <input
                      value={stageForm.stage}
                      onChange={(e) => setStageForm((f) => ({ ...f, stage: e.target.value }))}
                      placeholder="preparation"
                      className="block w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-[#1a2332]"
                    />
                  </div>
                  <div className="space-y-1">
                    <label className="text-xs font-medium text-gray-700">Label *</label>
                    <input
                      value={stageForm.label}
                      onChange={(e) => setStageForm((f) => ({ ...f, label: e.target.value }))}
                      placeholder="Preparing materials"
                      className="block w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-[#1a2332]"
                    />
                  </div>
                </div>
                <div className="space-y-1">
                  <label className="text-xs font-medium text-gray-700">Description</label>
                  <input
                    value={stageForm.description}
                    onChange={(e) => setStageForm((f) => ({ ...f, description: e.target.value }))}
                    placeholder="Optional details"
                    className="block w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-[#1a2332]"
                  />
                </div>
                <Button disabled={actionLoading === "add_stage"} onClick={addStage}
                  className="bg-[#1a2332] hover:bg-[#2a3342] text-white gap-2">
                  {actionLoading === "add_stage" ? <RefreshCw className="h-4 w-4 animate-spin" /> : <PlusCircle className="h-4 w-4" />}
                  Add Stage
                </Button>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
