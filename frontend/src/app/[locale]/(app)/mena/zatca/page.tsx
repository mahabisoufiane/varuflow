"use client";

import { api } from "@/lib/api-client";
import { useEffect, useState } from "react";
import { useRouter, useParams } from "next/navigation";
import { toast } from "sonner";
import {
  FileCheck2, RefreshCw, Download, Search, AlertTriangle,
  CheckCircle, XCircle, Clock, BarChart3
} from "lucide-react";

interface ZatcaRecord {
  id: string; org_id: string; invoice_id: string;
  invoice_hash: string; qr_tlv_b64: string;
  clearance_status: string; zatca_uuid?: string;
  created_at: string; updated_at: string;
}
interface Dashboard {
  summary: { pending: number; submitted: number; cleared: number; rejected: number; not_submitted: number };
  total: number;
  recent: ZatcaRecord[];
}

const STATUS_STYLE: Record<string, { bg: string; label: string; Icon: any }> = {
  pending:       { bg: "bg-amber-100 text-amber-700",  label: "Pending",       Icon: Clock },
  submitted:     { bg: "bg-blue-100 text-blue-700",    label: "Submitted",     Icon: RefreshCw },
  cleared:       { bg: "bg-green-100 text-green-700",  label: "Cleared",       Icon: CheckCircle },
  rejected:      { bg: "bg-red-100 text-red-700",      label: "Rejected",      Icon: XCircle },
  not_submitted: { bg: "bg-gray-100 text-gray-600",    label: "Not Submitted", Icon: AlertTriangle },
};

export default function ZatcaDashboardPage() {
  const router = useRouter();
  const params = useParams();
  const locale = params.locale as string;

  const [dashboard, setDashboard] = useState<Dashboard | null>(null);
  const [records, setRecords] = useState<ZatcaRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [invoiceId, setInvoiceId] = useState("");
  const [generating, setGenerating] = useState(false);
  const [totalRecords, setTotalRecords] = useState(0);
  const [page, setPage] = useState(1);

  async function loadAll() {
    setLoading(true);
    try {
      const [dash, list] = await Promise.all([
        api.get("/api/mena/zatca/dashboard"),
        api.get(`/api/mena/zatca/list?page=${page}&limit=20`),
      ]);
      setDashboard(dash);
      setRecords(list.records ?? []);
      setTotalRecords(list.total ?? 0);
    } catch (err: any) {
      if (err?.status === 401) router.push(`/${locale}/auth/login`);
      else toast.error("Failed to load ZATCA data");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { loadAll(); }, [page]);

  async function generate() {
    if (!invoiceId.trim()) return toast.error("Enter an invoice ID");
    setGenerating(true);
    try {
      const result = await api.post(`/api/mena/zatca/generate/${invoiceId.trim()}`, {});
      toast.success(`ZATCA record generated. Hash: ${result.invoice_hash.slice(0, 16)}…`);
      setInvoiceId("");
      loadAll();
    } catch {
      toast.error("Failed to generate ZATCA record — check invoice ID");
    } finally {
      setGenerating(false);
    }
  }

  async function downloadXml(invoiceId: string) {
    try {
      await api.downloadBlob(`/api/mena/zatca/${invoiceId}/xml`, `zatca-${invoiceId}.xml`);
    } catch {
      toast.error("Failed to download XML");
    }
  }

  const summary = dashboard?.summary;

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">ZATCA E-Invoicing</h1>
          <p className="text-sm text-muted-foreground mt-1">
            Saudi Arabia — ZATCA Phase 2 compliance dashboard
          </p>
        </div>
        {loading && <RefreshCw className="h-4 w-4 animate-spin text-muted-foreground" />}
      </div>

      {/* Compliance summary cards */}
      {summary && (
        <div className="grid grid-cols-2 sm:grid-cols-5 gap-4">
          {[
            { key: "cleared",       label: "Cleared",       value: summary.cleared },
            { key: "submitted",     label: "Submitted",     value: summary.submitted },
            { key: "pending",       label: "Pending",       value: summary.pending },
            { key: "rejected",      label: "Rejected",      value: summary.rejected },
            { key: "not_submitted", label: "Not Submitted", value: summary.not_submitted },
          ].map(({ key, label, value }) => {
            const s = STATUS_STYLE[key];
            const Icon = s?.Icon ?? BarChart3;
            return (
              <div key={key} className="rounded-2xl border bg-card p-4">
                <div className="flex items-center gap-2 mb-1">
                  <Icon className="h-4 w-4 text-muted-foreground" />
                  <p className="text-xs text-muted-foreground">{label}</p>
                </div>
                <p className="text-2xl font-bold">{value}</p>
              </div>
            );
          })}
        </div>
      )}

      {/* Rejection warning */}
      {summary && summary.rejected > 0 && (
        <div className="flex items-center gap-3 p-4 rounded-2xl bg-red-50 border border-red-200 text-red-800">
          <XCircle className="h-5 w-5 flex-shrink-0" />
          <p className="text-sm font-medium">
            {summary.rejected} invoice{summary.rejected !== 1 ? "s" : ""} rejected by ZATCA — review and resubmit
          </p>
        </div>
      )}

      {/* Generate for invoice */}
      <div className="rounded-2xl border bg-card p-5">
        <h3 className="font-semibold mb-3">Generate ZATCA Record</h3>
        <p className="text-sm text-muted-foreground mb-4">
          Generate a ZATCA Phase 2 UBL XML document and TLV QR code for an invoice.
          Requires PRO plan.
        </p>
        <div className="flex gap-3">
          <input
            className="input flex-1"
            placeholder="Invoice UUID"
            value={invoiceId}
            onChange={e => setInvoiceId(e.target.value)}
            onKeyDown={e => e.key === "Enter" && generate()}
          />
          <button
            className="btn-primary flex items-center gap-2"
            onClick={generate}
            disabled={generating}
          >
            {generating ? <RefreshCw className="h-4 w-4 animate-spin" /> : <Search className="h-4 w-4" />}
            Generate
          </button>
        </div>
      </div>

      {/* CSID notice */}
      <div className="rounded-2xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-900">
        <p className="font-medium mb-1">Clearance mode — CSID required</p>
        <p className="text-amber-800">
          Real-time ZATCA clearance requires a per-company Cryptographic Stamp Identifier (CSID)
          issued by ZATCA. XML and QR code generation works without a CSID. Complete ZATCA onboarding
          at <span className="font-mono">zatca.gov.sa</span> and configure your certificate to enable live clearance.
        </p>
      </div>

      {/* Records list */}
      {loading ? (
        <div className="flex justify-center py-16">
          <RefreshCw className="h-6 w-6 animate-spin text-muted-foreground" />
        </div>
      ) : records.length === 0 ? (
        <div className="rounded-2xl border bg-card flex flex-col items-center justify-center py-20 text-center">
          <FileCheck2 className="h-12 w-12 text-muted-foreground mb-4" />
          <p className="font-medium">No ZATCA records yet</p>
          <p className="text-sm text-muted-foreground mt-1">Generate records for invoices to see them here</p>
        </div>
      ) : (
        <div className="rounded-2xl border bg-card overflow-hidden">
          <div className="px-4 py-3 border-b flex items-center justify-between">
            <h3 className="font-semibold text-sm">Invoice Records</h3>
            <span className="text-xs text-muted-foreground">{totalRecords} total</span>
          </div>
          <div className="divide-y">
            {records.map(r => {
              const s = STATUS_STYLE[r.clearance_status] ?? STATUS_STYLE.pending;
              const SIcon = s.Icon;
              return (
                <div key={r.id} className="flex items-center gap-4 px-4 py-3 hover:bg-muted/20">
                  <SIcon className="h-4 w-4 text-muted-foreground flex-shrink-0" />
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-mono truncate">{r.invoice_id}</p>
                    <p className="text-xs text-muted-foreground font-mono">{r.invoice_hash.slice(0, 32)}…</p>
                  </div>
                  <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${s.bg}`}>
                    {s.label}
                  </span>
                  <span className="text-xs text-muted-foreground">
                    {new Date(r.created_at).toLocaleDateString("sv-SE")}
                  </span>
                  <button
                    className="btn-secondary text-xs flex items-center gap-1"
                    onClick={() => downloadXml(r.invoice_id)}
                  >
                    <Download className="h-3 w-3" /> XML
                  </button>
                </div>
              );
            })}
          </div>
          {totalRecords > 20 && (
            <div className="flex justify-center gap-2 p-3 border-t">
              <button className="btn-secondary text-xs" disabled={page === 1} onClick={() => setPage(p => p - 1)}>Previous</button>
              <span className="text-xs text-muted-foreground self-center">Page {page}</span>
              <button className="btn-secondary text-xs" disabled={page * 20 >= totalRecords} onClick={() => setPage(p => p + 1)}>Next</button>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
