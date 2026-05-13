"use client";

import { useState, useEffect } from "react";
import { useTranslations } from "next-intl";
import { api } from "@/lib/api-client";
import { Plus, Pencil, UserCircle } from "lucide-react";
import { toast } from "sonner";

interface Employee {
  id: string;
  name: string;
  role: string;
  status: "active" | "on_leave" | "terminated";
  email: string;
}

const statusColors: Record<Employee["status"], string> = {
  active: "bg-green-100 text-green-800",
  on_leave: "bg-yellow-100 text-yellow-800",
  terminated: "bg-red-100 text-red-800",
};

const statusLabels: Record<Employee["status"], string> = {
  active: "Active",
  on_leave: "On Leave",
  terminated: "Terminated",
};

export default function EmployeesPage() {
  const t = useTranslations();
  const [employees, setEmployees] = useState<Employee[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function fetchEmployees() {
      try {
        const data = await api.get<Employee[]>("/api/hr/employees");
        setEmployees(data);
      } catch {
        toast.error("Failed to load employees. Please try again.");
      } finally {
        setLoading(false);
      }
    }
    fetchEmployees();
  }, []);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="vf-text-1 text-2xl font-semibold">Employees</h1>
        <button
          className="inline-flex items-center gap-2 rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700"
          onClick={() => toast.info("Create employee form coming soon.")}
        >
          <Plus className="h-4 w-4" />
          Add Employee
        </button>
      </div>

      {loading ? (
        <p className="vf-text-m">Loading...</p>
      ) : employees.length === 0 ? (
        <div className="vf-bg-card vf-border rounded-lg p-8 text-center">
          <p className="vf-text-m">No employees found.</p>
        </div>
      ) : (
        <div className="vf-bg-card vf-border rounded-lg overflow-hidden">
          <table className="w-full text-left text-sm">
            <thead className="vf-border border-b">
              <tr>
                <th className="vf-text-m px-4 py-3 font-medium">Name</th>
                <th className="vf-text-m px-4 py-3 font-medium">Role</th>
                <th className="vf-text-m px-4 py-3 font-medium">Status</th>
                <th className="px-4 py-3" />
              </tr>
            </thead>
            <tbody>
              {employees.map((emp) => (
                <tr key={emp.id} className="vf-border border-b last:border-b-0">
                  <td className="px-4 py-3 flex items-center gap-3">
                    <UserCircle className="h-8 w-8 text-gray-400" />
                    <div>
                      <p className="vf-text-1 font-medium">{emp.name}</p>
                      <p className="vf-text-m text-xs">{emp.email}</p>
                    </div>
                  </td>
                  <td className="vf-text-1 px-4 py-3">{emp.role}</td>
                  <td className="px-4 py-3">
                    <span
                      className={`inline-block rounded-full px-2 py-0.5 text-xs font-medium ${statusColors[emp.status]}`}
                    >
                      {statusLabels[emp.status]}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-right">
                    <button
                      className="inline-flex items-center gap-1 text-sm text-blue-600 hover:underline"
                      onClick={() => toast.info("Edit form coming soon.")}
                    >
                      <Pencil className="h-3.5 w-3.5" />
                      Edit
                    </button>
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
