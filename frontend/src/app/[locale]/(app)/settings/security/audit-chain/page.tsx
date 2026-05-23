"use client";

import { useState, useEffect } from "react";
import { toast } from "sonner";
import { CheckCircle2, XCircle, Shield, Download, RefreshCw } from "lucide-react";

interface Entry {
  id: string; sequence_no?: number; action: string; actor_user_id?: string;
  target_type?: string; target_id?: string; ip_address?: string;
  previous_hash: string; row_hash: string; created_at: string; chained: boolean;
}
interface VerifyResult {
  ok: boolean; total_rows_checked: number; first_broken_id?: string;
  first_broken_seq?: number; error?: string; message: string;
}

export default function AuditChainPage() {
  const apiBase = process.env.NEXT_PUBLIC_API_URL!;
  const [result, setResult] = useState<VerifyResult | null>(null);
  const [entries, setEntries] = useState<Entry[]>([]);
  const [verifying, setVerifying] = useState(false);
  const [page, setPage] = useState(1);
  const LIMIT = 50;

  const fetch_ = (url: string, opts?: RequestInit) =>
    fetch(`${apiBase}${url}`, { credentials: "include", ...opts });

  async function verify() {
    setVerifying(true);
    try {
      const res = await fetch_("/api/compliance/audit-chain/verify");
      if (res.ok) setResult(await res.json());
      else toast.error("Verification request failed");
    } catch { toast.error("Network error"); }
    setVerifying(false);
  }

  async function loadEntries() {
    const res = await fetch_(`/api/compliance/audit-chain/entries?page=${page}&limit=${LIMIT}`);
    if (res.ok) setEntries((await res.json()).entries);
  }

  useEffect(() => { verify(); loadEntries(); }, []);
  useEffect(() => { loadEntries(); }, [page]);

  async function exportNDJSON() {
    const res = await fetch_("/api/compliance/audit-chain/export", { method: "POST" });
    if (!res.ok) { toast.error("Export failed"); return; }
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url; a.download = "audit_log.ndjson"; a.click();
    URL.revokeObjectURL(url);
    toast.success("Audit log exported");
  }

  function truncate(h: string) { return h === "0".repeat(64) ? "genesis" : `${h.slice(0, 12)}…`; }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-gray-900">SOC 2 Audit Chain</h1>
          <p className="mt-1 text-sm text-gray-500">
            Tamper-evident SHA-256 hash chain. Each audit row links to its predecessor — any tampering breaks the chain.
          </p>
        </div>
        <div className="flex gap-2">
          <button onClick={verify} disabled={verifying} className="btn-secondary flex items-center gap-1.5">
            <RefreshCw className={`h-3.5 w-3.5 ${verifying ? "animate-spin" : ""}`} />
            {verifying ? "Verifying…" : "Re-verify"}
          </button>
          <button onClick={exportNDJSON} className="btn-primary flex items-center gap-1.5">
            <Download className="h-3.5 w-3.5" /> Export NDJSON
          </button>
        </div>
      </div>

      {/* Chain integrity banner */}
      {result && (
        <div className={`rounded-xl p-5 flex items-start gap-4 ${result.ok ? "bg-green-50 border border-green-200" : "bg-red-50 border border-red-300"}`}>
          {result.ok
            ? <CheckCircle2 className="h-6 w-6 text-green-600 flex-shrink-0 mt-0.5" />
            : <XCircle className="h-6 w-6 text-red-500 flex-shrink-0 mt-0.5" />
          }
          <div>
            <p className={`font-semibold text-base ${result.ok ? "text-green-900" : "text-red-900"}`}>
              {result.ok ? "Chain Intact" : "Chain Violation Detected"}
            </p>
            <p className="text-sm mt-0.5" style={{ color: result.ok ? "#166534" : "#7f1d1d" }}>
              {result.message}
            </p>
            {!result.ok && result.first_broken_id && (
              <p className="text-xs text-red-600 mt-1">
                First broken row ID: <code>{result.first_broken_id}</code>
              </p>
            )}
          </div>
          <div className="ml-auto text-right">
            <p className="text-2xl font-bold text-gray-900">{result.total_rows_checked.toLocaleString()}</p>
            <p className="text-xs text-gray-500">rows checked</p>
          </div>
        </div>
      )}

      {/* What this means */}
      <div className="rounded-xl border border-gray-200 bg-white p-5 text-sm text-gray-600 space-y-2">
        <div className="flex items-center gap-2 font-medium text-gray-800">
          <Shield className="h-4 w-4 text-blue-600" /> How hash chaining works
        </div>
        <p>Each audit entry stores: <code className="bg-gray-100 px-1 rounded">row_hash = SHA-256(previous_hash ‖ action ‖ actor ‖ org ‖ timestamp ‖ payload)</code></p>
        <p>The first entry uses a genesis hash of 64 zeros. Any row deletion, modification, or insertion between existing rows will produce a hash mismatch detectable by the verifier above.</p>
        <p className="text-gray-400 text-xs">Export the NDJSON to give to an external auditor who can independently re-compute every hash off your systems.</p>
      </div>

      {/* Log entries */}
      <div>
        <h2 className="text-sm font-semibold text-gray-500 uppercase tracking-wider mb-3">Recent Entries</h2>
        <div className="overflow-x-auto rounded-xl border border-gray-200">
          <table className="w-full text-xs">
            <thead className="bg-gray-50 border-b border-gray-200">
              <tr>
                <th className="text-left px-4 py-2 font-medium text-gray-500">Seq</th>
                <th className="text-left px-4 py-2 font-medium text-gray-500">Timestamp</th>
                <th className="text-left px-4 py-2 font-medium text-gray-500">Action</th>
                <th className="text-left px-4 py-2 font-medium text-gray-500">Target</th>
                <th className="text-left px-4 py-2 font-medium text-gray-500">IP</th>
                <th className="text-left px-4 py-2 font-medium text-gray-500">Prev Hash</th>
                <th className="text-left px-4 py-2 font-medium text-gray-500">Row Hash</th>
                <th className="text-center px-4 py-2 font-medium text-gray-500">Chained</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {entries.map(e => (
                <tr key={e.id} className="hover:bg-gray-50">
                  <td className="px-4 py-2 text-gray-400">{e.sequence_no ?? "—"}</td>
                  <td className="px-4 py-2 text-gray-600 whitespace-nowrap">{new Date(e.created_at).toLocaleString()}</td>
                  <td className="px-4 py-2 font-mono text-blue-700">{e.action}</td>
                  <td className="px-4 py-2 text-gray-500">{e.target_type ?? ""}{e.target_id ? ` ${e.target_id.slice(0, 8)}…` : ""}</td>
                  <td className="px-4 py-2 text-gray-400">{e.ip_address ?? "—"}</td>
                  <td className="px-4 py-2 font-mono text-gray-400">{truncate(e.previous_hash)}</td>
                  <td className="px-4 py-2 font-mono text-gray-700 font-medium">{truncate(e.row_hash)}</td>
                  <td className="px-4 py-2 text-center">
                    {e.chained ? <CheckCircle2 className="h-3.5 w-3.5 text-green-500 inline" /> : <span className="text-gray-300">—</span>}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div className="flex justify-between mt-3">
          <button onClick={() => setPage(p => Math.max(1, p - 1))} disabled={page === 1} className="btn-secondary text-xs">← Previous</button>
          <span className="text-xs text-gray-400 self-center">Page {page}</span>
          <button onClick={() => setPage(p => p + 1)} disabled={entries.length < LIMIT} className="btn-secondary text-xs">Next →</button>
        </div>
      </div>
    </div>
  );
}
