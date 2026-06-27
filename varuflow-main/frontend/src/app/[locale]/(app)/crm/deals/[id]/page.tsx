"use client";
import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import {
  Target, ArrowLeft, Phone, Mail, Users, Pencil, CheckCircle2,
  XCircle, Calendar, DollarSign, Clock, Link2, FileText,
  Loader2, Plus,
} from "lucide-react";
import { toast } from "sonner";
import Link from "next/link";
import { api } from "@/lib/api-client";

interface Stage { slug: string; name: string; color: string; is_won: boolean; is_lost: boolean; }
interface Activity {
  id: string; activity_type: string; note: string | null;
  actor_name: string | null; old_value: string | null; new_value: string | null; created_at: string;
}
interface Deal {
  id: string; title: string; stage: string; value: number | null; currency: string;
  close_date: string | null; customer_id: string | null; owner_id: string | null;
  notes: string | null; probability: number | null;
  win_reason: string | null; loss_reason: string | null; closed_at: string | null;
  quote_id: string | null; invoice_id: string | null; sales_cycle_days: number | null;
  created_at: string; updated_at: string; activities: Activity[];
}

const ACTIVITY_LABELS: Record<string, string> = {
  call: "Call", email: "Email", meeting: "Meeting", note: "Note", stage_change: "Stage change",
};
const ACTIVITY_TYPES = ["call", "email", "meeting", "note"];

function fmt(v: number | null, currency = "SEK") {
  if (v == null) return "—";
  return v.toLocaleString(undefined, { maximumFractionDigits: 0 }) + " " + currency;
}

export default function DealDetailPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const [deal, setDeal] = useState<Deal | null>(null);
  const [stages, setStages] = useState<Stage[]>([]);
  const [loading, setLoading] = useState(true);
  const [editing, setEditing] = useState(false);
  const [editTitle, setEditTitle] = useState("");
  const [editValue, setEditValue] = useState("");
  const [editCloseDate, setEditCloseDate] = useState("");
  const [editProbability, setEditProbability] = useState("");
  const [editNotes, setEditNotes] = useState("");
  const [saving, setSaving] = useState(false);
  const [activityType, setActivityType] = useState("note");
  const [activityNote, setActivityNote] = useState("");
  const [loggingActivity, setLoggingActivity] = useState(false);

  const load = async () => {
    try {
      const [d, s] = await Promise.all([
        api.get<Deal>(`/api/crm/deals/${id}`),
        api.get<Stage[]>("/api/crm/stages"),
      ]);
      setDeal(d);
      setStages(s);
      setEditTitle(d.title);
      setEditValue(d.value !== null ? String(d.value) : "");
      setEditCloseDate(d.close_date ?? "");
      setEditProbability(d.probability !== null ? String(d.probability) : "");
      setEditNotes(d.notes ?? "");
    } catch { toast.error("Failed to load deal"); }
    finally { setLoading(false); }
  };

  useEffect(() => { load(); }, [id]);

  const saveEdits = async () => {
    setSaving(true);
    try {
      await api.patch(`/api/crm/deals/${id}`, {
        title: editTitle.trim() || undefined,
        value: editValue ? parseFloat(editValue) : undefined,
        close_date: editCloseDate || undefined,
        probability: editProbability ? parseInt(editProbability) : undefined,
        notes: editNotes || undefined,
      });
      await load();
      setEditing(false);
      toast.success("Saved");
    } catch { toast.error("Failed to save"); }
    finally { setSaving(false); }
  };

  const moveStage = async (slug: string) => {
    try {
      await api.patch(`/api/crm/deals/${id}`, { stage: slug });
      await load();
    } catch { toast.error("Failed to move stage"); }
  };

  const logActivity = async () => {
    if (!activityNote.trim()) return;
    setLoggingActivity(true);
    try {
      await api.post(`/api/crm/deals/${id}/activities`, {
        activity_type: activityType, note: activityNote.trim(),
      });
      setActivityNote("");
      await load();
      toast.success("Activity logged");
    } catch { toast.error("Failed to log activity"); }
    finally { setLoggingActivity(false); }
  };

  const deleteDeal = async () => {
    if (!confirm("Delete this deal?")) return;
    try {
      await api.delete(`/api/crm/deals/${id}`);
      router.push("/crm");
    } catch { toast.error("Failed to delete deal"); }
  };

  if (loading) return <div className="p-8 flex justify-center"><Loader2 size={24} className="animate-spin text-gray-300" /></div>;
  if (!deal) return <div className="p-8 text-gray-400">Deal not found.</div>;

  const stageInfo = stages.find(s => s.slug === deal.stage);
  const isClosed = stageInfo?.is_won || stageInfo?.is_lost;

  return (
    <div className="p-6 max-w-4xl space-y-6">
      {/* Back + title */}
      <div className="flex items-start justify-between gap-4">
        <div className="flex items-start gap-3">
          <button onClick={() => router.back()} className="mt-0.5 p-1.5 rounded hover:bg-gray-100">
            <ArrowLeft size={16} className="text-gray-500" />
          </button>
          <div>
            {editing ? (
              <input
                className="text-2xl font-bold border-b border-[#1a2332] outline-none w-full"
                value={editTitle}
                onChange={e => setEditTitle(e.target.value)}
              />
            ) : (
              <h1 className="text-2xl font-bold">{deal.title}</h1>
            )}
            <div className="flex items-center gap-2 mt-1">
              {stageInfo && (
                <span className={`px-2 py-0.5 rounded text-xs font-medium ${stageInfo.color}`}>
                  {stageInfo.is_won && <CheckCircle2 size={10} className="inline mr-0.5" />}
                  {stageInfo.is_lost && <XCircle size={10} className="inline mr-0.5" />}
                  {stageInfo.name}
                </span>
              )}
              <span className="text-xs text-gray-400">Created {new Date(deal.created_at).toLocaleDateString()}</span>
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
              <button onClick={() => setEditing(true)} className="flex items-center gap-1.5 px-3 py-1.5 border rounded text-sm hover:bg-gray-50">
                <Pencil size={13} /> Edit
              </button>
              <button onClick={deleteDeal} className="px-3 py-1.5 border border-red-200 text-red-500 rounded text-sm hover:bg-red-50">Delete</button>
            </>
          )}
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* ── Left: details ─────────────────────────────────────────── */}
        <div className="lg:col-span-2 space-y-4">
          {/* KPI cards */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            {[
              { label: "Value", icon: <DollarSign size={14} />, value: fmt(deal.value, deal.currency) },
              { label: "Probability", icon: <Target size={14} />, value: editing ? (
                <input type="number" min={0} max={100} className="w-full border-b outline-none text-sm" value={editProbability} onChange={e => setEditProbability(e.target.value)} />
              ) : deal.probability !== null ? `${deal.probability}%` : "—" },
              { label: "Close date", icon: <Calendar size={14} />, value: editing ? (
                <input type="date" className="w-full border-b outline-none text-sm" value={editCloseDate} onChange={e => setEditCloseDate(e.target.value)} />
              ) : deal.close_date ?? "—" },
              { label: "Sales cycle", icon: <Clock size={14} />, value: deal.sales_cycle_days !== null ? `${deal.sales_cycle_days}d` : "—" },
            ].map(item => (
              <div key={item.label} className="bg-white border rounded-lg p-3 space-y-1">
                <div className="flex items-center gap-1.5 text-xs text-gray-400">
                  {item.icon} {item.label}
                </div>
                <div className="text-sm font-semibold text-gray-900">{item.value}</div>
              </div>
            ))}
          </div>

          {/* Value edit */}
          {editing && (
            <div className="bg-white border rounded-lg p-4 space-y-3">
              <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide">Edit details</p>
              <div>
                <label className="text-xs text-gray-400">Value</label>
                <input type="number" className="mt-1 w-full border rounded px-3 py-1.5 text-sm focus:outline-none" value={editValue} onChange={e => setEditValue(e.target.value)} />
              </div>
            </div>
          )}

          {/* Notes */}
          <div className="bg-white border rounded-lg p-4">
            <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">Notes</p>
            {editing ? (
              <textarea rows={4} className="w-full border rounded px-3 py-2 text-sm resize-none focus:outline-none focus:ring-1" value={editNotes} onChange={e => setEditNotes(e.target.value)} />
            ) : (
              <p className="text-sm text-gray-700 whitespace-pre-wrap">{deal.notes || <span className="text-gray-300">No notes</span>}</p>
            )}
          </div>

          {/* Win / loss reason */}
          {(deal.win_reason || deal.loss_reason) && (
            <div className={`border rounded-lg p-4 ${deal.win_reason ? "bg-green-50 border-green-200" : "bg-red-50 border-red-200"}`}>
              <p className={`text-xs font-semibold uppercase tracking-wide mb-1 ${deal.win_reason ? "text-green-700" : "text-red-600"}`}>
                {deal.win_reason ? "Win reason" : "Loss reason"}
              </p>
              <p className="text-sm">{deal.win_reason || deal.loss_reason}</p>
            </div>
          )}

          {/* Links */}
          {(deal.quote_id || deal.invoice_id) && (
            <div className="bg-white border rounded-lg p-4 space-y-2">
              <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide">Linked</p>
              {deal.quote_id && (
                <Link href={`/quotes/${deal.quote_id}`} className="flex items-center gap-2 text-sm text-blue-600 hover:underline">
                  <FileText size={13} /> Quote
                </Link>
              )}
              {deal.invoice_id && (
                <Link href={`/invoices/${deal.invoice_id}`} className="flex items-center gap-2 text-sm text-blue-600 hover:underline">
                  <Link2 size={13} /> Invoice
                </Link>
              )}
            </div>
          )}

          {/* Activity log */}
          <div className="bg-white border rounded-lg p-4 space-y-3">
            <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide">Activity Log</p>

            {/* Log form */}
            <div className="space-y-2 border-b pb-3">
              <div className="flex gap-1.5">
                {ACTIVITY_TYPES.map(t => (
                  <button key={t} onClick={() => setActivityType(t)}
                    className={`px-2 py-0.5 rounded text-xs capitalize ${activityType === t ? "bg-[#1a2332] text-white" : "bg-gray-100 hover:bg-gray-200"}`}>
                    {t}
                  </button>
                ))}
              </div>
              <textarea
                rows={2}
                value={activityNote}
                onChange={e => setActivityNote(e.target.value)}
                placeholder="What happened?"
                className="w-full border rounded px-3 py-1.5 text-sm resize-none focus:outline-none focus:ring-1"
              />
              <button onClick={logActivity} disabled={loggingActivity || !activityNote.trim()}
                className="flex items-center gap-1.5 px-3 py-1.5 bg-[#1a2332] text-white rounded text-sm hover:opacity-90 disabled:opacity-40">
                <Plus size={13} />
                {loggingActivity ? "Logging…" : `Log ${activityType}`}
              </button>
            </div>

            {/* Timeline */}
            <div className="space-y-3">
              {[...(deal.activities ?? [])].reverse().map(a => (
                <div key={a.id} className="flex gap-3 text-xs">
                  <div className="mt-0.5 w-6 h-6 rounded-full bg-gray-100 flex items-center justify-center shrink-0 text-gray-500">
                    {a.activity_type === "call" && <Phone size={11} />}
                    {a.activity_type === "email" && <Mail size={11} />}
                    {a.activity_type === "meeting" && <Users size={11} />}
                    {(a.activity_type === "note" || a.activity_type === "stage_change") && <Pencil size={11} />}
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center justify-between gap-2">
                      <span className="font-medium text-gray-700 capitalize">{ACTIVITY_LABELS[a.activity_type] ?? a.activity_type}</span>
                      <span className="text-gray-300 shrink-0">{new Date(a.created_at).toLocaleString()}</span>
                    </div>
                    {a.activity_type === "stage_change"
                      ? <p className="text-gray-500 mt-0.5">{a.old_value} → {a.new_value}</p>
                      : a.note && <p className="text-gray-600 mt-0.5">{a.note}</p>
                    }
                    {a.actor_name && <p className="text-gray-400">by {a.actor_name}</p>}
                  </div>
                </div>
              ))}
              {deal.activities.length === 0 && <p className="text-gray-300 text-xs">No activity yet</p>}
            </div>
          </div>
        </div>

        {/* ── Right: stage pipeline ──────────────────────────────────── */}
        <div className="space-y-3">
          <div className="bg-white border rounded-lg p-4">
            <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-3">Pipeline Stage</p>
            <div className="space-y-1.5">
              {stages.map((s, i) => (
                <button
                  key={s.slug}
                  onClick={() => moveStage(s.slug)}
                  className={`w-full flex items-center gap-2 px-3 py-2 rounded-lg text-sm text-left transition-colors ${deal.stage === s.slug ? "bg-[#1a2332] text-white" : "hover:bg-gray-50"}`}
                >
                  <span className={`w-5 h-5 rounded-full flex items-center justify-center text-xs shrink-0 ${deal.stage === s.slug ? "bg-white/20 text-white" : "bg-gray-100 text-gray-500"}`}>
                    {i + 1}
                  </span>
                  <span className="flex-1">{s.name}</span>
                  {s.is_won && <CheckCircle2 size={13} className={deal.stage === s.slug ? "text-white" : "text-green-500"} />}
                  {s.is_lost && <XCircle size={13} className={deal.stage === s.slug ? "text-white" : "text-red-400"} />}
                </button>
              ))}
            </div>
          </div>

          {/* Closed info */}
          {deal.closed_at && (
            <div className="bg-white border rounded-lg p-4 space-y-1 text-xs">
              <p className="font-semibold text-gray-500 uppercase tracking-wide">Closed</p>
              <p className="text-gray-700">{new Date(deal.closed_at).toLocaleDateString()}</p>
              {deal.sales_cycle_days !== null && (
                <p className="text-gray-400">{deal.sales_cycle_days} days from lead to close</p>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
