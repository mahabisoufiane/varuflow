"use client";

import { useState } from "react";
import { toast } from "sonner";
import { api } from "@/lib/api-client";
import { FileBarChart2, Download, Check } from "lucide-react";

const SECTIONS = [
  { key: "pnl",         label: "P&L Summary" },
  { key: "customers",   label: "Top Customers" },
  { key: "kpi_goals",   label: "KPI Goals Progress" },
  { key: "benchmarks",  label: "Industry Benchmarks" },
];

const PERIODS = [
  { value: "ytd",    label: "Year to Date" },
  { value: "q1",     label: "Q1" },
  { value: "q2",     label: "Q2" },
  { value: "q3",     label: "Q3" },
  { value: "q4",     label: "Q4" },
  { value: "last12m", label: "Last 12 Months" },
];

export default function BoardReportPage() {
  const [title, setTitle] = useState("Q2 2026 Board Report");
  const [period, setPeriod] = useState("ytd");
  const [sections, setSections] = useState<Set<string>>(new Set(["pnl", "customers", "kpi_goals"]));
  const [generating, setGenerating] = useState(false);

  function toggleSection(key: string) {
    setSections(prev => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key); else next.add(key);
      return next;
    });
  }

  async function generate() {
    if (sections.size === 0) { toast.error("Select at least one section"); return; }
    setGenerating(true);
    try {
      await api.downloadBlob(
        "/api/ceo/board-report",
        `${title.replace(/\s+/g, "-").toLowerCase()}.pdf`,
        "POST",
        { title, period, include_sections: Array.from(sections) },
      );
      toast.success("Board report downloaded");
    } finally {
      setGenerating(false);
    }
  }

  return (
    <div className="max-w-2xl space-y-6">
      <div>
        <h1 className="text-2xl font-semibold text-gray-900">Board / Investor Report</h1>
        <p className="mt-1 text-sm text-gray-500">Generate a professional PDF report for stakeholders, investors or board meetings.</p>
      </div>

      {/* Config */}
      <div className="rounded-xl border border-gray-200 bg-white p-6 space-y-5">
        <div>
          <label className="text-sm font-medium text-gray-700 mb-1 block">Report Title</label>
          <input className="input w-full" value={title} onChange={e => setTitle(e.target.value)} placeholder="Q2 2026 Board Report" />
        </div>

        <div>
          <label className="text-sm font-medium text-gray-700 mb-1 block">Reporting Period</label>
          <div className="grid grid-cols-3 gap-2">
            {PERIODS.map(p => (
              <button key={p.value} onClick={() => setPeriod(p.value)}
                className={`px-3 py-2 rounded-lg text-sm font-medium text-left transition-all ${
                  period === p.value ? "bg-blue-500 text-white" : "bg-gray-100 text-gray-700 hover:bg-gray-200"
                }`}>{p.label}</button>
            ))}
          </div>
        </div>

        <div>
          <label className="text-sm font-medium text-gray-700 mb-2 block">Sections to Include</label>
          <div className="space-y-2">
            {SECTIONS.map(s => (
              <label key={s.key} className={`flex items-center gap-3 p-3 rounded-xl border cursor-pointer transition-all ${
                sections.has(s.key) ? "border-blue-400 bg-blue-50" : "border-gray-200 hover:border-gray-300"
              }`}>
                <div className={`w-5 h-5 rounded flex items-center justify-center flex-shrink-0 ${
                  sections.has(s.key) ? "bg-blue-500" : "bg-gray-200"
                }`}>
                  {sections.has(s.key) && <Check className="h-3.5 w-3.5 text-white" />}
                </div>
                <input type="checkbox" className="sr-only" checked={sections.has(s.key)} onChange={() => toggleSection(s.key)} />
                <span className="text-sm font-medium text-gray-900">{s.label}</span>
              </label>
            ))}
          </div>
        </div>
      </div>

      {/* Preview summary */}
      <div className="rounded-xl border border-gray-200 bg-gray-50 p-4 text-sm text-gray-600 space-y-1">
        <p className="font-medium text-gray-700 flex items-center gap-2">
          <FileBarChart2 className="h-4 w-4 text-blue-500" /> What&apos;s included
        </p>
        <p>• Cover page with org name, period and generation date</p>
        <p>• KPI summary table (revenue, expenses, gross profit, net income)</p>
        {sections.has("customers") && <p>• Top 5 customers by revenue</p>}
        {sections.has("kpi_goals") && <p>• KPI goals with target vs actual</p>}
        {sections.has("benchmarks") && <p>• Industry benchmark comparison</p>}
        <p className="text-xs text-gray-400 mt-2">Data is pulled live from your Varuflow account at the time of generation.</p>
      </div>

      <button onClick={generate} disabled={generating || sections.size === 0}
        className="btn-primary flex items-center gap-2 w-full justify-center py-3">
        <Download className="h-4 w-4" />
        {generating ? "Generating PDF…" : "Download Board Report PDF"}
      </button>
    </div>
  );
}
