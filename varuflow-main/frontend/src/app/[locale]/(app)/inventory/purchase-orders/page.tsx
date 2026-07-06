"use client";

import { api } from "@/lib/api-client";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Link } from "@/i18n/navigation";
import { useEffect, useState } from "react";
import { FileText, Plus } from "lucide-react";
import styles from "./page.module.scss";
import ContentPanel from "@/components/console/ContentPanel";

interface PurchaseOrder {
  id: string; status: "DRAFT" | "SENT" | "RECEIVED"; total: string; notes: string | null;
  created_at: string; supplier: { name: string };
  items: { id: string; quantity: number; unit_price: string; line_total: string; product_id: string }[];
}

const STATUS_COLORS: Record<string, string> = {
  DRAFT: "bg-gray-100 text-gray-700",
  SENT: "bg-blue-100 text-blue-700",
  RECEIVED: "bg-green-100 text-green-700",
};

const STATUS_MODULE: Record<string, keyof typeof styles> = {
  DRAFT:    "statusDraft",
  SENT:     "statusSent",
  RECEIVED: "statusReceived",
};

export default function PurchaseOrdersPage() {
  const [orders, setOrders] = useState<PurchaseOrder[]>([]);
  const [loading, setLoading] = useState(true);
  const [selected, setSelected] = useState<PurchaseOrder | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [updating, setUpdating] = useState<string | null>(null);

  async function load() {
    try { setOrders(await api.get<PurchaseOrder[]>("/api/inventory/purchase-orders")); }
    catch (e: any) { setError(e.message); }
    finally { setLoading(false); }
  }

  useEffect(() => { load(); }, []);

  async function advanceStatus(po: PurchaseOrder) {
    const next = po.status === "DRAFT" ? "SENT" : po.status === "SENT" ? "RECEIVED" : null;
    if (!next) return;
    setUpdating(po.id);
    try {
      await api.patch(`/api/inventory/purchase-orders/${po.id}/status`, { status: next });
      await load();
    } catch (e: any) { setError(e.message); } finally { setUpdating(null); }
  }

  function downloadPDF(id: string) {
    window.open(api.downloadUrl(`/api/inventory/purchase-orders/${id}/pdf`), "_blank");
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-[var(--vf-text-primary)]">Purchase Orders</h1>
          <p className="text-sm text-muted-foreground">{orders.length} orders</p>
        </div>
        <Button asChild size="sm" className="bg-[var(--vf-brand-primary)] hover:bg-[var(--vf-brand-primary-hover)] text-white">
          <Link href="/inventory/purchase-orders/new">
            <Plus className="mr-1.5 h-3.5 w-3.5" />New order
          </Link>
        </Button>
      </div>

      {error && <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-2 text-sm text-red-700">{error}</div>}

      {!loading && orders.length === 0 ? (
        <div className="rounded-xl border bg-white px-6 py-12 text-center">
          <FileText className="mx-auto h-10 w-10 text-gray-300" />
          <h3 className="mt-3 font-medium text-gray-900">No purchase orders yet</h3>
          <p className="mt-1 text-sm text-muted-foreground">Create a PO to restock from a supplier.</p>
          <Button asChild size="sm" className="mt-4 bg-[var(--vf-brand-primary)] hover:bg-[var(--vf-brand-primary-hover)] text-white">
            <Link href="/inventory/purchase-orders/new"><Plus className="mr-1.5 h-3.5 w-3.5" />New order</Link>
          </Button>
        </div>
      ) : (
        <div className="overflow-hidden rounded-xl border bg-white">
          <ContentPanel<PurchaseOrder>
            hideHeader
            title="Purchase Orders"
            rows={orders}
            loading={loading}
            getRowId={(po) => po.id}
            columns={[
              { key: "id", header: "PO #", render: (po) => <span className="font-mono text-xs">{po.id.slice(0, 8).toUpperCase()}</span> },
              { key: "supplier", header: "Supplier", render: (po) => <span className="font-medium text-foreground">{po.supplier.name}</span> },
              { key: "status", header: "Status", render: (po) => <span className={styles[STATUS_MODULE[po.status] ?? "statusDraft"]}>{po.status}</span> },
              { key: "total", header: "Total (SEK)", className: "text-right", render: (po) => <span className="font-mono">{Number(po.total).toLocaleString("sv-SE", { minimumFractionDigits: 2 })}</span> },
              { key: "created_at", header: "Date", render: (po) => new Date(po.created_at).toLocaleDateString("sv-SE") },
            ]}
            selected={selected}
            onSelect={setSelected}
            detailTitle={(po) => `PO ${po.id.slice(0, 8).toUpperCase()}`}
            detailDescription={(po) => po.supplier.name}
            renderDetail={(po) => (
              <div className="space-y-4">
                <dl className="divide-y">
                  <div className="grid grid-cols-3 gap-2 py-2.5">
                    <dt className="text-xs font-medium text-muted-foreground">Status</dt>
                    <dd className="col-span-2"><span className={styles[STATUS_MODULE[po.status] ?? "statusDraft"]}>{po.status}</span></dd>
                  </div>
                  {([
                    ["Supplier", po.supplier.name],
                    ["Total", `${Number(po.total).toLocaleString("sv-SE", { minimumFractionDigits: 2 })} SEK`],
                    ["Line items", String(po.items.length)],
                    ["Created", new Date(po.created_at).toLocaleDateString("sv-SE")],
                  ] as [string, string][]).map(([label, val]) => (
                    <div key={label} className="grid grid-cols-3 gap-2 py-2.5">
                      <dt className="text-xs font-medium text-muted-foreground">{label}</dt>
                      <dd className="col-span-2 text-sm text-foreground">{val}</dd>
                    </div>
                  ))}
                </dl>
                <div className="flex flex-wrap gap-2">
                  <Button variant="ghost" size="sm" onClick={() => downloadPDF(po.id)}>PDF</Button>
                  {po.status !== "RECEIVED" && (
                    <Button variant="outline" size="sm" disabled={updating === po.id} onClick={() => { setSelected(null); advanceStatus(po); }}>
                      {po.status === "DRAFT" ? "Mark Sent" : "Mark Received"}
                    </Button>
                  )}
                </div>
              </div>
            )}
          />
        </div>
      )}
    </div>
  );
}
