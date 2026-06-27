"use client";

import { useState, useEffect } from "react";
import { RoleGuard } from "@/components/app/RoleContext";
import { ChevronLeft, ChevronRight, Calendar, AlertTriangle } from "lucide-react";
import { api } from "@/lib/api-client";
import { isPlanGateError, PlanGateBlock } from "@/components/ui/PlanGate";
import styles from "./page.module.scss";

interface ShiftEntry { id: string; start_at: string; end_at: string; notes: string | null }
interface StaffRoster { staff_id: string; staff_name: string; shifts: ShiftEntry[] }
interface OvertimeEntry { staff_id: string; total_hours: number; is_overtime: boolean }

function isoDate(d: Date) { return d.toISOString().slice(0, 10); }
function addDays(d: Date, n: number) { const r = new Date(d); r.setDate(r.getDate() + n); return r; }
function getMonday(d: Date) { const day = d.getDay(); return addDays(d, day === 0 ? -6 : 1 - day); }

const DOW = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];

function RosterPageInner() {
  const [roster, setRoster] = useState<StaffRoster[]>([]);
  const [overtime, setOvertime] = useState<OvertimeEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [weekStart, setWeekStart] = useState<Date>(getMonday(new Date()));
  const [planBlocked, setPlanBlocked] = useState<{ module: string; currentPlan: string } | null>(null);

  const weekDays = Array.from({ length: 7 }, (_, i) => addDays(weekStart, i));
  const weekStr = isoDate(weekStart);

  useEffect(() => {
    Promise.all([
      api.get<StaffRoster[]>(`/api/scheduling/roster?week_start=${weekStr}`),
      api.get<OvertimeEntry[]>(`/api/scheduling/overtime?week_start=${weekStr}`).catch(() => [] as OvertimeEntry[]),
    ]).then(([r, o]) => { setRoster(r); setOvertime(o); setLoading(false); })
      .catch((err) => {
        if (isPlanGateError(err)) {
          setPlanBlocked({ module: (err as any).module ?? "hr", currentPlan: (err as any).currentPlan ?? "FREE" });
        }
        setLoading(false);
      });
  }, [weekStr]);

  const today = isoDate(new Date());
  const otMap = Object.fromEntries(overtime.map(o => [o.staff_id, o]));

  if (loading) return <div className="animate-pulse space-y-4"><div className="h-10 rounded-lg bg-gray-100 w-64" /><div className="h-64 rounded-xl bg-gray-100" /></div>;
  if (planBlocked) return <PlanGateBlock module={planBlocked.module} currentPlan={planBlocked.currentPlan} featureName="Scheduling" />;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold text-gray-900">Weekly Roster</h1>
        <p className="mt-1 text-sm text-gray-500">Visual shift calendar — see who is working when.</p>
      </div>

      <div className="flex items-center gap-2">
        <button onClick={() => setWeekStart(w => addDays(w, -7))} className="p-1.5 rounded-lg border border-gray-200 hover:bg-gray-50"><ChevronLeft className="h-4 w-4" /></button>
        <button onClick={() => setWeekStart(getMonday(new Date()))} className="px-3 py-1.5 text-sm font-medium rounded-lg border border-gray-200 hover:bg-gray-50">Today</button>
        <button onClick={() => setWeekStart(w => addDays(w, 7))} className="p-1.5 rounded-lg border border-gray-200 hover:bg-gray-50"><ChevronRight className="h-4 w-4" /></button>
        <span className="text-sm font-medium text-gray-700 ml-2">
          {weekDays[0].toLocaleDateString("en-GB", { day: "numeric", month: "short" })} – {weekDays[6].toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric" })}
        </span>
      </div>

      {overtime.filter(o => o.is_overtime).length > 0 && (
        <div className="flex items-center gap-2 p-3 rounded-xl bg-red-50 border border-red-200">
          <AlertTriangle className="h-4 w-4 text-red-500" />
          <span className="text-sm text-red-700 font-medium">
            {overtime.filter(o => o.is_overtime).length} staff member{overtime.filter(o => o.is_overtime).length > 1 ? "s" : ""} over 40h this week
          </span>
        </div>
      )}

      <div className="rounded-xl border border-gray-200 bg-white overflow-hidden">
        <div className="grid grid-cols-8 border-b border-gray-100">
          <div className="p-3 bg-gray-50 border-r border-gray-100"><span className="text-xs font-medium text-gray-500">Staff</span></div>
          {weekDays.map((day, i) => {
            const ds = isoDate(day);
            const isToday = ds === today;
            return (
              <div key={ds} className={`p-3 text-center border-r border-gray-100 last:border-r-0 ${i >= 5 ? "bg-gray-50" : ""}`}>
                <p className="text-xs font-medium text-gray-500">{DOW[i]}</p>
                <p className={`text-sm font-semibold mt-0.5 ${isToday ? "text-blue-600" : "text-gray-900"}`}>{day.getDate()}</p>
                {isToday && <div className="w-1.5 h-1.5 rounded-full bg-blue-500 mx-auto mt-0.5" />}
              </div>
            );
          })}
        </div>

        {roster.length === 0 && (
          <div className="py-12 text-center text-gray-400"><Calendar className="h-8 w-8 mx-auto mb-2 opacity-40" /><p>No shifts scheduled this week.</p></div>
        )}

        {roster.map((staff, si) => {
          const ot = otMap[staff.staff_id];
          return (
            <div key={staff.staff_id} className={`grid grid-cols-8 border-b border-gray-50 last:border-b-0 ${si % 2 === 0 ? "bg-white" : "bg-gray-50/30"}`}>
              <div className="p-3 border-r border-gray-100 flex items-center gap-2">
                <span className="text-sm font-medium text-gray-800 truncate">{staff.staff_name}</span>
                {ot?.is_overtime && <span className={styles.overtimeBadge}>{ot.total_hours}h</span>}
              </div>
              {weekDays.map((day, i) => {
                const ds = isoDate(day);
                const dayShifts = staff.shifts.filter(s => s.start_at.slice(0, 10) === ds);
                return (
                  <div key={ds} className={`p-1.5 border-r border-gray-100 last:border-r-0 min-h-[52px] ${i >= 5 ? "bg-gray-50" : ""}`}>
                    {dayShifts.map(shift => {
                      const start = new Date(shift.start_at);
                      const end = new Date(shift.end_at);
                      return (
                        <div key={shift.id} className="rounded px-1.5 py-1 text-xs font-medium bg-blue-100 text-blue-700 border border-blue-200 mb-0.5">
                          {start.toLocaleTimeString("sv-SE", { hour: "2-digit", minute: "2-digit" })}–{end.toLocaleTimeString("sv-SE", { hour: "2-digit", minute: "2-digit" })}
                        </div>
                      );
                    })}
                  </div>
                );
              })}
            </div>
          );
        })}
      </div>
    </div>
  );
}

export default function RosterPage() {
  return (
    <RoleGuard minRole="ADMIN">
      <RosterPageInner />
    </RoleGuard>
  );
}
