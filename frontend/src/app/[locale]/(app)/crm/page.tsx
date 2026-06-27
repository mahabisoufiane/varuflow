"use client";
import { useCallback, useEffect, useRef, useState } from "react";
import {
  Target, Plus, Loader2, X, List, BarChart2, CheckCircle2,
  XCircle, Phone, Mail, Users, Calendar, DollarSign, Pencil,
} from "lucide-react";
import { toast } from "sonner";
import Link from "next/link";
import { api } from "@/lib/api-client";

interface Stage {
  slug: string;
  name: string;
  color: string;
  probability: number;
  is_won: boolean;
  is_lost: boolean;
  order_idx: number;
}

interface Deal {
  id: string;
  title: string;
  stage: string;
  value: number | null;
  currency: string;
  close_date: string | null;
  customer_id: string | null;
  owner_id: string | null;
  notes: string | null;
  probability: number | null;
  win_reason: string | null;
  loss_reason: string | null;
  closed_at: string | null;
  quote_id: string | null;
  invoice_id: string | null;
  sales_cycle_days: number | null;
  created_at: string;
}

interface PipelineCol {
  stage: Stage;
  deals: Deal[];
  total_value: number;
}

type PipelineData = { stages: Stage[]; pipeline: Record<string, PipelineCol> };

const ACTIVITY_ICONS: Record<string, React.ReactNode> = {
  call:         <Phone size={12} />,
  email:        <Mail size={12} />,
  meeting:      <Users size={12} />,
  note:         <Pencil size={12} />,
  stage_change: <Target size={12} />,
};

const ACTIVITY_TYPES = ["call", "email", "meeting", "note"];

function fmt(v: number | null, currency = "SEK") {
  if (v === null || v === undefined) return "—";
  return v.toLocaleString(undefined, { maximumFractionDigits: 0 }) + " " + currency;
}

export default function CrmPipelinePage() {
  const [data, setData] = useState<PipelineData | null>(null);
  const [loading, setLoading] = useState(true);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [selectedDeal, setSelectedDeal] = useState<(Deal & { activities?: any[] }) | null>(null);
  const [showNew, setShowNew] = useState(false);
  const [newTitle, setNewTitle] = useState("");
  const [newValue, setNewValue] = useState("");
  const [newCloseDate, setNewCloseDate] = useState("");
  const [newStage, setNewStage] = useState("lead");
  const [saving, setSaving] = useState(false);

  // Win/loss reason modal
  const [closeModal, setCloseModal] = useState<{ deal: Deal; targetStage: string } | null>(null);
  const [closeReason, setCloseReason] = useState("");

  // Activity log
  const [activityType, setActivityType] = useState("note");
  const [activityNote, setActivityNote] = useState("");
  const [loggingActivity, setLoggingActivity] = useState(false);

  // Drag state
  const dragDeal = useRef<Deal | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const res = await api.get<PipelineData>("/api/crm/pipeline");
      setData(res);
      if (res.stages?.[0]?.slug) setNewStage(res.stages[0].slug);
    } catch { toast.error("Failed to load pipeline"); }
    finally { setLoading(false); }
  }, []);

  useEffect(() => { load(); }, [load]);

  const handleCreate = async () => {
    if (!newTitle.trim()) return;
    setSaving(true);
    try {
      await api.post("/api/crm/deals", {
        title: newTitle.trim(),
        stage: newStage,
        value: newValue ? parseFloat(newValue) : null,
        close_date: newCloseDate || null,
      });
      setShowNew(false);
      setNewTitle(""); setNewValue(""); setNewCloseDate("");
      await load();
      toast.success("Deal created");
    } catch { toast.error("Failed to create deal"); }
    finally { setSaving(false); }
  };

  const moveDeal = async (deal: Deal, targetStage: string) => {
    if (deal.stage === targetStage) return;
    const stageInfo = data?.stages.find(s => s.slug === targetStage);
    if (stageInfo && (stageInfo.is_won || stageInfo.is_lost)) {
      setCloseModal({ deal, targetStage });
      setCloseReason("");
      return;
    }
    try {
      await api.patch(`/api/crm/deals/${deal.id}`, { stage: targetStage });
      await load();
    } catch { toast.error("Failed to move deal"); }
  };

  const confirmClose = async () => {
    if (!closeModal) return;
    const { deal, targetStage } = closeModal;
    const stageInfo = data?.stages.find(s => s.slug === targetStage);
    setSaving(true);
    try {
      await api.patch(`/api/crm/deals/${deal.id}`, {
        stage: targetStage,
        win_reason: stageInfo?.is_won ? closeReason || null : null,
        loss_reason: stageInfo?.is_lost ? closeReason || null : null,
      });
      setCloseModal(null);
      setCloseReason("");
      await load();
      toast.success(stageInfo?.is_won ? "Deal won 🎉" : "Deal marked as lost");
    } catch { toast.error("Failed to update deal"); }
    finally { setSaving(false); }
  };

  const openDetail = async (deal: Deal) => {
    setSelectedId(deal.id);
    try {
      const d = await api.get<Deal & { activities: any[] }>(`/api/crm/deals/${deal.id}`);
      setSelectedDeal(d);
    } catch { toast.error("Failed to load deal"); }
  };

  const handleLogActivity = async () => {
    if (!selectedDeal || !activityNote.trim()) return;
    setLoggingActivity(true);
    try {
      await api.post(`/api/crm/deals/${selectedDeal.id}/activities`, {
        activity_type: activityType,
        note: activityNote.trim(),
      });
      setActivityNote("");
      const d = await api.get<Deal & { activities: any[] }>(`/api/crm/deals/${selectedDeal.id}`);
      setSelectedDeal(d);
      await load();
    } catch { toast.error("Failed to log activity"); }
    finally { setLoggingActivity(false); }
  };

  const stages = data?.stages ?? [];

  const totalPipeline = stages
    .filter(s => !s.is_won && !s.is_lost)
    .reduce((acc, s) => acc + (data?.pipeline[s.slug]?.total_value ?? 0), 0);

  const totalWeighted = stages
    .filter(s => !s.is_won && !s.is_lost)
    .reduce((acc, s) => {
      const col = data?.pipeline[s.slug];
      if (!col) return acc;
      return acc + col.deals.reduce((a, d) => {
        const p = (d.probability ?? s.probability) / 100;
        return a + (d.value ?? 0) * p;
      }, 0);
    }, 0);

  return (
    <div className="flex flex-col h-[calc(100vh-4rem)] overflow-hidden">
      {/* ── Header ─────────────────────────────────────────────────────── */}
      <div className="px-6 pt-5 pb-3 border-b bg-white shrink-0">
        <div className="flex items-center justify-between flex-wrap gap-2">
          <div className="flex items-center gap-2">
            <Target size={20} className="text-[#1a2332]" />
            <h1 className="text-xl font-bold">Sales Pipeline</h1>
            {!loading && (
              <span className="text-xs text-gray-400 ml-2">
                {fmt(totalPipeline)} pipeline · {fmt(totalWeighted)} weighted
              </span>
            )}
          </div>
          <div className="flex items-center gap-2">
            <Link href="/crm/list" className="flex items-center gap-1.5 px-3 py-1.5 border rounded text-sm hover:bg-gray-50 text-gray-600">
              <List size={14} /> List
            </Link>
            <Link href="/crm/analytics" className="flex items-center gap-1.5 px-3 py-1.5 border rounded text-sm hover:bg-gray-50 text-gray-600">
              <BarChart2 size={14} /> Analytics
            </Link>
            <button
              onClick={() => setShowNew(s => !s)}
              className="flex items-center gap-1.5 px-3 py-1.5 bg-[#1a2332] text-white rounded text-sm hover:opacity-90"
            >
              <Plus size={14} /> New Deal
            </button>
          </div>
        </div>

        {/* New deal form */}
        {showNew && (
          <div className="mt-3 p-4 bg-gray-50 rounded-lg border space-y-3">
            <div className="flex flex-wrap gap-2">
              <input
                autoFocus
                className="flex-1 min-w-48 border rounded px-3 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-[#1a2332]"
                placeholder="Deal title…"
                value={newTitle}
                onChange={e => setNewTitle(e.target.value)}
                onKeyDown={e => e.key === "Enter" && handleCreate()}
              />
              <input
                type="number"
                className="w-36 border rounded px-3 py-1.5 text-sm focus:outline-none"
                placeholder="Value (SEK)"
                value={newValue}
                onChange={e => setNewValue(e.target.value)}
              />
              <input
                type="date"
                className="w-40 border rounded px-3 py-1.5 text-sm focus:outline-none"
                value={newCloseDate}
                onChange={e => setNewCloseDate(e.target.value)}
              />
              <select
                className="border rounded px-3 py-1.5 text-sm focus:outline-none"
                value={newStage}
                onChange={e => setNewStage(e.target.value)}
              >
                {stages.map(s => <option key={s.slug} value={s.slug}>{s.name}</option>)}
              </select>
              <button
                onClick={handleCreate}
                disabled={saving || !newTitle.trim()}
                className="px-4 py-1.5 bg-[#1a2332] text-white rounded text-sm hover:opacity-90 disabled:opacity-50"
              >
                {saving ? <Loader2 size={14} className="animate-spin" /> : "Create"}
              </button>
              <button onClick={() => setShowNew(false)} className="px-2 py-1.5 text-gray-400 hover:text-gray-600">
                <X size={14} />
              </button>
            </div>
          </div>
        )}
      </div>

      {/* ── Board ──────────────────────────────────────────────────────── */}
      <div className="flex-1 overflow-x-auto">
        {loading ? (
          <div className="flex items-center justify-center h-full">
            <Loader2 size={28} className="animate-spin text-gray-300" />
          </div>
        ) : (
          <div className="flex gap-3 p-4 h-full min-w-max">
            {stages.map(stage => {
              const col = data?.pipeline[stage.slug];
              const deals = col?.deals ?? [];
              const colValue = col?.total_value ?? 0;

              return (
                <div
                  key={stage.slug}
                  className="flex flex-col w-64 shrink-0"
                  onDragOver={e => e.preventDefault()}
                  onDrop={e => {
                    e.preventDefault();
                    if (dragDeal.current) moveDeal(dragDeal.current, stage.slug);
                  }}
                >
                  {/* Column header */}
                  <div className={`rounded-t-lg px-3 py-2 ${stage.color ?? "bg-gray-100"}`}>
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-1.5">
                        {stage.is_won && <CheckCircle2 size={13} className="text-green-700" />}
                        {stage.is_lost && <XCircle size={13} className="text-red-600" />}
                        <span className="text-xs font-semibold text-gray-800">{stage.name}</span>
                        <span className="text-xs text-gray-500 ml-1">{deals.length}</span>
                      </div>
                      <span className="text-xs text-gray-600 font-medium">
                        {colValue > 0 ? colValue.toLocaleString(undefined, { maximumFractionDigits: 0 }) : ""}
                      </span>
                    </div>
                  </div>

                  {/* Cards */}
                  <div className="flex-1 overflow-y-auto bg-gray-50 rounded-b-lg border border-t-0 p-2 space-y-2 min-h-20">
                    {deals.map(deal => (
                      <div
                        key={deal.id}
                        draggable
                        onDragStart={() => { dragDeal.current = deal; }}
                        onDragEnd={() => { dragDeal.current = null; }}
                        onClick={() => openDetail(deal)}
                        className={`bg-white rounded-lg border p-3 cursor-pointer hover:shadow-sm transition-shadow space-y-1.5 ${selectedId === deal.id ? "ring-2 ring-[#1a2332]" : ""}`}
                      >
                        <p className="text-xs font-semibold text-gray-900 leading-tight line-clamp-2">{deal.title}</p>
                        {deal.value !== null && (
                          <div className="flex items-center gap-1 text-xs text-gray-600">
                            <DollarSign size={11} className="shrink-0" />
                            {fmt(deal.value, deal.currency)}
                          </div>
                        )}
                        {deal.close_date && (
                          <div className="flex items-center gap-1 text-xs text-gray-400">
                            <Calendar size={11} className="shrink-0" />
                            {deal.close_date}
                          </div>
                        )}
                        {deal.probability !== null && (
                          <div className="flex items-center gap-1.5">
                            <div className="flex-1 h-1 bg-gray-100 rounded-full overflow-hidden">
                              <div
                                className="h-full bg-blue-400 rounded-full"
                                style={{ width: `${deal.probability}%` }}
                              />
                            </div>
                            <span className="text-[10px] text-gray-400 shrink-0">{deal.probability}%</span>
                          </div>
                        )}
                      </div>
                    ))}
                    {deals.length === 0 && (
                      <p className="text-xs text-gray-300 text-center py-4">Drop deals here</p>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* ── Win/Loss reason modal ────────────────────────────────────── */}
      {closeModal && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-xl w-full max-w-md p-6 space-y-4 shadow-xl">
            <div className="flex items-center gap-2">
              {data?.stages.find(s => s.slug === closeModal.targetStage)?.is_won
                ? <CheckCircle2 size={20} className="text-green-600" />
                : <XCircle size={20} className="text-red-500" />
              }
              <h2 className="font-semibold text-lg">
                {data?.stages.find(s => s.slug === closeModal.targetStage)?.is_won
                  ? `Mark "${closeModal.deal.title}" as won`
                  : `Mark "${closeModal.deal.title}" as lost`}
              </h2>
            </div>
            <div>
              <label className="text-xs font-medium text-gray-500 block mb-1">
                {data?.stages.find(s => s.slug === closeModal.targetStage)?.is_won ? "Win reason" : "Loss reason"}
                {" "}(optional)
              </label>
              <textarea
                rows={3}
                autoFocus
                value={closeReason}
                onChange={e => setCloseReason(e.target.value)}
                placeholder="e.g. Price, competitor, timing…"
                className="w-full border rounded-lg px-3 py-2 text-sm resize-none focus:outline-none focus:ring-1 focus:ring-[#1a2332]"
              />
            </div>
            <div className="flex gap-3">
              <button
                onClick={confirmClose}
                disabled={saving}
                className={`flex-1 py-2 rounded-lg text-white text-sm font-medium disabled:opacity-50 ${data?.stages.find(s => s.slug === closeModal.targetStage)?.is_won ? "bg-green-600 hover:bg-green-700" : "bg-red-600 hover:bg-red-700"}`}
              >
                {saving ? <Loader2 size={14} className="animate-spin mx-auto" /> : "Confirm"}
              </button>
              <button
                onClick={() => setCloseModal(null)}
                className="flex-1 py-2 rounded-lg border text-sm hover:bg-gray-50"
              >
                Cancel
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ── Deal detail side-panel ─────────────────────────────────── */}
      {selectedDeal && (
        <div className="fixed inset-y-0 right-0 w-96 bg-white border-l shadow-xl flex flex-col z-40">
          <div className="flex items-center justify-between px-4 py-3 border-b shrink-0">
            <div className="min-w-0">
              <h2 className="font-semibold text-sm truncate">{selectedDeal.title}</h2>
              <p className="text-xs text-gray-400">{stages.find(s => s.slug === selectedDeal.stage)?.name ?? selectedDeal.stage}</p>
            </div>
            <div className="flex items-center gap-2 shrink-0">
              <Link href={`/crm/deals/${selectedDeal.id}`} className="p-1.5 rounded hover:bg-gray-100" title="Open full page">
                <Pencil size={14} className="text-gray-500" />
              </Link>
              <button onClick={() => { setSelectedDeal(null); setSelectedId(null); }} className="p-1.5 rounded hover:bg-gray-100">
                <X size={16} className="text-gray-500" />
              </button>
            </div>
          </div>

          <div className="flex-1 overflow-y-auto p-4 space-y-4">
            {/* Stage quick-move */}
            <div className="flex flex-wrap gap-1.5">
              {stages.map(s => (
                <button
                  key={s.slug}
                  onClick={() => moveDeal(selectedDeal, s.slug)}
                  className={`px-2 py-0.5 rounded text-xs font-medium border transition-colors ${selectedDeal.stage === s.slug ? "bg-[#1a2332] text-white border-[#1a2332]" : "hover:bg-gray-50"}`}
                >
                  {s.name}
                </button>
              ))}
            </div>

            {/* Key metrics */}
            <div className="grid grid-cols-2 gap-2 text-xs">
              <div className="bg-gray-50 rounded p-2">
                <p className="text-gray-400">Value</p>
                <p className="font-semibold">{fmt(selectedDeal.value, selectedDeal.currency)}</p>
              </div>
              <div className="bg-gray-50 rounded p-2">
                <p className="text-gray-400">Probability</p>
                <p className="font-semibold">{selectedDeal.probability !== null ? `${selectedDeal.probability}%` : "—"}</p>
              </div>
              <div className="bg-gray-50 rounded p-2">
                <p className="text-gray-400">Close date</p>
                <p className="font-semibold">{selectedDeal.close_date ?? "—"}</p>
              </div>
              <div className="bg-gray-50 rounded p-2">
                <p className="text-gray-400">Cycle days</p>
                <p className="font-semibold">{selectedDeal.sales_cycle_days !== null ? selectedDeal.sales_cycle_days : "—"}</p>
              </div>
            </div>

            {selectedDeal.win_reason && (
              <div className="bg-green-50 border border-green-200 rounded p-2 text-xs text-green-700">
                <span className="font-medium">Won: </span>{selectedDeal.win_reason}
              </div>
            )}
            {selectedDeal.loss_reason && (
              <div className="bg-red-50 border border-red-200 rounded p-2 text-xs text-red-700">
                <span className="font-medium">Lost: </span>{selectedDeal.loss_reason}
              </div>
            )}

            {selectedDeal.notes && (
              <div className="text-xs text-gray-600 bg-gray-50 rounded p-2 whitespace-pre-wrap">
                {selectedDeal.notes}
              </div>
            )}

            {/* Activity timeline */}
            <div>
              <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">Activity</p>
              {(selectedDeal.activities ?? []).length === 0 && (
                <p className="text-xs text-gray-300 py-2">No activity yet</p>
              )}
              <div className="space-y-2">
                {[...(selectedDeal.activities ?? [])].reverse().map((a: any) => (
                  <div key={a.id} className="flex gap-2 text-xs">
                    <span className="mt-0.5 shrink-0 text-gray-400">
                      {ACTIVITY_ICONS[a.activity_type] ?? <Pencil size={12} />}
                    </span>
                    <div className="min-w-0">
                      {a.activity_type === "stage_change"
                        ? <p className="text-gray-500">Moved <span className="font-medium">{a.old_value}</span> → <span className="font-medium">{a.new_value}</span></p>
                        : <p className="text-gray-700">{a.note}</p>
                      }
                      <p className="text-gray-300">{new Date(a.created_at).toLocaleString()}</p>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {/* Log activity */}
            <div className="border-t pt-3 space-y-2">
              <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide">Log activity</p>
              <div className="flex gap-1.5">
                {ACTIVITY_TYPES.map(t => (
                  <button
                    key={t}
                    onClick={() => setActivityType(t)}
                    className={`px-2 py-1 rounded text-xs capitalize ${activityType === t ? "bg-[#1a2332] text-white" : "bg-gray-100 hover:bg-gray-200"}`}
                  >
                    {t}
                  </button>
                ))}
              </div>
              <textarea
                rows={2}
                value={activityNote}
                onChange={e => setActivityNote(e.target.value)}
                placeholder="Add a note…"
                className="w-full border rounded px-2 py-1.5 text-xs resize-none focus:outline-none focus:ring-1 focus:ring-[#1a2332]"
              />
              <button
                onClick={handleLogActivity}
                disabled={loggingActivity || !activityNote.trim()}
                className="w-full py-1.5 bg-[#1a2332] text-white rounded text-xs hover:opacity-90 disabled:opacity-40"
              >
                {loggingActivity ? <Loader2 size={12} className="animate-spin mx-auto" /> : "Log"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
