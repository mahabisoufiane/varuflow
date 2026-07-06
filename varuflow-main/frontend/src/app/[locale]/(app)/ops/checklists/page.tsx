"use client";

import { useEffect, useState } from "react";
import { useRouter, useParams } from "next/navigation";
import { createClient } from "@/lib/supabase/client";
import { PlusCircle, RefreshCw, CheckSquare, Trash2, ChevronDown, ChevronRight, CheckCircle2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { toast } from "sonner";
import styles from "./page.module.scss";

interface ChecklistItem {
  id: string;
  title: string;
  description: string | null;
  sort_order: number;
}

interface ChecklistTemplate {
  id: string;
  title: string;
  category: string | null;
  description: string | null;
  frequency: string;
  items: ChecklistItem[];
}

interface RunItem {
  id: string;
  item_id: string;
  title: string;
  description: string | null;
  sort_order: number;
  is_checked: boolean;
  checked_by: string | null;
  checked_at: string | null;
  notes: string | null;
}

interface ChecklistRun {
  id: string;
  template_id: string;
  template_title: string;
  started_at: string;
  completed_at: string | null;
  status: string;
  items: RunItem[];
  checked_count: number;
  total_count: number;
}

const FREQ_CONFIG: Record<string, { label: string; color: string }> = {
  daily:   { label: "Daily",   color: "bg-green-100 text-green-700"  },
  weekly:  { label: "Weekly",  color: "bg-blue-100 text-blue-700"    },
  monthly: { label: "Monthly", color: "bg-purple-100 text-purple-700" },
  manual:  { label: "Manual",  color: "bg-gray-100 text-gray-600"    },
};

const FREQ_MODULE: Record<string, keyof typeof styles> = {
  daily:   "freqDaily",
  weekly:  "freqWeekly",
  monthly: "freqMonthly",
  manual:  "freqManual",
};

type TabType = "templates" | "runs";

export default function ChecklistsPage() {
  const router = useRouter();
  const params = useParams<{ locale: string }>();
  const locale = params?.locale ?? "en";
  const supabase = createClient();

  const [tab, setTab] = useState<TabType>("templates");
  const [templates, setTemplates] = useState<ChecklistTemplate[]>([]);
  const [runs, setRuns] = useState<ChecklistRun[]>([]);
  const [loading, setLoading] = useState(true);
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [actionLoading, setActionLoading] = useState<string | null>(null);
  const [runNotes, setRunNotes] = useState<Record<string, string>>({});

  const [showNew, setShowNew] = useState(false);
  const [newForm, setNewForm] = useState({ title: "", category: "", description: "", frequency: "manual" });

  const [showAddItem, setShowAddItem] = useState<string | null>(null);
  const [newItem, setNewItem] = useState({ title: "", description: "", sort_order: "0" });

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

      const [tRes, rRes] = await Promise.all([
        fetch(apiUrl("/api/checklists/templates"), { headers: { Authorization: `Bearer ${token}` } }),
        fetch(apiUrl("/api/checklists/runs"), { headers: { Authorization: `Bearer ${token}` } }),
      ]);
      if (tRes.status === 401) { router.push(`/${locale}/auth/login`); return; }
      if (tRes.ok) setTemplates(await tRes.json());
      if (rRes.ok) setRuns(await rRes.json());
    } catch {
      toast.error("Failed to load checklists");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { load(); }, []);  // eslint-disable-line react-hooks/exhaustive-deps

  async function createTemplate() {
    if (!newForm.title.trim()) { toast.error("Title is required"); return; }
    setActionLoading("create");
    try {
      const token = await getToken();
      if (!token) return;
      const res = await fetch(apiUrl("/api/checklists/templates"), {
        method: "POST",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
        body: JSON.stringify({
          title: newForm.title,
          category: newForm.category || null,
          description: newForm.description || null,
          frequency: newForm.frequency,
        }),
      });
      if (!res.ok) {
        const b = await res.json().catch(() => ({}));
        toast.error(b.detail ?? "Failed to create template");
        return;
      }
      toast.success("Template created");
      setShowNew(false);
      setNewForm({ title: "", category: "", description: "", frequency: "manual" });
      await load();
    } catch {
      toast.error("Something went wrong");
    } finally {
      setActionLoading(null);
    }
  }

  async function deleteTemplate(id: string) {
    setActionLoading(id + "_delete");
    try {
      const token = await getToken();
      if (!token) return;
      const res = await fetch(apiUrl(`/api/checklists/templates/${id}`), {
        method: "DELETE",
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) {
        const b = await res.json().catch(() => ({}));
        toast.error(b.detail ?? "Failed to delete template");
        return;
      }
      toast.success("Template deleted");
      await load();
    } catch {
      toast.error("Something went wrong");
    } finally {
      setActionLoading(null);
    }
  }

  async function startRun(templateId: string) {
    setActionLoading(templateId + "_start");
    try {
      const token = await getToken();
      if (!token) return;
      const res = await fetch(apiUrl(`/api/checklists/templates/${templateId}/start`), {
        method: "POST",
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) {
        const b = await res.json().catch(() => ({}));
        toast.error(b.detail ?? "Failed to start run");
        return;
      }
      toast.success("Run started");
      await load();
      setTab("runs");
    } catch {
      toast.error("Something went wrong");
    } finally {
      setActionLoading(null);
    }
  }

  async function addItem(templateId: string) {
    if (!newItem.title.trim()) { toast.error("Title is required"); return; }
    setActionLoading(templateId + "_additem");
    try {
      const token = await getToken();
      if (!token) return;
      const res = await fetch(apiUrl(`/api/checklists/templates/${templateId}/items`), {
        method: "POST",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
        body: JSON.stringify({
          title: newItem.title,
          description: newItem.description || null,
          sort_order: parseInt(newItem.sort_order) || 0,
        }),
      });
      if (!res.ok) {
        const b = await res.json().catch(() => ({}));
        toast.error(b.detail ?? "Failed to add item");
        return;
      }
      toast.success("Item added");
      setShowAddItem(null);
      setNewItem({ title: "", description: "", sort_order: "0" });
      await load();
    } catch {
      toast.error("Something went wrong");
    } finally {
      setActionLoading(null);
    }
  }

  async function deleteItem(itemId: string) {
    setActionLoading(itemId + "_delitem");
    try {
      const token = await getToken();
      if (!token) return;
      const res = await fetch(apiUrl(`/api/checklists/items/${itemId}`), {
        method: "DELETE",
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) {
        const b = await res.json().catch(() => ({}));
        toast.error(b.detail ?? "Failed to delete item");
        return;
      }
      toast.success("Item deleted");
      await load();
    } catch {
      toast.error("Something went wrong");
    } finally {
      setActionLoading(null);
    }
  }

  async function toggleCheck(runId: string, itemId: string, currentlyChecked: boolean) {
    setActionLoading(`${runId}_check_${itemId}`);
    try {
      const token = await getToken();
      if (!token) return;
      const res = await fetch(apiUrl(`/api/checklists/runs/${runId}/check/${itemId}`), {
        method: "POST",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
        body: JSON.stringify({ checked: !currentlyChecked }),
      });
      if (!res.ok) {
        const b = await res.json().catch(() => ({}));
        toast.error(b.detail ?? "Failed to update");
        return;
      }
      await load();
    } catch {
      toast.error("Something went wrong");
    } finally {
      setActionLoading(null);
    }
  }

  async function saveItemNotes(runId: string, itemId: string) {
    const notes = runNotes[`${runId}_${itemId}`];
    if (notes === undefined) return;
    try {
      const token = await getToken();
      if (!token) return;
      await fetch(apiUrl(`/api/checklists/runs/${runId}/items/${itemId}`), {
        method: "PATCH",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
        body: JSON.stringify({ notes }),
      });
    } catch {
      toast.error("Failed to save notes");
    }
  }

  return (
    <div className="mx-auto max-w-4xl space-y-6 p-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-gray-900">Checklist Templates</h1>
          <p className="text-sm text-muted-foreground mt-0.5">Reusable checklists for recurring routines.</p>
        </div>
        {tab === "templates" && (
          <Button onClick={() => setShowNew(true)} className="bg-[var(--vf-brand-primary)] hover:bg-[var(--vf-brand-primary-hover)] text-white gap-2">
            <PlusCircle className="h-4 w-4" /> New Template
          </Button>
        )}
      </div>

      {/* Tabs */}
      <div className={styles.tabBar}>
        {(["templates", "runs"] as const).map((t) => (
          <button
            key={t}
            type="button"
            onClick={() => setTab(t)}
            className={`${styles.tab} ${tab === t ? styles.tabActive : ""}`}
          >
            {t === "templates" ? "Templates" : "Active Runs"}
          </button>
        ))}
      </div>

      {/* New template form */}
      {showNew && tab === "templates" && (
        <div className={styles.formCard}>
          <h3 className="text-sm font-semibold text-gray-900">Create Template</h3>
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1">
              <label className="text-xs font-medium text-gray-700">Title *</label>
              <input
                value={newForm.title}
                onChange={(e) => setNewForm((f) => ({ ...f, title: e.target.value }))}
                placeholder="Daily Opening Checklist"
                className={styles.formInput}
              />
            </div>
            <div className="space-y-1">
              <label className="text-xs font-medium text-gray-700">Category</label>
              <input
                value={newForm.category}
                onChange={(e) => setNewForm((f) => ({ ...f, category: e.target.value }))}
                placeholder="Operations, Finance…"
                className={styles.formInput}
              />
            </div>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1">
              <label className="text-xs font-medium text-gray-700">Description</label>
              <input
                value={newForm.description}
                onChange={(e) => setNewForm((f) => ({ ...f, description: e.target.value }))}
                placeholder="Optional description…"
                className={styles.formInput}
              />
            </div>
            <div className="space-y-1">
              <label className="text-xs font-medium text-gray-700">Frequency</label>
              <select
                value={newForm.frequency}
                onChange={(e) => setNewForm((f) => ({ ...f, frequency: e.target.value }))}
                className={styles.formInput}
              >
                <option value="daily">Daily</option>
                <option value="weekly">Weekly</option>
                <option value="monthly">Monthly</option>
                <option value="manual">Manual</option>
              </select>
            </div>
          </div>
          <div className="flex gap-2">
            <Button variant="outline" onClick={() => setShowNew(false)}>Cancel</Button>
            <Button
              disabled={actionLoading === "create"}
              onClick={createTemplate}
              className="bg-[var(--vf-brand-primary)] hover:bg-[var(--vf-brand-primary-hover)] text-white"
            >
              {actionLoading === "create" ? "Creating…" : "Create Template"}
            </Button>
          </div>
        </div>
      )}

      {/* Content */}
      {loading && templates.length === 0 ? (
        <div className="text-center py-12">
          <RefreshCw className="h-6 w-6 animate-spin mx-auto text-muted-foreground" />
        </div>
      ) : tab === "templates" ? (
        templates.length === 0 ? (
          <div className="rounded-xl border bg-white shadow-sm py-12 text-center">
            <CheckSquare className="h-10 w-10 text-muted-foreground mx-auto mb-3" />
            <p className="text-gray-600 font-medium">No templates yet</p>
          </div>
        ) : (
          <div className={styles.templateList}>
            {templates.map((tmpl) => {
              const freq = FREQ_CONFIG[tmpl.frequency] ?? FREQ_CONFIG.manual;
              const isExpanded = expandedId === tmpl.id;

              return (
                <div key={tmpl.id}>
                  <div className={styles.templateRow}>
                    <button
                      type="button"
                      onClick={() => setExpandedId(isExpanded ? null : tmpl.id)}
                      className="flex-1 min-w-0 text-left"
                    >
                      <div className="flex items-center gap-2">
                        {isExpanded
                          ? <ChevronDown className="h-4 w-4 text-muted-foreground flex-shrink-0" />
                          : <ChevronRight className="h-4 w-4 text-muted-foreground flex-shrink-0" />}
                        <span className="text-sm font-medium text-gray-900">{tmpl.title}</span>
                        {tmpl.category && (
                          <span className="rounded-full bg-purple-100 text-purple-700 px-2 py-0.5 text-xs">
                            {tmpl.category}
                          </span>
                        )}
                        <span className={styles[FREQ_MODULE[tmpl.frequency] ?? "freqManual"]}>
                          {freq.label}
                        </span>
                      </div>
                      <p className="text-xs text-muted-foreground mt-0.5 pl-6">
                        {tmpl.items.length} item{tmpl.items.length !== 1 ? "s" : ""}
                        {tmpl.description ? ` · ${tmpl.description}` : ""}
                      </p>
                    </button>

                    <div className="flex items-center gap-2 flex-shrink-0">
                      <Button
                        size="sm"
                        disabled={actionLoading === tmpl.id + "_start"}
                        onClick={() => startRun(tmpl.id)}
                        className="bg-[var(--vf-brand-primary)] hover:bg-[var(--vf-brand-primary-hover)] text-white"
                      >
                        {actionLoading === tmpl.id + "_start"
                          ? <RefreshCw className="h-3 w-3 animate-spin" />
                          : "Start Run"}
                      </Button>
                      <Button
                        variant="ghost"
                        size="sm"
                        disabled={actionLoading === tmpl.id + "_delete"}
                        onClick={() => deleteTemplate(tmpl.id)}
                        className="text-red-600 hover:text-red-700 hover:bg-red-50"
                      >
                        <Trash2 className="h-4 w-4" />
                      </Button>
                    </div>
                  </div>

                  {isExpanded && (
                    <div className="border-t border-gray-100 bg-gray-50 px-5 py-4 space-y-3">
                      <p className="text-xs font-semibold text-gray-700 uppercase tracking-wide">Items</p>
                      {tmpl.items.length === 0 ? (
                        <p className="text-sm text-muted-foreground">No items yet. Add the first one below.</p>
                      ) : (
                        <div className="space-y-1">
                          {[...tmpl.items]
                            .sort((a, b) => a.sort_order - b.sort_order)
                            .map((item) => (
                              <div key={item.id} className="flex items-center gap-3 bg-white rounded-md border border-gray-200 px-3 py-2">
                                <span className="text-xs font-mono text-muted-foreground w-6 text-right flex-shrink-0">
                                  {item.sort_order}
                                </span>
                                <div className="flex-1 min-w-0">
                                  <p className="text-sm text-gray-900">{item.title}</p>
                                  {item.description && (
                                    <p className="text-xs text-muted-foreground">{item.description}</p>
                                  )}
                                </div>
                                <Button
                                  variant="ghost"
                                  size="sm"
                                  disabled={actionLoading === item.id + "_delitem"}
                                  onClick={() => deleteItem(item.id)}
                                  className="text-red-500 hover:text-red-600 hover:bg-red-50 flex-shrink-0"
                                >
                                  <Trash2 className="h-3 w-3" />
                                </Button>
                              </div>
                            ))}
                        </div>
                      )}

                      {showAddItem === tmpl.id ? (
                        <div className="bg-white rounded-md border border-[var(--vf-brand-primary)]/20 p-3 space-y-2">
                          <div className="grid grid-cols-3 gap-2">
                            <div className="col-span-2 space-y-1">
                              <label className="text-xs font-medium text-gray-700">Title *</label>
                              <input
                                value={newItem.title}
                                onChange={(e) => setNewItem((n) => ({ ...n, title: e.target.value }))}
                                placeholder="Check inventory levels"
                                className="block w-full rounded-md border border-gray-300 px-2 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-[var(--vf-brand-primary)]"
                              />
                            </div>
                            <div className="space-y-1">
                              <label className="text-xs font-medium text-gray-700">Sort Order</label>
                              <input
                                type="number"
                                value={newItem.sort_order}
                                onChange={(e) => setNewItem((n) => ({ ...n, sort_order: e.target.value }))}
                                className="block w-full rounded-md border border-gray-300 px-2 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-[var(--vf-brand-primary)]"
                              />
                            </div>
                          </div>
                          <div className="space-y-1">
                            <label className="text-xs font-medium text-gray-700">Description</label>
                            <input
                              value={newItem.description}
                              onChange={(e) => setNewItem((n) => ({ ...n, description: e.target.value }))}
                              placeholder="Optional description…"
                              className="block w-full rounded-md border border-gray-300 px-2 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-[var(--vf-brand-primary)]"
                            />
                          </div>
                          <div className="flex gap-2">
                            <Button variant="outline" size="sm" onClick={() => setShowAddItem(null)}>Cancel</Button>
                            <Button
                              size="sm"
                              disabled={actionLoading === tmpl.id + "_additem"}
                              onClick={() => addItem(tmpl.id)}
                              className="bg-[var(--vf-brand-primary)] hover:bg-[var(--vf-brand-primary-hover)] text-white"
                            >
                              Add Item
                            </Button>
                          </div>
                        </div>
                      ) : (
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => setShowAddItem(tmpl.id)}
                          className="gap-1"
                        >
                          <PlusCircle className="h-3.5 w-3.5" /> Add Item
                        </Button>
                      )}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )
      ) : (
        /* Runs tab */
        runs.length === 0 ? (
          <div className="rounded-xl border bg-white shadow-sm py-12 text-center">
            <CheckSquare className="h-10 w-10 text-muted-foreground mx-auto mb-3" />
            <p className="text-gray-600 font-medium">No active runs</p>
          </div>
        ) : (
          <div className="rounded-xl border bg-white shadow-sm divide-y divide-gray-100">
            {runs.map((run) => {
              const isExpanded = expandedId === run.id;
              const progress = run.total_count > 0
                ? Math.round((run.checked_count / run.total_count) * 100)
                : 0;
              const statusColor = run.status === "completed"
                ? "bg-green-100 text-green-700"
                : "bg-blue-100 text-blue-700";

              return (
                <div key={run.id}>
                  <div className="flex items-center gap-4 px-5 py-4">
                    <button
                      type="button"
                      onClick={() => setExpandedId(isExpanded ? null : run.id)}
                      className="flex-1 min-w-0 text-left"
                    >
                      <div className="flex items-center gap-2">
                        {isExpanded
                          ? <ChevronDown className="h-4 w-4 text-muted-foreground flex-shrink-0" />
                          : <ChevronRight className="h-4 w-4 text-muted-foreground flex-shrink-0" />}
                        <span className="text-sm font-medium text-gray-900">{run.template_title}</span>
                        <span className={`rounded-full px-2.5 py-0.5 text-xs font-medium ${statusColor}`}>
                          {run.status === "completed" ? "Completed" : "In Progress"}
                        </span>
                      </div>
                      <p className="text-xs text-muted-foreground mt-0.5 pl-6">
                        Started {new Date(run.started_at).toLocaleDateString()} · {progress}% complete
                        ({run.checked_count}/{run.total_count})
                      </p>
                    </button>
                  </div>

                  {isExpanded && (
                    <div className="border-t border-gray-100 bg-gray-50 px-5 py-4 space-y-3">
                      {run.status === "completed" && run.completed_at && (
                        <div className="flex items-center gap-2 rounded-md bg-green-50 border border-green-200 px-3 py-2">
                          <CheckCircle2 className="h-4 w-4 text-green-600 flex-shrink-0" />
                          <p className="text-sm text-green-800 font-medium">
                            Completed on {new Date(run.completed_at).toLocaleString()}
                          </p>
                        </div>
                      )}

                      <div className="space-y-2">
                        {[...run.items]
                          .sort((a, b) => a.sort_order - b.sort_order)
                          .map((item) => {
                            const noteKey = `${run.id}_${item.id}`;
                            const noteValue = runNotes[noteKey] ?? item.notes ?? "";
                            return (
                              <div key={item.id} className="bg-white rounded-md border border-gray-200 p-3 space-y-2">
                                <div className="flex items-start gap-3">
                                  <input
                                    type="checkbox"
                                    checked={item.is_checked}
                                    disabled={
                                      run.status === "completed" ||
                                      actionLoading === `${run.id}_check_${item.id}`
                                    }
                                    onChange={() => toggleCheck(run.id, item.id, item.is_checked)}
                                    className="mt-0.5 h-4 w-4 rounded border-gray-300 accent-[var(--vf-brand-primary)] cursor-pointer"
                                  />
                                  <div className="flex-1 min-w-0">
                                    <p className={`text-sm font-medium ${item.is_checked ? "line-through text-muted-foreground" : "text-gray-900"}`}>
                                      {item.title}
                                    </p>
                                    {item.description && (
                                      <p className="text-xs text-muted-foreground">{item.description}</p>
                                    )}
                                    {item.is_checked && item.checked_by && (
                                      <p className="text-xs text-muted-foreground mt-0.5">
                                        Checked by {item.checked_by.slice(0, 8)}…
                                        {item.checked_at ? ` at ${new Date(item.checked_at).toLocaleTimeString()}` : ""}
                                      </p>
                                    )}
                                  </div>
                                </div>
                                <input
                                  type="text"
                                  value={noteValue}
                                  onChange={(e) => setRunNotes((n) => ({ ...n, [noteKey]: e.target.value }))}
                                  onBlur={() => saveItemNotes(run.id, item.id)}
                                  placeholder="Add notes…"
                                  disabled={run.status === "completed"}
                                  className="block w-full rounded-md border border-gray-200 px-2 py-1.5 text-xs text-gray-600 focus:outline-none focus:ring-1 focus:ring-[var(--vf-brand-primary)] disabled:bg-gray-50"
                                />
                              </div>
                            );
                          })}
                      </div>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )
      )}
    </div>
  );
}
