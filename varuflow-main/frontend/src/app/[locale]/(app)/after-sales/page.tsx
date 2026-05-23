"use client";
import { useEffect, useState } from "react";
import { api } from "@/lib/api-client";
import { toast } from "sonner";

type Tab = "returns" | "warranties" | "surveys";

interface ReturnItem { id: string; customer_id: string; reason: string; description: string | null; photo_url: string | null; status: string; refund_amount: number | null; created_at: string; }
interface WarrantyItem { id: string; customer_id: string; product_name_snapshot: string | null; serial_number: string | null; warranty_months: number; starts_at: string; expires_at: string; status: string; }
interface SurveyItem { id: string; customer_id: string; reference_type: string; score: number | null; comment: string | null; submitted_at: string | null; created_at: string; }

const STATUS_COLORS: Record<string, string> = {
  pending: "bg-yellow-100 text-yellow-800",
  approved: "bg-blue-100 text-blue-800",
  refunded: "bg-green-100 text-green-800",
  rejected: "bg-red-100 text-red-800",
  exchanged: "bg-purple-100 text-purple-800",
  active: "bg-green-100 text-green-800",
  expired: "bg-red-100 text-red-800",
};

export default function AfterSalesPage() {
  const [tab, setTab] = useState<Tab>("returns");
  const [returns, setReturns] = useState<ReturnItem[]>([]);
  const [warranties, setWarranties] = useState<WarrantyItem[]>([]);
  const [surveys, setSurveys] = useState<SurveyItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [resolveId, setResolveId] = useState("");
  const [resolution, setResolution] = useState("");
  const [resolveStatus, setResolveStatus] = useState("approved");

  useEffect(() => {
    setLoading(true);
    if (tab === "returns") {
      api.get<ReturnItem[]>("/api/after-sales/returns").then(setReturns).catch(() => toast.error("Load failed")).finally(() => setLoading(false));
    } else if (tab === "warranties") {
      api.get<WarrantyItem[]>("/api/after-sales/warranties").then(setWarranties).catch(() => toast.error("Load failed")).finally(() => setLoading(false));
    } else {
      api.get<SurveyItem[]>("/api/after-sales/surveys").then(setSurveys).catch(() => toast.error("Load failed")).finally(() => setLoading(false));
    }
  }, [tab]);

  const resolveReturn = async (id: string) => {
    try {
      await api.patch(`/api/after-sales/returns/${id}`, { status: resolveStatus, resolution_notes: resolution || null });
      toast.success("Return updated");
      setResolveId("");
      api.get<ReturnItem[]>("/api/after-sales/returns").then(setReturns);
    } catch {
      toast.error("Failed to update");
    }
  };

  const approveReturn = async (id: string) => {
    try {
      await api.post(`/api/after-sales/returns/${id}/approve`, {});
      toast.success("Return approved — credit note and stock adjustment created");
      api.get<ReturnItem[]>("/api/after-sales/returns").then(setReturns);
    } catch {
      toast.error("Failed to approve");
    }
  };

  const tabs: Tab[] = ["returns", "warranties", "surveys"];
  const TAB_LABELS: Record<Tab, string> = { returns: "Returns & Refunds", warranties: "Warranties", surveys: "Satisfaction Surveys" };

  return (
    <div className="space-y-6 p-6">
      <h1 className="text-2xl font-bold">After-Sales</h1>
      <div className="flex gap-2 border-b">
        {tabs.map(t => (
          <button key={t} onClick={() => setTab(t)} className={`px-4 py-2 text-sm font-medium border-b-2 -mb-px transition-colors ${tab === t ? "border-[#1a2332] text-[#1a2332]" : "border-transparent text-gray-500 hover:text-gray-800"}`}>
            {TAB_LABELS[t]}
          </button>
        ))}
      </div>

      {loading && <p className="text-sm text-gray-500">Loading…</p>}

      {/* Returns */}
      {tab === "returns" && !loading && (
        <div className="space-y-3">
          {returns.length === 0 && <p className="text-sm text-gray-500">No return requests.</p>}
          {returns.map(r => (
            <div key={r.id} className="border rounded p-4 bg-white space-y-2">
              <div className="flex justify-between items-start">
                <div>
                  <p className="font-medium text-sm">{r.reason}</p>
                  {r.description && <p className="text-xs text-gray-500">{r.description}</p>}
                  {r.photo_url && (
                    <a href={r.photo_url} target="_blank" rel="noreferrer" className="text-xs text-indigo-600 hover:underline">View photo</a>
                  )}
                  <p className="text-xs text-gray-400">{new Date(r.created_at).toLocaleDateString()} · Customer {r.customer_id.slice(0, 8)}…</p>
                </div>
                <span className={`text-xs px-2 py-0.5 rounded font-medium ${STATUS_COLORS[r.status] || "bg-gray-100"}`}>{r.status}</span>
              </div>
              {r.status === "pending" && (
                resolveId === r.id ? (
                  <div className="space-y-2 border-t pt-2">
                    <select value={resolveStatus} onChange={e => setResolveStatus(e.target.value)} className="border rounded px-2 py-1 text-xs">
                      {["approved", "rejected", "refunded", "exchanged"].map(s => <option key={s} value={s}>{s}</option>)}
                    </select>
                    <textarea value={resolution} onChange={e => setResolution(e.target.value)} placeholder="Resolution notes…" rows={2} className="w-full border rounded px-2 py-1 text-xs" />
                    <div className="flex gap-2">
                      <button onClick={() => resolveReturn(r.id)} className="px-3 py-1 bg-[#1a2332] text-white text-xs rounded hover:opacity-90">Save</button>
                      <button onClick={() => setResolveId("")} className="px-3 py-1 border text-xs rounded">Cancel</button>
                    </div>
                  </div>
                ) : (
                  <div className="flex items-center gap-3">
                    <button onClick={() => approveReturn(r.id)} className="text-xs text-green-700 font-medium hover:underline">Approve (auto)</button>
                    <button onClick={() => { setResolveId(r.id); setResolution(""); setResolveStatus("approved"); }} className="text-xs text-blue-600 hover:underline">Manual resolve</button>
                  </div>
                )
              )}
            </div>
          ))}
        </div>
      )}

      {/* Warranties */}
      {tab === "warranties" && !loading && (
        <div className="overflow-x-auto">
          <table className="w-full text-sm border rounded bg-white">
            <thead className="bg-gray-50 text-xs text-gray-500 uppercase">
              <tr>
                <th className="text-left px-4 py-2">Product</th>
                <th className="text-left px-4 py-2">Serial</th>
                <th className="text-left px-4 py-2">Months</th>
                <th className="text-left px-4 py-2">Expires</th>
                <th className="text-left px-4 py-2">Status</th>
              </tr>
            </thead>
            <tbody className="divide-y">
              {warranties.length === 0 && <tr><td colSpan={5} className="px-4 py-4 text-sm text-gray-500">No warranty records.</td></tr>}
              {warranties.map(w => (
                <tr key={w.id} className="hover:bg-gray-50">
                  <td className="px-4 py-2">{w.product_name_snapshot || "—"}</td>
                  <td className="px-4 py-2 text-xs">{w.serial_number || "—"}</td>
                  <td className="px-4 py-2">{w.warranty_months}</td>
                  <td className="px-4 py-2 text-xs">{w.expires_at}</td>
                  <td className="px-4 py-2"><span className={`px-2 py-0.5 rounded text-xs font-medium ${STATUS_COLORS[w.status] || "bg-gray-100"}`}>{w.status}</span></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Surveys */}
      {tab === "surveys" && !loading && (
        <div className="space-y-3">
          {surveys.length === 0 && <p className="text-sm text-gray-500">No surveys sent yet.</p>}
          {surveys.map(s => (
            <div key={s.id} className="border rounded p-3 bg-white flex justify-between items-start">
              <div>
                <p className="text-sm font-medium capitalize">{s.reference_type} — Customer {s.customer_id.slice(0, 8)}…</p>
                {s.comment && <p className="text-xs text-gray-500 mt-0.5">"{s.comment}"</p>}
                {s.submitted_at && <p className="text-xs text-gray-400">{new Date(s.submitted_at).toLocaleDateString()}</p>}
              </div>
              <div className="text-right">
                {s.score ? (
                  <div>
                    <span className="text-2xl font-bold">{s.score}</span>
                    <span className="text-xs text-gray-400">/5</span>
                  </div>
                ) : <span className="text-xs text-gray-400 italic">Pending</span>}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
