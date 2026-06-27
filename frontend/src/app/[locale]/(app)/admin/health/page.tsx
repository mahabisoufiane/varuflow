"use client";

import { useEffect, useState, useCallback } from "react";
import { Search, AlertTriangle, XCircle, CheckCircle2, Download } from "lucide-react";
import { toast } from "sonner";
import apiClient from "@/lib/api-client";

interface HealthFactor {
  [key: string]: number | string | boolean | null;
}

interface OrgHealth {
  id: string;
  org_id: string;
  org_name: string;
  score: number;
  risk_level: "healthy" | "at_risk" | "critical";
  calculated_at: string;
  factors: HealthFactor;
}

interface HealthResponse {
  orgs: OrgHealth[];
  summary: {
    total: number;
    at_risk: number;
    critical: number;
  };
}

type RiskFilter = "all" | "healthy" | "at_risk" | "critical";

function ScoreBar({ score }: { score: number }) {
  const color =
    score >= 80
      ? "bg-green-500"
      : score >= 50
      ? "bg-yellow-500"
      : "bg-red-500";
  return (
    <div className="flex items-center gap-2">
      <div className="w-20 h-2 bg-slate-700 rounded-full overflow-hidden">
        <div
          className={`h-full rounded-full ${color} transition-all`}
          style={{ width: `${score}%` }}
        />
      </div>
      <span className="text-xs font-mono text-slate-300">{score}</span>
    </div>
  );
}

function RiskBadge({ level }: { level: OrgHealth["risk_level"] }) {
  const styles = {
    healthy: "bg-green-500/20 text-green-400 border-green-500/30",
    at_risk: "bg-yellow-500/20 text-yellow-400 border-yellow-500/30",
    critical: "bg-red-500/20 text-red-400 border-red-500/30",
  };
  const labels = { healthy: "Healthy", at_risk: "At Risk", critical: "Critical" };
  return (
    <span
      className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-semibold border ${styles[level]}`}
    >
      {labels[level]}
    </span>
  );
}

function exportCsv(orgs: OrgHealth[]) {
  const header = "org_id,score,risk_level,calculated_at";
  const rows = orgs.map(
    (o) =>
      `${o.org_id},${o.score},${o.risk_level},${o.calculated_at}`
  );
  const csv = [header, ...rows].join("\n");
  const blob = new Blob([csv], { type: "text/csv" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `varuflow-health-${new Date().toISOString().slice(0, 10)}.csv`;
  a.click();
  URL.revokeObjectURL(url);
}

export default function AdminHealthPage() {
  const [adminKey, setAdminKey] = useState<string>(() =>
    typeof window !== "undefined" ? sessionStorage.getItem("admin_key") ?? "" : ""
  );
  const [keyInput, setKeyInput] = useState("");
  const [data, setData] = useState<HealthResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [riskFilter, setRiskFilter] = useState<RiskFilter>("all");
  const [search, setSearch] = useState("");
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [intervening, setIntervening] = useState<string | null>(null);

  const fetchHealth = useCallback(
    async (key: string) => {
      setLoading(true);
      try {
        const result = await apiClient.get<HealthResponse>("/api/admin/health", {
          headers: { "X-Admin-Key": key },
        });
        setData(result);
      } catch (err: unknown) {
        const status = (err as { status?: number }).status;
        if (status === 401 || status === 403) {
          toast.error("Invalid admin key.");
          setAdminKey("");
          sessionStorage.removeItem("admin_key");
        } else {
          toast.error("Failed to load health data.");
        }
      } finally {
        setLoading(false);
      }
    },
    []
  );

  useEffect(() => {
    if (adminKey) {
      fetchHealth(adminKey);
    }
  }, [adminKey, fetchHealth]);

  function handleKeySubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!keyInput.trim()) return;
    sessionStorage.setItem("admin_key", keyInput.trim());
    setAdminKey(keyInput.trim());
  }

  async function handleIntervene(org: OrgHealth) {
    setIntervening(org.id);
    try {
      await apiClient.post(`/api/admin/health/${org.id}/intervene`, {}, {
        headers: { "X-Admin-Key": adminKey },
      });
      toast.success(`Intervention email sent to ${org.org_name}.`);
    } catch {
      toast.error("Failed to send intervention email.");
    } finally {
      setIntervening(null);
    }
  }

  // No key entered yet
  if (!adminKey) {
    return (
      <div className="min-h-screen bg-[#0f172a] flex items-center justify-center p-4">
        <div className="bg-slate-900 border border-slate-700 rounded-xl p-8 w-full max-w-sm">
          <h1 className="text-lg font-semibold text-slate-100 mb-1">Admin Health Dashboard</h1>
          <p className="text-sm text-slate-400 mb-6">Enter your admin key to continue.</p>
          <form onSubmit={handleKeySubmit} className="space-y-4">
            <input
              type="password"
              value={keyInput}
              onChange={(e) => setKeyInput(e.target.value)}
              placeholder="Admin key"
              className="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-sm text-slate-200 placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-indigo-500"
              autoFocus
            />
            <button
              type="submit"
              className="w-full py-2 bg-indigo-600 hover:bg-indigo-500 text-white text-sm font-semibold rounded-lg transition-colors"
            >
              Enter admin key
            </button>
          </form>
        </div>
      </div>
    );
  }

  const orgs = data?.orgs ?? [];

  const filtered = orgs
    .filter((o) => riskFilter === "all" || o.risk_level === riskFilter)
    .filter((o) =>
      search ? o.org_name.toLowerCase().includes(search.toLowerCase()) : true
    )
    .sort((a, b) => a.score - b.score); // worst first

  const riskTabs: { label: string; value: RiskFilter; icon?: React.ReactNode }[] = [
    { label: "All", value: "all" },
    { label: "Healthy", value: "healthy", icon: <CheckCircle2 size={13} className="text-green-400" /> },
    { label: "At Risk", value: "at_risk", icon: <AlertTriangle size={13} className="text-yellow-400" /> },
    { label: "Critical", value: "critical", icon: <XCircle size={13} className="text-red-400" /> },
  ];

  return (
    <div className="min-h-screen bg-[#0f172a] p-6">
      <div className="max-w-6xl mx-auto">
        {/* Header */}
        <div className="flex items-center justify-between mb-6">
          <div>
            <h1 className="text-xl font-bold text-slate-100">Subscription Health</h1>
            <p className="text-sm text-slate-400 mt-0.5">Organisation health scores &amp; risk levels</p>
          </div>
          <div className="flex gap-2">
            <button
              onClick={() => fetchHealth(adminKey)}
              disabled={loading}
              className="px-3 py-1.5 text-xs font-semibold rounded-lg bg-slate-800 border border-slate-700 text-slate-300 hover:bg-slate-700 transition-colors disabled:opacity-50"
            >
              {loading ? "Refreshing…" : "Refresh"}
            </button>
            <button
              onClick={() => exportCsv(filtered)}
              disabled={filtered.length === 0}
              className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold rounded-lg bg-indigo-600 text-white hover:bg-indigo-500 transition-colors disabled:opacity-40"
            >
              <Download size={13} />
              Export CSV
            </button>
          </div>
        </div>

        {/* Summary tiles */}
        {data && (
          <div className="grid grid-cols-3 gap-4 mb-6">
            <div className="bg-slate-900 border border-slate-700 rounded-xl p-4">
              <p className="text-xs text-slate-400 mb-1">Total orgs</p>
              <p className="text-2xl font-bold text-slate-100">{data.summary.total}</p>
            </div>
            <div className="bg-slate-900 border border-yellow-500/20 rounded-xl p-4">
              <p className="text-xs text-yellow-400 mb-1">At Risk</p>
              <p className="text-2xl font-bold text-yellow-400">{data.summary.at_risk}</p>
            </div>
            <div className="bg-slate-900 border border-red-500/20 rounded-xl p-4">
              <p className="text-xs text-red-400 mb-1">Critical</p>
              <p className="text-2xl font-bold text-red-400">{data.summary.critical}</p>
            </div>
          </div>
        )}

        {/* Filter bar */}
        <div className="flex flex-col sm:flex-row gap-3 mb-4">
          <div className="flex gap-1 bg-slate-900 border border-slate-700 rounded-lg p-1">
            {riskTabs.map((tab) => (
              <button
                key={tab.value}
                onClick={() => setRiskFilter(tab.value)}
                className={`flex items-center gap-1.5 px-3 py-1.5 rounded text-xs font-semibold transition-colors ${
                  riskFilter === tab.value
                    ? "bg-indigo-600 text-white"
                    : "text-slate-400 hover:text-slate-200"
                }`}
              >
                {tab.icon}
                {tab.label}
              </button>
            ))}
          </div>
          <div className="relative flex-1">
            <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-500" />
            <input
              type="text"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search organisation…"
              className="w-full pl-8 pr-3 py-2 bg-slate-900 border border-slate-700 rounded-lg text-sm text-slate-200 placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-indigo-500"
            />
          </div>
        </div>

        {/* Table */}
        {loading ? (
          <div className="text-center py-16 text-slate-500 text-sm">Loading health data…</div>
        ) : filtered.length === 0 ? (
          <div className="text-center py-16 text-slate-500 text-sm">No organisations match the current filters.</div>
        ) : (
          <div className="bg-slate-900 border border-slate-700 rounded-xl overflow-hidden">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-slate-700">
                  <th className="text-left px-4 py-3 text-xs font-semibold text-slate-400 uppercase tracking-wider">Org</th>
                  <th className="text-left px-4 py-3 text-xs font-semibold text-slate-400 uppercase tracking-wider">Score</th>
                  <th className="text-left px-4 py-3 text-xs font-semibold text-slate-400 uppercase tracking-wider">Risk</th>
                  <th className="text-left px-4 py-3 text-xs font-semibold text-slate-400 uppercase tracking-wider">Calculated</th>
                  <th className="text-right px-4 py-3 text-xs font-semibold text-slate-400 uppercase tracking-wider">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800">
                {filtered.map((org) => (
                  <>
                    <tr
                      key={org.id}
                      className="hover:bg-slate-800/50 cursor-pointer transition-colors"
                      onClick={() => setExpandedId(expandedId === org.id ? null : org.id)}
                    >
                      <td className="px-4 py-3">
                        <p className="font-medium text-slate-200">{org.org_name}</p>
                        <p className="text-xs text-slate-500 font-mono">{org.org_id}</p>
                      </td>
                      <td className="px-4 py-3">
                        <ScoreBar score={org.score} />
                      </td>
                      <td className="px-4 py-3">
                        <RiskBadge level={org.risk_level} />
                      </td>
                      <td className="px-4 py-3 text-xs text-slate-400">
                        {new Date(org.calculated_at).toLocaleDateString()}
                      </td>
                      <td className="px-4 py-3 text-right">
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            handleIntervene(org);
                          }}
                          disabled={intervening === org.id}
                          className="px-2.5 py-1 text-xs font-semibold rounded bg-indigo-600/20 text-indigo-400 border border-indigo-500/30 hover:bg-indigo-600/40 transition-colors disabled:opacity-50"
                        >
                          {intervening === org.id ? "Sending…" : "Send email"}
                        </button>
                      </td>
                    </tr>
                    {expandedId === org.id && (
                      <tr key={`${org.id}-expand`} className="bg-slate-800/40">
                        <td colSpan={5} className="px-6 py-4">
                          <p className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2">
                            Health factors
                          </p>
                          <table className="text-xs w-full max-w-lg">
                            <thead>
                              <tr>
                                <th className="text-left pb-1 text-slate-500 font-medium">Factor</th>
                                <th className="text-right pb-1 text-slate-500 font-medium">Value</th>
                              </tr>
                            </thead>
                            <tbody className="divide-y divide-slate-700/50">
                              {Object.entries(org.factors).map(([k, v]) => (
                                <tr key={k}>
                                  <td className="py-1 text-slate-400">{k}</td>
                                  <td className="py-1 text-right font-mono text-slate-300">
                                    {String(v)}
                                  </td>
                                </tr>
                              ))}
                            </tbody>
                          </table>
                        </td>
                      </tr>
                    )}
                  </>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
