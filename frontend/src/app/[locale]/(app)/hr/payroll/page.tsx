"use client";

import { useState, useEffect } from "react";
import { useTranslations } from "next-intl";
import { api } from "@/lib/api-client";
import { Download, CalendarDays } from "lucide-react";
import { toast } from "sonner";

interface PayrollRun {
  id: string;
  employee_name: string;
  gross_salary: number;
  net_salary: number;
  tax: number;
  status: string;
}

const months = [
  "January", "February", "March", "April", "May", "June",
  "July", "August", "September", "October", "November", "December",
];

export default function PayrollPage() {
  const t = useTranslations();
  const now = new Date();
  const [month, setMonth] = useState(now.getMonth() + 1);
  const [year, setYear] = useState(now.getFullYear());
  const [runs, setRuns] = useState<PayrollRun[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    async function fetchRuns() {
      setLoading(true);
      try {
        const data = await api.get<PayrollRun[]>(
          `/api/payroll/runs?month=${month}&year=${year}`
        );
        setRuns(data);
      } catch {
        toast.error("Failed to load payroll data. Please try again.");
      } finally {
        setLoading(false);
      }
    }
    fetchRuns();
  }, [month, year]);

  async function handleExportCsv() {
    try {
      await api.downloadBlob(
        `/api/payroll/runs/export?month=${month}&year=${year}`,
        `payroll-${year}-${String(month).padStart(2, "0")}.csv`
      );
      toast.success("CSV downloaded.");
    } catch {
      toast.error("Failed to export CSV. Please try again.");
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="vf-text-1 text-2xl font-semibold">Payroll</h1>
        <button
          onClick={handleExportCsv}
          className="inline-flex items-center gap-2 rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700"
        >
          <Download className="h-4 w-4" />
          Export CSV
        </button>
      </div>

      {/* Period selector */}
      <div className="flex items-center gap-4">
        <CalendarDays className="h-5 w-5 vf-text-m" />
        <select
          value={month}
          onChange={(e) => setMonth(Number(e.target.value))}
          className="vf-bg-card vf-border rounded-md px-3 py-2 text-sm vf-text-1"
        >
          {months.map((m, i) => (
            <option key={i} value={i + 1}>
              {m}
            </option>
          ))}
        </select>
        <select
          value={year}
          onChange={(e) => setYear(Number(e.target.value))}
          className="vf-bg-card vf-border rounded-md px-3 py-2 text-sm vf-text-1"
        >
          {Array.from({ length: 5 }, (_, i) => now.getFullYear() - 2 + i).map(
            (y) => (
              <option key={y} value={y}>
                {y}
              </option>
            )
          )}
        </select>
      </div>

      {/* Payroll data table */}
      {loading ? (
        <p className="vf-text-m">Loading...</p>
      ) : runs.length === 0 ? (
        <div className="vf-bg-card vf-border rounded-lg p-8 text-center">
          <p className="vf-text-m">No payroll data for this period.</p>
        </div>
      ) : (
        <div className="vf-bg-card vf-border rounded-lg overflow-hidden">
          <table className="w-full text-left text-sm">
            <thead className="vf-border border-b">
              <tr>
                <th className="vf-text-m px-4 py-3 font-medium">Employee</th>
                <th className="vf-text-m px-4 py-3 font-medium text-right">Gross</th>
                <th className="vf-text-m px-4 py-3 font-medium text-right">Tax</th>
                <th className="vf-text-m px-4 py-3 font-medium text-right">Net</th>
                <th className="vf-text-m px-4 py-3 font-medium">Status</th>
              </tr>
            </thead>
            <tbody>
              {runs.map((run) => (
                <tr key={run.id} className="vf-border border-b last:border-b-0">
                  <td className="vf-text-1 px-4 py-3">{run.employee_name}</td>
                  <td className="vf-text-1 px-4 py-3 text-right">
                    {run.gross_salary.toLocaleString()}
                  </td>
                  <td className="vf-text-1 px-4 py-3 text-right">
                    {run.tax.toLocaleString()}
                  </td>
                  <td className="vf-text-1 px-4 py-3 text-right">
                    {run.net_salary.toLocaleString()}
                  </td>
                  <td className="px-4 py-3">
                    <span className="vf-text-m text-xs">{run.status}</span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
