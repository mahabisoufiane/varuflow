"use client";
import { useState, useEffect, useCallback } from "react";
import { toast } from "sonner";
import { api } from "@/lib/api-client";
import { ClipboardList, Plus, X, Check, LayoutGrid, List, AlertCircle, MessageSquare, ChevronRight } from "lucide-react";
import styles from "./page.module.scss";

interface Staff { id: string; name: string; }
interface TaskComment { id: string; staff_id: string | null; body: string; created_at: string; }
interface Task {
  id: string; title: string; description: string | null;
  assignee_id: string | null; status: string; priority: string;
  due_date: string | null; completed_at: string | null;
  is_overdue: boolean; is_recurring: boolean; recurrence_rule: string | null;
  parent_task_id: string | null;
  subtasks?: Task[]; comments?: TaskComment[];
  created_at: string | null;
}

const STATUSES = ["todo", "in_progress", "blocked", "done"] as const;
type Status = typeof STATUSES[number];
const STATUS_LABELS: Record<Status, string> = { todo: "To Do", in_progress: "In Progress", blocked: "Blocked", done: "Done" };
const STATUS_COLORS: Record<Status, string> = {
  todo: "bg-gray-100 text-gray-600",
  in_progress: "bg-blue-100 text-blue-700",
  blocked: "bg-orange-100 text-orange-800",
  done: "bg-green-100 text-green-700",
};
const STATUS_MODULE: Record<Status, keyof typeof styles> = {
  todo:        "statusTodo",
  in_progress: "statusInProgress",
  blocked:     "statusBlocked",
  done:        "statusDone",
};
const KANBAN_BG: Record<Status, string> = { todo: "bg-gray-50", in_progress: "bg-blue-50", blocked: "bg-orange-50", done: "bg-green-50" };
const PRIORITY_COLORS: Record<string, string> = {
  low: "bg-gray-200 text-gray-500",
  medium: "bg-amber-100 text-amber-700",
  high: "bg-red-100 text-red-700",
  urgent: "bg-red-200 text-red-900 font-semibold",
};
const PRIORITY_MODULE: Record<string, keyof typeof styles> = {
  low:    "priorityLow",
  medium: "priorityMedium",
  high:   "priorityHigh",
  urgent: "priorityUrgent",
};

function SubtaskInput({ onAdd }: { onAdd: (title: string) => void }) {
  const [val, setVal] = useState("");
  return (
    <div className="flex gap-2 mt-1">
      <input className="input flex-1 text-sm" placeholder="Subtask title…" value={val} onChange={e => setVal(e.target.value)}
        onKeyDown={e => { if (e.key === "Enter" && val.trim()) { onAdd(val); setVal(""); } }} />
      <button onClick={() => { if (val.trim()) { onAdd(val); setVal(""); } }} className="btn-primary text-sm px-3">Add</button>
    </div>
  );
}

export default function TasksPage() {
  const [tasks, setTasks] = useState<Task[]>([]);
  const [staff, setStaff] = useState<Staff[]>([]);
  const [loading, setLoading] = useState(true);
  const [view, setView] = useState<"list" | "board">("list");
  const [tab, setTab] = useState<"all" | "my" | "overdue">("all");
  const [filterAssignee, setFilterAssignee] = useState("");
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState({ title: "", description: "", assignee_id: "", priority: "medium", due_date: "", status: "todo", is_recurring: false, recurrence_rule: "" });
  const [selected, setSelected] = useState<Task | null>(null);
  const [commentBody, setCommentBody] = useState("");
  const [showSubtaskInput, setShowSubtaskInput] = useState(false);

  const load = useCallback(async () => {
    const params = new URLSearchParams();
    if (filterAssignee) params.set("assignee_id", filterAssignee);
    const endpoint = tab === "my" ? "/api/work/tasks/my"
      : tab === "overdue" ? "/api/work/tasks?overdue=true"
      : `/api/work/tasks${params.size ? "?" + params : ""}`;
    const [t, s] = await Promise.all([
      api.get<Task[]>(endpoint).catch(() => []),
      api.get<Staff[]>("/api/hr/employees").catch(() => []),
    ]);
    setTasks(t); setStaff(s); setLoading(false);
  }, [tab, filterAssignee]);

  useEffect(() => { load(); }, [load]);

  const staffMap = Object.fromEntries(staff.map(s => [s.id, s.name]));

  async function createTask() {
    if (!form.title.trim()) { toast.error("Title required"); return; }
    const body = { ...form, assignee_id: form.assignee_id || null, due_date: form.due_date || null, recurrence_rule: form.is_recurring ? form.recurrence_rule || null : null, description: form.description || null };
    await api.post("/api/work/tasks", body);
    toast.success("Task created");
    setShowForm(false);
    setForm({ title: "", description: "", assignee_id: "", priority: "medium", due_date: "", status: "todo", is_recurring: false, recurrence_rule: "" });
    load();
  }

  async function updateStatus(id: string, status: string) {
    await api.patch(`/api/work/tasks/${id}`, { status });
    if (selected?.id === id) setSelected(prev => prev ? { ...prev, status } : null);
    setTasks(prev => prev.map(t => t.id === id ? { ...t, status } : t));
  }

  async function deleteTask(id: string) {
    try {
      await api.delete(`/api/work/tasks/${id}`);
      setTasks(prev => prev.filter(t => t.id !== id));
      if (selected?.id === id) setSelected(null);
    } catch {
      toast.error("Failed to delete task");
    }
  }

  async function openDetail(task: Task) {
    const detail = await api.get<Task>(`/api/work/tasks/${task.id}`).catch(() => task);
    setSelected(detail);
    setShowSubtaskInput(false);
  }

  async function sendComment() {
    if (!commentBody.trim() || !selected) return;
    await api.post(`/api/work/tasks/${selected.id}/comments`, { body: commentBody });
    setCommentBody("");
    const detail = await api.get<Task>(`/api/work/tasks/${selected.id}`).catch(() => selected);
    setSelected(detail);
  }

  async function addSubtask(title: string) {
    if (!selected) return;
    await api.post("/api/work/tasks", { title, parent_task_id: selected.id, priority: "medium", status: "todo" });
    const detail = await api.get<Task>(`/api/work/tasks/${selected.id}`).catch(() => selected);
    setSelected(detail);
    load();
  }

  if (loading) return <div className="animate-pulse space-y-4">{[1,2,3].map(i => <div key={i} className="h-16 rounded-xl bg-gray-100" />)}</div>;

  const byStatus = (status: Status) => tasks.filter(t => t.status === status);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <h1 className="text-2xl font-semibold text-gray-900">Tasks</h1>
          <p className="text-sm text-gray-500 mt-0.5">Assign and track work across your team.</p>
        </div>
        <div className="flex items-center gap-2">
          <button onClick={() => setView(v => v === "list" ? "board" : "list")} className="btn-secondary flex items-center gap-1.5 text-sm">
            {view === "list" ? <><LayoutGrid className="h-4 w-4" /> Board</> : <><List className="h-4 w-4" /> List</>}
          </button>
          <button onClick={() => setShowForm(true)} className="btn-primary flex items-center gap-2"><Plus className="h-4 w-4" /> New Task</button>
        </div>
      </div>

      {showForm && (
        <div className="rounded-xl border border-blue-200 bg-blue-50 p-5 space-y-3">
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div className="sm:col-span-2">
              <input className="input w-full" placeholder="Task title…" value={form.title} onChange={e => setForm(p => ({ ...p, title: e.target.value }))} />
            </div>
            <div className="sm:col-span-2">
              <textarea className="input w-full h-16 resize-none" placeholder="Description (optional)…" value={form.description} onChange={e => setForm(p => ({ ...p, description: e.target.value }))} />
            </div>
            <select className="input" value={form.assignee_id} onChange={e => setForm(p => ({ ...p, assignee_id: e.target.value }))}>
              <option value="">Unassigned</option>
              {staff.map(s => <option key={s.id} value={s.id}>{s.name}</option>)}
            </select>
            <select className="input" value={form.priority} onChange={e => setForm(p => ({ ...p, priority: e.target.value }))}>
              {["low","medium","high","urgent"].map(p => <option key={p} value={p}>{p.charAt(0).toUpperCase()+p.slice(1)}</option>)}
            </select>
            <input className="input" type="date" value={form.due_date} onChange={e => setForm(p => ({ ...p, due_date: e.target.value }))} />
            <select className="input" value={form.status} onChange={e => setForm(p => ({ ...p, status: e.target.value }))}>
              {STATUSES.map(s => <option key={s} value={s}>{STATUS_LABELS[s]}</option>)}
            </select>
          </div>
          <label className="flex items-center gap-2 text-sm text-gray-700 cursor-pointer">
            <input type="checkbox" checked={form.is_recurring} onChange={e => setForm(p => ({ ...p, is_recurring: e.target.checked }))} />
            Recurring task
            {form.is_recurring && (
              <select className="input ml-2 text-sm" value={form.recurrence_rule} onChange={e => setForm(p => ({ ...p, recurrence_rule: e.target.value }))}>
                <option value="">— frequency —</option>
                <option value="daily">Daily</option>
                <option value="weekly">Weekly</option>
                <option value="monthly">Monthly</option>
              </select>
            )}
          </label>
          <div className="flex gap-2">
            <button onClick={createTask} className="btn-primary text-sm">Create</button>
            <button onClick={() => setShowForm(false)} className="btn-secondary text-sm">Cancel</button>
          </div>
        </div>
      )}

      <div className="flex items-center gap-3 flex-wrap">
        <div className="flex gap-1">
          {(["all","my","overdue"] as const).map(t => (
            <button key={t} onClick={() => setTab(t)}
              className={`px-3 py-1.5 rounded-lg text-sm font-medium ${tab === t ? "bg-[var(--vf-brand-primary)] text-white" : "bg-gray-100 text-gray-600 hover:bg-gray-200"}`}>
              {t === "all" ? "All" : t === "my" ? "My Tasks" : "⚠ Overdue"}
            </button>
          ))}
        </div>
        {tab === "all" && (
          <select className="input text-sm w-40" value={filterAssignee} onChange={e => setFilterAssignee(e.target.value)}>
            <option value="">All assignees</option>
            {staff.map(s => <option key={s.id} value={s.id}>{s.name}</option>)}
          </select>
        )}
      </div>

      {tasks.length === 0 && !showForm && (
        <div className="text-center py-12 text-gray-400">
          <ClipboardList className="h-10 w-10 mx-auto mb-3 opacity-40" />
          <p>No tasks{tab === "overdue" ? " overdue" : tab === "my" ? " assigned to you" : ""}.</p>
        </div>
      )}

      {/* BOARD */}
      {view === "board" && tasks.length > 0 && (
        <div className="grid grid-cols-4 gap-4 min-w-0 overflow-x-auto">
          {STATUSES.map(col => (
            <div key={col} className={`rounded-xl ${KANBAN_BG[col]} p-3 min-h-[200px]`}>
              <div className="flex items-center justify-between mb-3">
                <span className={styles[STATUS_MODULE[col]]}>{STATUS_LABELS[col]}</span>
                <span className="text-xs text-gray-400">{byStatus(col).length}</span>
              </div>
              <div className="space-y-2">
                {byStatus(col).map(task => (
                  <button key={task.id} onClick={() => openDetail(task)}
                    className={`w-full text-left bg-white border rounded-lg p-3 shadow-sm hover:shadow-md transition-shadow ${task.is_overdue ? "border-red-300" : ""}`}>
                    <div className="flex items-start justify-between gap-1">
                      <span className="text-sm font-medium text-gray-900 line-clamp-2">{task.title}</span>
                      {task.is_overdue && <AlertCircle className="h-3.5 w-3.5 text-red-500 flex-shrink-0 mt-0.5" />}
                    </div>
                    <div className="flex items-center gap-1.5 mt-2 flex-wrap">
                      <span className={styles[PRIORITY_MODULE[task.priority] ?? "priorityMedium"]}>{task.priority}</span>
                      {task.assignee_id && <span className="text-xs text-gray-500">{(staffMap[task.assignee_id] || "?").split(" ")[0]}</span>}
                      {task.due_date && <span className="text-xs text-gray-400">{task.due_date}</span>}
                    </div>
                  </button>
                ))}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* LIST */}
      {view === "list" && tasks.length > 0 && (
        <div className="space-y-2">
          {tasks.map(task => (
            <div key={task.id} onClick={() => openDetail(task)}
              className={`rounded-xl border bg-white p-4 flex items-center gap-4 cursor-pointer hover:border-gray-300 transition-colors ${task.is_overdue ? "border-red-200 bg-red-50/30" : ""}`}>
              <button onClick={e => { e.stopPropagation(); updateStatus(task.id, task.status === "done" ? "todo" : "done"); }}
                className={`w-5 h-5 rounded flex items-center justify-center flex-shrink-0 ${task.status === "done" ? "bg-green-500" : "border-2 border-gray-300 hover:border-green-400"}`}>
                {task.status === "done" && <Check className="h-3 w-3 text-white" />}
              </button>
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 flex-wrap">
                  <span className={`font-medium text-gray-900 ${task.status === "done" ? "line-through text-gray-400" : ""}`}>{task.title}</span>
                  <span className={styles[PRIORITY_MODULE[task.priority] ?? "priorityMedium"]}>{task.priority}</span>
                  <span className={styles[STATUS_MODULE[task.status as Status] ?? "statusTodo"]}>{STATUS_LABELS[task.status as Status] || task.status}</span>
                  {task.is_overdue && <span className="text-xs text-red-600 font-medium flex items-center gap-0.5"><AlertCircle className="h-3 w-3" /> Overdue</span>}
                  {task.is_recurring && <span className="text-xs text-indigo-600">↻ {task.recurrence_rule}</span>}
                </div>
                <div className="flex gap-3 text-xs text-gray-500 mt-0.5">
                  {task.assignee_id && <span>{staffMap[task.assignee_id] || "Unknown"}</span>}
                  {task.due_date && <span>Due {task.due_date}</span>}
                </div>
              </div>
              <button onClick={e => { e.stopPropagation(); deleteTask(task.id); }} className="p-1.5 rounded-lg hover:bg-red-50 text-gray-400 hover:text-red-500 flex-shrink-0">
                <X className="h-4 w-4" />
              </button>
            </div>
          ))}
        </div>
      )}

      {/* DETAIL DRAWER */}
      {selected && (
        <div className="fixed inset-0 z-50 flex" onClick={() => setSelected(null)}>
          <div className="flex-1 bg-black/30" />
          <div className="w-full max-w-lg bg-white shadow-2xl overflow-y-auto" onClick={e => e.stopPropagation()}>
            <div className="p-6 space-y-5">
              <div className="flex items-start justify-between gap-3">
                <div>
                  <h2 className="text-xl font-bold text-gray-900">{selected.title}</h2>
                  <div className="flex items-center gap-2 mt-1 flex-wrap">
                    <span className={styles[STATUS_MODULE[selected.status as Status] ?? "statusTodo"]}>{STATUS_LABELS[selected.status as Status] || selected.status}</span>
                    <span className={styles[PRIORITY_MODULE[selected.priority] ?? "priorityMedium"]}>{selected.priority}</span>
                    {selected.is_overdue && <span className="text-xs text-red-600 font-medium">⚠ Overdue</span>}
                  </div>
                </div>
                <button onClick={() => setSelected(null)} className="text-gray-400 hover:text-gray-600"><X className="h-5 w-5" /></button>
              </div>

              <div className="grid grid-cols-2 gap-3 text-sm">
                <div>
                  <p className="text-xs text-gray-500 mb-1">Assignee</p>
                  <select className="input text-sm w-full" value={selected.assignee_id || ""} onChange={async e => {
                    await api.patch(`/api/work/tasks/${selected.id}`, { assignee_id: e.target.value || null });
                    setSelected(prev => prev ? { ...prev, assignee_id: e.target.value || null } : null);
                    load();
                  }}>
                    <option value="">Unassigned</option>
                    {staff.map(s => <option key={s.id} value={s.id}>{s.name}</option>)}
                  </select>
                </div>
                <div>
                  <p className="text-xs text-gray-500 mb-1">Status</p>
                  <select className="input text-sm w-full" value={selected.status} onChange={e => updateStatus(selected.id, e.target.value)}>
                    {STATUSES.map(s => <option key={s} value={s}>{STATUS_LABELS[s]}</option>)}
                  </select>
                </div>
                <div>
                  <p className="text-xs text-gray-500 mb-1">Priority</p>
                  <select className="input text-sm w-full" value={selected.priority} onChange={async e => {
                    await api.patch(`/api/work/tasks/${selected.id}`, { priority: e.target.value });
                    setSelected(prev => prev ? { ...prev, priority: e.target.value } : null);
                  }}>
                    {["low","medium","high","urgent"].map(p => <option key={p} value={p}>{p}</option>)}
                  </select>
                </div>
                <div>
                  <p className="text-xs text-gray-500 mb-1">Due date</p>
                  <input type="date" className="input text-sm w-full" value={selected.due_date || ""} onChange={async e => {
                    await api.patch(`/api/work/tasks/${selected.id}`, { due_date: e.target.value || null });
                    setSelected(prev => prev ? { ...prev, due_date: e.target.value || null } : null);
                  }} />
                </div>
              </div>

              {selected.description && (
                <div>
                  <p className="text-xs text-gray-500 mb-1">Description</p>
                  <p className="text-sm text-gray-700 whitespace-pre-wrap bg-gray-50 rounded-lg p-3">{selected.description}</p>
                </div>
              )}

              {/* Subtasks */}
              <div>
                <div className="flex items-center justify-between mb-2">
                  <p className="text-sm font-semibold text-gray-700">Subtasks ({(selected.subtasks || []).length})</p>
                  <button onClick={() => setShowSubtaskInput(v => !v)} className="text-xs text-indigo-600 hover:underline flex items-center gap-0.5">
                    + Add <ChevronRight className="h-3 w-3" />
                  </button>
                </div>
                <div className="space-y-1 mb-2">
                  {(selected.subtasks || []).map(sub => (
                    <div key={sub.id} className="flex items-center gap-2 text-sm bg-gray-50 rounded px-3 py-2">
                      <button onClick={() => updateStatus(sub.id, sub.status === "done" ? "todo" : "done")}
                        className={`w-4 h-4 rounded flex items-center justify-center flex-shrink-0 ${sub.status === "done" ? "bg-green-500" : "border border-gray-400"}`}>
                        {sub.status === "done" && <Check className="h-2.5 w-2.5 text-white" />}
                      </button>
                      <span className={sub.status === "done" ? "line-through text-gray-400" : "text-gray-700"}>{sub.title}</span>
                    </div>
                  ))}
                </div>
                {showSubtaskInput && <SubtaskInput onAdd={addSubtask} />}
              </div>

              {/* Comments */}
              <div>
                <p className="text-sm font-semibold text-gray-700 mb-2 flex items-center gap-1.5">
                  <MessageSquare className="h-4 w-4" /> Comments ({(selected.comments || []).length})
                </p>
                <div className="space-y-2 mb-3 max-h-48 overflow-y-auto">
                  {(selected.comments || []).map(c => (
                    <div key={c.id} className="bg-gray-50 rounded-lg px-3 py-2 text-sm">
                      <div className="text-xs text-gray-400 mb-0.5">{new Date(c.created_at).toLocaleString()}</div>
                      <p className="text-gray-800">{c.body}</p>
                    </div>
                  ))}
                  {(selected.comments || []).length === 0 && <p className="text-xs text-gray-400">No comments yet.</p>}
                </div>
                <div className="flex gap-2">
                  <input className="input flex-1 text-sm" placeholder="Add a comment…" value={commentBody}
                    onChange={e => setCommentBody(e.target.value)} onKeyDown={e => e.key === "Enter" && sendComment()} />
                  <button onClick={sendComment} className="btn-primary text-sm px-3">Post</button>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
