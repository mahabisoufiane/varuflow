"use client";

import { api } from "@/lib/api-client";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useEffect, useState } from "react";
import { AlertTriangle, Download, Filter, Clock } from "lucide-react";
import { useTranslations } from "next-intl";

interface MovementAudit {
  id: string;
  created_at: string;
  type: "IN" | "OUT" | "ADJUSTMENT" | "RESERVED";
  quantity: number;
  product_id: string;
  product_sku: string | null;
  product_name: string | null;
  warehouse_id: string;
  warehouse_name: string | null;
  reference: string | null;
  reason: string | null;
  actor_user_id: string | null;
  ip_address: string | null;
  unusual: boolean;
  reasons: string[];
}

interface Product { id: string; name: string; sku: string; }
interface WarehouseItem { id: string; name: string; }

function typeVariant(t: string) {
  switch (t) {
    case "IN": return "default";
    case "OUT": return "secondary";
    case "ADJUSTMENT": return "destructive";
    default: return "outline";
  }
}

export default function InventoryAuditPage() {
  const t = useTranslations("inventory_audit");
  const [rows, setRows] = useState<MovementAudit[]>([]);
  const [products, setProducts] = useState<Product[]>([]);
  const [warehouses, setWarehouses] = useState<WarehouseItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [filters, setFilters] = useState({
    product_id: "",
    warehouse_id: "",
    type: "",
    start_date: "",
    end_date: "",
  });

  async function load() {
    setLoading(true);
    setError(null);
    try {
      const params = new URLSearchParams();
      if (filters.product_id) params.set("product_id", filters.product_id);
      if (filters.warehouse_id) params.set("warehouse_id", filters.warehouse_id);
      if (filters.type) params.set("type", filters.type);
      if (filters.start_date) params.set("start_date", filters.start_date);
      if (filters.end_date) params.set("end_date", filters.end_date);
      const q = params.toString();
      const data = await api.get<MovementAudit[]>(
        `/api/inventory/audit/movements${q ? `?${q}` : ""}`
      );
      setRows(data);
    } catch (e: any) {
      setError(e.message || String(e));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    (async () => {
      try {
        const [pr, wh] = await Promise.all([
          api.get<{ items: Product[] }>("/api/inventory/products?limit=500&is_active=true"),
          api.get<WarehouseItem[]>("/api/inventory/warehouses"),
        ]);
        setProducts(pr.items || []);
        setWarehouses(wh || []);
      } catch {
        /* non-critical — filters still work by ID */
      }
    })();
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  function setFilter(k: string, v: string) {
    setFilters((s) => ({ ...s, [k]: v }));
  }

  async function exportCsv() {
    const params = new URLSearchParams();
    if (filters.product_id) params.set("product_id", filters.product_id);
    if (filters.warehouse_id) params.set("warehouse_id", filters.warehouse_id);
    if (filters.type) params.set("type", filters.type);
    if (filters.start_date) params.set("start_date", filters.start_date);
    if (filters.end_date) params.set("end_date", filters.end_date);
    const url = `/api/inventory/audit/movements.csv${params.toString() ? `?${params.toString()}` : ""}`;
    await api.downloadBlob(url, "inventory-audit.csv");
  }

  return (
    <div className="space-y-6">
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-2xl font-semibold">{t("title")}</h1>
          <p className="text-sm text-muted-foreground">{t("subtitle")}</p>
        </div>
        <Button onClick={exportCsv} variant="outline" className="gap-2">
          <Download className="h-4 w-4" /> {t("export_csv")}
        </Button>
      </div>

      <div className="rounded-lg border bg-card p-4">
        <div className="mb-3 flex items-center gap-2 text-sm font-medium">
          <Filter className="h-4 w-4" /> {t("filters")}
        </div>
        <div className="grid gap-3 md:grid-cols-5">
          <div>
            <Label>{t("product")}</Label>
            <select
              className="mt-1 w-full rounded-md border bg-background px-2 py-2 text-sm"
              value={filters.product_id}
              onChange={(e) => setFilter("product_id", e.target.value)}
            >
              <option value="">{t("all")}</option>
              {products.map((p) => (
                <option key={p.id} value={p.id}>{p.sku} — {p.name}</option>
              ))}
            </select>
          </div>
          <div>
            <Label>{t("warehouse")}</Label>
            <select
              className="mt-1 w-full rounded-md border bg-background px-2 py-2 text-sm"
              value={filters.warehouse_id}
              onChange={(e) => setFilter("warehouse_id", e.target.value)}
            >
              <option value="">{t("all")}</option>
              {warehouses.map((w) => (
                <option key={w.id} value={w.id}>{w.name}</option>
              ))}
            </select>
          </div>
          <div>
            <Label>{t("type")}</Label>
            <select
              className="mt-1 w-full rounded-md border bg-background px-2 py-2 text-sm"
              value={filters.type}
              onChange={(e) => setFilter("type", e.target.value)}
            >
              <option value="">{t("all")}</option>
              <option value="IN">IN</option>
              <option value="OUT">OUT</option>
              <option value="ADJUSTMENT">ADJUSTMENT</option>
              <option value="RESERVED">RESERVED</option>
            </select>
          </div>
          <div>
            <Label>{t("start_date")}</Label>
            <Input
              type="datetime-local"
              value={filters.start_date}
              onChange={(e) => setFilter("start_date", e.target.value)}
            />
          </div>
          <div>
            <Label>{t("end_date")}</Label>
            <Input
              type="datetime-local"
              value={filters.end_date}
              onChange={(e) => setFilter("end_date", e.target.value)}
            />
          </div>
        </div>
        <div className="mt-3 flex justify-end">
          <Button onClick={load} disabled={loading}>
            {loading ? t("loading") : t("apply")}
          </Button>
        </div>
      </div>

      {error && (
        <div className="rounded-md border border-destructive/50 bg-destructive/10 p-3 text-sm text-destructive">
          {error}
        </div>
      )}

      <div className="rounded-lg border bg-card">
        <table className="w-full text-sm">
          <thead className="border-b bg-muted/50 text-left">
            <tr>
              <th className="p-2">{t("col_time")}</th>
              <th className="p-2">{t("col_type")}</th>
              <th className="p-2 text-right">{t("col_qty")}</th>
              <th className="p-2">{t("col_product")}</th>
              <th className="p-2">{t("col_warehouse")}</th>
              <th className="p-2">{t("col_reference")}</th>
              <th className="p-2">{t("col_reason")}</th>
              <th className="p-2">{t("col_actor")}</th>
              <th className="p-2">{t("col_flag")}</th>
            </tr>
          </thead>
          <tbody>
            {rows.length === 0 && !loading && (
              <tr>
                <td colSpan={9} className="p-6 text-center text-muted-foreground">
                  {t("empty")}
                </td>
              </tr>
            )}
            {rows.map((r) => (
              <tr
                key={r.id}
                className={
                  r.unusual
                    ? "border-b border-red-200 bg-red-50/60 dark:bg-red-950/20"
                    : "border-b"
                }
              >
                <td className="p-2">
                  <div className="flex items-center gap-1 text-xs text-muted-foreground">
                    <Clock className="h-3 w-3" />
                    {new Date(r.created_at).toLocaleString()}
                  </div>
                </td>
                <td className="p-2">
                  <Badge variant={typeVariant(r.type) as any}>{r.type}</Badge>
                </td>
                <td className="p-2 text-right font-mono">{r.quantity}</td>
                <td className="p-2">
                  <div className="font-medium">{r.product_name || "—"}</div>
                  <div className="text-xs text-muted-foreground">{r.product_sku || ""}</div>
                </td>
                <td className="p-2">{r.warehouse_name || "—"}</td>
                <td className="p-2 text-muted-foreground">{r.reference || "—"}</td>
                <td className="p-2 text-muted-foreground">{r.reason || "—"}</td>
                <td className="p-2">
                  <div className="font-mono text-xs">{r.actor_user_id?.slice(0, 8) || "—"}</div>
                  {r.ip_address && (
                    <div className="text-xs text-muted-foreground">{r.ip_address}</div>
                  )}
                </td>
                <td className="p-2">
                  {r.unusual ? (
                    <div className="flex items-center gap-1 text-red-600">
                      <AlertTriangle className="h-4 w-4" />
                      <span className="text-xs">
                        {r.reasons.map((x) => t(`reason_${x}`)).join(", ")}
                      </span>
                    </div>
                  ) : (
                    <span className="text-xs text-muted-foreground">—</span>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
