"use client";

import { api } from "@/lib/api-client";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import Link from "next/link";
import { useEffect, useState } from "react";
import { AlertTriangle, ArrowRight, Package, TrendingDown, Warehouse } from "lucide-react";

interface StockLevel {
  id: string;
  product_id: string;
  warehouse_id: string;
  quantity: number;
  min_threshold: number;
  is_low: boolean;
  product: { id: string; name: string; sku: string; unit: string };
  warehouse: { id: string; name: string };
}

export default function InventoryPage() {
  const [stock, setStock] = useState<StockLevel[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.get<StockLevel[]>("/api/inventory/stock")
      .then(setStock)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  const lowStock = stock.filter((s) => s.is_low);
  const totalProducts = new Set(stock.map((s) => s.product_id)).size;
  const totalWarehouses = new Set(stock.map((s) => s.warehouse_id)).size;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-[#1a2332]">Inventory</h1>
          <p className="text-sm text-muted-foreground">
            Stock levels across all warehouses
          </p>
        </div>
        <div className="flex gap-2">
          <Button asChild variant="outline" size="sm">
            <Link href="/inventory/movements">Record movement</Link>
          </Button>
          <Button asChild size="sm" className="bg-[#1a2332] hover:bg-[#2a3342] text-white">
            <Link href="/inventory/products">Manage products</Link>
          </Button>
        </div>
      </div>

      {/* KPI cards */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        <KpiCard
          icon={<Package className="h-5 w-5 text-[#1a2332]" />}
          label="Total Products"
          value={loading ? "—" : String(totalProducts)}
        />
        <KpiCard
          icon={<Warehouse className="h-5 w-5 text-[#1a2332]" />}
          label="Warehouses"
          value={loading ? "—" : String(totalWarehouses)}
        />
        <KpiCard
          icon={<TrendingDown className="h-5 w-5 text-red-500" />}
          label="Low Stock Alerts"
          value={loading ? "—" : String(lowStock.length)}
          highlight={lowStock.length > 0}
        />
      </div>

      {error && (
        <div className="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-700">
          {error}
        </div>
      )}

      {/* Low stock alerts */}
      {!loading && lowStock.length > 0 && (
        <section>
          <div className="mb-3 flex items-center gap-2">
            <AlertTriangle className="h-4 w-4 text-amber-500" />
            <h2 className="font-semibold text-gray-900">Low Stock Alerts</h2>
            <Badge variant="destructive" className="text-xs">
              {lowStock.length}
            </Badge>
          </div>
          <div className="rounded-xl border bg-white divide-y">
            {lowStock.map((s) => (
              <div key={s.id} className="flex items-center justify-between px-4 py-3">
                <div>
                  <p className="font-medium text-sm text-gray-900">{s.product.name}</p>
                  <p className="text-xs text-muted-foreground">
                    SKU: {s.product.sku} · {s.warehouse.name}
                  </p>
                </div>
                <div className="text-right">
                  <Badge variant="destructive" className="text-xs">
                    {s.quantity} {s.product.unit} left
                  </Badge>
                  <p className="mt-0.5 text-xs text-muted-foreground">min: {s.min_threshold}</p>
                </div>
              </div>
            ))}
          </div>
        </section>
      )}

      {/* All stock levels */}
      <section>
        <div className="mb-3 flex items-center justify-between">
          <h2 className="font-semibold text-gray-900">All Stock Levels</h2>
          <Button asChild variant="ghost" size="sm" className="text-xs text-[#1a2332]">
            <Link href="/inventory/warehouses" className="flex items-center gap-1">
              Manage warehouses <ArrowRight className="h-3 w-3" />
            </Link>
          </Button>
        </div>

        {loading ? (
          <StockSkeleton />
        ) : stock.length === 0 ? (
          <EmptyStock />
        ) : (
          <div className="rounded-xl border bg-white overflow-hidden">
            <table className="w-full text-sm">
              <thead className="bg-gray-50 text-xs text-gray-500 uppercase">
                <tr>
                  <th className="px-4 py-3 text-left">Product</th>
                  <th className="px-4 py-3 text-left">SKU</th>
                  <th className="px-4 py-3 text-left">Warehouse</th>
                  <th className="px-4 py-3 text-right">Qty</th>
                  <th className="px-4 py-3 text-right">Min</th>
                  <th className="px-4 py-3 text-center">Status</th>
                </tr>
              </thead>
              <tbody className="divide-y">
                {stock.map((s) => (
                  <tr key={s.id} className="hover:bg-gray-50">
                    <td className="px-4 py-3 font-medium">{s.product.name}</td>
                    <td className="px-4 py-3 text-muted-foreground">{s.product.sku}</td>
                    <td className="px-4 py-3 text-muted-foreground">{s.warehouse.name}</td>
                    <td className="px-4 py-3 text-right font-mono">
                      {s.quantity} {s.product.unit}
                    </td>
                    <td className="px-4 py-3 text-right text-muted-foreground font-mono">
                      {s.min_threshold}
                    </td>
                    <td className="px-4 py-3 text-center">
                      {s.is_low ? (
                        <Badge variant="destructive" className="text-xs">Low</Badge>
                      ) : (
                        <Badge className="text-xs text-green-700 bg-green-100 hover:bg-green-100">OK</Badge>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  );
}

function KpiCard({ icon, label, value, highlight = false }: {
  icon: React.ReactNode; label: string; value: string; highlight?: boolean;
}) {
  return (
    <div className={`rounded-xl border bg-white p-5 ${highlight ? "border-red-200 bg-red-50" : ""}`}>
      <div className="flex items-center gap-3">
        <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-gray-100">{icon}</div>
        <div>
          <p className="text-xs text-muted-foreground">{label}</p>
          <p className="text-2xl font-bold text-[#1a2332]">{value}</p>
        </div>
      </div>
    </div>
  );
}

function StockSkeleton() {
  return (
    <div className="rounded-xl border bg-white divide-y animate-pulse">
      {[1, 2, 3, 4].map((i) => (
        <div key={i} className="flex gap-4 px-4 py-3">
          <div className="h-4 w-32 rounded bg-gray-200" />
          <div className="h-4 w-20 rounded bg-gray-200" />
          <div className="ml-auto h-4 w-12 rounded bg-gray-200" />
        </div>
      ))}
    </div>
  );
}

function EmptyStock() {
  return (
    <div className="rounded-xl border bg-white px-6 py-12 text-center">
      <Package className="mx-auto h-10 w-10 text-gray-300" />
      <h3 className="mt-3 font-medium text-gray-900">No stock data yet</h3>
      <p className="mt-1 text-sm text-muted-foreground">
        Add products and warehouses, then record your first stock movement.
      </p>
      <div className="mt-4 flex justify-center gap-2">
        <Button asChild variant="outline" size="sm">
          <Link href="/inventory/warehouses">Add warehouse</Link>
        </Button>
        <Button asChild size="sm" className="bg-[#1a2332] hover:bg-[#2a3342] text-white">
          <Link href="/inventory/products/new">Add product</Link>
        </Button>
      </div>
    </div>
  );
}
