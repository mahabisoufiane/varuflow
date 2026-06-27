"use client";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { portalApi, PORTAL_TOKEN_KEY } from "@/lib/portal-client";
import { toast } from "sonner";

interface ReturnReq {
  id: string;
  invoice_id: string | null;
  product_id: string | null;
  reason: string;
  description: string | null;
  status: string;
  resolution_notes: string | null;
  refund_amount: number | null;
  resolved_at: string | null;
  created_at: string;
}

const REASON_LABELS: Record<string, string> = {
  defective: "Defective / not working",
  wrong_item: "Wrong item sent",
  not_as_described: "Not as described",
  changed_mind: "Changed mind",
  other: "Other",
};

const STATUS_COLORS: Record<string, string> = {
  pending: "bg-yellow-100 text-yellow-800",
  approved: "bg-blue-100 text-blue-800",
  refunded: "bg-green-100 text-green-800",
  exchanged: "bg-purple-100 text-purple-800",
  rejected: "bg-red-100 text-red-800",
};

export default function PortalReturnsPage() {
  const router = useRouter();
  const [returns, setReturns] = useState<ReturnReq[]>([]);
  const [showForm, setShowForm] = useState(false);
  const [invoiceId, setInvoiceId] = useState("");
  const [reason, setReason] = useState("defective");
  const [description, setDescription] = useState("");
  const [photoUrl, setPhotoUrl] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const load = () => {
    portalApi.get<ReturnReq[]>("/api/portal/returns").then(setReturns).catch(() => {});
  };

  useEffect(() => {
    if (!localStorage.getItem(PORTAL_TOKEN_KEY)) { router.replace("/portal/login"); return; }
    load();
  }, []);

  const submit = async () => {
    setSubmitting(true);
    try {
      await portalApi.post("/api/portal/returns", {
        invoice_id: invoiceId || null,
        reason,
        description: description || null,
        photo_url: photoUrl || null,
      });
      toast.success("Return request submitted");
      setShowForm(false);
      setInvoiceId(""); setReason("defective"); setDescription(""); setPhotoUrl("");
      load();
    } catch {
      toast.error("Failed to submit return request");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="space-y-4">
      <div className="flex justify-between items-center">
        <h1 className="text-xl font-bold">Returns & Refunds</h1>
        <button onClick={() => setShowForm(s => !s)} className="px-3 py-1.5 bg-[#1a2332] text-white text-sm rounded hover:opacity-90">
          {showForm ? "Cancel" : "+ New Request"}
        </button>
      </div>

      {showForm && (
        <div className="border rounded p-4 space-y-3 bg-white">
          <h2 className="font-semibold text-sm">Submit a return request</h2>
          <div>
            <label className="text-xs text-gray-500">Invoice ID (optional)</label>
            <input className="mt-1 block w-full border rounded px-3 py-2 text-sm" placeholder="Paste invoice ID" value={invoiceId} onChange={e => setInvoiceId(e.target.value)} />
          </div>
          <div>
            <label className="text-xs text-gray-500">Reason</label>
            <select className="mt-1 block w-full border rounded px-3 py-2 text-sm" value={reason} onChange={e => setReason(e.target.value)}>
              {Object.entries(REASON_LABELS).map(([v, l]) => <option key={v} value={v}>{l}</option>)}
            </select>
          </div>
          <div>
            <label className="text-xs text-gray-500">Description</label>
            <textarea className="mt-1 block w-full border rounded px-3 py-2 text-sm" rows={3} placeholder="Describe the issue…" value={description} onChange={e => setDescription(e.target.value)} />
          </div>
          <div>
            <label className="text-xs text-gray-500">Photo URL (optional — paste a link to a photo of the issue)</label>
            <input type="url" className="mt-1 block w-full border rounded px-3 py-2 text-sm" placeholder="https://…" value={photoUrl} onChange={e => setPhotoUrl(e.target.value)} />
          </div>
          <button onClick={submit} disabled={submitting} className="px-4 py-2 bg-[#1a2332] text-white text-sm rounded hover:opacity-90 disabled:opacity-50">
            {submitting ? "Submitting…" : "Submit Request"}
          </button>
        </div>
      )}

      {returns.length === 0 && !showForm && <p className="text-sm text-gray-500">No return requests yet.</p>}
      <div className="space-y-2">
        {returns.map(r => (
          <div key={r.id} className="border rounded p-3 bg-white space-y-1">
            <div className="flex justify-between items-center">
              <span className="text-sm font-medium">{REASON_LABELS[r.reason] || r.reason}</span>
              <span className={`text-xs px-2 py-0.5 rounded font-medium ${STATUS_COLORS[r.status] || "bg-gray-100"}`}>{r.status}</span>
            </div>
            {r.description && <p className="text-xs text-gray-500">{r.description}</p>}
            {r.resolution_notes && <p className="text-xs text-green-700 border-t pt-1">{r.resolution_notes}</p>}
            {r.refund_amount && <p className="text-xs text-green-700">Refund: {r.refund_amount.toLocaleString()}</p>}
            <p className="text-xs text-gray-400">{new Date(r.created_at).toLocaleDateString()}</p>
          </div>
        ))}
      </div>
    </div>
  );
}
