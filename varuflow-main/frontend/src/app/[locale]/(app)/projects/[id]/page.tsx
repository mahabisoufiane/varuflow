"use client";

import { useEffect, useState } from "react";
import { FolderKanban, Plus, Loader2, Trash2, CheckCircle, Circle, ArrowLeft, Flag } from "lucide-react";
import { useRouter } from "next/navigation";
import { useLocale } from "next-intl";
import { toast } from "sonner";
import { api } from "@/lib/api-client";
import { isPlanGateError, PlanGateBlock } from "@/components/ui/PlanGate";

interface Task {
  id: string;
  title: string;
  description: string | null;
  assignee_name: string | null;
  status: string;
  priority: string;
  due_date: string | null;
  completed_at: string | null;
}

interface Milestone {
  id: string;
  title: string;
  due_date: string | null;
  completed_at: string | null;
}

interface Expense {
  id: string;
  description: string;
  amount: number;
  currency: string;
  incurred_date: string;
}

interface Project {
  id: string;
  name: string;
  description: string | null;
  customer_name: string | null;
  status: string;
  project_type: string;
  budget: number | null;
  default_hourly_rate: number | null;
  start_date: string | null;
  end_date: string | null;
  tasks: Task[];
  milestones: Milestone[];
  expenses: Expense[];
}

const PRIORITY_COLOR: Record<string, string> = {
  high: "text-red-500",
  medium: "text-yellow-500",
  low: "text-blue-400",
};

const TASK_STATUSES = ["todo", "in_progress", "done"] as const;

export default function ProjectDetailPage({ params }: { params: { id: string } }) {
  const router = useRouter();
  const locale = useLocale();
  const [project, setProject] = useState<Project | null>(null);
  const [loading, setLoading] = useState(true);
  const [tab, setTab] = useState<"tasks" | "milestones" | "expenses">("tasks");
  const [showTaskForm, setShowTaskForm] = useState(false);
  const [taskForm, setTaskForm] = useState({ title: "", assignee_name: "", priority: "medium", due_date: "", status: "todo" });
  const [showMsForm, setShowMsForm] = useState(false);
  const [msForm, setMsForm] = useState({ title: "", due_date: "" });
  const [showExpForm, setShowExpForm] = useState(false);
  const [expForm, setExpForm] = useState({ description: "", amount: "", currency: "SEK", incurred_date: new Date().toISOString().slice(0, 10) });
  const [planBlocked, setPlanBlocked] = useState<{ module: string; currentPlan: string } | null>(null);

  useEffect(() => {
    api.get(`/api/projects/${params.id}`)
      .then(setProject)
      .catch((err) => {
        if (isPlanGateError(err)) {
          setPlanBlocked({ module: (err as any).module ?? "hr", currentPlan: (err as any).currentPlan ?? "FREE" });
          return;
        }
        toast.error("Failed to load project");
      })
      .finally(() => setLoading(false));
  }, [params.id]);

  async function addTask() {
    if (!taskForm.title) { toast.error("Enter a title"); return; }
    try {
      const t = await api.post(`/api/projects/${params.id}/tasks`, {
        title: taskForm.title,
        assignee_name: taskForm.assignee_name || undefined,
        priority: taskForm.priority,
        due_date: taskForm.due_date || undefined,
        status: taskForm.status,
      });
      setProject((p) => p ? { ...p, tasks: [...p.tasks, t] } : p);
      setTaskForm({ title: "", assignee_name: "", priority: "medium", due_date: "", status: "todo" });
      setShowTaskForm(false);
      toast.success("Task added");
    } catch { toast.error("Failed to add task"); }
  }

  async function toggleTask(task: Task) {
    const newStatus = task.status === "done" ? "todo" : "done";
    try {
      const updated = await api.patch(`/api/projects/${params.id}/tasks/${task.id}`, { status: newStatus });
      setProject((p) => p ? { ...p, tasks: p.tasks.map((t) => t.id === task.id ? { ...t, ...updated } : t) } : p);
    } catch { toast.error("Failed to update task"); }
  }

  async function deleteTask(id: string) {
    try {
      await api.delete(`/api/projects/${params.id}/tasks/${id}`);
      setProject((p) => p ? { ...p, tasks: p.tasks.filter((t) => t.id !== id) } : p);
      toast.success("Task deleted");
    } catch { toast.error("Failed to delete"); }
  }

  async function addMilestone() {
    if (!msForm.title) { toast.error("Enter a title"); return; }
    try {
      const m = await api.post(`/api/projects/${params.id}/milestones`, { title: msForm.title, due_date: msForm.due_date || undefined });
      setProject((p) => p ? { ...p, milestones: [...p.milestones, m] } : p);
      setMsForm({ title: "", due_date: "" });
      setShowMsForm(false);
      toast.success("Milestone added");
    } catch { toast.error("Failed to add milestone"); }
  }

  async function completeMilestone(m: Milestone) {
    const completed_at = m.completed_at ? null : new Date().toISOString();
    try {
      const updated = await api.patch(`/api/projects/${params.id}/milestones/${m.id}`, { completed_at });
      setProject((p) => p ? { ...p, milestones: p.milestones.map((x) => x.id === m.id ? { ...x, ...updated } : x) } : p);
    } catch { toast.error("Failed to update milestone"); }
  }

  async function deleteMilestone(id: string) {
    try {
      await api.delete(`/api/projects/${params.id}/milestones/${id}`);
      setProject((p) => p ? { ...p, milestones: p.milestones.filter((x) => x.id !== id) } : p);
    } catch { toast.error("Failed to delete"); }
  }

  async function addExpense() {
    if (!expForm.description || !expForm.amount) { toast.error("Fill in description and amount"); return; }
    try {
      const e = await api.post(`/api/projects/${params.id}/expenses`, {
        description: expForm.description, amount: parseFloat(expForm.amount),
        currency: expForm.currency, incurred_date: expForm.incurred_date,
      });
      setProject((p) => p ? { ...p, expenses: [...p.expenses, e] } : p);
      setExpForm({ description: "", amount: "", currency: "SEK", incurred_date: new Date().toISOString().slice(0, 10) });
      setShowExpForm(false);
      toast.success("Expense added");
    } catch { toast.error("Failed to add expense"); }
  }

  async function deleteExpense(id: string) {
    try {
      await api.delete(`/api/projects/${params.id}/expenses/${id}`);
      setProject((p) => p ? { ...p, expenses: p.expenses.filter((x) => x.id !== id) } : p);
    } catch { toast.error("Failed to delete"); }
  }

  if (loading) return <div className="flex items-center justify-center h-64"><Loader2 className="w-6 h-6 animate-spin" /></div>;
  if (planBlocked) return <PlanGateBlock module={planBlocked.module} currentPlan={planBlocked.currentPlan} featureName="Projects" />;
  if (!project) return <div className="p-6"><p className="text-muted-foreground">Project not found.</p></div>;

  const openTasks = project.tasks.filter((t) => t.status !== "done");
  const doneTasks = project.tasks.filter((t) => t.status === "done");
  const totalExpenses = project.expenses.reduce((s, e) => s + e.amount, 0);

  return (
    <div className="p-6 max-w-5xl mx-auto">
      <button onClick={() => router.push(`/${locale}/projects`)} className="flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground mb-4">
        <ArrowLeft className="w-4 h-4" /> Projects
      </button>

      <div className="mb-6">
        <div className="flex items-start justify-between">
          <div>
            <h1 className="text-2xl font-semibold">{project.name}</h1>
            {project.customer_name && <p className="text-sm text-muted-foreground">{project.customer_name}</p>}
            {project.description && <p className="text-sm text-muted-foreground mt-1">{project.description}</p>}
          </div>
          <div className="text-right text-sm space-y-0.5">
            {project.budget && <p className="text-muted-foreground">Budget: <span className="font-medium text-foreground">{project.budget.toLocaleString()} SEK</span></p>}
            {project.end_date && <p className="text-muted-foreground">Due: <span className="font-medium text-foreground">{project.end_date}</span></p>}
            <button onClick={() => router.push(`/${locale}/projects/pl?project_id=${project.id}`)} className="text-xs text-primary underline">View P&L</button>
          </div>
        </div>
        <div className="flex gap-3 mt-3 text-xs text-muted-foreground">
          <span>{openTasks.length} open tasks</span>
          <span>{doneTasks.length} done</span>
          <span>{project.milestones.length} milestones</span>
          <span>{totalExpenses.toLocaleString()} SEK expenses</span>
        </div>
      </div>

      <div className="flex gap-1 mb-4 border-b">
        {(["tasks", "milestones", "expenses"] as const).map((t) => (
          <button key={t} onClick={() => setTab(t)} className={`px-4 py-2 text-sm font-medium capitalize transition-colors ${tab === t ? "border-b-2 border-primary text-primary" : "text-muted-foreground hover:text-foreground"}`}>
            {t} {t === "tasks" ? `(${project.tasks.length})` : t === "milestones" ? `(${project.milestones.length})` : `(${project.expenses.length})`}
          </button>
        ))}
      </div>

      {tab === "tasks" && (
        <div>
          <div className="flex justify-end mb-3">
            <button onClick={() => setShowTaskForm((x) => !x)} className="flex items-center gap-1 text-xs border rounded px-2 py-1 hover:bg-accent">
              <Plus className="w-3 h-3" /> Add Task
            </button>
          </div>
          {showTaskForm && (
            <div className="border rounded p-3 mb-4 grid grid-cols-3 gap-2">
              <div className="col-span-3">
                <input className="border rounded px-2 py-1.5 text-sm w-full" placeholder="Task title" value={taskForm.title} onChange={(e) => setTaskForm((f) => ({ ...f, title: e.target.value }))} onKeyDown={(e) => e.key === "Enter" && addTask()} />
              </div>
              <input placeholder="Assignee" className="border rounded px-2 py-1 text-xs" value={taskForm.assignee_name} onChange={(e) => setTaskForm((f) => ({ ...f, assignee_name: e.target.value }))} />
              <select className="border rounded px-2 py-1 text-xs" value={taskForm.priority} onChange={(e) => setTaskForm((f) => ({ ...f, priority: e.target.value }))}>
                <option value="low">Low</option>
                <option value="medium">Medium</option>
                <option value="high">High</option>
              </select>
              <input type="date" className="border rounded px-2 py-1 text-xs" value={taskForm.due_date} onChange={(e) => setTaskForm((f) => ({ ...f, due_date: e.target.value }))} />
              <div className="col-span-3 flex gap-1">
                <button onClick={addTask} className="bg-primary text-primary-foreground rounded px-2 py-1 text-xs">Add</button>
                <button onClick={() => setShowTaskForm(false)} className="border rounded px-2 py-1 text-xs">×</button>
              </div>
            </div>
          )}
          {TASK_STATUSES.map((status) => {
            const group = project.tasks.filter((t) => t.status === status);
            if (group.length === 0 && status === "done") return null;
            return (
              <div key={status} className="mb-4">
                <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground mb-2">{status.replace("_", " ")} ({group.length})</p>
                <div className="space-y-1.5">
                  {group.map((task) => (
                    <div key={task.id} className="flex items-center gap-2 border rounded-lg p-2.5">
                      <button onClick={() => toggleTask(task)} className="shrink-0">
                        {task.status === "done" ? <CheckCircle className="w-4 h-4 text-green-500" /> : <Circle className="w-4 h-4 text-muted-foreground" />}
                      </button>
                      <div className="flex-1 min-w-0">
                        <p className={`text-sm ${task.status === "done" ? "line-through text-muted-foreground" : ""}`}>{task.title}</p>
                        {(task.assignee_name || task.due_date) && (
                          <p className="text-xs text-muted-foreground">{task.assignee_name}{task.assignee_name && task.due_date ? " · " : ""}{task.due_date}</p>
                        )}
                      </div>
                      <Flag className={`w-3 h-3 shrink-0 ${PRIORITY_COLOR[task.priority]}`} />
                      <button onClick={() => deleteTask(task.id)} className="text-muted-foreground hover:text-destructive"><Trash2 className="w-3 h-3" /></button>
                    </div>
                  ))}
                </div>
              </div>
            );
          })}
          {project.tasks.length === 0 && <p className="text-sm text-muted-foreground">No tasks yet.</p>}
        </div>
      )}

      {tab === "milestones" && (
        <div>
          <div className="flex justify-end mb-3">
            <button onClick={() => setShowMsForm((x) => !x)} className="flex items-center gap-1 text-xs border rounded px-2 py-1 hover:bg-accent">
              <Plus className="w-3 h-3" /> Add Milestone
            </button>
          </div>
          {showMsForm && (
            <div className="flex gap-2 mb-4 border rounded p-3">
              <input className="border rounded px-2 py-1.5 text-sm flex-1" placeholder="Milestone title" value={msForm.title} onChange={(e) => setMsForm((f) => ({ ...f, title: e.target.value }))} />
              <input type="date" className="border rounded px-2 py-1.5 text-sm" value={msForm.due_date} onChange={(e) => setMsForm((f) => ({ ...f, due_date: e.target.value }))} />
              <button onClick={addMilestone} className="bg-primary text-primary-foreground rounded px-3 py-1.5 text-sm">Add</button>
              <button onClick={() => setShowMsForm(false)} className="border rounded px-3 py-1.5 text-sm">×</button>
            </div>
          )}
          <div className="space-y-2">
            {project.milestones.map((m) => (
              <div key={m.id} className="flex items-center gap-3 border rounded-lg p-3">
                <button onClick={() => completeMilestone(m)}>
                  {m.completed_at ? <CheckCircle className="w-4 h-4 text-green-500" /> : <Circle className="w-4 h-4 text-muted-foreground" />}
                </button>
                <div className="flex-1">
                  <p className={`text-sm font-medium ${m.completed_at ? "line-through text-muted-foreground" : ""}`}>{m.title}</p>
                  {m.due_date && <p className="text-xs text-muted-foreground">{m.due_date}</p>}
                </div>
                <button onClick={() => deleteMilestone(m.id)} className="text-muted-foreground hover:text-destructive"><Trash2 className="w-3 h-3" /></button>
              </div>
            ))}
            {project.milestones.length === 0 && <p className="text-sm text-muted-foreground">No milestones yet.</p>}
          </div>
        </div>
      )}

      {tab === "expenses" && (
        <div>
          <div className="flex items-center justify-between mb-3">
            <p className="text-sm text-muted-foreground">Total: <span className="font-semibold text-foreground">{totalExpenses.toLocaleString()} SEK</span></p>
            <button onClick={() => setShowExpForm((x) => !x)} className="flex items-center gap-1 text-xs border rounded px-2 py-1 hover:bg-accent">
              <Plus className="w-3 h-3" /> Add Expense
            </button>
          </div>
          {showExpForm && (
            <div className="border rounded p-3 mb-4 grid grid-cols-2 gap-2">
              <div className="col-span-2">
                <input className="border rounded px-2 py-1.5 text-sm w-full" placeholder="Description" value={expForm.description} onChange={(e) => setExpForm((f) => ({ ...f, description: e.target.value }))} />
              </div>
              <input type="number" step="100" placeholder="Amount" className="border rounded px-2 py-1.5 text-xs" value={expForm.amount} onChange={(e) => setExpForm((f) => ({ ...f, amount: e.target.value }))} />
              <input type="date" className="border rounded px-2 py-1.5 text-xs" value={expForm.incurred_date} onChange={(e) => setExpForm((f) => ({ ...f, incurred_date: e.target.value }))} />
              <div className="col-span-2 flex gap-1">
                <button onClick={addExpense} className="bg-primary text-primary-foreground rounded px-2 py-1 text-xs">Add</button>
                <button onClick={() => setShowExpForm(false)} className="border rounded px-2 py-1 text-xs">×</button>
              </div>
            </div>
          )}
          <table className="w-full text-sm">
            <thead><tr className="border-b text-muted-foreground"><th className="py-2 text-left pr-4 font-medium">Description</th><th className="py-2 text-left pr-4 font-medium">Date</th><th className="py-2 text-right pr-4 font-medium">Amount</th><th /></tr></thead>
            <tbody className="divide-y">
              {project.expenses.map((e) => (
                <tr key={e.id}>
                  <td className="py-2 pr-4">{e.description}</td>
                  <td className="py-2 pr-4 text-muted-foreground">{e.incurred_date}</td>
                  <td className="py-2 pr-4 text-right font-medium">{e.amount.toLocaleString()} {e.currency}</td>
                  <td className="py-2"><button onClick={() => deleteExpense(e.id)} className="text-muted-foreground hover:text-destructive"><Trash2 className="w-3 h-3" /></button></td>
                </tr>
              ))}
            </tbody>
          </table>
          {project.expenses.length === 0 && <p className="text-sm text-muted-foreground mt-2">No expenses yet.</p>}
        </div>
      )}
    </div>
  );
}
