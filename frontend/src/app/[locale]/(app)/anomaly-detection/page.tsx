"use client";

import { api } from "@/lib/api-client";
import { useEffect, useState } from "react";
import { useRouter, useParams } from "next/navigation";
import { toast } from "sonner";
import {
  AlertTriangle, ShieldCheck, RefreshCw, ChevronDown, ChevronUp,
  Search, X, Check, Flag, Clock, TrendingDown
} from "lucide-react";

interface Finding {
  id: string;
  anomaly_type: string;
  severity: string;
  title: string;
  detail?: string;
  context?: Record<string, any>;
  status: string;
  detected_at: string;
  resolved_at?: string;
}

const TYPE_LABELS: Record<string, string> = {
  duplicate_invoice:        "Duplicate Invoice",
  duplicate_payment:        "Duplicate Payment",
  unusual_expense:          "Unusual Expense",
  supplier_price_spike:     "Price Spike",
  payment_behavior_change:  "Payment Behaviour Change",
  inventory_discrepancy:    "Inventory Discrepancy",
};

const SEVERITY_STYLE: Record<string, string> = {
  high:   "bg-red-100 text-red-700",
  medium: "bg-amber-100 text-amber-700",
  low:    "bg-blue-100 text-blue-700",
};

const STATUS_STYLE: Record<string, string> = {
  open:       "bg-orange-100 text-orange-700",
  dismissed:  "bg-gray-100 text-gray-500",
  escalated:  "bg-purple-100 text-purple-700",
};

export default function AnomalyDetectionPage() {
  const router = useRouter();
  const params = useParams();
  const locale = params.locale as string;

  const [findings, setFindings] = useState<Finding[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [scanning, setScanning] = useState(false);
  const [expanded, setExpanded] = useState<string | null>(null);
  const [statusFilter, setStatusFilter] = useState<string>("open");
  const [typeFilter, setTypeFilter] = useState<string>("");
  const [severityFilter, setSeverityFilter] = useState<string>("");
  const [resolving, setResolving] = useState<string | null>(null);
  const [summary, setSummary] = useState<Array<{status: string; severity: string; count: number}>>([]);

  async function load() {
    try {
      const params: string[] = [];
      if (statusFilter) params.push(`status=${statusFilter}`);
      if (typeFilter) params.push(`anomaly_type=${typeFilter}`);
      if (severityFilter) params.push(`severity=${severityFilter}`);
      const qs = params.length ? `?${params.join("&")}` : "";

      const [fData, sData] = await Promise.all([
        api.get(`/api/anomalies${qs}`),
        api.get("/api/anomalies/summary"),
      ]);
      setFindings(fData.items ?? fData);
      setTotal(fData.total ?? 0);
      setSummary(sData.breakdown ?? []);
    } catch (err: any) {
      if (err?.status === 401) router.push(`/${locale}/auth/login`);
      else toast.error("Failed to load anomalies");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { load(); }, [statusFilter, typeFilter, severityFilter]);

  async function runScan() {
    setScanning(true);
    try {
      const result = await api.post("/api/anomalies/scan", {});
      toast.success(`Scan complete — ${result.new_findings} new finding${result.new_findings !== 1 ? "s" : ""} detected`);
      load();
    } catch {
      toast.error("Scan failed");
    } finally {
      setScanning(false);
    }
  }

  async function resolve(id: string, status: "dismissed" | "escalated") {
    setResolving(id);
    try {
      await api.patch(`/api/anomalies/${id}`, { status });
      toast.success(status === "dismissed" ? "Finding dismissed" : "Finding escalated");
      load();
    } catch {
      toast.error("Failed");
    } finally {
      setResolving(null);
    }
  }

  const openCount = summary.filter(s => s.status === "open").reduce((a, b) => a + b.count, 0);
  const highCount = summary.filter(s => s.severity === "high" && s.status === "open").reduce((a, b) => a + b.count, 0);

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Anomaly Detection</h1>
          <p className="text-sm text-muted-foreground mt-1">
            Automated scanner for duplicate transactions, price spikes, and unusual patterns
          </p>
        </div>
        <button
          className="btn-primary flex items-center gap-2"
          onClick={runScan}
          disabled={scanning}
        >
          {scanning ? <RefreshCw className="h-4 w-4 animate-spin" /> : <Search className="h-4 w-4" />}
          {scanning ? "Scanning…" : "Run Scan"}
        </button>
      </div>

      {/* Summary cards */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
        <div className="rounded-2xl border bg-card p-4">
          <p className="text-xs text-muted-foreground">Open Findings</p>
          <p className={`text-2xl font-bold mt-1 ${openCount > 0 ? "text-amber-600" : "text-green-600"}`}>{openCount}</p>
        </div>
        <div className="rounded-2xl border bg-card p-4">
          <p className="text-xs text-muted-foreground">High Severity</p>
          <p className={`text-2xl font-bold mt-1 ${highCount > 0 ? "text-red-600" : ""}`}>{highCount}</p>
        </div>
        <div className="rounded-2xl border bg-card p-4">
          <p className="text-xs text-muted-foreground">Dismissed</p>
          <p className="text-2xl font-bold mt-1">{summary.filter(s => s.status === "dismissed").reduce((a, b) => a + b.count, 0)}</p>
        </div>
        <div className="rounded-2xl border bg-card p-4">
          <p className="text-xs text-muted-foreground">Escalated</p>
          <p className="text-2xl font-bold mt-1 text-purple-600">{summary.filter(s => s.status === "escalated").reduce((a, b) => a + b.count, 0)}</p>
        </div>
      </div>

      {/* Filters */}
      <div className="flex flex-wrap gap-3">
        <select className="input text-sm py-1.5 h-9" value={statusFilter} onChange={e => setStatusFilter(e.target.value)}>
          <option value="">All statuses</option>
          <option value="open">Open</option>
          <option value="dismissed">Dismissed</option>
          <option value="escalated">Escalated</option>
        </select>
        <select className="input text-sm py-1.5 h-9" value={severityFilter} onChange={e => setSeverityFilter(e.target.value)}>
          <option value="">All severities</option>
          <option value="high">High</option>
          <option value="medium">Medium</option>
          <option value="low">Low</option>
        </select>
        <select className="input text-sm py-1.5 h-9" value={typeFilter} onChange={e => setTypeFilter(e.target.value)}>
          <option value="">All types</option>
          {Object.entries(TYPE_LABELS).map(([v, l]) => <option key={v} value={v}>{l}</option>)}
        </select>
        {(statusFilter || typeFilter || severityFilter) && (
          <button className="text-xs text-muted-foreground hover:text-foreground flex items-center gap-1" onClick={() => { setStatusFilter(""); setTypeFilter(""); setSeverityFilter(""); }}>
            <X className="h-3 w-3" /> Clear
          </button>
        )}
      </div>

      {/* Findings list */}
      {loading ? (
        <div className="flex justify-center py-16">
          <RefreshCw className="h-6 w-6 animate-spin text-muted-foreground" />
        </div>
      ) : findings.length === 0 ? (
        <div className="rounded-2xl border bg-card flex flex-col items-center justify-center py-20 text-center">
          <ShieldCheck className="h-12 w-12 text-green-500 mb-4" />
          <p className="font-medium">No anomalies found</p>
          <p className="text-sm text-muted-foreground mt-1">Run a scan to check for unusual patterns</p>
        </div>
      ) : (
        <div className="space-y-2">
          {findings.map(f => (
            <div key={f.id} className="rounded-2xl border bg-card overflow-hidden">
              <div
                className="flex items-center gap-3 p-4 cursor-pointer hover:bg-muted/30 transition-colors"
                onClick={() => setExpanded(expanded === f.id ? null : f.id)}
              >
                <span className={`text-xs font-semibold px-2 py-0.5 rounded-full ${SEVERITY_STYLE[f.severity] ?? ""}`}>
                  {f.severity}
                </span>
                <span className="text-xs text-muted-foreground px-2 py-0.5 rounded-full border">
                  {TYPE_LABELS[f.anomaly_type] ?? f.anomaly_type}
                </span>
                <p className="flex-1 text-sm font-medium truncate">{f.title}</p>
                <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${STATUS_STYLE[f.status] ?? ""}`}>
                  {f.status}
                </span>
                <span className="text-xs text-muted-foreground">
                  {new Date(f.detected_at).toLocaleDateString("sv-SE")}
                </span>
                {expanded === f.id ? <ChevronUp className="h-4 w-4 text-muted-foreground" /> : <ChevronDown className="h-4 w-4 text-muted-foreground" />}
              </div>

              {expanded === f.id && (
                <div className="border-t px-4 pb-4 pt-3 space-y-3">
                  {f.detail && <p className="text-sm text-muted-foreground">{f.detail}</p>}
                  {f.context && (
                    <div className="bg-muted/40 rounded-xl p-3 space-y-1">
                      {Object.entries(f.context).map(([k, v]) => (
                        <div key={k} className="flex gap-2 text-xs">
                          <span className="text-muted-foreground font-medium">{k}:</span>
                          <span className="font-mono">{Array.isArray(v) ? v.join(", ") : String(v)}</span>
                        </div>
                      ))}
                    </div>
                  )}
                  {f.status === "open" && (
                    <div className="flex gap-2">
                      <button
                        className="btn-secondary text-xs flex items-center gap-1.5"
                        onClick={() => resolve(f.id, "dismissed")}
                        disabled={resolving === f.id}
                      >
                        {resolving === f.id ? <RefreshCw className="h-3 w-3 animate-spin" /> : <Check className="h-3 w-3" />}
                        Dismiss
                      </button>
                      <button
                        className="btn-primary text-xs flex items-center gap-1.5"
                        onClick={() => resolve(f.id, "escalated")}
                        disabled={resolving === f.id}
                      >
                        <Flag className="h-3 w-3" /> Escalate
                      </button>
                    </div>
                  )}
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
