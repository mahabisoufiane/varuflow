"use client";

import { useEffect, useState } from "react";
import { RoleGuard } from "@/components/app/RoleContext";
import { useRouter, useParams } from "next/navigation";
import Link from "next/link";
import { createClient } from "@/lib/supabase/client";
import {
  PlusCircle, FileText, CheckCircle2, Clock, RotateCcw,
  ArrowRight, RefreshCw, AlertCircle, ChevronRight,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { toast } from "sonner";
import styles from "./page.module.scss";
import { isPlanGateError, PlanGateBlock } from "@/components/ui/PlanGate";

interface Budget {
  id: string;
  name: string;
  fiscal_year: number;
  department: string | null;
  status: string;
  submitted_at: string | null;
  review_notes: string | null;
  approved_at: string | null;
  created_at: string;
  lines: { id: string; account_code: string; month: number; amount: number }[];
}

const STATUS_CONFIG: Record<string, { label: string; color: string; Icon: React.ElementType }> = {
  DRAFT:              { label: "Draft",             color: "bg-gray-100 text-gray-600",    Icon: FileText      },
  SUBMITTED:          { label: "Submitted",         color: "bg-blue-100 text-blue-700",    Icon: Clock         },
  CHANGES_REQUESTED:  { label: "Changes Requested", color: "bg-amber-100 text-amber-700",  Icon: RotateCcw     },
  APPROVED:           { label: "Approved",          color: "bg-green-100 text-green-700",  Icon: CheckCircle2  },
};

function BudgetPageInner() {
  const router = useRouter();
  const params = useParams<{ locale: string }>();
  const locale = params?.locale ?? "en";
  const supabase = createClient();

  const [budgets, setBudgets] = useState<Budget[]>([]);
  const [submissions, setSubmissions] = useState<Budget[]>([]);
  const [loading, setLoading] = useState(true);
  const [tab, setTab] = useState<"my" | "review">("my");
  const [actionLoading, setActionLoading] = useState<string | null>(null);

  // New budget form
  const [showNew, setShowNew] = useState(false);
  const [newForm, setNewForm] = useState({
    name: "", fiscal_year: new Date().getFullYear().toString(), department: "",
  });

  // Review note modal
  const [reviewModal, setReviewModal] = useState<{ id: string; notes: string } | null>(null);

  const [planBlocked, setPlanBlocked] = useState<{ module: string; currentPlan: string } | null>(null);

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

      const [myRes, subRes] = await Promise.all([
        fetch(apiUrl("/api/accounting/budgets"), { headers: { Authorization: `Bearer ${token}` } }),
        fetch(apiUrl("/api/accounting/budgets/submissions"), { headers: { Authorization: `Bearer ${token}` } }),
      ]);
      if (myRes.status === 401) { router.push(`/${locale}/auth/login`); return; }
      if (myRes.ok) setBudgets(await myRes.json());
      if (subRes.ok) setSubmissions(await subRes.json());
    } catch (err) {
      if (isPlanGateError(err)) {
        setPlanBlocked({ module: (err as any).module ?? "finance", currentPlan: (err as any).currentPlan ?? "FREE" });
        return;
      }
      toast.error("Failed to load budgets");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { load(); }, []);  // eslint-disable-line react-hooks/exhaustive-deps

  async function createBudget() {
    if (!newForm.name.trim()) { toast.error("Name is required"); return; }
    setActionLoading("create");
    try {
      const token = await getToken();
      if (!token) return;
      const res = await fetch(apiUrl("/api/accounting/budgets"), {
        method: "POST",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
        body: JSON.stringify({
          name: newForm.name,
          fiscal_year: parseInt(newForm.fiscal_year),
          department: newForm.department || null,
        }),
      });
      if (!res.ok) {
        const b = await res.json().catch(() => ({}));
        toast.error(b.detail ?? "Failed to create budget");
        return;
      }
      toast.success("Budget created");
      setShowNew(false);
      setNewForm({ name: "", fiscal_year: new Date().getFullYear().toString(), department: "" });
      await load();
    } catch {
      toast.error("Something went wrong");
    } finally {
      setActionLoading(null);
    }
  }

  async function submitBudget(id: string) {
    setActionLoading(id + "_submit");
    try {
      const token = await getToken();
      if (!token) return;
      const res = await fetch(apiUrl(`/api/accounting/budgets/${id}/submit`), {
        method: "POST",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
        body: JSON.stringify({ note: null }),
      });
      if (!res.ok) {
        const b = await res.json().catch(() => ({}));
        toast.error(b.detail ?? "Failed to submit");
        return;
      }
      toast.success("Budget submitted for review");
      await load();
    } catch {
      toast.error("Something went wrong");
    } finally {
      setActionLoading(null);
    }
  }

  async function approveBudget(id: string) {
    setActionLoading(id + "_approve");
    try {
      const token = await getToken();
      if (!token) return;
      const res = await fetch(apiUrl(`/api/accounting/budgets/${id}/approve`), {
        method: "POST",
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) {
        const b = await res.json().catch(() => ({}));
        toast.error(b.detail ?? "Failed to approve");
        return;
      }
      toast.success("Budget approved and locked");
      await load();
    } catch {
      toast.error("Something went wrong");
    } finally {
      setActionLoading(null);
    }
  }

  async function requestChanges() {
    if (!reviewModal) return;
    setActionLoading(reviewModal.id + "_changes");
    try {
      const token = await getToken();
      if (!token) return;
      const res = await fetch(apiUrl(`/api/accounting/budgets/${reviewModal.id}/request-changes`), {
        method: "POST",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
        body: JSON.stringify({ notes: reviewModal.notes }),
      });
      if (!res.ok) {
        const b = await res.json().catch(() => ({}));
        toast.error(b.detail ?? "Failed to request changes");
        return;
      }
      toast.success("Changes requested, budget returned to submitter");
      setReviewModal(null);
      await load();
    } catch {
      toast.error("Something went wrong");
    } finally {
      setActionLoading(null);
    }
  }

  const pendingReviewCount = submissions.filter((b) => b.status === "SUBMITTED").length;

  if (planBlocked) return <PlanGateBlock module={planBlocked.module} currentPlan={planBlocked.currentPlan} featureName="Budget" />;

  return (
    <>
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-gray-900">Budget Planning</h1>
          <p className="text-sm text-muted-foreground mt-0.5">
            Department managers submit budgets; owners approve and lock the baseline.
          </p>
        </div>
        <Button onClick={() => setShowNew(true)} className="bg-[#1a2332] hover:bg-[#2a3342] text-white gap-2">
          <PlusCircle className="h-4 w-4" /> New Budget
        </Button>
      </div>

      {/* Tabs */}
      <div className={styles.tabBar}>
        {(["my", "review"] as const).map((t) => (
          <button key={t} type="button" onClick={() => setTab(t)}
            className={`${styles.tab} ${tab === t ? styles.tabActive : ""}`}>
            {t === "my" ? "My Budgets" : (
              <span className="flex items-center gap-2">
                Review Queue
                {pendingReviewCount > 0 && (
                  <span className={styles.reviewCount}>{pendingReviewCount}</span>
                )}
              </span>
            )}
          </button>
        ))}
      </div>

      {/* New budget form */}
      {showNew && (
        <div className={`${styles.formCard} space-y-3`}>
          <h3 className="text-sm font-semibold text-gray-900">Create Budget</h3>
          <div className="grid grid-cols-3 gap-3">
            <div className="col-span-2 space-y-1">
              <label className={styles.formLabel}>Budget Name *</label>
              <input value={newForm.name} onChange={(e) => setNewForm((f) => ({ ...f, name: e.target.value }))}
                placeholder="Sales Dept FY 2026"
                className={styles.formInput} />
            </div>
            <div className="space-y-1">
              <label className={styles.formLabel}>Fiscal Year</label>
              <input type="number" value={newForm.fiscal_year}
                onChange={(e) => setNewForm((f) => ({ ...f, fiscal_year: e.target.value }))}
                className={styles.formInput} />
            </div>
          </div>
          <div className="space-y-1">
            <label className={styles.formLabel}>Department (optional)</label>
            <input value={newForm.department} onChange={(e) => setNewForm((f) => ({ ...f, department: e.target.value }))}
              placeholder="Sales, Finance, Operations…"
              className={styles.formInput} />
          </div>
          <div className="flex gap-2">
            <Button variant="outline" onClick={() => setShowNew(false)}>Cancel</Button>
            <Button disabled={actionLoading === "create"} onClick={createBudget}
              className="bg-[#1a2332] hover:bg-[#2a3342] text-white">
              {actionLoading === "create" ? "Creating…" : "Create Budget"}
            </Button>
          </div>
        </div>
      )}

      {/* Budget list */}
      {loading && budgets.length === 0 ? (
        <div className="text-center py-12"><RefreshCw className="h-6 w-6 animate-spin mx-auto text-muted-foreground" /></div>
      ) : (
        <div className={styles.budgetList}>
          {(tab === "my" ? budgets : submissions).length === 0 ? (
            <div className={styles.emptyState}>
              <FileText className="h-10 w-10 text-muted-foreground mx-auto mb-3" />
              <p className="text-gray-600 font-medium">
                {tab === "my" ? "No budgets yet" : "No submissions pending review"}
              </p>
            </div>
          ) : (
            <div className="divide-y divide-gray-100">
              {(tab === "my" ? budgets : submissions).map((b) => {
                const cfg = STATUS_CONFIG[b.status] ?? STATUS_CONFIG.DRAFT;
                const Icon = cfg.Icon;
                return (
                  <div key={b.id} className={styles.budgetRow}>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 mb-0.5">
                        <p className="text-sm font-medium text-gray-900">{b.name}</p>
                        {b.department && (
                          <span className={styles.deptBadge}>{b.department}</span>
                        )}
                      </div>
                      <p className="text-xs text-muted-foreground">
                        FY {b.fiscal_year}
                        {b.submitted_at && ` · Submitted ${new Date(b.submitted_at).toLocaleDateString()}`}
                        {b.approved_at && ` · Approved ${new Date(b.approved_at).toLocaleDateString()}`}
                      </p>
                      {b.review_notes && b.status === "CHANGES_REQUESTED" && (
                        <div className={styles.warningBox}>
                          <AlertCircle className="h-3.5 w-3.5 text-amber-600 flex-shrink-0 mt-0.5" />
                          <p className="text-xs text-amber-800">{b.review_notes}</p>
                        </div>
                      )}
                    </div>

                    <span className={`${styles.statusBadge} ${cfg.color}`}>
                      <Icon className="h-3 w-3" />
                      {cfg.label}
                    </span>

                    {/* Actions */}
                    <div className="flex items-center gap-2 flex-shrink-0">
                      {b.status === "DRAFT" || b.status === "CHANGES_REQUESTED" ? (
                        <Button variant="outline" size="sm"
                          disabled={actionLoading === b.id + "_submit"}
                          onClick={() => submitBudget(b.id)}
                          className="gap-1">
                          {actionLoading === b.id + "_submit"
                            ? <RefreshCw className="h-3 w-3 animate-spin" />
                            : null}
                          Submit for Review
                        </Button>
                      ) : null}

                      {tab === "review" && b.status === "SUBMITTED" && (
                        <>
                          <Button size="sm"
                            disabled={actionLoading === b.id + "_approve"}
                            onClick={() => approveBudget(b.id)}
                            className="bg-green-600 hover:bg-green-700 text-white gap-1">
                            {actionLoading === b.id + "_approve"
                              ? <RefreshCw className="h-3 w-3 animate-spin" /> : <CheckCircle2 className="h-3 w-3" />}
                            Approve
                          </Button>
                          <Button variant="outline" size="sm"
                            onClick={() => setReviewModal({ id: b.id, notes: "" })}
                            className="gap-1 border-amber-200 text-amber-700 hover:bg-amber-50">
                            <RotateCcw className="h-3 w-3" />
                            Request Changes
                          </Button>
                        </>
                      )}

                      <Link href={`/${locale}/budget/${b.id}`}>
                        <Button variant="ghost" size="sm">
                          <ChevronRight className="h-4 w-4" />
                        </Button>
                      </Link>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      )}

      {/* Request changes modal */}
      {reviewModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
          <div className="w-full max-w-md rounded-xl bg-white p-6 shadow-xl space-y-4">
            <h3 className="text-base font-semibold text-gray-900">Request Revisions</h3>
            <p className="text-sm text-muted-foreground">
              Explain what changes the department manager should make before you can approve.
            </p>
            <textarea
              value={reviewModal.notes}
              onChange={(e) => setReviewModal((m) => m ? { ...m, notes: e.target.value } : null)}
              rows={4} placeholder="Please revise Q3 expense figures…"
              className="block w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-[#1a2332]"
            />
            <div className="flex gap-2 justify-end">
              <Button variant="outline" onClick={() => setReviewModal(null)}>Cancel</Button>
              <Button
                disabled={!reviewModal.notes.trim() || actionLoading?.endsWith("_changes")}
                onClick={requestChanges}
                className="bg-amber-600 hover:bg-amber-700 text-white"
              >
                Send Back for Revisions
              </Button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}

export default function BudgetPage() {
  return (
    <RoleGuard minRole="ADMIN">
      <BudgetPageInner />
    </RoleGuard>
  );
}
