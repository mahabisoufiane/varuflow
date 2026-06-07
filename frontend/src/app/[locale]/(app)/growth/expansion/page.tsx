"use client";

import { useState, useEffect } from "react";
import { toast } from "sonner";
import { api } from "@/lib/api-client";
import { Globe, Plus, Check, X, ChevronRight, Flag } from "lucide-react";

interface Market { code: string; name: string; currency: string; region: string }
interface ChecklistItem { id: string; category: string; title: string; done: boolean; notes: string }
interface Checklist {
  id: string; country_code: string; country_name: string;
  items: ChecklistItem[]; items_by_category: Record<string, ChecklistItem[]>;
  completion_pct: number; done_count: number; total_count: number;
  target_launch_date: string | null;
}

function ProgressRing({ pct }: { pct: number }) {
  const r = 22; const c = 2 * Math.PI * r;
  const dash = (pct / 100) * c;
  const color = pct >= 80 ? "#10b981" : pct >= 50 ? "#f59e0b" : "#3b82f6";
  return (
    <svg width="56" height="56" className="flex-shrink-0">
      <circle cx="28" cy="28" r={r} fill="none" stroke="#f3f4f6" strokeWidth="4" />
      <circle cx="28" cy="28" r={r} fill="none" stroke={color} strokeWidth="4"
        strokeDasharray={`${dash} ${c - dash}`} strokeLinecap="round"
        transform="rotate(-90 28 28)" />
      <text x="28" y="33" textAnchor="middle" fontSize="11" fontWeight="600" fill={color}>{Math.round(pct)}%</text>
    </svg>
  );
}

export default function ExpansionPage() {

  const [markets, setMarkets] = useState<Market[]>([]);
  const [checklists, setChecklists] = useState<Checklist[]>([]);
  const [loading, setLoading] = useState(true);
  const [activeId, setActiveId] = useState<string | null>(null);
  const [showAdd, setShowAdd] = useState(false);
  const [selectedCountry, setSelectedCountry] = useState("");
  const [targetDate, setTargetDate] = useState("");

  useEffect(() => {
    Promise.all([
      api.get<Market[]>("/api/growth/expansion/markets").then(setMarkets).catch(() => {}),
      api.get<Checklist[]>("/api/growth/expansion/checklists").then(setChecklists).catch(() => {}),
    ]).finally(() => setLoading(false));
  }, []);

  const activeChecklist = checklists.find(c => c.id === activeId);
  const existingCodes = new Set(checklists.map(c => c.country_code));
  const availableMarkets = markets.filter(m => !existingCodes.has(m.code));

  async function addChecklist() {
    if (!selectedCountry) { toast.error("Select a country"); return; }
    try {
      const created = await api.post<Checklist>("/api/growth/expansion/checklists", {
        country_code: selectedCountry,
        target_launch_date: targetDate || null,
      });
      setChecklists(prev => [...prev, created]);
      setActiveId(created.id);
      setShowAdd(false);
      setSelectedCountry("");
      toast.success(`${created.country_name} checklist created`);
    } catch (err: any) {
      toast.error(err?.detail || "Failed");
    }
  }

  async function toggleItem(checklistId: string, itemId: string, done: boolean) {
    try {
      const updated = await api.patch<Checklist>(`/api/growth/expansion/checklists/${checklistId}/item`, {
        item_id: itemId, done, notes: "",
      });
      setChecklists(prev => prev.map(c => c.id === checklistId ? updated : c));
    } catch {
      toast.error("Failed to update");
    }
  }

  if (loading) return <div className="animate-pulse space-y-4">{[1,2].map(i => <div key={i} className="h-24 rounded-xl bg-gray-100" />)}</div>;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-gray-900">Market Expansion</h1>
          <p className="mt-1 text-sm text-gray-500">Track per-country readiness for legal, financial, operational and marketing launch requirements.</p>
        </div>
        {availableMarkets.length > 0 && (
          <button onClick={() => setShowAdd(true)} className="btn-primary flex items-center gap-2">
            <Plus className="h-4 w-4" /> Add Market
          </button>
        )}
      </div>

      {showAdd && (
        <div className="rounded-xl border border-green-200 bg-green-50 p-4 space-y-3">
          <p className="text-sm font-semibold text-green-800">Add expansion market</p>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <select className="input" value={selectedCountry} onChange={e => setSelectedCountry(e.target.value)}>
              <option value="">Select country...</option>
              {availableMarkets.map(m => <option key={m.code} value={m.code}>{m.name} ({m.region})</option>)}
            </select>
            <div>
              <input className="input" type="date" placeholder="Target launch date" value={targetDate} onChange={e => setTargetDate(e.target.value)} />
              <p className="text-xs text-gray-400 mt-0.5">Optional target launch date</p>
            </div>
          </div>
          <div className="flex gap-2">
            <button onClick={addChecklist} className="btn-primary text-sm">Create</button>
            <button onClick={() => setShowAdd(false)} className="btn-secondary text-sm">Cancel</button>
          </div>
        </div>
      )}

      {checklists.length === 0 && (
        <div className="text-center py-16 text-gray-400">
          <Globe className="h-10 w-10 mx-auto mb-3 opacity-40" />
          <p>No markets tracked yet. Add your first expansion target.</p>
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Country list */}
        <div className="space-y-2 lg:col-span-1">
          {checklists.map(cl => (
            <button key={cl.id} onClick={() => setActiveId(cl.id)}
              className={`w-full rounded-xl border p-4 flex items-center gap-3 text-left transition-all ${
                activeId === cl.id ? "border-blue-400 bg-blue-50" : "border-gray-200 bg-white hover:border-gray-300"
              }`}>
              <ProgressRing pct={cl.completion_pct} />
              <div className="flex-1 min-w-0">
                <p className="font-semibold text-gray-900">{cl.country_name}</p>
                <p className="text-xs text-gray-500">{cl.done_count}/{cl.total_count} done</p>
                {cl.target_launch_date && (
                  <p className="text-xs text-blue-600 flex items-center gap-1 mt-0.5">
                    <Flag className="h-3 w-3" /> {cl.target_launch_date}
                  </p>
                )}
              </div>
              <ChevronRight className="h-4 w-4 text-gray-400 flex-shrink-0" />
            </button>
          ))}
        </div>

        {/* Checklist detail */}
        {activeChecklist && (
          <div className="lg:col-span-2 space-y-4">
            <h2 className="text-lg font-semibold text-gray-900">{activeChecklist.country_name} — Launch Checklist</h2>
            {Object.entries(activeChecklist.items_by_category).map(([category, items]) => (
              <div key={category} className="rounded-xl border border-gray-200 bg-white overflow-hidden">
                <div className="bg-gray-50 px-4 py-2 border-b border-gray-100">
                  <p className="text-xs font-semibold text-gray-600 uppercase tracking-wide">{category}</p>
                </div>
                <div className="divide-y divide-gray-50">
                  {items.map(item => (
                    <label key={item.id} className="flex items-center gap-3 px-4 py-3 cursor-pointer hover:bg-gray-50 transition-colors">
                      <div
                        onClick={() => toggleItem(activeChecklist.id, item.id, !item.done)}
                        className={`w-5 h-5 rounded flex items-center justify-center flex-shrink-0 transition-all cursor-pointer ${
                          item.done ? "bg-green-500" : "border-2 border-gray-300 bg-white"
                        }`}
                      >
                        {item.done && <Check className="h-3 w-3 text-white" />}
                      </div>
                      <span className={`text-sm ${item.done ? "line-through text-gray-400" : "text-gray-700"}`}>{item.title}</span>
                    </label>
                  ))}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
