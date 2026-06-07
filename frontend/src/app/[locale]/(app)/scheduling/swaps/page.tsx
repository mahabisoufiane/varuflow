"use client";

import { useState, useEffect } from "react";
import { toast } from "sonner";
import { ArrowLeftRight, Check, X } from "lucide-react";
import { api } from "@/lib/api-client";
import styles from "./page.module.scss";

interface SwapRequest {
  id: string; requester_shift_id: string; requester_staff_id: string;
  target_staff_id: string; status: string; manager_notes: string | null;
  created_at: string | null; resolved_at: string | null;
}
interface Staff { id: string; name: string }

const STATUS_COLORS: Record<string, string> = {
  pending: "bg-amber-100 text-amber-700",
  approved: "bg-green-100 text-green-700",
  rejected: "bg-red-100 text-red-700",
};

const STATUS_MODULE: Record<string, keyof typeof styles> = {
  pending:  "statusPending",
  approved: "statusApproved",
  rejected: "statusRejected",
};

export default function SwapsPage() {
  const [swaps, setSwaps] = useState<SwapRequest[]>([]);
  const [staff, setStaff] = useState<Staff[]>([]);
  const [loading, setLoading] = useState(true);
  const [filterStatus, setFilterStatus] = useState("");

  async function load() {
    const params = filterStatus ? `?status=${filterStatus}` : "";
    const [s, st] = await Promise.all([
      api.get<SwapRequest[]>(`/api/scheduling/swap-requests${params}`).catch(() => [] as SwapRequest[]),
      api.get<Staff[]>("/api/hr/employees").catch(() => [] as Staff[]),
    ]);
    setSwaps(s); setStaff(st); setLoading(false);
  }

  useEffect(() => { load(); }, [filterStatus]);

  async function decide(id: string, status: "approved" | "rejected") {
    try {
      await api.patch(`/api/scheduling/swap-requests/${id}`, { status });
      toast.success(status === "approved" ? "Swap approved" : "Swap rejected");
      load();
    } catch {
      toast.error("Failed to update swap request");
    }
  }

  const staffMap = Object.fromEntries(staff.map(s => [s.id, s.name]));

  if (loading) return <div className="animate-pulse space-y-4">{[1,2,3].map(i => <div key={i} className="h-16 rounded-xl bg-gray-100" />)}</div>;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold text-gray-900">Shift Swap Requests</h1>
        <p className="mt-1 text-sm text-gray-500">Review and approve staff shift swap requests.</p>
      </div>

      <div className="flex gap-2">
        {["", "pending", "approved", "rejected"].map(s => (
          <button key={s} onClick={() => setFilterStatus(s)}
            className={`px-3 py-1.5 text-sm rounded-lg border ${filterStatus === s ? "border-blue-400 bg-blue-50 text-blue-700" : "border-gray-200 text-gray-600 hover:bg-gray-50"}`}>
            {s || "All"}
          </button>
        ))}
      </div>

      {swaps.length === 0 && (
        <div className="text-center py-12 text-gray-400"><ArrowLeftRight className="h-10 w-10 mx-auto mb-3 opacity-40" /><p>No swap requests.</p></div>
      )}

      <div className="space-y-2">
        {swaps.map(swap => (
          <div key={swap.id} className="rounded-xl border border-gray-200 bg-white p-4 flex items-center gap-4">
            <ArrowLeftRight className="h-5 w-5 text-gray-400 flex-shrink-0" />
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2 flex-wrap">
                <span className="font-medium text-gray-900">{staffMap[swap.requester_staff_id] || "Requester"}</span>
                <span className="text-gray-400">→</span>
                <span className="font-medium text-gray-900">{staffMap[swap.target_staff_id] || "Target"}</span>
                <span className={styles[STATUS_MODULE[swap.status] ?? "statusPending"]}>{swap.status}</span>
              </div>
              <div className="flex gap-3 text-xs text-gray-500 mt-0.5">
                {swap.created_at && <span>Requested: {new Date(swap.created_at).toLocaleDateString("sv-SE")}</span>}
                {swap.manager_notes && <span>· Note: {swap.manager_notes}</span>}
              </div>
            </div>
            {swap.status === "pending" && (
              <div className="flex gap-1 flex-shrink-0">
                <button onClick={() => decide(swap.id, "approved")} className="p-2 rounded-lg bg-green-100 text-green-700 hover:bg-green-200"><Check className="h-4 w-4" /></button>
                <button onClick={() => decide(swap.id, "rejected")} className="p-2 rounded-lg bg-red-100 text-red-700 hover:bg-red-200"><X className="h-4 w-4" /></button>
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
