"use client";

import { useState, useEffect } from "react";
import { toast } from "sonner";
import { api } from "@/lib/api-client";
import { Package, Upload, CheckCircle2, History } from "lucide-react";
import styles from "./page.module.scss";

interface Agreement { id: string; franchisee_name: string; franchisee_org_id?: string; status: string }
interface PushLog { id: string; franchisee_org_id: string; pushed_count: number; created_count: number; updated_count: number; status: string; created_at: string }

export default function FranchiseCatalogPage() {
  const [agreements, setAgreements] = useState<Agreement[]>([]);
  const [pushes, setPushes] = useState<PushLog[]>([]);
  const [selectedFranchisee, setSelectedFranchisee] = useState("");
  const [pushing, setPushing] = useState(false);
  const [tab, setTab] = useState<"push" | "history">("push");

  async function load() {
    const [aRes, pRes] = await Promise.all([
      api.get<{agreements: Agreement[]}>("/api/franchise/agreements?status=active&limit=50").catch(() => null),
      api.get<{pushes: PushLog[]}>("/api/franchise/catalog/pushes?limit=30").catch(() => null),
    ]);
    if (aRes) setAgreements(aRes.agreements.filter((a: Agreement) => a.franchisee_org_id));
    if (pRes) setPushes(pRes.pushes ?? []);
  }

  useEffect(() => { load(); }, []);

  async function pushAll() {
    if (!selectedFranchisee) { toast.error("Select a franchisee"); return; }
    const agreement = agreements.find(a => a.franchisee_org_id === selectedFranchisee || a.id === selectedFranchisee);
    if (!agreement?.franchisee_org_id) { toast.error("Franchisee org not linked yet"); return; }

    setPushing(true);
    try {
      const data = await api.post<PushLog>("/api/franchise/catalog/push", { franchisee_org_id: agreement.franchisee_org_id });
      toast.success(`Pushed ${data.pushed_count} products — ${data.created_count} created, ${data.updated_count} updated`);
      await load();
      setTab("history");
    } catch (err: any) {
      toast.error(err?.message || "Push failed");
    } finally {
      setPushing(false);
    }
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold text-gray-900">Franchise Catalogue</h1>
        <p className="mt-1 text-sm text-gray-500">Push your master product catalogue to franchisee organisations.</p>
      </div>

      {/* Tabs */}
      <div className="flex gap-2 border-b border-gray-200">
        {(["push", "history"] as const).map(t => (
          <button key={t} onClick={() => setTab(t)}
            className={`px-4 py-2 text-sm font-medium capitalize border-b-2 transition-colors ${
              tab === t ? "border-blue-600 text-blue-600" : "border-transparent text-gray-500 hover:text-gray-700"
            }`}>
            {t === "push" ? "Push Catalogue" : "Push History"}
          </button>
        ))}
      </div>

      {tab === "push" && (
        <div className="max-w-md space-y-5">
          <div className="rounded-lg bg-blue-50 border border-blue-200 p-4 text-sm text-blue-800">
            Pushing the catalogue copies <strong>all your products</strong> (SKU, name, price, cost) to the selected franchisee's Varuflow org.
            Existing products with matching SKUs will be updated; new SKUs will be created with zero stock.
          </div>

          <div>
            <label className="text-xs font-medium text-gray-700 mb-1 block">Select Franchisee*</label>
            <select
              className="input w-full"
              value={selectedFranchisee}
              onChange={e => setSelectedFranchisee(e.target.value)}
            >
              <option value="">Select franchisee…</option>
              {agreements.map(a => (
                <option key={a.id} value={a.franchisee_org_id || a.id}>
                  {a.franchisee_name}
                  {!a.franchisee_org_id ? " (no org linked yet)" : ""}
                </option>
              ))}
            </select>
          </div>

          {agreements.length === 0 && (
            <p className="text-sm text-amber-600">
              No active franchisees with linked orgs. Activate a franchisee agreement and link their Varuflow org first.
            </p>
          )}

          <button
            onClick={pushAll}
            disabled={pushing || !selectedFranchisee}
            className="btn-primary flex items-center gap-2 w-full justify-center"
          >
            <Upload className="h-4 w-4" />
            {pushing ? "Pushing catalogue…" : "Push All Products"}
          </button>
        </div>
      )}

      {tab === "history" && (
        <div className="space-y-3">
          {pushes.length === 0 ? (
            <div className="rounded-xl border border-dashed border-gray-300 p-10 text-center text-sm text-gray-400">
              No catalogue pushes yet.
            </div>
          ) : (
            pushes.map(p => (
              <div key={p.id} className="flex items-center gap-4 rounded-xl border border-gray-200 bg-white p-4">
                <Package className="h-4 w-4 text-gray-400 flex-shrink-0" />
                <div className="flex-1">
                  <p className="text-sm font-medium text-gray-900">
                    {agreements.find(a => a.franchisee_org_id === p.franchisee_org_id)?.franchisee_name || p.franchisee_org_id.slice(0, 8)}
                  </p>
                  <p className="text-xs text-gray-500">
                    {p.pushed_count} products · {p.created_count} created · {p.updated_count} updated · {new Date(p.created_at).toLocaleString()}
                  </p>
                </div>
                <span className={styles[p.status === "completed" ? "statusCompleted" : "statusPending"]}>
                  {p.status}
                </span>
                {p.status === "completed" && <CheckCircle2 className="h-4 w-4 text-green-500 flex-shrink-0" />}
              </div>
            ))
          )}
        </div>
      )}
    </div>
  );
}
