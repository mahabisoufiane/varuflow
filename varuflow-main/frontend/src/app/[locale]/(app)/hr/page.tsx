"use client";

import { useEffect, useState } from "react";
import { Users2, Plus, Loader2, Search, X } from "lucide-react";
import { useRouter } from "next/navigation";
import { useLocale } from "next-intl";
import { toast } from "sonner";
import { api } from "@/lib/api-client";
import { isPlanGateError, PlanGateBlock } from "@/components/ui/PlanGate";
import { RoleGuard } from "@/components/app/RoleContext";
import styles from "./page.module.scss";

interface Employee {
  id: string;
  name: string;
  email: string | null;
  profile: {
    job_title: string | null;
    employment_type: string;
    department: string | null;
    status: string;
    start_date: string | null;
  } | null;
}

const TYPE_LABELS: Record<string, string> = {
  full_time: "Full-time",
  part_time: "Part-time",
  contractor: "Contractor",
  intern: "Intern",
};

const STATUS_STYLE: Record<string, string> = {
  active: "bg-emerald-100 text-emerald-700",
  on_leave: "bg-amber-100 text-amber-700",
  terminated: "bg-rose-100 text-rose-700",
};

const DEPARTMENTS = [
  "Engineering", "Sales", "Finance", "HR", "Operations",
  "Marketing", "Customer Success", "Management",
];

// Employee directory is manager-level data — mirrors require_role(ADMIN) on the
// /api/hr/employees router. Regular employees use self-service HR pages instead.
export default function HrPage() {
  return (
    <RoleGuard minRole="ADMIN">
      <HrPageInner />
    </RoleGuard>
  );
}

function HrPageInner() {
  const router = useRouter();
  const locale = useLocale();
  const [employees, setEmployees] = useState<Employee[]>([]);
  const [loading, setLoading] = useState(true);
  const [planBlocked, setPlanBlocked] = useState<{ module: string; currentPlan: string } | null>(null);
  const [search, setSearch] = useState("");
  const [filterStatus, setFilterStatus] = useState("");
  const [filterDept, setFilterDept] = useState("");
  const [showAddModal, setShowAddModal] = useState(false);
  const [addForm, setAddForm] = useState({ name: "", email: "", role: "STAFF" });
  const [adding, setAdding] = useState(false);

  function loadEmployees() {
    setLoading(true);
    const params = new URLSearchParams();
    if (filterStatus) params.set("status", filterStatus);
    if (filterDept) params.set("department", filterDept);
    const qs = params.toString();
    api.get(`/api/hr/employees${qs ? "?" + qs : ""}`)
      .then(setEmployees)
      .catch((err) => {
        if (isPlanGateError(err)) {
          setPlanBlocked({ module: (err as any).module ?? "hr", currentPlan: (err as any).currentPlan ?? "FREE" });
        } else {
          toast.error("Failed to load employees");
        }
      })
      .finally(() => setLoading(false));
  }

  useEffect(() => { loadEmployees(); }, [filterStatus, filterDept]); // eslint-disable-line react-hooks/exhaustive-deps

  const filtered = employees.filter((e) =>
    e.name.toLowerCase().includes(search.toLowerCase()) ||
    (e.profile?.job_title ?? "").toLowerCase().includes(search.toLowerCase()) ||
    (e.profile?.department ?? "").toLowerCase().includes(search.toLowerCase())
  );

  async function handleAddEmployee() {
    if (!addForm.name.trim()) { toast.error("Name is required"); return; }
    setAdding(true);
    try {
      await api.post("/api/team/members", addForm);
      toast.success("Employee added");
      setShowAddModal(false);
      setAddForm({ name: "", email: "", role: "STAFF" });
      loadEmployees();
    } catch {
      toast.error("Failed to add employee");
    } finally {
      setAdding(false);
    }
  }

  if (planBlocked) {
    return <PlanGateBlock module={planBlocked.module} currentPlan={planBlocked.currentPlan} featureName="HR & People" />;
  }

  return (
    <div className="vf-section">
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-2">
          <Users2 className="w-5 h-5 text-vf-accent" />
          <h1 className="vf-text-1 text-xl font-semibold">Employees</h1>
        </div>
        <button onClick={() => setShowAddModal(true)} className="vf-btn flex items-center gap-1.5">
          <Plus className="w-4 h-4" /> Add Employee
        </button>
      </div>

      {/* Filters row */}
      <div className="flex flex-wrap gap-2 mb-4">
        <div className="relative">
          <Search className="absolute left-3 top-2.5 w-4 h-4 text-muted-foreground" />
          <input
            className="vf-input pl-9 w-60"
            placeholder="Search employees…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>
        <select className="vf-input w-36" value={filterStatus} onChange={(e) => setFilterStatus(e.target.value)}>
          <option value="">All statuses</option>
          <option value="active">Active</option>
          <option value="on_leave">On leave</option>
          <option value="terminated">Terminated</option>
        </select>
        <select className="vf-input w-44" value={filterDept} onChange={(e) => setFilterDept(e.target.value)}>
          <option value="">All departments</option>
          {DEPARTMENTS.map((d) => <option key={d} value={d}>{d}</option>)}
        </select>
        {(filterStatus || filterDept) && (
          <button onClick={() => { setFilterStatus(""); setFilterDept(""); }} className="vf-btn-ghost flex items-center gap-1 text-xs">
            <X className="w-3 h-3" /> Clear filters
          </button>
        )}
      </div>

      {loading ? (
        <div className="flex items-center justify-center h-40">
          <Loader2 className="w-6 h-6 animate-spin text-vf-accent" />
        </div>
      ) : filtered.length === 0 ? (
        <p className="vf-text-m text-muted-foreground">No employees found.</p>
      ) : (
        <div className={styles.employeeGrid}>
          {filtered.map((emp) => {
            const st = emp.profile?.status ?? "active";
            return (
              <button
                key={emp.id}
                onClick={() => router.push(`/${locale}/hr/${emp.id}`)}
                className={styles.employeeCard}
              >
                <div className="flex items-center justify-between mb-2">
                  <div className="flex items-center gap-3">
                    <div className={styles.avatar}>
                      {emp.name.charAt(0).toUpperCase()}
                    </div>
                    <div>
                      <p className="font-medium text-sm">{emp.name}</p>
                      {emp.email && <p className="text-xs text-muted-foreground">{emp.email}</p>}
                    </div>
                  </div>
                  <span className={`${styles.statusBadge} ${st === "active" ? styles.statusActive : st === "on_leave" ? styles.statusLeave : styles.statusTerminated}`}>
                    {st === "on_leave" ? "On leave" : st.charAt(0).toUpperCase() + st.slice(1)}
                  </span>
                </div>
                {emp.profile ? (
                  <div className="text-xs text-muted-foreground space-y-0.5 mt-1">
                    {emp.profile.job_title && <p>{emp.profile.job_title}</p>}
                    {emp.profile.department && <p className="text-vf-accent font-medium">{emp.profile.department}</p>}
                    <p>{TYPE_LABELS[emp.profile.employment_type] ?? emp.profile.employment_type}</p>
                    {emp.profile.start_date && (
                      <p>Since {new Date(emp.profile.start_date).toLocaleDateString()}</p>
                    )}
                  </div>
                ) : (
                  <p className="text-xs text-muted-foreground italic mt-1">No profile yet</p>
                )}
              </button>
            );
          })}
        </div>
      )}

      {/* Add Employee Modal */}
      {showAddModal && (
        <div className={styles.modal}>
          <div className={styles.modalPanel}>
            <div className="flex items-center justify-between mb-4">
              <h2 className="font-semibold vf-text-1">Add Employee</h2>
              <button onClick={() => setShowAddModal(false)} className="vf-btn-ghost p-1">
                <X className="w-4 h-4" />
              </button>
            </div>
            <div className="space-y-3">
              <div>
                <label className="text-xs font-medium text-muted-foreground">Full Name *</label>
                <input
                  className="vf-input w-full mt-1"
                  placeholder="Jane Doe"
                  value={addForm.name}
                  onChange={(e) => setAddForm((f) => ({ ...f, name: e.target.value }))}
                />
              </div>
              <div>
                <label className="text-xs font-medium text-muted-foreground">Email</label>
                <input
                  className="vf-input w-full mt-1"
                  type="email"
                  placeholder="jane@company.com"
                  value={addForm.email}
                  onChange={(e) => setAddForm((f) => ({ ...f, email: e.target.value }))}
                />
              </div>
              <div>
                <label className="text-xs font-medium text-muted-foreground">Role</label>
                <select className="vf-input w-full mt-1" value={addForm.role} onChange={(e) => setAddForm((f) => ({ ...f, role: e.target.value }))}>
                  <option value="STAFF">Staff</option>
                  <option value="ADMIN">Admin</option>
                  <option value="OWNER">Owner</option>
                </select>
              </div>
              <div className="flex gap-2 pt-1">
                <button onClick={handleAddEmployee} disabled={adding} className="vf-btn flex-1 flex items-center justify-center gap-2">
                  {adding && <Loader2 className="w-3 h-3 animate-spin" />} Add
                </button>
                <button onClick={() => setShowAddModal(false)} className="vf-btn-ghost flex-1">Cancel</button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
