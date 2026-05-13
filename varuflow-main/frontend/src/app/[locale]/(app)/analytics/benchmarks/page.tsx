"use client";

import { useState, useEffect } from "react";
import { toast } from "sonner";
import { TrendingUp, TrendingDown, Minus, ChevronDown } from "lucide-react";

const SECTORS = ["wholesale", "retail", "manufacturing", "food_beverage", "construction", "services"] as const;

interface Metric {
  metric: string; label: string;
  org_value: number | null; industry_value: number | null;
  unit: string; higher_is_better: boolean;
}
interface BenchmarkData { sector: string; source: string; metrics: Metric[] }

function PerformanceBar({ org, industry, higherIsBetter }: { org: number | null; industry: number | null; higherIsBetter: boolean }) {
  if (org == null || industry == null) return <div className="h-2 bg-gray-100 rounded-full" />;
  const max = Math.max(Math.abs(org), Math.abs(industry)) * 1.3 || 1;
  const orgPct = Math.max(0, Math.min(100, (org / max) * 100));
  const indPct = Math.max(0, Math.min(100, (industry / max) * 100));
  const better = higherIsBetter ? org >= industry : org <= industry;
  return (
    <div className="space-y-1.5">
      <div className="relative h-2 bg-gray-100 rounded-full overflow-hidden">
        <div className={`absolute h-full rounded-full transition-all ${better ? "bg-green-500" : "bg-amber-400"}`} style={{ width: `${orgPct}%` }} />
      </div>
      <div className="relative h-1.5 bg-gray-100 rounded-full overflow-hidden">
        <div className="absolute h-full bg-blue-300 rounded-full" style={{ width: `${indPct}%` }} />
      </div>
    </div>
  );
}

function DeltaBadge({ org, industry, higherIsBetter, unit }: { org: number | null; industry: number | null; higherIsBetter: boolean; unit: string }) {
  if (org == null || industry == null) return <span className="text-xs text-gray-400">No data</span>;
  const delta = org - industry;
  const better = higherIsBetter ? delta >= 0 : delta <= 0;
  const icon = Math.abs(delta) < 0.1 ? <Minus className="h-3 w-3" /> :
    delta > 0 ? <TrendingUp className="h-3 w-3" /> : <TrendingDown className="h-3 w-3" />;
  return (
    <span className={`inline-flex items-center gap-0.5 text-xs font-medium px-1.5 py-0.5 rounded-full ${better ? "bg-green-100 text-green-700" : "bg-amber-100 text-amber-700"}`}>
      {icon} {delta > 0 ? "+" : ""}{delta.toFixed(1)}{unit}
    </span>
  );
}

export default function BenchmarksPage() {
  const apiBase = process.env.NEXT_PUBLIC_API_URL!;
  const [sector, setSector] = useState<string>("wholesale");
  const [data, setData] = useState<BenchmarkData | null>(null);
  const [loading, setLoading] = useState(false);

  const f = (url: string, opts?: RequestInit) =>
    fetch(`${apiBase}${url}`, { credentials: "include", ...opts });

  async function load(s: string) {
    setLoading(true);
    try {
      const res = await f(`/api/bi/benchmarks?sector=${s}`);
      if (res.ok) setData(await res.json());
      else { const e = await res.json(); toast.error(e.detail || "Failed"); }
    } finally { setLoading(false); }
  }

  async function saveSector(s: string) {
    await f("/api/bi/benchmarks/sector", {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ sector: s }),
    });
    toast.success("Sector saved");
  }

  useEffect(() => { load(sector); }, [sector]);

  return (
    <div className="max-w-3xl space-y-6">
      <div>
        <h1 className="text-2xl font-semibold text-gray-900">Benchmark Comparisons</h1>
        <p className="mt-1 text-sm text-gray-500">Your KPIs vs industry averages — see where you stand.</p>
      </div>

      {/* Sector picker */}
      <div className="flex items-center gap-3">
        <label className="text-sm font-medium text-gray-700">Your Industry</label>
        <div className="relative">
          <select
            className="input pr-8 appearance-none capitalize"
            value={sector}
            onChange={e => { setSector(e.target.value); saveSector(e.target.value); }}
          >
            {SECTORS.map(s => <option key={s} value={s}>{s.replace("_", " & ")}</option>)}
          </select>
          <ChevronDown className="absolute right-2 top-2.5 h-4 w-4 text-gray-400 pointer-events-none" />
        </div>
      </div>

      {loading ? (
        <div className="space-y-3">
          {[1,2,3,4].map(i => <div key={i} className="animate-pulse h-24 rounded-xl bg-gray-100" />)}
        </div>
      ) : data ? (
        <>
          <div className="space-y-3">
            {data.metrics.map(m => (
              <div key={m.metric} className="rounded-xl border border-gray-200 bg-white p-5">
                <div className="flex items-start justify-between mb-3">
                  <p className="text-sm font-medium text-gray-900">{m.label}</p>
                  <DeltaBadge org={m.org_value} industry={m.industry_value} higherIsBetter={m.higher_is_better} unit={m.unit} />
                </div>
                <PerformanceBar org={m.org_value} industry={m.industry_value} higherIsBetter={m.higher_is_better} />
                <div className="mt-3 grid grid-cols-2 gap-4 text-center">
                  <div>
                    <p className="text-xl font-bold text-gray-900">
                      {m.org_value != null ? `${m.org_value}${m.unit}` : "—"}
                    </p>
                    <p className="text-xs text-gray-500">Your company</p>
                  </div>
                  <div>
                    <p className="text-xl font-bold text-blue-600">
                      {m.industry_value != null ? `${m.industry_value}${m.unit}` : "—"}
                    </p>
                    <p className="text-xs text-gray-500">Industry avg</p>
                  </div>
                </div>
              </div>
            ))}
          </div>

          <p className="text-[11px] text-gray-400">
            Source: {data.source}. Benchmarks are indicative averages for the Nordic region.
            Your values are computed from your last 12 months of data in Varuflow.
          </p>
        </>
      ) : null}
    </div>
  );
}
