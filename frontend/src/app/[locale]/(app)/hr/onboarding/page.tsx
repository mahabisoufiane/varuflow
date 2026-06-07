"use client";

import { useState, useEffect } from "react";
import { toast } from "sonner";
import { api } from "@/lib/api-client";
import { CheckSquare, Plus, RefreshCw, X, Check, ChevronRight, Settings, User } from "lucide-react";
import styles from "./page.module.scss";

interface Staff { id: string; name: string; role?: string }
interface Task {
  id: string; staff_id: string; title: string; category: string;
  description: string | null; is_done: boolean; done_at: string | null;
  due_days_after_start: number | null; sort_order: number;
}
interface Summary { staff_id: string; staff_name: string; total: number; done: number; completion_pct: number }

const CAT_COLORS: Record<string, string> = {
  it_setup: "bg-blue-100 text-blue-700", access: "bg-indigo-100 text-indigo-700",
  hr_admin: "bg-green-100 text-green-700", equipment: "bg-amber-100 text-amber-700",
  intro: "bg-purple-100 text-purple-700", compliance: "bg-red-100 text-red-700",
  general: "bg-gray-100 text-gray-600",
};

const CAT_MODULE: Record<string, keyof typeof styles> = {
  it_setup:   "catItSetup",
  access:     "catAccess",
  hr_admin:   "catHrAdmin",
  equipment:  "catEquipment",
  intro:      "catIntro",
  compliance: "catCompliance",
  general:    "catGeneral",
};

const CAT_LABELS: Record<string, string> = {
  it_setup: "IT Setup", access: "Access", hr_admin: "HR Admin",
  equipment: "Equipment", intro: "Introduction", compliance: "Compliance", general: "General",
};

function ProgressBar({ pct }: { pct: number }) {
  const color = pct === 100 ? "bg-green-500" : pct >= 50 ? "bg-blue-500" : "bg-amber-400";
  return (
    <div className="flex items-center gap-2">
      <div className="flex-1 h-2 bg-gray-100 rounded-full overflow-hidden">
        <div className={`h-full rounded-full ${color} transition-all`} style={{ width: `${pct}%` }} />
      </div>
      <span className="text-xs font-semibold text-gray-600 w-10 text-right">{Math.round(pct)}%</span>
    </div>
  );
}

export default function OnboardingPage() {
  const [staff, setStaff] = useState<Staff[]>([]);
  const [summary, setSummary] = useState<Summary[]>([]);
  const [tasks, setTasks] = useState<Task[]>([]);
  const [template, setTemplate] = useState<any[]>([]);
  const [selectedStaff, setSelectedStaff] = useState<string | null>(null);
  const [tab, setTab] = useState<"employees" | "template">("employees");
  const [loading, setLoading] = useState(true);
  const [newTaskTitle, setNewTaskTitle] = useState("");
  const [newTaskCat, setNewTaskCat] = useState("general");
  const [showAddTask, setShowAddTask] = useState(false);

  async function load() {
    const [emps, summ, templ] = await Promise.all([
      api.get<any[]>("/api/hr/employees").catch(() => []),
      api.get<Summary[]>("/api/hr/onboarding/summary").catch(() => []),
      api.get<any[]>("/api/hr/onboarding/template").catch(() => []),
    ]);
    setStaff(emps as Staff[]);
    setSummary(summ as Summary[]);
    setTemplate(templ as any[]);
    setLoading(false);
  }

  useEffect(() => { load(); }, []);

  async function selectEmployee(staffId: string) {
    setSelectedStaff(staffId);
    const data = await api.get<Task[]>(`/api/hr/onboarding/${staffId}`).catch(() => []);
    setTasks(data as Task[]);
  }

  async function initFromTemplate() {
    if (!selectedStaff) return;
    try {
      const { created } = await api.post<{ created: number }>(`/api/hr/onboarding/${selectedStaff}/from-template`, {});
      toast.success(`${created} tasks created from template`);
      const data = await api.get<Task[]>(`/api/hr/onboarding/${selectedStaff}`).catch(() => []);
      setTasks(data as Task[]);
      load();
    } catch { toast.error("Failed"); }
  }

  async function toggleTask(task: Task) {
    try {
      const updated = await api.patch<Task>(`/api/hr/onboarding/${task.staff_id}/${task.id}`, { is_done: !task.is_done });
      setTasks(prev => prev.map(t => t.id === task.id ? updated : t));
      load();
    } catch { toast.error("Failed"); }
  }

  async function addTask() {
    if (!selectedStaff || !newTaskTitle.trim()) return;
    try {
      const created = await api.post<Task>(`/api/hr/onboarding/${selectedStaff}`, { title: newTaskTitle, category: newTaskCat });
      setTasks(prev => [...prev, created]);
      setNewTaskTitle("");
      setShowAddTask(false);
      load();
    } catch { toast.error("Failed"); }
  }

  async function deleteTask(task: Task) {
    await api.delete(`/api/hr/onboarding/${task.staff_id}/${task.id}`).catch(() => {});
    setTasks(prev => prev.filter(t => t.id !== task.id));
    load();
  }

  async function addTemplateItem() {
    if (!newTaskTitle.trim()) return;
    try {
      const created = await api.post<any>("/api/hr/onboarding/template", { title: newTaskTitle, category: newTaskCat });
      setTemplate(prev => [...prev, created]);
      setNewTaskTitle("");
      toast.success("Template item added");
    } catch { toast.error("Failed"); }
  }

  const byCategory = tasks.reduce((acc, t) => {
    (acc[t.category] = acc[t.category] || []).push(t);
    return acc;
  }, {} as Record<string, Task[]>);

  const selectedSummary = summary.find(s => s.staff_id === selectedStaff);
  const selectedStaffRecord = staff.find(s => s.id === selectedStaff);

  if (loading) return <div className="animate-pulse space-y-4">{[1,2,3].map(i => <div key={i} className="h-20 rounded-xl bg-gray-100" />)}</div>;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold text-gray-900">Employee Onboarding</h1>
        <p className="mt-1 text-sm text-gray-500">Per-hire checklists to track every step from day 1 to full onboarding completion.</p>
      </div>

      {/* Tabs */}
      <div className="flex gap-2 border-b border-gray-200">
        {(["employees", "template"] as const).map(t => (
          <button key={t} onClick={() => { setTab(t); setSelectedStaff(null); }}
            className={`px-4 py-2 text-sm font-medium capitalize border-b-2 -mb-px transition-all ${
              tab === t ? "border-blue-500 text-blue-600" : "border-transparent text-gray-500 hover:text-gray-700"
            }`}>{t === "template" ? <><Settings className="h-3.5 w-3.5 inline mr-1.5" />Template</> : "Employees"}</button>
        ))}
      </div>

      {/* Employees tab */}
      {tab === "employees" && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Staff list */}
          <div className="space-y-2">
            <p className="text-xs font-semibold text-gray-500 uppercase">Staff members</p>
            {staff.length === 0 && <p className="text-sm text-gray-400 py-4">No staff found.</p>}
            {staff.map(s => {
              const sum = summary.find(x => x.staff_id === s.id);
              return (
                <button key={s.id} onClick={() => selectEmployee(s.id)}
                  className={`w-full rounded-xl border p-3.5 text-left transition-all ${
                    selectedStaff === s.id ? "border-blue-400 bg-blue-50" : "border-gray-200 bg-white hover:border-gray-300"
                  }`}>
                  <div className="flex items-center gap-2 mb-1.5">
                    <User className="h-4 w-4 text-gray-400 flex-shrink-0" />
                    <span className="font-medium text-gray-900 text-sm">{s.name}</span>
                    <ChevronRight className="h-3.5 w-3.5 text-gray-400 ml-auto flex-shrink-0" />
                  </div>
                  {sum ? (
                    <ProgressBar pct={sum.completion_pct} />
                  ) : (
                    <p className="text-xs text-gray-400">No checklist yet</p>
                  )}
                </button>
              );
            })}
          </div>

          {/* Task list */}
          {selectedStaff && (
            <div className="lg:col-span-2 space-y-4">
              <div className="flex items-center justify-between">
                <div>
                  <h2 className="font-semibold text-gray-900">{selectedStaffRecord?.name || "Employee"}</h2>
                  {selectedSummary && (
                    <p className="text-sm text-gray-500">{selectedSummary.done}/{selectedSummary.total} tasks complete · {Math.round(selectedSummary.completion_pct)}%</p>
                  )}
                </div>
                <div className="flex gap-2">
                  {tasks.length === 0 && (
                    <button onClick={initFromTemplate} className="text-sm px-3 py-1.5 rounded-lg bg-blue-100 text-blue-700 hover:bg-blue-200 flex items-center gap-1.5">
                      <RefreshCw className="h-3.5 w-3.5" /> Load template
                    </button>
                  )}
                  <button onClick={() => setShowAddTask(v => !v)} className="text-sm px-3 py-1.5 rounded-lg bg-gray-100 text-gray-700 hover:bg-gray-200 flex items-center gap-1.5">
                    <Plus className="h-3.5 w-3.5" /> Add task
                  </button>
                </div>
              </div>

              {showAddTask && (
                <div className="flex gap-2">
                  <input className="input flex-1 text-sm" placeholder="Task title…" value={newTaskTitle} onChange={e => setNewTaskTitle(e.target.value)} onKeyDown={e => e.key === "Enter" && addTask()} />
                  <select className="input text-sm w-36" value={newTaskCat} onChange={e => setNewTaskCat(e.target.value)}>
                    {Object.entries(CAT_LABELS).map(([v, l]) => <option key={v} value={v}>{l}</option>)}
                  </select>
                  <button onClick={addTask} className="px-3 py-1.5 rounded-lg bg-blue-500 text-white text-sm hover:bg-blue-600">Add</button>
                </div>
              )}

              {tasks.length === 0 && (
                <div className="text-center py-10 text-gray-400">
                  <CheckSquare className="h-8 w-8 mx-auto mb-2 opacity-40" />
                  <p className="text-sm">No tasks yet. Load the template to get started.</p>
                </div>
              )}

              {Object.entries(byCategory).map(([cat, catTasks]) => (
                <div key={cat} className="rounded-xl border border-gray-200 bg-white overflow-hidden">
                  <div className="bg-gray-50 px-4 py-2 border-b border-gray-100 flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <span className={styles[CAT_MODULE[cat] ?? "catGeneral"]}>{CAT_LABELS[cat] || cat}</span>
                      <span className="text-xs text-gray-400">{catTasks.filter(t => t.is_done).length}/{catTasks.length}</span>
                    </div>
                  </div>
                  <div className="divide-y divide-gray-50">
                    {catTasks.map(task => (
                      <div key={task.id} className="flex items-center gap-3 px-4 py-3">
                        <button
                          onClick={() => toggleTask(task)}
                          className={`w-5 h-5 rounded flex items-center justify-center flex-shrink-0 transition-all ${
                            task.is_done ? "bg-green-500" : "border-2 border-gray-300"
                          }`}
                        >
                          {task.is_done && <Check className="h-3 w-3 text-white" />}
                        </button>
                        <div className="flex-1 min-w-0">
                          <p className={`text-sm ${task.is_done ? "line-through text-gray-400" : "text-gray-800"}`}>{task.title}</p>
                          {task.due_days_after_start && !task.is_done && (
                            <p className="text-xs text-gray-400">Due: day {task.due_days_after_start} after start</p>
                          )}
                          {task.done_at && (
                            <p className="text-xs text-green-600">Completed {new Date(task.done_at).toLocaleDateString("sv-SE")}</p>
                          )}
                        </div>
                        <button onClick={() => deleteTask(task)} className="p-1 rounded hover:bg-red-50 text-gray-300 hover:text-red-400 flex-shrink-0">
                          <X className="h-3.5 w-3.5" />
                        </button>
                      </div>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Template tab */}
      {tab === "template" && (
        <div className="space-y-4 max-w-2xl">
          <p className="text-sm text-gray-600">These tasks are automatically applied when you click "Load template" for a new hire. Customise to match your company's onboarding process.</p>

          <div className="flex gap-2">
            <input className="input flex-1 text-sm" placeholder="New template task…" value={newTaskTitle} onChange={e => setNewTaskTitle(e.target.value)} onKeyDown={e => e.key === "Enter" && addTemplateItem()} />
            <select className="input text-sm w-36" value={newTaskCat} onChange={e => setNewTaskCat(e.target.value)}>
              {Object.entries(CAT_LABELS).map(([v, l]) => <option key={v} value={v}>{l}</option>)}
            </select>
            <button onClick={addTemplateItem} className="px-3 py-1.5 rounded-lg bg-blue-500 text-white text-sm hover:bg-blue-600 flex items-center gap-1.5">
              <Plus className="h-3.5 w-3.5" /> Add
            </button>
          </div>

          <div className="rounded-xl border border-gray-200 bg-white divide-y divide-gray-50">
            {template.map((item, i) => (
              <div key={item.id || i} className="flex items-center gap-3 px-4 py-3">
                <div className="w-5 h-5 rounded border-2 border-gray-200 flex-shrink-0" />
                <div className="flex-1 min-w-0">
                  <p className="text-sm text-gray-800">{item.title}</p>
                  {item.due_days_after_start && (
                    <p className="text-xs text-gray-400">Target: day {item.due_days_after_start}</p>
                  )}
                </div>
                <span className={styles[CAT_MODULE[item.category] ?? "catGeneral"]}>{CAT_LABELS[item.category] || item.category}</span>
                {item.id && (
                  <button onClick={async () => {
                    await api.delete(`/api/hr/onboarding/template/${item.id}`).catch(() => {});
                    setTemplate(prev => prev.filter((t: any) => t.id !== item.id));
                  }} className="p-1 rounded hover:bg-red-50 text-gray-300 hover:text-red-400 flex-shrink-0">
                    <X className="h-3.5 w-3.5" />
                  </button>
                )}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
