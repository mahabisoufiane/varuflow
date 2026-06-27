"use client";

/**
 * Analytics → Commissions (Item 32)
 *
 * Admin view of commission runs (monthly periods) with per-staff
 * totals. Supports creating a new run, locking, and CSV/PDF export.
 *
 * Wires: GET/POST /api/commissions/runs, GET /runs/{id},
 *        POST /runs/{id}/lock, GET /runs/{id}/export.{csv,pdf}
 */
import { useCallback, useEffect, useState } from "react";
import { useTranslations } from "next-intl";
import { toast } from "sonner";
import { BadgeDollarSign, Loader2, Lock, Download, Plus } from "lucide-react";

import { api } from "@/lib/api-client";

interface CommissionRun {
  id: string;
  period_start: string;
  period_end: string;
  status: "open" | "locked" | "paid";
  total_paid: string;
  locked_at: string | null;
}

interface CommissionEntry {
  id: string;
  staff_id: string;
  source_type: string;
  source_id: string;
  base_amount: string;
  commission_amount: string;
  created_at: string;
}

interface RunDetail extends CommissionRun {
  entries: CommissionEntry[];
}

export default function CommissionsAnalyticsPage() {
  const t = useTranslations("commissions");
  const [runs, setRuns] = useState<CommissionRun[]>([]);
  const [selected, setSelected] = useState<RunDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [creating, setCreating] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const data = await api.get<CommissionRun[]>("/api/commissions/runs");
      setRuns(data);
    } catch (err) {
      toast.error(t("load_runs_failed"));
    } finally {
      setLoading(false);
    }
  }, [t]);

  useEffect(() => {
    load();
  }, [load]);

  const createRun = async () => {
    const today = new Date();
    const first = new Date(today.getFullYear(), today.getMonth() - 1, 1);
    const last = new Date(today.getFullYear(), today.getMonth(), 0);
    setCreating(true);
    try {
      await api.post("/api/commissions/runs", {
        period_start: first.toISOString().slice(0, 10),
        period_end: last.toISOString().slice(0, 10),
      });
      toast.success(t("run_created"));
      await load();
    } catch (err) {
      toast.error(t("create_run_failed"));
    } finally {
      setCreating(false);
    }
  };

  const openRun = async (id: string) => {
    try {
      const data = await api.get<RunDetail>(`/api/commissions/runs/${id}`);
      setSelected(data);
    } catch {
      toast.error(t("load_run_failed"));
    }
  };

  const lockRun = async (id: string) => {
    try {
      await api.post(`/api/commissions/runs/${id}/lock`, {});
      toast.success(t("run_locked"));
      await load();
      if (selected?.id === id) await openRun(id);
    } catch {
      toast.error(t("lock_failed"));
    }
  };

  const exportCsv = (id: string) => {
    window.open(`/api/commissions/runs/${id}/export.csv`, "_blank");
  };

  const exportPdf = (id: string) => {
    window.open(`/api/commissions/runs/${id}/export.pdf`, "_blank");
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center p-12">
        <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
      </div>
    );
  }

  return (
    <div className="container mx-auto p-6 space-y-6">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <BadgeDollarSign className="h-6 w-6" />
          <h1 className="text-2xl font-semibold">{t("analytics_title")}</h1>
        </div>
        <button
          onClick={createRun}
          disabled={creating}
          className="inline-flex items-center gap-1 rounded bg-primary text-primary-foreground px-3 py-1.5 text-sm"
        >
          {creating ? <Loader2 className="h-4 w-4 animate-spin" /> : <Plus className="h-4 w-4" />}
          {t("create_run")}
        </button>
      </div>

      <div className="rounded-lg border">
        <table className="w-full text-sm">
          <thead className="bg-muted">
            <tr>
              <th className="text-left p-2">{t("col_period")}</th>
              <th className="text-left p-2">{t("col_status")}</th>
              <th className="text-right p-2">{t("col_total")}</th>
              <th className="p-2" />
            </tr>
          </thead>
          <tbody>
            {runs.length === 0 && (
              <tr>
                <td colSpan={4} className="p-4 text-center text-muted-foreground">
                  {t("no_runs")}
                </td>
              </tr>
            )}
            {runs.map((r) => (
              <tr key={r.id} className="border-t hover:bg-muted/50">
                <td className="p-2">
                  <button onClick={() => openRun(r.id)} className="hover:underline">
                    {r.period_start} → {r.period_end}
                  </button>
                </td>
                <td className="p-2">{t(`status_${r.status}`)}</td>
                <td className="p-2 text-right">{r.total_paid}</td>
                <td className="p-2 text-right space-x-2">
                  {r.status === "open" && (
                    <button
                      onClick={() => lockRun(r.id)}
                      className="inline-flex items-center gap-1 text-xs text-amber-700 hover:underline"
                    >
                      <Lock className="h-3.5 w-3.5" />
                      {t("lock")}
                    </button>
                  )}
                  <button
                    onClick={() => exportCsv(r.id)}
                    className="inline-flex items-center gap-1 text-xs hover:underline"
                  >
                    <Download className="h-3.5 w-3.5" />
                    CSV
                  </button>
                  <button
                    onClick={() => exportPdf(r.id)}
                    className="inline-flex items-center gap-1 text-xs hover:underline"
                  >
                    <Download className="h-3.5 w-3.5" />
                    PDF
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {selected && (
        <div className="rounded-lg border p-4">
          <h2 className="font-medium mb-2">
            {t("run_entries")} ({selected.period_start} → {selected.period_end})
          </h2>
          <table className="w-full text-sm">
            <thead className="bg-muted">
              <tr>
                <th className="text-left p-2">{t("col_staff")}</th>
                <th className="text-left p-2">{t("col_source")}</th>
                <th className="text-right p-2">{t("col_base")}</th>
                <th className="text-right p-2">{t("col_commission")}</th>
              </tr>
            </thead>
            <tbody>
              {selected.entries.length === 0 && (
                <tr>
                  <td colSpan={4} className="p-4 text-center text-muted-foreground">
                    {t("no_entries")}
                  </td>
                </tr>
              )}
              {selected.entries.map((e) => (
                <tr key={e.id} className="border-t">
                  <td className="p-2">{e.staff_id.slice(0, 8)}</td>
                  <td className="p-2">{e.source_type}</td>
                  <td className="p-2 text-right">{e.base_amount}</td>
                  <td className="p-2 text-right">{e.commission_amount}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
