"use client";

import { useEffect, useState } from "react";
import { useRouter, useParams } from "next/navigation";
import { createClient } from "@/lib/supabase/client";
import {
  PlusCircle, ChevronRight, ChevronDown, Target, CheckCircle2,
  AlertTriangle, XCircle, RefreshCw, Trash2, Plus, Edit3,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { toast } from "sonner";

interface KeyResult {
  id: string;
  title: string;
  target_value: number;
  current_value: number;
  unit: string | null;
  status: string;
  progress_pct: number;
}

interface Objective {
  id: string;
  title: string;
  description: string | null;
  level: string;
  department: string | null;
  status: string;
  period_label: string | null;
  progress_pct: number;
  child_count: number;
  key_results: KeyResult[];
  children?: Objective[];
}

interface OkrSummary {
  overall_progress_pct: number;
  total_objectives: number;
  by_level: Record<string, { count: number; avg_progress: number }>;
}

const LEVEL_COLORS: Record<string, string> = {
  company:    "bg-blue-100 text-blue-700 border-blue-200",
  department: "bg-purple-100 text-purple-700 border-purple-200",
  individual: "bg-green-100 text-green-700 border-green-200",
};

const KR_STATUS_CONFIG: Record<string, { color: string; icon: React.ElementType }> = {
  on_track:  { color: "text-green-600",  icon: CheckCircle2  },
  at_risk:   { color: "text-amber-500",  icon: AlertTriangle },
  off_track: { color: "text-red-500",    icon: XCircle       },
  completed: { color: "text-blue-600",   icon: CheckCircle2  },
};

const CURRENT_QUARTER = (() => {
  const now = new Date();
  return `Q${Math.ceil((now.getMonth() + 1) / 3)} ${now.getFullYear()}`;
})();

export default function OkrPage() {
  const router = useRouter();
  const params = useParams<{ locale: string }>();
  const locale = params?.locale ?? "en";
  const supabase = createClient();

  const [objectives, setObjectives] = useState<Objective[]>([]);
  const [summary, setSummary] = useState<OkrSummary | null>(null);
  const [period, setPeriod] = useState(CURRENT_QUARTER);
  const [loading, setLoading] = useState(true);
  const [expanded, setExpanded] = useState<Set<string>>(new Set());

  // New objective form
  const [showNewObj, setShowNewObj] = useState(false);
  const [newObj, setNewObj] = useState({
    title: "", level: "company", department: "",
    period_label: CURRENT_QUARTER, parent_id: "" as string,
  });

  // New KR form
  const [showNewKr, setShowNewKr] = useState<string | null>(null);
  const [newKr, setNewKr] = useState({ title: "", target_value: "", unit: "", current_value: "" });

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

      const [objRes, sumRes] = await Promise.all([
        fetch(apiUrl(`/api/okr/objectives?status=active`), { headers: { Authorization: `Bearer ${token}` } }),
        fetch(apiUrl(`/api/okr/progress/${encodeURIComponent(period)}`), { headers: { Authorization: `Bearer ${token}` } }),
      ]);

      if (objRes.status === 401 || sumRes.status === 401) { router.push(`/${locale}/auth/login`); return; }
      if (objRes.ok) setObjectives(await objRes.json());
      if (sumRes.ok) setSummary(await sumRes.json());
    } catch {
      toast.error("Failed to load OKRs");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { load(); }, [period]);  // eslint-disable-line react-hooks/exhaustive-deps

  async function createObjective() {
    if (!newObj.title.trim()) { toast.error("Title is required"); return; }
    try {
      const token = await getToken();
      if (!token) return;
      const res = await fetch(apiUrl("/api/okr/objectives"), {
        method: "POST",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
        body: JSON.stringify({
          title: newObj.title,
          level: newObj.level,
          department: newObj.department || null,
          period_label: newObj.period_label || null,
          parent_id: newObj.parent_id || null,
        }),
      });
      if (!res.ok) {
        const b = await res.json().catch(() => ({}));
        toast.error(b.detail ?? "Failed to create objective");
        return;
      }
      toast.success("Objective created");
      setShowNewObj(false);
      setNewObj({ title: "", level: "company", department: "", period_label: CURRENT_QUARTER, parent_id: "" });
      await load();
    } catch {
      toast.error("Something went wrong");
    }
  }

  async function addKeyResult(objId: string) {
    if (!newKr.title.trim() || !newKr.target_value) { toast.error("Title and target are required"); return; }
    try {
      const token = await getToken();
      if (!token) return;
      const res = await fetch(apiUrl(`/api/okr/objectives/${objId}/key-results`), {
        method: "POST",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
        body: JSON.stringify({
          title: newKr.title,
          target_value: parseFloat(newKr.target_value),
          current_value: parseFloat(newKr.current_value) || 0,
          unit: newKr.unit || null,
        }),
      });
      if (!res.ok) {
        const b = await res.json().catch(() => ({}));
        toast.error(b.detail ?? "Failed to add key result");
        return;
      }
      toast.success("Key result added");
      setShowNewKr(null);
      setNewKr({ title: "", target_value: "", unit: "", current_value: "" });
      await load();
    } catch {
      toast.error("Something went wrong");
    }
  }

  async function updateKrProgress(krId: string, val: string) {
    const parsed = parseFloat(val);
    if (isNaN(parsed)) return;
    try {
      const token = await getToken();
      if (!token) return;
      await fetch(apiUrl(`/api/okr/key-results/${krId}`), {
        method: "PATCH",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
        body: JSON.stringify({ current_value: parsed }),
      });
      await load();
    } catch {}
  }

  async function deleteObjective(id: string) {
    try {
      const token = await getToken();
      if (!token) return;
      await fetch(apiUrl(`/api/okr/objectives/${id}`), {
        method: "DELETE",
        headers: { Authorization: `Bearer ${token}` },
      });
      await load();
    } catch {}
  }

  function toggle(id: string) {
    setExpanded((prev) => {
      const next = new Set(prev);
      next.has(id) ? next.delete(id) : next.add(id);
      return next;
    });
  }

  const scoreColor = (p: number) => p >= 70 ? "text-green-600" : p >= 40 ? "text-amber-500" : "text-red-500";
  const barColor   = (p: number) => p >= 70 ? "bg-green-500" : p >= 40 ? "bg-amber-400" : "bg-red-400";

  return (
    <div className="mx-auto max-w-4xl space-y-6 p-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-gray-900">OKRs — Objectives & Key Results</h1>
          <p className="text-sm text-muted-foreground mt-0.5">
            Cascade goals from company → department → individual.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <input
            value={period}
            onChange={(e) => setPeriod(e.target.value)}
            placeholder="Q1 2025"
            className="rounded-md border border-gray-300 px-3 py-1.5 text-sm w-28 focus:outline-none focus:ring-1 focus:ring-[#1a2332]"
          />
          <Button onClick={() => setShowNewObj(true)} className="bg-[#1a2332] hover:bg-[#2a3342] text-white gap-2">
            <PlusCircle className="h-4 w-4" /> Add Objective
          </Button>
        </div>
      </div>

      {/* Summary card */}
      {summary && (
        <div className="grid grid-cols-1 sm:grid-cols-4 gap-4">
          <div className="sm:col-span-2 rounded-xl border bg-white p-5 shadow-sm">
            <p className="text-sm text-muted-foreground">Overall Progress</p>
            <p className={`text-3xl font-bold ${scoreColor(summary.overall_progress_pct)}`}>
              {summary.overall_progress_pct.toFixed(0)}%
            </p>
            <div className="mt-2 h-2 w-full rounded-full bg-gray-100 overflow-hidden">
              <div className={`h-full rounded-full transition-all ${barColor(summary.overall_progress_pct)}`}
                style={{ width: `${summary.overall_progress_pct}%` }} />
            </div>
            <p className="mt-1 text-xs text-muted-foreground">{summary.total_objectives} objectives · {period}</p>
          </div>
          {Object.entries(summary.by_level).map(([lvl, data]) => (
            <div key={lvl} className="rounded-xl border bg-white p-5 shadow-sm">
              <p className="text-xs text-muted-foreground capitalize">{lvl}</p>
              <p className={`text-2xl font-bold ${scoreColor(data.avg_progress)}`}>
                {data.avg_progress.toFixed(0)}%
              </p>
              <p className="text-xs text-muted-foreground">{data.count} objectives</p>
            </div>
          ))}
        </div>
      )}

      {/* New objective form */}
      {showNewObj && (
        <div className="rounded-xl border border-[#1a2332]/20 bg-white p-5 shadow-sm space-y-3">
          <h3 className="text-sm font-semibold text-gray-900">New Objective</h3>
          <input
            placeholder="Objective title *"
            value={newObj.title}
            onChange={(e) => setNewObj((f) => ({ ...f, title: e.target.value }))}
            className="block w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-[#1a2332]"
          />
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            <select value={newObj.level} onChange={(e) => setNewObj((f) => ({ ...f, level: e.target.value }))}
              className="rounded-md border border-gray-300 px-2 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-[#1a2332]">
              <option value="company">Company</option>
              <option value="department">Department</option>
              <option value="individual">Individual</option>
            </select>
            <input placeholder="Department" value={newObj.department}
              onChange={(e) => setNewObj((f) => ({ ...f, department: e.target.value }))}
              className="rounded-md border border-gray-300 px-2 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-[#1a2332]" />
            <input placeholder="Period label" value={newObj.period_label}
              onChange={(e) => setNewObj((f) => ({ ...f, period_label: e.target.value }))}
              className="rounded-md border border-gray-300 px-2 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-[#1a2332]" />
            <select value={newObj.parent_id}
              onChange={(e) => setNewObj((f) => ({ ...f, parent_id: e.target.value }))}
              className="rounded-md border border-gray-300 px-2 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-[#1a2332]">
              <option value="">No parent</option>
              {objectives.filter((o) => o.level !== "individual").map((o) => (
                <option key={o.id} value={o.id}>{o.title.slice(0, 40)}</option>
              ))}
            </select>
          </div>
          <div className="flex gap-2">
            <Button variant="outline" onClick={() => setShowNewObj(false)}>Cancel</Button>
            <Button onClick={createObjective} className="bg-[#1a2332] hover:bg-[#2a3342] text-white">
              Create
            </Button>
          </div>
        </div>
      )}

      {/* Objectives list */}
      {loading && objectives.length === 0
        ? <div className="text-center py-12 text-muted-foreground">Loading…</div>
        : objectives.length === 0
        ? (
          <div className="rounded-xl border bg-white p-12 text-center shadow-sm">
            <Target className="h-10 w-10 text-muted-foreground mx-auto mb-3" />
            <p className="text-gray-600 font-medium">No objectives for {period}</p>
            <p className="text-sm text-muted-foreground mt-1">Create your first company objective to get started.</p>
          </div>
        )
        : (
          <div className="space-y-3">
            {objectives.map((obj) => (
              <ObjectiveCard
                key={obj.id}
                obj={obj}
                expanded={expanded.has(obj.id)}
                onToggle={() => toggle(obj.id)}
                onDelete={() => deleteObjective(obj.id)}
                onAddKr={() => { setShowNewKr(obj.id); setNewKr({ title: "", target_value: "", unit: "", current_value: "" }); }}
                onUpdateKrProgress={updateKrProgress}
                showNewKrForm={showNewKr === obj.id}
                newKr={newKr}
                setNewKr={setNewKr}
                onSaveKr={() => addKeyResult(obj.id)}
                onCancelKr={() => setShowNewKr(null)}
              />
            ))}
          </div>
        )}
    </div>
  );
}

function ProgressBar({ value, className = "" }: { value: number; className?: string }) {
  const color = value >= 70 ? "bg-green-500" : value >= 40 ? "bg-amber-400" : "bg-red-400";
  return (
    <div className={`h-1.5 w-full rounded-full bg-gray-100 overflow-hidden ${className}`}>
      <div className={`h-full rounded-full transition-all ${color}`} style={{ width: `${Math.min(value, 100)}%` }} />
    </div>
  );
}

function ObjectiveCard({
  obj, expanded, onToggle, onDelete, onAddKr,
  onUpdateKrProgress, showNewKrForm, newKr, setNewKr, onSaveKr, onCancelKr,
}: {
  obj: Objective;
  expanded: boolean;
  onToggle: () => void;
  onDelete: () => void;
  onAddKr: () => void;
  onUpdateKrProgress: (krId: string, val: string) => void;
  showNewKrForm: boolean;
  newKr: { title: string; target_value: string; unit: string; current_value: string };
  setNewKr: React.Dispatch<React.SetStateAction<typeof newKr>>;
  onSaveKr: () => void;
  onCancelKr: () => void;
}) {
  const levelClass = LEVEL_COLORS[obj.level] ?? "bg-gray-100 text-gray-600";

  return (
    <div className="rounded-xl border bg-white shadow-sm overflow-hidden">
      <div
        className="flex items-center gap-3 px-5 py-4 cursor-pointer hover:bg-gray-50 transition-colors"
        onClick={onToggle}
      >
        <div className="flex-shrink-0">
          {expanded
            ? <ChevronDown className="h-4 w-4 text-muted-foreground" />
            : <ChevronRight className="h-4 w-4 text-muted-foreground" />}
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <span className={`rounded-full border px-2 py-0.5 text-xs font-medium capitalize ${levelClass}`}>
              {obj.level}
            </span>
            {obj.department && (
              <span className="text-xs text-muted-foreground">{obj.department}</span>
            )}
            {obj.period_label && (
              <span className="text-xs text-muted-foreground">· {obj.period_label}</span>
            )}
          </div>
          <p className="text-sm font-medium text-gray-900 truncate">{obj.title}</p>
          <ProgressBar value={obj.progress_pct} className="mt-2 max-w-xs" />
        </div>
        <div className="flex-shrink-0 text-right">
          <p className="text-lg font-bold text-gray-900">{obj.progress_pct.toFixed(0)}%</p>
          <p className="text-xs text-muted-foreground">{obj.key_results.length} KRs</p>
        </div>
        <button
          type="button"
          onClick={(e) => { e.stopPropagation(); onDelete(); }}
          className="flex-shrink-0 text-muted-foreground hover:text-red-600 transition-colors p-1"
        >
          <Trash2 className="h-4 w-4" />
        </button>
      </div>

      {expanded && (
        <div className="border-t bg-gray-50 px-5 py-4 space-y-3">
          {obj.key_results.length === 0 && !showNewKrForm && (
            <p className="text-sm text-muted-foreground">No key results yet.</p>
          )}
          {obj.key_results.map((kr) => {
            const cfg = KR_STATUS_CONFIG[kr.status] ?? KR_STATUS_CONFIG.on_track;
            const Icon = cfg.icon;
            return (
              <div key={kr.id} className="flex items-center gap-3 rounded-lg bg-white border px-4 py-3">
                <Icon className={`h-4 w-4 flex-shrink-0 ${cfg.color}`} />
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium text-gray-800 truncate">{kr.title}</p>
                  <ProgressBar value={kr.progress_pct} className="mt-1.5 max-w-xs" />
                </div>
                <div className="flex items-center gap-2 flex-shrink-0">
                  <input
                    type="number"
                    defaultValue={kr.current_value}
                    onBlur={(e) => onUpdateKrProgress(kr.id, e.target.value)}
                    className="w-20 rounded border border-gray-300 px-2 py-1 text-xs focus:outline-none focus:ring-1 focus:ring-[#1a2332]"
                  />
                  <span className="text-xs text-muted-foreground">/ {kr.target_value} {kr.unit ?? ""}</span>
                </div>
              </div>
            );
          })}

          {showNewKrForm ? (
            <div className="rounded-lg border bg-white p-4 space-y-2">
              <input placeholder="Key result title *" value={newKr.title}
                onChange={(e) => setNewKr((f) => ({ ...f, title: e.target.value }))}
                className="block w-full rounded-md border border-gray-300 px-3 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-[#1a2332]" />
              <div className="grid grid-cols-3 gap-2">
                <input placeholder="Target" type="number" value={newKr.target_value}
                  onChange={(e) => setNewKr((f) => ({ ...f, target_value: e.target.value }))}
                  className="rounded-md border border-gray-300 px-2 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-[#1a2332]" />
                <input placeholder="Current (opt)" type="number" value={newKr.current_value}
                  onChange={(e) => setNewKr((f) => ({ ...f, current_value: e.target.value }))}
                  className="rounded-md border border-gray-300 px-2 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-[#1a2332]" />
                <input placeholder="Unit (%, SEK…)" value={newKr.unit}
                  onChange={(e) => setNewKr((f) => ({ ...f, unit: e.target.value }))}
                  className="rounded-md border border-gray-300 px-2 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-[#1a2332]" />
              </div>
              <div className="flex gap-2">
                <Button variant="outline" size="sm" onClick={onCancelKr}>Cancel</Button>
                <Button size="sm" className="bg-[#1a2332] hover:bg-[#2a3342] text-white" onClick={onSaveKr}>
                  Add Key Result
                </Button>
              </div>
            </div>
          ) : (
            <button type="button" onClick={onAddKr}
              className="flex items-center gap-2 text-sm text-[#1a2332] hover:text-[#2a3342] font-medium">
              <Plus className="h-4 w-4" /> Add Key Result
            </button>
          )}
        </div>
      )}
    </div>
  );
}
