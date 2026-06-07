"use client";

import { useState, useEffect } from "react";
import { api } from "@/lib/api-client";
import { toast } from "sonner";
import { ArrowLeftRight, Plus, CheckCircle2 } from "lucide-react";

interface Transfer { id: string; from_org_id: string; to_org_id: string; transfer_type: string; quantity?: string; transfer_price: string; currency: string; transfer_date: string; status: string; description?: string; reference?: string }
interface Entity { id: string; name: string }

export default function IntercompanyPage() {
  const [transfers, setTransfers] = useState<Transfer[]>([]);
  const [entities, setEntities] = useState<Entity[]>([]);
  const [showForm, setShowForm] = useState(false);
  const [posting, setPosting] = useState<string | null>(null);
  const [form, setForm] = useState({
    to_org_id: "",
    transfer_type: "stock",
    transfer_price: "",
    currency: "SEK",
    transfer_date: new Date().toISOString().split("T")[0],
    quantity: "",
    description: "",
    reference: "",
  });

  async function load() {
    const [tResult, eResult] = await Promise.all([
      api.get<{ transfers: Transfer[] }>("/api/multi-entity/transfers?limit=50").catch(() => null),
      api.get<{ entities: Entity[] }>("/api/multi-entity/entities").catch(() => null),
    ]);
    if (tResult) setTransfers(tResult.transfers);
    if (eResult) setEntities(eResult.entities);
  }

  useEffect(() => { load(); }, []);

  async function create() {
    if (!form.to_org_id || !form.transfer_price) { toast.error("Target entity and amount required"); return; }
    try {
      await api.post("/api/multi-entity/transfers", {
        ...form,
        transfer_price: parseFloat(form.transfer_price),
        quantity: form.quantity ? parseFloat(form.quantity) : undefined,
      });
      toast.success("Transfer created");
      setShowForm(false);
      await load();
    } catch (err: any) {
      toast.error(err.message || "Failed");
    }
  }

  async function postTransfer(id: string) {
    setPosting(id);
    try {
      await api.patch(`/api/multi-entity/transfers/${id}/post`, {});
      toast.success("Transfer posted — elimination entry created");
      await load();
    } catch (err: any) {
      toast.error(err.message || "Post failed");
    }
    setPosting(null);
  }

  const entityName = (id: string) => entities.find(e => e.id === id)?.name || id.slice(0, 8);

  const statusColor: Record<string, string> = {
    draft: "bg-gray-100 text-gray-600",
    posted: "bg-green-100 text-green-700",
    eliminated: "bg-purple-100 text-purple-700",
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-gray-900">Intercompany Transfers</h1>
          <p className="mt-1 text-sm text-gray-500">Stock, cash, and service transfers between group entities with transfer pricing.</p>
        </div>
        <button onClick={() => setShowForm(true)} className="btn-primary flex items-center gap-2">
          <Plus className="h-4 w-4" /> New Transfer
        </button>
      </div>

      {showForm && (
        <div className="rounded-xl border border-blue-200 bg-blue-50 p-4 space-y-3">
          <div className="grid grid-cols-2 gap-3">
            <div className="col-span-2">
              <label className="text-xs font-medium text-gray-700 mb-1 block">Target Entity*</label>
              <select className="input w-full" value={form.to_org_id} onChange={e => setForm(f => ({ ...f, to_org_id: e.target.value }))}>
                <option value="">Select entity…</option>
                {entities.map(e => <option key={e.id} value={e.id}>{e.name}</option>)}
              </select>
            </div>
            <div>
              <label className="text-xs font-medium text-gray-700 mb-1 block">Type</label>
              <select className="input w-full" value={form.transfer_type} onChange={e => setForm(f => ({ ...f, transfer_type: e.target.value }))}>
                <option value="stock">Stock</option>
                <option value="cash">Cash</option>
                <option value="service">Service</option>
              </select>
            </div>
            <div>
              <label className="text-xs font-medium text-gray-700 mb-1 block">Transfer Date</label>
              <input className="input w-full" type="date" value={form.transfer_date} onChange={e => setForm(f => ({ ...f, transfer_date: e.target.value }))} />
            </div>
            <div>
              <label className="text-xs font-medium text-gray-700 mb-1 block">Transfer Price*</label>
              <input className="input w-full" type="number" placeholder="0.00" value={form.transfer_price} onChange={e => setForm(f => ({ ...f, transfer_price: e.target.value }))} />
            </div>
            <div>
              <label className="text-xs font-medium text-gray-700 mb-1 block">Quantity (stock only)</label>
              <input className="input w-full" type="number" placeholder="Optional" value={form.quantity} onChange={e => setForm(f => ({ ...f, quantity: e.target.value }))} />
            </div>
            <div className="col-span-2">
              <label className="text-xs font-medium text-gray-700 mb-1 block">Description</label>
              <input className="input w-full" placeholder="Optional" value={form.description} onChange={e => setForm(f => ({ ...f, description: e.target.value }))} />
            </div>
          </div>
          <div className="flex gap-2">
            <button onClick={create} className="btn-primary">Create</button>
            <button onClick={() => setShowForm(false)} className="btn-secondary">Cancel</button>
          </div>
        </div>
      )}

      {/* Transfer list */}
      {transfers.length === 0 ? (
        <div className="rounded-xl border border-dashed border-gray-300 p-12 text-center text-sm text-gray-400">
          No intercompany transfers yet.
        </div>
      ) : (
        <div className="space-y-2">
          {transfers.map(t => (
            <div key={t.id} className="flex items-center gap-4 rounded-xl border border-gray-200 bg-white p-4">
              <ArrowLeftRight className="h-4 w-4 text-gray-400 flex-shrink-0" />
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium text-gray-900">
                  {entityName(t.from_org_id)} → {entityName(t.to_org_id)}
                </p>
                <p className="text-xs text-gray-500 capitalize">
                  {t.transfer_type} · {t.transfer_price} {t.currency} · {t.transfer_date}
                </p>
                {t.description && <p className="text-xs text-gray-400 italic">{t.description}</p>}
              </div>
              <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${statusColor[t.status] || "bg-gray-100 text-gray-600"}`}>
                {t.status}
              </span>
              {t.status === "draft" && (
                <button
                  onClick={() => postTransfer(t.id)}
                  disabled={posting === t.id}
                  className="btn-sm-outline flex items-center gap-1 text-green-700 border-green-300"
                >
                  <CheckCircle2 className="h-3.5 w-3.5" />
                  {posting === t.id ? "Posting…" : "Post"}
                </button>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
