"use client";
import { useEffect, useState } from "react";
import { api } from "@/lib/api-client";

interface StaffAttendance {
  staff_id: string;
  staff_name: string;
  scheduled_shifts: number;
  attended: number;
  missed: number;
  late: number;
}

interface AttendanceData {
  week_start: string;
  week_end: string;
  staff: StaffAttendance[];
}

export default function AttendanceReportPage() {
  const [data, setData] = useState<AttendanceData | null>(null);
  const [weekStart, setWeekStart] = useState(() => {
    const d = new Date();
    d.setDate(d.getDate() - d.getDay() + 1);
    return d.toISOString().split("T")[0];
  });

  useEffect(() => {
    api.get<AttendanceData>(`/api/reports/attendance?week_start=${weekStart}`)
      .then(setData)
      .catch(() => {});
  }, [weekStart]);

  const prevWeek = () => { const d = new Date(weekStart); d.setDate(d.getDate() - 7); setWeekStart(d.toISOString().split("T")[0]); };
  const nextWeek = () => { const d = new Date(weekStart); d.setDate(d.getDate() + 7); setWeekStart(d.toISOString().split("T")[0]); };

  return (
    <div className="p-6 space-y-4">
      <h1 className="text-2xl font-bold">Attendance Report</h1>
      <div className="flex gap-4 items-center">
        <button onClick={prevWeek} className="px-3 py-1 border rounded">← Prev</button>
        <span className="font-medium">{data?.week_start} — {data?.week_end}</span>
        <button onClick={nextWeek} className="px-3 py-1 border rounded">Next →</button>
      </div>
      <table className="w-full text-sm border">
        <thead className="bg-gray-50">
          <tr>
            <th className="px-4 py-2 text-left">Staff</th>
            <th className="px-4 py-2 text-right">Scheduled</th>
            <th className="px-4 py-2 text-right">Attended</th>
            <th className="px-4 py-2 text-right">Missed</th>
            <th className="px-4 py-2 text-right">Late</th>
          </tr>
        </thead>
        <tbody>
          {data?.staff.map(s => (
            <tr key={s.staff_id} className="border-t">
              <td className="px-4 py-2">{s.staff_name}</td>
              <td className="px-4 py-2 text-right">{s.scheduled_shifts}</td>
              <td className="px-4 py-2 text-right">{s.attended}</td>
              <td className="px-4 py-2 text-right text-red-600">{s.missed}</td>
              <td className="px-4 py-2 text-right text-yellow-600">{s.late}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
