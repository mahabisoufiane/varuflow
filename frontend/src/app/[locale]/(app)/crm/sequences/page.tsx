"use client";

import { useCallback, useEffect, useState } from "react";
import { Mail, Plus, Loader2, X, Trash2, ToggleLeft, ToggleRight } from "lucide-react";
import { toast } from "sonner";
import { api } from "@/lib/api-client";

interface Step {
  id: string;
  step_number: number;
  delay_days: number;
  subject: string;
  body_html: string;
}

interface Sequence {
  id: string;
  name: string;
  trigger_type: string | null;
  trigger_value: string | null;
  is_active: boolean;
  enrollment_count: number;
  steps?: Step[];
}

export default function CrmSequencesPage() {
  const [sequences, setSequences] = useState<Sequence[]>([]);
  const [loading, setLoading] = useState(true);
  const [selected, setSelected] = useState<Sequence | null>(null);
  const [showNew, setShowNew] = useState(false);
  const [newName, setNewName] = useState("");
  const [saving, setSaving] = useState(false);
  const [showStepForm, setShowStepForm] = useState(false);
  const [stepSubject, setStepSubject] = useState("");
  const [stepBody, setStepBody] = useState("");
  const [stepDelay, setStepDelay] = useState("0");
  const [enrollEmails, setEnrollEmails] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const data = await api.get<Sequence[]>("/api/crm/sequences");
      setSequences(data);
    } catch {
      toast.error("Failed to load sequences");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  async function loadDetail(id: string) {
    try {
      const d = await api.get<Sequence>(`/api/crm/sequences/${id}`);
      setSelected(d);
    } catch {
      toast.error("Failed to load sequence");
    }
  }

  async function handleCreate() {
    if (!newName.trim()) return;
    setSaving(true);
    try {
      await api.post("/api/crm/sequences", { name: newName });
      setShowNew(false); setNewName("");
      toast.success("Sequence created");
      load();
    } catch {
      toast.error("Failed to create sequence");
    } finally {
      setSaving(false);
    }
  }

  async function toggleActive(seq: Sequence) {
    try {
      await api.patch(`/api/crm/sequences/${seq.id}`, { is_active: !seq.is_active });
      setSequences((prev) => prev.map((s) => s.id === seq.id ? { ...s, is_active: !seq.is_active } : s));
      if (selected?.id === seq.id) setSelected((s) => s ? { ...s, is_active: !seq.is_active } : s);
    } catch {
      toast.error("Failed to update sequence");
    }
  }

  async function addStep() {
    if (!selected || !stepSubject.trim() || !stepBody.trim()) return;
    setSaving(true);
    try {
      const nextNum = (selected.steps?.length ?? 0) + 1;
      await api.post(`/api/crm/sequences/${selected.id}/steps`, {
        step_number: nextNum,
        delay_days: parseInt(stepDelay) || 0,
        subject: stepSubject,
        body_html: stepBody,
      });
      setStepSubject(""); setStepBody(""); setStepDelay("0"); setShowStepForm(false);
      loadDetail(selected.id);
    } catch {
      toast.error("Failed to add step");
    } finally {
      setSaving(false);
    }
  }

  async function deleteStep(stepId: string) {
    if (!selected) return;
    try {
      await api.delete(`/api/crm/sequences/${selected.id}/steps/${stepId}`);
      loadDetail(selected.id);
    } catch {
      toast.error("Failed to delete step");
    }
  }

  async function handleEnroll() {
    if (!selected || !enrollEmails.trim()) return;
    const emails = enrollEmails.split(/[\n,]+/).map((e) => e.trim()).filter(Boolean);
    try {
      const r = await api.post<{ enrolled: number }>(`/api/crm/sequences/${selected.id}/enroll`, { emails });
      toast.success(`Enrolled ${r.enrolled} contacts`);
      setEnrollEmails("");
    } catch {
      toast.error("Failed to enroll contacts");
    }
  }

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Mail className="h-5 w-5 vf-text-m" />
          <h1 className="text-[15px] font-semibold vf-text-1">Email Sequences</h1>
        </div>
        <button
          onClick={() => setShowNew(true)}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-indigo-600 text-white text-xs font-medium hover:bg-indigo-700 transition-colors"
        >
          <Plus className="h-3.5 w-3.5" /> New Sequence
        </button>
      </div>

      <div className="grid lg:grid-cols-[280px_1fr] gap-5">
        {/* Sequence list */}
        <div className="space-y-2">
          {showNew && (
            <div className="vf-card p-3 space-y-2">
              <input
                autoFocus
                type="text"
                placeholder="Sequence name"
                value={newName}
                onChange={(e) => setNewName(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && handleCreate()}
                className="w-full rounded-lg px-3 py-2 text-sm vf-input"
              />
              <div className="flex gap-2">
                <button onClick={handleCreate} disabled={saving} className="flex-1 py-1.5 rounded-lg bg-indigo-600 text-white text-xs font-medium hover:bg-indigo-700 disabled:opacity-50">
                  {saving ? <Loader2 className="h-3.5 w-3.5 animate-spin mx-auto" /> : "Create"}
                </button>
                <button onClick={() => setShowNew(false)} className="px-3 py-1.5 rounded-lg vf-btn-ghost text-xs">Cancel</button>
              </div>
            </div>
          )}
          {loading ? (
            <div className="flex justify-center py-8"><Loader2 className="h-5 w-5 animate-spin text-gray-400" /></div>
          ) : sequences.length === 0 ? (
            <p className="text-sm vf-text-m text-center py-8">No sequences yet.</p>
          ) : sequences.map((seq) => (
            <div
              key={seq.id}
              onClick={() => loadDetail(seq.id)}
              className={`vf-card p-3 cursor-pointer hover:bg-[var(--vf-hover)] transition-colors ${selected?.id === seq.id ? "border-indigo-500/50" : ""}`}
            >
              <div className="flex items-start justify-between gap-2">
                <div className="min-w-0">
                  <p className="text-[13px] font-medium vf-text-1 truncate">{seq.name}</p>
                  <p className="text-[11px] vf-text-m mt-0.5">{seq.enrollment_count} enrolled</p>
                  {seq.trigger_type && (
                    <span className="inline-block mt-1 px-1.5 py-0.5 rounded text-[10px] bg-indigo-500/10 text-indigo-500">
                      {seq.trigger_type}: {seq.trigger_value}
                    </span>
                  )}
                </div>
                <button
                  onClick={(e) => { e.stopPropagation(); toggleActive(seq); }}
                  className="shrink-0 vf-text-m hover:vf-text-1 transition-colors"
                >
                  {seq.is_active
                    ? <ToggleRight className="h-5 w-5 text-emerald-500" />
                    : <ToggleLeft className="h-5 w-5" />}
                </button>
              </div>
            </div>
          ))}
        </div>

        {/* Detail panel */}
        {selected && (
          <div className="vf-card p-5 space-y-5">
            <div className="flex items-center justify-between">
              <h2 className="text-[14px] font-semibold vf-text-1">{selected.name}</h2>
              <button onClick={() => setSelected(null)}><X className="h-4 w-4 vf-text-m" /></button>
            </div>

            {/* Steps */}
            <div>
              <div className="flex items-center justify-between mb-3">
                <h3 className="text-[12px] font-semibold vf-text-m uppercase tracking-wider">Steps</h3>
                <button
                  onClick={() => setShowStepForm(true)}
                  className="flex items-center gap-1 text-xs text-indigo-500 hover:text-indigo-600"
                >
                  <Plus className="h-3.5 w-3.5" /> Add Step
                </button>
              </div>
              <div className="space-y-2">
                {(selected.steps ?? []).length === 0 && !showStepForm && (
                  <p className="text-xs vf-text-m">No steps yet. Add the first step above.</p>
                )}
                {(selected.steps ?? []).map((step) => (
                  <div key={step.id} className="border border-[var(--vf-border)] rounded-xl p-3">
                    <div className="flex items-start justify-between gap-2">
                      <div className="min-w-0">
                        <p className="text-[12px] font-semibold vf-text-m">Step {step.step_number} · Day {step.delay_days}</p>
                        <p className="text-[13px] font-medium vf-text-1 truncate">{step.subject}</p>
                      </div>
                      <button
                        onClick={() => deleteStep(step.id)}
                        className="shrink-0 p-1 rounded hover:bg-red-50 text-red-500 transition-colors"
                      >
                        <Trash2 className="h-3.5 w-3.5" />
                      </button>
                    </div>
                  </div>
                ))}
                {showStepForm && (
                  <div className="border border-indigo-500/30 rounded-xl p-3 space-y-2">
                    <div className="flex items-center gap-2">
                      <span className="text-xs vf-text-m shrink-0">Delay (days):</span>
                      <input
                        type="number"
                        min="0"
                        value={stepDelay}
                        onChange={(e) => setStepDelay(e.target.value)}
                        className="w-16 rounded px-2 py-1 text-xs vf-input"
                      />
                    </div>
                    <input
                      type="text"
                      placeholder="Subject *"
                      value={stepSubject}
                      onChange={(e) => setStepSubject(e.target.value)}
                      className="w-full rounded-lg px-3 py-2 text-sm vf-input"
                    />
                    <textarea
                      placeholder="Email body (HTML) *"
                      value={stepBody}
                      onChange={(e) => setStepBody(e.target.value)}
                      rows={4}
                      className="w-full rounded-lg px-3 py-2 text-sm vf-input resize-none font-mono text-xs"
                    />
                    <div className="flex gap-2">
                      <button onClick={addStep} disabled={saving} className="flex-1 py-1.5 rounded-lg bg-indigo-600 text-white text-xs font-medium hover:bg-indigo-700 disabled:opacity-50">
                        {saving ? <Loader2 className="h-3.5 w-3.5 animate-spin mx-auto" /> : "Add Step"}
                      </button>
                      <button onClick={() => setShowStepForm(false)} className="px-3 py-1.5 rounded-lg vf-btn-ghost text-xs">Cancel</button>
                    </div>
                  </div>
                )}
              </div>
            </div>

            {/* Enroll */}
            <div className="border-t border-[var(--vf-border)] pt-4">
              <h3 className="text-[12px] font-semibold vf-text-m uppercase tracking-wider mb-2">Enroll contacts</h3>
              <textarea
                placeholder="Enter email addresses, one per line or comma-separated"
                value={enrollEmails}
                onChange={(e) => setEnrollEmails(e.target.value)}
                rows={3}
                className="w-full rounded-lg px-3 py-2 text-sm vf-input resize-none"
              />
              <button
                onClick={handleEnroll}
                className="mt-2 px-4 py-2 rounded-lg bg-indigo-600 text-white text-xs font-medium hover:bg-indigo-700 transition-colors"
              >
                Enroll
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
