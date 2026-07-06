"use client";

import { useEffect, useState } from "react";
import { useRouter, useParams } from "next/navigation";
import { createClient } from "@/lib/supabase/client";
import { PlusCircle, RefreshCw, ClipboardList, ChevronDown, ChevronRight } from "lucide-react";
import { Button } from "@/components/ui/button";
import { toast } from "sonner";
import styles from "./page.module.scss";

interface DecisionStats {
  total: number;
  last_90_days: number;
  by_area: Record<string, number>;
}

interface Decision {
  id: string;
  title: string;
  area: string;
  decided_at: string;
  decided_by_name: string | null;
  status: string;
  decision_summary: string;
  alternatives_considered: string | null;
  expected_outcome: string | null;
  actual_outcome: string | null;
}

const AREA_COLORS: Record<string, string> = {
  product:    "bg-blue-100 text-blue-700",
  finance:    "bg-green-100 text-green-700",
  hr:         "bg-purple-100 text-purple-700",
  operations: "bg-orange-100 text-orange-700",
  strategy:   "bg-indigo-100 text-indigo-700",
  other:      "bg-gray-100 text-gray-600",
};

const AREA_MODULE: Record<string, keyof typeof styles> = {
  product:    "areaProduct",
  finance:    "areaFinance",
  hr:         "areaHr",
  operations: "areaOperations",
  strategy:   "areaStrategy",
  other:      "areaOther",
};

const STATUS_CONFIG: Record<string, { label: string; color: string }> = {
  pending:     { label: "Pending",     color: "bg-gray-100 text-gray-600"  },
  in_progress: { label: "In Progress", color: "bg-blue-100 text-blue-700"  },
  completed:   { label: "Completed",   color: "bg-green-100 text-green-700" },
  reversed:    { label: "Reversed",    color: "bg-red-100 text-red-700"    },
};

const STATUS_MODULE: Record<string, keyof typeof styles> = {
  pending:     "statusPending",
  in_progress: "statusInProgress",
  completed:   "statusCompleted",
  reversed:    "statusReversed",
};

const AREAS = ["product", "finance", "hr", "operations", "strategy", "other"] as const;

export default function DecisionsPage() {
  const router = useRouter();
  const params = useParams<{ locale: string }>();
  const locale = params?.locale ?? "en";
  const supabase = createClient();

  const [decisions, setDecisions] = useState<Decision[]>([]);
  const [stats, setStats] = useState<DecisionStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [areaFilter, setAreaFilter] = useState<string>("all");
  const [statusFilter, setStatusFilter] = useState<string>("all");
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editForm, setEditForm] = useState<Partial<Decision>>({});
  const [actionLoading, setActionLoading] = useState<string | null>(null);

  const [showNew, setShowNew] = useState(false);
  const [newForm, setNewForm] = useState({
    title: "",
    decided_at: new Date().toISOString().split("T")[0],
    decided_by_name: "",
    area: "operations",
    decision_summary: "",
    alternatives_considered: "",
    expected_outcome: "",
  });

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

      const [decRes, statsRes] = await Promise.all([
        fetch(apiUrl("/api/decisions"), { headers: { Authorization: `Bearer ${token}` } }),
        fetch(apiUrl("/api/decisions/stats"), { headers: { Authorization: `Bearer ${token}` } }),
      ]);
      if (decRes.status === 401) { router.push(`/${locale}/auth/login`); return; }
      if (decRes.ok) setDecisions(await decRes.json());
      if (statsRes.ok) setStats(await statsRes.json());
    } catch {
      toast.error("Failed to load decisions");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { load(); }, []);  // eslint-disable-line react-hooks/exhaustive-deps

  async function createDecision() {
    if (!newForm.title.trim()) { toast.error("Title is required"); return; }
    if (!newForm.decided_at) { toast.error("Decided At is required"); return; }
    if (!newForm.decision_summary.trim()) { toast.error("Decision summary is required"); return; }
    setActionLoading("create");
    try {
      const token = await getToken();
      if (!token) return;
      const res = await fetch(apiUrl("/api/decisions"), {
        method: "POST",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
        body: JSON.stringify({
          title: newForm.title,
          decided_at: newForm.decided_at,
          decided_by_name: newForm.decided_by_name || null,
          area: newForm.area,
          decision_summary: newForm.decision_summary,
          alternatives_considered: newForm.alternatives_considered || null,
          expected_outcome: newForm.expected_outcome || null,
        }),
      });
      if (!res.ok) {
        const b = await res.json().catch(() => ({}));
        toast.error(b.detail ?? "Failed to create decision");
        return;
      }
      toast.success("Decision logged");
      setShowNew(false);
      setNewForm({
        title: "",
        decided_at: new Date().toISOString().split("T")[0],
        decided_by_name: "",
        area: "operations",
        decision_summary: "",
        alternatives_considered: "",
        expected_outcome: "",
      });
      await load();
    } catch {
      toast.error("Something went wrong");
    } finally {
      setActionLoading(null);
    }
  }

  async function saveEdit(id: string) {
    setActionLoading(id + "_save");
    try {
      const token = await getToken();
      if (!token) return;
      const res = await fetch(apiUrl(`/api/decisions/${id}`), {
        method: "PATCH",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
        body: JSON.stringify(editForm),
      });
      if (!res.ok) {
        const b = await res.json().catch(() => ({}));
        toast.error(b.detail ?? "Failed to save");
        return;
      }
      toast.success("Decision updated");
      setEditingId(null);
      setEditForm({});
      await load();
    } catch {
      toast.error("Something went wrong");
    } finally {
      setActionLoading(null);
    }
  }

  const filtered = decisions
    .filter((d) => {
      if (areaFilter !== "all" && d.area !== areaFilter) return false;
      if (statusFilter !== "all" && d.status !== statusFilter) return false;
      return true;
    })
    .sort((a, b) => new Date(b.decided_at).getTime() - new Date(a.decided_at).getTime());

  return (
    <div className="mx-auto max-w-4xl space-y-6 p-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-gray-900">Decision Log</h1>
          <p className="text-sm text-muted-foreground mt-0.5">
            Record significant business decisions with context and outcomes.
          </p>
        </div>
        <Button onClick={() => setShowNew(true)} className="bg-[var(--vf-brand-primary)] hover:bg-[var(--vf-brand-primary-hover)] text-white gap-2">
          <PlusCircle className="h-4 w-4" /> Log Decision
        </Button>
      </div>

      {/* Stats row */}
      {stats && (
        <div className="flex flex-wrap items-center gap-3">
          <div className="rounded-lg border bg-white shadow-sm px-4 py-3 flex flex-col items-center min-w-[90px]">
            <p className="text-2xl font-bold text-gray-900">{stats.total}</p>
            <p className="text-xs text-muted-foreground">Total</p>
          </div>
          <div className="rounded-lg border bg-white shadow-sm px-4 py-3 flex flex-col items-center min-w-[90px]">
            <p className="text-2xl font-bold text-gray-900">{stats.last_90_days}</p>
            <p className="text-xs text-muted-foreground">Last 90 days</p>
          </div>
          {Object.entries(stats.by_area).map(([area, count]) => (
            <span
              key={area}
              className={`rounded-full px-3 py-1 text-xs font-medium ${AREA_COLORS[area] ?? AREA_COLORS.other}`}
            >
              {area}: {count}
            </span>
          ))}
        </div>
      )}

      {/* Filters */}
      <div className="flex items-center gap-3 flex-wrap">
        <select
          value={areaFilter}
          onChange={(e) => setAreaFilter(e.target.value)}
          className="rounded-md border border-gray-300 px-3 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-[var(--vf-brand-primary)]"
        >
          <option value="all">All Areas</option>
          {AREAS.map((a) => (
            <option key={a} value={a}>{a.charAt(0).toUpperCase() + a.slice(1)}</option>
          ))}
        </select>
        <select
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value)}
          className="rounded-md border border-gray-300 px-3 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-[var(--vf-brand-primary)]"
        >
          <option value="all">All Statuses</option>
          {Object.entries(STATUS_CONFIG).map(([k, v]) => (
            <option key={k} value={k}>{v.label}</option>
          ))}
        </select>
      </div>

      {/* New decision form */}
      {showNew && (
        <div className="rounded-xl border border-[var(--vf-brand-primary)]/20 bg-white p-5 shadow-sm space-y-3">
          <h3 className="text-sm font-semibold text-gray-900">Log Decision</h3>
          <div className="grid grid-cols-2 gap-3">
            <div className="col-span-2 space-y-1">
              <label className="text-xs font-medium text-gray-700">Title *</label>
              <input
                value={newForm.title}
                onChange={(e) => setNewForm((f) => ({ ...f, title: e.target.value }))}
                placeholder="Move to new warehouse provider"
                className="block w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-[var(--vf-brand-primary)]"
              />
            </div>
            <div className="space-y-1">
              <label className="text-xs font-medium text-gray-700">Decided At *</label>
              <input
                type="date"
                value={newForm.decided_at}
                onChange={(e) => setNewForm((f) => ({ ...f, decided_at: e.target.value }))}
                className="block w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-[var(--vf-brand-primary)]"
              />
            </div>
            <div className="space-y-1">
              <label className="text-xs font-medium text-gray-700">Decided By</label>
              <input
                value={newForm.decided_by_name}
                onChange={(e) => setNewForm((f) => ({ ...f, decided_by_name: e.target.value }))}
                placeholder="Anna Svensson"
                className="block w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-[var(--vf-brand-primary)]"
              />
            </div>
            <div className="space-y-1">
              <label className="text-xs font-medium text-gray-700">Area</label>
              <select
                value={newForm.area}
                onChange={(e) => setNewForm((f) => ({ ...f, area: e.target.value }))}
                className="block w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-[var(--vf-brand-primary)]"
              >
                {AREAS.map((a) => (
                  <option key={a} value={a}>{a.charAt(0).toUpperCase() + a.slice(1)}</option>
                ))}
              </select>
            </div>
          </div>
          <div className="space-y-1">
            <label className="text-xs font-medium text-gray-700">Decision Summary *</label>
            <textarea
              value={newForm.decision_summary}
              onChange={(e) => setNewForm((f) => ({ ...f, decision_summary: e.target.value }))}
              rows={3}
              placeholder="Describe the decision made…"
              className="block w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-[var(--vf-brand-primary)]"
            />
          </div>
          <div className="space-y-1">
            <label className="text-xs font-medium text-gray-700">Alternatives Considered</label>
            <textarea
              value={newForm.alternatives_considered}
              onChange={(e) => setNewForm((f) => ({ ...f, alternatives_considered: e.target.value }))}
              rows={2}
              placeholder="What other options were evaluated?"
              className="block w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-[var(--vf-brand-primary)]"
            />
          </div>
          <div className="space-y-1">
            <label className="text-xs font-medium text-gray-700">Expected Outcome</label>
            <textarea
              value={newForm.expected_outcome}
              onChange={(e) => setNewForm((f) => ({ ...f, expected_outcome: e.target.value }))}
              rows={2}
              placeholder="What outcome is expected?"
              className="block w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-[var(--vf-brand-primary)]"
            />
          </div>
          <div className="flex gap-2">
            <Button variant="outline" onClick={() => setShowNew(false)}>Cancel</Button>
            <Button
              disabled={actionLoading === "create"}
              onClick={createDecision}
              className="bg-[var(--vf-brand-primary)] hover:bg-[var(--vf-brand-primary-hover)] text-white"
            >
              {actionLoading === "create" ? "Saving…" : "Log Decision"}
            </Button>
          </div>
        </div>
      )}

      {/* List */}
      {loading && decisions.length === 0 ? (
        <div className="text-center py-12">
          <RefreshCw className="h-6 w-6 animate-spin mx-auto text-muted-foreground" />
        </div>
      ) : filtered.length === 0 ? (
        <div className="rounded-xl border bg-white shadow-sm py-12 text-center">
          <ClipboardList className="h-10 w-10 text-muted-foreground mx-auto mb-3" />
          <p className="text-gray-600 font-medium">No decisions found</p>
        </div>
      ) : (
        <div className="rounded-xl border bg-white shadow-sm divide-y divide-gray-100">
          {filtered.map((dec) => {
            const areaCls = AREA_COLORS[dec.area] ?? AREA_COLORS.other;
            const statusCfg = STATUS_CONFIG[dec.status] ?? STATUS_CONFIG.pending;
            const isExpanded = expandedId === dec.id;
            const isEditing = editingId === dec.id;

            return (
              <div key={dec.id}>
                <div className="flex items-center gap-4 px-5 py-4">
                  <button
                    type="button"
                    onClick={() => setExpandedId(isExpanded ? null : dec.id)}
                    className="flex-1 min-w-0 text-left"
                  >
                    <div className="flex items-center gap-2">
                      {isExpanded
                        ? <ChevronDown className="h-4 w-4 text-muted-foreground flex-shrink-0" />
                        : <ChevronRight className="h-4 w-4 text-muted-foreground flex-shrink-0" />}
                      <span className="text-sm font-medium text-gray-900">{dec.title}</span>
                      <span className={styles[AREA_MODULE[dec.area] ?? "areaOther"]}>
                        {dec.area}
                      </span>
                    </div>
                    <p className="text-xs text-muted-foreground mt-0.5 pl-6">
                      {new Date(dec.decided_at).toLocaleDateString()}
                      {dec.decided_by_name ? ` · ${dec.decided_by_name}` : ""}
                    </p>
                  </button>

                  <span className={styles[STATUS_MODULE[dec.status] ?? "statusPending"]}>
                    {STATUS_CONFIG[dec.status]?.label ?? dec.status}
                  </span>
                </div>

                {isExpanded && (
                  <div className="border-t border-gray-100 bg-gray-50 px-5 py-4 space-y-4">
                    {isEditing ? (
                      /* Edit mode */
                      <div className="space-y-3">
                        <div className="space-y-1">
                          <label className="text-xs font-medium text-gray-700">Decision Summary</label>
                          <textarea
                            value={editForm.decision_summary ?? dec.decision_summary}
                            onChange={(e) => setEditForm((f) => ({ ...f, decision_summary: e.target.value }))}
                            rows={3}
                            className="block w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-[var(--vf-brand-primary)]"
                          />
                        </div>
                        <div className="space-y-1">
                          <label className="text-xs font-medium text-gray-700">Alternatives Considered</label>
                          <textarea
                            value={editForm.alternatives_considered ?? dec.alternatives_considered ?? ""}
                            onChange={(e) => setEditForm((f) => ({ ...f, alternatives_considered: e.target.value }))}
                            rows={2}
                            className="block w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-[var(--vf-brand-primary)]"
                          />
                        </div>
                        <div className="space-y-1">
                          <label className="text-xs font-medium text-gray-700">Expected Outcome</label>
                          <textarea
                            value={editForm.expected_outcome ?? dec.expected_outcome ?? ""}
                            onChange={(e) => setEditForm((f) => ({ ...f, expected_outcome: e.target.value }))}
                            rows={2}
                            className="block w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-[var(--vf-brand-primary)]"
                          />
                        </div>
                        <div className="space-y-1">
                          <label className="text-xs font-medium text-gray-700">Actual Outcome</label>
                          <textarea
                            value={editForm.actual_outcome ?? dec.actual_outcome ?? ""}
                            onChange={(e) => setEditForm((f) => ({ ...f, actual_outcome: e.target.value }))}
                            rows={2}
                            placeholder="What actually happened?"
                            className="block w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-[var(--vf-brand-primary)]"
                          />
                        </div>
                        <div className="space-y-1">
                          <label className="text-xs font-medium text-gray-700">Status</label>
                          <select
                            value={editForm.status ?? dec.status}
                            onChange={(e) => setEditForm((f) => ({ ...f, status: e.target.value }))}
                            className="rounded-md border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-[var(--vf-brand-primary)]"
                          >
                            {Object.entries(STATUS_CONFIG).map(([k, v]) => (
                              <option key={k} value={k}>{v.label}</option>
                            ))}
                          </select>
                        </div>
                        <div className="flex gap-2">
                          <Button
                            variant="outline"
                            onClick={() => { setEditingId(null); setEditForm({}); }}
                          >
                            Cancel
                          </Button>
                          <Button
                            disabled={actionLoading === dec.id + "_save"}
                            onClick={() => saveEdit(dec.id)}
                            className="bg-[var(--vf-brand-primary)] hover:bg-[var(--vf-brand-primary-hover)] text-white"
                          >
                            {actionLoading === dec.id + "_save" ? "Saving…" : "Save Changes"}
                          </Button>
                        </div>
                      </div>
                    ) : (
                      /* View mode */
                      <>
                        <div className="space-y-1">
                          <p className="text-xs font-semibold text-gray-700 uppercase tracking-wide">Decision Summary</p>
                          <p className="text-sm text-gray-800">{dec.decision_summary}</p>
                        </div>
                        <div className="space-y-1">
                          <p className="text-xs font-semibold text-gray-700 uppercase tracking-wide">Alternatives Considered</p>
                          <p className="text-sm text-gray-600">{dec.alternatives_considered ?? <span className="text-muted-foreground italic">None recorded</span>}</p>
                        </div>
                        {dec.expected_outcome && (
                          <div className="space-y-1">
                            <p className="text-xs font-semibold text-gray-700 uppercase tracking-wide">Expected Outcome</p>
                            <p className="text-sm text-gray-600">{dec.expected_outcome}</p>
                          </div>
                        )}
                        {dec.actual_outcome && (
                          <div className="space-y-1">
                            <p className="text-xs font-semibold text-gray-700 uppercase tracking-wide">Actual Outcome</p>
                            <p className="text-sm text-gray-600">{dec.actual_outcome}</p>
                          </div>
                        )}
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => {
                            setEditingId(dec.id);
                            setEditForm({
                              decision_summary: dec.decision_summary,
                              alternatives_considered: dec.alternatives_considered ?? "",
                              expected_outcome: dec.expected_outcome ?? "",
                              actual_outcome: dec.actual_outcome ?? "",
                              status: dec.status,
                            });
                          }}
                        >
                          Edit
                        </Button>
                      </>
                    )}
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
