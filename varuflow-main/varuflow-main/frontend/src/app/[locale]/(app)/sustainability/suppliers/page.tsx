"use client";

import { useEffect, useState } from "react";
import { useRouter, useParams } from "next/navigation";
import { createClient } from "@/lib/supabase/client";
import { PlusCircle, Award, RefreshCw, Edit3, CheckCircle2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { toast } from "sonner";

interface SupplierRating {
  id: string;
  supplier_id: string;
  environmental_score: number;
  social_score: number;
  governance_score: number;
  overall_score: number;
  risk_level: string;
  ethical_sourcing_verified: boolean;
  certifications: string[];
  updated_at: string;
}

const RISK_COLORS: Record<string, string> = {
  low:      "bg-green-100 text-green-700",
  medium:   "bg-amber-100 text-amber-700",
  high:     "bg-orange-100 text-orange-700",
  critical: "bg-red-100 text-red-700",
};

function ScoreBar({ value }: { value: number }) {
  const color = value >= 70 ? "bg-green-500" : value >= 40 ? "bg-amber-400" : "bg-red-400";
  return (
    <div className="flex items-center gap-2">
      <div className="h-1.5 w-24 rounded-full bg-gray-100 overflow-hidden flex-shrink-0">
        <div className={`h-full rounded-full ${color}`} style={{ width: `${Math.min(value, 100)}%` }} />
      </div>
      <span className="text-xs text-gray-700">{value}</span>
    </div>
  );
}

const EMPTY_FORM = {
  supplier_id: "", environmental_score: "50", social_score: "50", governance_score: "50",
  risk_level: "medium", ethical_sourcing_verified: false, certifications: "",
};

export default function SupplierSustainabilityPage() {
  const router = useRouter();
  const params = useParams<{ locale: string }>();
  const locale = params?.locale ?? "en";
  const supabase = createClient();

  const [ratings, setRatings] = useState<SupplierRating[]>([]);
  const [loading, setLoading] = useState(true);
  const [riskFilter, setRiskFilter] = useState("all");
  const [showForm, setShowForm] = useState<string | null>(null); // null = hidden, "new" = create, id = edit
  const [form, setForm] = useState(EMPTY_FORM);
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
      const res = await fetch(apiUrl("/api/supplier-sustainability"), { headers: { Authorization: `Bearer ${token}` } });
      if (res.status === 401) { router.push(`/${locale}/auth/login`); return; }
      if (res.ok) setRatings(await res.json());
    } catch {
      toast.error("Failed to load supplier ratings");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { load(); }, []);  // eslint-disable-line react-hooks/exhaustive-deps

  function openEdit(rating: SupplierRating) {
    setForm({
      supplier_id: rating.supplier_id,
      environmental_score: String(rating.environmental_score),
      social_score: String(rating.social_score),
      governance_score: String(rating.governance_score),
      risk_level: rating.risk_level,
      ethical_sourcing_verified: rating.ethical_sourcing_verified,
      certifications: (rating.certifications ?? []).join(", "),
    });
    setShowForm(rating.id);
  }

  async function saveRating() {
    if (!form.supplier_id.trim()) { toast.error("Supplier ID is required"); return; }
    const isEdit = showForm && showForm !== "new";
    setActionLoading("save");
    try {
      const token = await getToken();
      if (!token) return;
      const body = {
        supplier_id: form.supplier_id,
        environmental_score: parseInt(form.environmental_score),
        social_score: parseInt(form.social_score),
        governance_score: parseInt(form.governance_score),
        risk_level: form.risk_level,
        ethical_sourcing_verified: form.ethical_sourcing_verified,
        certifications: form.certifications
          ? form.certifications.split(",").map((c) => c.trim()).filter(Boolean)
          : [],
      };
      const res = await fetch(
        isEdit ? apiUrl(`/api/supplier-sustainability/${showForm}`) : apiUrl("/api/supplier-sustainability"),
        {
          method: isEdit ? "PUT" : "POST",
          headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
          body: JSON.stringify(body),
        },
      );
      if (!res.ok) {
        const b = await res.json().catch(() => ({}));
        toast.error(b.detail ?? "Failed to save rating");
        return;
      }
      toast.success(isEdit ? "Rating updated" : "Rating created");
      setShowForm(null);
      setForm(EMPTY_FORM);
      await load();
    } catch {
      toast.error("Something went wrong");
    } finally {
      setActionLoading(null);
    }
  }

  const filtered = riskFilter === "all" ? ratings : ratings.filter((r) => r.risk_level === riskFilter);

  return (
    <div className="mx-auto max-w-4xl space-y-6 p-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-gray-900">Supplier Sustainability</h1>
          <p className="text-sm text-muted-foreground mt-0.5">Rate and monitor supplier ESG performance.</p>
        </div>
        <Button onClick={() => { setForm(EMPTY_FORM); setShowForm("new"); }}
          className="bg-[#1a2332] hover:bg-[#2a3342] text-white gap-2">
          <PlusCircle className="h-4 w-4" /> Add Rating
        </Button>
      </div>

      {/* Risk filter */}
      <div className="flex items-center gap-2 flex-wrap">
        {["all", "low", "medium", "high", "critical"].map((r) => (
          <button key={r} type="button" onClick={() => setRiskFilter(r)}
            className={`rounded-full px-3 py-1 text-xs font-medium capitalize transition-colors ${
              riskFilter === r ? "bg-[#1a2332] text-white" : "bg-gray-100 text-gray-600 hover:bg-gray-200"
            }`}>
            {r === "all" ? "All" : r}
          </button>
        ))}
      </div>

      {/* Form */}
      {showForm && (
        <div className="rounded-xl border border-[#1a2332]/20 bg-white p-5 shadow-sm space-y-3">
          <h3 className="text-sm font-semibold text-gray-900">{showForm === "new" ? "New Rating" : "Edit Rating"}</h3>
          <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
            <div className="space-y-1 col-span-2 sm:col-span-1">
              <label className="text-xs font-medium text-gray-700">Supplier ID (UUID) *</label>
              <input value={form.supplier_id} onChange={(e) => setForm((f) => ({ ...f, supplier_id: e.target.value }))}
                placeholder="UUID from your supplier record"
                className="block w-full rounded-md border border-gray-300 px-3 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-[#1a2332]" />
            </div>
            <div className="space-y-1">
              <label className="text-xs font-medium text-gray-700">Environmental (0-100)</label>
              <input type="number" min="0" max="100" value={form.environmental_score}
                onChange={(e) => setForm((f) => ({ ...f, environmental_score: e.target.value }))}
                className="block w-full rounded-md border border-gray-300 px-3 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-[#1a2332]" />
            </div>
            <div className="space-y-1">
              <label className="text-xs font-medium text-gray-700">Social (0-100)</label>
              <input type="number" min="0" max="100" value={form.social_score}
                onChange={(e) => setForm((f) => ({ ...f, social_score: e.target.value }))}
                className="block w-full rounded-md border border-gray-300 px-3 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-[#1a2332]" />
            </div>
            <div className="space-y-1">
              <label className="text-xs font-medium text-gray-700">Governance (0-100)</label>
              <input type="number" min="0" max="100" value={form.governance_score}
                onChange={(e) => setForm((f) => ({ ...f, governance_score: e.target.value }))}
                className="block w-full rounded-md border border-gray-300 px-3 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-[#1a2332]" />
            </div>
            <div className="space-y-1">
              <label className="text-xs font-medium text-gray-700">Risk Level</label>
              <select value={form.risk_level} onChange={(e) => setForm((f) => ({ ...f, risk_level: e.target.value }))}
                className="block w-full rounded-md border border-gray-300 px-2 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-[#1a2332]">
                <option value="low">Low</option>
                <option value="medium">Medium</option>
                <option value="high">High</option>
                <option value="critical">Critical</option>
              </select>
            </div>
            <div className="space-y-1 col-span-2">
              <label className="text-xs font-medium text-gray-700">Certifications (comma-separated)</label>
              <input value={form.certifications}
                onChange={(e) => setForm((f) => ({ ...f, certifications: e.target.value }))}
                placeholder="ISO 14001, SA8000, Fair Trade…"
                className="block w-full rounded-md border border-gray-300 px-3 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-[#1a2332]" />
            </div>
          </div>
          <label className="flex items-center gap-2 cursor-pointer">
            <input type="checkbox" checked={form.ethical_sourcing_verified}
              onChange={(e) => setForm((f) => ({ ...f, ethical_sourcing_verified: e.target.checked }))}
              className="rounded border-gray-300" />
            <span className="text-xs font-medium text-gray-700">Ethical Sourcing Verified</span>
          </label>
          <div className="flex gap-2">
            <Button variant="outline" onClick={() => setShowForm(null)}>Cancel</Button>
            <Button disabled={actionLoading === "save"} onClick={saveRating}
              className="bg-[#1a2332] hover:bg-[#2a3342] text-white">
              {actionLoading === "save" ? "Saving…" : "Save Rating"}
            </Button>
          </div>
        </div>
      )}

      {/* Ratings list */}
      {loading && ratings.length === 0 ? (
        <div className="text-center py-12"><RefreshCw className="h-6 w-6 animate-spin mx-auto text-muted-foreground" /></div>
      ) : filtered.length === 0 ? (
        <div className="rounded-xl border bg-white p-12 text-center shadow-sm">
          <Award className="h-10 w-10 text-muted-foreground mx-auto mb-3" />
          <p className="text-gray-600 font-medium">No supplier ratings found</p>
        </div>
      ) : (
        <div className="rounded-xl border bg-white shadow-sm divide-y divide-gray-100">
          <div className="hidden sm:grid grid-cols-[1fr_auto_auto_auto_auto_auto_auto_auto] gap-4 px-5 py-2.5 text-xs font-medium text-muted-foreground bg-gray-50 rounded-t-xl">
            <span>Supplier</span>
            <span>Risk</span>
            <span>Environmental</span>
            <span>Social</span>
            <span>Governance</span>
            <span>Overall</span>
            <span>Ethical</span>
            <span />
          </div>
          {filtered.map((r) => (
            <div key={r.id} className="flex items-center gap-4 px-5 py-3.5 flex-wrap">
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium text-gray-900 font-mono">{r.supplier_id.slice(0, 12)}…</p>
                {r.certifications && r.certifications.length > 0 && (
                  <div className="flex flex-wrap gap-1 mt-1">
                    {r.certifications.map((cert) => (
                      <span key={cert} className="inline-flex rounded-full px-2 py-0.5 text-xs bg-gray-100 text-gray-700">{cert}</span>
                    ))}
                  </div>
                )}
              </div>
              <span className={`inline-flex rounded-full px-2.5 py-0.5 text-xs font-medium flex-shrink-0 capitalize ${RISK_COLORS[r.risk_level] ?? "bg-gray-100 text-gray-600"}`}>
                {r.risk_level}
              </span>
              <div className="flex-shrink-0"><ScoreBar value={r.environmental_score} /></div>
              <div className="flex-shrink-0"><ScoreBar value={r.social_score} /></div>
              <div className="flex-shrink-0"><ScoreBar value={r.governance_score} /></div>
              <div className="flex-shrink-0"><ScoreBar value={r.overall_score} /></div>
              {r.ethical_sourcing_verified ? (
                <CheckCircle2 className="h-4 w-4 text-green-600 flex-shrink-0" />
              ) : (
                <span className="h-4 w-4 flex-shrink-0" />
              )}
              <button type="button" onClick={() => openEdit(r)}
                className="text-muted-foreground hover:text-[#1a2332] transition-colors flex-shrink-0">
                <Edit3 className="h-4 w-4" />
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
