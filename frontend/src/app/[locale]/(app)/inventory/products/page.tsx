"use client";

import { api } from "@/lib/api-client";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { Package, Pencil, Plus, Search, Upload } from "lucide-react";

interface Product {
  id: string;
  name: string;
  sku: string;
  category: string | null;
  unit: string;
  purchase_price: string;
  sell_price: string;
  tax_rate: string;
  is_active: boolean;
}

export default function ProductsPage() {
  const [products, setProducts] = useState<Product[]>([]);
  const [total, setTotal] = useState(0);
  const [search, setSearch] = useState("");
  const [loading, setLoading] = useState(true);
  const [importing, setImporting] = useState(false);
  const [importResult, setImportResult] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  async function fetchProducts(q = "") {
    setLoading(true);
    try {
      const params = new URLSearchParams({ limit: "100", is_active: "true" });
      if (q) params.set("search", q);
      const data = await api.get<{ items: Product[]; total: number }>(
        `/api/inventory/products?${params}`
      );
      setProducts(data.items);
      setTotal(data.total);
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    fetchProducts();
  }, []);

  function handleSearch(e: React.FormEvent) {
    e.preventDefault();
    fetchProducts(search);
  }

  async function handleCSVImport(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    setImporting(true);
    setImportResult(null);
    try {
      const result = await api.upload<{ created: number; updated: number; errors: string[] }>(
        "/api/inventory/products/import",
        file
      );
      setImportResult(
        `Imported: ${result.created} created, ${result.updated} updated${
          result.errors.length ? `. ${result.errors.length} errors.` : "."
        }`
      );
      fetchProducts();
    } catch (e: any) {
      setError(e.message);
    } finally {
      setImporting(false);
      if (fileRef.current) fileRef.current.value = "";
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-[#1a2332]">Products</h1>
          <p className="text-sm text-muted-foreground">{total} products in catalog</p>
        </div>
        <div className="flex gap-2">
          <input
            ref={fileRef}
            type="file"
            accept=".csv"
            className="hidden"
            onChange={handleCSVImport}
          />
          <Button
            variant="outline"
            size="sm"
            disabled={importing}
            onClick={() => fileRef.current?.click()}
          >
            <Upload className="mr-1.5 h-3.5 w-3.5" />
            {importing ? "Importing…" : "Import CSV"}
          </Button>
          <Button asChild size="sm" className="bg-[#1a2332] hover:bg-[#2a3342] text-white">
            <Link href="/inventory/products/new">
              <Plus className="mr-1.5 h-3.5 w-3.5" />
              New product
            </Link>
          </Button>
        </div>
      </div>

      {importResult && (
        <div className="rounded-lg border border-green-200 bg-green-50 px-4 py-2 text-sm text-green-700">
          {importResult}
        </div>
      )}
      {error && (
        <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-2 text-sm text-red-700">
          {error}
        </div>
      )}

      {/* Search */}
      <form onSubmit={handleSearch} className="flex gap-2">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-gray-400" />
          <input
            type="text"
            placeholder="Search by name or SKU…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full rounded-md border border-gray-300 py-2 pl-9 pr-3 text-sm focus:border-[#1a2332] focus:outline-none focus:ring-1 focus:ring-[#1a2332]"
          />
        </div>
        <Button type="submit" variant="outline" size="sm">Search</Button>
      </form>

      {/* CSV hint */}
      <p className="text-xs text-muted-foreground">
        CSV format: <code className="rounded bg-gray-100 px-1 py-0.5">name, sku, category, unit, purchase_price, sell_price, tax_rate</code>
      </p>

      {loading ? (
        <TableSkeleton />
      ) : products.length === 0 ? (
        <EmptyProducts />
      ) : (
        <div className="rounded-xl border bg-white overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-gray-50 text-xs text-gray-500 uppercase">
              <tr>
                <th className="px-4 py-3 text-left">Product</th>
                <th className="px-4 py-3 text-left">SKU</th>
                <th className="px-4 py-3 text-left">Category</th>
                <th className="px-4 py-3 text-right">Buy (SEK)</th>
                <th className="px-4 py-3 text-right">Sell (SEK)</th>
                <th className="px-4 py-3 text-center">VAT</th>
                <th className="px-4 py-3 text-right" />
              </tr>
            </thead>
            <tbody className="divide-y">
              {products.map((p) => (
                <tr key={p.id} className="hover:bg-gray-50">
                  <td className="px-4 py-3 font-medium">{p.name}</td>
                  <td className="px-4 py-3 font-mono text-xs text-muted-foreground">{p.sku}</td>
                  <td className="px-4 py-3 text-muted-foreground">{p.category ?? "—"}</td>
                  <td className="px-4 py-3 text-right font-mono">{Number(p.purchase_price).toFixed(2)}</td>
                  <td className="px-4 py-3 text-right font-mono">{Number(p.sell_price).toFixed(2)}</td>
                  <td className="px-4 py-3 text-center">
                    <VatBadge rate={p.tax_rate} />
                  </td>
                  <td className="px-4 py-3 text-right">
                    <Button asChild variant="ghost" size="sm" className="h-7 px-2">
                      <Link href={`/inventory/products/${p.id}`}>
                        <Pencil className="h-3.5 w-3.5" />
                      </Link>
                    </Button>
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

function VatBadge({ rate }: { rate: string }) {
  const n = Number(rate);
  const color =
    n === 25 ? "bg-blue-100 text-blue-700" :
    n === 12 ? "bg-purple-100 text-purple-700" :
    "bg-gray-100 text-gray-700";
  return <span className={`rounded px-1.5 py-0.5 text-xs font-medium ${color}`}>{n}%</span>;
}

function TableSkeleton() {
  return (
    <div className="rounded-xl border bg-white divide-y animate-pulse">
      {[1, 2, 3, 4, 5].map((i) => (
        <div key={i} className="flex gap-6 px-4 py-3">
          <div className="h-4 w-40 rounded bg-gray-200" />
          <div className="h-4 w-20 rounded bg-gray-200" />
          <div className="ml-auto h-4 w-16 rounded bg-gray-200" />
        </div>
      ))}
    </div>
  );
}

function EmptyProducts() {
  return (
    <div className="rounded-xl border bg-white px-6 py-12 text-center">
      <Package className="mx-auto h-10 w-10 text-gray-300" />
      <h3 className="mt-3 font-medium text-gray-900">No products yet</h3>
      <p className="mt-1 text-sm text-muted-foreground">
        Create your first product or import from a CSV file.
      </p>
      <Button asChild size="sm" className="mt-4 bg-[#1a2332] hover:bg-[#2a3342] text-white">
        <Link href="/inventory/products/new">
          <Plus className="mr-1.5 h-3.5 w-3.5" />
          New product
        </Link>
      </Button>
    </div>
  );
}
