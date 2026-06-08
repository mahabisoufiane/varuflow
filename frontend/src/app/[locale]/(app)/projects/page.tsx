"use client";

import { useEffect, useState } from "react";
import { FolderKanban, Plus, Loader2, ChevronRight } from "lucide-react";
import { useRouter } from "next/navigation";
import { useLocale } from "next-intl";
import { toast } from "sonner";
import { api } from "@/lib/api-client";
import { isPlanGateError, PlanGateBlock } from "@/components/ui/PlanGate";
import styles from "./page.module.scss";

interface Project {
  id: string;
  name: string;
  description: string | null;
  customer_id: string | null;
  customer_name: string | null;
  status: string;
  project_type: string;
  budget: number | null;
  default_hourly_rate: number | null;
  start_date: string | null;
  end_date: string | null;
  created_at: string;
}

interface Customer {
  id: string;
  company_name: string;
}

const STATUS_BADGE: Record<string, string> = {
  active: "bg-green-100 text-green-800",
  on_hold: "bg-yellow-100 text-yellow-800",
  completed: "bg-blue-100 text-blue-800",
  cancelled: "bg-red-100 text-red-800",
};

const STATUS_MODULE_CLASS: Record<string, keyof typeof styles> = {
  active: "badgeActive",
  on_hold: "badgeOnHold",
  completed: "badgeCompleted",
  cancelled: "badgeCancelled",
};

const TYPE_LABELS: Record<string, string> = {
  time_material: "T&M",
  fixed: "Fixed",
  retainer: "Retainer",
};

export default function ProjectsPage() {
  const router = useRouter();
  const locale = useLocale();
  const [projects, setProjects] = useState<Project[]>([]);
  const [customers, setCustomers] = useState<Customer[]>([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [planBlocked, setPlanBlocked] = useState<{ module: string; currentPlan: string } | null>(null);
  const [form, setForm] = useState({
    name: "", description: "", customer_id: "", status: "active",
    project_type: "time_material", budget: "", default_hourly_rate: "",
    start_date: "", end_date: "",
  });

  useEffect(() => {
    Promise.all([
      api.get("/api/projects"),
      api.get("/api/inventory/customers?limit=500").catch(() => ({ items: [] })),
    ]).then(([projs, custs]) => {
      setProjects(projs);
      setCustomers(custs.items ?? custs ?? []);
    }).catch((err) => {
      if (isPlanGateError(err)) {
        setPlanBlocked({ module: (err as any).module ?? "hr", currentPlan: (err as any).currentPlan ?? "FREE" });
        return;
      }
      toast.error("Failed to load projects");
    }).finally(() => setLoading(false));
  }, []);

  async function create() {
    if (!form.name) { toast.error("Enter a project name"); return; }
    try {
      const body: Record<string, unknown> = {
        name: form.name, description: form.description || undefined,
        customer_id: form.customer_id || undefined,
        status: form.status, project_type: form.project_type,
        budget: form.budget ? parseFloat(form.budget) : undefined,
        default_hourly_rate: form.default_hourly_rate ? parseFloat(form.default_hourly_rate) : undefined,
        start_date: form.start_date || undefined,
        end_date: form.end_date || undefined,
      };
      const created = await api.post("/api/projects", body);
      setProjects((p) => [created, ...p]);
      setShowForm(false);
      toast.success("Project created");
      router.push(`/${locale}/projects/${created.id}`);
    } catch { toast.error("Failed to create project"); }
  }

  const byStatus = (s: string) => projects.filter((p) => p.status === s);

  if (planBlocked) return <PlanGateBlock module={planBlocked.module} currentPlan={planBlocked.currentPlan} featureName="Projects" />;

  return (
    <div className="p-6 max-w-7xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-2">
          <FolderKanban className="w-6 h-6" />
          <h1 className="text-2xl font-semibold">Projects</h1>
        </div>
        <button onClick={() => setShowForm((x) => !x)} className="flex items-center gap-1.5 bg-primary text-primary-foreground rounded px-3 py-1.5 text-sm">
          <Plus className="w-4 h-4" /> New Project
        </button>
      </div>

      {showForm && (
        <div className={styles.formCard}>
          <div className="col-span-2">
            <label className={styles.formLabel}>Project Name</label>
            <input className={styles.formInput} value={form.name} onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))} />
          </div>
          <div className="col-span-2">
            <label className={styles.formLabel}>Description</label>
            <textarea className={`${styles.formInput} resize-none`} rows={2} value={form.description} onChange={(e) => setForm((f) => ({ ...f, description: e.target.value }))} />
          </div>
          <div>
            <label className={styles.formLabel}>Customer</label>
            <select className={styles.formInput} value={form.customer_id} onChange={(e) => setForm((f) => ({ ...f, customer_id: e.target.value }))}>
              <option value="">— none —</option>
              {customers.map((c) => <option key={c.id} value={c.id}>{c.company_name}</option>)}
            </select>
          </div>
          <div>
            <label className={styles.formLabel}>Type</label>
            <select className={styles.formInput} value={form.project_type} onChange={(e) => setForm((f) => ({ ...f, project_type: e.target.value }))}>
              <option value="time_material">Time & Material</option>
              <option value="fixed">Fixed Price</option>
              <option value="retainer">Retainer</option>
            </select>
          </div>
          <div>
            <label className={styles.formLabel}>Budget (SEK)</label>
            <input type="number" step="1000" className={styles.formInput} value={form.budget} onChange={(e) => setForm((f) => ({ ...f, budget: e.target.value }))} />
          </div>
          <div>
            <label className={styles.formLabel}>Default Hourly Rate</label>
            <input type="number" step="50" className={styles.formInput} value={form.default_hourly_rate} onChange={(e) => setForm((f) => ({ ...f, default_hourly_rate: e.target.value }))} />
          </div>
          <div>
            <label className={styles.formLabel}>Start Date</label>
            <input type="date" className={styles.formInput} value={form.start_date} onChange={(e) => setForm((f) => ({ ...f, start_date: e.target.value }))} />
          </div>
          <div>
            <label className={styles.formLabel}>End Date</label>
            <input type="date" className={styles.formInput} value={form.end_date} onChange={(e) => setForm((f) => ({ ...f, end_date: e.target.value }))} />
          </div>
          <div className="col-span-2 flex gap-2">
            <button onClick={create} className="bg-primary text-primary-foreground rounded px-3 py-1.5 text-sm">Create</button>
            <button onClick={() => setShowForm(false)} className="border rounded px-3 py-1.5 text-sm">Cancel</button>
          </div>
        </div>
      )}

      {loading ? (
        <div className="flex items-center justify-center h-40"><Loader2 className="w-6 h-6 animate-spin" /></div>
      ) : projects.length === 0 ? (
        <p className="text-sm text-muted-foreground">No projects yet. Create your first project to get started.</p>
      ) : (
        <div className={styles.kanbanGrid}>
          {["active", "on_hold", "completed"].map((status) => (
            <div key={status}>
              <p className={styles.columnHeader}>
                {status.replace("_", " ")} ({byStatus(status).length})
              </p>
              <div className="space-y-3">
                {byStatus(status).map((p) => (
                  <button key={p.id} onClick={() => router.push(`/${locale}/projects/${p.id}`)} className={styles.projectCard}>
                    <div className="flex items-start justify-between mb-1">
                      <p className="font-medium text-sm leading-tight">{p.name}</p>
                      <span className={`${styles.typeBadge} ${styles[STATUS_MODULE_CLASS[p.status] ?? "badgeActive"]}`}>{TYPE_LABELS[p.project_type] ?? p.project_type}</span>
                    </div>
                    {p.customer_name && <p className="text-xs text-muted-foreground">{p.customer_name}</p>}
                    {p.budget && <p className="text-xs text-muted-foreground mt-1">Budget: {p.budget.toLocaleString()} SEK</p>}
                    <div className="flex items-center justify-between mt-2">
                      {p.end_date && <p className="text-xs text-muted-foreground">Due {p.end_date}</p>}
                      <ChevronRight className="w-3 h-3 text-muted-foreground ml-auto" />
                    </div>
                  </button>
                ))}
                {byStatus(status).length === 0 && <p className="text-xs text-muted-foreground">None</p>}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
