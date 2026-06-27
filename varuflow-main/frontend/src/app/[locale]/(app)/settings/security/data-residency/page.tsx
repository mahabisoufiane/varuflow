"use client";

import { useState, useEffect } from "react";
import { toast } from "sonner";
import { Globe, AlertTriangle, CheckCircle2 } from "lucide-react";
import { api } from "@/lib/api-client";

interface Region { id: string; name: string; description: string; frameworks: string[]; countries: string[] }
interface Residency { data_region: string; region_info: Region }

export default function DataResidencyPage() {
  const [current, setCurrent] = useState<Residency | null>(null);
  const [regions, setRegions] = useState<Region[]>([]);
  const [selected, setSelected] = useState("");
  const [acknowledged, setAcknowledged] = useState(false);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    Promise.all([
      api.get<Residency>("/api/compliance/data-residency")
        .then(d => { setCurrent(d); setSelected(d.data_region); })
        .catch(() => {}),
      api.get<{ regions: Region[] }>("/api/compliance/data-residency/regions")
        .then(d => setRegions(d.regions))
        .catch(() => {}),
    ]);
  }, []);

  async function save() {
    if (!selected) { toast.error("Select a region"); return; }
    if (!acknowledged) { toast.error("Please acknowledge the implications below"); return; }
    setSaving(true);
    try {
      const data = await api.patch<Residency & { warning: string }>("/api/compliance/data-residency", { data_region: selected, acknowledged: true });
      setCurrent(data);
      toast.success("Data region updated");
      toast.info(data.warning, { duration: 8000 });
      setAcknowledged(false);
    } catch { toast.error("Update failed"); }
    setSaving(false);
  }

  const regionColors: Record<string, string> = {
    eu: "bg-blue-50 border-blue-400 text-blue-900",
    mena: "bg-amber-50 border-amber-400 text-amber-900",
    us: "bg-purple-50 border-purple-400 text-purple-900",
    apac: "bg-green-50 border-green-400 text-green-900",
  };

  const hasChanged = selected && current && selected !== current.data_region;

  return (
    <div className="max-w-2xl space-y-6">
      <div>
        <h1 className="text-2xl font-semibold text-gray-900">Data Residency</h1>
        <p className="mt-1 text-sm text-gray-500">
          Select where your organisation's data is processed and stored. Critical for enterprise procurement and regulatory compliance.
        </p>
      </div>

      {current && (
        <div className={`rounded-xl border-2 p-4 ${regionColors[current.data_region] || "bg-gray-50 border-gray-300"}`}>
          <div className="flex items-center gap-2">
            <CheckCircle2 className="h-5 w-5" />
            <span className="font-semibold">Current region: {current.region_info?.name || current.data_region.toUpperCase()}</span>
          </div>
          {current.region_info?.frameworks && (
            <div className="mt-2 flex flex-wrap gap-1">
              {current.region_info.frameworks.map(f => (
                <span key={f} className="text-xs bg-white/60 border border-current/20 rounded-full px-2 py-0.5">{f}</span>
              ))}
            </div>
          )}
        </div>
      )}

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
        {regions.map(r => (
          <label key={r.id} className={`flex flex-col gap-2 rounded-xl border-2 p-4 cursor-pointer transition-all ${
            selected === r.id ? "border-blue-500 bg-blue-50" : "border-gray-200 hover:border-gray-300"
          }`}>
            <input type="radio" name="region" value={r.id} checked={selected === r.id} onChange={() => setSelected(r.id)} className="sr-only" />
            <div className="flex items-center gap-2">
              <Globe className="h-4 w-4 text-gray-500" />
              <span className="font-medium text-sm text-gray-900">{r.name}</span>
            </div>
            <p className="text-xs text-gray-500">{r.description}</p>
            <div className="flex flex-wrap gap-1">
              {r.frameworks.map(f => (
                <span key={f} className="text-xs bg-white border border-gray-200 rounded-full px-2 py-0.5 text-gray-600">{f}</span>
              ))}
            </div>
          </label>
        ))}
      </div>

      {hasChanged && (
        <div className="rounded-xl border border-amber-300 bg-amber-50 p-4 space-y-3">
          <div className="flex items-start gap-2 text-amber-800">
            <AlertTriangle className="h-5 w-5 flex-shrink-0 mt-0.5" />
            <div>
              <p className="font-semibold text-sm">Important: this change records your region preference only.</p>
              <p className="text-xs mt-1">
                Changing the region does <strong>not</strong> automatically migrate existing data. If you need existing data physically
                moved to a new region for compliance, contact <strong>support@varuflow.com</strong> to initiate a data migration.
                The change is logged to the tamper-evident audit trail.
              </p>
            </div>
          </div>
          <label className="flex items-start gap-2 cursor-pointer">
            <input type="checkbox" checked={acknowledged} onChange={e => setAcknowledged(e.target.checked)} className="rounded mt-0.5" />
            <span className="text-sm text-amber-800">
              I understand that changing the region setting does not automatically migrate existing data and may require a separate data migration process.
            </span>
          </label>
          <button onClick={save} disabled={saving || !acknowledged} className="btn-primary">
            {saving ? "Saving…" : `Switch to ${regions.find(r => r.id === selected)?.name}`}
          </button>
        </div>
      )}

      <div className="rounded-xl border border-gray-200 bg-gray-50 p-4 text-xs text-gray-500 space-y-1">
        <p className="font-medium text-gray-700">What this controls</p>
        <p>• Which compliance frameworks apply to your organisation's data processing</p>
        <p>• Data locality requirements shown in your compliance summary / procurement questionnaire</p>
        <p>• All region changes are recorded in the hash-chained audit log</p>
        <p>• Actual infrastructure placement is managed by Varuflow's infrastructure team</p>
      </div>
    </div>
  );
}
