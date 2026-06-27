"use client";
import { useEffect, useState } from "react";

interface StaffProd {
  staff_id: string;
  staff_name: string;
  invoices_raised: number;
  appointments_completed: number;
  billable_hours: number;
}

export default function ProductivityReportPage() {
  const [data, setData] = useState<StaffProd[]>([]);
  const [fromDate, setFromDate] = useState(() => { const d = new Date(); d.setDate(1); return d.toISOString().split("T")[0]; });
  const [toDate, setToDate] = useState(() => new Date().toISOString().split("T")[0]);

  const load = () => {
    fetch(`${process.env.NEXT_PUBLIC_API_URL}/api/reports/staff-productivity?from_date=${fromDate}&to_date=${toDate}`, { credentials: "include" })
      .then(r => r.ok ? r.json() : [])
      .then(setData);
  };

  useEffect(() => { load(); }, [fromDate, toDate]);

  return (
    <div className="p-6 space-y-4">
      <h1 className="text-2xl font-bold">Staff Productivity</h1>
      <div className="flex gap-4 items-center">
        <input type="date" value={fromDate} onChange={e => setFromDate(e.target.value)} className="border rounded px-3 py-2" />
        <span>to</span>
        <input type="date" value={toDate} onChange={e => setToDate(e.target.value)} className="border rounded px-3 py-2" />
      </div>
      <table className="w-full text-sm border">
        <thead className="bg-gray-50">
          <tr>
            <th className="px-4 py-2 text-left">Staff</th>
            <th className="px-4 py-2 text-right">Invoices Raised</th>
            <th className="px-4 py-2 text-right">Appointments</th>
            <th className="px-4 py-2 text-right">Billable Hours</th>
          </tr>
        </thead>
        <tbody>
          {data.map(s => (
            <tr key={s.staff_id} className="border-t">
              <td className="px-4 py-2">{s.staff_name}</td>
              <td className="px-4 py-2 text-right">{s.invoices_raised}</td>
              <td className="px-4 py-2 text-right">{s.appointments_completed}</td>
              <td className="px-4 py-2 text-right">{s.billable_hours}h</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
