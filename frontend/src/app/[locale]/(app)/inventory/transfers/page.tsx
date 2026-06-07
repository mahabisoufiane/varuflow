"use client";

import { api } from "@/lib/api-client";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import Link from "next/link";
import { useEffect, useState } from "react";
import { Truck, Plus, ArrowRight } from "lucide-react";
import styles from "./page.module.scss";

interface TransferItem {
  id: string;
  product_id: string;
  batch_id: string | null;
  qty_requested: number;
  qty_shipped: number;
  qty_received: number;
}

interface Transfer {
  id: string;
  from_warehouse_id: string;
  to_warehouse_id: string;
  status: "DRAFT" | "IN_TRANSIT" | "PARTIAL" | "RECEIVED" | "CANCELLED";
  notes: string | null;
  created_at: string;
  shipped_at: string | null;
  received_at: string | null;
  cancelled_at: string | null;
  items: TransferItem[];
}

// Tailwind doesn't pick up dynamic class names; enumerate per status
// so the list stays colour-coded without a global arbitrary value.
const STATUS_COLORS: Record<Transfer["status"], string> = {
  DRAFT: "bg-gray-100 text-gray-700",
  IN_TRANSIT: "bg-blue-100 text-blue-700",
  PARTIAL: "bg-amber-100 text-amber-700",
  RECEIVED: "bg-green-100 text-green-700",
  CANCELLED: "bg-red-100 text-red-700",
};

const STATUS_MODULE: Record<string, keyof typeof styles> = {
  DRAFT:      "statusDraft",
  IN_TRANSIT: "statusInTransit",
  PARTIAL:    "statusPartial",
  RECEIVED:   "statusReceived",
  CANCELLED:  "statusCancelled",
};

export default function StockTransfersPage() {
  const [rows, setRows] = useState<Transfer[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .get<Transfer[]>("/api/stock-transfers")
      .then(setRows)
      .catch((e: any) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-[#1a2332]">Stock Transfers</h1>
          <p className="text-sm text-muted-foreground">
            {rows.length} transfer{rows.length === 1 ? "" : "s"}
          </p>
        </div>
        <Button asChild size="sm" className="bg-[#1a2332] hover:bg-[#2a3342] text-white">
          <Link href="/inventory/transfers/new">
            <Plus className="mr-1.5 h-3.5 w-3.5" />
            New transfer
          </Link>
        </Button>
      </div>

      {error && (
        <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-2 text-sm text-red-700">
          {error}
        </div>
      )}

      {loading ? (
        <div className="space-y-2 animate-pulse">
          {[1, 2, 3].map((i) => (
            <div key={i} className="h-16 rounded-xl bg-gray-100" />
          ))}
        </div>
      ) : rows.length === 0 ? (
        <div className="rounded-xl border bg-white px-6 py-12 text-center">
          <Truck className="mx-auto h-10 w-10 text-gray-300" />
          <h3 className="mt-3 font-medium text-gray-900">No transfers yet</h3>
          <p className="mt-1 text-sm text-muted-foreground">
            Move stock between warehouses with a tracked, audited paper trail.
          </p>
          <Button
            asChild
            size="sm"
            className="mt-4 bg-[#1a2332] hover:bg-[#2a3342] text-white"
          >
            <Link href="/inventory/transfers/new">
              <Plus className="mr-1.5 h-3.5 w-3.5" />
              New transfer
            </Link>
          </Button>
        </div>
      ) : (
        <div className="rounded-xl border bg-white overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-gray-50 text-xs text-gray-500 uppercase">
              <tr>
                <th className="px-4 py-2 text-left">Status</th>
                <th className="px-4 py-2 text-left">Route</th>
                <th className="px-4 py-2 text-right">Lines</th>
                <th className="px-4 py-2 text-right">Units</th>
                <th className="px-4 py-2 text-left">Created</th>
                <th className="px-4 py-2"></th>
              </tr>
            </thead>
            <tbody>
              {rows.map((t) => {
                const units = t.items.reduce((n, i) => n + i.qty_requested, 0);
                return (
                  <tr key={t.id} className="border-t">
                    <td className="px-4 py-2">
                      <span className={styles[STATUS_MODULE[t.status] ?? "statusDraft"]}>{t.status}</span>
                    </td>
                    <td className="px-4 py-2 text-xs font-mono text-gray-600">
                      {t.from_warehouse_id.slice(0, 8)} → {t.to_warehouse_id.slice(0, 8)}
                    </td>
                    <td className="px-4 py-2 text-right tabular-nums">
                      {t.items.length}
                    </td>
                    <td className="px-4 py-2 text-right tabular-nums">{units}</td>
                    <td className="px-4 py-2 text-xs text-gray-500">
                      {new Date(t.created_at).toLocaleString()}
                    </td>
                    <td className="px-4 py-2 text-right">
                      <Link
                        href={`/inventory/transfers/${t.id}`}
                        className="inline-flex items-center text-sm text-[#1a2332] hover:underline"
                      >
                        Details <ArrowRight className="ml-1 h-3 w-3" />
                      </Link>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
