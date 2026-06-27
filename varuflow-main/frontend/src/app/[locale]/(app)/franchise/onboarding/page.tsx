"use client";

import { useState, useEffect } from "react";
import { toast } from "sonner";
import { api } from "@/lib/api-client";
import { Users, Plus, CheckCircle2, XCircle } from "lucide-react";
import styles from "./page.module.scss";

interface Agreement {
  id: string; franchisee_name: string; franchisee_email: string; franchisee_country?: string;
  royalty_rate: string; royalty_basis: string; billing_cycle: string; status: string;
  start_date?: string; end_date?: string;
}

const STATUS_COLORS: Record<string, string> = {
  pending: "bg-amber-100 text-amber-700",
  active: "bg-green-100 text-green-700",
  terminated: "bg-red-100 text-red-600",
};

const STATUS_MODULE: Record<string, keyof typeof styles> = {
  pending:    "statusPending",
  active:     "statusActive",
  terminated: "statusTerminated",
};

export default function FranchiseeOnboardingPage() {
  const [agreements, setAgreements] = useState<Agreement[]>([]);
  const [showForm, setShowForm] = useState(false);
  const [loading, setLoading] = useState(false);
  const [form, setForm] = useState({
    franchisee_name: "",
    franchisee_email: "",
    franchisee_country: "SE",
    royalty_rate: "0.05",
    royalty_basis: "gross_revenue",
    billing_cycle: "monthly",
    start_date: new Date().toISOString().split("T")[0],
    notes: "",
  });

  async function load() {
    api.get<{agreements: Agreement[]}>("/api/franchise/agreements?limit=50")
      .then(d => setAgreements(d.agreements ?? []))
      .catch(() => {});
  }

  useEffect(() => { load(); }, []);

  async function create() {
    if (!form.franchisee_name || !form.franchisee_email) { toast.error("Name and email required"); return; }
    setLoading(true);
    try {
      await api.post("/api/franchise/agreements", { ...form, royalty_rate: parseFloat(form.royalty_rate) });
      toast.success("Franchisee agreement created");
      setShowForm(false);
      await load();
    } catch (err: any) {
      toast.error(err?.message || "Failed");
    } finally {
      setLoading(false);
    }
  }

  async function activate(id: string) {
    try {
      await api.patch(`/api/franchise/agreements/${id}`, { status: "active" });
      toast.success("Agreement activated");
      await load();
    } catch { /* silent */ }
  }

  async function terminate(id: string) {
    try {
      await api.patch(`/api/franchise/agreements/${id}`, { status: "terminated", end_date: new Date().toISOString().split("T")[0] });
      toast.success("Agreement terminated");
      await load();
    } catch { /* silent */ }
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-gray-900">Franchisee Onboarding</h1>
          <p className="mt-1 text-sm text-gray-500">Register and manage franchise agreements.</p>
        </div>
        <button onClick={() => setShowForm(true)} className="btn-primary flex items-center gap-2">
          <Plus className="h-4 w-4" /> Add Franchisee
        </button>
      </div>

      {showForm && (
        <div className="rounded-xl border border-blue-200 bg-blue-50 p-5 space-y-4">
          <h2 className="text-sm font-semibold text-gray-700">New Franchise Agreement</h2>
          <div className="grid grid-cols-2 gap-3">
            <input className="input col-span-2" placeholder="Franchisee company name*" value={form.franchisee_name} onChange={e => setForm(f => ({ ...f, franchisee_name: e.target.value }))} />
            <input className="input col-span-2" type="email" placeholder="Contact email*" value={form.franchisee_email} onChange={e => setForm(f => ({ ...f, franchisee_email: e.target.value }))} />
            <div>
              <label className="text-xs font-medium text-gray-700 mb-1 block">Country</label>
              <select className="input w-full" value={form.franchisee_country} onChange={e => setForm(f => ({ ...f, franchisee_country: e.target.value }))}>
                <option value="SE">Sweden</option>
                <option value="NO">Norway</option>
                <option value="DK">Denmark</option>
                <option value="FI">Finland</option>
                <option value="DE">Germany</option>
                <option value="NL">Netherlands</option>
              </select>
            </div>
            <div>
              <label className="text-xs font-medium text-gray-700 mb-1 block">Royalty Basis</label>
              <select className="input w-full" value={form.royalty_basis} onChange={e => setForm(f => ({ ...f, royalty_basis: e.target.value }))}>
                <option value="gross_revenue">% of Gross Revenue</option>
                <option value="net_revenue">% of Net Revenue</option>
                <option value="fixed">Fixed Amount</option>
              </select>
            </div>
            <div>
              <label className="text-xs font-medium text-gray-700 mb-1 block">
                {form.royalty_basis === "fixed" ? "Fixed Amount per Period" : "Royalty Rate (e.g. 0.05 = 5%)"}
              </label>
              <input className="input w-full" type="number" step="0.01" value={form.royalty_rate} onChange={e => setForm(f => ({ ...f, royalty_rate: e.target.value }))} />
            </div>
            <div>
              <label className="text-xs font-medium text-gray-700 mb-1 block">Billing Cycle</label>
              <select className="input w-full" value={form.billing_cycle} onChange={e => setForm(f => ({ ...f, billing_cycle: e.target.value }))}>
                <option value="monthly">Monthly</option>
                <option value="quarterly">Quarterly</option>
              </select>
            </div>
            <div>
              <label className="text-xs font-medium text-gray-700 mb-1 block">Start Date</label>
              <input className="input w-full" type="date" value={form.start_date} onChange={e => setForm(f => ({ ...f, start_date: e.target.value }))} />
            </div>
            <textarea className="input col-span-2 h-20 resize-none" placeholder="Notes (optional)" value={form.notes} onChange={e => setForm(f => ({ ...f, notes: e.target.value }))} />
          </div>
          <div className="flex gap-2">
            <button onClick={create} disabled={loading} className="btn-primary">{loading ? "Creating…" : "Create Agreement"}</button>
            <button onClick={() => setShowForm(false)} className="btn-secondary">Cancel</button>
          </div>
        </div>
      )}

      {/* Agreement list */}
      {agreements.length === 0 ? (
        <div className="rounded-xl border border-dashed border-gray-300 p-12 text-center text-sm text-gray-400">
          No franchise agreements yet.
        </div>
      ) : (
        <div className="space-y-3">
          {agreements.map(a => (
            <div key={a.id} className="rounded-xl border border-gray-200 bg-white p-5">
              <div className="flex items-start justify-between gap-4">
                <div className="flex items-center gap-3">
                  <Users className="h-5 w-5 text-gray-400" />
                  <div>
                    <p className="font-medium text-gray-900">{a.franchisee_name}</p>
                    <p className="text-xs text-gray-500">{a.franchisee_email} · {a.franchisee_country}</p>
                  </div>
                </div>
                <span className={styles[STATUS_MODULE[a.status] ?? "statusPending"]}>
                  {a.status}
                </span>
              </div>
              <div className="mt-3 flex flex-wrap gap-3 text-xs text-gray-500">
                <span>
                  Royalty: {a.royalty_basis === "fixed"
                    ? `Fixed`
                    : `${(parseFloat(a.royalty_rate) * 100).toFixed(1)}% of ${a.royalty_basis.replace("_", " ")}`
                  }
                </span>
                <span>Billing: {a.billing_cycle}</span>
                {a.start_date && <span>Since: {a.start_date}</span>}
              </div>
              <div className="mt-3 flex gap-2">
                {a.status === "pending" && (
                  <button onClick={() => activate(a.id)} className="btn-sm-outline flex items-center gap-1 text-green-700 border-green-300">
                    <CheckCircle2 className="h-3.5 w-3.5" /> Activate
                  </button>
                )}
                {a.status === "active" && (
                  <button onClick={() => terminate(a.id)} className="btn-sm-danger-outline flex items-center gap-1">
                    <XCircle className="h-3.5 w-3.5" /> Terminate
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
