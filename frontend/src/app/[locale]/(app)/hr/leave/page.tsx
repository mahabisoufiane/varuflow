"use client";

import { useEffect, useState, useCallback } from "react";
import {
  CalendarOff, Plus, Loader2, Check, X, Download, ChevronLeft, ChevronRight,
  Calendar, Users2, Globe, BarChart2,
} from "lucide-react";
import { toast } from "sonner";
import { api } from "@/lib/api-client";

// ── Types ─────────────────────────────────────────────────────────────────────

type Tab = "requests" | "calendar" | "entitlements" | "holidays";

interface LeaveRequest {
  id: string;
  staff_id: string;
  staff_name?: string;
  leave_type: string;
  start_date: string;
  end_date: string;
  half_day: boolean;
  reason: string | null;
  status: string;
  reviewer_note: string | null;
  rejection_reason: string | null;
  created_at: string;
}

interface Balance {
  leave_type: string;
  days_allocated: number;
  days_used: number;
  days_pending: number;
  days_remaining: number;
}

interface CalendarEntry {
  staff_name: string;
  leave_type: string;
  start_date: string;
  end_date: string;
  status: string;
}

interface CalendarData {
  week_start: string;
  week_end: string;
  leaves: CalendarEntry[];
  public_holidays: { date: string; name: string }[];
}

interface Entitlement {
  id: string;
  staff_id: string;
  leave_type: string;
  year: number;
  days_allocated: number;
  carry_over_days: number;
  carry_over_cap: number | null;
}

interface StaffMember {
  id: string;
  name: string;
}

interface Holiday {
  id: string;
  country_code: string;
  holiday_date: string;
  name: string;
  year: number;
}

// ── Constants ─────────────────────────────────────────────────────────────────

const TYPE_COLORS: Record<string, string> = {
  annual: "bg-blue-100 text-blue-800",
  sick: "bg-orange-100 text-orange-800",
  parental: "bg-purple-100 text-purple-800",
  unpaid: "bg-gray-100 text-gray-700",
  public_holiday: "bg-teal-100 text-teal-800",
  other: "bg-gray-100 text-gray-700",
};

const STATUS_COLORS: Record<string, string> = {
  pending: "bg-amber-100 text-amber-800",
  approved: "bg-emerald-100 text-emerald-800",
  rejected: "bg-rose-100 text-rose-700",
  cancelled: "bg-gray-100 text-gray-600",
};

const LEAVE_TYPES = ["annual", "sick", "parental", "unpaid", "public_holiday", "other"] as const;
const COUNTRIES = [{ code: "SE", label: "Sweden" }, { code: "AE", label: "UAE" }, { code: "SA", label: "Saudi Arabia" }, { code: "MA", label: "Morocco" }];

// ── Utilities ─────────────────────────────────────────────────────────────────

function isoMonday(d: Date): string {
  const day = d.getDay();
  const diff = d.getDate() - day + (day === 0 ? -6 : 1);
  const mon = new Date(d);
  mon.setDate(diff);
  return mon.toISOString().slice(0, 10);
}

function addDays(iso: string, n: number): string {
  const d = new Date(iso);
  d.setDate(d.getDate() + n);
  return d.toISOString().slice(0, 10);
}

function dayLabel(iso: string): string {
  return new Date(iso).toLocaleDateString("en-GB", { weekday: "short", day: "numeric", month: "short" });
}

// ── Main Component ────────────────────────────────────────────────────────────

export default function LeavePage() {
  const [tab, setTab] = useState<Tab>("requests");
  const [requests, setRequests] = useState<LeaveRequest[]>([]);
  const [loading, setLoading] = useState(true);
  const [statusFilter, setStatusFilter] = useState("pending");
  const [staffMembers, setStaffMembers] = useState<StaffMember[]>([]);

  // New request form
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState({ staff_id: "", leave_type: "annual", start_date: "", end_date: "", half_day: false, reason: "" });
  const [submitting, setSubmitting] = useState(false);

  // Reject modal
  const [rejectTarget, setRejectTarget] = useState<LeaveRequest | null>(null);
  const [rejectNote, setRejectNote] = useState("");

  // Balance
  const [balanceStaffId, setBalanceStaffId] = useState("");
  const [balances, setBalances] = useState<Balance[]>([]);
  const [balanceLoading, setBalanceLoading] = useState(false);

  // Calendar
  const [weekStart, setWeekStart] = useState(() => isoMonday(new Date()));
  const [calData, setCalData] = useState<CalendarData | null>(null);
  const [calLoading, setCalLoading] = useState(false);
  const [calCountry, setCalCountry] = useState("SE");

  // Entitlements
  const [entitlements, setEntitlements] = useState<Entitlement[]>([]);
  const [entLoading, setEntLoading] = useState(false);
  const [entForm, setEntForm] = useState({ staff_id: "", leave_type: "annual", year: new Date().getFullYear(), days_allocated: "", carry_over_days: "0", carry_over_cap: "" });

  // Holidays
  const [holidays, setHolidays] = useState<Holiday[]>([]);
  const [holLoading, setHolLoading] = useState(false);
  const [holCountry, setHolCountry] = useState("SE");
  const [holYear, setHolYear] = useState(2026);
  const [seeding, setSeeding] = useState(false);

  // ── Load requests & staff ──────────────────────────────────────────────────

  const loadRequests = useCallback(async () => {
    setLoading(true);
    try {
      const [data, staff] = await Promise.all([
        api.get("/api/hr/leave"),
        api.get("/api/hr/employees"),
      ]);
      setRequests(data);
      setStaffMembers(staff.map((s: { id: string; name: string }) => ({ id: s.id, name: s.name })));
    } catch {
      toast.error("Failed to load leave data");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { loadRequests(); }, [loadRequests]);

  // ── Calendar load ──────────────────────────────────────────────────────────

  const loadCalendar = useCallback(async () => {
    setCalLoading(true);
    try {
      const data = await api.get(`/api/hr/leave/calendar?week_start=${weekStart}&country_code=${calCountry}`);
      setCalData(data);
    } catch {
      toast.error("Failed to load calendar");
    } finally {
      setCalLoading(false);
    }
  }, [weekStart, calCountry]);

  useEffect(() => {
    if (tab === "calendar") loadCalendar();
  }, [tab, loadCalendar]);

  // ── Entitlements load ──────────────────────────────────────────────────────

  const loadEntitlements = useCallback(async () => {
    setEntLoading(true);
    try {
      const data = await api.get(`/api/hr/leave/entitlements?year=${new Date().getFullYear()}`);
      setEntitlements(data);
    } catch {
      toast.error("Failed to load entitlements");
    } finally {
      setEntLoading(false);
    }
  }, []);

  useEffect(() => {
    if (tab === "entitlements") loadEntitlements();
  }, [tab, loadEntitlements]);

  // ── Holidays load ──────────────────────────────────────────────────────────

  const loadHolidays = useCallback(async () => {
    setHolLoading(true);
    try {
      const data = await api.get(`/api/hr/leave/holidays?country_code=${holCountry}&year=${holYear}`);
      setHolidays(data);
    } catch {
      toast.error("Failed to load holidays");
    } finally {
      setHolLoading(false);
    }
  }, [holCountry, holYear]);

  useEffect(() => {
    if (tab === "holidays") loadHolidays();
  }, [tab, loadHolidays]);

  // ── Balance load ──────────────────────────────────────────────────────────

  async function loadBalance(staffId: string) {
    if (!staffId) return;
    setBalanceLoading(true);
    try {
      const data = await api.get(`/api/hr/leave/balance/${staffId}`);
      setBalances(data.balances ?? []);
    } catch {
      toast.error("Failed to load balance");
    } finally {
      setBalanceLoading(false);
    }
  }

  // ── Actions ───────────────────────────────────────────────────────────────

  async function createRequest() {
    if (!form.staff_id || !form.start_date || !form.end_date) {
      toast.error("Staff, start date, and end date are required");
      return;
    }
    setSubmitting(true);
    try {
      const created = await api.post("/api/hr/leave", form);
      setRequests((r) => [{ ...created, staff_name: staffMembers.find((s) => s.id === form.staff_id)?.name }, ...r]);
      setShowForm(false);
      setForm({ staff_id: "", leave_type: "annual", start_date: "", end_date: "", half_day: false, reason: "" });
      toast.success("Request created");
    } catch {
      toast.error("Failed to create request");
    } finally {
      setSubmitting(false);
    }
  }

  async function approve(req: LeaveRequest) {
    try {
      const updated = await api.post(`/api/hr/leave/${req.id}/approve`, {});
      setRequests((r) => r.map((x) => (x.id === req.id ? { ...updated, staff_name: req.staff_name } : x)));
      toast.success("Approved");
    } catch {
      toast.error("Failed to approve");
    }
  }

  async function reject() {
    if (!rejectTarget) return;
    try {
      const updated = await api.post(`/api/hr/leave/${rejectTarget.id}/reject`, {
        rejection_reason: rejectNote,
        reviewer_note: rejectNote,
      });
      setRequests((r) => r.map((x) => (x.id === rejectTarget.id ? { ...updated, staff_name: rejectTarget.staff_name } : x)));
      setRejectTarget(null);
      setRejectNote("");
      toast.success("Rejected");
    } catch {
      toast.error("Failed to reject");
    }
  }

  async function upsertEntitlement() {
    if (!entForm.staff_id || !entForm.days_allocated) { toast.error("Staff and days are required"); return; }
    try {
      const created = await api.post("/api/hr/leave/entitlements", {
        ...entForm,
        days_allocated: parseFloat(entForm.days_allocated),
        carry_over_days: parseFloat(entForm.carry_over_days || "0"),
        carry_over_cap: entForm.carry_over_cap ? parseFloat(entForm.carry_over_cap) : null,
      });
      setEntitlements((e) => {
        const idx = e.findIndex((x) => x.id === created.id);
        return idx >= 0 ? e.map((x, i) => (i === idx ? created : x)) : [created, ...e];
      });
      toast.success("Entitlement saved");
    } catch {
      toast.error("Failed to save entitlement");
    }
  }

  async function seedHolidays() {
    setSeeding(true);
    try {
      const result = await api.post("/api/hr/leave/holidays/seed", { country_code: holCountry, year: holYear });
      toast.success(`Seeded ${result.inserted} holidays for ${holCountry} ${holYear}`);
      loadHolidays();
    } catch {
      toast.error("Failed to seed holidays");
    } finally {
      setSeeding(false);
    }
  }

  function downloadExport() {
    const from = new Date();
    const to = new Date(from.getFullYear(), 11, 31);
    const path = `/api/hr/leave/export?from_date=${from.toISOString().slice(0, 10)}&to_date=${to.toISOString().slice(0, 10)}`;
    api.downloadBlob(path, `leave_export_${from.getFullYear()}.csv`).catch(() => toast.error("Export failed"));
  }

  // ── Filtered requests ─────────────────────────────────────────────────────

  const filtered = statusFilter === "all" ? requests : requests.filter((r) => r.status === statusFilter);
  const pendingCount = requests.filter((r) => r.status === "pending").length;

  // ── Render ─────────────────────────────────────────────────────────────────

  const TABS: { key: Tab; label: string; badge?: number }[] = [
    { key: "requests", label: "Requests", badge: pendingCount || undefined },
    { key: "calendar", label: "Calendar" },
    { key: "entitlements", label: "Entitlements" },
    { key: "holidays", label: "Public Holidays" },
  ];

  return (
    <div className="vf-section">
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-2">
          <CalendarOff className="w-5 h-5 text-vf-accent" />
          <h1 className="vf-text-1 text-xl font-semibold">Leave Management</h1>
        </div>
        {tab === "requests" && (
          <div className="flex gap-2">
            <button onClick={downloadExport} className="vf-btn-ghost flex items-center gap-1.5">
              <Download className="w-4 h-4" /> Export CSV
            </button>
            <button onClick={() => setShowForm((x) => !x)} className="vf-btn flex items-center gap-1.5">
              <Plus className="w-4 h-4" /> New Request
            </button>
          </div>
        )}
      </div>

      {/* Tabs */}
      <div className="flex gap-1 border-b mb-6">
        {TABS.map((t) => (
          <button
            key={t.key}
            onClick={() => setTab(t.key)}
            className={`px-4 py-2 text-sm font-medium border-b-2 -mb-px flex items-center gap-1.5 transition-colors ${tab === t.key ? "border-primary text-primary" : "border-transparent text-muted-foreground hover:text-foreground"}`}
          >
            {t.label}
            {t.badge ? <span className="bg-amber-500 text-white text-xs rounded-full px-1.5 py-0.5 leading-none">{t.badge}</span> : null}
          </button>
        ))}
      </div>

      {/* ── REQUESTS TAB ────────────────────────────────────────────────── */}
      {tab === "requests" && (
        <div>
          {/* Balance lookup */}
          <div className="border rounded-lg p-4 mb-5 bg-muted/30">
            <div className="flex items-center gap-2 mb-3">
              <BarChart2 className="w-4 h-4 text-vf-accent" />
              <span className="text-sm font-medium">Leave Balance</span>
            </div>
            <div className="flex gap-2 items-end">
              <div className="flex-1 max-w-xs">
                <label className="text-xs text-muted-foreground">Select employee</label>
                <select
                  className="vf-input w-full mt-1"
                  value={balanceStaffId}
                  onChange={(e) => { setBalanceStaffId(e.target.value); loadBalance(e.target.value); }}
                >
                  <option value="">— pick staff —</option>
                  {staffMembers.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
                </select>
              </div>
              {balanceLoading && <Loader2 className="w-4 h-4 animate-spin text-vf-accent" />}
            </div>
            {balances.length > 0 && (
              <div className="mt-3 grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-2">
                {balances.map((b) => (
                  <div key={b.leave_type} className="bg-background border rounded-lg p-3 text-center">
                    <span className={`text-xs px-1.5 py-0.5 rounded-full font-medium capitalize ${TYPE_COLORS[b.leave_type] ?? "bg-gray-100"}`}>{b.leave_type}</span>
                    <p className="text-2xl font-bold mt-1">{b.days_remaining}</p>
                    <p className="text-xs text-muted-foreground">remaining</p>
                    <p className="text-xs text-muted-foreground">{b.days_used} used · {b.days_pending} pending</p>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* New request form */}
          {showForm && (
            <div className="border rounded-lg p-4 mb-5 grid grid-cols-2 gap-3 max-w-lg bg-muted/30">
              <div>
                <label className="text-xs font-medium text-muted-foreground">Employee *</label>
                <select className="vf-input w-full mt-1" value={form.staff_id} onChange={(e) => setForm((f) => ({ ...f, staff_id: e.target.value }))}>
                  <option value="">— select —</option>
                  {staffMembers.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
                </select>
              </div>
              <div>
                <label className="text-xs font-medium text-muted-foreground">Leave Type *</label>
                <select className="vf-input w-full mt-1" value={form.leave_type} onChange={(e) => setForm((f) => ({ ...f, leave_type: e.target.value }))}>
                  {LEAVE_TYPES.map((t) => <option key={t} value={t}>{t.replace("_", " ")}</option>)}
                </select>
              </div>
              <div>
                <label className="text-xs font-medium text-muted-foreground">Start Date *</label>
                <input type="date" className="vf-input w-full mt-1" value={form.start_date} onChange={(e) => setForm((f) => ({ ...f, start_date: e.target.value }))} />
              </div>
              <div>
                <label className="text-xs font-medium text-muted-foreground">End Date *</label>
                <input type="date" className="vf-input w-full mt-1" value={form.end_date} onChange={(e) => setForm((f) => ({ ...f, end_date: e.target.value }))} />
              </div>
              <div className="col-span-2">
                <label className="text-xs font-medium text-muted-foreground">Reason</label>
                <input className="vf-input w-full mt-1" value={form.reason} onChange={(e) => setForm((f) => ({ ...f, reason: e.target.value }))} />
              </div>
              <div className="col-span-2 flex items-center gap-2">
                <input type="checkbox" id="half_day" checked={form.half_day} onChange={(e) => setForm((f) => ({ ...f, half_day: e.target.checked }))} />
                <label htmlFor="half_day" className="text-xs text-muted-foreground">Half day</label>
              </div>
              <div className="col-span-2 flex gap-2">
                <button onClick={createRequest} disabled={submitting} className="vf-btn flex items-center gap-2">
                  {submitting && <Loader2 className="w-3 h-3 animate-spin" />} Submit
                </button>
                <button onClick={() => setShowForm(false)} className="vf-btn-ghost">Cancel</button>
              </div>
            </div>
          )}

          {/* Status filter */}
          <div className="flex gap-1 mb-4 border-b pb-2">
            {["pending", "approved", "rejected", "cancelled", "all"].map((s) => (
              <button key={s} onClick={() => setStatusFilter(s)} className={`px-3 py-1 text-xs rounded-full capitalize transition-colors ${statusFilter === s ? "bg-primary text-primary-foreground" : "bg-muted text-muted-foreground hover:text-foreground"}`}>
                {s}
              </button>
            ))}
          </div>

          {loading ? (
            <div className="flex items-center justify-center h-40"><Loader2 className="w-6 h-6 animate-spin text-vf-accent" /></div>
          ) : filtered.length === 0 ? (
            <p className="vf-text-m text-muted-foreground">No requests found.</p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b text-left text-muted-foreground">
                    <th className="py-2 pr-4 font-medium">Employee</th>
                    <th className="py-2 pr-4 font-medium">Type</th>
                    <th className="py-2 pr-4 font-medium">Dates</th>
                    <th className="py-2 pr-4 font-medium">Status</th>
                    <th className="py-2 font-medium">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y">
                  {filtered.map((r) => (
                    <tr key={r.id} className="hover:bg-muted/30">
                      <td className="py-2 pr-4 font-medium">{r.staff_name ?? r.staff_id.slice(0, 8)}</td>
                      <td className="py-2 pr-4">
                        <span className={`text-xs px-2 py-0.5 rounded-full font-medium capitalize ${TYPE_COLORS[r.leave_type] ?? "bg-gray-100"}`}>{r.leave_type.replace("_", " ")}</span>
                      </td>
                      <td className="py-2 pr-4 text-muted-foreground">
                        {r.start_date} → {r.end_date}{r.half_day ? " (½)" : ""}
                      </td>
                      <td className="py-2 pr-4">
                        <span className={`text-xs px-2 py-0.5 rounded-full font-medium capitalize ${STATUS_COLORS[r.status] ?? "bg-gray-100"}`}>{r.status}</span>
                        {r.rejection_reason && <p className="text-xs text-muted-foreground mt-0.5">{r.rejection_reason}</p>}
                      </td>
                      <td className="py-2">
                        {r.status === "pending" && (
                          <div className="flex gap-1">
                            <button onClick={() => approve(r)} className="p-1.5 rounded hover:bg-emerald-100 text-emerald-700" title="Approve">
                              <Check className="w-3.5 h-3.5" />
                            </button>
                            <button onClick={() => setRejectTarget(r)} className="p-1.5 rounded hover:bg-rose-100 text-rose-700" title="Reject">
                              <X className="w-3.5 h-3.5" />
                            </button>
                          </div>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {/* ── CALENDAR TAB ────────────────────────────────────────────────── */}
      {tab === "calendar" && (
        <div>
          <div className="flex items-center gap-3 mb-4">
            <button onClick={() => setWeekStart(addDays(weekStart, -7))} className="vf-btn-ghost p-1"><ChevronLeft className="w-4 h-4" /></button>
            <span className="text-sm font-medium">{dayLabel(weekStart)} — {dayLabel(addDays(weekStart, 6))}</span>
            <button onClick={() => setWeekStart(addDays(weekStart, 7))} className="vf-btn-ghost p-1"><ChevronRight className="w-4 h-4" /></button>
            <select className="vf-input ml-auto w-36" value={calCountry} onChange={(e) => setCalCountry(e.target.value)}>
              {COUNTRIES.map((c) => <option key={c.code} value={c.code}>{c.label}</option>)}
            </select>
          </div>

          {calLoading ? (
            <div className="flex items-center justify-center h-40"><Loader2 className="w-6 h-6 animate-spin text-vf-accent" /></div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-xs border-collapse">
                <thead>
                  <tr>
                    {Array.from({ length: 7 }, (_, i) => addDays(weekStart, i)).map((day) => {
                      const isHoliday = calData?.public_holidays.some((h) => h.date === day);
                      return (
                        <th key={day} className={`py-2 px-2 text-center font-medium border ${isHoliday ? "bg-teal-50 text-teal-700" : "bg-muted/30"}`}>
                          <div>{new Date(day).toLocaleDateString("en-GB", { weekday: "short" })}</div>
                          <div className="font-bold">{new Date(day).getDate()}</div>
                          {isHoliday && <div className="text-teal-600 text-[10px]">{calData?.public_holidays.find((h) => h.date === day)?.name}</div>}
                        </th>
                      );
                    })}
                  </tr>
                </thead>
                <tbody>
                  {(() => {
                    const leavesByStaff: Record<string, { name: string; byDay: Record<string, { type: string; status: string }> }> = {};
                    for (const l of calData?.leaves ?? []) {
                      if (!leavesByStaff[l.staff_name]) leavesByStaff[l.staff_name] = { name: l.staff_name, byDay: {} };
                      for (let i = 0; i < 7; i++) {
                        const d = addDays(weekStart, i);
                        if (d >= l.start_date && d <= l.end_date) {
                          leavesByStaff[l.staff_name].byDay[d] = { type: l.leave_type, status: l.status };
                        }
                      }
                    }
                    const entries = Object.values(leavesByStaff);
                    if (entries.length === 0) return (
                      <tr><td colSpan={7} className="text-center text-muted-foreground py-8">No leave this week.</td></tr>
                    );
                    return entries.map((e) => (
                      <tr key={e.name} className="border-b">
                        {Array.from({ length: 7 }, (_, i) => addDays(weekStart, i)).map((day) => {
                          const cell = e.byDay[day];
                          return (
                            <td key={day} className="border px-2 py-2 text-center align-top min-w-[80px]">
                              {cell ? (
                                <div>
                                  <span className={`text-[10px] px-1.5 py-0.5 rounded-full font-medium capitalize ${TYPE_COLORS[cell.type] ?? "bg-gray-100"}`}>{cell.type.replace("_", " ")}</span>
                                  <div className="text-[10px] text-muted-foreground mt-0.5">{e.name.split(" ")[0]}</div>
                                  {cell.status === "pending" && <div className="text-[10px] text-amber-600">pending</div>}
                                </div>
                              ) : null}
                            </td>
                          );
                        })}
                      </tr>
                    ));
                  })()}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {/* ── ENTITLEMENTS TAB ─────────────────────────────────────────────── */}
      {tab === "entitlements" && (
        <div>
          <div className="border rounded-lg p-4 mb-5 grid grid-cols-2 sm:grid-cols-3 gap-3 max-w-2xl bg-muted/30">
            <div>
              <label className="text-xs font-medium text-muted-foreground">Employee *</label>
              <select className="vf-input w-full mt-1" value={entForm.staff_id} onChange={(e) => setEntForm((f) => ({ ...f, staff_id: e.target.value }))}>
                <option value="">— select —</option>
                {staffMembers.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
              </select>
            </div>
            <div>
              <label className="text-xs font-medium text-muted-foreground">Leave Type</label>
              <select className="vf-input w-full mt-1" value={entForm.leave_type} onChange={(e) => setEntForm((f) => ({ ...f, leave_type: e.target.value }))}>
                {LEAVE_TYPES.filter((t) => t !== "public_holiday" && t !== "other").map((t) => <option key={t} value={t}>{t}</option>)}
              </select>
            </div>
            <div>
              <label className="text-xs font-medium text-muted-foreground">Year</label>
              <input type="number" className="vf-input w-full mt-1" value={entForm.year} onChange={(e) => setEntForm((f) => ({ ...f, year: parseInt(e.target.value) }))} />
            </div>
            <div>
              <label className="text-xs font-medium text-muted-foreground">Days Allocated *</label>
              <input type="number" className="vf-input w-full mt-1" placeholder="25" value={entForm.days_allocated} onChange={(e) => setEntForm((f) => ({ ...f, days_allocated: e.target.value }))} />
            </div>
            <div>
              <label className="text-xs font-medium text-muted-foreground">Carry-over Days</label>
              <input type="number" className="vf-input w-full mt-1" value={entForm.carry_over_days} onChange={(e) => setEntForm((f) => ({ ...f, carry_over_days: e.target.value }))} />
            </div>
            <div>
              <label className="text-xs font-medium text-muted-foreground">Carry-over Cap</label>
              <input type="number" className="vf-input w-full mt-1" placeholder="(none = uncapped)" value={entForm.carry_over_cap} onChange={(e) => setEntForm((f) => ({ ...f, carry_over_cap: e.target.value }))} />
            </div>
            <div className="col-span-2 sm:col-span-3">
              <button onClick={upsertEntitlement} className="vf-btn">Save Entitlement</button>
            </div>
          </div>

          {entLoading ? (
            <div className="flex items-center justify-center h-20"><Loader2 className="w-5 h-5 animate-spin text-vf-accent" /></div>
          ) : entitlements.length === 0 ? (
            <p className="vf-text-m text-muted-foreground">No entitlements configured yet.</p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b text-muted-foreground text-left">
                    <th className="py-2 pr-4 font-medium">Employee</th>
                    <th className="py-2 pr-4 font-medium">Type</th>
                    <th className="py-2 pr-4 font-medium">Year</th>
                    <th className="py-2 pr-4 font-medium">Allocated</th>
                    <th className="py-2 pr-4 font-medium">Carry-over</th>
                    <th className="py-2 font-medium">Cap</th>
                  </tr>
                </thead>
                <tbody className="divide-y">
                  {entitlements.map((e) => (
                    <tr key={e.id}>
                      <td className="py-2 pr-4 text-muted-foreground">{staffMembers.find((s) => s.id === e.staff_id)?.name ?? e.staff_id.slice(0, 8)}</td>
                      <td className="py-2 pr-4">
                        <span className={`text-xs px-2 py-0.5 rounded-full font-medium capitalize ${TYPE_COLORS[e.leave_type] ?? "bg-gray-100"}`}>{e.leave_type}</span>
                      </td>
                      <td className="py-2 pr-4">{e.year}</td>
                      <td className="py-2 pr-4 font-semibold">{e.days_allocated}</td>
                      <td className="py-2 pr-4">{e.carry_over_days}</td>
                      <td className="py-2">{e.carry_over_cap ?? "—"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {/* ── HOLIDAYS TAB ─────────────────────────────────────────────────── */}
      {tab === "holidays" && (
        <div>
          <div className="flex items-center gap-3 mb-4 flex-wrap">
            <select className="vf-input w-36" value={holCountry} onChange={(e) => setHolCountry(e.target.value)}>
              {COUNTRIES.map((c) => <option key={c.code} value={c.code}>{c.label}</option>)}
            </select>
            <select className="vf-input w-24" value={holYear} onChange={(e) => setHolYear(parseInt(e.target.value))}>
              {[2025, 2026, 2027].map((y) => <option key={y} value={y}>{y}</option>)}
            </select>
            <button onClick={seedHolidays} disabled={seeding} className="vf-btn flex items-center gap-2">
              {seeding ? <Loader2 className="w-3 h-3 animate-spin" /> : <Globe className="w-4 h-4" />}
              Seed {holCountry} {holYear}
            </button>
          </div>

          {holLoading ? (
            <div className="flex items-center justify-center h-32"><Loader2 className="w-5 h-5 animate-spin text-vf-accent" /></div>
          ) : holidays.length === 0 ? (
            <p className="vf-text-m text-muted-foreground">No holidays loaded. Click &ldquo;Seed&rdquo; to import preset holiday data.</p>
          ) : (
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-2">
              {holidays.map((h) => (
                <div key={h.id} className="border rounded-lg p-3 flex items-center justify-between">
                  <div>
                    <p className="text-sm font-medium">{h.name}</p>
                    <p className="text-xs text-muted-foreground">{new Date(h.holiday_date).toLocaleDateString("en-GB", { weekday: "long", day: "numeric", month: "long" })}</p>
                  </div>
                  <span className="text-xs bg-teal-100 text-teal-700 px-2 py-0.5 rounded-full">{h.country_code}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Reject modal */}
      {rejectTarget && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50">
          <div className="bg-background rounded-xl shadow-xl p-6 max-w-sm w-full">
            <h3 className="font-semibold vf-text-1 mb-1">Decline Leave Request</h3>
            <p className="text-sm text-muted-foreground mb-4">
              {rejectTarget.staff_name} · {rejectTarget.leave_type} · {rejectTarget.start_date} → {rejectTarget.end_date}
            </p>
            <textarea
              className="vf-input w-full h-24 resize-none mb-4"
              placeholder="Reason (optional)"
              value={rejectNote}
              onChange={(e) => setRejectNote(e.target.value)}
            />
            <div className="flex gap-2 justify-end">
              <button onClick={() => { setRejectTarget(null); setRejectNote(""); }} className="vf-btn-ghost">Cancel</button>
              <button onClick={reject} className="px-4 py-1.5 text-sm rounded bg-rose-600 text-white hover:bg-rose-700 transition-colors">Decline</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
