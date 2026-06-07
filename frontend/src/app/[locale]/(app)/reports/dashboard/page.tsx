"use client";
import { useEffect, useState } from "react";
import { api } from "@/lib/api-client";

interface DashboardData {
  pending_purchase_requests: number;
  pending_timesheet_approvals: number;
  invoices_total_this_month: number;
  petty_cash_balance: number;
}

export default function ManagerDashboardPage() {
  const [data, setData] = useState<DashboardData | null>(null);

  useEffect(() => {
    api.get<DashboardData>("/api/reports/manager-dashboard")
      .then(setData)
      .catch(() => {});
  }, []);

  if (!data) return <div className="p-6">Loading...</div>;

  const cards = [
    { label: "Pending Purchase Requests", value: data.pending_purchase_requests, color: "text-yellow-600" },
    { label: "Pending Timesheet Approvals", value: data.pending_timesheet_approvals, color: "text-yellow-600" },
    { label: "Invoices This Month", value: `${data.invoices_total_this_month.toLocaleString()} SEK`, color: "text-blue-600" },
    { label: "Petty Cash Balance", value: `${data.petty_cash_balance.toLocaleString()} SEK`, color: "text-green-600" },
  ];

  return (
    <div className="p-6 space-y-6">
      <h1 className="text-2xl font-bold">Manager Dashboard</h1>
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        {cards.map(c => (
          <div key={c.label} className="border rounded p-4">
            <div className="text-sm text-gray-500">{c.label}</div>
            <div className={`text-2xl font-bold ${c.color}`}>{c.value}</div>
          </div>
        ))}
      </div>
    </div>
  );
}
