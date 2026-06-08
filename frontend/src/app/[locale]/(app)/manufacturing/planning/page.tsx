"use client";

import { useEffect, useState } from "react";
import { CalendarCheck2, Loader2, CheckCircle, XCircle, ArrowRight } from "lucide-react";
import { useRouter } from "next/navigation";
import { useLocale } from "next-intl";
import { toast } from "sonner";
import { api } from "@/lib/api-client";
import { isPlanGateError, PlanGateBlock } from "@/components/ui/PlanGate";

interface Bom {
  id: string;
  name: string;
  product_id: string;
}

interface Warehouse {
  id: string;
  name: string;
}

interface Shortfall {
  product_id: string;
  name: string;
  sku: string;
  needed: number;
  available: number;
  short: number;
  ok: boolean;
}

interface FeasibilityResult {
  feasible: boolean;
  shortfalls: Shortfall[];
  bom_id: string;
  qty: number;
}

export default function PlanningPage() {
  const router = useRouter();
  const locale = useLocale();
  const [boms, setBoms] = useState<Bom[]>([]);
  const [warehouses, setWarehouses] = useState<Warehouse[]>([]);
  const [form, setForm] = useState({ bom_id: "", qty: 1, warehouse_id: "" });
  const [result, setResult] = useState<FeasibilityResult | null>(null);
  const [checking, setChecking] = useState(false);
  const [creating, setCreating] = useState(false);
  const [planBlocked, setPlanBlocked] = useState<{ module: string; currentPlan: string } | null>(null);

  useEffect(() => {
    Promise.all([
      api.get("/api/manufacturing/boms"),
      api.get("/api/inventory/warehouses").catch(() => []),
    ]).then(([bomList, whList]) => {
      setBoms(bomList);
      setWarehouses(whList);
    }).catch((err) => {
      if (isPlanGateError(err)) {
        setPlanBlocked({ module: (err as any).module ?? "manufacturing", currentPlan: (err as any).currentPlan ?? "FREE" });
        return;
      }
      toast.error("Failed to load data");
    });
  }, []);

  async function check() {
    if (!form.bom_id || !form.warehouse_id) { toast.error("Select BOM and warehouse"); return; }
    setChecking(true);
    setResult(null);
    try {
      const res = await api.post("/api/manufacturing/planning/check", form);
      setResult(res);
    } catch {
      toast.error("Feasibility check failed");
    } finally {
      setChecking(false);
    }
  }

  async function createWorkOrder() {
    if (!result) return;
    setCreating(true);
    try {
      const wo = await api.post("/api/manufacturing/work-orders", {
        bom_id: result.bom_id,
        warehouse_id: form.warehouse_id,
        planned_qty: result.qty,
      });
      toast.success(`Created ${wo.order_number}`);
      router.push(`/${locale}/manufacturing`);
    } catch {
      toast.error("Failed to create work order");
    } finally {
      setCreating(false);
    }
  }

  if (planBlocked) return <PlanGateBlock module={planBlocked.module} currentPlan={planBlocked.currentPlan} featureName="Production Planning" />;

  return (
    <div className="p-6 max-w-3xl mx-auto">
      <div className="flex items-center gap-2 mb-6">
        <CalendarCheck2 className="w-6 h-6" />
        <h1 className="text-2xl font-semibold">Production Planning</h1>
      </div>

      <div className="border rounded-lg p-4 mb-6">
        <h3 className="text-sm font-semibold mb-3">Feasibility Check</h3>
        <div className="grid grid-cols-3 gap-3 mb-4">
          <div>
            <label className="text-xs font-medium text-muted-foreground">BOM</label>
            <select className="border rounded px-2 py-1.5 text-sm w-full mt-1" value={form.bom_id} onChange={(e) => { setForm((f) => ({ ...f, bom_id: e.target.value })); setResult(null); }}>
              <option value="">— select —</option>
              {boms.map((b) => <option key={b.id} value={b.id}>{b.name}</option>)}
            </select>
          </div>
          <div>
            <label className="text-xs font-medium text-muted-foreground">Target Qty</label>
            <input type="number" min={1} className="border rounded px-2 py-1.5 text-sm w-full mt-1" value={form.qty} onChange={(e) => { setForm((f) => ({ ...f, qty: parseInt(e.target.value) || 1 })); setResult(null); }} />
          </div>
          <div>
            <label className="text-xs font-medium text-muted-foreground">Warehouse</label>
            <select className="border rounded px-2 py-1.5 text-sm w-full mt-1" value={form.warehouse_id} onChange={(e) => { setForm((f) => ({ ...f, warehouse_id: e.target.value })); setResult(null); }}>
              <option value="">— select —</option>
              {warehouses.map((w) => <option key={w.id} value={w.id}>{w.name}</option>)}
            </select>
          </div>
        </div>
        <button onClick={check} disabled={checking} className="flex items-center gap-2 bg-primary text-primary-foreground rounded px-4 py-2 text-sm disabled:opacity-50">
          {checking && <Loader2 className="w-4 h-4 animate-spin" />} Check Feasibility
        </button>
      </div>

      {result && (
        <div className="border rounded-lg overflow-hidden">
          <div className={`px-4 py-3 flex items-center justify-between ${result.feasible ? "bg-green-50 border-b border-green-200" : "bg-red-50 border-b border-red-200"}`}>
            <div className="flex items-center gap-2">
              {result.feasible
                ? <CheckCircle className="w-5 h-5 text-green-600" />
                : <XCircle className="w-5 h-5 text-red-600" />}
              <span className="font-semibold text-sm">
                {result.feasible ? "Feasible — all components in stock" : "Not feasible — stock shortage"}
              </span>
            </div>
            {result.feasible && (
              <button onClick={createWorkOrder} disabled={creating} className="flex items-center gap-1.5 bg-green-600 text-white rounded px-3 py-1.5 text-sm disabled:opacity-50">
                {creating && <Loader2 className="w-3 h-3 animate-spin" />}
                Create Work Order <ArrowRight className="w-3 h-3" />
              </button>
            )}
          </div>
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b text-left text-muted-foreground bg-muted/30">
                <th className="py-2 px-4 font-medium">Component</th>
                <th className="py-2 px-4 font-medium">SKU</th>
                <th className="py-2 px-4 font-medium text-right">Needed</th>
                <th className="py-2 px-4 font-medium text-right">In Stock</th>
                <th className="py-2 px-4 font-medium text-right">Status</th>
              </tr>
            </thead>
            <tbody className="divide-y">
              {result.shortfalls.map((s) => (
                <tr key={s.product_id} className={!s.ok ? "bg-red-50" : ""}>
                  <td className="py-2 px-4">{s.name}</td>
                  <td className="py-2 px-4 text-muted-foreground">{s.sku}</td>
                  <td className="py-2 px-4 text-right font-medium">{s.needed}</td>
                  <td className="py-2 px-4 text-right">{s.available}</td>
                  <td className="py-2 px-4 text-right">
                    {s.ok
                      ? <span className="text-green-600 font-medium">✓ OK</span>
                      : <span className="text-red-600 font-medium">−{s.short} short</span>}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
