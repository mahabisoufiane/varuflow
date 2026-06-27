"use client";

import { useEffect, useState } from "react";
import { useRouter, useParams } from "next/navigation";
import { createClient } from "@/lib/supabase/client";
import { Eye, RefreshCw, ChevronDown, ChevronRight, Info } from "lucide-react";
import { Button } from "@/components/ui/button";
import { toast } from "sonner";

interface Report {
  id: string;
  category: string;
  status: string;
  is_anonymous: boolean;
  submitted_at: string;
  description: string | null;
  resolution_notes: string | null;
  assignee: string | null;
}

const STATUS_COLORS: Record<string, string> = {
  new:          "bg-red-100 text-red-700",
  under_review: "bg-amber-100 text-amber-700",
  resolved:     "bg-green-100 text-green-700",
  dismissed:    "bg-gray-100 text-gray-600",
};

type TabKey = "all" | "new" | "under_review" | "resolved";
const TABS: { key: TabKey; label: string }[] = [
  { key: "all", label: "All" },
  { key: "new", label: "New" },
  { key: "under_review", label: "Under Review" },
  { key: "resolved", label: "Resolved" },
];

export default function WhistleblowerPage() {
  const router = useRouter();
  const params = useParams<{ locale: string }>();
  const locale = params?.locale ?? "en";
  const supabase = createClient();

  const [reports, setReports] = useState<Report[]>([]);
  const [loading, setLoading] = useState(true);
  const [tab, setTab] = useState<TabKey>("all");
  const [expanded, setExpanded] = useState<Set<string>>(new Set());
  const [editing, setEditing] = useState<Record<string, { status: string; notes: string }>>({});
  const [actionLoading, setActionLoading] = useState<string | null>(null);

  async function getToken() {
    const { data: { session } } = await supabase.auth.getSession();
    return session?.access_token ?? null;
  }
  function apiUrl(p: string) { return `${process.env.NEXT_PUBLIC_API_URL}${p}`; }

  async function load() {
    setLoading(true);
    try {
      const token = await getToken();
      if (!token) { router.push(`/${locale}/auth/login`); return; }
      const res = await fetch(apiUrl("/api/whistleblower/reports"), { headers: { Authorization: `Bearer ${token}` } });
      if (res.status === 401) { router.push(`/${locale}/auth/login`); return; }
      if (res.ok) setReports(await res.json());
    } catch {
      toast.error("Failed to load whistleblower reports");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { load(); }, []);  // eslint-disable-line react-hooks/exhaustive-deps

  function toggle(id: string, report: Report) {
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(id)) {
        next.delete(id);
      } else {
        next.add(id);
        if (!editing[id]) {
          setEditing((e) => ({ ...e, [id]: { status: report.status, notes: report.resolution_notes ?? "" } }));
        }
      }
      return next;
    });
  }

  async function saveReport(id: string) {
    const data = editing[id];
    if (!data) return;
    setActionLoading(id + "_save");
    try {
      const token = await getToken();
      if (!token) return;
      const res = await fetch(apiUrl(`/api/whistleblower/reports/${id}`), {
        method: "PATCH",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
        body: JSON.stringify({ status: data.status, resolution_notes: data.notes || null }),
      });
      if (!res.ok) {
        const b = await res.json().catch(() => ({}));
        toast.error(b.detail ?? "Failed to update report");
        return;
      }
      toast.success("Report updated");
      await load();
    } catch {
      toast.error("Something went wrong");
    } finally {
      setActionLoading(null);
    }
  }

  const filtered = tab === "all" ? reports : reports.filter((r) => r.status === tab);
  const newCount = reports.filter((r) => r.status === "new").length;

  return (
    <div className="mx-auto max-w-4xl space-y-6 p-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-gray-900">Whistleblower Reports</h1>
          <p className="text-sm text-muted-foreground mt-0.5">Review and manage anonymous reports from your team.</p>
        </div>
      </div>

      {/* Info banner */}
      <div className="flex items-start gap-3 rounded-xl border border-blue-200 bg-blue-50 px-4 py-3">
        <Info className="h-4 w-4 text-blue-600 flex-shrink-0 mt-0.5" />
        <p className="text-sm text-blue-800">
          The public submission URL for your organisation is available — share it with your team so they can submit reports anonymously.
        </p>
      </div>

      {/* Tabs */}
      <div className="flex items-center gap-1 border-b">
        {TABS.map((t) => (
          <button key={t.key} type="button" onClick={() => setTab(t.key)}
            className={`px-4 py-2.5 text-sm font-medium border-b-2 transition-colors flex items-center gap-2 ${
              tab === t.key ? "border-[#1a2332] text-[#1a2332]" : "border-transparent text-muted-foreground hover:text-gray-700"
            }`}>
            {t.label}
            {t.key === "new" && newCount > 0 && (
              <span className="inline-flex items-center justify-center h-4 min-w-4 rounded-full bg-red-600 text-white text-xs px-1">
                {newCount}
              </span>
            )}
          </button>
        ))}
      </div>

      {/* Reports */}
      {loading && reports.length === 0 ? (
        <div className="text-center py-12"><RefreshCw className="h-6 w-6 animate-spin mx-auto text-muted-foreground" /></div>
      ) : filtered.length === 0 ? (
        <div className="rounded-xl border bg-white p-12 text-center shadow-sm">
          <Eye className="h-10 w-10 text-muted-foreground mx-auto mb-3" />
          <p className="text-gray-600 font-medium">No reports in this category</p>
        </div>
      ) : (
        <div className="rounded-xl border bg-white shadow-sm divide-y divide-gray-100">
          {filtered.map((report) => {
            const isExpanded = expanded.has(report.id);
            const ed = editing[report.id];
            return (
              <div key={report.id}>
                <div className="flex items-center gap-3 px-5 py-4 cursor-pointer hover:bg-gray-50 transition-colors"
                  onClick={() => toggle(report.id, report)}>
                  <div className="flex-shrink-0">
                    {isExpanded
                      ? <ChevronDown className="h-4 w-4 text-muted-foreground" />
                      : <ChevronRight className="h-4 w-4 text-muted-foreground" />}
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <p className="text-sm font-medium text-gray-900 capitalize">{report.category.replace(/_/g, " ")}</p>
                      {report.is_anonymous && (
                        <span className="inline-flex rounded-full px-2 py-0.5 text-xs font-medium bg-gray-100 text-gray-600">
                          Anonymous
                        </span>
                      )}
                    </div>
                    <p className="text-xs text-muted-foreground mt-0.5">
                      Submitted {new Date(report.submitted_at).toLocaleDateString()}
                    </p>
                  </div>
                  <span className={`inline-flex rounded-full px-2.5 py-0.5 text-xs font-medium flex-shrink-0 capitalize ${STATUS_COLORS[report.status] ?? "bg-gray-100 text-gray-600"}`}>
                    {report.status.replace(/_/g, " ")}
                  </span>
                </div>

                {isExpanded && ed && (
                  <div className="border-t bg-gray-50 px-8 py-4 space-y-3">
                    {report.description && (
                      <div>
                        <p className="text-xs font-semibold text-gray-700 mb-1">Description</p>
                        <p className="text-sm text-gray-700 bg-white border rounded-lg px-3 py-2">{report.description}</p>
                      </div>
                    )}
                    {report.assignee && (
                      <p className="text-xs text-muted-foreground">Assigned to: {report.assignee}</p>
                    )}
                    <div className="space-y-1">
                      <label className="text-xs font-semibold text-gray-700">Status</label>
                      <select value={ed.status} onChange={(e) => setEditing((prev) => ({ ...prev, [report.id]: { ...ed, status: e.target.value } }))}
                        className="block rounded-md border border-gray-300 px-2 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-[#1a2332]">
                        <option value="new">New</option>
                        <option value="under_review">Under Review</option>
                        <option value="resolved">Resolved</option>
                        <option value="dismissed">Dismissed</option>
                      </select>
                    </div>
                    <div className="space-y-1">
                      <label className="text-xs font-semibold text-gray-700">Resolution Notes</label>
                      <textarea value={ed.notes} onChange={(e) => setEditing((prev) => ({ ...prev, [report.id]: { ...ed, notes: e.target.value } }))}
                        rows={3} placeholder="Add internal notes about this report…"
                        className="block w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-[#1a2332]" />
                    </div>
                    <Button size="sm" disabled={actionLoading === report.id + "_save"} onClick={() => saveReport(report.id)}
                      className="bg-[#1a2332] hover:bg-[#2a3342] text-white">
                      {actionLoading === report.id + "_save" ? "Saving…" : "Save Changes"}
                    </Button>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
