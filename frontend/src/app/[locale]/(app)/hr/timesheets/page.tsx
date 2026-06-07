"use client";

import { useEffect, useState, useCallback } from "react";
import { toast } from "sonner";
import { api } from "@/lib/api-client";
import {
  ChevronLeft,
  ChevronRight,
  RefreshCw,
  Download,
  CheckCircle,
  XCircle,
  Send,
  Unlock,
  Clock,
  AlertTriangle,
} from "lucide-react";

// ── types ──────────────────────────────────────────────────────────────────

interface TimesheetLine {
  id: string;
  work_date: string;
  clock_in_at: string | null;
  clock_out_at: string | null;
  hours_raw: number;
  hours_adjusted: number | null;
  adjustment_reason: string | null;
}

interface Timesheet {
  id: string;
  staff_id: string;
  staff_name: string;
  week_start: string;
  status: "draft" | "submitted" | "approved" | "rejected";
  total_hours: number;
  regular_hours: number;
  overtime_hours: number;
  total_cost: number | null;
  manager_comment: string | null;
  submitted_at: string | null;
  approved_at: string | null;
  rejected_at: string | null;
  lines?: TimesheetLine[];
}

// ── constants ─────────────────────────────────────────────────────────────

const STATUS_STYLE: Record<string, string> = {
  draft: "bg-gray-100 text-gray-600",
  submitted: "bg-blue-100 text-blue-700",
  approved: "bg-emerald-100 text-emerald-700",
  rejected: "bg-rose-100 text-rose-700",
};

const STATUS_LABEL: Record<string, string> = {
  draft: "Draft",
  submitted: "Submitted",
  approved: "Approved",
  rejected: "Rejected",
};

const DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];

// ── helpers ───────────────────────────────────────────────────────────────

function getMonday(d: Date): Date {
  const day = d.getDay(); // 0=Sun
  const diff = day === 0 ? -6 : 1 - day;
  const mon = new Date(d);
  mon.setDate(d.getDate() + diff);
  mon.setHours(0, 0, 0, 0);
  return mon;
}

function toIso(d: Date): string {
  return d.toISOString().split("T")[0];
}

function fmtHours(h: number): string {
  const hrs = Math.floor(h);
  const mins = Math.round((h - hrs) * 60);
  return mins > 0 ? `${hrs}h ${mins}m` : `${hrs}h`;
}

function fmtTime(dt: string | null): string {
  if (!dt) return "—";
  return new Date(dt).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

// ── component ─────────────────────────────────────────────────────────────

export default function TimesheetsPage() {
  const [weekStart, setWeekStart] = useState<Date>(() => getMonday(new Date()));
  const [timesheets, setTimesheets] = useState<Timesheet[]>([]);
  const [loading, setLoading] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [detail, setDetail] = useState<Timesheet | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [statusFilter, setStatusFilter] = useState<string>("");
  // line edit state
  const [editLineId, setEditLineId] = useState<string | null>(null);
  const [editHours, setEditHours] = useState("");
  const [editReason, setEditReason] = useState("");
  const [actionComment, setActionComment] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const weekIso = toIso(weekStart);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams({ week_start: weekIso, limit: "100" });
      if (statusFilter) params.set("status", statusFilter);
      const data = await api.get<Timesheet[]>(`/api/hr/timesheets?${params}`);
      setTimesheets(data);
    } catch {
      toast.error("Failed to load timesheets");
    } finally {
      setLoading(false);
    }
  }, [weekIso, statusFilter]);

  useEffect(() => { load(); }, [load]);

  async function generate() {
    setGenerating(true);
    try {
      const res = await api.post<{ generated: number }>(`/api/hr/timesheets/generate?week_start=${weekIso}`, {});
      toast.success(`Generated ${res.generated} timesheet(s)`);
      await load();
    } catch {
      toast.error("Failed to generate timesheets");
    } finally {
      setGenerating(false);
    }
  }

  async function openDetail(ts: Timesheet) {
    setDetail(ts);
    setEditLineId(null);
    setActionComment("");
    setDetailLoading(true);
    try {
      const data = await api.get<Timesheet>(`/api/hr/timesheets/${ts.id}`);
      setDetail(data);
    } catch {
      toast.error("Failed to load timesheet detail");
    } finally {
      setDetailLoading(false);
    }
  }

  async function doAction(action: "submit" | "approve" | "reject" | "unlock") {
    if (!detail) return;
    if ((action === "reject" || action === "unlock") && !actionComment.trim()) {
      toast.error("Comment is required for this action");
      return;
    }
    setSubmitting(true);
    try {
      const body = { comment: actionComment || undefined };
      const updated = await api.post<Timesheet>(`/api/hr/timesheets/${detail.id}/${action}`, body);
      toast.success(`Timesheet ${action}ed`);
      setDetail({ ...updated, lines: detail.lines });
      await load();
    } catch (err: any) {
      toast.error(err?.detail || "Action failed");
    } finally {
      setSubmitting(false);
    }
  }

  async function saveLineAdjust() {
    if (!detail || !editLineId) return;
    const h = parseFloat(editHours);
    if (isNaN(h) || h < 0) { toast.error("Invalid hours"); return; }
    setSubmitting(true);
    try {
      const res = await api.patch<{ timesheet: Timesheet; line: TimesheetLine }>(
        `/api/hr/timesheets/${detail.id}/lines/${editLineId}`,
        { hours_adjusted: h, adjustment_reason: editReason || null }
      );
      const updatedLines = (detail.lines || []).map(ln =>
        ln.id === editLineId ? res.line : ln
      );
      setDetail({ ...res.timesheet, lines: updatedLines, staff_name: detail.staff_name });
      setEditLineId(null);
      toast.success("Line adjusted");
      await load();
    } catch {
      toast.error("Failed to save adjustment");
    } finally {
      setSubmitting(false);
    }
  }

  async function exportCsv() {
    try {
      await api.downloadBlob(
        `/api/hr/timesheets/export?week_start=${weekIso}&status=approved`,
        `timesheets_${weekIso}_approved.csv`
      );
    } catch {
      toast.error("Export failed");
    }
  }

  function prevWeek() {
    const d = new Date(weekStart);
    d.setDate(d.getDate() - 7);
    setWeekStart(d);
  }

  function nextWeek() {
    const d = new Date(weekStart);
    d.setDate(d.getDate() + 7);
    setWeekStart(d);
  }

  function todayWeek() {
    setWeekStart(getMonday(new Date()));
  }

  const weekLabel = (() => {
    const end = new Date(weekStart);
    end.setDate(end.getDate() + 6);
    return `${weekStart.toLocaleDateString("en-GB", { day: "numeric", month: "short" })} – ${end.toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric" })}`;
  })();

  // Week day headers
  const weekDays = DAYS.map((label, i) => {
    const d = new Date(weekStart);
    d.setDate(d.getDate() + i);
    return { label, date: toIso(d) };
  });

  const filtered = statusFilter
    ? timesheets.filter(t => t.status === statusFilter)
    : timesheets;

  return (
    <div className="vf-section space-y-6">
      {/* Header */}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="vf-text-1 text-2xl font-semibold">Timesheet Approval</h1>
          <p className="vf-text-m text-sm mt-0.5">Weekly hours review before payroll export</p>
        </div>
        <div className="flex gap-2 flex-wrap">
          <button
            onClick={generate}
            disabled={generating}
            className="vf-btn flex items-center gap-1.5 text-sm"
          >
            <RefreshCw size={14} className={generating ? "animate-spin" : ""} />
            {generating ? "Generating…" : "Generate Week"}
          </button>
          <button
            onClick={exportCsv}
            className="vf-btn-ghost flex items-center gap-1.5 text-sm"
          >
            <Download size={14} />
            Export Approved CSV
          </button>
        </div>
      </div>

      {/* Week navigation */}
      <div className="flex items-center gap-2">
        <button onClick={prevWeek} className="vf-btn-ghost p-1.5 rounded"><ChevronLeft size={16} /></button>
        <span className="font-medium text-sm min-w-[200px] text-center">{weekLabel}</span>
        <button onClick={nextWeek} className="vf-btn-ghost p-1.5 rounded"><ChevronRight size={16} /></button>
        <button onClick={todayWeek} className="vf-btn-ghost text-xs px-2 py-1 rounded ml-1">Today</button>
      </div>

      {/* Status filter */}
      <div className="flex gap-2 flex-wrap">
        {["", "draft", "submitted", "approved", "rejected"].map(s => (
          <button
            key={s}
            onClick={() => setStatusFilter(s)}
            className={`px-3 py-1 rounded-full text-xs font-medium border transition-colors ${
              statusFilter === s
                ? "bg-indigo-600 text-white border-indigo-600"
                : "border-gray-200 text-gray-600 hover:border-gray-300"
            }`}
          >
            {s === "" ? "All" : STATUS_LABEL[s]}
          </button>
        ))}
      </div>

      {/* Table */}
      {loading ? (
        <div className="text-center py-12 vf-text-m text-sm">Loading…</div>
      ) : filtered.length === 0 ? (
        <div className="text-center py-12 vf-text-m text-sm space-y-2">
          <Clock size={32} className="mx-auto opacity-30" />
          <p>No timesheets for this week. Click <strong>Generate Week</strong> to build them from punches.</p>
        </div>
      ) : (
        <div className="overflow-x-auto rounded-xl border border-gray-100">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-100 bg-gray-50">
                <th className="text-left px-4 py-3 font-medium vf-text-m">Staff</th>
                <th className="text-left px-4 py-3 font-medium vf-text-m">Status</th>
                <th className="text-right px-4 py-3 font-medium vf-text-m">Total</th>
                <th className="text-right px-4 py-3 font-medium vf-text-m">Regular</th>
                <th className="text-right px-4 py-3 font-medium vf-text-m">Overtime</th>
                <th className="text-right px-4 py-3 font-medium vf-text-m">Est. Cost</th>
                <th className="px-4 py-3" />
              </tr>
            </thead>
            <tbody>
              {filtered.map(ts => (
                <tr
                  key={ts.id}
                  className={`border-b border-gray-50 hover:bg-gray-50 cursor-pointer transition-colors ${
                    ts.overtime_hours > 0 ? "bg-amber-50/40" : ""
                  }`}
                  onClick={() => openDetail(ts)}
                >
                  <td className="px-4 py-3 font-medium">{ts.staff_name}</td>
                  <td className="px-4 py-3">
                    <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${STATUS_STYLE[ts.status]}`}>
                      {STATUS_LABEL[ts.status]}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-right font-mono">{fmtHours(ts.total_hours)}</td>
                  <td className="px-4 py-3 text-right font-mono text-gray-500">{fmtHours(ts.regular_hours)}</td>
                  <td className="px-4 py-3 text-right font-mono">
                    {ts.overtime_hours > 0 ? (
                      <span className="text-amber-600 flex items-center justify-end gap-1">
                        <AlertTriangle size={12} />
                        {fmtHours(ts.overtime_hours)}
                      </span>
                    ) : (
                      <span className="text-gray-400">—</span>
                    )}
                  </td>
                  <td className="px-4 py-3 text-right text-gray-500">
                    {ts.total_cost != null ? `${Number(ts.total_cost).toLocaleString()} SEK` : "—"}
                  </td>
                  <td className="px-4 py-3 text-right">
                    <button
                      className="text-indigo-600 hover:underline text-xs"
                      onClick={e => { e.stopPropagation(); openDetail(ts); }}
                    >
                      View
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Detail modal */}
      {detail && (
        <div className="fixed inset-0 bg-black/40 z-50 flex items-end sm:items-center justify-center p-4">
          <div className="bg-white rounded-2xl shadow-2xl w-full max-w-2xl max-h-[90vh] overflow-y-auto">
            {/* Modal header */}
            <div className="flex items-center justify-between px-6 py-4 border-b border-gray-100">
              <div>
                <h2 className="font-semibold text-base">{detail.staff_name}</h2>
                <p className="text-xs vf-text-m mt-0.5">
                  Week of {detail.week_start} ·{" "}
                  <span className={`px-1.5 py-0.5 rounded-full ${STATUS_STYLE[detail.status]}`}>
                    {STATUS_LABEL[detail.status]}
                  </span>
                </p>
              </div>
              <button
                onClick={() => setDetail(null)}
                className="text-gray-400 hover:text-gray-600 text-xl leading-none"
              >
                ×
              </button>
            </div>

            {detailLoading ? (
              <div className="py-12 text-center vf-text-m text-sm">Loading lines…</div>
            ) : (
              <>
                {/* Summary cards */}
                <div className="grid grid-cols-3 gap-3 px-6 py-4">
                  {[
                    { label: "Total", value: fmtHours(detail.total_hours), color: "text-gray-900" },
                    { label: "Regular", value: fmtHours(detail.regular_hours), color: "text-gray-600" },
                    {
                      label: "Overtime",
                      value: fmtHours(detail.overtime_hours),
                      color: detail.overtime_hours > 0 ? "text-amber-600" : "text-gray-400",
                    },
                  ].map(c => (
                    <div key={c.label} className="bg-gray-50 rounded-xl p-3 text-center">
                      <p className="text-xs vf-text-m">{c.label}</p>
                      <p className={`font-semibold text-lg font-mono ${c.color}`}>{c.value}</p>
                    </div>
                  ))}
                </div>

                {/* Lines */}
                <div className="px-6 pb-2">
                  <p className="text-xs font-medium vf-text-m uppercase tracking-wide mb-2">Daily Breakdown</p>
                  <div className="space-y-1">
                    {(detail.lines || []).length === 0 && (
                      <p className="text-sm vf-text-m py-2">No punch records for this week.</p>
                    )}
                    {(detail.lines || []).map(ln => {
                      const effective = ln.hours_adjusted ?? ln.hours_raw;
                      const isEditing = editLineId === ln.id;
                      const locked = detail.status === "approved";
                      return (
                        <div
                          key={ln.id}
                          className={`rounded-lg border px-3 py-2 text-sm ${
                            ln.hours_adjusted != null ? "border-amber-200 bg-amber-50/40" : "border-gray-100"
                          }`}
                        >
                          <div className="flex items-center justify-between gap-2">
                            <div className="flex items-center gap-3">
                              <span className="font-medium w-12 text-xs">{ln.work_date.slice(5)}</span>
                              <span className="text-xs vf-text-m">
                                {fmtTime(ln.clock_in_at)} – {fmtTime(ln.clock_out_at)}
                              </span>
                            </div>
                            <div className="flex items-center gap-2">
                              <span className={`font-mono text-sm ${ln.hours_adjusted != null ? "text-amber-700" : ""}`}>
                                {fmtHours(effective)}
                                {ln.hours_adjusted != null && (
                                  <span className="text-xs vf-text-m ml-1">(was {fmtHours(ln.hours_raw)})</span>
                                )}
                              </span>
                              {!locked && !isEditing && (
                                <button
                                  className="text-xs text-indigo-600 hover:underline"
                                  onClick={() => {
                                    setEditLineId(ln.id);
                                    setEditHours(String(effective));
                                    setEditReason(ln.adjustment_reason || "");
                                  }}
                                >
                                  Adjust
                                </button>
                              )}
                            </div>
                          </div>
                          {isEditing && (
                            <div className="mt-2 space-y-1.5">
                              <input
                                type="number"
                                min="0"
                                step="0.25"
                                value={editHours}
                                onChange={e => setEditHours(e.target.value)}
                                className="vf-input w-24 text-sm py-1 px-2 rounded"
                                placeholder="Hours"
                              />
                              <input
                                type="text"
                                value={editReason}
                                onChange={e => setEditReason(e.target.value)}
                                className="vf-input w-full text-sm py-1 px-2 rounded"
                                placeholder="Reason for adjustment"
                              />
                              <div className="flex gap-2">
                                <button
                                  onClick={saveLineAdjust}
                                  disabled={submitting}
                                  className="vf-btn text-xs px-3 py-1"
                                >
                                  Save
                                </button>
                                <button
                                  onClick={() => setEditLineId(null)}
                                  className="vf-btn-ghost text-xs px-3 py-1"
                                >
                                  Cancel
                                </button>
                              </div>
                            </div>
                          )}
                          {!isEditing && ln.adjustment_reason && (
                            <p className="text-xs vf-text-m mt-0.5 ml-15">Note: {ln.adjustment_reason}</p>
                          )}
                        </div>
                      );
                    })}
                  </div>
                </div>

                {/* Manager comment */}
                {detail.manager_comment && (
                  <div className="mx-6 my-3 p-3 bg-gray-50 rounded-lg text-sm vf-text-m">
                    <span className="font-medium">Comment: </span>{detail.manager_comment}
                  </div>
                )}

                {/* Actions */}
                <div className="px-6 py-4 border-t border-gray-100 space-y-3">
                  {/* Comment input for reject / unlock */}
                  {(detail.status === "submitted" || detail.status === "approved") && (
                    <input
                      type="text"
                      value={actionComment}
                      onChange={e => setActionComment(e.target.value)}
                      className="vf-input w-full text-sm"
                      placeholder={
                        detail.status === "approved"
                          ? "Reason for unlocking (required)"
                          : "Comment (required for reject)"
                      }
                    />
                  )}
                  <div className="flex flex-wrap gap-2">
                    {detail.status === "draft" && (
                      <button
                        onClick={() => doAction("submit")}
                        disabled={submitting}
                        className="vf-btn flex items-center gap-1.5 text-sm"
                      >
                        <Send size={14} /> Submit for Approval
                      </button>
                    )}
                    {detail.status === "rejected" && (
                      <button
                        onClick={() => doAction("submit")}
                        disabled={submitting}
                        className="vf-btn flex items-center gap-1.5 text-sm"
                      >
                        <Send size={14} /> Resubmit
                      </button>
                    )}
                    {detail.status === "submitted" && (
                      <>
                        <button
                          onClick={() => doAction("approve")}
                          disabled={submitting}
                          className="vf-btn flex items-center gap-1.5 text-sm bg-emerald-600 hover:bg-emerald-700"
                        >
                          <CheckCircle size={14} /> Approve
                        </button>
                        <button
                          onClick={() => doAction("reject")}
                          disabled={submitting}
                          className="vf-btn flex items-center gap-1.5 text-sm bg-rose-600 hover:bg-rose-700"
                        >
                          <XCircle size={14} /> Reject
                        </button>
                      </>
                    )}
                    {detail.status === "approved" && (
                      <button
                        onClick={() => doAction("unlock")}
                        disabled={submitting}
                        className="vf-btn-ghost flex items-center gap-1.5 text-sm text-amber-600 border-amber-300"
                      >
                        <Unlock size={14} /> Unlock for Corrections
                      </button>
                    )}
                  </div>
                </div>
              </>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
