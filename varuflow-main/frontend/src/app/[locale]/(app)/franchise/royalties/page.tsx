"use client";

import { useState, useEffect } from "react";
import { toast } from "sonner";
import { api } from "@/lib/api-client";
import { Receipt, Calculator, Send, CheckCircle2 } from "lucide-react";
import styles from "./page.module.scss";

interface Agreement { id: string; franchisee_name: string; royalty_basis: string; billing_cycle: string; status: string }
interface Royalty { id: string; agreement_id: string; period: string; revenue_basis?: string; royalty_amount: string; currency: string; status: string; due_date?: string; paid_at?: string }

const STATUS_COLORS: Record<string, string> = {
  draft: "bg-gray-100 text-gray-600",
  sent: "bg-blue-100 text-blue-700",
  paid: "bg-green-100 text-green-700",
  overdue: "bg-red-100 text-red-600",
};

const STATUS_MODULE: Record<string, keyof typeof styles> = {
  draft:   "statusDraft",
  sent:    "statusSent",
  paid:    "statusPaid",
  overdue: "statusOverdue",
};

export default function RoyaltiesPage() {
  const now = new Date();
  const [period, setPeriod] = useState(`${now.getFullYear()}-${String(now.getMonth()).padStart(2, "0") || "12"}`);
  const [agreements, setAgreements] = useState<Agreement[]>([]);
  const [royalties, setRoyalties] = useState<Royalty[]>([]);
  const [selectedAgreement, setSelectedAgreement] = useState("");
  const [revenueBasis, setRevenueBasis] = useState("");
  const [calculating, setCalculating] = useState(false);
  const [sending, setSending] = useState<string | null>(null);
  const [marking, setMarking] = useState<string | null>(null);


  async function load() {
    const [aRes, rRes] = await Promise.all([
      api.get<{agreements: Agreement[]}>("/api/franchise/agreements?status=active&limit=50").catch(() => null),
      api.get<{royalties: Royalty[]}>("/api/franchise/royalties?limit=50").catch(() => null),
    ]);
    if (aRes) setAgreements(aRes.agreements ?? []);
    if (rRes) setRoyalties(rRes.royalties ?? []);
  }

  useEffect(() => { load(); }, []);

  async function calculate() {
    if (!selectedAgreement) { toast.error("Select an agreement"); return; }
    setCalculating(true);
    try {
      const body: Record<string, unknown> = {};
      if (revenueBasis) body.revenue_basis = parseFloat(revenueBasis);
      await api.post(`/api/franchise/royalties/calculate/${selectedAgreement}/${period}`, body);
      toast.success("Royalty calculated");
      await load();
    } catch (err: any) {
      toast.error(err?.message || "Calculation failed");
    } finally {
      setCalculating(false);
    }
  }

  async function send(id: string) {
    setSending(id);
    try {
      await api.post(`/api/franchise/royalties/${id}/send`, {});
      toast.success("Royalty billing sent");
      await load();
    } catch { toast.error("Failed to send"); }
    setSending(null);
  }

  async function markPaid(id: string) {
    setMarking(id);
    try {
      await api.patch(`/api/franchise/royalties/${id}/mark-paid`, {});
      toast.success("Marked as paid");
      await load();
    } catch { toast.error("Failed"); }
    setMarking(null);
  }

  const agreementName = (id: string) => agreements.find(a => a.id === id)?.franchisee_name || id.slice(0, 8);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold text-gray-900">Royalty Billing</h1>
        <p className="mt-1 text-sm text-gray-500">Calculate and issue royalty invoices to franchisees.</p>
      </div>

      {/* Calculate form */}
      <div className="rounded-xl border border-gray-200 bg-white p-5 space-y-4">
        <h2 className="text-sm font-semibold text-gray-700">Calculate Royalty</h2>
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          <div className="col-span-2">
            <label className="text-xs font-medium text-gray-700 mb-1 block">Franchisee</label>
            <select className="input w-full" value={selectedAgreement} onChange={e => setSelectedAgreement(e.target.value)}>
              <option value="">Select franchisee…</option>
              {agreements.map(a => <option key={a.id} value={a.id}>{a.franchisee_name}</option>)}
            </select>
          </div>
          <div>
            <label className="text-xs font-medium text-gray-700 mb-1 block">Period</label>
            <input className="input w-full" type="month" value={period} onChange={e => setPeriod(e.target.value)} />
          </div>
          <div>
            <label className="text-xs font-medium text-gray-700 mb-1 block">Revenue (if % basis)</label>
            <input className="input w-full" type="number" placeholder="e.g. 500000" value={revenueBasis} onChange={e => setRevenueBasis(e.target.value)} />
          </div>
        </div>
        <button onClick={calculate} disabled={calculating} className="btn-primary flex items-center gap-2">
          <Calculator className="h-4 w-4" />
          {calculating ? "Calculating…" : "Calculate & Draft"}
        </button>
      </div>

      {/* Royalty list */}
      {royalties.length === 0 ? (
        <div className="rounded-xl border border-dashed border-gray-300 p-10 text-center text-sm text-gray-400">
          No royalty billings yet. Calculate one above.
        </div>
      ) : (
        <div className="space-y-2">
          {royalties.map(r => (
            <div key={r.id} className="flex items-center gap-4 rounded-xl border border-gray-200 bg-white p-4">
              <Receipt className="h-4 w-4 text-gray-400 flex-shrink-0" />
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium text-gray-900">{agreementName(r.agreement_id)} · {r.period}</p>
                <p className="text-xs text-gray-500">
                  {r.royalty_amount} {r.currency}
                  {r.revenue_basis ? ` (${r.revenue_basis} basis)` : ""}
                  {r.due_date ? ` · Due ${r.due_date}` : ""}
                  {r.paid_at ? ` · Paid ${new Date(r.paid_at).toLocaleDateString()}` : ""}
                </p>
              </div>
              <span className={styles[STATUS_MODULE[r.status] ?? "statusDraft"]}>
                {r.status}
              </span>
              <div className="flex gap-2 flex-shrink-0">
                {r.status === "draft" && (
                  <button onClick={() => send(r.id)} disabled={sending === r.id} className="btn-sm-outline flex items-center gap-1">
                    <Send className="h-3.5 w-3.5" /> {sending === r.id ? "Sending…" : "Send"}
                  </button>
                )}
                {r.status === "sent" && (
                  <button onClick={() => markPaid(r.id)} disabled={marking === r.id} className="btn-sm-outline text-green-700 border-green-300 flex items-center gap-1">
                    <CheckCircle2 className="h-3.5 w-3.5" /> {marking === r.id ? "…" : "Mark Paid"}
                  </button>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
