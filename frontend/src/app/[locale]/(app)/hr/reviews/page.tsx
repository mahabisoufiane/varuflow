"use client";

import { useEffect, useState, useCallback } from "react";
import { ClipboardList, Plus, Loader2, Star, Users, FileText, ExternalLink } from "lucide-react";
import { toast } from "sonner";
import { api } from "@/lib/api-client";
import styles from "./page.module.scss";

// ── Types ──────────────────────────────────────────────────────────────────

interface Cycle {
  id: string;
  name: string;
  status: string;
  start_date: string;
  end_date: string;
  cycle_frequency: string;
  rating_labels: string[];
}

interface Goal {
  title: string;
  target?: string;
  self_rating?: number | null;
  self_comment?: string;
  manager_rating?: number | null;
  manager_comment?: string;
}

interface DevItem {
  action: string;
  by_when?: string;
}

interface Review {
  id: string;
  staff_id: string;
  staff_name?: string;
  cycle_id: string;
  status: string;
  overall_rating: number | null;
  goals: Goal[];
  self_assessment: string | null;
  manager_review: string | null;
  check_in_notes: string | null;
  development_plan: DevItem[];
}

// ── Constants ──────────────────────────────────────────────────────────────

const STATUS_BADGE: Record<string, string> = {
  draft: "bg-gray-100 text-gray-700",
  open: "bg-blue-100 text-blue-800",
  closed: "bg-green-100 text-green-800",
  pending: "bg-yellow-100 text-yellow-800",
  self_submitted: "bg-purple-100 text-purple-800",
  reviewed: "bg-blue-100 text-blue-800",
  completed: "bg-green-100 text-green-800",
};

const STATUS_MODULE: Record<string, keyof typeof styles> = {
  draft:          "statusDraft",
  open:           "statusOpen",
  closed:         "statusClosed",
  pending:        "statusPending",
  self_submitted: "statusSelfSubmitted",
  reviewed:       "statusReviewed",
  completed:      "statusCompleted",
};

const FREQ_LABELS: Record<string, string> = {
  quarterly: "Quarterly",
  semi_annual: "Semi-Annual",
  annual: "Annual",
};

// ── Helpers ────────────────────────────────────────────────────────────────

function StarRow({ value, onChange, labels }: { value: number | null | undefined; onChange?: (n: number) => void; labels?: string[] }) {
  return (
    <div className="flex gap-0.5">
      {[1, 2, 3, 4, 5].map((n) => (
        <button
          key={n}
          type="button"
          title={labels?.[n - 1]}
          onClick={() => onChange?.(n)}
          className={onChange ? "cursor-pointer" : "cursor-default"}
        >
          <Star className={`w-4 h-4 ${(value ?? 0) >= n ? "text-yellow-500 fill-yellow-500" : "text-gray-300"}`} />
        </button>
      ))}
    </div>
  );
}

// ── Component ──────────────────────────────────────────────────────────────

export default function ReviewsPage() {
  const [cycles, setCycles] = useState<Cycle[]>([]);
  const [reviews, setReviews] = useState<Review[]>([]);
  const [calibration, setCalibration] = useState<Review[] | null>(null);
  const [selectedCycle, setSelectedCycle] = useState<Cycle | null>(null);
  const [selectedReview, setSelectedReview] = useState<Review | null>(null);
  const [tab, setTab] = useState<"reviews" | "calibration">("reviews");
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);
  const [showCycleForm, setShowCycleForm] = useState(false);
  const [cycleForm, setCycleForm] = useState({
    name: "", start_date: "", end_date: "", cycle_frequency: "annual",
  });
  const [reviewEdit, setReviewEdit] = useState<Partial<Review>>({});
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    api.get<Cycle[]>("/api/hr/performance-cycles")
      .then(setCycles)
      .catch(() => toast.error("Failed to load cycles"))
      .finally(() => setLoading(false));
  }, []);

  const loadReviews = useCallback(async (cycle: Cycle) => {
    setSelectedCycle(cycle);
    setSelectedReview(null);
    setCalibration(null);
    try {
      const data = await api.get<Review[]>(`/api/hr/performance-reviews?cycle_id=${cycle.id}`);
      setReviews(data);
    } catch {
      toast.error("Failed to load reviews");
    }
  }, []);

  async function loadCalibration() {
    if (!selectedCycle) return;
    try {
      const data = await api.get<{ reviews: Review[] }>(
        `/api/hr/performance-reviews/calibration?cycle_id=${selectedCycle.id}`
      );
      setCalibration(data.reviews);
    } catch {
      toast.error("Failed to load calibration");
    }
  }

  async function createCycle() {
    if (!cycleForm.name || !cycleForm.start_date || !cycleForm.end_date) {
      toast.error("Fill in all fields");
      return;
    }
    try {
      const created = await api.post<Cycle>("/api/hr/performance-cycles", cycleForm);
      setCycles((c) => [created, ...c]);
      setShowCycleForm(false);
      setCycleForm({ name: "", start_date: "", end_date: "", cycle_frequency: "annual" });
      toast.success("Cycle created");
    } catch {
      toast.error("Failed to create cycle");
    }
  }

  async function generateReviews() {
    if (!selectedCycle) return;
    setGenerating(true);
    try {
      const res = await api.post<{ created: number }>(
        `/api/hr/performance-cycles/${selectedCycle.id}/reviews`, {}
      );
      toast.success(`Created ${res.created} review(s)`);
      loadReviews(selectedCycle);
    } catch {
      toast.error("Failed to generate reviews");
    } finally {
      setGenerating(false);
    }
  }

  function selectReview(r: Review) {
    setSelectedReview(r);
    setReviewEdit({
      ...r,
      goals: r.goals?.length ? r.goals : [],
      development_plan: r.development_plan ?? [],
    });
  }

  async function saveReview() {
    if (!selectedReview) return;
    setSaving(true);
    try {
      const updated = await api.patch<Review>(
        `/api/hr/performance-reviews/${selectedReview.id}`,
        reviewEdit
      );
      setReviews((rs) => rs.map((x) => (x.id === updated.id ? updated : x)));
      setSelectedReview(updated);
      setReviewEdit({ ...updated });
      toast.success("Review saved");
    } catch {
      toast.error("Failed to save review");
    } finally {
      setSaving(false);
    }
  }

  function openPdf() {
    if (!selectedReview) return;
    window.open(`/api/hr/performance-reviews/${selectedReview.id}/export-pdf`, "_blank");
  }

  function updateGoal(idx: number, key: keyof Goal, value: any) {
    const goals = [...((reviewEdit.goals as Goal[]) ?? [])];
    goals[idx] = { ...goals[idx], [key]: value };
    setReviewEdit((r) => ({ ...r, goals }));
  }

  function addGoal() {
    const goals = [...((reviewEdit.goals as Goal[]) ?? []), { title: "", target: "" }];
    setReviewEdit((r) => ({ ...r, goals }));
  }

  function removeGoal(idx: number) {
    const goals = ((reviewEdit.goals as Goal[]) ?? []).filter((_, i) => i !== idx);
    setReviewEdit((r) => ({ ...r, goals }));
  }

  function updateDevItem(idx: number, key: keyof DevItem, value: string) {
    const plan = [...((reviewEdit.development_plan as DevItem[]) ?? [])];
    plan[idx] = { ...plan[idx], [key]: value };
    setReviewEdit((r) => ({ ...r, development_plan: plan }));
  }

  function addDevItem() {
    const plan = [...((reviewEdit.development_plan as DevItem[]) ?? []), { action: "" }];
    setReviewEdit((r) => ({ ...r, development_plan: plan }));
  }

  const ratingLabels = selectedCycle?.rating_labels ?? [];

  return (
    <div className="vf-section space-y-6">
      <div className="flex items-center gap-2">
        <ClipboardList className="w-6 h-6" />
        <h1 className="vf-text-1 text-2xl font-semibold">Performance Reviews</h1>
      </div>

      <div className="grid grid-cols-12 gap-4">
        {/* ── Cycles panel ───────────────────────────────────────── */}
        <div className="col-span-3 border border-gray-100 rounded-xl p-3 space-y-2">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-semibold vf-text-1">Cycles</h3>
            <button onClick={() => setShowCycleForm((x) => !x)} className="vf-btn-ghost p-1 rounded">
              <Plus className="w-4 h-4" />
            </button>
          </div>

          {showCycleForm && (
            <div className="space-y-2 bg-gray-50 rounded-lg p-2">
              <input className="vf-input text-xs w-full" placeholder="Cycle name" value={cycleForm.name} onChange={(e) => setCycleForm((f) => ({ ...f, name: e.target.value }))} />
              <input type="date" className="vf-input text-xs w-full" value={cycleForm.start_date} onChange={(e) => setCycleForm((f) => ({ ...f, start_date: e.target.value }))} />
              <input type="date" className="vf-input text-xs w-full" value={cycleForm.end_date} onChange={(e) => setCycleForm((f) => ({ ...f, end_date: e.target.value }))} />
              <select className="vf-input text-xs w-full" value={cycleForm.cycle_frequency} onChange={(e) => setCycleForm((f) => ({ ...f, cycle_frequency: e.target.value }))}>
                <option value="quarterly">Quarterly</option>
                <option value="semi_annual">Semi-Annual</option>
                <option value="annual">Annual</option>
              </select>
              <div className="flex gap-1">
                <button onClick={createCycle} className="vf-btn text-xs px-3 py-1">Create</button>
                <button onClick={() => setShowCycleForm(false)} className="vf-btn-ghost text-xs px-3 py-1">Cancel</button>
              </div>
            </div>
          )}

          {loading ? <Loader2 className="w-4 h-4 animate-spin mx-auto" /> : (
            <div className="space-y-1">
              {cycles.map((c) => (
                <button key={c.id} onClick={() => loadReviews(c)}
                  className={`w-full text-left p-2 rounded-lg text-xs hover:bg-gray-50 transition-colors ${selectedCycle?.id === c.id ? "bg-indigo-50" : ""}`}>
                  <p className="font-medium">{c.name}</p>
                  <p className="vf-text-m">{c.start_date} – {c.end_date}</p>
                  <div className="flex gap-1 mt-0.5">
                    <span className={styles[STATUS_MODULE[c.status] ?? "statusDraft"]}>{c.status}</span>
                    <span className="px-1.5 py-0.5 rounded-full text-xs bg-gray-100 text-gray-600">{FREQ_LABELS[c.cycle_frequency] ?? c.cycle_frequency}</span>
                  </div>
                </button>
              ))}
            </div>
          )}
        </div>

        {/* ── Reviews / Calibration panel ─────────────────────────── */}
        <div className="col-span-4 border border-gray-100 rounded-xl p-3">
          {selectedCycle ? (
            <>
              <div className="flex items-center justify-between mb-3">
                <h3 className="text-sm font-semibold">{selectedCycle.name}</h3>
                <div className="flex gap-1.5">
                  <button onClick={generateReviews} disabled={generating}
                    className="vf-btn-ghost text-xs px-2 py-1 flex items-center gap-1 disabled:opacity-50">
                    {generating && <Loader2 className="w-3 h-3 animate-spin" />} Generate
                  </button>
                </div>
              </div>

              {/* Tab switcher */}
              <div className="flex gap-1 mb-3">
                {(["reviews", "calibration"] as const).map((t) => (
                  <button key={t} onClick={() => { setTab(t); if (t === "calibration") loadCalibration(); }}
                    className={`text-xs px-2 py-1 rounded-full font-medium transition-colors capitalize ${tab === t ? "bg-indigo-600 text-white" : "vf-btn-ghost"}`}>
                    {t === "calibration" ? <span className="flex items-center gap-1"><Users size={10} />{t}</span> : t}
                  </button>
                ))}
              </div>

              {tab === "reviews" && (
                reviews.length === 0 ? (
                  <p className="text-xs vf-text-m">No reviews. Click Generate.</p>
                ) : (
                  <div className="space-y-1">
                    {reviews.map((r) => (
                      <button key={r.id} onClick={() => selectReview(r)}
                        className={`w-full text-left p-2 rounded-lg text-xs hover:bg-gray-50 ${selectedReview?.id === r.id ? "bg-indigo-50" : ""}`}>
                        <div className="flex items-center justify-between">
                          <span className="font-medium truncate">{r.staff_name || r.staff_id.slice(0, 8) + "…"}</span>
                          <span className={styles[STATUS_MODULE[r.status] ?? "statusDraft"]}>{r.status}</span>
                        </div>
                        {r.overall_rating && <StarRow value={r.overall_rating} labels={ratingLabels} />}
                      </button>
                    ))}
                  </div>
                )
              )}

              {tab === "calibration" && (
                <div className="overflow-x-auto">
                  {!calibration ? (
                    <p className="text-xs vf-text-m">Loading…</p>
                  ) : calibration.length === 0 ? (
                    <p className="text-xs vf-text-m">No reviews in this cycle.</p>
                  ) : (
                    <table className="w-full text-xs">
                      <thead>
                        <tr className="border-b border-gray-100">
                          <th className="text-left py-1 pr-2 font-medium vf-text-m">Staff</th>
                          <th className="text-left py-1 font-medium vf-text-m">Rating</th>
                          <th className="text-left py-1 font-medium vf-text-m">Status</th>
                        </tr>
                      </thead>
                      <tbody>
                        {calibration.map((r) => (
                          <tr key={r.id} className="border-b border-gray-50">
                            <td className="py-1 pr-2 font-medium">{r.staff_name || "—"}</td>
                            <td className="py-1"><StarRow value={r.overall_rating} labels={ratingLabels} /></td>
                            <td className="py-1">
                              <span className={styles[STATUS_MODULE[r.status] ?? "statusDraft"]}>{r.status}</span>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  )}
                </div>
              )}
            </>
          ) : (
            <p className="text-xs vf-text-m">Select a cycle.</p>
          )}
        </div>

        {/* ── Review editor ──────────────────────────────────────── */}
        <div className="col-span-5 border border-gray-100 rounded-xl p-4 overflow-y-auto max-h-[80vh]">
          {selectedReview ? (
            <div className="space-y-4">
              {/* Title + actions */}
              <div className="flex items-center justify-between">
                <span className={styles[STATUS_MODULE[selectedReview.status] ?? "statusDraft"]}>
                  {selectedReview.status}
                </span>
                <div className="flex gap-1.5">
                  <button onClick={openPdf} title="Export PDF" className="vf-btn-ghost p-1 rounded text-xs flex items-center gap-1">
                    <FileText size={13} /><ExternalLink size={11} />
                  </button>
                </div>
              </div>

              {/* Status + overall rating */}
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="text-xs font-medium vf-text-m">Status</label>
                  <select className="vf-input text-xs w-full mt-1"
                    value={reviewEdit.status ?? selectedReview.status}
                    onChange={(e) => setReviewEdit((r) => ({ ...r, status: e.target.value }))}>
                    <option value="pending">Pending</option>
                    <option value="self_submitted">Self Submitted</option>
                    <option value="reviewed">Reviewed</option>
                    <option value="completed">Completed</option>
                  </select>
                </div>
                <div>
                  <label className="text-xs font-medium vf-text-m">Overall Rating</label>
                  <div className="mt-1">
                    <StarRow
                      value={reviewEdit.overall_rating ?? null}
                      onChange={(n) => setReviewEdit((r) => ({ ...r, overall_rating: n }))}
                      labels={ratingLabels}
                    />
                    {reviewEdit.overall_rating && ratingLabels[reviewEdit.overall_rating - 1] && (
                      <p className="text-xs vf-text-m mt-0.5">{ratingLabels[reviewEdit.overall_rating - 1]}</p>
                    )}
                  </div>
                </div>
              </div>

              {/* Goals */}
              <div>
                <div className="flex items-center justify-between mb-1">
                  <label className="text-xs font-medium vf-text-m">Goals</label>
                  <button onClick={addGoal} className="text-xs text-indigo-600 hover:underline flex items-center gap-0.5">
                    <Plus size={11} /> Add Goal
                  </button>
                </div>
                <div className="space-y-2">
                  {(reviewEdit.goals as Goal[] ?? []).map((g, i) => (
                    <div key={i} className="border border-gray-100 rounded-lg p-2 space-y-1.5 text-xs">
                      <div className="flex gap-1">
                        <input className="vf-input flex-1 text-xs py-1" placeholder={`Goal ${i + 1}`}
                          value={g.title ?? ""} onChange={(e) => updateGoal(i, "title", e.target.value)} />
                        <button onClick={() => removeGoal(i)} className="text-rose-400 hover:text-rose-600 px-1">×</button>
                      </div>
                      <input className="vf-input w-full text-xs py-1" placeholder="Measurable target"
                        value={g.target ?? ""} onChange={(e) => updateGoal(i, "target", e.target.value)} />
                      <div className="grid grid-cols-2 gap-2">
                        <div>
                          <p className="vf-text-m mb-0.5">Self</p>
                          <StarRow value={g.self_rating} onChange={(n) => updateGoal(i, "self_rating", n)} labels={ratingLabels} />
                          <input className="vf-input w-full text-xs py-0.5 mt-1" placeholder="Self comment"
                            value={g.self_comment ?? ""} onChange={(e) => updateGoal(i, "self_comment", e.target.value)} />
                        </div>
                        <div>
                          <p className="vf-text-m mb-0.5">Manager</p>
                          <StarRow value={g.manager_rating} onChange={(n) => updateGoal(i, "manager_rating", n)} labels={ratingLabels} />
                          <input className="vf-input w-full text-xs py-0.5 mt-1" placeholder="Manager comment"
                            value={g.manager_comment ?? ""} onChange={(e) => updateGoal(i, "manager_comment", e.target.value)} />
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              {/* Self assessment */}
              <div>
                <label className="text-xs font-medium vf-text-m">Self-Assessment</label>
                <textarea className="vf-input w-full text-xs h-16 resize-none mt-1"
                  value={reviewEdit.self_assessment ?? ""}
                  onChange={(e) => setReviewEdit((r) => ({ ...r, self_assessment: e.target.value }))} />
              </div>

              {/* Manager review */}
              <div>
                <label className="text-xs font-medium vf-text-m">Manager Review</label>
                <textarea className="vf-input w-full text-xs h-16 resize-none mt-1"
                  value={reviewEdit.manager_review ?? ""}
                  onChange={(e) => setReviewEdit((r) => ({ ...r, manager_review: e.target.value }))} />
              </div>

              {/* Mid-cycle check-in */}
              <div>
                <label className="text-xs font-medium vf-text-m">Mid-Cycle Check-In Notes</label>
                <textarea className="vf-input w-full text-xs h-14 resize-none mt-1"
                  value={reviewEdit.check_in_notes ?? ""}
                  onChange={(e) => setReviewEdit((r) => ({ ...r, check_in_notes: e.target.value }))} />
              </div>

              {/* Development plan */}
              <div>
                <div className="flex items-center justify-between mb-1">
                  <label className="text-xs font-medium vf-text-m">Development Plan</label>
                  <button onClick={addDevItem} className="text-xs text-indigo-600 hover:underline flex items-center gap-0.5">
                    <Plus size={11} /> Add Action
                  </button>
                </div>
                <div className="space-y-1">
                  {(reviewEdit.development_plan as DevItem[] ?? []).map((item, i) => (
                    <div key={i} className="flex gap-1">
                      <input className="vf-input flex-1 text-xs py-1" placeholder="Action item"
                        value={item.action ?? ""} onChange={(e) => updateDevItem(i, "action", e.target.value)} />
                      <input type="date" className="vf-input w-32 text-xs py-1" value={item.by_when ?? ""}
                        onChange={(e) => updateDevItem(i, "by_when", e.target.value)} />
                    </div>
                  ))}
                </div>
              </div>

              <button onClick={saveReview} disabled={saving} className="vf-btn text-sm w-full flex items-center justify-center gap-2">
                {saving && <Loader2 className="w-3 h-3 animate-spin" />} Save Review
              </button>
            </div>
          ) : (
            <p className="text-xs vf-text-m">Select a review to edit.</p>
          )}
        </div>
      </div>
    </div>
  );
}
