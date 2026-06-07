"use client";
import { useEffect, useState } from "react";
import { api } from "@/lib/api-client";
import { toast } from "sonner";
import { RefreshCw, Plus, Pause, Play, XCircle, TrendingUp, Users, DollarSign, ArrowDownCircle, ChevronRight, Trash2 } from "lucide-react";
import styles from "./page.module.scss";

interface Plan {
  id: string;
  name: string;
  description: string | null;
  price: number;
  currency: string;
  interval: string;
  interval_count: number;
  trial_days: number;
  is_active: boolean;
  stripe_price_id: string | null;
}

interface Subscription {
  id: string;
  plan_id: string;
  customer_id: string;
  status: string;
  trial_end: string | null;
  current_period_start: string | null;
  current_period_end: string | null;
  cancel_at: string | null;
  cancelled_at: string | null;
  paused_at: string | null;
  created_at: string;
}

interface Analytics {
  mrr: number;
  churn_rate: number;
  new_count: number;
  active_count: number;
}

const STATUS_COLOR: Record<string, string> = {
  active:    "bg-green-100 text-green-700",
  trialing:  "bg-blue-100 text-blue-700",
  paused:    "bg-yellow-100 text-yellow-700",
  past_due:  "bg-red-100 text-red-700",
  cancelled: "bg-gray-100 text-gray-500",
};

const STATUS_MODULE: Record<string, keyof typeof styles> = {
  active:    "statusActive",
  trialing:  "statusTrialing",
  paused:    "statusPaused",
  past_due:  "statusPastDue",
  cancelled: "statusCancelled",
};

const INTERVAL_LABEL: Record<string, string> = {
  weekly: "/ week", monthly: "/ month", annual: "/ year",
};

export default function MerchantSubscriptionsPage() {
  const [plans, setPlans] = useState<Plan[]>([]);
  const [subs, setSubs] = useState<Subscription[]>([]);
  const [analytics, setAnalytics] = useState<Analytics | null>(null);
  const [tab, setTab] = useState<"plans" | "subscriptions" | "analytics">("plans");
  const [showCreatePlan, setShowCreatePlan] = useState(false);
  const [showCreateSub, setShowCreateSub] = useState(false);
  const [filterStatus, setFilterStatus] = useState("");
  const [loading, setLoading] = useState(true);

  // Plan form
  const [planForm, setPlanForm] = useState({
    name: "", description: "", price: "", currency: "SEK",
    interval: "monthly", interval_count: 1, trial_days: 0,
  });
  // Sub form
  const [subForm, setSubForm] = useState({ plan_id: "", customer_id: "" });

  useEffect(() => { loadPlans(); loadAnalytics(); }, []);
  useEffect(() => { if (tab === "subscriptions") loadSubs(); }, [tab, filterStatus]);

  async function loadPlans() {
    setLoading(true);
    try {
      const data = await api.get("/api/merchant-subscriptions/plans");
      setPlans(Array.isArray(data) ? data : []);
    } catch { toast.error("Failed to load plans"); }
    finally { setLoading(false); }
  }

  async function loadSubs() {
    setLoading(true);
    try {
      const params = new URLSearchParams();
      if (filterStatus) params.set("status", filterStatus);
      params.set("limit", "100");
      const data = await api.get(`/api/merchant-subscriptions?${params.toString()}`);
      setSubs(Array.isArray(data) ? data : []);
    } catch { toast.error("Failed to load subscriptions"); }
    finally { setLoading(false); }
  }

  async function loadAnalytics() {
    try {
      const data = await api.get("/api/merchant-subscriptions/analytics");
      setAnalytics(data);
    } catch {}
  }

  async function createPlan() {
    if (!planForm.name || !planForm.price) { toast.error("Name and price are required"); return; }
    try {
      const p = await api.post("/api/merchant-subscriptions/plans", {
        name: planForm.name,
        description: planForm.description || null,
        price: parseFloat(planForm.price),
        currency: planForm.currency,
        interval: planForm.interval,
        interval_count: planForm.interval_count,
        trial_days: planForm.trial_days,
      });
      setPlans(prev => [...prev, p]);
      setShowCreatePlan(false);
      setPlanForm({ name: "", description: "", price: "", currency: "SEK", interval: "monthly", interval_count: 1, trial_days: 0 });
      toast.success("Plan created");
    } catch { toast.error("Failed to create plan"); }
  }

  async function deactivatePlan(id: string) {
    if (!confirm("Deactivate this plan? Existing subscriptions will continue.")) return;
    try {
      await api.delete(`/api/merchant-subscriptions/plans/${id}`);
      setPlans(prev => prev.map(p => p.id === id ? { ...p, is_active: false } : p));
      toast.success("Plan deactivated");
    } catch { toast.error("Failed"); }
  }

  async function createSub() {
    if (!subForm.plan_id || !subForm.customer_id) { toast.error("Plan and customer are required"); return; }
    try {
      const s = await api.post("/api/merchant-subscriptions", subForm);
      setSubs(prev => [s, ...prev]);
      setShowCreateSub(false);
      setSubForm({ plan_id: "", customer_id: "" });
      toast.success("Subscription created");
    } catch { toast.error("Failed to create subscription"); }
  }

  async function pauseSub(id: string) {
    try {
      const s = await api.post(`/api/merchant-subscriptions/${id}/pause`, {});
      setSubs(prev => prev.map(x => x.id === id ? s : x));
      toast.success("Subscription paused");
    } catch { toast.error("Failed"); }
  }

  async function resumeSub(id: string) {
    try {
      const s = await api.post(`/api/merchant-subscriptions/${id}/resume`, {});
      setSubs(prev => prev.map(x => x.id === id ? s : x));
      toast.success("Subscription resumed");
    } catch { toast.error("Failed"); }
  }

  async function cancelSub(id: string) {
    const notice = window.prompt("Notice period in days?", "30");
    if (!notice) return;
    try {
      const s = await api.post(`/api/merchant-subscriptions/${id}/cancel`, { notice_period_days: parseInt(notice) });
      setSubs(prev => prev.map(x => x.id === id ? s : x));
      toast.success(`Cancellation scheduled in ${notice} days`);
    } catch { toast.error("Failed"); }
  }

  const planMap = Object.fromEntries(plans.map(p => [p.id, p]));

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold flex items-center gap-2"><RefreshCw size={22} /> Subscription Billing</h1>
          <p className="text-sm text-gray-500 mt-0.5">Recurring billing plans and customer subscriptions</p>
        </div>
        <div className="flex gap-2">
          <button onClick={() => { setShowCreatePlan(true); setTab("plans"); }} className="btn-secondary flex items-center gap-2">
            <Plus size={16} /> New plan
          </button>
          <button onClick={() => { setShowCreateSub(true); setTab("subscriptions"); }} className="btn-primary flex items-center gap-2">
            <Plus size={16} /> New subscription
          </button>
        </div>
      </div>

      {/* Analytics cards */}
      {analytics && (
        <div className="grid grid-cols-4 gap-4">
          {[
            { label: "MRR", value: analytics.mrr.toLocaleString("sv-SE", { minimumFractionDigits: 2 }), icon: <DollarSign size={18} />, color: "text-green-600" },
            { label: "Active subscriptions", value: analytics.active_count, icon: <Users size={18} />, color: "text-blue-600" },
            { label: "New this month", value: analytics.new_count, icon: <TrendingUp size={18} />, color: "text-purple-600" },
            { label: "Churn rate", value: `${(analytics.churn_rate * 100).toFixed(1)}%`, icon: <ArrowDownCircle size={18} />, color: analytics.churn_rate > 0.05 ? "text-red-600" : "text-gray-600" },
          ].map(c => (
            <div key={c.label} className="bg-white border rounded-lg p-4">
              <div className={`${c.color} mb-1`}>{c.icon}</div>
              <p className="text-lg font-bold">{c.value}</p>
              <p className="text-xs text-gray-500">{c.label}</p>
            </div>
          ))}
        </div>
      )}

      {/* Tabs */}
      <div className="flex gap-1 border-b">
        {(["plans", "subscriptions", "analytics"] as const).map(t => (
          <button key={t} onClick={() => setTab(t)}
            className={`px-4 py-2 text-sm font-medium capitalize ${tab === t ? "border-b-2 border-[#1a2332] text-[#1a2332]" : "text-gray-500"}`}>
            {t.charAt(0).toUpperCase() + t.slice(1)}
          </button>
        ))}
      </div>

      {/* ── Plans tab ─────────────────────────────────────────────── */}
      {tab === "plans" && (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {plans.length === 0 && !loading && (
            <div className="col-span-3 p-8 text-center bg-white border rounded-lg text-gray-400">
              <RefreshCw size={32} className="mx-auto mb-2 opacity-30" />
              <p className="text-sm">No plans yet. Create one to start billing customers.</p>
            </div>
          )}
          {plans.map(p => (
            <div key={p.id} className={`bg-white border-2 rounded-xl p-5 ${p.is_active ? "border-[#1a2332]" : "border-gray-200 opacity-60"}`}>
              <div className="flex items-start justify-between">
                <div>
                  <h3 className="font-semibold">{p.name}</h3>
                  {p.description && <p className="text-xs text-gray-500 mt-0.5">{p.description}</p>}
                </div>
                {!p.is_active && <span className="text-xs bg-gray-100 text-gray-500 px-2 py-0.5 rounded">Inactive</span>}
              </div>
              <div className="mt-4">
                <span className="text-2xl font-bold">{p.currency} {p.price.toLocaleString("sv-SE", { minimumFractionDigits: 2 })}</span>
                <span className="text-sm text-gray-500 ml-1">{INTERVAL_LABEL[p.interval] ?? `/${p.interval}`}</span>
              </div>
              {p.trial_days > 0 && (
                <p className="text-xs text-blue-600 mt-1">{p.trial_days}-day free trial</p>
              )}
              {p.stripe_price_id && (
                <p className="text-xs text-gray-400 mt-1">Stripe: {p.stripe_price_id}</p>
              )}
              {p.is_active && (
                <button onClick={() => deactivatePlan(p.id)}
                  className="mt-3 text-xs text-red-500 hover:text-red-700">Deactivate</button>
              )}
            </div>
          ))}
        </div>
      )}

      {/* ── Subscriptions tab ─────────────────────────────────────── */}
      {tab === "subscriptions" && (
        <div className="space-y-3">
          <div className="flex gap-2 items-center">
            <select value={filterStatus} onChange={e => setFilterStatus(e.target.value)} className="input text-sm">
              <option value="">All statuses</option>
              {["active", "trialing", "paused", "past_due", "cancelled"].map(s => (
                <option key={s} value={s}>{s.charAt(0).toUpperCase() + s.slice(1)}</option>
              ))}
            </select>
          </div>
          <div className="bg-white border rounded-lg overflow-hidden">
            {subs.length === 0 ? (
              <p className="p-6 text-center text-sm text-gray-400">No subscriptions found.</p>
            ) : (
              <table className="w-full text-xs">
                <thead className="bg-gray-50 border-b">
                  <tr>
                    {["Customer", "Plan", "Status", "Period end", "Cancel at", "Actions"].map(h => (
                      <th key={h} className="px-3 py-2 text-left font-semibold text-gray-500">{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {subs.map(s => {
                    const plan = planMap[s.plan_id];
                    return (
                      <tr key={s.id} className="border-b hover:bg-gray-50">
                        <td className="px-3 py-2 font-mono text-gray-500">{s.customer_id.slice(0, 8)}…</td>
                        <td className="px-3 py-2 font-medium">{plan?.name ?? "Unknown"}</td>
                        <td className="px-3 py-2">
                          <span className={styles[STATUS_MODULE[s.status] ?? "statusActive"]}>
                            {s.status.replace("_", " ")}
                          </span>
                        </td>
                        <td className="px-3 py-2 text-gray-500">
                          {s.current_period_end ? new Date(s.current_period_end).toLocaleDateString() : "—"}
                        </td>
                        <td className="px-3 py-2 text-gray-500">
                          {s.cancel_at ? new Date(s.cancel_at).toLocaleDateString() : "—"}
                        </td>
                        <td className="px-3 py-2">
                          <div className="flex items-center gap-1">
                            {s.status === "active" && (
                              <button onClick={() => pauseSub(s.id)} title="Pause" className="p-1 rounded hover:bg-yellow-100 text-yellow-600"><Pause size={13} /></button>
                            )}
                            {s.status === "paused" && (
                              <button onClick={() => resumeSub(s.id)} title="Resume" className="p-1 rounded hover:bg-green-100 text-green-600"><Play size={13} /></button>
                            )}
                            {s.status !== "cancelled" && (
                              <button onClick={() => cancelSub(s.id)} title="Cancel" className="p-1 rounded hover:bg-red-100 text-red-600"><XCircle size={13} /></button>
                            )}
                          </div>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            )}
          </div>
        </div>
      )}

      {/* ── Analytics tab ─────────────────────────────────────────── */}
      {tab === "analytics" && analytics && (
        <div className="grid grid-cols-2 gap-6">
          <div className="bg-white border rounded-xl p-6 space-y-4">
            <h3 className="font-semibold text-sm">Revenue Metrics</h3>
            <div className="space-y-3">
              <div className="flex justify-between">
                <span className="text-sm text-gray-500">Monthly Recurring Revenue</span>
                <span className="font-bold">SEK {analytics.mrr.toLocaleString("sv-SE", { minimumFractionDigits: 2 })}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-sm text-gray-500">Annual Run Rate</span>
                <span className="font-medium">SEK {(analytics.mrr * 12).toLocaleString("sv-SE", { minimumFractionDigits: 0 })}</span>
              </div>
            </div>
          </div>
          <div className="bg-white border rounded-xl p-6 space-y-4">
            <h3 className="font-semibold text-sm">Subscriber Metrics</h3>
            <div className="space-y-3">
              <div className="flex justify-between">
                <span className="text-sm text-gray-500">Active subscribers</span>
                <span className="font-bold">{analytics.active_count}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-sm text-gray-500">New this month</span>
                <span className="font-medium text-green-600 ">+{analytics.new_count}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-sm text-gray-500">Churn rate (30d)</span>
                <span className={`font-medium ${analytics.churn_rate > 0.05 ? "text-red-600" : "text-gray-700"}`}>
                  {(analytics.churn_rate * 100).toFixed(1)}%
                </span>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* ── Create Plan Modal ────────────────────────────────────── */}
      {showCreatePlan && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50">
          <div className="bg-white rounded-xl shadow-xl w-full max-w-md p-6 space-y-3">
            <h3 className="font-semibold">New Subscription Plan</h3>
            <div>
              <label className="block text-xs font-medium mb-1">Name</label>
              <input value={planForm.name} onChange={e => setPlanForm(f => ({ ...f, name: e.target.value }))} className="input w-full" />
            </div>
            <div>
              <label className="block text-xs font-medium mb-1">Description</label>
              <input value={planForm.description} onChange={e => setPlanForm(f => ({ ...f, description: e.target.value }))} className="input w-full" />
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-xs font-medium mb-1">Price</label>
                <input value={planForm.price} onChange={e => setPlanForm(f => ({ ...f, price: e.target.value }))}
                  type="number" min="0" step="0.01" className="input w-full" placeholder="0.00" />
              </div>
              <div>
                <label className="block text-xs font-medium mb-1">Currency</label>
                <select value={planForm.currency} onChange={e => setPlanForm(f => ({ ...f, currency: e.target.value }))} className="input w-full">
                  {["SEK", "NOK", "DKK", "EUR", "USD", "SAR", "AED"].map(c => <option key={c}>{c}</option>)}
                </select>
              </div>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-xs font-medium mb-1">Billing interval</label>
                <select value={planForm.interval} onChange={e => setPlanForm(f => ({ ...f, interval: e.target.value }))} className="input w-full">
                  <option value="weekly">Weekly</option>
                  <option value="monthly">Monthly</option>
                  <option value="annual">Annual</option>
                </select>
              </div>
              <div>
                <label className="block text-xs font-medium mb-1">Trial days</label>
                <input value={planForm.trial_days} onChange={e => setPlanForm(f => ({ ...f, trial_days: parseInt(e.target.value) || 0 }))}
                  type="number" min="0" className="input w-full" />
              </div>
            </div>
            <div className="flex gap-2 justify-end">
              <button onClick={() => setShowCreatePlan(false)} className="btn-secondary">Cancel</button>
              <button onClick={createPlan} className="btn-primary">Create plan</button>
            </div>
          </div>
        </div>
      )}

      {/* ── Create Subscription Modal ────────────────────────────── */}
      {showCreateSub && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50">
          <div className="bg-white rounded-xl shadow-xl w-full max-w-md p-6 space-y-3">
            <h3 className="font-semibold">New Subscription</h3>
            <div>
              <label className="block text-xs font-medium mb-1">Plan</label>
              <select value={subForm.plan_id} onChange={e => setSubForm(f => ({ ...f, plan_id: e.target.value }))} className="input w-full">
                <option value="">Select a plan…</option>
                {plans.filter(p => p.is_active).map(p => (
                  <option key={p.id} value={p.id}>{p.name} — {p.currency} {p.price}/{p.interval}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-xs font-medium mb-1">Customer ID</label>
              <input value={subForm.customer_id} onChange={e => setSubForm(f => ({ ...f, customer_id: e.target.value }))}
                className="input w-full" placeholder="Paste customer UUID" />
            </div>
            <div className="flex gap-2 justify-end">
              <button onClick={() => setShowCreateSub(false)} className="btn-secondary">Cancel</button>
              <button onClick={createSub} className="btn-primary">Create subscription</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
