"use client";

import { api } from "@/lib/api-client";
import { useEffect, useState } from "react";
import { useRouter, useParams } from "next/navigation";
import { toast } from "sonner";
import { Plus, RefreshCw, CheckCircle, ChevronDown, ChevronUp, Truck, ShieldCheck, Package, Wrench } from "lucide-react";
import styles from "./page.module.scss";

type DistMethod = "by_value" | "by_weight" | "by_quantity" | "manual";

interface LandedCostLine {
  id: string;
  product_id: string;
  product_name?: string;
  quantity: number;
  item_value: number;
  unit_weight?: number;
  allocated_amount: number;
  applied_unit_cost: number;
}

interface LandedCostCharge {
  id: string;
  purchase_order_id?: string;
  po_reference?: string;
  charge_type: string;
  total_amount: number;
  currency: string;
  distribution_method: DistMethod;
  is_applied: boolean;
  applied_at?: string;
  created_at: string;
  lines: LandedCostLine[];
}

const CHARGE_TYPES = [
  { value: "freight",            label: "Freight",            icon: Truck },
  { value: "customs",            label: "Customs Duty",       icon: ShieldCheck },
  { value: "insurance",          label: "Insurance",          icon: ShieldCheck },
  { value: "handling",           label: "Handling",           icon: Package },
  { value: "quality_inspection", label: "Quality Inspection", icon: Wrench },
];

const DIST_METHODS: { value: DistMethod; label: string }[] = [
  { value: "by_value",    label: "By Value"    },
  { value: "by_weight",   label: "By Weight"   },
  { value: "by_quantity", label: "By Quantity" },
  { value: "manual",      label: "Manual"      },
];

const TYPE_COLORS: Record<string, string> = {
  freight:            "bg-blue-100 text-blue-700",
  customs:            "bg-amber-100 text-amber-700",
  insurance:          "bg-green-100 text-green-700",
  handling:           "bg-purple-100 text-purple-700",
  quality_inspection: "bg-rose-100 text-rose-700",
};

const TYPE_MODULE: Record<string, keyof typeof styles> = {
  freight:            "typeFreight",
  customs:            "typeCustoms",
  insurance:          "typeInsurance",
  handling:           "typeHandling",
  quality_inspection: "typeQualityInspection",
};

export default function LandedCostsPage() {
  const router = useRouter();
  const params = useParams();
  const locale = params.locale as string;

  const [charges, setCharges] = useState<LandedCostCharge[]>([]);
  const [loading, setLoading] = useState(true);
  const [expanded, setExpanded] = useState<string | null>(null);
  const [showAdd, setShowAdd] = useState(false);
  const [distributing, setDistributing] = useState<string | null>(null);
  const [applying, setApplying] = useState<string | null>(null);

  const [form, setForm] = useState({
    purchase_order_id: "",
    charge_type: "freight",
    total_amount: "",
    currency: "SEK",
    distribution_method: "by_value" as DistMethod,
  });

  async function load() {
    try {
      const data = await api.get("/api/landed-costs");
      setCharges(data.items ?? data);
    } catch (err: any) {
      if (err?.status === 401) router.push(`/${locale}/auth/login`);
      else toast.error("Failed to load landed costs");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { load(); }, []);

  async function handleAdd(e: React.FormEvent) {
    e.preventDefault();
    try {
      await api.post("/api/landed-costs", {
        ...form,
        total_amount: parseFloat(form.total_amount),
        purchase_order_id: form.purchase_order_id || undefined,
      });
      toast.success("Charge added");
      setShowAdd(false);
      setForm({ purchase_order_id: "", charge_type: "freight", total_amount: "", currency: "SEK", distribution_method: "by_value" });
      load();
    } catch {
      toast.error("Failed to add charge");
    }
  }

  async function distribute(chargeId: string) {
    setDistributing(chargeId);
    try {
      await api.post(`/api/landed-costs/${chargeId}/distribute`, {});
      toast.success("Allocation recalculated");
      load();
    } catch {
      toast.error("Failed to distribute");
    } finally {
      setDistributing(null);
    }
  }

  async function apply(chargeId: string) {
    setApplying(chargeId);
    try {
      await api.post(`/api/landed-costs/${chargeId}/apply`, {});
      toast.success("Landed costs applied to product prices");
      load();
    } catch {
      toast.error("Failed to apply");
    } finally {
      setApplying(null);
    }
  }

  const totalUnapplied = charges.filter(c => !c.is_applied).reduce((s, c) => s + c.total_amount, 0);
  const totalApplied   = charges.filter(c =>  c.is_applied).reduce((s, c) => s + c.total_amount, 0);

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Landed Cost Tracking</h1>
          <p className="text-sm text-muted-foreground mt-1">
            Distribute freight, customs, and other charges across purchase order items
          </p>
        </div>
        <button className="btn-primary flex items-center gap-2" onClick={() => setShowAdd(true)}>
          <Plus className="h-4 w-4" /> Add Charge
        </button>
      </div>

      {/* Summary cards */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <div className="rounded-2xl border bg-card p-5">
          <p className="text-sm text-muted-foreground">Total Charges</p>
          <p className="text-2xl font-bold mt-1">{charges.length}</p>
        </div>
        <div className="rounded-2xl border bg-card p-5">
          <p className="text-sm text-muted-foreground">Pending Application</p>
          <p className="text-2xl font-bold mt-1 text-amber-600">
            {totalUnapplied.toLocaleString("sv-SE", { minimumFractionDigits: 2 })}
          </p>
        </div>
        <div className="rounded-2xl border bg-card p-5">
          <p className="text-sm text-muted-foreground">Applied to Costs</p>
          <p className="text-2xl font-bold mt-1 text-green-600">
            {totalApplied.toLocaleString("sv-SE", { minimumFractionDigits: 2 })}
          </p>
        </div>
      </div>

      {/* Charges list */}
      {loading ? (
        <div className="flex justify-center py-16">
          <RefreshCw className="h-6 w-6 animate-spin text-muted-foreground" />
        </div>
      ) : charges.length === 0 ? (
        <div className="rounded-2xl border bg-card flex flex-col items-center justify-center py-20 text-center">
          <Truck className="h-12 w-12 text-muted-foreground mb-4" />
          <p className="font-medium">No landed cost charges yet</p>
          <p className="text-sm text-muted-foreground mt-1">
            Add freight, customs, or other charges to a purchase order
          </p>
        </div>
      ) : (
        <div className="space-y-3">
          {charges.map(charge => (
            <div key={charge.id} className="rounded-2xl border bg-card overflow-hidden">
              {/* Charge header row */}
              <div
                className="flex items-center gap-4 p-4 cursor-pointer hover:bg-muted/40 transition-colors"
                onClick={() => setExpanded(expanded === charge.id ? null : charge.id)}
              >
                <span className={styles[TYPE_MODULE[charge.charge_type] ?? "typeOther"]}>
                  {CHARGE_TYPES.find(t => t.value === charge.charge_type)?.label ?? charge.charge_type}
                </span>

                {charge.po_reference && (
                  <span className="text-sm text-muted-foreground">PO #{charge.po_reference}</span>
                )}

                <span className="ml-auto font-semibold">
                  {charge.total_amount.toLocaleString("sv-SE", { minimumFractionDigits: 2 })} {charge.currency}
                </span>

                <span className="text-xs text-muted-foreground">
                  {DIST_METHODS.find(d => d.value === charge.distribution_method)?.label}
                </span>

                {charge.is_applied ? (
                  <span className="flex items-center gap-1 text-xs text-green-600 font-medium">
                    <CheckCircle className="h-3.5 w-3.5" /> Applied
                  </span>
                ) : (
                  <span className="text-xs text-amber-600 font-medium">Pending</span>
                )}

                {expanded === charge.id ? <ChevronUp className="h-4 w-4 text-muted-foreground" /> : <ChevronDown className="h-4 w-4 text-muted-foreground" />}
              </div>

              {/* Expanded: lines + actions */}
              {expanded === charge.id && (
                <div className="border-t px-4 pb-4 pt-3 space-y-4">
                  {/* Lines table */}
                  {charge.lines.length > 0 ? (
                    <div className="overflow-x-auto rounded-xl border">
                      <table className="w-full text-sm">
                        <thead className="bg-muted/50">
                          <tr>
                            <th className="text-left px-4 py-2 font-medium">Product</th>
                            <th className="text-right px-4 py-2 font-medium">Qty</th>
                            <th className="text-right px-4 py-2 font-medium">Item Value</th>
                            <th className="text-right px-4 py-2 font-medium">Allocated</th>
                            <th className="text-right px-4 py-2 font-medium">Per Unit</th>
                          </tr>
                        </thead>
                        <tbody>
                          {charge.lines.map(line => (
                            <tr key={line.id} className="border-t">
                              <td className="px-4 py-2">{line.product_name ?? line.product_id}</td>
                              <td className="px-4 py-2 text-right">{line.quantity}</td>
                              <td className="px-4 py-2 text-right">{line.item_value.toFixed(2)}</td>
                              <td className="px-4 py-2 text-right font-medium">{line.allocated_amount.toFixed(2)}</td>
                              <td className="px-4 py-2 text-right text-blue-600">{line.applied_unit_cost.toFixed(4)}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  ) : (
                    <p className="text-sm text-muted-foreground">
                      No lines yet — click Distribute to calculate allocations.
                    </p>
                  )}

                  {/* Action buttons */}
                  {!charge.is_applied && (
                    <div className="flex gap-3">
                      <button
                        className="btn-secondary text-sm flex items-center gap-2"
                        onClick={() => distribute(charge.id)}
                        disabled={distributing === charge.id}
                      >
                        {distributing === charge.id ? (
                          <RefreshCw className="h-3.5 w-3.5 animate-spin" />
                        ) : (
                          <RefreshCw className="h-3.5 w-3.5" />
                        )}
                        Distribute
                      </button>
                      {charge.lines.length > 0 && (
                        <button
                          className="btn-primary text-sm flex items-center gap-2"
                          onClick={() => apply(charge.id)}
                          disabled={applying === charge.id}
                        >
                          {applying === charge.id ? (
                            <RefreshCw className="h-3.5 w-3.5 animate-spin" />
                          ) : (
                            <CheckCircle className="h-3.5 w-3.5" />
                          )}
                          Apply to Product Costs
                        </button>
                      )}
                    </div>
                  )}
                  {charge.is_applied && charge.applied_at && (
                    <p className="text-xs text-muted-foreground">
                      Applied {new Date(charge.applied_at).toLocaleDateString("sv-SE")}
                    </p>
                  )}
                </div>
              )}
            </div>
          ))}
        </div>
      )}

      {/* Add charge modal */}
      {showAdd && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
          <div className="bg-background rounded-2xl shadow-xl w-full max-w-md p-6 space-y-4">
            <h2 className="text-lg font-semibold">Add Landed Cost Charge</h2>
            <form onSubmit={handleAdd} className="space-y-4">
              <div>
                <label className="text-sm font-medium">Charge Type</label>
                <select
                  className="input mt-1 w-full"
                  value={form.charge_type}
                  onChange={e => setForm(f => ({ ...f, charge_type: e.target.value }))}
                >
                  {CHARGE_TYPES.map(t => (
                    <option key={t.value} value={t.value}>{t.label}</option>
                  ))}
                </select>
              </div>
              <div>
                <label className="text-sm font-medium">Purchase Order ID (optional)</label>
                <input
                  className="input mt-1 w-full"
                  placeholder="Leave blank to apply manually"
                  value={form.purchase_order_id}
                  onChange={e => setForm(f => ({ ...f, purchase_order_id: e.target.value }))}
                />
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="text-sm font-medium">Total Amount</label>
                  <input
                    required
                    type="number"
                    step="0.01"
                    min="0"
                    className="input mt-1 w-full"
                    placeholder="0.00"
                    value={form.total_amount}
                    onChange={e => setForm(f => ({ ...f, total_amount: e.target.value }))}
                  />
                </div>
                <div>
                  <label className="text-sm font-medium">Currency</label>
                  <select
                    className="input mt-1 w-full"
                    value={form.currency}
                    onChange={e => setForm(f => ({ ...f, currency: e.target.value }))}
                  >
                    {["SEK","NOK","DKK","EUR","USD","AED","SAR"].map(c => (
                      <option key={c} value={c}>{c}</option>
                    ))}
                  </select>
                </div>
              </div>
              <div>
                <label className="text-sm font-medium">Distribution Method</label>
                <select
                  className="input mt-1 w-full"
                  value={form.distribution_method}
                  onChange={e => setForm(f => ({ ...f, distribution_method: e.target.value as DistMethod }))}
                >
                  {DIST_METHODS.map(m => (
                    <option key={m.value} value={m.value}>{m.label}</option>
                  ))}
                </select>
              </div>
              <div className="flex gap-3 pt-2">
                <button type="button" className="btn-secondary flex-1" onClick={() => setShowAdd(false)}>Cancel</button>
                <button type="submit" className="btn-primary flex-1">Add Charge</button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
