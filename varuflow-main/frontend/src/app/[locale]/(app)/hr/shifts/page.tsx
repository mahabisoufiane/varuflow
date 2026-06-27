"use client";

import { useEffect, useState, useCallback, useRef } from "react";
import {
  CalendarDays, ChevronLeft, ChevronRight, Plus, Loader2,
  Printer, Send, Copy, Check, X, AlertTriangle,
} from "lucide-react";
import { toast } from "sonner";
import { api } from "@/lib/api-client";
import styles from "./page.module.scss";

// ── Types ─────────────────────────────────────────────────────────────────────

type View = "week" | "month";
type Tab = "roster" | "swaps";

interface ShiftEntry {
  id: string;
  staff_id: string;
  staff_name: string;
  start_at: string;
  end_at: string;
  notes: string | null;
  color: string | null;
  roster_week: string | null;
}

interface RosterData {
  week_start: string;
  published: boolean;
  published_at: string | null;
  shifts: ShiftEntry[];
}

interface StaffMember {
  id: string;
  name: string;
}

interface SwapRequest {
  id: string;
  requester_shift_id: string;
  requester_staff_id: string;
  target_staff_id: string;
  target_shift_id: string | null;
  status: string;
  requester_note: string | null;
  manager_notes: string | null;
  created_at: string;
}

interface MonthShift {
  id: string;
  staff_id: string;
  staff_name: string;
  start_at: string;
  color: string | null;
}

// ── Constants ─────────────────────────────────────────────────────────────────

const STAFF_PALETTE = [
  "#2563EB", "#D97706", "#059669", "#DC2626",
  "#3b82f6", "#7C3AED", "#f97316", "#14b8a6",
];

const DAY_LABELS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];

// ── Utilities ─────────────────────────────────────────────────────────────────

function isoMonday(d: Date): string {
  const day = d.getDay();
  const diff = d.getDate() - day + (day === 0 ? -6 : 1);
  const mon = new Date(d);
  mon.setDate(diff);
  return mon.toISOString().slice(0, 10);
}

function addDays(iso: string, n: number): string {
  const d = new Date(iso + "T00:00:00Z");
  d.setUTCDate(d.getUTCDate() + n);
  return d.toISOString().slice(0, 10);
}

function formatTime(iso: string): string {
  const d = new Date(iso);
  return d.toLocaleTimeString("en-GB", { hour: "2-digit", minute: "2-digit" });
}

function isoToDate(iso: string): string {
  return iso.slice(0, 10);
}

function staffColor(staffId: string, staffList: StaffMember[]): string {
  const idx = staffList.findIndex((s) => s.id === staffId);
  return STAFF_PALETTE[idx % STAFF_PALETTE.length];
}

function moveShiftToDate(shiftIso: string, newDate: string): string {
  // Keep time, change date
  const timePart = new Date(shiftIso).toISOString().slice(11); // "HH:MM:SS.sssZ"
  return `${newDate}T${timePart}`;
}

// ── Main Component ────────────────────────────────────────────────────────────

export default function ShiftsPage() {
  const [tab, setTab] = useState<Tab>("roster");
  const [view, setView] = useState<View>("week");
  const [weekStart, setWeekStart] = useState(() => isoMonday(new Date()));
  const [roster, setRoster] = useState<RosterData | null>(null);
  const [staff, setStaff] = useState<StaffMember[]>([]);
  const [loading, setLoading] = useState(true);
  const [publishing, setPublishing] = useState(false);
  const [copying, setCopying] = useState(false);

  // Month view
  const [monthShifts, setMonthShifts] = useState<MonthShift[]>([]);
  const [monthLoading, setMonthLoading] = useState(false);

  // Add/edit modal
  const [showModal, setShowModal] = useState(false);
  const [editShift, setEditShift] = useState<ShiftEntry | null>(null);
  const [form, setForm] = useState({ staff_id: "", date: "", start_time: "09:00", end_time: "17:00", notes: "", color: "" });
  const [saving, setSaving] = useState(false);

  // Drag state
  const dragId = useRef<string | null>(null);
  const dragStaffId = useRef<string | null>(null);

  // Swap state
  const [swaps, setSwaps] = useState<SwapRequest[]>([]);
  const [swapsLoading, setSwapsLoading] = useState(false);
  const [swapForm, setSwapForm] = useState({ requester_shift_id: "", requester_staff_id: "", target_staff_id: "", requester_note: "" });

  // ── Load data ────────────────────────────────────────────────────────────

  const loadRoster = useCallback(async () => {
    setLoading(true);
    try {
      const [rosterData, empData] = await Promise.all([
        api.get(`/api/shifts/roster?week_start=${weekStart}`),
        api.get("/api/hr/employees"),
      ]);
      setRoster(rosterData);
      setStaff(empData.map((e: { id: string; name: string }) => ({ id: e.id, name: e.name })));
    } catch {
      toast.error("Failed to load roster");
    } finally {
      setLoading(false);
    }
  }, [weekStart]);

  useEffect(() => {
    if (tab === "roster" && view === "week") loadRoster();
  }, [tab, view, loadRoster]);

  // Month view: load all shifts for the month
  const loadMonthShifts = useCallback(async () => {
    setMonthLoading(true);
    try {
      const d = new Date(weekStart + "T00:00:00Z");
      const monthStart = new Date(Date.UTC(d.getUTCFullYear(), d.getUTCMonth(), 1));
      const monthEnd = new Date(Date.UTC(d.getUTCFullYear(), d.getUTCMonth() + 1, 1));
      const [shiftsData, empData] = await Promise.all([
        api.get(`/api/shifts?start=${monthStart.toISOString()}&end=${monthEnd.toISOString()}`),
        staff.length ? Promise.resolve(staff) : api.get("/api/hr/employees"),
      ]);
      const staffList = Array.isArray(empData) ? empData.map((e: { id: string; name: string }) => ({ id: e.id, name: e.name })) : staff;
      if (staffList !== staff) setStaff(staffList);
      setMonthShifts(
        (shiftsData as ShiftEntry[]).map((s) => ({
          id: s.id,
          staff_id: s.staff_id,
          staff_name: s.staff_name || staffList.find((sm: StaffMember) => sm.id === s.staff_id)?.name || "Unknown",
          start_at: s.start_at,
          color: s.color,
        }))
      );
    } catch {
      toast.error("Failed to load month view");
    } finally {
      setMonthLoading(false);
    }
  }, [weekStart, staff]);

  useEffect(() => {
    if (tab === "roster" && view === "month") loadMonthShifts();
  }, [tab, view, loadMonthShifts]);

  // Swaps
  const loadSwaps = useCallback(async () => {
    setSwapsLoading(true);
    try {
      const data = await api.get("/api/shifts/swaps");
      setSwaps(data);
    } catch {
      toast.error("Failed to load swap requests");
    } finally {
      setSwapsLoading(false);
    }
  }, []);

  useEffect(() => {
    if (tab === "swaps") loadSwaps();
  }, [tab, loadSwaps]);

  // ── Actions ───────────────────────────────────────────────────────────────

  async function publishRoster() {
    setPublishing(true);
    try {
      await api.post(`/api/shifts/roster/publish?week_start=${weekStart}`, {});
      toast.success("Roster published — staff notified");
      loadRoster();
    } catch {
      toast.error("Failed to publish");
    } finally {
      setPublishing(false);
    }
  }

  async function copyLastWeek() {
    setCopying(true);
    try {
      const result = await api.post(`/api/shifts/roster/copy-last-week?week_start=${weekStart}`, {});
      toast.success(`Copied ${result.created} shifts from last week`);
      loadRoster();
    } catch (e: unknown) {
      const msg = (e as { detail?: string })?.detail;
      toast.error(msg ?? "No shifts to copy from last week");
    } finally {
      setCopying(false);
    }
  }

  function openAdd(staffId: string, day: string) {
    setEditShift(null);
    setForm({ staff_id: staffId, date: day, start_time: "09:00", end_time: "17:00", notes: "", color: staffColor(staffId, staff) });
    setShowModal(true);
  }

  function openEdit(shift: ShiftEntry) {
    setEditShift(shift);
    const d = isoToDate(shift.start_at);
    setForm({
      staff_id: shift.staff_id,
      date: d,
      start_time: formatTime(shift.start_at),
      end_time: formatTime(shift.end_at),
      notes: shift.notes ?? "",
      color: shift.color ?? staffColor(shift.staff_id, staff),
    });
    setShowModal(true);
  }

  async function saveShift() {
    if (!form.staff_id || !form.date) { toast.error("Staff and date required"); return; }
    setSaving(true);
    try {
      const start_at = `${form.date}T${form.start_time}:00Z`;
      const end_at = `${form.date}T${form.end_time}:00Z`;
      if (editShift) {
        const updated = await api.patch(`/api/shifts/${editShift.id}`, { start_at, end_at, notes: form.notes || null, color: form.color || null });
        setRoster((r) => r ? { ...r, shifts: r.shifts.map((s) => s.id === editShift.id ? { ...s, ...updated, staff_name: editShift.staff_name } : s) } : r);
      } else {
        const created = await api.post("/api/shifts", { staff_id: form.staff_id, start_at, end_at, notes: form.notes || null, color: form.color || null });
        const sName = staff.find((s) => s.id === form.staff_id)?.name ?? "";
        setRoster((r) => r ? { ...r, shifts: [...r.shifts, { ...created, staff_name: sName }] } : r);
      }
      setShowModal(false);
      toast.success(editShift ? "Shift updated" : "Shift created");
    } catch (e: unknown) {
      const detail = (e as { detail?: string })?.detail;
      if (detail?.includes("overlap")) toast.error("Overlaps an existing shift");
      else if (detail?.includes("rest")) toast.error(`Rest period violation: ${detail}`);
      else toast.error("Failed to save shift");
    } finally {
      setSaving(false);
    }
  }

  async function deleteShift(id: string) {
    try {
      await api.delete(`/api/shifts/${id}`);
      setRoster((r) => r ? { ...r, shifts: r.shifts.filter((s) => s.id !== id) } : r);
      setShowModal(false);
      toast.success("Shift deleted");
    } catch {
      toast.error("Failed to delete shift");
    }
  }

  // Drag-to-move (same staff, different day)
  function onDragStart(shift: ShiftEntry) {
    dragId.current = shift.id;
    dragStaffId.current = shift.staff_id;
  }

  async function onDropCell(staffId: string, day: string) {
    if (!dragId.current || dragStaffId.current !== staffId) {
      dragId.current = null;
      dragStaffId.current = null;
      return;
    }
    const shiftId = dragId.current;
    dragId.current = null;
    dragStaffId.current = null;
    const shift = roster?.shifts.find((s) => s.id === shiftId);
    if (!shift) return;
    if (isoToDate(shift.start_at) === day) return; // same day, no move
    const newStart = moveShiftToDate(shift.start_at, day);
    const newEnd = moveShiftToDate(shift.end_at, day);
    try {
      const updated = await api.patch(`/api/shifts/${shiftId}`, { start_at: newStart, end_at: newEnd });
      setRoster((r) => r ? { ...r, shifts: r.shifts.map((s) => s.id === shiftId ? { ...s, ...updated, staff_name: shift.staff_name } : s) } : r);
      toast.success("Shift moved");
    } catch (e: unknown) {
      const detail = (e as { detail?: string })?.detail;
      if (detail?.includes("overlap")) toast.error("Cannot move — overlaps another shift");
      else if (detail?.includes("rest")) toast.error("Cannot move — rest period violation");
      else toast.error("Failed to move shift");
    }
  }

  // Swaps
  async function resolveSwap(id: string, action: "approve" | "reject") {
    try {
      await api.post(`/api/shifts/swaps/${id}/${action}`, {});
      setSwaps((s) => s.map((x) => x.id === id ? { ...x, status: action === "approve" ? "approved" : "rejected" } : x));
      toast.success(action === "approve" ? "Swap approved" : "Swap rejected");
    } catch {
      toast.error(`Failed to ${action} swap`);
    }
  }

  // ── Derived data ──────────────────────────────────────────────────────────

  // Matrix: staffId → dayIso → ShiftEntry[]
  const days = Array.from({ length: 7 }, (_, i) => addDays(weekStart, i));
  const shiftsByStaffDay: Record<string, Record<string, ShiftEntry[]>> = {};
  for (const shift of roster?.shifts ?? []) {
    const day = isoToDate(shift.start_at);
    if (!shiftsByStaffDay[shift.staff_id]) shiftsByStaffDay[shift.staff_id] = {};
    if (!shiftsByStaffDay[shift.staff_id][day]) shiftsByStaffDay[shift.staff_id][day] = [];
    shiftsByStaffDay[shift.staff_id][day].push(shift);
  }

  // All staff that appear in this week's roster + staff list
  const weekStaff = Array.from(
    new Map([
      ...staff.map((s) => [s.id, s] as [string, StaffMember]),
      ...(roster?.shifts ?? []).map((s) => [s.staff_id, { id: s.staff_id, name: s.staff_name }] as [string, StaffMember]),
    ]).values()
  );

  const pendingSwaps = swaps.filter((s) => s.status === "pending").length;

  // ── Month view data ───────────────────────────────────────────────────────

  function getMonthDays(): { date: string; isCurrentMonth: boolean }[] {
    const d = new Date(weekStart + "T00:00:00Z");
    const year = d.getUTCFullYear();
    const month = d.getUTCMonth();
    const firstDay = new Date(Date.UTC(year, month, 1));
    const lastDay = new Date(Date.UTC(year, month + 1, 0));
    // Pad to Monday
    const startPad = firstDay.getUTCDay() === 0 ? 6 : firstDay.getUTCDay() - 1;
    const endPad = lastDay.getUTCDay() === 0 ? 0 : 7 - lastDay.getUTCDay();
    const cells: { date: string; isCurrentMonth: boolean }[] = [];
    for (let i = startPad; i > 0; i--) {
      const dd = new Date(firstDay);
      dd.setUTCDate(dd.getUTCDate() - i);
      cells.push({ date: dd.toISOString().slice(0, 10), isCurrentMonth: false });
    }
    for (let i = 1; i <= lastDay.getUTCDate(); i++) {
      cells.push({ date: new Date(Date.UTC(year, month, i)).toISOString().slice(0, 10), isCurrentMonth: true });
    }
    for (let i = 1; i <= endPad; i++) {
      const dd = new Date(lastDay);
      dd.setUTCDate(dd.getUTCDate() + i);
      cells.push({ date: dd.toISOString().slice(0, 10), isCurrentMonth: false });
    }
    return cells;
  }

  const monthDays = view === "month" ? getMonthDays() : [];
  const shiftsByDay: Record<string, MonthShift[]> = {};
  for (const s of monthShifts) {
    const d = isoToDate(s.start_at);
    if (!shiftsByDay[d]) shiftsByDay[d] = [];
    shiftsByDay[d].push(s);
  }

  // ── Render ─────────────────────────────────────────────────────────────────

  return (
    <div className="vf-section print:p-0" id="shift-roster">
      {/* Header */}
      <div className="flex items-center justify-between mb-4 print:hidden">
        <div className="flex items-center gap-2">
          <CalendarDays className="w-5 h-5 text-vf-accent" />
          <h1 className="vf-text-1 text-xl font-semibold">Shift Roster</h1>
        </div>
        <div className="flex gap-2">
          <button onClick={() => window.print()} className="vf-btn-ghost flex items-center gap-1.5 text-sm">
            <Printer className="w-4 h-4" /> Print
          </button>
        </div>
      </div>

      {/* Tabs */}
      <div className={`${styles.tabBar} print:hidden`}>
        {[
          { key: "roster" as Tab, label: "Roster" },
          { key: "swaps" as Tab, label: "Swaps", badge: pendingSwaps || undefined },
        ].map((t) => (
          <button
            key={t.key}
            onClick={() => setTab(t.key)}
            className={`${styles.tab} ${tab === t.key ? styles.tabActive : ""} flex items-center gap-1.5`}
          >
            {t.label}
            {t.badge ? <span className="bg-amber-500 text-white text-xs rounded-full px-1.5 py-0.5 leading-none">{t.badge}</span> : null}
          </button>
        ))}
      </div>

      {/* ── ROSTER TAB ──────────────────────────────────────────────────── */}
      {tab === "roster" && (
        <div>
          {/* Controls */}
          <div className="flex flex-wrap items-center gap-2 mb-4 print:hidden">
            {/* Week nav */}
            <button onClick={() => setWeekStart(addDays(weekStart, -7))} className="vf-btn-ghost p-1.5"><ChevronLeft className="w-4 h-4" /></button>
            <span className="text-sm font-medium min-w-[180px] text-center">
              {new Date(weekStart + "T00:00:00Z").toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric" })}
              {" — "}
              {new Date(addDays(weekStart, 6) + "T00:00:00Z").toLocaleDateString("en-GB", { day: "numeric", month: "short" })}
            </span>
            <button onClick={() => setWeekStart(addDays(weekStart, 7))} className="vf-btn-ghost p-1.5"><ChevronRight className="w-4 h-4" /></button>
            <button onClick={() => setWeekStart(isoMonday(new Date()))} className="vf-btn-ghost text-xs px-2">Today</button>

            {/* View toggle */}
            <div className="flex border rounded-md overflow-hidden ml-2">
              {(["week", "month"] as View[]).map((v) => (
                <button key={v} onClick={() => setView(v)} className={`px-3 py-1.5 text-xs capitalize transition-colors ${view === v ? "bg-primary text-primary-foreground" : "hover:bg-muted text-muted-foreground"}`}>{v}</button>
              ))}
            </div>

            <div className="flex-1" />

            {roster?.published ? (
              <span className={styles.rosterPublished}>
                <Check className="w-3 h-3" /> Published
              </span>
            ) : (
              <span className={styles.rosterDraft}>Draft (staff cannot see)</span>
            )}

            <button onClick={copyLastWeek} disabled={copying} className="vf-btn-ghost flex items-center gap-1.5 text-sm">
              {copying ? <Loader2 className="w-3 h-3 animate-spin" /> : <Copy className="w-4 h-4" />} Copy Last Week
            </button>
            <button onClick={publishRoster} disabled={publishing || roster?.published} className="vf-btn flex items-center gap-1.5 text-sm disabled:opacity-60">
              {publishing ? <Loader2 className="w-3 h-3 animate-spin" /> : <Send className="w-4 h-4" />}
              {roster?.published ? "Published" : "Publish Roster"}
            </button>
          </div>

          {/* ── WEEK VIEW ────────────────────────────────────────────────── */}
          {view === "week" && (
            loading ? (
              <div className="flex items-center justify-center h-48"><Loader2 className="w-6 h-6 animate-spin text-vf-accent" /></div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full border-collapse text-sm print:text-xs">
                  <thead>
                    <tr>
                      <th className="py-2 px-3 text-left font-medium text-muted-foreground border-b w-32">Staff</th>
                      {days.map((day, i) => {
                        const isToday = day === isoMonday(new Date()) ? false : day === new Date().toISOString().slice(0, 10);
                        return (
                          <th key={day} className={`py-2 px-2 text-center font-medium border-b ${isToday ? "bg-primary/5 text-primary" : "text-muted-foreground"}`}>
                            <div className="text-xs">{DAY_LABELS[i]}</div>
                            <div className={`text-sm font-bold ${isToday ? "text-primary" : ""}`}>
                              {new Date(day + "T00:00:00Z").getUTCDate()}
                            </div>
                          </th>
                        );
                      })}
                    </tr>
                  </thead>
                  <tbody>
                    {weekStaff.length === 0 ? (
                      <tr>
                        <td colSpan={8} className="text-center text-muted-foreground py-12 text-sm">
                          No staff on roster this week. Use &ldquo;Copy Last Week&rdquo; or click a cell to add shifts.
                        </td>
                      </tr>
                    ) : weekStaff.map((member) => {
                      const color = staffColor(member.id, staff);
                      return (
                        <tr key={member.id} className="border-b hover:bg-muted/10 group">
                          {/* Staff name cell */}
                          <td className="py-2 px-3 font-medium text-sm">
                            <div className="flex items-center gap-1.5">
                              <div className="w-2.5 h-2.5 rounded-full flex-shrink-0" style={{ backgroundColor: color }} />
                              <span className="truncate max-w-[100px]">{member.name}</span>
                            </div>
                          </td>
                          {/* Day cells */}
                          {days.map((day) => {
                            const cellShifts = shiftsByStaffDay[member.id]?.[day] ?? [];
                            return (
                              <td
                                key={day}
                                className="py-1.5 px-1.5 border-l min-w-[110px] align-top"
                                onDragOver={(e) => e.preventDefault()}
                                onDrop={() => onDropCell(member.id, day)}
                              >
                                {cellShifts.map((shift) => (
                                  <div
                                    key={shift.id}
                                    draggable
                                    onDragStart={() => onDragStart(shift)}
                                    onClick={() => openEdit(shift)}
                                    className={styles.shiftPill}
                                    style={{ backgroundColor: shift.color ?? color }}
                                  >
                                    <div className="font-medium">{formatTime(shift.start_at)}–{formatTime(shift.end_at)}</div>
                                    {shift.notes && <div className="opacity-80 truncate">{shift.notes}</div>}
                                  </div>
                                ))}
                                {/* Add shift + button (hover) */}
                                <button
                                  onClick={() => openAdd(member.id, day)}
                                  className="w-full rounded border border-dashed border-muted-foreground/30 text-muted-foreground/50 hover:text-muted-foreground hover:border-muted-foreground/50 text-xs py-0.5 opacity-0 group-hover:opacity-100 transition-opacity"
                                >
                                  <Plus className="w-3 h-3 inline" />
                                </button>
                              </td>
                            );
                          })}
                        </tr>
                      );
                    })}
                    {/* Add staff row */}
                    <tr>
                      <td className="py-2 px-3" colSpan={8}>
                        <button onClick={() => openAdd("", weekStart)} className="vf-btn-ghost text-xs flex items-center gap-1.5">
                          <Plus className="w-3.5 h-3.5" /> Add Shift
                        </button>
                      </td>
                    </tr>
                  </tbody>
                </table>

                {/* Staff colour legend */}
                {weekStaff.length > 0 && (
                  <div className="flex flex-wrap gap-3 mt-3 pt-3 border-t print:mt-2">
                    {weekStaff.map((m) => (
                      <div key={m.id} className="flex items-center gap-1.5 text-xs text-muted-foreground">
                        <div className="w-3 h-3 rounded-sm" style={{ backgroundColor: staffColor(m.id, staff) }} />
                        {m.name}
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )
          )}

          {/* ── MONTH VIEW ─────────────────────────────────────────────────── */}
          {view === "month" && (
            monthLoading ? (
              <div className="flex items-center justify-center h-48"><Loader2 className="w-6 h-6 animate-spin text-vf-accent" /></div>
            ) : (
              <div>
                <div className={styles.monthGrid}>
                  {DAY_LABELS.map((d) => (
                    <div key={d} className="bg-muted/50 py-1.5 text-center font-medium text-muted-foreground">{d}</div>
                  ))}
                  {monthDays.map(({ date, isCurrentMonth }) => {
                    const dayShifts = shiftsByDay[date] ?? [];
                    const isToday = date === new Date().toISOString().slice(0, 10);
                    return (
                      <div
                        key={date}
                        className={`${styles.monthCell} ${!isCurrentMonth ? styles.monthCellInactive : ""} text-xs`}
                        onClick={() => { setWeekStart(isoMonday(new Date(date + "T00:00:00Z"))); setView("week"); }}
                      >
                        <div className={`text-xs font-medium mb-1 w-5 h-5 flex items-center justify-center rounded-full ${isToday ? "bg-primary text-primary-foreground" : "text-muted-foreground"}`}>
                          {parseInt(date.slice(8))}
                        </div>
                        <div className="space-y-0.5">
                          {dayShifts.slice(0, 3).map((s) => (
                            <div
                              key={s.id}
                              className="rounded px-1 py-0.5 text-white text-[10px] truncate"
                              style={{ backgroundColor: s.color ?? staffColor(s.staff_id, staff) }}
                              title={`${s.staff_name} ${formatTime(s.start_at)}`}
                            >
                              {s.staff_name.split(" ")[0]}
                            </div>
                          ))}
                          {dayShifts.length > 3 && (
                            <div className="text-[10px] text-muted-foreground pl-1">+{dayShifts.length - 3} more</div>
                          )}
                        </div>
                      </div>
                    );
                  })}
                </div>
                {/* Legend */}
                <div className="flex flex-wrap gap-3 mt-3 pt-3 border-t">
                  {staff.map((m) => (
                    <div key={m.id} className="flex items-center gap-1.5 text-xs text-muted-foreground">
                      <div className="w-3 h-3 rounded-sm" style={{ backgroundColor: staffColor(m.id, staff) }} />
                      {m.name}
                    </div>
                  ))}
                </div>
              </div>
            )
          )}
        </div>
      )}

      {/* ── SWAPS TAB ───────────────────────────────────────────────────── */}
      {tab === "swaps" && (
        <div>
          {swapsLoading ? (
            <div className="flex items-center justify-center h-32"><Loader2 className="w-5 h-5 animate-spin text-vf-accent" /></div>
          ) : swaps.length === 0 ? (
            <p className="vf-text-m text-muted-foreground">No swap requests yet.</p>
          ) : (
            <div className="space-y-2">
              {swaps.map((swap) => (
                <div key={swap.id} className={styles.swapCard}>
                  <div className="flex-1">
                    <div className="flex items-center gap-2 mb-1">
                      <span className={`${swap.status === "pending" ? styles.swapPending : swap.status === "approved" ? styles.swapApproved : styles.swapRejected}`}>
                        {swap.status}
                      </span>
                      <span className="text-xs text-muted-foreground">{new Date(swap.created_at).toLocaleDateString()}</span>
                    </div>
                    <p className="text-sm">
                      <span className="font-medium">Shift:</span> {swap.requester_shift_id.slice(0, 8)}…
                      {swap.target_shift_id && <> ↔ {swap.target_shift_id.slice(0, 8)}…</>}
                    </p>
                    {swap.requester_note && <p className="text-xs text-muted-foreground mt-0.5">Note: {swap.requester_note}</p>}
                    {swap.manager_notes && <p className="text-xs text-muted-foreground mt-0.5">Manager: {swap.manager_notes}</p>}
                  </div>
                  {swap.status === "pending" && (
                    <div className="flex gap-1.5 flex-shrink-0">
                      <button onClick={() => resolveSwap(swap.id, "approve")} className="p-1.5 rounded hover:bg-emerald-100 text-emerald-700" title="Approve swap">
                        <Check className="w-4 h-4" />
                      </button>
                      <button onClick={() => resolveSwap(swap.id, "reject")} className="p-1.5 rounded hover:bg-rose-100 text-rose-700" title="Reject swap">
                        <X className="w-4 h-4" />
                      </button>
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}

          {/* Create swap form */}
          <div className="mt-6 border rounded-lg p-4 bg-muted/30">
            <h3 className="text-sm font-semibold mb-3">Request Shift Swap</h3>
            <div className="grid grid-cols-2 gap-3 max-w-lg">
              <div>
                <label className="text-xs text-muted-foreground">Requester Shift ID</label>
                <input className="vf-input w-full mt-1" placeholder="shift UUID" value={swapForm.requester_shift_id} onChange={(e) => setSwapForm((f) => ({ ...f, requester_shift_id: e.target.value }))} />
              </div>
              <div>
                <label className="text-xs text-muted-foreground">Requester Staff</label>
                <select className="vf-input w-full mt-1" value={swapForm.requester_staff_id} onChange={(e) => setSwapForm((f) => ({ ...f, requester_staff_id: e.target.value }))}>
                  <option value="">— select —</option>
                  {staff.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
                </select>
              </div>
              <div>
                <label className="text-xs text-muted-foreground">Target Staff</label>
                <select className="vf-input w-full mt-1" value={swapForm.target_staff_id} onChange={(e) => setSwapForm((f) => ({ ...f, target_staff_id: e.target.value }))}>
                  <option value="">— select —</option>
                  {staff.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
                </select>
              </div>
              <div>
                <label className="text-xs text-muted-foreground">Note</label>
                <input className="vf-input w-full mt-1" value={swapForm.requester_note} onChange={(e) => setSwapForm((f) => ({ ...f, requester_note: e.target.value }))} />
              </div>
              <div className="col-span-2">
                <button
                  onClick={async () => {
                    try {
                      const res = await api.post("/api/shifts/swaps", {
                        requester_shift_id: swapForm.requester_shift_id,
                        requester_staff_id: swapForm.requester_staff_id,
                        target_staff_id: swapForm.target_staff_id,
                        requester_note: swapForm.requester_note || null,
                      });
                      setSwaps((s) => [res, ...s]);
                      setSwapForm({ requester_shift_id: "", requester_staff_id: "", target_staff_id: "", requester_note: "" });
                      toast.success("Swap request submitted");
                    } catch { toast.error("Failed to submit swap"); }
                  }}
                  className="vf-btn"
                >
                  Submit Swap Request
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* ── ADD/EDIT SHIFT MODAL ────────────────────────────────────────── */}
      {showModal && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 print:hidden">
          <div className="bg-background rounded-xl shadow-xl p-6 w-full max-w-sm">
            <div className="flex items-center justify-between mb-4">
              <h2 className="font-semibold vf-text-1">{editShift ? "Edit Shift" : "Add Shift"}</h2>
              <button onClick={() => setShowModal(false)} className="vf-btn-ghost p-1"><X className="w-4 h-4" /></button>
            </div>
            <div className="space-y-3">
              <div>
                <label className="text-xs font-medium text-muted-foreground">Staff Member *</label>
                <select className="vf-input w-full mt-1" value={form.staff_id} onChange={(e) => setForm((f) => ({ ...f, staff_id: e.target.value, color: staffColor(e.target.value, staff) }))} disabled={!!editShift}>
                  <option value="">— select —</option>
                  {staff.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
                </select>
              </div>
              <div>
                <label className="text-xs font-medium text-muted-foreground">Date *</label>
                <input type="date" className="vf-input w-full mt-1" value={form.date} onChange={(e) => setForm((f) => ({ ...f, date: e.target.value }))} />
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="text-xs font-medium text-muted-foreground">Start Time</label>
                  <input type="time" className="vf-input w-full mt-1" value={form.start_time} onChange={(e) => setForm((f) => ({ ...f, start_time: e.target.value }))} />
                </div>
                <div>
                  <label className="text-xs font-medium text-muted-foreground">End Time</label>
                  <input type="time" className="vf-input w-full mt-1" value={form.end_time} onChange={(e) => setForm((f) => ({ ...f, end_time: e.target.value }))} />
                </div>
              </div>
              <div>
                <label className="text-xs font-medium text-muted-foreground">Notes</label>
                <input className="vf-input w-full mt-1" value={form.notes} onChange={(e) => setForm((f) => ({ ...f, notes: e.target.value }))} />
              </div>
              <div>
                <label className="text-xs font-medium text-muted-foreground">Colour</label>
                <div className="flex items-center gap-2 mt-1">
                  <input type="color" className="h-8 w-12 rounded border cursor-pointer" value={form.color || "#2563EB"} onChange={(e) => setForm((f) => ({ ...f, color: e.target.value }))} />
                  <div className="flex gap-1">
                    {STAFF_PALETTE.map((c) => (
                      <button key={c} onClick={() => setForm((f) => ({ ...f, color: c }))} className="w-5 h-5 rounded-sm border-2 transition-all" style={{ backgroundColor: c, borderColor: form.color === c ? "white" : c }} />
                    ))}
                  </div>
                </div>
              </div>
              <div className="flex gap-2 pt-1">
                <button onClick={saveShift} disabled={saving} className="vf-btn flex-1 flex items-center justify-center gap-2">
                  {saving && <Loader2 className="w-3 h-3 animate-spin" />} {editShift ? "Update" : "Create"}
                </button>
                {editShift && (
                  <button onClick={() => deleteShift(editShift.id)} className="px-3 py-1.5 rounded border border-rose-300 text-rose-600 hover:bg-rose-50 text-sm transition-colors">
                    Delete
                  </button>
                )}
                <button onClick={() => setShowModal(false)} className="vf-btn-ghost">Cancel</button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Print styles */}
      <style>{`
        @media print {
          body > *:not(#shift-roster) { display: none !important; }
          #shift-roster { padding: 0 !important; }
          .print\\:hidden { display: none !important; }
        }
      `}</style>
    </div>
  );
}
