"use client";

import { useState, useEffect } from "react";
import { toast } from "sonner";
import { Users, Plus, Handshake, Check, X, ChevronDown, ChevronUp, DollarSign } from "lucide-react";

interface PartnerProgram { id: string; name: string; commission_type: string; commission_rate: number; currency: string; is_active: boolean }
interface Partner { id: string; company_name: string; contact_name: string | null; contact_email: string; referral_code: string; status: string; program_id: string | null; total_referred_revenue: number; total_commission_earned: number; commission_pending: number }
interface Deal { id: string; partner_id: string; deal_name: string | null; stage: string; deal_value: number; commission_amount: number; created_at: string | null }

const STATUS_COLORS: Record<string, string> = {
  pending: "bg-yellow-100 text-yellow-700",
  active: "bg-green-100 text-green-700",
  suspended: "bg-orange-100 text-orange-700",
  terminated: "bg-red-100 text-red-700",
};

const DEAL_STAGE_COLORS: Record<string, string> = {
  registered: "bg-blue-100 text-blue-700",
  approved: "bg-green-100 text-green-700",
  paid: "bg-purple-100 text-purple-700",
};

export default function PartnersPage() {
  const apiBase = process.env.NEXT_PUBLIC_API_URL!;
  const f = (url: string, init?: RequestInit) => fetch(`${apiBase}${url}`, { credentials: "include", ...init });

  const [programs, setPrograms] = useState<PartnerProgram[]>([]);
  const [partners, setPartners] = useState<Partner[]>([]);
  const [deals, setDeals] = useState<Deal[]>([]);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState<"partners" | "programs">("partners");
  const [expandedPartner, setExpandedPartner] = useState<string | null>(null);

  // New partner form
  const [showPartnerForm, setShowPartnerForm] = useState(false);
  const [newPartner, setNewPartner] = useState({ company_name: "", contact_name: "", contact_email: "", program_id: "" });

  // New program form
  const [showProgramForm, setShowProgramForm] = useState(false);
  const [newProgram, setNewProgram] = useState({ name: "", commission_type: "percentage", commission_rate: 0.05, currency: "SEK" });

  const fmt = (v: number) => v.toLocaleString("sv-SE", { maximumFractionDigits: 0 });

  useEffect(() => {
    Promise.all([
      f("/api/growth/programs").then(r => r.ok ? r.json() : []).then(setPrograms),
      f("/api/growth/partners").then(r => r.ok ? r.json() : []).then(setPartners),
      f("/api/growth/deals").then(r => r.ok ? r.json() : []).then(setDeals),
    ]).finally(() => setLoading(false));
  }, []);

  async function createPartner() {
    if (!newPartner.company_name || !newPartner.contact_email) {
      toast.error("Company name and email are required");
      return;
    }
    const res = await f("/api/growth/partners", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ ...newPartner, program_id: newPartner.program_id || null }),
    });
    if (!res.ok) { toast.error("Failed to create partner"); return; }
    const created = await res.json();
    setPartners(prev => [created, ...prev]);
    setShowPartnerForm(false);
    setNewPartner({ company_name: "", contact_name: "", contact_email: "", program_id: "" });
    toast.success("Partner added");
  }

  async function createProgram() {
    if (!newProgram.name) { toast.error("Name is required"); return; }
    const res = await f("/api/growth/programs", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify(newProgram),
    });
    if (!res.ok) { toast.error("Failed to create program"); return; }
    const created = await res.json();
    setPrograms(prev => [created, ...prev]);
    setShowProgramForm(false);
    toast.success("Program created");
  }

  async function updateDealStage(dealId: string, stage: string) {
    const res = await f(`/api/growth/deals/${dealId}/stage`, {
      method: "PATCH", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ stage }),
    });
    if (!res.ok) { toast.error("Failed to update deal"); return; }
    const updated = await res.json();
    setDeals(prev => prev.map(d => d.id === dealId ? updated : d));
    // Refresh partner totals
    f("/api/growth/partners").then(r => r.ok ? r.json() : null).then(d => d && setPartners(d));
    toast.success("Deal updated");
  }

  async function deletePartner(id: string) {
    await f(`/api/growth/partners/${id}`, { method: "DELETE" });
    setPartners(prev => prev.filter(p => p.id !== id));
    toast.success("Partner removed");
  }

  const partnerDeals = (partnerId: string) => deals.filter(d => d.partner_id === partnerId);
  const programMap = Object.fromEntries(programs.map(p => [p.id, p.name]));

  const totalPending = partners.reduce((s, p) => s + p.commission_pending, 0);
  const totalEarned = partners.reduce((s, p) => s + p.total_commission_earned, 0);

  if (loading) return <div className="animate-pulse space-y-4">{[1,2,3].map(i => <div key={i} className="h-20 rounded-xl bg-gray-100" />)}</div>;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-gray-900">Partner Program</h1>
          <p className="mt-1 text-sm text-gray-500">Track B2B affiliates, referral deals and commission payouts.</p>
        </div>
        <button
          onClick={() => activeTab === "partners" ? setShowPartnerForm(true) : setShowProgramForm(true)}
          className="btn-primary flex items-center gap-2"
        >
          <Plus className="h-4 w-4" />
          {activeTab === "partners" ? "Add Partner" : "New Program"}
        </button>
      </div>

      {/* Summary */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <div className="rounded-xl border border-gray-200 bg-white p-4">
          <p className="text-xs font-medium text-gray-500 uppercase">Partners</p>
          <p className="text-2xl font-bold text-gray-900 mt-1">{partners.length}</p>
          <p className="text-xs text-gray-400">{partners.filter(p => p.status === "active").length} active</p>
        </div>
        <div className="rounded-xl border border-gray-200 bg-white p-4">
          <p className="text-xs font-medium text-gray-500 uppercase">Commission Earned</p>
          <p className="text-2xl font-bold text-gray-900 mt-1">{fmt(totalEarned)}</p>
        </div>
        <div className="rounded-xl border border-amber-200 bg-amber-50 p-4">
          <p className="text-xs font-medium text-amber-600 uppercase">Commission Pending</p>
          <p className="text-2xl font-bold text-amber-800 mt-1">{fmt(totalPending)}</p>
          <p className="text-xs text-amber-600">Awaiting payout</p>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex gap-2 border-b border-gray-200">
        {(["partners", "programs"] as const).map(tab => (
          <button key={tab} onClick={() => setActiveTab(tab)}
            className={`px-4 py-2 text-sm font-medium capitalize border-b-2 -mb-px transition-all ${
              activeTab === tab ? "border-blue-500 text-blue-600" : "border-transparent text-gray-500 hover:text-gray-700"
            }`}>{tab}</button>
        ))}
      </div>

      {/* New Partner Form */}
      {showPartnerForm && activeTab === "partners" && (
        <div className="rounded-xl border border-blue-200 bg-blue-50 p-4 space-y-3">
          <p className="text-sm font-semibold text-blue-800">New Partner</p>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <input className="input" placeholder="Company name *" value={newPartner.company_name} onChange={e => setNewPartner(p => ({ ...p, company_name: e.target.value }))} />
            <input className="input" placeholder="Contact email *" type="email" value={newPartner.contact_email} onChange={e => setNewPartner(p => ({ ...p, contact_email: e.target.value }))} />
            <input className="input" placeholder="Contact name" value={newPartner.contact_name} onChange={e => setNewPartner(p => ({ ...p, contact_name: e.target.value }))} />
            <select className="input" value={newPartner.program_id} onChange={e => setNewPartner(p => ({ ...p, program_id: e.target.value }))}>
              <option value="">No program</option>
              {programs.map(p => <option key={p.id} value={p.id}>{p.name}</option>)}
            </select>
          </div>
          <div className="flex gap-2">
            <button onClick={createPartner} className="btn-primary text-sm">Create</button>
            <button onClick={() => setShowPartnerForm(false)} className="btn-secondary text-sm">Cancel</button>
          </div>
        </div>
      )}

      {/* New Program Form */}
      {showProgramForm && activeTab === "programs" && (
        <div className="rounded-xl border border-blue-200 bg-blue-50 p-4 space-y-3">
          <p className="text-sm font-semibold text-blue-800">New Program</p>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <input className="input sm:col-span-2" placeholder="Program name *" value={newProgram.name} onChange={e => setNewProgram(p => ({ ...p, name: e.target.value }))} />
            <select className="input" value={newProgram.commission_type} onChange={e => setNewProgram(p => ({ ...p, commission_type: e.target.value }))}>
              <option value="percentage">Percentage of deal</option>
              <option value="fixed">Fixed amount per deal</option>
            </select>
            <input className="input" type="number" placeholder={newProgram.commission_type === "percentage" ? "Rate (e.g. 0.05 = 5%)" : "Fixed amount"} value={newProgram.commission_rate} onChange={e => setNewProgram(p => ({ ...p, commission_rate: parseFloat(e.target.value) || 0 }))} step="0.01" />
          </div>
          <div className="flex gap-2">
            <button onClick={createProgram} className="btn-primary text-sm">Create</button>
            <button onClick={() => setShowProgramForm(false)} className="btn-secondary text-sm">Cancel</button>
          </div>
        </div>
      )}

      {/* Partners list */}
      {activeTab === "partners" && (
        <div className="space-y-3">
          {partners.length === 0 && (
            <div className="text-center py-12 text-gray-400">
              <Users className="h-8 w-8 mx-auto mb-2 opacity-40" />
              <p>No partners yet. Add your first partner to get started.</p>
            </div>
          )}
          {partners.map(partner => {
            const pDeals = partnerDeals(partner.id);
            const isExpanded = expandedPartner === partner.id;
            return (
              <div key={partner.id} className="rounded-xl border border-gray-200 bg-white overflow-hidden">
                <div className="p-4 flex items-center gap-4">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className="font-semibold text-gray-900">{partner.company_name}</span>
                      <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${STATUS_COLORS[partner.status] || "bg-gray-100 text-gray-600"}`}>
                        {partner.status}
                      </span>
                      <span className="text-xs text-gray-400 font-mono">#{partner.referral_code}</span>
                      {partner.program_id && <span className="text-xs text-blue-600">{programMap[partner.program_id] || "Program"}</span>}
                    </div>
                    <p className="text-xs text-gray-500 mt-0.5">{partner.contact_email}</p>
                  </div>
                  <div className="hidden sm:flex gap-4 text-right">
                    <div>
                      <p className="text-xs text-gray-400">Revenue</p>
                      <p className="text-sm font-semibold text-gray-900">{fmt(partner.total_referred_revenue)}</p>
                    </div>
                    <div>
                      <p className="text-xs text-gray-400">Pending</p>
                      <p className="text-sm font-semibold text-amber-700">{fmt(partner.commission_pending)}</p>
                    </div>
                  </div>
                  <div className="flex items-center gap-1">
                    <button onClick={() => setExpandedPartner(isExpanded ? null : partner.id)}
                      className="p-1.5 rounded-lg hover:bg-gray-100 text-gray-400">
                      {isExpanded ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
                    </button>
                    <button onClick={() => deletePartner(partner.id)} className="p-1.5 rounded-lg hover:bg-red-50 text-gray-400 hover:text-red-500">
                      <X className="h-4 w-4" />
                    </button>
                  </div>
                </div>

                {isExpanded && (
                  <div className="border-t border-gray-100 p-4 bg-gray-50">
                    <p className="text-xs font-semibold text-gray-500 uppercase mb-3">Deals ({pDeals.length})</p>
                    {pDeals.length === 0 && <p className="text-sm text-gray-400">No deals registered for this partner.</p>}
                    <div className="space-y-2">
                      {pDeals.map(deal => (
                        <div key={deal.id} className="flex items-center justify-between bg-white rounded-lg border border-gray-200 px-3 py-2">
                          <div>
                            <span className="text-sm font-medium text-gray-800">{deal.deal_name || "Unnamed deal"}</span>
                            <span className={`ml-2 text-xs px-1.5 py-0.5 rounded font-medium ${DEAL_STAGE_COLORS[deal.stage] || ""}`}>{deal.stage}</span>
                          </div>
                          <div className="flex items-center gap-3">
                            <span className="text-sm text-gray-600">{fmt(deal.deal_value)}</span>
                            <span className="text-xs text-green-700">+{fmt(deal.commission_amount)} commission</span>
                            {deal.stage === "registered" && (
                              <button onClick={() => updateDealStage(deal.id, "approved")}
                                className="text-xs px-2 py-1 rounded bg-green-100 text-green-700 hover:bg-green-200">
                                Approve
                              </button>
                            )}
                            {deal.stage === "approved" && (
                              <button onClick={() => updateDealStage(deal.id, "paid")}
                                className="text-xs px-2 py-1 rounded bg-purple-100 text-purple-700 hover:bg-purple-200">
                                Mark Paid
                              </button>
                            )}
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}

      {/* Programs list */}
      {activeTab === "programs" && (
        <div className="space-y-3">
          {programs.length === 0 && (
            <div className="text-center py-12 text-gray-400">
              <Handshake className="h-8 w-8 mx-auto mb-2 opacity-40" />
              <p>No programs yet. Create a commission program first.</p>
            </div>
          )}
          {programs.map(prog => (
            <div key={prog.id} className="rounded-xl border border-gray-200 bg-white p-4 flex items-center justify-between">
              <div>
                <p className="font-semibold text-gray-900">{prog.name}</p>
                <p className="text-sm text-gray-500">
                  {prog.commission_type === "percentage"
                    ? `${(prog.commission_rate * 100).toFixed(1)}% of deal value`
                    : `${fmt(prog.commission_rate)} ${prog.currency} fixed per deal`}
                </p>
              </div>
              <span className={`text-xs px-2 py-1 rounded-full font-medium ${prog.is_active ? "bg-green-100 text-green-700" : "bg-gray-100 text-gray-500"}`}>
                {prog.is_active ? "Active" : "Inactive"}
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
