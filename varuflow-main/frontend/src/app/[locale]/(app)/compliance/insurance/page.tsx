"use client";

import { useEffect, useState } from "react";
import { useRouter, useParams } from "next/navigation";
import { createClient } from "@/lib/supabase/client";
import { PlusCircle, Building2, RefreshCw, ChevronDown, ChevronRight, AlertTriangle } from "lucide-react";
import { Button } from "@/components/ui/button";
import { toast } from "sonner";
import styles from "./page.module.scss";

interface Claim {
  id: string;
  claim_date: string;
  description: string | null;
  amount_claimed: number | null;
  status: string;
}

interface Policy {
  id: string;
  policy_name: string;
  insurer: string | null;
  policy_number: string | null;
  type: string | null;
  status: string;
  coverage_amount: number | null;
  currency: string;
  premium_annual: number | null;
  start_date: string | null;
  end_date: string | null;
  renewal_due: string | null;
  claims?: Claim[];
}

interface Renewal {
  id: string;
  policy_name: string;
  renewal_due: string;
}

const STATUS_COLORS: Record<string, string> = {
  active:    "bg-green-100 text-green-700",
  expired:   "bg-red-100 text-red-700",
  cancelled: "bg-gray-100 text-gray-600",
};

const STATUS_MODULE: Record<string, keyof typeof styles> = {
  active:    "statusActive",
  expired:   "statusExpired",
  cancelled: "statusCancelled",
};

function isDueSoon(date: string | null): boolean {
  if (!date) return false;
  const diff = new Date(date).getTime() - Date.now();
  return diff <= 30 * 24 * 60 * 60 * 1000;
}

const EMPTY_POLICY = {
  policy_name: "", insurer: "", policy_number: "", type: "general_liability",
  coverage_amount: "", currency: "SEK", premium_annual: "", start_date: "", end_date: "", renewal_due: "",
};

const EMPTY_CLAIM = { claim_date: "", description: "", amount_claimed: "" };

export default function InsurancePage() {
  const router = useRouter();
  const params = useParams<{ locale: string }>();
  const locale = params?.locale ?? "en";
  const supabase = createClient();

  const [policies, setPolicies] = useState<Policy[]>([]);
  const [renewals, setRenewals] = useState<Renewal[]>([]);
  const [loading, setLoading] = useState(true);
  const [expanded, setExpanded] = useState<Set<string>>(new Set());
  const [claimsMap, setClaimsMap] = useState<Record<string, Claim[]>>({});
  const [showNew, setShowNew] = useState(false);
  const [newForm, setNewForm] = useState(EMPTY_POLICY);
  const [showClaimFor, setShowClaimFor] = useState<string | null>(null);
  const [newClaim, setNewClaim] = useState(EMPTY_CLAIM);
  const [actionLoading, setActionLoading] = useState<string | null>(null);

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
      const [polRes, renRes] = await Promise.all([
        fetch(apiUrl("/api/insurance/policies"), { headers: { Authorization: `Bearer ${token}` } }),
        fetch(apiUrl("/api/insurance/renewals"), { headers: { Authorization: `Bearer ${token}` } }),
      ]);
      if (polRes.status === 401) { router.push(`/${locale}/auth/login`); return; }
      if (polRes.ok) setPolicies(await polRes.json());
      if (renRes.ok) setRenewals(await renRes.json());
    } catch {
      toast.error("Failed to load insurance policies");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { load(); }, []);  // eslint-disable-line react-hooks/exhaustive-deps

  async function loadClaims(policyId: string) {
    try {
      const token = await getToken();
      if (!token) return;
      const res = await fetch(apiUrl(`/api/insurance/policies/${policyId}/claims`), {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (res.ok) {
        const data = await res.json();
        setClaimsMap((prev) => ({ ...prev, [policyId]: data }));
      }
    } catch {
      toast.error("Failed to load claims");
    }
  }

  function toggle(id: string) {
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(id)) {
        next.delete(id);
      } else {
        next.add(id);
        loadClaims(id);
      }
      return next;
    });
  }

  async function createPolicy() {
    if (!newForm.policy_name.trim()) { toast.error("Policy name is required"); return; }
    setActionLoading("create_policy");
    try {
      const token = await getToken();
      if (!token) return;
      const res = await fetch(apiUrl("/api/insurance/policies"), {
        method: "POST",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
        body: JSON.stringify({
          ...newForm,
          coverage_amount: newForm.coverage_amount ? parseFloat(newForm.coverage_amount) : null,
          premium_annual: newForm.premium_annual ? parseFloat(newForm.premium_annual) : null,
          start_date: newForm.start_date || null,
          end_date: newForm.end_date || null,
          renewal_due: newForm.renewal_due || null,
          insurer: newForm.insurer || null,
          policy_number: newForm.policy_number || null,
        }),
      });
      if (!res.ok) {
        const b = await res.json().catch(() => ({}));
        toast.error(b.detail ?? "Failed to create policy");
        return;
      }
      toast.success("Policy created");
      setShowNew(false);
      setNewForm(EMPTY_POLICY);
      await load();
    } catch {
      toast.error("Something went wrong");
    } finally {
      setActionLoading(null);
    }
  }

  async function addClaim(policyId: string) {
    if (!newClaim.claim_date) { toast.error("Claim date is required"); return; }
    setActionLoading("create_claim_" + policyId);
    try {
      const token = await getToken();
      if (!token) return;
      const res = await fetch(apiUrl(`/api/insurance/policies/${policyId}/claims`), {
        method: "POST",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
        body: JSON.stringify({
          claim_date: newClaim.claim_date,
          description: newClaim.description || null,
          amount_claimed: newClaim.amount_claimed ? parseFloat(newClaim.amount_claimed) : null,
        }),
      });
      if (!res.ok) {
        const b = await res.json().catch(() => ({}));
        toast.error(b.detail ?? "Failed to add claim");
        return;
      }
      toast.success("Claim recorded");
      setShowClaimFor(null);
      setNewClaim(EMPTY_CLAIM);
      await loadClaims(policyId);
    } catch {
      toast.error("Something went wrong");
    } finally {
      setActionLoading(null);
    }
  }

  return (
    <div className="mx-auto max-w-4xl space-y-6 p-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-gray-900">Insurance Policies</h1>
          <p className="text-sm text-muted-foreground mt-0.5">Manage policies, track renewals, and log claims.</p>
        </div>
        <Button onClick={() => setShowNew(true)} className="bg-[var(--vf-brand-primary)] hover:bg-[var(--vf-brand-primary-hover)] text-white gap-2">
          <PlusCircle className="h-4 w-4" /> Add Policy
        </Button>
      </div>

      {/* Renewals alert */}
      {renewals.length > 0 && (
        <div className="flex items-center gap-3 rounded-xl border border-amber-200 bg-amber-50 px-4 py-3">
          <AlertTriangle className="h-4 w-4 text-amber-600 flex-shrink-0" />
          <p className="text-sm text-amber-800 font-medium">
            {renewals.length} {renewals.length === 1 ? "policy" : "policies"} due for renewal soon.
          </p>
        </div>
      )}

      {/* New policy form */}
      {showNew && (
        <div className="rounded-xl border border-[var(--vf-brand-primary)]/20 bg-white p-5 shadow-sm space-y-3">
          <h3 className="text-sm font-semibold text-gray-900">New Policy</h3>
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1">
              <label className="text-xs font-medium text-gray-700">Policy Name *</label>
              <input value={newForm.policy_name} onChange={(e) => setNewForm((f) => ({ ...f, policy_name: e.target.value }))}
                placeholder="General Liability 2026"
                className="block w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-[var(--vf-brand-primary)]" />
            </div>
            <div className="space-y-1">
              <label className="text-xs font-medium text-gray-700">Insurer</label>
              <input value={newForm.insurer} onChange={(e) => setNewForm((f) => ({ ...f, insurer: e.target.value }))}
                placeholder="Folksam"
                className="block w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-[var(--vf-brand-primary)]" />
            </div>
            <div className="space-y-1">
              <label className="text-xs font-medium text-gray-700">Policy Number</label>
              <input value={newForm.policy_number} onChange={(e) => setNewForm((f) => ({ ...f, policy_number: e.target.value }))}
                className="block w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-[var(--vf-brand-primary)]" />
            </div>
            <div className="space-y-1">
              <label className="text-xs font-medium text-gray-700">Type</label>
              <select value={newForm.type} onChange={(e) => setNewForm((f) => ({ ...f, type: e.target.value }))}
                className="block w-full rounded-md border border-gray-300 px-2 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-[var(--vf-brand-primary)]">
                <option value="general_liability">General Liability</option>
                <option value="property">Property</option>
                <option value="cyber">Cyber</option>
                <option value="directors_officers">D&amp;O</option>
                <option value="workers_comp">Workers Comp</option>
                <option value="product_liability">Product Liability</option>
                <option value="other">Other</option>
              </select>
            </div>
            <div className="space-y-1">
              <label className="text-xs font-medium text-gray-700">Coverage Amount</label>
              <input type="number" value={newForm.coverage_amount} onChange={(e) => setNewForm((f) => ({ ...f, coverage_amount: e.target.value }))}
                className="block w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-[var(--vf-brand-primary)]" />
            </div>
            <div className="space-y-1">
              <label className="text-xs font-medium text-gray-700">Currency</label>
              <select value={newForm.currency} onChange={(e) => setNewForm((f) => ({ ...f, currency: e.target.value }))}
                className="block w-full rounded-md border border-gray-300 px-2 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-[var(--vf-brand-primary)]">
                <option value="SEK">SEK</option>
                <option value="NOK">NOK</option>
                <option value="DKK">DKK</option>
                <option value="EUR">EUR</option>
              </select>
            </div>
            <div className="space-y-1">
              <label className="text-xs font-medium text-gray-700">Annual Premium</label>
              <input type="number" value={newForm.premium_annual} onChange={(e) => setNewForm((f) => ({ ...f, premium_annual: e.target.value }))}
                className="block w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-[var(--vf-brand-primary)]" />
            </div>
            <div className="space-y-1">
              <label className="text-xs font-medium text-gray-700">Renewal Due</label>
              <input type="date" value={newForm.renewal_due} onChange={(e) => setNewForm((f) => ({ ...f, renewal_due: e.target.value }))}
                className="block w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-[var(--vf-brand-primary)]" />
            </div>
            <div className="space-y-1">
              <label className="text-xs font-medium text-gray-700">Start Date</label>
              <input type="date" value={newForm.start_date} onChange={(e) => setNewForm((f) => ({ ...f, start_date: e.target.value }))}
                className="block w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-[var(--vf-brand-primary)]" />
            </div>
            <div className="space-y-1">
              <label className="text-xs font-medium text-gray-700">End Date</label>
              <input type="date" value={newForm.end_date} onChange={(e) => setNewForm((f) => ({ ...f, end_date: e.target.value }))}
                className="block w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-[var(--vf-brand-primary)]" />
            </div>
          </div>
          <div className="flex gap-2">
            <Button variant="outline" onClick={() => setShowNew(false)}>Cancel</Button>
            <Button disabled={actionLoading === "create_policy"} onClick={createPolicy}
              className="bg-[var(--vf-brand-primary)] hover:bg-[var(--vf-brand-primary-hover)] text-white">
              {actionLoading === "create_policy" ? "Saving…" : "Create Policy"}
            </Button>
          </div>
        </div>
      )}

      {/* Policy list */}
      {loading && policies.length === 0 ? (
        <div className="text-center py-12"><RefreshCw className="h-6 w-6 animate-spin mx-auto text-muted-foreground" /></div>
      ) : policies.length === 0 ? (
        <div className="rounded-xl border bg-white p-12 text-center shadow-sm">
          <Building2 className="h-10 w-10 text-muted-foreground mx-auto mb-3" />
          <p className="text-gray-600 font-medium">No insurance policies yet</p>
        </div>
      ) : (
        <div className="rounded-xl border bg-white shadow-sm divide-y divide-gray-100">
          {policies.map((policy) => {
            const isExpanded = expanded.has(policy.id);
            const renewalDueSoon = isDueSoon(policy.renewal_due);
            return (
              <div key={policy.id}>
                <div className="flex items-center gap-3 px-5 py-4 cursor-pointer hover:bg-gray-50 transition-colors"
                  onClick={() => toggle(policy.id)}>
                  <div className="flex-shrink-0">
                    {isExpanded
                      ? <ChevronDown className="h-4 w-4 text-muted-foreground" />
                      : <ChevronRight className="h-4 w-4 text-muted-foreground" />}
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium text-gray-900 truncate">{policy.policy_name}</p>
                    <p className="text-xs text-muted-foreground mt-0.5">
                      {policy.insurer ?? "Unknown insurer"}
                      {policy.policy_number && ` · ${policy.policy_number}`}
                    </p>
                  </div>
                  {policy.type && (
                    <span className="inline-flex rounded-full px-2.5 py-0.5 text-xs font-medium bg-blue-100 text-blue-700 flex-shrink-0 capitalize">
                      {policy.type.replace(/_/g, " ")}
                    </span>
                  )}
                  <span className={styles[STATUS_MODULE[policy.status] ?? "statusActive"]}>
                    {policy.status}
                  </span>
                  {policy.coverage_amount != null && (
                    <span className="text-sm text-gray-700 flex-shrink-0">
                      {policy.coverage_amount.toLocaleString()} {policy.currency}
                    </span>
                  )}
                  {policy.renewal_due && (
                    <span className={`text-xs flex-shrink-0 ${renewalDueSoon ? "text-red-600 font-semibold" : "text-muted-foreground"}`}>
                      Renew {new Date(policy.renewal_due).toLocaleDateString()}
                      {renewalDueSoon && " ⚠"}
                    </span>
                  )}
                </div>

                {isExpanded && (
                  <div className="border-t bg-gray-50 px-8 py-4 space-y-4">
                    <div className="flex items-center justify-between">
                      <p className="text-xs font-semibold text-gray-700">Claims</p>
                      <Button size="sm" variant="outline" onClick={(e) => { e.stopPropagation(); setShowClaimFor(policy.id); setNewClaim(EMPTY_CLAIM); }}
                        className="gap-1 text-xs h-7">
                        <PlusCircle className="h-3 w-3" /> Add Claim
                      </Button>
                    </div>

                    {showClaimFor === policy.id && (
                      <div className="rounded-lg border bg-white p-4 space-y-2">
                        <div className="grid grid-cols-3 gap-2">
                          <div className="space-y-1">
                            <label className="text-xs font-medium text-gray-700">Claim Date *</label>
                            <input type="date" value={newClaim.claim_date}
                              onChange={(e) => setNewClaim((f) => ({ ...f, claim_date: e.target.value }))}
                              className="block w-full rounded-md border border-gray-300 px-2 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-[var(--vf-brand-primary)]" />
                          </div>
                          <div className="space-y-1 col-span-2">
                            <label className="text-xs font-medium text-gray-700">Description</label>
                            <input value={newClaim.description}
                              onChange={(e) => setNewClaim((f) => ({ ...f, description: e.target.value }))}
                              placeholder="Brief claim description"
                              className="block w-full rounded-md border border-gray-300 px-2 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-[var(--vf-brand-primary)]" />
                          </div>
                          <div className="space-y-1">
                            <label className="text-xs font-medium text-gray-700">Amount Claimed</label>
                            <input type="number" value={newClaim.amount_claimed}
                              onChange={(e) => setNewClaim((f) => ({ ...f, amount_claimed: e.target.value }))}
                              className="block w-full rounded-md border border-gray-300 px-2 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-[var(--vf-brand-primary)]" />
                          </div>
                        </div>
                        <div className="flex gap-2">
                          <Button variant="outline" size="sm" onClick={() => setShowClaimFor(null)}>Cancel</Button>
                          <Button size="sm" disabled={actionLoading === "create_claim_" + policy.id} onClick={() => addClaim(policy.id)}
                            className="bg-[var(--vf-brand-primary)] hover:bg-[var(--vf-brand-primary-hover)] text-white">
                            Save Claim
                          </Button>
                        </div>
                      </div>
                    )}

                    {(claimsMap[policy.id] ?? []).length === 0 ? (
                      <p className="text-sm text-muted-foreground">No claims recorded.</p>
                    ) : (
                      <div className="space-y-2">
                        {(claimsMap[policy.id] ?? []).map((claim) => (
                          <div key={claim.id} className="rounded-lg border bg-white px-4 py-2.5 flex items-center gap-4">
                            <span className="text-xs text-muted-foreground flex-shrink-0">{new Date(claim.claim_date).toLocaleDateString()}</span>
                            <span className="text-sm text-gray-800 flex-1">{claim.description ?? "—"}</span>
                            {claim.amount_claimed != null && (
                              <span className="text-sm font-medium text-gray-700">{claim.amount_claimed.toLocaleString()}</span>
                            )}
                            <span className={styles[STATUS_MODULE[claim.status] ?? "statusActive"]}>
                              {claim.status}
                            </span>
                          </div>
                        ))}
                      </div>
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
