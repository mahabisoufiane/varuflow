"use client";

import { api } from "@/lib/api-client";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { useParams, useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";
import { ArrowLeft, RefreshCw, Download, Trash2, Plus, Users } from "lucide-react";
import styles from "./page.module.scss";

interface Segment {
  id: string;
  name: string;
  description: string | null;
  type: "AUTO" | "MANUAL";
  rules: Record<string, unknown>;
  customer_count: number;
  last_computed_at: string | null;
}

interface Member {
  customer_id: string;
  company_name: string;
  email: string | null;
  added_at: string;
}

interface Customer {
  id: string;
  company_name: string;
}

export default function SegmentDetailPage() {
  const params = useParams();
  const router = useRouter();
  const id = String(params?.id ?? "");
  const [seg, setSeg] = useState<Segment | null>(null);
  const [members, setMembers] = useState<Member[]>([]);
  const [customers, setCustomers] = useState<Customer[]>([]);
  const [picker, setPicker] = useState("");
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    try {
      const [s, m] = await Promise.all([
        api.get<Segment>(`/api/segments/${id}`),
        api.get<Member[]>(`/api/segments/${id}/members`),
      ]);
      setSeg(s);
      setMembers(m);
    } catch (e: any) {
      toast.error(e.message);
    }
  }, [id]);

  useEffect(() => {
    if (id) load();
  }, [id, load]);

  useEffect(() => {
    if (seg?.type === "MANUAL") {
      api
        .get<Customer[]>("/api/invoicing/customers")
        .then(setCustomers)
        .catch(() => {
          /* non-fatal */
        });
    }
  }, [seg?.type]);

  async function addMember() {
    if (!picker) return;
    setBusy(true);
    try {
      await api.post(`/api/segments/${id}/members`, { customer_id: picker });
      setPicker("");
      await load();
    } catch (e: any) {
      toast.error(e.message);
    } finally {
      setBusy(false);
    }
  }

  async function removeMember(customerId: string) {
    setBusy(true);
    try {
      await api.delete(`/api/segments/${id}/members/${customerId}`);
      await load();
    } catch (e: any) {
      toast.error(e.message);
    } finally {
      setBusy(false);
    }
  }

  async function refresh() {
    setBusy(true);
    try {
      await api.post(`/api/segments/${id}/refresh`, {});
      toast.success("Refreshed");
      await load();
    } catch (e: any) {
      toast.error(e.message);
    } finally {
      setBusy(false);
    }
  }

  async function deleteSegment() {
    if (!confirm("Delete this segment?")) return;
    setBusy(true);
    try {
      await api.delete(`/api/segments/${id}`);
      toast.success("Deleted");
      router.push("/customers/segments");
    } catch (e: any) {
      toast.error(e.message);
    } finally {
      setBusy(false);
    }
  }

  function exportCsv() {
    window.open(api.downloadUrl(`/api/segments/${id}/export.csv`), "_blank");
  }

  if (!seg) {
    return <div className="text-sm text-gray-500">Loading…</div>;
  }

  return (
    <div className="space-y-6 max-w-4xl">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Button variant="ghost" size="sm" onClick={() => router.back()}>
            <ArrowLeft className="h-4 w-4" />
          </Button>
          <div>
            <h1 className="text-2xl font-bold text-[var(--vf-text-primary)] flex items-center gap-2">
              <Users className="h-5 w-5" /> {seg.name}
            </h1>
            <p className="text-xs text-gray-500">
              {seg.customer_count} members
              {seg.last_computed_at
                ? ` · refreshed ${new Date(seg.last_computed_at).toLocaleString()}`
                : ""}
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <span
            className={styles[seg.type === "AUTO" ? "typeAuto" : "typeManual"]}
          >
            {seg.type}
          </span>
          {seg.type === "AUTO" && (
            <Button variant="outline" size="sm" onClick={refresh} disabled={busy}>
              <RefreshCw className="mr-1.5 h-3.5 w-3.5" />
              Refresh
            </Button>
          )}
          <Button variant="outline" size="sm" onClick={exportCsv}>
            <Download className="mr-1.5 h-3.5 w-3.5" />
            Export CSV
          </Button>
          <Button
            variant="outline"
            size="sm"
            onClick={deleteSegment}
            disabled={busy}
            className="text-red-600 hover:text-red-700"
          >
            <Trash2 className="mr-1.5 h-3.5 w-3.5" />
            Delete
          </Button>
        </div>
      </div>

      {seg.description && (
        <div className="rounded-xl border bg-white p-4 text-sm">
          {seg.description}
        </div>
      )}

      {seg.type === "AUTO" && (
        <div className="rounded-xl border bg-white p-4">
          <div className="text-xs uppercase text-gray-500 mb-1">Rule</div>
          <pre className="text-xs font-mono bg-gray-50 rounded p-3 overflow-x-auto">
            {JSON.stringify(seg.rules, null, 2)}
          </pre>
        </div>
      )}

      {seg.type === "MANUAL" && (
        <div className="rounded-xl border bg-white p-4 space-y-2">
          <div className="text-sm font-medium">Add customer</div>
          <div className="flex gap-2">
            <select
              className="flex-1 rounded border px-3 py-2 text-sm"
              value={picker}
              onChange={(e) => setPicker(e.target.value)}
            >
              <option value="">Select customer…</option>
              {customers.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.company_name}
                </option>
              ))}
            </select>
            <Button
              onClick={addMember}
              disabled={busy || !picker}
              className="bg-[var(--vf-brand-primary)] hover:bg-[var(--vf-brand-primary-hover)] text-white"
            >
              <Plus className="mr-1.5 h-3.5 w-3.5" />
              Add
            </Button>
          </div>
        </div>
      )}

      <div className="rounded-xl border bg-white overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-gray-50 text-xs uppercase text-gray-500">
            <tr>
              <th className="px-4 py-2 text-left">Company</th>
              <th className="px-4 py-2 text-left">Email</th>
              <th className="px-4 py-2 text-left">Added</th>
              <th className="px-4 py-2"></th>
            </tr>
          </thead>
          <tbody>
            {members.length === 0 ? (
              <tr>
                <td colSpan={4} className="px-4 py-6 text-center text-sm text-gray-500">
                  No members yet
                </td>
              </tr>
            ) : (
              members.map((m) => (
                <tr key={m.customer_id} className="border-t">
                  <td className="px-4 py-2">{m.company_name}</td>
                  <td className="px-4 py-2 text-xs text-gray-600">{m.email ?? "—"}</td>
                  <td className="px-4 py-2 text-xs text-gray-500">
                    {new Date(m.added_at).toLocaleString()}
                  </td>
                  <td className="px-4 py-2 text-right">
                    {seg.type === "MANUAL" && (
                      <button
                        type="button"
                        onClick={() => removeMember(m.customer_id)}
                        disabled={busy}
                        className="text-xs text-red-600 hover:underline"
                      >
                        Remove
                      </button>
                    )}
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
