"use client";

import { useEffect, useState } from "react";
import { useRouter, useParams } from "next/navigation";
import { createClient } from "@/lib/supabase/client";
import { PlusCircle, Users, RefreshCw, ChevronDown, ChevronRight, CheckCircle2, XCircle } from "lucide-react";
import { Button } from "@/components/ui/button";
import { toast } from "sonner";
import styles from "./page.module.scss";

interface Declaration {
  id: string;
  user_id: string;
  declaration_type: string;
  counterparty_name: string;
  counterparty_type: string | null;
  relationship_description: string | null;
  declared_value: number | null;
  currency: string | null;
  status: string;
  review_notes: string | null;
  created_at: string;
}

const STATUS_COLORS: Record<string, string> = {
  pending:  "bg-amber-100 text-amber-700",
  approved: "bg-green-100 text-green-700",
  rejected: "bg-red-100 text-red-700",
};

const STATUS_MODULE: Record<string, keyof typeof styles> = {
  pending:  "statusPending",
  approved: "statusApproved",
  rejected: "statusRejected",
};

const TYPE_COLORS: Record<string, string> = {
  financial_interest: "bg-blue-100 text-blue-700",
  family_relationship: "bg-purple-100 text-purple-700",
  outside_employment: "bg-orange-100 text-orange-700",
  gift_hospitality: "bg-pink-100 text-pink-700",
  other: "bg-gray-100 text-gray-600",
};

const TYPE_MODULE: Record<string, keyof typeof styles> = {
  financial_interest:  "typeFinancialInterest",
  family_relationship: "typeFamilyRelationship",
  outside_employment:  "typeOutsideEmployment",
  gift_hospitality:    "typeGiftHospitality",
  other:               "typeOther",
};

const EMPTY_FORM = {
  declaration_type: "financial_interest", counterparty_name: "", counterparty_type: "",
  relationship_description: "", declared_value: "", currency: "SEK",
};

export default function ConflictsPage() {
  const router = useRouter();
  const params = useParams<{ locale: string }>();
  const locale = params?.locale ?? "en";
  const supabase = createClient();

  const [declarations, setDeclarations] = useState<Declaration[]>([]);
  const [loading, setLoading] = useState(true);
  const [expanded, setExpanded] = useState<Set<string>>(new Set());
  const [showNew, setShowNew] = useState(false);
  const [newForm, setNewForm] = useState(EMPTY_FORM);
  const [reviewNotes, setReviewNotes] = useState<Record<string, string>>({});
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
      const res = await fetch(apiUrl("/api/conflicts"), { headers: { Authorization: `Bearer ${token}` } });
      if (res.status === 401) { router.push(`/${locale}/auth/login`); return; }
      if (res.ok) setDeclarations(await res.json());
    } catch {
      toast.error("Failed to load conflict declarations");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { load(); }, []);  // eslint-disable-line react-hooks/exhaustive-deps

  async function createDeclaration() {
    if (!newForm.counterparty_name.trim()) { toast.error("Counterparty name is required"); return; }
    setActionLoading("create");
    try {
      const token = await getToken();
      if (!token) return;
      const res = await fetch(apiUrl("/api/conflicts"), {
        method: "POST",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
        body: JSON.stringify({
          declaration_type: newForm.declaration_type,
          counterparty_name: newForm.counterparty_name,
          counterparty_type: newForm.counterparty_type || null,
          relationship_description: newForm.relationship_description || null,
          declared_value: newForm.declared_value ? parseFloat(newForm.declared_value) : null,
          currency: newForm.currency || null,
        }),
      });
      if (!res.ok) {
        const b = await res.json().catch(() => ({}));
        toast.error(b.detail ?? "Failed to submit declaration");
        return;
      }
      toast.success("Declaration submitted");
      setShowNew(false);
      setNewForm(EMPTY_FORM);
      await load();
    } catch {
      toast.error("Something went wrong");
    } finally {
      setActionLoading(null);
    }
  }

  async function reviewDeclaration(id: string, verdict: "approved" | "rejected") {
    setActionLoading(id + "_" + verdict);
    try {
      const token = await getToken();
      if (!token) return;
      const res = await fetch(apiUrl(`/api/conflicts/${id}`), {
        method: "PATCH",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
        body: JSON.stringify({ status: verdict, review_notes: reviewNotes[id] || null }),
      });
      if (!res.ok) {
        const b = await res.json().catch(() => ({}));
        toast.error(b.detail ?? "Failed to update declaration");
        return;
      }
      toast.success(`Declaration ${verdict}`);
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

  return (
    <div className="mx-auto max-w-4xl space-y-6 p-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-gray-900">Conflict of Interest Register</h1>
          <p className="text-sm text-muted-foreground mt-0.5">Declare and review potential conflicts of interest.</p>
        </div>
        <Button onClick={() => setShowNew(true)} className="bg-[#1a2332] hover:bg-[#2a3342] text-white gap-2">
          <PlusCircle className="h-4 w-4" /> Declare Conflict
        </Button>
      </div>

      {/* New declaration form */}
      {showNew && (
        <div className="rounded-xl border border-[#1a2332]/20 bg-white p-5 shadow-sm space-y-3">
          <h3 className="text-sm font-semibold text-gray-900">New Declaration</h3>
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1">
              <label className="text-xs font-medium text-gray-700">Declaration Type</label>
              <select value={newForm.declaration_type} onChange={(e) => setNewForm((f) => ({ ...f, declaration_type: e.target.value }))}
                className="block w-full rounded-md border border-gray-300 px-2 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-[#1a2332]">
                <option value="financial_interest">Financial Interest</option>
                <option value="family_relationship">Family Relationship</option>
                <option value="outside_employment">Outside Employment</option>
                <option value="gift_hospitality">Gift / Hospitality</option>
                <option value="other">Other</option>
              </select>
            </div>
            <div className="space-y-1">
              <label className="text-xs font-medium text-gray-700">Counterparty Name *</label>
              <input value={newForm.counterparty_name} onChange={(e) => setNewForm((f) => ({ ...f, counterparty_name: e.target.value }))}
                placeholder="Company or person name"
                className="block w-full rounded-md border border-gray-300 px-3 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-[#1a2332]" />
            </div>
            <div className="space-y-1">
              <label className="text-xs font-medium text-gray-700">Counterparty Type</label>
              <input value={newForm.counterparty_type} onChange={(e) => setNewForm((f) => ({ ...f, counterparty_type: e.target.value }))}
                placeholder="Supplier, Customer, Competitor…"
                className="block w-full rounded-md border border-gray-300 px-3 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-[#1a2332]" />
            </div>
            <div className="grid grid-cols-2 gap-2">
              <div className="space-y-1">
                <label className="text-xs font-medium text-gray-700">Declared Value</label>
                <input type="number" value={newForm.declared_value} onChange={(e) => setNewForm((f) => ({ ...f, declared_value: e.target.value }))}
                  className="block w-full rounded-md border border-gray-300 px-3 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-[#1a2332]" />
              </div>
              <div className="space-y-1">
                <label className="text-xs font-medium text-gray-700">Currency</label>
                <select value={newForm.currency} onChange={(e) => setNewForm((f) => ({ ...f, currency: e.target.value }))}
                  className="block w-full rounded-md border border-gray-300 px-2 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-[#1a2332]">
                  <option value="SEK">SEK</option>
                  <option value="NOK">NOK</option>
                  <option value="DKK">DKK</option>
                  <option value="EUR">EUR</option>
                </select>
              </div>
            </div>
          </div>
          <div className="space-y-1">
            <label className="text-xs font-medium text-gray-700">Relationship Description</label>
            <textarea value={newForm.relationship_description} onChange={(e) => setNewForm((f) => ({ ...f, relationship_description: e.target.value }))}
              rows={3} placeholder="Describe the nature of the relationship or conflict…"
              className="block w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-[#1a2332]" />
          </div>
          <div className="flex gap-2">
            <Button variant="outline" onClick={() => setShowNew(false)}>Cancel</Button>
            <Button disabled={actionLoading === "create"} onClick={createDeclaration}
              className="bg-[#1a2332] hover:bg-[#2a3342] text-white">
              {actionLoading === "create" ? "Submitting…" : "Submit Declaration"}
            </Button>
          </div>
        </div>
      )}

      {/* Declarations list */}
      {loading && declarations.length === 0 ? (
        <div className="text-center py-12"><RefreshCw className="h-6 w-6 animate-spin mx-auto text-muted-foreground" /></div>
      ) : declarations.length === 0 ? (
        <div className="rounded-xl border bg-white p-12 text-center shadow-sm">
          <Users className="h-10 w-10 text-muted-foreground mx-auto mb-3" />
          <p className="text-gray-600 font-medium">No declarations yet</p>
        </div>
      ) : (
        <div className="rounded-xl border bg-white shadow-sm divide-y divide-gray-100">
          {declarations.map((dec) => {
            const isExpanded = expanded.has(dec.id);
            return (
              <div key={dec.id}>
                <div className="flex items-center gap-3 px-5 py-4 cursor-pointer hover:bg-gray-50 transition-colors"
                  onClick={() => toggle(dec.id)}>
                  <div className="flex-shrink-0">
                    {isExpanded
                      ? <ChevronDown className="h-4 w-4 text-muted-foreground" />
                      : <ChevronRight className="h-4 w-4 text-muted-foreground" />}
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium text-gray-900 truncate">{dec.counterparty_name}</p>
                    <p className="text-xs text-muted-foreground mt-0.5">
                      Declared by {dec.user_id.slice(0, 8)}…
                      {dec.counterparty_type && ` · ${dec.counterparty_type}`}
                      {dec.declared_value != null && ` · ${dec.declared_value.toLocaleString()} ${dec.currency ?? ""}`}
                    </p>
                  </div>
                  <span className={styles[TYPE_MODULE[dec.declaration_type] ?? "typeOther"]}>
                    {dec.declaration_type.replace(/_/g, " ")}
                  </span>
                  <span className={styles[STATUS_MODULE[dec.status] ?? "statusPending"]}>
                    {dec.status}
                  </span>
                </div>

                {isExpanded && (
                  <div className="border-t bg-gray-50 px-8 py-4 space-y-3">
                    {dec.relationship_description && (
                      <div>
                        <p className="text-xs font-semibold text-gray-700 mb-1">Relationship Description</p>
                        <p className="text-sm text-gray-700">{dec.relationship_description}</p>
                      </div>
                    )}
                    {dec.review_notes && (
                      <div>
                        <p className="text-xs font-semibold text-gray-700 mb-1">Review Notes</p>
                        <p className="text-sm text-gray-700">{dec.review_notes}</p>
                      </div>
                    )}
                    {dec.status === "pending" && (
                      <div className="space-y-2">
                        <label className="text-xs font-semibold text-gray-700">Review Notes</label>
                        <textarea
                          value={reviewNotes[dec.id] ?? ""}
                          onChange={(e) => setReviewNotes((prev) => ({ ...prev, [dec.id]: e.target.value }))}
                          rows={2} placeholder="Optional notes for reviewer decision…"
                          className="block w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-[#1a2332]"
                        />
                        <div className="flex gap-2">
                          <Button size="sm"
                            disabled={!!(actionLoading?.startsWith(dec.id))}
                            onClick={() => reviewDeclaration(dec.id, "approved")}
                            className="bg-green-600 hover:bg-green-700 text-white gap-1">
                            <CheckCircle2 className="h-3 w-3" /> Approve
                          </Button>
                          <Button size="sm" variant="outline"
                            disabled={!!(actionLoading?.startsWith(dec.id))}
                            onClick={() => reviewDeclaration(dec.id, "rejected")}
                            className="border-red-200 text-red-600 hover:bg-red-50 gap-1">
                            <XCircle className="h-3 w-3" /> Reject
                          </Button>
                        </div>
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
