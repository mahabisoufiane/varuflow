"use client";
import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { ArrowLeft, Pencil, Loader2, Target, Star, CheckCircle2, ArrowRight, UserCheck } from "lucide-react";
import { toast } from "sonner";
import { Link } from "@/i18n/navigation";
import { api } from "@/lib/api-client";
import styles from "./page.module.scss";

interface ScoreEvent {
  id: string; event_type: string; points: number; note: string | null; created_at: string;
}

interface Lead {
  id: string; name: string; company: string | null; email: string | null;
  phone: string | null; source: string | null; status: string;
  assigned_to: string | null; score: number; notes: string | null;
  converted_customer_id: string | null; converted_deal_id: string | null;
  converted_at: string | null; last_contacted_at: string | null;
  created_at: string; updated_at: string;
  score_events: ScoreEvent[];
}

const STATUSES = ["new", "contacted", "qualified", "converted", "dead"];
const SOURCES = ["website", "referral", "cold_outreach", "lead_form", "event", "partner", "other"];
const SCORE_EVENTS = ["email_opened", "link_clicked", "page_visit", "form_submitted", "meeting_booked", "demo_completed"];

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

export default function LeadDetailPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const [lead, setLead] = useState<Lead | null>(null);
  const [loading, setLoading] = useState(true);
  const [editing, setEditing] = useState(false);
  const [saving, setSaving] = useState(false);
  const [converting, setConverting] = useState(false);
  const [showConvert, setShowConvert] = useState(false);
  const [dealTitle, setDealTitle] = useState("");
  const [dealValue, setDealValue] = useState("");

  // Edit fields
  const [editName, setEditName] = useState("");
  const [editCompany, setEditCompany] = useState("");
  const [editEmail, setEditEmail] = useState("");
  const [editPhone, setEditPhone] = useState("");
  const [editSource, setEditSource] = useState("");
  const [editNotes, setEditNotes] = useState("");

  const load = async () => {
    try {
      const d = await api.get<Lead>(`/api/leads/${id}`);
      setLead(d);
      setEditName(d.name);
      setEditCompany(d.company ?? "");
      setEditEmail(d.email ?? "");
      setEditPhone(d.phone ?? "");
      setEditSource(d.source ?? "");
      setEditNotes(d.notes ?? "");
      setDealTitle(`Deal – ${d.company || d.name}`);
    } catch { toast.error("Failed to load lead"); }
    finally { setLoading(false); }
  };

  useEffect(() => { load(); }, [id]);

  const saveEdits = async () => {
    setSaving(true);
    try {
      await api.patch(`/api/leads/${id}`, {
        name: editName.trim() || undefined,
        company: editCompany || undefined,
        email: editEmail || undefined,
        phone: editPhone || undefined,
        source: editSource || undefined,
        notes: editNotes || undefined,
      });
      await load();
      setEditing(false);
      toast.success("Saved");
    } catch { toast.error("Failed to save"); }
    finally { setSaving(false); }
  };

  const moveStatus = async (status: string) => {
    try {
      await api.patch(`/api/leads/${id}`, { status });
      await load();
    } catch { toast.error("Failed to update status"); }
  };

  const convertLead = async () => {
    setConverting(true);
    try {
      const result = await api.post<{ customer_id: string; deal_id: string }>(`/api/leads/${id}/convert`, {
        deal_title: dealTitle.trim() || undefined,
        deal_value: dealValue ? parseFloat(dealValue) : undefined,
      });
      toast.success("Lead converted to customer + deal");
      setShowConvert(false);
      router.push(`/crm/deals/${result.deal_id}`);
    } catch { toast.error("Failed to convert lead"); }
    finally { setConverting(false); }
  };

  const deleteLead = async () => {
    if (!confirm("Delete this lead?")) return;
    try {
      await api.delete(`/api/leads/${id}`);
      router.push("/crm/leads");
    } catch { toast.error("Failed to delete lead"); }
  };

  if (loading) return <div className="p-8 flex justify-center"><Loader2 size={24} className="animate-spin text-gray-300" /></div>;
  if (!lead) return <div className="p-8 text-gray-400">Lead not found.</div>;

  const scoreColor = lead.score >= 50 ? "text-green-600" : lead.score >= 20 ? "text-yellow-600" : "text-gray-400";

  return (
    <div className="p-6 max-w-4xl space-y-6">
      {/* Header */}
      <div className="flex items-start justify-between gap-4">
        <div className="flex items-start gap-3">
          <button onClick={() => router.back()} className="mt-0.5 p-1.5 rounded hover:bg-gray-100">
            <ArrowLeft size={16} className="text-gray-500" />
          </button>
          <div>
            {editing ? (
              <input className="text-2xl font-bold border-b outline-none w-full" value={editName}
                onChange={e => setEditName(e.target.value)} />
            ) : (
              <h1 className="text-2xl font-bold">{lead.name}</h1>
            )}
            <div className="flex items-center gap-2 mt-1">
              <span className={styles[STATUS_MODULE[lead.status] ?? "statusNew"]}>
                {lead.status}
              </span>
              <span className={`text-sm font-semibold ${scoreColor}`}><Star size={11} className="inline mr-0.5" />{lead.score} pts</span>
              <span className="text-xs text-gray-400">Created {new Date(lead.created_at).toLocaleDateString()}</span>
            </div>
          </div>
        </div>
        <div className="flex gap-2 shrink-0">
          {editing ? (
            <>
              <button onClick={saveEdits} disabled={saving} className="px-3 py-1.5 bg-[#1a2332] text-white rounded text-sm hover:opacity-90 disabled:opacity-50">
                {saving ? <Loader2 size={13} className="animate-spin" /> : "Save"}
              </button>
              <button onClick={() => setEditing(false)} className="px-3 py-1.5 border rounded text-sm hover:bg-gray-50">Cancel</button>
            </>
          ) : (
            <>
              {lead.status !== "converted" && (
                <button onClick={() => setShowConvert(true)} className="flex items-center gap-1.5 px-3 py-1.5 bg-green-600 text-white rounded text-sm hover:opacity-90">
                  <UserCheck size={13} /> Convert
                </button>
              )}
              <button onClick={() => setEditing(true)} className="flex items-center gap-1.5 px-3 py-1.5 border rounded text-sm hover:bg-gray-50">
                <Pencil size={13} /> Edit
              </button>
              <button onClick={deleteLead} className="px-3 py-1.5 border border-red-200 text-red-500 rounded text-sm hover:bg-red-50">Delete</button>
            </>
          )}
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left: details */}
        <div className="lg:col-span-2 space-y-4">
          {/* Fields */}
          <div className="bg-white border rounded-lg p-4 space-y-3">
            <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide">Contact Details</p>
            <div className="grid grid-cols-2 gap-3 text-sm">
              {[
                { label: "Email", value: lead.email, editVal: editEmail, setEdit: setEditEmail, type: "email" },
                { label: "Phone", value: lead.phone, editVal: editPhone, setEdit: setEditPhone, type: "tel" },
                { label: "Company", value: lead.company, editVal: editCompany, setEdit: setEditCompany, type: "text" },
                { label: "Source", value: lead.source, editVal: editSource, setEdit: setEditSource, type: "select" },
              ].map(f => (
                <div key={f.label}>
                  <p className="text-xs text-gray-400 mb-0.5">{f.label}</p>
                  {editing ? (
                    f.type === "select" ? (
                      <select className="w-full border rounded px-2 py-1 text-sm focus:outline-none" value={f.editVal}
                        onChange={e => f.setEdit(e.target.value)}>
                        <option value="">—</option>
                        {SOURCES.map(s => <option key={s} value={s}>{s.replace("_", " ")}</option>)}
                      </select>
                    ) : (
                      <input type={f.type} className="w-full border rounded px-2 py-1 text-sm focus:outline-none"
                        value={f.editVal} onChange={e => f.setEdit(e.target.value)} />
                    )
                  ) : (
                    <p className="text-gray-700 capitalize">{f.value ?? "—"}</p>
                  )}
                </div>
              ))}
            </div>
          </div>

          {/* Notes */}
          <div className="bg-white border rounded-lg p-4">
            <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">Notes</p>
            {editing ? (
              <textarea rows={4} className="w-full border rounded px-3 py-2 text-sm resize-none focus:outline-none focus:ring-1"
                value={editNotes} onChange={e => setEditNotes(e.target.value)} />
            ) : (
              <p className="text-sm text-gray-700 whitespace-pre-wrap">{lead.notes || <span className="text-gray-300">No notes</span>}</p>
            )}
          </div>

          {/* Convert prompt */}
          {lead.converted_customer_id && (
            <div className="bg-green-50 border border-green-200 rounded-lg p-4 space-y-2">
              <p className="text-xs font-semibold text-green-700 uppercase tracking-wide">Converted</p>
              <div className="flex gap-3 text-sm">
                <Link href={`/customers/${lead.converted_customer_id}`} className="flex items-center gap-1.5 text-blue-600 hover:underline">
                  <CheckCircle2 size={13} /> Customer
                </Link>
                {lead.converted_deal_id && (
                  <Link href={`/crm/deals/${lead.converted_deal_id}`} className="flex items-center gap-1.5 text-blue-600 hover:underline">
                    <ArrowRight size={13} /> Deal
                  </Link>
                )}
              </div>
              {lead.converted_at && <p className="text-xs text-gray-400">{new Date(lead.converted_at).toLocaleDateString()}</p>}
            </div>
          )}

          {/* Convert modal */}
          {showConvert && (
            <div className="bg-white border rounded-lg p-4 space-y-3">
              <p className="text-sm font-semibold">Convert to Customer + Deal</p>
              <input placeholder="Deal title" className="w-full border rounded px-3 py-1.5 text-sm focus:outline-none"
                value={dealTitle} onChange={e => setDealTitle(e.target.value)} />
              <input type="number" placeholder="Deal value (optional)" className="w-full border rounded px-3 py-1.5 text-sm focus:outline-none"
                value={dealValue} onChange={e => setDealValue(e.target.value)} />
              <div className="flex gap-2">
                <button onClick={convertLead} disabled={converting} className="px-4 py-1.5 bg-green-600 text-white rounded text-sm hover:opacity-90 disabled:opacity-40">
                  {converting ? <Loader2 size={13} className="animate-spin" /> : "Convert"}
                </button>
                <button onClick={() => setShowConvert(false)} className="px-4 py-1.5 border rounded text-sm hover:bg-gray-50">Cancel</button>
              </div>
            </div>
          )}

          {/* Score events */}
          <div className="bg-white border rounded-lg p-4 space-y-3">
            <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide">Score Events</p>
            {lead.score_events.length === 0 ? (
              <p className="text-xs text-gray-300">No score events yet</p>
            ) : (
              <div className="space-y-2">
                {[...lead.score_events].reverse().map(e => (
                  <div key={e.id} className="flex items-center justify-between text-xs">
                    <div>
                      <span className="font-medium capitalize text-gray-700">{e.event_type.replace("_", " ")}</span>
                      {e.note && <span className="text-gray-400 ml-2">{e.note}</span>}
                    </div>
                    <div className="flex items-center gap-3">
                      <span className="text-green-600 font-medium">+{e.points}</span>
                      <span className="text-gray-300">{new Date(e.created_at).toLocaleDateString()}</span>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* Right: status pipeline */}
        <div className="space-y-3">
          <div className="bg-white border rounded-lg p-4">
            <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-3">Status</p>
            <div className="space-y-1.5">
              {STATUSES.map((s, i) => (
                <button key={s} onClick={() => moveStatus(s)}
                  className={`w-full flex items-center gap-2 px-3 py-2 rounded-lg text-sm text-left transition-colors capitalize ${lead.status === s ? "bg-[#1a2332] text-white" : "hover:bg-gray-50"}`}>
                  <span className={`w-5 h-5 rounded-full flex items-center justify-center text-xs shrink-0 ${lead.status === s ? "bg-white/20" : "bg-gray-100 text-gray-500"}`}>
                    {i + 1}
                  </span>
                  {s}
                  {s === "converted" && <CheckCircle2 size={13} className={lead.status === s ? "text-white ml-auto" : "text-green-500 ml-auto"} />}
                </button>
              ))}
            </div>
          </div>

          {/* Score card */}
          <div className="bg-white border rounded-lg p-4 space-y-2">
            <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide">Lead Score</p>
            <div className={`text-3xl font-bold ${scoreColor}`}>{lead.score}</div>
            <div className="h-2 bg-gray-100 rounded-full overflow-hidden">
              <div className={`h-full rounded-full ${lead.score >= 50 ? "bg-green-500" : lead.score >= 20 ? "bg-yellow-400" : "bg-gray-300"}`}
                style={{ width: `${Math.min(lead.score, 100)}%` }} />
            </div>
            <p className="text-xs text-gray-400">
              {lead.score >= 50 ? "Hot lead" : lead.score >= 20 ? "Warm lead" : "Cold lead"}
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
