"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api-client";
import { RefreshCw, CreditCard, Info } from "lucide-react";
import { Button } from "@/components/ui/button";
import { toast } from "sonner";

interface WalletPass {
  id: string;
  customer_id: string;
  platform: "apple" | "google";
  serial_number: string;
  points_balance: number;
  tier: string;
  last_synced_at: string | null;
  revoked: boolean;
}

const PLATFORM_BADGE: Record<string, string> = {
  apple: "bg-gray-100 text-gray-700",
  google: "bg-blue-100 text-blue-700",
};

type PlatformFilter = "all" | "apple" | "google";

export default function WalletPassesPage() {
  const [passes, setPasses] = useState<WalletPass[]>([]);
  const [loading, setLoading] = useState(true);
  const [platformFilter, setPlatformFilter] = useState<PlatformFilter>("all");
  const [actionLoading, setActionLoading] = useState<string | null>(null);
  const [showIssueForm, setShowIssueForm] = useState(false);
  const [issueForm, setIssueForm] = useState({ customer_id: "", platform: "apple", tier: "" });

  async function load() {
    setLoading(true);
    try {
      const data = await api.get<WalletPass[]>("/api/wallet");
      setPasses(data);
    } catch {
      toast.error("Failed to load wallet passes");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { load(); }, []);  // eslint-disable-line react-hooks/exhaustive-deps

  async function syncPass(id: string) {
    setActionLoading(id + "_sync");
    try {
      await api.post(`/api/wallet/${id}/sync`, {});
      toast.success("Pass synced");
      await load();
    } catch {
      toast.error("Something went wrong");
    } finally {
      setActionLoading(null);
    }
  }

  async function revokePass(id: string) {
    setActionLoading(id + "_revoke");
    try {
      await api.post(`/api/wallet/${id}/revoke`, {});
      toast.success("Pass revoked");
      await load();
    } catch {
      toast.error("Something went wrong");
    } finally {
      setActionLoading(null);
    }
  }

  async function issuePass() {
    if (!issueForm.customer_id.trim()) { toast.error("Customer ID is required"); return; }
    setActionLoading("issue");
    try {
      await api.post("/api/wallet", {
        customer_id: issueForm.customer_id,
        platform: issueForm.platform,
        tier: issueForm.tier || null,
      });
      toast.success("Wallet pass issued");
      setShowIssueForm(false);
      setIssueForm({ customer_id: "", platform: "apple", tier: "" });
      await load();
    } catch {
      toast.error("Something went wrong");
    } finally {
      setActionLoading(null);
    }
  }

  const filtered = passes.filter((p) => platformFilter === "all" || p.platform === platformFilter);
  const inputCls = "block w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-[#1a2332]";

  return (
    <div className="mx-auto max-w-4xl space-y-6 p-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-gray-900">Wallet Passes</h1>
          <p className="text-sm text-muted-foreground mt-0.5">Issue and manage Apple and Google Wallet loyalty passes.</p>
        </div>
        <Button onClick={() => setShowIssueForm((s) => !s)} className="bg-[#1a2332] hover:bg-[#2a3342] text-white gap-2">
          <CreditCard className="h-4 w-4" /> Issue Pass
        </Button>
      </div>

      {/* Info banner */}
      <div className="flex items-start gap-2.5 rounded-lg bg-blue-50 border border-blue-200 px-4 py-3">
        <Info className="h-4 w-4 text-blue-600 flex-shrink-0 mt-0.5" />
        <p className="text-xs text-blue-800">
          Passes are linked to the customer&apos;s active loyalty account. Points sync automatically on each daily sync.
        </p>
      </div>

      {/* Filter */}
      <div className="flex gap-1 border-b">
        {(["all", "apple", "google"] as PlatformFilter[]).map((f) => (
          <button key={f} type="button" onClick={() => setPlatformFilter(f)}
            className={`px-4 py-2.5 text-sm font-medium border-b-2 capitalize transition-colors ${
              platformFilter === f
                ? "border-[#1a2332] text-[#1a2332]"
                : "border-transparent text-muted-foreground hover:text-gray-700"
            }`}>
            {f === "all" ? "All" : f.charAt(0).toUpperCase() + f.slice(1)}
          </button>
        ))}
      </div>

      {/* Issue form */}
      {showIssueForm && (
        <div className="rounded-xl border border-[#1a2332]/20 bg-white p-5 shadow-sm space-y-3">
          <h3 className="text-sm font-semibold text-gray-900">Issue Wallet Pass</h3>
          <div className="grid grid-cols-3 gap-3">
            <div className="col-span-2 space-y-1">
              <label className="text-xs font-medium text-gray-700">Customer ID *</label>
              <input value={issueForm.customer_id}
                onChange={(e) => setIssueForm((f) => ({ ...f, customer_id: e.target.value }))}
                placeholder="UUID" className={inputCls} />
            </div>
            <div className="space-y-1">
              <label className="text-xs font-medium text-gray-700">Platform *</label>
              <select value={issueForm.platform}
                onChange={(e) => setIssueForm((f) => ({ ...f, platform: e.target.value }))}
                className={inputCls}>
                <option value="apple">Apple</option>
                <option value="google">Google</option>
              </select>
            </div>
          </div>
          <div className="space-y-1">
            <label className="text-xs font-medium text-gray-700">Tier (optional)</label>
            <input value={issueForm.tier}
              onChange={(e) => setIssueForm((f) => ({ ...f, tier: e.target.value }))}
              placeholder="gold, silver, bronze…" className={inputCls} />
          </div>
          <div className="flex gap-2">
            <Button variant="outline" onClick={() => setShowIssueForm(false)}>Cancel</Button>
            <Button disabled={actionLoading === "issue"} onClick={issuePass}
              className="bg-[#1a2332] hover:bg-[#2a3342] text-white">
              {actionLoading === "issue" ? "Issuing…" : "Issue Pass"}
            </Button>
          </div>
        </div>
      )}

      {/* Table */}
      <div className="rounded-xl border bg-white shadow-sm">
        {loading ? (
          <div className="py-12 text-center">
            <RefreshCw className="h-6 w-6 animate-spin mx-auto text-muted-foreground" />
          </div>
        ) : filtered.length === 0 ? (
          <div className="py-12 text-center">
            <CreditCard className="h-10 w-10 text-muted-foreground mx-auto mb-3" />
            <p className="text-gray-600 font-medium">No wallet passes found</p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-gray-100 text-left">
                  <th className="px-5 py-3 text-xs font-medium text-muted-foreground">Customer</th>
                  <th className="px-4 py-3 text-xs font-medium text-muted-foreground">Platform</th>
                  <th className="px-4 py-3 text-xs font-medium text-muted-foreground">Serial</th>
                  <th className="px-4 py-3 text-xs font-medium text-muted-foreground">Points</th>
                  <th className="px-4 py-3 text-xs font-medium text-muted-foreground">Tier</th>
                  <th className="px-4 py-3 text-xs font-medium text-muted-foreground">Last Synced</th>
                  <th className="px-4 py-3 text-xs font-medium text-muted-foreground">Status</th>
                  <th className="px-4 py-3 text-xs font-medium text-muted-foreground">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {filtered.map((p) => (
                  <tr key={p.id} className="hover:bg-gray-50">
                    <td className="px-5 py-3 font-mono text-xs text-gray-700">{p.customer_id.slice(0, 8)}…</td>
                    <td className="px-4 py-3">
                      <span className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-medium ${PLATFORM_BADGE[p.platform] ?? "bg-gray-100 text-gray-700"}`}>
                        {p.platform === "apple" ? "Apple" : "Google"}
                      </span>
                    </td>
                    <td className="px-4 py-3 font-mono text-xs text-gray-600 truncate max-w-[120px]">{p.serial_number}</td>
                    <td className="px-4 py-3 text-sm font-medium text-gray-900">{p.points_balance.toLocaleString()}</td>
                    <td className="px-4 py-3">
                      {p.tier && (
                        <span className="inline-flex items-center rounded-full bg-purple-100 text-purple-700 px-2 py-0.5 text-xs capitalize">
                          {p.tier}
                        </span>
                      )}
                    </td>
                    <td className="px-4 py-3 text-xs text-muted-foreground">
                      {p.last_synced_at ? new Date(p.last_synced_at).toLocaleDateString() : "Never"}
                    </td>
                    <td className="px-4 py-3">
                      {p.revoked && (
                        <span className="inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-medium bg-red-100 text-red-700">
                          Revoked
                        </span>
                      )}
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-1.5">
                        <Button variant="outline" size="sm" disabled={!!actionLoading || p.revoked}
                          onClick={() => syncPass(p.id)}>
                          {actionLoading === p.id + "_sync" ? <RefreshCw className="h-3 w-3 animate-spin" /> : "Sync"}
                        </Button>
                        {!p.revoked && (
                          <Button variant="outline" size="sm" disabled={!!actionLoading}
                            onClick={() => revokePass(p.id)}
                            className="text-red-600 border-red-200 hover:bg-red-50">
                            {actionLoading === p.id + "_revoke" ? <RefreshCw className="h-3 w-3 animate-spin" /> : "Revoke"}
                          </Button>
                        )}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
