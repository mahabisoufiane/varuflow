"use client";

import { useState, useEffect } from "react";
import { useTranslations } from "next-intl";
import { api } from "@/lib/api-client";
import { toast } from "sonner";
import {
  RefreshCw,
  Plus,
  ToggleLeft,
  ToggleRight,
  Package,
  Trash2,
} from "lucide-react";

interface AutoReorderRule {
  id: string;
  product_id: string;
  product_name: string;
  min_stock: number;
  reorder_qty: number;
  supplier: string;
  active: boolean;
}

interface CreateRuleForm {
  product: string;
  min_stock: number;
  reorder_qty: number;
  supplier: string;
}

const EMPTY_FORM: CreateRuleForm = {
  product: "",
  min_stock: 0,
  reorder_qty: 0,
  supplier: "",
};

export default function AutoReorderPage() {
  const t = useTranslations("inventory");
  const [rules, setRules] = useState<AutoReorderRule[]>([]);
  const [loading, setLoading] = useState(true);
  const [form, setForm] = useState<CreateRuleForm>(EMPTY_FORM);
  const [creating, setCreating] = useState(false);
  const [showForm, setShowForm] = useState(false);

  const fetchRules = async () => {
    try {
      setLoading(true);
      const data = await api.get<AutoReorderRule[]>(
        "/api/inventory/auto-reorder-rules"
      );
      setRules(data);
    } catch {
      toast.error("Failed to load auto-reorder rules.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchRules();
  }, []);

  const handleCreate = async () => {
    if (!form.product || form.min_stock <= 0 || form.reorder_qty <= 0) {
      toast.error("Please fill in all required fields.");
      return;
    }
    try {
      setCreating(true);
      await api.post("/api/inventory/auto-reorder-rules", {
        product: form.product,
        min_stock: form.min_stock,
        reorder_qty: form.reorder_qty,
        supplier: form.supplier,
      });
      toast.success("Rule created successfully.");
      setForm(EMPTY_FORM);
      setShowForm(false);
      await fetchRules();
    } catch {
      toast.error("Failed to create rule.");
    } finally {
      setCreating(false);
    }
  };

  const toggleActive = async (rule: AutoReorderRule) => {
    try {
      await api.patch(`/api/inventory/auto-reorder-rules/${rule.id}`, {
        active: !rule.active,
      });
      setRules((prev) =>
        prev.map((r) => (r.id === rule.id ? { ...r, active: !r.active } : r))
      );
      toast.success(`Rule ${rule.active ? "deactivated" : "activated"}.`);
    } catch {
      toast.error("Failed to update rule.");
    }
  };

  const deleteRule = async (id: string) => {
    try {
      await api.delete(`/api/inventory/auto-reorder-rules/${id}`);
      setRules((prev) => prev.filter((r) => r.id !== id));
      toast.success("Rule deleted.");
    } catch {
      toast.error("Failed to delete rule.");
    }
  };

  return (
    <div className="space-y-6 p-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="vf-text-1 text-2xl font-semibold">
            Auto-Reorder Rules
          </h1>
          <p className="vf-text-m mt-1">
            Configure automatic reorder rules for your products.
          </p>
        </div>
        <button
          onClick={() => setShowForm(!showForm)}
          className="inline-flex items-center gap-2 rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700"
        >
          <Plus className="h-4 w-4" />
          New Rule
        </button>
      </div>

      {showForm && (
        <div className="vf-bg-card vf-border rounded-lg border p-6 space-y-4">
          <h2 className="vf-text-1 text-lg font-medium">Create Rule</h2>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <div>
              <label className="vf-text-m mb-1 block text-sm font-medium">
                Product
              </label>
              <input
                type="text"
                value={form.product}
                onChange={(e) =>
                  setForm((f) => ({ ...f, product: e.target.value }))
                }
                placeholder="Product name or SKU"
                className="vf-border w-full rounded-md border px-3 py-2 text-sm"
              />
            </div>
            <div>
              <label className="vf-text-m mb-1 block text-sm font-medium">
                Min Stock
              </label>
              <input
                type="number"
                value={form.min_stock || ""}
                onChange={(e) =>
                  setForm((f) => ({
                    ...f,
                    min_stock: parseInt(e.target.value) || 0,
                  }))
                }
                placeholder="0"
                className="vf-border w-full rounded-md border px-3 py-2 text-sm"
              />
            </div>
            <div>
              <label className="vf-text-m mb-1 block text-sm font-medium">
                Reorder Qty
              </label>
              <input
                type="number"
                value={form.reorder_qty || ""}
                onChange={(e) =>
                  setForm((f) => ({
                    ...f,
                    reorder_qty: parseInt(e.target.value) || 0,
                  }))
                }
                placeholder="0"
                className="vf-border w-full rounded-md border px-3 py-2 text-sm"
              />
            </div>
            <div>
              <label className="vf-text-m mb-1 block text-sm font-medium">
                Supplier
              </label>
              <input
                type="text"
                value={form.supplier}
                onChange={(e) =>
                  setForm((f) => ({ ...f, supplier: e.target.value }))
                }
                placeholder="Supplier name"
                className="vf-border w-full rounded-md border px-3 py-2 text-sm"
              />
            </div>
          </div>
          <div className="flex gap-2">
            <button
              onClick={handleCreate}
              disabled={creating}
              className="inline-flex items-center gap-2 rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
            >
              {creating ? (
                <RefreshCw className="h-4 w-4 animate-spin" />
              ) : (
                <Plus className="h-4 w-4" />
              )}
              {creating ? "Creating..." : "Create Rule"}
            </button>
            <button
              onClick={() => {
                setShowForm(false);
                setForm(EMPTY_FORM);
              }}
              className="rounded-lg px-4 py-2 text-sm font-medium vf-text-m hover:bg-gray-100 dark:hover:bg-gray-800"
            >
              Cancel
            </button>
          </div>
        </div>
      )}

      {loading ? (
        <div className="flex items-center justify-center py-20">
          <RefreshCw className="h-6 w-6 animate-spin vf-text-m" />
        </div>
      ) : rules.length === 0 ? (
        <div className="vf-bg-card vf-border flex flex-col items-center justify-center rounded-lg border py-16">
          <Package className="h-12 w-12 vf-text-m mb-4" />
          <p className="vf-text-1 font-medium">No auto-reorder rules yet</p>
          <p className="vf-text-m mt-1 text-sm">
            Create your first rule to automate inventory replenishment.
          </p>
        </div>
      ) : (
        <div className="vf-bg-card vf-border overflow-hidden rounded-lg border">
          <table className="w-full text-sm">
            <thead>
              <tr className="vf-border border-b">
                <th className="vf-text-m px-4 py-3 text-left font-medium">
                  Product
                </th>
                <th className="vf-text-m px-4 py-3 text-left font-medium">
                  Min Stock
                </th>
                <th className="vf-text-m px-4 py-3 text-left font-medium">
                  Reorder Qty
                </th>
                <th className="vf-text-m px-4 py-3 text-left font-medium">
                  Supplier
                </th>
                <th className="vf-text-m px-4 py-3 text-left font-medium">
                  Status
                </th>
                <th className="vf-text-m px-4 py-3 text-right font-medium">
                  Actions
                </th>
              </tr>
            </thead>
            <tbody>
              {rules.map((rule) => (
                <tr key={rule.id} className="vf-border border-b last:border-0">
                  <td className="vf-text-1 px-4 py-3 font-medium">
                    {rule.product_name}
                  </td>
                  <td className="vf-text-m px-4 py-3">{rule.min_stock}</td>
                  <td className="vf-text-m px-4 py-3">{rule.reorder_qty}</td>
                  <td className="vf-text-m px-4 py-3">{rule.supplier}</td>
                  <td className="px-4 py-3">
                    <button
                      onClick={() => toggleActive(rule)}
                      className="inline-flex items-center gap-1.5"
                    >
                      {rule.active ? (
                        <>
                          <ToggleRight className="h-5 w-5 text-emerald-500" />
                          <span className="text-emerald-600 text-xs font-medium">
                            Active
                          </span>
                        </>
                      ) : (
                        <>
                          <ToggleLeft className="h-5 w-5 vf-text-m" />
                          <span className="vf-text-m text-xs font-medium">
                            Inactive
                          </span>
                        </>
                      )}
                    </button>
                  </td>
                  <td className="px-4 py-3 text-right">
                    <button
                      onClick={() => deleteRule(rule.id)}
                      className="rounded p-1 text-red-500 hover:bg-red-50 dark:hover:bg-red-900/20"
                    >
                      <Trash2 className="h-4 w-4" />
                    </button>
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
