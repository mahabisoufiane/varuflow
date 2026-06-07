"use client";

import { useEffect, useState } from "react";
import { useRouter, useParams } from "next/navigation";
import { createClient } from "@/lib/supabase/client";
import { PlusCircle, Leaf, RefreshCw, CheckCircle2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { toast } from "sonner";
import styles from "./page.module.scss";

interface CarbonEntry {
  id: string;
  scope: number;
  category: string;
  description: string | null;
  quantity: number;
  unit: string;
  co2_kg: number;
  period_start: string;
  data_source: string | null;
  verified: boolean;
}

interface CarbonSummary {
  scope1_tco2: number;
  scope2_tco2: number;
  scope3_tco2: number;
  total_tco2: number;
  year: number;
}

const SCOPE_COLORS: Record<number, string> = {
  1: "bg-orange-100 text-orange-700",
  2: "bg-yellow-100 text-yellow-700",
  3: "bg-blue-100 text-blue-700",
};

const SCOPE_MODULE: Record<string, keyof typeof styles> = {
  "1": "scope1",
  "2": "scope2",
  "3": "scope3",
};

const SCOPE_CARD_COLORS: Record<number, { bg: string; text: string; label: string }> = {
  1: { bg: "bg-orange-50 border-orange-200", text: "text-orange-700", label: "Scope 1 — Direct" },
  2: { bg: "bg-yellow-50 border-yellow-200", text: "text-yellow-700", label: "Scope 2 — Energy" },
  3: { bg: "bg-blue-50 border-blue-200", text: "text-blue-700", label: "Scope 3 — Value Chain" },
};

const EMPTY_FORM = {
  scope: "1", category: "", description: "", quantity: "", unit: "kg",
  emission_factor: "", co2_kg: "", period_start: "", data_source: "",
};

export default function CarbonPage() {
  const router = useRouter();
  const params = useParams<{ locale: string }>();
  const locale = params?.locale ?? "en";
  const supabase = createClient();

  const [entries, setEntries] = useState<CarbonEntry[]>([]);
  const [summary, setSummary] = useState<CarbonSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [year, setYear] = useState(new Date().getFullYear().toString());
  const [showNew, setShowNew] = useState(false);
  const [newForm, setNewForm] = useState(EMPTY_FORM);
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
      const [entRes, sumRes] = await Promise.all([
        fetch(apiUrl("/api/carbon"), { headers: { Authorization: `Bearer ${token}` } }),
        fetch(apiUrl(`/api/carbon/summary?year=${year}`), { headers: { Authorization: `Bearer ${token}` } }),
      ]);
      if (entRes.status === 401) { router.push(`/${locale}/auth/login`); return; }
      if (entRes.ok) setEntries(await entRes.json());
      if (sumRes.ok) setSummary(await sumRes.json());
    } catch {
      toast.error("Failed to load carbon data");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { load(); }, [year]);  // eslint-disable-line react-hooks/exhaustive-deps

  async function createEntry() {
    if (!newForm.quantity || !newForm.unit || !newForm.period_start || !newForm.category) {
      toast.error("Category, quantity, unit, and period start are required"); return;
    }
    setActionLoading("create");
    try {
      const token = await getToken();
      if (!token) return;
      const res = await fetch(apiUrl("/api/carbon"), {
        method: "POST",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
        body: JSON.stringify({
          scope: parseInt(newForm.scope),
          category: newForm.category,
          description: newForm.description || null,
          quantity: parseFloat(newForm.quantity),
          unit: newForm.unit,
          emission_factor: newForm.emission_factor ? parseFloat(newForm.emission_factor) : null,
          co2_kg: newForm.co2_kg ? parseFloat(newForm.co2_kg) : null,
          period_start: newForm.period_start,
          data_source: newForm.data_source || null,
        }),
      });
      if (!res.ok) {
        const b = await res.json().catch(() => ({}));
        toast.error(b.detail ?? "Failed to create entry");
        return;
      }
      toast.success("Carbon entry added");
      setShowNew(false);
      setNewForm(EMPTY_FORM);
      await load();
    } catch {
      toast.error("Something went wrong");
    } finally {
      setActionLoading(null);
    }
  }

  async function verifyEntry(id: string) {
    setActionLoading(id + "_verify");
    try {
      const token = await getToken();
      if (!token) return;
      const res = await fetch(apiUrl(`/api/carbon/${id}/verify`), {
        method: "POST",
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) {
        const b = await res.json().catch(() => ({}));
        toast.error(b.detail ?? "Failed to verify");
        return;
      }
      toast.success("Entry verified");
      await load();
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
          <h1 className="text-xl font-semibold text-gray-900">Carbon Calculator</h1>
          <p className="text-sm text-muted-foreground mt-0.5">Track greenhouse gas emissions across Scope 1, 2, and 3.</p>
        </div>
        <div className="flex items-center gap-2">
          <input
            type="number" value={year} onChange={(e) => setYear(e.target.value)}
            className="w-24 rounded-md border border-gray-300 px-3 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-[#1a2332]"
          />
          <Button onClick={() => setShowNew(true)} className="bg-[#1a2332] hover:bg-[#2a3342] text-white gap-2">
            <PlusCircle className="h-4 w-4" /> Add Entry
          </Button>
        </div>
      </div>

      {/* Summary cards */}
      {summary && (
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
          {([1, 2, 3] as const).map((scope) => {
            const cfg = SCOPE_CARD_COLORS[scope];
            const value = scope === 1 ? summary.scope1_tco2 : scope === 2 ? summary.scope2_tco2 : summary.scope3_tco2;
            return (
              <div key={scope} className={`rounded-xl border p-4 ${cfg.bg}`}>
                <p className="text-xs text-gray-600">{cfg.label}</p>
                <p className={`text-2xl font-bold mt-1 ${cfg.text}`}>{value.toFixed(2)}</p>
                <p className="text-xs text-gray-500 mt-0.5">t CO₂e</p>
              </div>
            );
          })}
          <div className="rounded-xl border bg-gray-50 border-gray-200 p-4">
            <p className="text-xs text-gray-600">Total</p>
            <p className="text-2xl font-bold mt-1 text-gray-900">{summary.total_tco2.toFixed(2)}</p>
            <p className="text-xs text-gray-500 mt-0.5">t CO₂e in {summary.year}</p>
          </div>
        </div>
      )}

      {/* New entry form */}
      {showNew && (
        <div className="rounded-xl border border-[#1a2332]/20 bg-white p-5 shadow-sm space-y-3">
          <h3 className="text-sm font-semibold text-gray-900">New Carbon Entry</h3>
          <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
            <div className="space-y-1">
              <label className="text-xs font-medium text-gray-700">Scope</label>
              <select value={newForm.scope} onChange={(e) => setNewForm((f) => ({ ...f, scope: e.target.value }))}
                className="block w-full rounded-md border border-gray-300 px-2 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-[#1a2332]">
                <option value="1">Scope 1 — Direct</option>
                <option value="2">Scope 2 — Energy</option>
                <option value="3">Scope 3 — Value Chain</option>
              </select>
            </div>
            <div className="space-y-1">
              <label className="text-xs font-medium text-gray-700">Category *</label>
              <input value={newForm.category} onChange={(e) => setNewForm((f) => ({ ...f, category: e.target.value }))}
                placeholder="Fuel, Electricity, Transport…"
                className="block w-full rounded-md border border-gray-300 px-3 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-[#1a2332]" />
            </div>
            <div className="space-y-1">
              <label className="text-xs font-medium text-gray-700">Period Start *</label>
              <input type="date" value={newForm.period_start} onChange={(e) => setNewForm((f) => ({ ...f, period_start: e.target.value }))}
                className="block w-full rounded-md border border-gray-300 px-3 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-[#1a2332]" />
            </div>
            <div className="space-y-1">
              <label className="text-xs font-medium text-gray-700">Quantity *</label>
              <input type="number" value={newForm.quantity} onChange={(e) => setNewForm((f) => ({ ...f, quantity: e.target.value }))}
                className="block w-full rounded-md border border-gray-300 px-3 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-[#1a2332]" />
            </div>
            <div className="space-y-1">
              <label className="text-xs font-medium text-gray-700">Unit *</label>
              <input value={newForm.unit} onChange={(e) => setNewForm((f) => ({ ...f, unit: e.target.value }))}
                placeholder="kg, kWh, km…"
                className="block w-full rounded-md border border-gray-300 px-3 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-[#1a2332]" />
            </div>
            <div className="space-y-1">
              <label className="text-xs font-medium text-gray-700">Emission Factor</label>
              <input type="number" value={newForm.emission_factor} onChange={(e) => setNewForm((f) => ({ ...f, emission_factor: e.target.value }))}
                placeholder="kg CO₂ per unit"
                className="block w-full rounded-md border border-gray-300 px-3 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-[#1a2332]" />
            </div>
            <div className="space-y-1">
              <label className="text-xs font-medium text-gray-700">CO₂ kg (manual override)</label>
              <input type="number" value={newForm.co2_kg} onChange={(e) => setNewForm((f) => ({ ...f, co2_kg: e.target.value }))}
                className="block w-full rounded-md border border-gray-300 px-3 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-[#1a2332]" />
            </div>
            <div className="space-y-1 col-span-2">
              <label className="text-xs font-medium text-gray-700">Data Source</label>
              <input value={newForm.data_source} onChange={(e) => setNewForm((f) => ({ ...f, data_source: e.target.value }))}
                placeholder="Meter reading, invoice, estimate…"
                className="block w-full rounded-md border border-gray-300 px-3 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-[#1a2332]" />
            </div>
          </div>
          <textarea value={newForm.description} onChange={(e) => setNewForm((f) => ({ ...f, description: e.target.value }))}
            placeholder="Description (optional)" rows={2}
            className="block w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-[#1a2332]" />
          <div className="flex gap-2">
            <Button variant="outline" onClick={() => setShowNew(false)}>Cancel</Button>
            <Button disabled={actionLoading === "create"} onClick={createEntry}
              className="bg-[#1a2332] hover:bg-[#2a3342] text-white">
              {actionLoading === "create" ? "Saving…" : "Add Entry"}
            </Button>
          </div>
        </div>
      )}

      {/* Entries list */}
      {loading && entries.length === 0 ? (
        <div className="text-center py-12"><RefreshCw className="h-6 w-6 animate-spin mx-auto text-muted-foreground" /></div>
      ) : entries.length === 0 ? (
        <div className="rounded-xl border bg-white p-12 text-center shadow-sm">
          <Leaf className="h-10 w-10 text-muted-foreground mx-auto mb-3" />
          <p className="text-gray-600 font-medium">No carbon entries yet</p>
        </div>
      ) : (
        <div className="rounded-xl border bg-white shadow-sm divide-y divide-gray-100">
          <div className="hidden sm:grid grid-cols-[auto_1fr_auto_auto_auto_auto_auto] gap-4 px-5 py-2.5 text-xs font-medium text-muted-foreground bg-gray-50 rounded-t-xl">
            <span>Scope</span>
            <span>Category</span>
            <span>Quantity</span>
            <span>CO₂ kg</span>
            <span>Period</span>
            <span>Verified</span>
            <span />
          </div>
          {entries.map((entry) => (
            <div key={entry.id} className="flex items-center gap-4 px-5 py-3.5 flex-wrap">
              <span className={styles[SCOPE_MODULE[String(entry.scope)] ?? "scope1"]}>
                Scope {entry.scope}
              </span>
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium text-gray-900">{entry.category}</p>
                {entry.description && <p className="text-xs text-muted-foreground truncate">{entry.description}</p>}
              </div>
              <span className="text-sm text-gray-700 flex-shrink-0">{entry.quantity} {entry.unit}</span>
              <span className="text-sm font-medium text-gray-900 flex-shrink-0">{entry.co2_kg.toFixed(1)} kg</span>
              <span className="text-xs text-muted-foreground flex-shrink-0">{new Date(entry.period_start).toLocaleDateString()}</span>
              {entry.verified ? (
                <span className="inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium bg-green-100 text-green-700 flex-shrink-0">
                  <CheckCircle2 className="h-3 w-3" /> Verified
                </span>
              ) : (
                <Button size="sm" variant="outline"
                  disabled={actionLoading === entry.id + "_verify"}
                  onClick={() => verifyEntry(entry.id)}
                  className="gap-1 text-xs h-7 flex-shrink-0">
                  {actionLoading === entry.id + "_verify" ? <RefreshCw className="h-3 w-3 animate-spin" /> : null}
                  Verify
                </Button>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
