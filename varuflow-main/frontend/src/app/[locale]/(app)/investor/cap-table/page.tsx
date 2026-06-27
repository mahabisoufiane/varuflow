"use client";

import { useEffect, useState } from "react";
import { useRouter, useParams } from "next/navigation";
import { createClient } from "@/lib/supabase/client";
import { PlusCircle, RefreshCw } from "lucide-react";
import { Button } from "@/components/ui/button";
import { toast } from "sonner";
import styles from "./page.module.scss";

interface CapTableSummary {
  total_shareholders: number;
  total_issued_shares: number;
  by_class: { class_name: string; shares: number }[];
  by_shareholder: { name: string; shares: number; ownership_pct: number }[];
}

interface Shareholder {
  id: string;
  name: string;
  shareholder_type: string;
  email: string | null;
  notes: string | null;
}

interface ShareClass {
  id: string;
  name: string;
  authorized_shares: number | null;
  liquidation_priority: number | null;
  has_anti_dilution: boolean;
  has_voting_rights: boolean;
}

interface Scenario {
  id: string;
  title: string;
  new_shares: number;
  pre_money_valuation: number | null;
  currency: string | null;
  notes: string | null;
}

interface ModelResult {
  pre_dilution: { name: string; pct: number }[];
  post_dilution: { name: string; pct: number }[];
}

const TYPE_COLOR: Record<string, string> = {
  founder: "bg-blue-100 text-blue-700",
  investor: "bg-green-100 text-green-700",
  employee: "bg-purple-100 text-purple-700",
  other: "bg-gray-100 text-gray-600",
};

const TYPE_MODULE: Record<string, keyof typeof styles> = {
  founder:  "typeFounder",
  investor: "typeInvestor",
  employee: "typeEmployee",
  other:    "typeOther",
};

export default function CapTablePage() {
  const router = useRouter();
  const params = useParams<{ locale: string }>();
  const locale = params?.locale ?? "en";
  const supabase = createClient();

  const [tab, setTab] = useState<"summary" | "shareholders" | "classes" | "scenarios">("summary");
  const [summary, setSummary] = useState<CapTableSummary | null>(null);
  const [shareholders, setShareholders] = useState<Shareholder[]>([]);
  const [classes, setClasses] = useState<ShareClass[]>([]);
  const [scenarios, setScenarios] = useState<Scenario[]>([]);
  const [loading, setLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState<string | null>(null);
  const [modelModal, setModelModal] = useState<{ id: string; result: ModelResult | null } | null>(null);

  const [shForm, setShForm] = useState({ name: "", shareholder_type: "investor", email: "", notes: "" });
  const [showShForm, setShowShForm] = useState(false);

  const [clForm, setClForm] = useState({ name: "", authorized_shares: "", liquidation_priority: "", has_anti_dilution: false, has_voting_rights: true });
  const [showClForm, setShowClForm] = useState(false);

  const [scForm, setScForm] = useState({ title: "", new_shares: "", pre_money_valuation: "", currency: "SEK", notes: "" });
  const [showScForm, setShowScForm] = useState(false);

  async function getToken() {
    const { data: { session } } = await supabase.auth.getSession();
    return session?.access_token ?? null;
  }
  function apiUrl(p: string) { return `${process.env.NEXT_PUBLIC_API_URL}${p}`; }

  async function load() {
    setLoading(true);
    try {
      const token = await getToken();
      if (!token) { router.push(`/${locale}/auth/login`); return; }
      const headers = { Authorization: `Bearer ${token}` };
      const [sumRes, shRes, clRes, scRes] = await Promise.all([
        fetch(apiUrl("/api/cap-table/summary"), { headers }),
        fetch(apiUrl("/api/cap-table/shareholders"), { headers }),
        fetch(apiUrl("/api/cap-table/classes"), { headers }),
        fetch(apiUrl("/api/cap-table/scenarios"), { headers }),
      ]);
      if (sumRes.status === 401) { router.push(`/${locale}/auth/login`); return; }
      if (sumRes.ok) setSummary(await sumRes.json());
      if (shRes.ok) setShareholders(await shRes.json());
      if (clRes.ok) setClasses(await clRes.json());
      if (scRes.ok) setScenarios(await scRes.json());
    } catch {
      toast.error("Failed to load cap table");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { load(); }, []); // eslint-disable-line react-hooks/exhaustive-deps

  async function createShareholder() {
    if (!shForm.name.trim()) { toast.error("Name is required"); return; }
    setActionLoading("sh_create");
    try {
      const token = await getToken();
      if (!token) return;
      const res = await fetch(apiUrl("/api/cap-table/shareholders"), {
        method: "POST",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
        body: JSON.stringify({ ...shForm, email: shForm.email || null, notes: shForm.notes || null }),
      });
      if (!res.ok) { const b = await res.json().catch(() => ({})); toast.error(b.detail ?? "Failed to create"); return; }
      toast.success("Shareholder added");
      setShowShForm(false);
      setShForm({ name: "", shareholder_type: "investor", email: "", notes: "" });
      await load();
    } catch { toast.error("Something went wrong"); }
    finally { setActionLoading(null); }
  }

  async function createClass() {
    if (!clForm.name.trim()) { toast.error("Name is required"); return; }
    setActionLoading("cl_create");
    try {
      const token = await getToken();
      if (!token) return;
      const res = await fetch(apiUrl("/api/cap-table/classes"), {
        method: "POST",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
        body: JSON.stringify({
          name: clForm.name,
          authorized_shares: clForm.authorized_shares ? parseInt(clForm.authorized_shares) : null,
          liquidation_priority: clForm.liquidation_priority ? parseInt(clForm.liquidation_priority) : null,
          has_anti_dilution: clForm.has_anti_dilution,
          has_voting_rights: clForm.has_voting_rights,
        }),
      });
      if (!res.ok) { const b = await res.json().catch(() => ({})); toast.error(b.detail ?? "Failed to create"); return; }
      toast.success("Share class created");
      setShowClForm(false);
      setClForm({ name: "", authorized_shares: "", liquidation_priority: "", has_anti_dilution: false, has_voting_rights: true });
      await load();
    } catch { toast.error("Something went wrong"); }
    finally { setActionLoading(null); }
  }

  async function createScenario() {
    if (!scForm.title.trim() || !scForm.new_shares) { toast.error("Title and new shares are required"); return; }
    setActionLoading("sc_create");
    try {
      const token = await getToken();
      if (!token) return;
      const res = await fetch(apiUrl("/api/cap-table/scenarios"), {
        method: "POST",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
        body: JSON.stringify({
          title: scForm.title,
          new_shares: parseInt(scForm.new_shares),
          pre_money_valuation: scForm.pre_money_valuation ? parseFloat(scForm.pre_money_valuation) : null,
          currency: scForm.currency || "SEK",
          notes: scForm.notes || null,
        }),
      });
      if (!res.ok) { const b = await res.json().catch(() => ({})); toast.error(b.detail ?? "Failed to create"); return; }
      toast.success("Scenario created");
      setShowScForm(false);
      setScForm({ title: "", new_shares: "", pre_money_valuation: "", currency: "SEK", notes: "" });
      await load();
    } catch { toast.error("Something went wrong"); }
    finally { setActionLoading(null); }
  }

  async function modelScenario(id: string) {
    setActionLoading(id + "_model");
    setModelModal({ id, result: null });
    try {
      const token = await getToken();
      if (!token) return;
      const res = await fetch(apiUrl(`/api/cap-table/scenarios/${id}/model`), { headers: { Authorization: `Bearer ${token}` } });
      if (!res.ok) { const b = await res.json().catch(() => ({})); toast.error(b.detail ?? "Failed to model"); setModelModal(null); return; }
      const data = await res.json();
      setModelModal({ id, result: data });
    } catch { toast.error("Something went wrong"); setModelModal(null); }
    finally { setActionLoading(null); }
  }

  const TABS = [
    { key: "summary" as const, label: "Summary" },
    { key: "shareholders" as const, label: "Shareholders" },
    { key: "classes" as const, label: "Share Classes" },
    { key: "scenarios" as const, label: "Scenarios" },
  ];

  return (
    <div className="mx-auto max-w-4xl space-y-6 p-6">
      <div>
        <h1 className="text-xl font-semibold text-gray-900">Cap Table</h1>
        <p className="text-sm text-muted-foreground mt-0.5">Shareholders, share classes, and dilution scenarios.</p>
      </div>

      <div className="flex items-center gap-1 border-b">
        {TABS.map((t) => (
          <button key={t.key} type="button" onClick={() => setTab(t.key)}
            className={`px-4 py-2.5 text-sm font-medium border-b-2 transition-colors ${tab === t.key ? "border-[#1a2332] text-[#1a2332]" : "border-transparent text-muted-foreground hover:text-gray-700"}`}>
            {t.label}
          </button>
        ))}
      </div>

      {loading && (
        <div className="text-center py-12"><RefreshCw className="h-6 w-6 animate-spin mx-auto text-muted-foreground" /></div>
      )}

      {!loading && tab === "summary" && summary && (
        <div className="space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <div className="rounded-xl border bg-white shadow-sm p-4">
              <p className="text-xs text-muted-foreground">Total Shareholders</p>
              <p className="text-2xl font-semibold text-gray-900">{summary.total_shareholders}</p>
            </div>
            <div className="rounded-xl border bg-white shadow-sm p-4">
              <p className="text-xs text-muted-foreground">Total Issued Shares</p>
              <p className="text-2xl font-semibold text-gray-900">{summary.total_issued_shares?.toLocaleString()}</p>
            </div>
          </div>
          <div className="rounded-xl border bg-white shadow-sm overflow-hidden">
            <table className="w-full text-sm">
              <thead className="bg-gray-50 border-b">
                <tr>
                  <th className="px-4 py-3 text-left font-medium text-gray-700">Shareholder</th>
                  <th className="px-4 py-3 text-right font-medium text-gray-700">Shares</th>
                  <th className="px-4 py-3 text-right font-medium text-gray-700">Ownership %</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {summary.by_shareholder?.map((sh) => (
                  <tr key={sh.name}>
                    <td className="px-4 py-3 text-gray-900">{sh.name}</td>
                    <td className="px-4 py-3 text-right text-gray-600">{sh.shares?.toLocaleString()}</td>
                    <td className="px-4 py-3 text-right text-gray-600">{sh.ownership_pct?.toFixed(1)}%</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {!loading && tab === "shareholders" && (
        <div className="space-y-4">
          <div className="flex justify-end">
            <Button onClick={() => setShowShForm(true)} className="bg-[#1a2332] hover:bg-[#2a3342] text-white gap-2">
              <PlusCircle className="h-4 w-4" /> Add Shareholder
            </Button>
          </div>
          {showShForm && (
            <div className="rounded-xl border border-[#1a2332]/20 bg-white p-5 shadow-sm space-y-3">
              <div className="grid grid-cols-2 gap-3">
                <div className="space-y-1">
                  <label className="text-xs font-medium text-gray-700">Name *</label>
                  <input value={shForm.name} onChange={(e) => setShForm((f) => ({ ...f, name: e.target.value }))}
                    className="block w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-[#1a2332]" />
                </div>
                <div className="space-y-1">
                  <label className="text-xs font-medium text-gray-700">Type</label>
                  <select value={shForm.shareholder_type} onChange={(e) => setShForm((f) => ({ ...f, shareholder_type: e.target.value }))}
                    className="block w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-[#1a2332]">
                    {["founder", "investor", "employee", "other"].map((t) => <option key={t} value={t}>{t}</option>)}
                  </select>
                </div>
                <div className="space-y-1">
                  <label className="text-xs font-medium text-gray-700">Email</label>
                  <input value={shForm.email} onChange={(e) => setShForm((f) => ({ ...f, email: e.target.value }))}
                    className="block w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-[#1a2332]" />
                </div>
                <div className="space-y-1">
                  <label className="text-xs font-medium text-gray-700">Notes</label>
                  <input value={shForm.notes} onChange={(e) => setShForm((f) => ({ ...f, notes: e.target.value }))}
                    className="block w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-[#1a2332]" />
                </div>
              </div>
              <div className="flex gap-2">
                <Button variant="outline" onClick={() => setShowShForm(false)}>Cancel</Button>
                <Button disabled={actionLoading === "sh_create"} onClick={createShareholder}
                  className="bg-[#1a2332] hover:bg-[#2a3342] text-white">
                  {actionLoading === "sh_create" ? "Adding…" : "Add Shareholder"}
                </Button>
              </div>
            </div>
          )}
          <div className="rounded-xl border bg-white shadow-sm divide-y divide-gray-100">
            {shareholders.length === 0 ? (
              <div className="py-12 text-center text-sm text-gray-500">No shareholders yet</div>
            ) : shareholders.map((sh) => (
              <div key={sh.id} className="flex items-center gap-4 px-5 py-3">
                <div className="flex-1">
                  <p className="text-sm font-medium text-gray-900">{sh.name}</p>
                  {sh.email && <p className="text-xs text-muted-foreground">{sh.email}</p>}
                </div>
                <span className={styles[TYPE_MODULE[sh.shareholder_type] ?? "typeOther"]}>
                  {sh.shareholder_type}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      {!loading && tab === "classes" && (
        <div className="space-y-4">
          <div className="flex justify-end">
            <Button onClick={() => setShowClForm(true)} className="bg-[#1a2332] hover:bg-[#2a3342] text-white gap-2">
              <PlusCircle className="h-4 w-4" /> Add Share Class
            </Button>
          </div>
          {showClForm && (
            <div className="rounded-xl border border-[#1a2332]/20 bg-white p-5 shadow-sm space-y-3">
              <div className="grid grid-cols-2 gap-3">
                <div className="space-y-1">
                  <label className="text-xs font-medium text-gray-700">Name *</label>
                  <input value={clForm.name} onChange={(e) => setClForm((f) => ({ ...f, name: e.target.value }))}
                    placeholder="Series A Preferred"
                    className="block w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-[#1a2332]" />
                </div>
                <div className="space-y-1">
                  <label className="text-xs font-medium text-gray-700">Authorized Shares</label>
                  <input type="number" value={clForm.authorized_shares} onChange={(e) => setClForm((f) => ({ ...f, authorized_shares: e.target.value }))}
                    className="block w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-[#1a2332]" />
                </div>
                <div className="space-y-1">
                  <label className="text-xs font-medium text-gray-700">Liquidation Priority</label>
                  <input type="number" value={clForm.liquidation_priority} onChange={(e) => setClForm((f) => ({ ...f, liquidation_priority: e.target.value }))}
                    className="block w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-[#1a2332]" />
                </div>
                <div className="flex items-center gap-4 pt-5">
                  <label className="flex items-center gap-2 text-sm text-gray-700">
                    <input type="checkbox" checked={clForm.has_anti_dilution} onChange={(e) => setClForm((f) => ({ ...f, has_anti_dilution: e.target.checked }))} />
                    Anti-dilution
                  </label>
                  <label className="flex items-center gap-2 text-sm text-gray-700">
                    <input type="checkbox" checked={clForm.has_voting_rights} onChange={(e) => setClForm((f) => ({ ...f, has_voting_rights: e.target.checked }))} />
                    Voting Rights
                  </label>
                </div>
              </div>
              <div className="flex gap-2">
                <Button variant="outline" onClick={() => setShowClForm(false)}>Cancel</Button>
                <Button disabled={actionLoading === "cl_create"} onClick={createClass}
                  className="bg-[#1a2332] hover:bg-[#2a3342] text-white">
                  {actionLoading === "cl_create" ? "Creating…" : "Create Share Class"}
                </Button>
              </div>
            </div>
          )}
          <div className="rounded-xl border bg-white shadow-sm divide-y divide-gray-100">
            {classes.length === 0 ? (
              <div className="py-12 text-center text-sm text-gray-500">No share classes yet</div>
            ) : classes.map((cl) => (
              <div key={cl.id} className="flex items-center gap-4 px-5 py-3">
                <div className="flex-1">
                  <p className="text-sm font-medium text-gray-900">{cl.name}</p>
                  <p className="text-xs text-muted-foreground">
                    {cl.authorized_shares?.toLocaleString() ?? "—"} authorized · Priority {cl.liquidation_priority ?? "—"}
                  </p>
                </div>
                <div className="flex items-center gap-2">
                  {cl.has_anti_dilution && <span className="rounded-full bg-orange-100 text-orange-700 px-2 py-0.5 text-xs">Anti-dilution</span>}
                  {cl.has_voting_rights && <span className="rounded-full bg-blue-100 text-blue-700 px-2 py-0.5 text-xs">Voting</span>}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {!loading && tab === "scenarios" && (
        <div className="space-y-4">
          <div className="flex justify-end">
            <Button onClick={() => setShowScForm(true)} className="bg-[#1a2332] hover:bg-[#2a3342] text-white gap-2">
              <PlusCircle className="h-4 w-4" /> New Scenario
            </Button>
          </div>
          {showScForm && (
            <div className="rounded-xl border border-[#1a2332]/20 bg-white p-5 shadow-sm space-y-3">
              <div className="grid grid-cols-2 gap-3">
                <div className="space-y-1 col-span-2">
                  <label className="text-xs font-medium text-gray-700">Title *</label>
                  <input value={scForm.title} onChange={(e) => setScForm((f) => ({ ...f, title: e.target.value }))}
                    placeholder="Series B Round"
                    className="block w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-[#1a2332]" />
                </div>
                <div className="space-y-1">
                  <label className="text-xs font-medium text-gray-700">New Shares *</label>
                  <input type="number" value={scForm.new_shares} onChange={(e) => setScForm((f) => ({ ...f, new_shares: e.target.value }))}
                    className="block w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-[#1a2332]" />
                </div>
                <div className="space-y-1">
                  <label className="text-xs font-medium text-gray-700">Pre-money Valuation</label>
                  <input type="number" value={scForm.pre_money_valuation} onChange={(e) => setScForm((f) => ({ ...f, pre_money_valuation: e.target.value }))}
                    className="block w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-[#1a2332]" />
                </div>
                <div className="space-y-1">
                  <label className="text-xs font-medium text-gray-700">Currency</label>
                  <input value={scForm.currency} onChange={(e) => setScForm((f) => ({ ...f, currency: e.target.value }))}
                    className="block w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-[#1a2332]" />
                </div>
                <div className="space-y-1">
                  <label className="text-xs font-medium text-gray-700">Notes</label>
                  <input value={scForm.notes} onChange={(e) => setScForm((f) => ({ ...f, notes: e.target.value }))}
                    className="block w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-[#1a2332]" />
                </div>
              </div>
              <div className="flex gap-2">
                <Button variant="outline" onClick={() => setShowScForm(false)}>Cancel</Button>
                <Button disabled={actionLoading === "sc_create"} onClick={createScenario}
                  className="bg-[#1a2332] hover:bg-[#2a3342] text-white">
                  {actionLoading === "sc_create" ? "Creating…" : "Create Scenario"}
                </Button>
              </div>
            </div>
          )}
          <div className="rounded-xl border bg-white shadow-sm divide-y divide-gray-100">
            {scenarios.length === 0 ? (
              <div className="py-12 text-center text-sm text-gray-500">No scenarios yet</div>
            ) : scenarios.map((sc) => (
              <div key={sc.id} className="flex items-center gap-4 px-5 py-3">
                <div className="flex-1">
                  <p className="text-sm font-medium text-gray-900">{sc.title}</p>
                  <p className="text-xs text-muted-foreground">
                    {sc.new_shares?.toLocaleString()} new shares
                    {sc.pre_money_valuation != null && ` · Pre-money: ${sc.pre_money_valuation?.toLocaleString()} ${sc.currency}`}
                  </p>
                </div>
                <Button size="sm" variant="outline" disabled={actionLoading === sc.id + "_model"}
                  onClick={() => modelScenario(sc.id)}>
                  {actionLoading === sc.id + "_model" ? <RefreshCw className="h-3 w-3 animate-spin" /> : "Model"}
                </Button>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Model modal */}
      {modelModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
          <div className="w-full max-w-lg rounded-xl bg-white p-6 shadow-xl space-y-4 max-h-[80vh] overflow-y-auto">
            <h3 className="text-base font-semibold text-gray-900">Dilution Model</h3>
            {!modelModal.result ? (
              <div className="text-center py-8"><RefreshCw className="h-6 w-6 animate-spin mx-auto text-muted-foreground" /></div>
            ) : (
              <div className="grid grid-cols-2 gap-6">
                {[
                  { label: "Pre-Dilution", data: modelModal.result.pre_dilution },
                  { label: "Post-Dilution", data: modelModal.result.post_dilution },
                ].map(({ label, data }) => (
                  <div key={label}>
                    <p className="text-xs font-semibold text-gray-700 mb-2">{label}</p>
                    <table className="w-full text-xs">
                      <thead>
                        <tr className="border-b">
                          <th className="text-left pb-1 text-gray-600">Shareholder</th>
                          <th className="text-right pb-1 text-gray-600">%</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-gray-100">
                        {data?.map((row) => (
                          <tr key={row.name}>
                            <td className="py-1 text-gray-900">{row.name}</td>
                            <td className="py-1 text-right text-gray-600">{row.pct?.toFixed(1)}%</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                ))}
              </div>
            )}
            <div className="flex justify-end">
              <Button variant="outline" onClick={() => setModelModal(null)}>Close</Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
