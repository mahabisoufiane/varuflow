"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { createClient } from "@/lib/supabase/client";
import { FlaskConical, RefreshCw, Trash2, Play, RotateCcw, ExternalLink } from "lucide-react";
import { Button } from "@/components/ui/button";
import { toast } from "sonner";

interface SandboxStatus {
  is_sandbox: boolean;
  sandbox_org_id: string | null;
  production_org_id: string;
  demo_stats: { products: number; customers: number; invoices: number } | null;
}

export default function SandboxPage() {
  const [status, setStatus] = useState<SandboxStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState<string | null>(null);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const router = useRouter();
  const supabase = createClient();

  async function getToken() {
    const { data: { session } } = await supabase.auth.getSession();
    return session?.access_token ?? null;
  }
  function apiUrl(path: string) { return `${process.env.NEXT_PUBLIC_API_URL}${path}`; }

  async function loadStatus() {
    setLoading(true);
    try {
      const token = await getToken();
      if (!token) { router.push("/auth/login"); return; }
      const res = await fetch(apiUrl("/api/sandbox/status"), {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (res.status === 401) { router.push("/auth/login"); return; }
      if (!res.ok) { toast.error("Failed to load sandbox status"); return; }
      setStatus(await res.json());
    } catch {
      toast.error("Something went wrong. Please try again.");
    } finally {
      setLoading(false);
    }
  }

  async function createSandbox() {
    setActionLoading("create");
    try {
      const token = await getToken();
      if (!token) return;
      const res = await fetch(apiUrl("/api/sandbox/create"), {
        method: "POST",
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) {
        const b = await res.json().catch(() => ({}));
        toast.error(b.detail ?? "Failed to create sandbox");
        return;
      }
      toast.success("Sandbox created with demo data");
      await loadStatus();
    } catch {
      toast.error("Something went wrong. Please try again.");
    } finally {
      setActionLoading(null);
    }
  }

  async function resetSandbox() {
    setActionLoading("reset");
    try {
      const token = await getToken();
      if (!token) return;
      const res = await fetch(apiUrl("/api/sandbox/reset"), {
        method: "POST",
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) {
        const b = await res.json().catch(() => ({}));
        toast.error(b.detail ?? "Failed to reset sandbox");
        return;
      }
      toast.success("Sandbox reset with fresh demo data");
      await loadStatus();
    } catch {
      toast.error("Something went wrong. Please try again.");
    } finally {
      setActionLoading(null);
    }
  }

  async function deleteSandbox() {
    setActionLoading("delete");
    try {
      const token = await getToken();
      if (!token) return;
      const res = await fetch(apiUrl("/api/sandbox"), {
        method: "DELETE",
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) {
        const b = await res.json().catch(() => ({}));
        toast.error(b.detail ?? "Failed to delete sandbox");
        return;
      }
      toast.success("Sandbox deleted");
      setConfirmDelete(false);
      await loadStatus();
    } catch {
      toast.error("Something went wrong. Please try again.");
    } finally {
      setActionLoading(null);
    }
  }

  useEffect(() => { loadStatus(); }, []);  // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <div className="mx-auto max-w-2xl space-y-6 p-6">
      <div>
        <h1 className="text-xl font-semibold text-gray-900 flex items-center gap-2">
          <FlaskConical className="h-5 w-5" /> Sandbox / Demo Mode
        </h1>
        <p className="text-sm text-muted-foreground mt-0.5">
          A sandbox is a separate copy of your organisation pre-filled with realistic demo data.
          Explore features safely without touching production records.
        </p>
      </div>

      {loading && !status ? (
        <div className="rounded-xl border bg-white p-8 text-center">
          <RefreshCw className="h-6 w-6 animate-spin mx-auto text-muted-foreground" />
        </div>
      ) : status?.sandbox_org_id ? (
        /* ── Sandbox exists ── */
        <div className="space-y-4">
          <div className="rounded-xl border bg-white p-6 shadow-sm space-y-4">
            <div className="flex items-center justify-between">
              <p className="text-sm font-semibold text-gray-900">Sandbox Active</p>
              <span className="inline-flex items-center gap-1.5 rounded-full bg-green-100 px-2.5 py-0.5 text-xs font-medium text-green-700">
                <span className="h-1.5 w-1.5 rounded-full bg-green-500" /> Live
              </span>
            </div>

            {status.demo_stats && (
              <div className="grid grid-cols-3 gap-4">
                {[
                  { label: "Products",  value: status.demo_stats.products  },
                  { label: "Customers", value: status.demo_stats.customers },
                  { label: "Invoices",  value: status.demo_stats.invoices  },
                ].map(({ label, value }) => (
                  <div key={label} className="rounded-lg bg-gray-50 border px-4 py-3 text-center">
                    <p className="text-2xl font-bold text-gray-900">{value}</p>
                    <p className="text-xs text-muted-foreground">{label}</p>
                  </div>
                ))}
              </div>
            )}

            <p className="text-xs text-muted-foreground">
              Org ID: <span className="font-mono">{status.sandbox_org_id}</span>
            </p>
          </div>

          <div className="rounded-xl border bg-white p-6 shadow-sm space-y-3">
            <p className="text-sm font-semibold text-gray-900">Actions</p>

            <div className="flex flex-col gap-2 sm:flex-row">
              <Button
                variant="outline"
                className="flex-1 gap-2"
                disabled={actionLoading === "reset"}
                onClick={resetSandbox}
              >
                {actionLoading === "reset"
                  ? <RefreshCw className="h-4 w-4 animate-spin" />
                  : <RotateCcw className="h-4 w-4" />}
                Reset Demo Data
              </Button>

              <Button
                variant="outline"
                className="flex-1 gap-2"
                asChild
              >
                <a href="/dashboard" target="_blank">
                  <ExternalLink className="h-4 w-4" />
                  Open Sandbox
                </a>
              </Button>
            </div>

            <div className="border-t pt-3">
              {!confirmDelete ? (
                <Button
                  variant="outline"
                  className="w-full border-red-200 text-red-600 hover:bg-red-50 gap-2"
                  onClick={() => setConfirmDelete(true)}
                >
                  <Trash2 className="h-4 w-4" />
                  Delete Sandbox
                </Button>
              ) : (
                <div className="space-y-2">
                  <p className="text-sm text-red-600 font-medium text-center">
                    Are you sure? This will permanently delete all sandbox data.
                  </p>
                  <div className="flex gap-2">
                    <Button variant="outline" className="flex-1" onClick={() => setConfirmDelete(false)}>
                      Cancel
                    </Button>
                    <Button
                      className="flex-1 bg-red-600 hover:bg-red-700 text-white gap-2"
                      disabled={actionLoading === "delete"}
                      onClick={deleteSandbox}
                    >
                      {actionLoading === "delete"
                        ? <RefreshCw className="h-4 w-4 animate-spin" />
                        : <Trash2 className="h-4 w-4" />}
                      Delete
                    </Button>
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      ) : (
        /* ── No sandbox yet ── */
        <div className="rounded-xl border bg-white p-8 shadow-sm space-y-5 text-center">
          <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-full bg-blue-100">
            <FlaskConical className="h-7 w-7 text-blue-600" />
          </div>
          <div>
            <h2 className="text-base font-semibold text-gray-900">No Sandbox Yet</h2>
            <p className="mt-1 text-sm text-muted-foreground max-w-sm mx-auto">
              Create a sandbox to get a pre-populated demo environment with 8 products, 5 customers, and 5 invoices in different states.
            </p>
          </div>

          <ul className="text-left space-y-2 max-w-xs mx-auto">
            {[
              "8 demo products (furniture, electronics, office)",
              "5 customers (Bergström, Nilsson, Lindqvist…)",
              "5 invoices: paid, sent, overdue, draft",
              "2 demo suppliers",
            ].map((item) => (
              <li key={item} className="flex items-start gap-2 text-sm text-gray-600">
                <span className="mt-1 h-1.5 w-1.5 rounded-full bg-blue-400 flex-shrink-0" />
                {item}
              </li>
            ))}
          </ul>

          <Button
            className="bg-[var(--vf-brand-primary)] hover:bg-[var(--vf-brand-primary-hover)] text-white gap-2"
            disabled={actionLoading === "create"}
            onClick={createSandbox}
          >
            {actionLoading === "create"
              ? <RefreshCw className="h-4 w-4 animate-spin" />
              : <Play className="h-4 w-4" />}
            Create Sandbox
          </Button>
        </div>
      )}

      <div className="rounded-xl border bg-amber-50 border-amber-200 px-5 py-4">
        <p className="text-sm text-amber-800">
          <strong>Note:</strong> The sandbox is a completely separate organisation. Your production data is never affected.
          Switch between orgs from the organisation selector in the top navigation.
        </p>
      </div>
    </div>
  );
}
