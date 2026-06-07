"use client";

import { useState, useEffect } from "react";
import { ChevronLeft, ChevronRight, Clock, AlertTriangle } from "lucide-react";
import { api } from "@/lib/api-client";
import styles from "./page.module.scss";

interface OvertimeEntry { staff_id: string; staff_name: string; total_hours: number; is_overtime: boolean }

function isoDate(d: Date) { return d.toISOString().slice(0, 10); }
function addDays(d: Date, n: number) { const r = new Date(d); r.setDate(r.getDate() + n); return r; }
function getMonday(d: Date) { const day = d.getDay(); return addDays(d, day === 0 ? -6 : 1 - day); }

export default function OvertimePage() {
  const [data, setData] = useState<OvertimeEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [weekStart, setWeekStart] = useState<Date>(getMonday(new Date()));

  const weekStr = isoDate(weekStart);
  const weekDays = Array.from({ length: 7 }, (_, i) => addDays(weekStart, i));

  useEffect(() => {
    api.get<OvertimeEntry[]>(`/api/scheduling/overtime?week_start=${weekStr}`)
      .then(d => { setData(d); setLoading(false); })
      .catch(() => { setLoading(false); });
  }, [weekStr]);

  const overtimeCount = data.filter(d => d.is_overtime).length;

  if (loading) return <div className="animate-pulse space-y-4"><div className="h-10 rounded-lg bg-gray-100 w-64" /><div className="h-48 rounded-xl bg-gray-100" /></div>;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold text-gray-900">Overtime</h1>
        <p className="mt-1 text-sm text-gray-500">Weekly hours per staff member. Flag when exceeding 40h.</p>
      </div>

      <div className="flex items-center gap-2">
        <button onClick={() => setWeekStart(w => addDays(w, -7))} className="p-1.5 rounded-lg border border-gray-200 hover:bg-gray-50"><ChevronLeft className="h-4 w-4" /></button>
        <button onClick={() => setWeekStart(getMonday(new Date()))} className="px-3 py-1.5 text-sm font-medium rounded-lg border border-gray-200 hover:bg-gray-50">This week</button>
        <button onClick={() => setWeekStart(w => addDays(w, 7))} className="p-1.5 rounded-lg border border-gray-200 hover:bg-gray-50"><ChevronRight className="h-4 w-4" /></button>
        <span className="text-sm font-medium text-gray-700 ml-2">
          {weekDays[0].toLocaleDateString("en-GB", { day: "numeric", month: "short" })} – {weekDays[6].toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric" })}
        </span>
      </div>

      {overtimeCount > 0 && (
        <div className="flex items-center gap-2 p-3 rounded-xl bg-red-50 border border-red-200">
          <AlertTriangle className="h-4 w-4 text-red-500" />
          <span className="text-sm text-red-700 font-medium">{overtimeCount} staff over 40h limit</span>
        </div>
      )}

      {data.length === 0 && (
        <div className="text-center py-12 text-gray-400"><Clock className="h-10 w-10 mx-auto mb-3 opacity-40" /><p>No shifts this week.</p></div>
      )}

      <div className="space-y-2">
        {data.map(entry => (
          <div key={entry.staff_id} className={`rounded-xl border p-4 flex items-center gap-4 ${entry.is_overtime ? "border-red-200 bg-red-50/30" : "border-gray-200 bg-white"}`}>
            <div className="flex-1 min-w-0">
              <span className="font-medium text-gray-900">{entry.staff_name}</span>
            </div>
            <div className="flex items-center gap-3">
              <div className="w-48 h-3 bg-gray-100 rounded-full overflow-hidden">
                <div
                  className={`h-full rounded-full ${entry.is_overtime ? "bg-red-500" : "bg-blue-500"}`}
                  style={{ width: `${Math.min(entry.total_hours / 50 * 100, 100)}%` }}
                />
              </div>
              <span className={`text-sm font-semibold w-16 text-right ${entry.is_overtime ? "text-red-700" : "text-gray-700"}`}>
                {entry.total_hours}h
              </span>
              {entry.is_overtime && <span className={styles.overtimeBadge}>Overtime</span>}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
