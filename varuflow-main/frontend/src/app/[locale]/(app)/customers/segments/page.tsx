"use client";

import { api } from "@/lib/api-client";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Link } from "@/i18n/navigation";
import { useEffect, useState } from "react";
import { Users, Plus, RefreshCw, Download } from "lucide-react";
import { toast } from "sonner";
import styles from "./page.module.scss";

interface Segment {
  id: string;
  name: string;
  description: string | null;
  type: "AUTO" | "MANUAL";
  rules: Record<string, unknown>;
  customer_count: number;
  last_computed_at: string | null;
  created_at: string;
}

export default function SegmentsListPage() {
  const [rows, setRows] = useState<Segment[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState<string | null>(null);

  async function load() {
    try {
      setRows(await api.get<Segment[]>("/api/segments"));
    } catch (e: any) {
      toast.error(e.message);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
  }, []);

  async function refresh(id: string) {
    setRefreshing(id);
    try {
      await api.post(`/api/segments/${id}/refresh`, {});
      toast.success("Segment refreshed");
      await load();
    } catch (e: any) {
      toast.error(e.message);
    } finally {
      setRefreshing(null);
    }
  }

  function exportCsv(id: string) {
    window.open(api.downloadUrl(`/api/segments/${id}/export.csv`), "_blank");
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-[var(--vf-text-primary)]">Customer Segments</h1>
          <p className="text-sm text-muted-foreground">
            {rows.length} segment{rows.length === 1 ? "" : "s"}
          </p>
        </div>
        <Button asChild size="sm" className="bg-[var(--vf-brand-primary)] hover:bg-[var(--vf-brand-primary-hover)] text-white">
          <Link href="/customers/segments/new">
            <Plus className="mr-1.5 h-3.5 w-3.5" />
            New segment
          </Link>
        </Button>
      </div>

      {loading ? (
        <div className="space-y-2 animate-pulse">
          {[1, 2, 3].map((i) => (
            <div key={i} className="h-16 rounded-xl bg-gray-100" />
          ))}
        </div>
      ) : rows.length === 0 ? (
        <div className="rounded-xl border bg-white px-6 py-12 text-center">
          <Users className="mx-auto h-10 w-10 text-gray-300" />
          <h3 className="mt-3 font-medium text-gray-900">No segments yet</h3>
          <p className="mt-1 text-sm text-muted-foreground">
            Group customers by rules or pick them manually to target campaigns.
          </p>
          <Button
            asChild
            size="sm"
            className="mt-4 bg-[var(--vf-brand-primary)] hover:bg-[var(--vf-brand-primary-hover)] text-white"
          >
            <Link href="/customers/segments/new">
              <Plus className="mr-1.5 h-3.5 w-3.5" />
              New segment
            </Link>
          </Button>
        </div>
      ) : (
        <div className="rounded-xl border bg-white overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-gray-50 text-xs uppercase text-gray-500">
              <tr>
                <th className="px-4 py-2 text-left">Name</th>
                <th className="px-4 py-2 text-left">Type</th>
                <th className="px-4 py-2 text-right">Members</th>
                <th className="px-4 py-2 text-left">Last computed</th>
                <th className="px-4 py-2"></th>
              </tr>
            </thead>
            <tbody>
              {rows.map((s) => (
                <tr key={s.id} className="border-t">
                  <td className="px-4 py-2">
                    <Link href={`/customers/segments/${s.id}`} className="font-medium text-[var(--vf-text-primary)] hover:underline">
                      {s.name}
                    </Link>
                    {s.description && (
                      <div className="text-xs text-gray-500">{s.description}</div>
                    )}
                  </td>
                  <td className="px-4 py-2">
                    <span className={styles[s.type === "AUTO" ? "typeAuto" : "typeManual"]}>
                      {s.type}
                    </span>
                  </td>
                  <td className="px-4 py-2 text-right tabular-nums">
                    {s.customer_count}
                  </td>
                  <td className="px-4 py-2 text-xs text-gray-500">
                    {s.last_computed_at
                      ? new Date(s.last_computed_at).toLocaleString()
                      : "—"}
                  </td>
                  <td className="px-4 py-2 text-right">
                    <div className="inline-flex gap-1">
                      {s.type === "AUTO" && (
                        <button
                          type="button"
                          onClick={() => refresh(s.id)}
                          disabled={refreshing === s.id}
                          className="inline-flex items-center gap-1 rounded border px-2 py-1 text-xs hover:bg-gray-50"
                        >
                          <RefreshCw className="h-3 w-3" />
                          {refreshing === s.id ? "…" : "Refresh"}
                        </button>
                      )}
                      <button
                        type="button"
                        onClick={() => exportCsv(s.id)}
                        className="inline-flex items-center gap-1 rounded border px-2 py-1 text-xs hover:bg-gray-50"
                      >
                        <Download className="h-3 w-3" />
                        CSV
                      </button>
                    </div>
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
