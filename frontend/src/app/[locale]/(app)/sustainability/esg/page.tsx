"use client";

import { useEffect, useState } from "react";
import { useRouter, useParams } from "next/navigation";
import { createClient } from "@/lib/supabase/client";
import { PlusCircle, BarChart3, RefreshCw, ChevronDown, ChevronRight } from "lucide-react";
import { Button } from "@/components/ui/button";
import { toast } from "sonner";
import styles from "./page.module.scss";

interface EsgReport {
  id: string;
  title: string;
  report_year: number;
  status: string;
  // Environmental
  total_co2_tonnes: number | null;
  co2_per_revenue: number | null;
  renewable_energy_pct: number | null;
  waste_recycled_pct: number | null;
  // Social
  employee_count: number | null;
  female_leadership_pct: number | null;
  training_hours_per_employee: number | null;
  employee_satisfaction_score: number | null;
  injury_rate: number | null;
  // Governance
  audit_complete: boolean | null;
  whistleblower_mechanism: boolean | null;
  anti_corruption_training_pct: number | null;
  board_diversity_pct: number | null;
  created_at: string;
}

const STATUS_COLORS: Record<string, string> = {
  draft:     "bg-gray-100 text-gray-600",
  published: "bg-green-100 text-green-700",
};

const STATUS_MODULE: Record<string, keyof typeof styles> = {
  draft:     "statusDraft",
  published: "statusPublished",
};

export default function EsgPage() {
  const router = useRouter();
  const params = useParams<{ locale: string }>();
  const locale = params?.locale ?? "en";
  const supabase = createClient();

  const [reports, setReports] = useState<EsgReport[]>([]);
  const [loading, setLoading] = useState(true);
  const [expanded, setExpanded] = useState<Set<string>>(new Set());
  const [showNew, setShowNew] = useState(false);
  const [newForm, setNewForm] = useState({ title: "", report_year: new Date().getFullYear().toString() });
  const [editFields, setEditFields] = useState<Record<string, Partial<EsgReport>>>({});
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
      const res = await fetch(apiUrl("/api/esg/reports"), { headers: { Authorization: `Bearer ${token}` } });
      if (res.status === 401) { router.push(`/${locale}/auth/login`); return; }
      if (res.ok) setReports(await res.json());
    } catch {
      toast.error("Failed to load ESG reports");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { load(); }, []);  // eslint-disable-line react-hooks/exhaustive-deps

  function toggle(id: string, report: EsgReport) {
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(id)) {
        next.delete(id);
      } else {
        next.add(id);
        if (!editFields[id]) setEditFields((e) => ({ ...e, [id]: {} }));
      }
      return next;
    });
  }

  async function createReport() {
    if (!newForm.title.trim()) { toast.error("Title is required"); return; }
    setActionLoading("create");
    try {
      const token = await getToken();
      if (!token) return;
      const res = await fetch(apiUrl("/api/esg/reports"), {
        method: "POST",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
        body: JSON.stringify({ title: newForm.title, report_year: parseInt(newForm.report_year) }),
      });
      if (!res.ok) {
        const b = await res.json().catch(() => ({}));
        toast.error(b.detail ?? "Failed to create report");
        return;
      }
      toast.success("ESG report created");
      setShowNew(false);
      setNewForm({ title: "", report_year: new Date().getFullYear().toString() });
      await load();
    } catch {
      toast.error("Something went wrong");
    } finally {
      setActionLoading(null);
    }
  }

  async function saveFields(id: string) {
    const fields = editFields[id];
    if (!fields) return;
    setActionLoading(id + "_save");
    try {
      const token = await getToken();
      if (!token) return;
      const res = await fetch(apiUrl(`/api/esg/reports/${id}`), {
        method: "PATCH",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
        body: JSON.stringify(fields),
      });
      if (!res.ok) {
        const b = await res.json().catch(() => ({}));
        toast.error(b.detail ?? "Failed to save");
        return;
      }
      toast.success("Metrics saved");
      await load();
    } catch {
      toast.error("Something went wrong");
    } finally {
      setActionLoading(null);
    }
  }

  async function autoPopulate(id: string) {
    setActionLoading(id + "_auto");
    try {
      const token = await getToken();
      if (!token) return;
      const res = await fetch(apiUrl(`/api/esg/reports/${id}/auto-populate`), {
        method: "POST",
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) {
        const b = await res.json().catch(() => ({}));
        toast.error(b.detail ?? "Failed to auto-populate");
        return;
      }
      toast.success("Auto-populated from carbon data");
      await load();
    } catch {
      toast.error("Something went wrong");
    } finally {
      setActionLoading(null);
    }
  }

  async function publishReport(id: string) {
    setActionLoading(id + "_publish");
    try {
      const token = await getToken();
      if (!token) return;
      const res = await fetch(apiUrl(`/api/esg/reports/${id}/publish`), {
        method: "POST",
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) {
        const b = await res.json().catch(() => ({}));
        toast.error(b.detail ?? "Failed to publish");
        return;
      }
      toast.success("Report published");
      await load();
    } catch {
      toast.error("Something went wrong");
    } finally {
      setActionLoading(null);
    }
  }

  function numInput(id: string, field: keyof EsgReport, label: string, report: EsgReport) {
    const current = editFields[id]?.[field] ?? report[field];
    return (
      <div className="space-y-1">
        <label className="text-xs font-medium text-gray-700">{label}</label>
        <input type="number"
          value={current == null ? "" : String(current)}
          onChange={(e) => setEditFields((prev) => ({
            ...prev, [id]: { ...prev[id], [field]: e.target.value === "" ? null : parseFloat(e.target.value) },
          }))}
          className="block w-full rounded-md border border-gray-300 px-2 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-[#1a2332]"
        />
      </div>
    );
  }

  function checkInput(id: string, field: keyof EsgReport, label: string, report: EsgReport) {
    const current = (editFields[id]?.[field] ?? report[field]) as boolean | null;
    return (
      <label className="flex items-center gap-2 cursor-pointer">
        <input type="checkbox" checked={!!current}
          onChange={(e) => setEditFields((prev) => ({
            ...prev, [id]: { ...prev[id], [field]: e.target.checked },
          }))}
          className="rounded border-gray-300"
        />
        <span className="text-xs font-medium text-gray-700">{label}</span>
      </label>
    );
  }

  return (
    <div className="mx-auto max-w-4xl space-y-6 p-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-gray-900">ESG Reports</h1>
          <p className="text-sm text-muted-foreground mt-0.5">Create and publish Environmental, Social, and Governance reports.</p>
        </div>
        <Button onClick={() => setShowNew(true)} className="bg-[#1a2332] hover:bg-[#2a3342] text-white gap-2">
          <PlusCircle className="h-4 w-4" /> New Report
        </Button>
      </div>

      {/* New report form */}
      {showNew && (
        <div className="rounded-xl border border-[#1a2332]/20 bg-white p-5 shadow-sm space-y-3">
          <h3 className="text-sm font-semibold text-gray-900">New ESG Report</h3>
          <div className="grid grid-cols-3 gap-3">
            <div className="col-span-2 space-y-1">
              <label className="text-xs font-medium text-gray-700">Title *</label>
              <input value={newForm.title} onChange={(e) => setNewForm((f) => ({ ...f, title: e.target.value }))}
                placeholder="Annual Sustainability Report 2026"
                className="block w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-[#1a2332]" />
            </div>
            <div className="space-y-1">
              <label className="text-xs font-medium text-gray-700">Report Year</label>
              <input type="number" value={newForm.report_year} onChange={(e) => setNewForm((f) => ({ ...f, report_year: e.target.value }))}
                className="block w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-[#1a2332]" />
            </div>
          </div>
          <div className="flex gap-2">
            <Button variant="outline" onClick={() => setShowNew(false)}>Cancel</Button>
            <Button disabled={actionLoading === "create"} onClick={createReport}
              className="bg-[#1a2332] hover:bg-[#2a3342] text-white">
              {actionLoading === "create" ? "Creating…" : "Create Report"}
            </Button>
          </div>
        </div>
      )}

      {/* Reports list */}
      {loading && reports.length === 0 ? (
        <div className="text-center py-12"><RefreshCw className="h-6 w-6 animate-spin mx-auto text-muted-foreground" /></div>
      ) : reports.length === 0 ? (
        <div className="rounded-xl border bg-white p-12 text-center shadow-sm">
          <BarChart3 className="h-10 w-10 text-muted-foreground mx-auto mb-3" />
          <p className="text-gray-600 font-medium">No ESG reports yet</p>
        </div>
      ) : (
        <div className="space-y-3">
          {reports.map((report) => {
            const isExpanded = expanded.has(report.id);
            const ed = editFields[report.id] ?? {};
            return (
              <div key={report.id} className="rounded-xl border bg-white shadow-sm overflow-hidden">
                <div className="flex items-center gap-3 px-5 py-4 cursor-pointer hover:bg-gray-50 transition-colors"
                  onClick={() => toggle(report.id, report)}>
                  <div className="flex-shrink-0">
                    {isExpanded
                      ? <ChevronDown className="h-4 w-4 text-muted-foreground" />
                      : <ChevronRight className="h-4 w-4 text-muted-foreground" />}
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium text-gray-900">{report.title}</p>
                    <p className="text-xs text-muted-foreground mt-0.5">{report.report_year}</p>
                  </div>
                  <span className={styles[STATUS_MODULE[report.status] ?? "statusDraft"]}>
                    {report.status}
                  </span>
                  <div className="flex items-center gap-2 flex-shrink-0" onClick={(e) => e.stopPropagation()}>
                    <Button size="sm" variant="outline"
                      disabled={actionLoading === report.id + "_auto"}
                      onClick={() => autoPopulate(report.id)}
                      className="text-xs h-7 gap-1">
                      {actionLoading === report.id + "_auto" ? <RefreshCw className="h-3 w-3 animate-spin" /> : null}
                      Auto-Populate
                    </Button>
                    {report.status === "draft" && (
                      <Button size="sm"
                        disabled={actionLoading === report.id + "_publish"}
                        onClick={() => publishReport(report.id)}
                        className="bg-green-600 hover:bg-green-700 text-white text-xs h-7">
                        Publish
                      </Button>
                    )}
                  </div>
                </div>

                {isExpanded && (
                  <div className="border-t bg-gray-50 px-5 py-5 space-y-6">
                    {/* Environmental */}
                    <div>
                      <h4 className="text-xs font-bold text-green-700 uppercase tracking-wide mb-3">Environmental</h4>
                      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                        {numInput(report.id, "total_co2_tonnes", "Total CO₂ (tonnes)", report)}
                        {numInput(report.id, "co2_per_revenue", "CO₂ per Revenue", report)}
                        {numInput(report.id, "renewable_energy_pct", "Renewable Energy %", report)}
                        {numInput(report.id, "waste_recycled_pct", "Waste Recycled %", report)}
                      </div>
                    </div>

                    {/* Social */}
                    <div>
                      <h4 className="text-xs font-bold text-blue-700 uppercase tracking-wide mb-3">Social</h4>
                      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                        {numInput(report.id, "employee_count", "Employees", report)}
                        {numInput(report.id, "female_leadership_pct", "Female Leadership %", report)}
                        {numInput(report.id, "training_hours_per_employee", "Training Hours / Employee", report)}
                        {numInput(report.id, "employee_satisfaction_score", "Satisfaction Score", report)}
                        {numInput(report.id, "injury_rate", "Injury Rate", report)}
                      </div>
                    </div>

                    {/* Governance */}
                    <div>
                      <h4 className="text-xs font-bold text-purple-700 uppercase tracking-wide mb-3">Governance</h4>
                      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                        {numInput(report.id, "anti_corruption_training_pct", "Anti-Corruption Training %", report)}
                        {numInput(report.id, "board_diversity_pct", "Board Diversity %", report)}
                      </div>
                      <div className="flex items-center gap-6 mt-3">
                        {checkInput(report.id, "audit_complete", "Audit Complete", report)}
                        {checkInput(report.id, "whistleblower_mechanism", "Whistleblower Mechanism", report)}
                      </div>
                    </div>

                    <Button size="sm" disabled={actionLoading === report.id + "_save"} onClick={() => saveFields(report.id)}
                      className="bg-[#1a2332] hover:bg-[#2a3342] text-white">
                      {actionLoading === report.id + "_save" ? "Saving…" : "Save Metrics"}
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
