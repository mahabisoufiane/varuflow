"use client";

import { useState, useEffect } from "react";
import { toast } from "sonner";
import { Building2, Plus, Edit2 } from "lucide-react";

interface Entity { id: string; name: string; legal_name?: string; entity_type: string; reporting_currency?: string; parent_org_id?: string }

export default function SubsidiariesPage() {
  const apiBase = process.env.NEXT_PUBLIC_API_URL!;
  const [entities, setEntities] = useState<Entity[]>([]);
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState({ name: "", legal_name: "", reporting_currency: "SEK" });
  const [loading, setLoading] = useState(false);

  const fetch_ = (url: string, opts?: RequestInit) =>
    fetch(`${apiBase}${url}`, { credentials: "include", ...opts });

  async function load() {
    const res = await fetch_("/api/multi-entity/entities");
    if (res.ok) setEntities((await res.json()).entities);
  }

  useEffect(() => { load(); }, []);

  async function create() {
    if (!form.name) { toast.error("Name required"); return; }
    setLoading(true);
    const res = await fetch_("/api/multi-entity/entities", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ ...form, entity_type: "subsidiary" }),
    });
    if (res.ok) {
      toast.success("Subsidiary created");
      setShowForm(false);
      setForm({ name: "", legal_name: "", reporting_currency: "SEK" });
      await load();
    } else {
      const err = await res.json();
      toast.error(err.detail || "Failed");
    }
    setLoading(false);
  }

  const entityTypeColor: Record<string, string> = {
    standalone: "bg-gray-100 text-gray-600",
    parent: "bg-blue-100 text-blue-700",
    subsidiary: "bg-purple-100 text-purple-700",
    franchisor: "bg-amber-100 text-amber-700",
    franchisee: "bg-green-100 text-green-700",
  };

  // Separate caller org from subsidiaries
  const parent = entities.find(e => !e.parent_org_id);
  const children = entities.filter(e => e.parent_org_id);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-gray-900">Group Structure</h1>
          <p className="mt-1 text-sm text-gray-500">Subsidiaries and branches under your organisation.</p>
        </div>
        <button onClick={() => setShowForm(true)} className="btn-primary flex items-center gap-2">
          <Plus className="h-4 w-4" /> Add Subsidiary
        </button>
      </div>

      {showForm && (
        <div className="rounded-xl border border-blue-200 bg-blue-50 p-4 space-y-3">
          <input className="input w-full" placeholder="Company name*" value={form.name} onChange={e => setForm(f => ({ ...f, name: e.target.value }))} />
          <input className="input w-full" placeholder="Legal name (if different)" value={form.legal_name} onChange={e => setForm(f => ({ ...f, legal_name: e.target.value }))} />
          <select className="input w-40" value={form.reporting_currency} onChange={e => setForm(f => ({ ...f, reporting_currency: e.target.value }))}>
            <option>SEK</option><option>EUR</option><option>NOK</option><option>DKK</option><option>USD</option>
          </select>
          <div className="flex gap-2">
            <button onClick={create} disabled={loading} className="btn-primary">{loading ? "Creating…" : "Create"}</button>
            <button onClick={() => setShowForm(false)} className="btn-secondary">Cancel</button>
          </div>
        </div>
      )}

      {/* Entity tree */}
      {parent && (
        <div>
          {/* Parent node */}
          <div className="flex items-center gap-4 rounded-xl border-2 border-blue-400 bg-blue-50 p-5">
            <Building2 className="h-6 w-6 text-blue-600" />
            <div className="flex-1">
              <p className="font-semibold text-gray-900">{parent.name}</p>
              {parent.legal_name && <p className="text-xs text-gray-500">{parent.legal_name}</p>}
            </div>
            <span className={`text-xs px-2 py-0.5 rounded-full font-medium capitalize ${entityTypeColor[parent.entity_type] || "bg-gray-100 text-gray-600"}`}>
              {parent.entity_type} (this org)
            </span>
          </div>

          {/* Children */}
          {children.length > 0 && (
            <div className="ml-8 mt-2 space-y-2 border-l-2 border-gray-200 pl-6">
              {children.map(child => (
                <div key={child.id} className="flex items-center gap-4 rounded-xl border border-gray-200 bg-white p-4">
                  <Building2 className="h-5 w-5 text-gray-400" />
                  <div className="flex-1">
                    <p className="font-medium text-sm text-gray-900">{child.name}</p>
                    {child.legal_name && <p className="text-xs text-gray-500">{child.legal_name}</p>}
                    {child.reporting_currency && <p className="text-xs text-gray-400">{child.reporting_currency}</p>}
                  </div>
                  <span className={`text-xs px-2 py-0.5 rounded-full font-medium capitalize ${entityTypeColor[child.entity_type] || "bg-gray-100 text-gray-600"}`}>
                    {child.entity_type}
                  </span>
                </div>
              ))}
            </div>
          )}

          {children.length === 0 && !showForm && (
            <p className="mt-4 text-center text-sm text-gray-400">No subsidiaries yet. Add one above.</p>
          )}
        </div>
      )}
    </div>
  );
}
