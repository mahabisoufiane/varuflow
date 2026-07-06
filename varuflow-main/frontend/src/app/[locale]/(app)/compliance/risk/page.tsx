"use client";

import { useEffect, useState } from "react";
import { useRouter, useParams } from "next/navigation";
import { createClient } from "@/lib/supabase/client";
import { PlusCircle, Shield, RefreshCw, Trash2, ChevronDown, ChevronRight } from "lucide-react";
import { Button } from "@/components/ui/button";
import { toast } from "sonner";
import styles from "./page.module.scss";

interface Risk {
  id: string;
  title: string;
  category: string;
  status: string;
  likelihood: number;
  impact: number;
  risk_score: number;
  description: string | null;
  mitigation_plan: string | null;
  created_at: string;
}

const CATEGORY_COLORS: Record<string, string> = {
  supply_chain: "bg-orange-100 text-orange-700",
  key_person:   "bg-purple-100 text-purple-700",
  currency:     "bg-blue-100 text-blue-700",
  legal:        "bg-red-100 text-red-700",
};

const CATEGORY_MODULE: Record<string, keyof typeof styles> = {
  supply_chain: "categorySupplyChain",
  key_person:   "categoryKeyPerson",
  currency:     "categoryCurrency",
  legal:        "categoryLegal",
};

const STATUS_COLORS: Record<string, string> = {
  identified: "bg-blue-100 text-blue-700",
  monitoring: "bg-yellow-100 text-yellow-700",
  mitigating: "bg-amber-100 text-amber-700",
  resolved:   "bg-green-100 text-green-700",
  accepted:   "bg-gray-100 text-gray-600",
};

const STATUS_MODULE: Record<string, keyof typeof styles> = {
  identified: "statusIdentified",
  monitoring: "statusMonitoring",
  mitigating: "statusMitigating",
  resolved:   "statusResolved",
  accepted:   "statusAccepted",
};

function riskScoreColor(score: number) {
  if (score > 12) return "text-red-600 font-bold";
  if (score > 8)  return "text-orange-600 font-bold";
  if (score > 4)  return "text-amber-600 font-bold";
  return "text-green-600 font-bold";
}

function riskScoreLabel(score: number) {
  if (score > 12) return "Critical";
  if (score > 8)  return "High";
  if (score > 4)  return "Medium";
  return "Low";
}

const LIKELIHOOD_OPTS = [1,2,3,4] as const;
const IMPACT_OPTS     = [1,2,3,4] as const;

export default function RiskRegisterPage() {
  const router = useRouter();
  const params = useParams<{ locale: string }>();
  const locale = params?.locale ?? "en";
  const supabase = createClient();

  const [risks, setRisks] = useState<Risk[]>([]);
  const [loading, setLoading] = useState(true);
  const [statusFilter, setStatusFilter] = useState("all");
  const [expanded, setExpanded] = useState<Set<string>>(new Set());
  const [showNew, setShowNew] = useState(false);
  const [actionLoading, setActionLoading] = useState<string | null>(null);

  const [newForm, setNewForm] = useState({
    title: "", category: "supply_chain", likelihood: "2", impact: "2",
    description: "", mitigation_plan: "",
  });

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
      const res = await fetch(apiUrl("/api/risk"), { headers: { Authorization: `Bearer ${token}` } });
      if (res.status === 401) { router.push(`/${locale}/auth/login`); return; }
      if (res.ok) setRisks(await res.json());
    } catch {
      toast.error("Failed to load risk register");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { load(); }, []);  // eslint-disable-line react-hooks/exhaustive-deps

  async function createRisk() {
    if (!newForm.title.trim()) { toast.error("Title is required"); return; }
    setActionLoading("create");
    try {
      const token = await getToken();
      if (!token) return;
      const res = await fetch(apiUrl("/api/risk"), {
        method: "POST",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
        body: JSON.stringify({
          title: newForm.title,
          category: newForm.category,
          likelihood: parseInt(newForm.likelihood),
          impact: parseInt(newForm.impact),
          description: newForm.description || null,
          mitigation_plan: newForm.mitigation_plan || null,
        }),
      });
      if (!res.ok) {
        const b = await res.json().catch(() => ({}));
        toast.error(b.detail ?? "Failed to create risk");
        return;
      }
      toast.success("Risk added to register");
      setShowNew(false);
      setNewForm({ title: "", category: "supply_chain", likelihood: "2", impact: "2", description: "", mitigation_plan: "" });
      await load();
    } catch {
      toast.error("Something went wrong");
    } finally {
      setActionLoading(null);
    }
  }

  async function deleteRisk(id: string) {
    setActionLoading(id + "_del");
    try {
      const token = await getToken();
      if (!token) return;
      await fetch(apiUrl(`/api/risk/${id}`), {
        method: "DELETE",
        headers: { Authorization: `Bearer ${token}` },
      });
      toast.success("Risk removed");
      await load();
    } catch {
      toast.error("Something went wrong");
    } finally {
      setActionLoading(null);
    }
  }

  function toggle(id: string) {
    setExpanded((prev) => {
      const next = new Set(prev);
      next.has(id) ? next.delete(id) : next.add(id);
      return next;
    });
  }

  const filtered = statusFilter === "all" ? risks : risks.filter((r) => r.status === statusFilter);

  return (
    <div className="mx-auto max-w-4xl space-y-6 p-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-gray-900">Risk Register</h1>
          <p className="text-sm text-muted-foreground mt-0.5">Identify and monitor operational, financial, and strategic risks.</p>
        </div>
        <Button onClick={() => setShowNew(true)} className="bg-[var(--vf-brand-primary)] hover:bg-[var(--vf-brand-primary-hover)] text-white gap-2">
          <PlusCircle className="h-4 w-4" /> Add Risk
        </Button>
      </div>

      {/* Status filter */}
      <div className="flex items-center gap-2 flex-wrap">
        {["all", "identified", "monitoring", "mitigating", "resolved", "accepted"].map((s) => (
          <button key={s} type="button" onClick={() => setStatusFilter(s)}
            className={`rounded-full px-3 py-1 text-xs font-medium capitalize transition-colors ${
              statusFilter === s ? "bg-[var(--vf-brand-primary)] text-white" : "bg-gray-100 text-gray-600 hover:bg-gray-200"
            }`}>
            {s === "all" ? "All" : s}
          </button>
        ))}
      </div>

      {/* New risk form */}
      {showNew && (
        <div className="rounded-xl border border-[var(--vf-brand-primary)]/20 bg-white p-5 shadow-sm space-y-3">
          <h3 className="text-sm font-semibold text-gray-900">New Risk</h3>
          <input value={newForm.title} onChange={(e) => setNewForm((f) => ({ ...f, title: e.target.value }))}
            placeholder="Risk title *"
            className="block w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-[var(--vf-brand-primary)]" />
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            <div className="space-y-1">
              <label className="text-xs font-medium text-gray-700">Category</label>
              <select value={newForm.category} onChange={(e) => setNewForm((f) => ({ ...f, category: e.target.value }))}
                className="block w-full rounded-md border border-gray-300 px-2 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-[var(--vf-brand-primary)]">
                <option value="supply_chain">Supply Chain</option>
                <option value="key_person">Key Person</option>
                <option value="currency">Currency</option>
                <option value="legal">Legal</option>
              </select>
            </div>
            <div className="space-y-1">
              <label className="text-xs font-medium text-gray-700">Likelihood (1-4)</label>
              <select value={newForm.likelihood} onChange={(e) => setNewForm((f) => ({ ...f, likelihood: e.target.value }))}
                className="block w-full rounded-md border border-gray-300 px-2 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-[var(--vf-brand-primary)]">
                {LIKELIHOOD_OPTS.map((v) => <option key={v} value={v}>{v}</option>)}
              </select>
            </div>
            <div className="space-y-1">
              <label className="text-xs font-medium text-gray-700">Impact (1-4)</label>
              <select value={newForm.impact} onChange={(e) => setNewForm((f) => ({ ...f, impact: e.target.value }))}
                className="block w-full rounded-md border border-gray-300 px-2 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-[var(--vf-brand-primary)]">
                {IMPACT_OPTS.map((v) => <option key={v} value={v}>{v}</option>)}
              </select>
            </div>
            <div className="flex items-end">
              <p className="text-xs text-muted-foreground">
                Score: <span className={riskScoreColor(parseInt(newForm.likelihood) * parseInt(newForm.impact))}>
                  {parseInt(newForm.likelihood) * parseInt(newForm.impact)}
                </span>
              </p>
            </div>
          </div>
          <textarea value={newForm.description} onChange={(e) => setNewForm((f) => ({ ...f, description: e.target.value }))}
            placeholder="Description (optional)" rows={2}
            className="block w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-[var(--vf-brand-primary)]" />
          <textarea value={newForm.mitigation_plan} onChange={(e) => setNewForm((f) => ({ ...f, mitigation_plan: e.target.value }))}
            placeholder="Mitigation plan (optional)" rows={2}
            className="block w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-[var(--vf-brand-primary)]" />
          <div className="flex gap-2">
            <Button variant="outline" onClick={() => setShowNew(false)}>Cancel</Button>
            <Button disabled={actionLoading === "create"} onClick={createRisk}
              className="bg-[var(--vf-brand-primary)] hover:bg-[var(--vf-brand-primary-hover)] text-white">
              {actionLoading === "create" ? "Saving…" : "Add Risk"}
            </Button>
          </div>
        </div>
      )}

      {/* Risk list */}
      {loading && risks.length === 0 ? (
        <div className="text-center py-12"><RefreshCw className="h-6 w-6 animate-spin mx-auto text-muted-foreground" /></div>
      ) : filtered.length === 0 ? (
        <div className="rounded-xl border bg-white p-12 text-center shadow-sm">
          <Shield className="h-10 w-10 text-muted-foreground mx-auto mb-3" />
          <p className="text-gray-600 font-medium">No risks found</p>
        </div>
      ) : (
        <div className="rounded-xl border bg-white shadow-sm divide-y divide-gray-100">
          {/* Table header */}
          <div className="hidden sm:grid grid-cols-[1fr_auto_auto_auto_auto_auto_auto] gap-4 px-5 py-2.5 text-xs font-medium text-muted-foreground bg-gray-50 rounded-t-xl">
            <span>Title</span>
            <span>Category</span>
            <span>Status</span>
            <span>Likelihood</span>
            <span>Impact</span>
            <span>Score</span>
            <span />
          </div>

          {filtered.map((risk) => {
            const isExpanded = expanded.has(risk.id);
            return (
              <div key={risk.id}>
                <div className="flex items-center gap-3 px-5 py-3.5 cursor-pointer hover:bg-gray-50 transition-colors"
                  onClick={() => toggle(risk.id)}>
                  <div className="flex-shrink-0">
                    {isExpanded
                      ? <ChevronDown className="h-4 w-4 text-muted-foreground" />
                      : <ChevronRight className="h-4 w-4 text-muted-foreground" />}
                  </div>
                  <p className="flex-1 text-sm font-medium text-gray-900 min-w-0 truncate">{risk.title}</p>
                  <span className={styles[CATEGORY_MODULE[risk.category] ?? "categoryLegal"]}>
                    {risk.category.replace("_", " ")}
                  </span>
                  <span className={styles[STATUS_MODULE[risk.status] ?? "statusAccepted"]}>
                    {risk.status}
                  </span>
                  <span className="text-sm text-gray-700 w-8 text-center flex-shrink-0">{risk.likelihood}</span>
                  <span className="text-sm text-gray-700 w-8 text-center flex-shrink-0">{risk.impact}</span>
                  <span className={`w-16 text-sm text-center flex-shrink-0 ${riskScoreColor(risk.risk_score)}`}>
                    {risk.risk_score} <span className="text-xs font-normal">({riskScoreLabel(risk.risk_score)})</span>
                  </span>
                  <button type="button" onClick={(e) => { e.stopPropagation(); deleteRisk(risk.id); }}
                    disabled={actionLoading === risk.id + "_del"}
                    className="flex-shrink-0 text-muted-foreground hover:text-red-600 transition-colors p-1">
                    <Trash2 className="h-4 w-4" />
                  </button>
                </div>
                {isExpanded && (
                  <div className="border-t bg-gray-50 px-8 py-4 space-y-2">
                    {risk.description && (
                      <div>
                        <p className="text-xs font-semibold text-gray-700 mb-0.5">Description</p>
                        <p className="text-sm text-gray-600">{risk.description}</p>
                      </div>
                    )}
                    {risk.mitigation_plan && (
                      <div>
                        <p className="text-xs font-semibold text-gray-700 mb-0.5">Mitigation Plan</p>
                        <p className="text-sm text-gray-600">{risk.mitigation_plan}</p>
                      </div>
                    )}
                    {!risk.description && !risk.mitigation_plan && (
                      <p className="text-sm text-muted-foreground">No additional details recorded.</p>
                    )}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
