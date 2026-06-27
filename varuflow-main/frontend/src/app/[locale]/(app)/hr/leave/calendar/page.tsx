"use client";

import { useState, useEffect } from "react";
import { ChevronLeft, ChevronRight, Calendar, Users } from "lucide-react";
import { api } from "@/lib/api-client";
import styles from "./page.module.scss";

interface LeaveRequest {
  id: string; staff_id: string; staff_name?: string;
  leave_type: string; start_date: string; end_date: string; status: string;
  reason?: string;
}

const LEAVE_TYPE_COLORS: Record<string, string> = {
  annual:   "bg-blue-100 text-blue-700 border-blue-200",
  sick:     "bg-red-100 text-red-700 border-red-200",
  parental: "bg-purple-100 text-purple-700 border-purple-200",
  unpaid:   "bg-gray-100 text-gray-600 border-gray-200",
  other:    "bg-amber-100 text-amber-700 border-amber-200",
};

const LEAVE_TYPE_MODULE: Record<string, keyof typeof styles> = {
  annual:   "leaveAnnual",
  sick:     "leaveSick",
  parental: "leaveParental",
  unpaid:   "leaveUnpaid",
  other:    "leaveOther",
};

const LEAVE_TYPE_BG: Record<string, string> = {
  annual: "bg-blue-400", sick: "bg-red-400", parental: "bg-purple-400",
  unpaid: "bg-gray-400", other: "bg-amber-400",
};

const DOW = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];

function isoDate(d: Date) {
  return d.toISOString().slice(0, 10);
}

function addDays(d: Date, n: number) {
  const r = new Date(d);
  r.setDate(r.getDate() + n);
  return r;
}

function getMonday(d: Date) {
  const day = d.getDay();
  const diff = (day === 0 ? -6 : 1 - day);
  return addDays(d, diff);
}

function overlapsDays(leave: LeaveRequest, days: string[]) {
  return days.some(d => d >= leave.start_date && d <= leave.end_date);
}

export default function LeaveCalendarPage() {
  const [leaves, setLeaves] = useState<LeaveRequest[]>([]);
  const [staff, setStaff] = useState<{ id: string; name: string }[]>([]);
  const [loading, setLoading] = useState(true);
  const [weekStart, setWeekStart] = useState<Date>(getMonday(new Date()));
  const [view, setView] = useState<"week" | "month">("week");
  const [filterType, setFilterType] = useState("");

  const weekDays = Array.from({ length: 7 }, (_, i) => addDays(weekStart, i));
  const weekDayStrs = weekDays.map(isoDate);

  useEffect(() => {
    // Load approved leaves for a 3-month window
    Promise.all([
      api.get<LeaveRequest[] | { leaves?: LeaveRequest[] }>("/api/hr/leave?status=approved").catch(() => []),
      api.get<any[]>("/api/hr/employees").catch(() => []),
    ]).then(([lvs, emps]) => {
      const leaveArr = Array.isArray(lvs) ? lvs : (lvs as any).leaves ?? [];
      setLeaves(leaveArr);
      setStaff((emps as any[]).map((e: any) => ({ id: e.id, name: e.name })));
      setLoading(false);
    });
  }, []);

  function prevWeek() { setWeekStart(w => addDays(w, -7)); }
  function nextWeek() { setWeekStart(w => addDays(w, 7)); }
  function goToday()  { setWeekStart(getMonday(new Date())); }

  const today = isoDate(new Date());
  const filtered = filterType ? leaves.filter(l => l.leave_type === filterType) : leaves;

  // Staff with any leave this week
  const staffOnLeaveThisWeek = new Set(
    filtered.filter(l => overlapsDays(l, weekDayStrs)).map(l => l.staff_id)
  );

  if (loading) return (
    <div className="animate-pulse space-y-4">
      <div className="h-10 rounded-lg bg-gray-100 w-64" />
      <div className="h-64 rounded-xl bg-gray-100" />
    </div>
  );

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold text-gray-900">Leave Calendar</h1>
        <p className="mt-1 text-sm text-gray-500">See who is off and when — approved leave across all staff.</p>
      </div>

      {/* Controls */}
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div className="flex items-center gap-2">
          <button onClick={prevWeek} className="p-1.5 rounded-lg border border-gray-200 hover:bg-gray-50"><ChevronLeft className="h-4 w-4" /></button>
          <button onClick={goToday} className="px-3 py-1.5 text-sm font-medium rounded-lg border border-gray-200 hover:bg-gray-50">Today</button>
          <button onClick={nextWeek} className="p-1.5 rounded-lg border border-gray-200 hover:bg-gray-50"><ChevronRight className="h-4 w-4" /></button>
          <span className="text-sm font-medium text-gray-700 ml-2">
            {weekDays[0].toLocaleDateString("en-GB", { day: "numeric", month: "short" })}
            {" – "}
            {weekDays[6].toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric" })}
          </span>
        </div>
        <div className="flex items-center gap-2">
          <select className="input text-sm" value={filterType} onChange={e => setFilterType(e.target.value)}>
            <option value="">All leave types</option>
            <option value="annual">Annual</option>
            <option value="sick">Sick</option>
            <option value="parental">Parental</option>
            <option value="unpaid">Unpaid</option>
            <option value="other">Other</option>
          </select>
        </div>
      </div>

      {/* Staff off this week summary */}
      {staffOnLeaveThisWeek.size > 0 && (
        <div className="flex items-center gap-2 p-3 rounded-xl bg-blue-50 border border-blue-200">
          <Users className="h-4 w-4 text-blue-500 flex-shrink-0" />
          <span className="text-sm text-blue-800 font-medium">{staffOnLeaveThisWeek.size} staff member{staffOnLeaveThisWeek.size > 1 ? "s" : ""} off this week</span>
          <div className="flex gap-1.5 ml-2 flex-wrap">
            {Array.from(staffOnLeaveThisWeek).map(sid => {
              const s = staff.find(x => x.id === sid);
              return <span key={sid} className="text-xs bg-blue-100 text-blue-700 px-2 py-0.5 rounded-full">{s?.name || "Staff"}</span>;
            })}
          </div>
        </div>
      )}

      {/* Weekly grid */}
      <div className="rounded-xl border border-gray-200 bg-white overflow-hidden">
        {/* Header */}
        <div className="grid grid-cols-8 border-b border-gray-100">
          <div className="p-3 bg-gray-50 border-r border-gray-100">
            <span className="text-xs font-medium text-gray-500">Staff</span>
          </div>
          {weekDays.map((day, i) => {
            const ds = isoDate(day);
            const isToday = ds === today;
            const isWeekend = i >= 5;
            return (
              <div key={ds} className={`p-3 text-center border-r border-gray-100 last:border-r-0 ${isWeekend ? "bg-gray-50" : ""}`}>
                <p className="text-xs font-medium text-gray-500">{DOW[i]}</p>
                <p className={`text-sm font-semibold mt-0.5 ${isToday ? "text-blue-600" : "text-gray-900"}`}>
                  {day.getDate()}
                </p>
                {isToday && <div className="w-1.5 h-1.5 rounded-full bg-blue-500 mx-auto mt-0.5" />}
              </div>
            );
          })}
        </div>

        {/* Staff rows */}
        {staff.length === 0 && (
          <div className="py-12 text-center text-gray-400">
            <Calendar className="h-8 w-8 mx-auto mb-2 opacity-40" />
            <p>No staff found. Add staff members to see their leave.</p>
          </div>
        )}
        {staff.map((s, si) => {
          const staffLeaves = filtered.filter(l => l.staff_id === s.id && overlapsDays(l, weekDayStrs));
          return (
            <div key={s.id} className={`grid grid-cols-8 border-b border-gray-50 last:border-b-0 ${si % 2 === 0 ? "bg-white" : "bg-gray-50/30"}`}>
              <div className="p-3 border-r border-gray-100 flex items-center">
                <span className="text-sm font-medium text-gray-800 truncate">{s.name}</span>
              </div>
              {weekDays.map((day, i) => {
                const ds = isoDate(day);
                const dayLeave = staffLeaves.find(l => ds >= l.start_date && ds <= l.end_date);
                const isWeekend = i >= 5;
                return (
                  <div key={ds} className={`p-1.5 border-r border-gray-100 last:border-r-0 min-h-[52px] ${isWeekend ? "bg-gray-50" : ""}`}>
                    {dayLeave && (
                      <div className={styles[LEAVE_TYPE_MODULE[dayLeave.leave_type] ?? "leaveOther"]}>
                        {dayLeave.leave_type.charAt(0).toUpperCase() + dayLeave.leave_type.slice(1)}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          );
        })}
      </div>

      {/* Legend */}
      <div className="flex gap-4 flex-wrap">
        {Object.entries(LEAVE_TYPE_COLORS).map(([type, cls]) => (
          <div key={type} className="flex items-center gap-1.5">
            <div className={`w-3 h-3 rounded ${LEAVE_TYPE_BG[type]}`} />
            <span className="text-xs text-gray-600 capitalize">{type}</span>
          </div>
        ))}
      </div>

      {/* Upcoming leave list */}
      {filtered.filter(l => l.end_date >= today).length > 0 && (
        <div className="space-y-2">
          <p className="text-sm font-semibold text-gray-700">Upcoming approved leave</p>
          {filtered.filter(l => l.end_date >= today).sort((a, b) => a.start_date.localeCompare(b.start_date)).slice(0, 15).map(l => {
            const s = staff.find(x => x.id === l.staff_id);
            const start = new Date(l.start_date);
            const end = new Date(l.end_date);
            const days = Math.round((end.getTime() - start.getTime()) / 86400000) + 1;
            return (
              <div key={l.id} className="flex items-center justify-between rounded-xl border border-gray-200 bg-white p-3 gap-3">
                <div className="flex items-center gap-3">
                  <div className={`w-2.5 h-2.5 rounded-full flex-shrink-0 ${LEAVE_TYPE_BG[l.leave_type]}`} />
                  <span className="font-medium text-sm text-gray-800">{s?.name || "Staff"}</span>
                  <span className={styles[LEAVE_TYPE_MODULE[l.leave_type] ?? "leaveOther"]}>
                    {l.leave_type}
                  </span>
                </div>
                <div className="text-right text-sm text-gray-600">
                  {start.toLocaleDateString("en-GB", { day: "numeric", month: "short" })}
                  {days > 1 && ` – ${end.toLocaleDateString("en-GB", { day: "numeric", month: "short" })}`}
                  <span className="text-xs text-gray-400 ml-1.5">({days}d)</span>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
