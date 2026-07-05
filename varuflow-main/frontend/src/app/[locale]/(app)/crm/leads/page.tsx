"use client";
import { useEffect, useRef, useState } from "react";
import { Users, Search, Plus, Upload, ChevronDown, AlertCircle, ArrowRight, Loader2 } from "lucide-react";
import { Link } from "@/i18n/navigation";
import { useRouter } from "next/navigation";
import { toast } from "sonner";
import { api } from "@/lib/api-client";
import styles from "./page.module.scss";

interface Lead {
  id: string; name: string; company: string | null; email: string | null;
  phone: string | null; source: string | null; status: string;
  assigned_to: string | null; score: number;
  created_at: string; duplicate_warning?: { id: string; name: string };
}

const STATUSES = ["new", "contacted", "qualified", "converted", "dead"];
const SOURCES = ["website", "referral", "cold_outreach", "lead_form", "event", "partner", "other"];

const STATUS_BADGE: Record<string, string> = {
  new:        "bg-blue-100 text-blue-700",
  contacted:  "bg-yellow-100 text-yellow-700",
  qualified:  "bg-purple-100 text-purple-700",
  converted:  "bg-green-100 text-green-700",
  dead:       "bg-gray-100 text-gray-500",
};

const STATUS_MODULE: Record<string, keyof typeof styles> = {
  new:       "statusNew",
  contacted: "statusContacted",
  qualified: "statusQualified",
  converted: "statusConverted",
  dead:      "statusDead",
};

export default function LeadsPage() {
  const router = useRouter();
  const [leads, setLeads] = useState<Lead[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [sourceFilter, setSourceFilter] = useState("");
  const [showNew, setShowNew] = useState(false);
  const [newName, setNewName] = useState("");
  const [newEmail, setNewEmail] = useState("");
  const [newCompany, setNewCompany] = useState("");
  const [newSource, setNewSource] = useState("");
  const [saving, setSaving] = useState(false);
  const [showCsv, setShowCsv] = useState(false);
  const [csvText, setCsvText] = useState("");
  const [importing, setImporting] = useState(false);
  const csvRef = useRef<HTMLTextAreaElement>(null);

  const load = async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams();
      if (statusFilter) params.set("status", statusFilter);
      if (sourceFilter) params.set("source", sourceFilter);
      if (search) params.set("search", search);
      params.set("limit", "200");
      const data = await api.get<Lead[]>(`/api/leads?${params.toString()}`);
      setLeads(data);
    } catch { /* silent */ }
    finally { setLoading(false); }
  };

  useEffect(() => { load(); }, [statusFilter, sourceFilter]);

  const handleSearch = (e: React.FormEvent) => { e.preventDefault(); load(); };

  const createLead = async () => {
    if (!newName.trim()) return;
    setSaving(true);
    try {
      const result = await api.post<Lead>("/api/leads", {
        name: newName.trim(),
        email: newEmail.trim() || undefined,
        company: newCompany.trim() || undefined,
        source: newSource || undefined,
      });
      if (result.duplicate_warning) {
        toast.warning(`Possible duplicate: ${result.duplicate_warning.name}`);
      } else {
        toast.success("Lead created");
      }
      setShowNew(false);
      setNewName(""); setNewEmail(""); setNewCompany(""); setNewSource("");
      load();
    } catch { toast.error("Failed to create lead"); }
    finally { setSaving(false); }
  };

  const importCsv = async () => {
    const lines = csvText.trim().split("\n").filter(Boolean);
    if (lines.length < 2) { toast.error("CSV needs a header row and at least one data row"); return; }
    const headers = lines[0].split(",").map(h => h.trim().toLowerCase());
    const nameIdx = headers.indexOf("name");
    if (nameIdx === -1) { toast.error("CSV must have a 'name' column"); return; }

    const rows = lines.slice(1).map(line => {
      const cols = line.split(",").map(c => c.trim());
      const row: Record<string, string> = {};
      headers.forEach((h, i) => { if (cols[i]) row[h] = cols[i]; });
      return row;
    }).filter(r => r.name);

    setImporting(true);
    try {
      const result = await api.post<{ created: number; skipped: number }>("/api/leads/import-csv", rows);
      toast.success(`Imported ${result.created} leads, skipped ${result.skipped} duplicates`);
      setShowCsv(false);
      setCsvText("");
      load();
    } catch { toast.error("Import failed"); }
    finally { setImporting(false); }
  };

  const totalByStatus = STATUSES.reduce((acc, s) => {
    acc[s] = leads.filter(l => l.status === s).length;
    return acc;
  }, {} as Record<string, number>);

  return (
    <div className="p-6 space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between flex-wrap gap-2">
        <div className="flex items-center gap-2">
          <Users size={20} className="text-[#1a2332]" />
          <h1 className="text-xl font-bold">Leads</h1>
          <span className="text-xs text-gray-400 ml-1">{leads.length} leads</span>
        </div>
        <div className="flex items-center gap-2">
          <Link href="/crm/leads/forms" className="flex items-center gap-1.5 px-3 py-1.5 border rounded text-sm hover:bg-gray-50 text-gray-600">
            Lead Forms
          </Link>
          <button onClick={() => setShowCsv(true)} className="flex items-center gap-1.5 px-3 py-1.5 border rounded text-sm hover:bg-gray-50">
            <Upload size={13} /> Import CSV
          </button>
          <button onClick={() => setShowNew(true)} className="flex items-center gap-1.5 px-3 py-1.5 bg-[#1a2332] text-white rounded text-sm hover:opacity-90">
            <Plus size={13} /> New Lead
          </button>
        </div>
      </div>

      {/* Status strip */}
      <div className="flex gap-2 flex-wrap">
        {STATUSES.map(s => (
          <button key={s}
            onClick={() => setStatusFilter(statusFilter === s ? "" : s)}
            className={`px-3 py-1 rounded-full text-xs font-medium capitalize transition-colors ${statusFilter === s ? STATUS_BADGE[s] + " ring-1 ring-current" : "bg-gray-100 text-gray-600 hover:bg-gray-200"}`}>
            {s} <span className="ml-1 opacity-60">{totalByStatus[s] || 0}</span>
          </button>
        ))}
      </div>

      {/* Filters */}
      <div className="flex flex-wrap gap-2 items-center">
        <form onSubmit={handleSearch} className="flex items-center gap-1.5">
          <div className="relative">
            <Search size={13} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-gray-400" />
            <input
              className="pl-7 pr-3 py-1.5 border rounded text-sm focus:outline-none focus:ring-1 w-48"
              placeholder="Search leads…"
              value={search}
              onChange={e => setSearch(e.target.value)}
            />
          </div>
          <button type="submit" className="px-3 py-1.5 bg-[#1a2332] text-white rounded text-sm hover:opacity-90">Search</button>
        </form>

        <select className="border rounded px-2 py-1.5 text-sm focus:outline-none" value={sourceFilter} onChange={e => setSourceFilter(e.target.value)}>
          <option value="">All sources</option>
          {SOURCES.map(s => <option key={s} value={s}>{s.replace("_", " ")}</option>)}
        </select>
      </div>

      {/* New lead modal */}
      {showNew && (
        <div className="bg-white border rounded-xl p-4 space-y-3 max-w-md">
          <p className="text-sm font-semibold">New Lead</p>
          <input placeholder="Name *" className="w-full border rounded px-3 py-1.5 text-sm focus:outline-none" value={newName} onChange={e => setNewName(e.target.value)} />
          <input placeholder="Email" className="w-full border rounded px-3 py-1.5 text-sm focus:outline-none" value={newEmail} onChange={e => setNewEmail(e.target.value)} />
          <input placeholder="Company" className="w-full border rounded px-3 py-1.5 text-sm focus:outline-none" value={newCompany} onChange={e => setNewCompany(e.target.value)} />
          <select className="w-full border rounded px-3 py-1.5 text-sm focus:outline-none" value={newSource} onChange={e => setNewSource(e.target.value)}>
            <option value="">Source (optional)</option>
            {SOURCES.map(s => <option key={s} value={s}>{s.replace("_", " ")}</option>)}
          </select>
          <div className="flex gap-2">
            <button onClick={createLead} disabled={saving || !newName.trim()} className="px-4 py-1.5 bg-[#1a2332] text-white rounded text-sm hover:opacity-90 disabled:opacity-40">
              {saving ? <Loader2 size={13} className="animate-spin" /> : "Create"}
            </button>
            <button onClick={() => setShowNew(false)} className="px-4 py-1.5 border rounded text-sm hover:bg-gray-50">Cancel</button>
          </div>
        </div>
      )}

      {/* CSV import modal */}
      {showCsv && (
        <div className="bg-white border rounded-xl p-4 space-y-3">
          <p className="text-sm font-semibold">Import CSV</p>
          <p className="text-xs text-gray-400">Paste CSV with columns: name, email, company, phone, source, notes (name required)</p>
          <textarea ref={csvRef} rows={6} value={csvText} onChange={e => setCsvText(e.target.value)}
            placeholder="name,email,company&#10;John Smith,john@example.com,Acme"
            className="w-full border rounded px-3 py-2 text-sm font-mono resize-none focus:outline-none" />
          <div className="flex gap-2">
            <button onClick={importCsv} disabled={importing || !csvText.trim()} className="px-4 py-1.5 bg-[#1a2332] text-white rounded text-sm hover:opacity-90 disabled:opacity-40">
              {importing ? <Loader2 size={13} className="animate-spin" /> : "Import"}
            </button>
            <button onClick={() => setShowCsv(false)} className="px-4 py-1.5 border rounded text-sm hover:bg-gray-50">Cancel</button>
          </div>
        </div>
      )}

      {/* Table */}
      <div className="bg-white border rounded-xl overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-gray-50 text-xs text-gray-500">
            <tr>
              <th className="px-4 py-3 text-left">Name</th>
              <th className="px-4 py-3 text-left">Company</th>
              <th className="px-4 py-3 text-left">Email</th>
              <th className="px-4 py-3 text-left">Source</th>
              <th className="px-4 py-3 text-left">Status</th>
              <th className="px-4 py-3 text-right">Score</th>
              <th className="px-4 py-3 text-left">Created</th>
              <th className="px-4 py-3" />
            </tr>
          </thead>
          <tbody className="divide-y">
            {loading ? (
              <tr><td colSpan={8} className="text-center py-8 text-gray-300">Loading…</td></tr>
            ) : leads.length === 0 ? (
              <tr><td colSpan={8} className="text-center py-8 text-gray-300">No leads found</td></tr>
            ) : leads.map(lead => (
              <tr key={lead.id} className="hover:bg-gray-50">
                <td className="px-4 py-3">
                  <Link href={`/crm/leads/${lead.id}`} className="font-medium text-gray-900 hover:text-blue-600 hover:underline">
                    {lead.name}
                  </Link>
                </td>
                <td className="px-4 py-3 text-gray-500">{lead.company ?? "—"}</td>
                <td className="px-4 py-3 text-gray-500">{lead.email ?? "—"}</td>
                <td className="px-4 py-3 text-gray-500 capitalize">{lead.source?.replace("_", " ") ?? "—"}</td>
                <td className="px-4 py-3">
                  <span className={styles[STATUS_MODULE[lead.status] ?? "statusNew"]}>
                    {lead.status}
                  </span>
                </td>
                <td className="px-4 py-3 text-right">
                  <span className={`text-xs font-medium ${lead.score >= 50 ? "text-green-600" : lead.score >= 20 ? "text-yellow-600" : "text-gray-400"}`}>
                    {lead.score}
                  </span>
                </td>
                <td className="px-4 py-3 text-gray-400 text-xs">{new Date(lead.created_at).toLocaleDateString()}</td>
                <td className="px-4 py-3 text-right">
                  <Link href={`/crm/leads/${lead.id}`} className="text-gray-300 hover:text-gray-600">
                    <ArrowRight size={14} />
                  </Link>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
