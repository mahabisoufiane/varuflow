"use client";

import { api } from "@/lib/api-client";
import { useEffect, useState } from "react";
import { GitBranch, Pencil, Plus, Save, Trash2, X } from "lucide-react";
import { toast } from "sonner";
import { useRouter } from "@/i18n/navigation";
import { useLocale } from "next-intl";

/* ── Types ─────────────────────────────────────────────────────────────────── */
interface WorkflowRule {
  id: string;
  name: string;
  description: string | null;
  is_active: boolean;
  trigger_type: string;
  trigger_conditions: Record<string, unknown>;
  actions: unknown[];
  run_count: number;
  last_run_at: string | null;
  created_at: string;
}

const TRIGGER_TYPES = [
  { value: "invoice_overdue_days", label: "Invoice overdue by N days" },
  { value: "new_invoice",          label: "New invoice created"       },
  { value: "payment_received",     label: "Payment received"          },
];

/* ── Empty form state ───────────────────────────────────────────────────────── */
const EMPTY = {
  name: "",
  description: "",
  trigger_type: "invoice_overdue_days",
  trigger_conditions: '{"days": 7}',
  actions: '[{"type": "notify", "message": "Invoice overdue"}]',
  is_active: true,
};

/* ── Page ───────────────────────────────────────────────────────────────────── */
export default function WorkflowsPage() {
  const locale = useLocale();
  const router = useRouter();
  const [rules, setRules] = useState<WorkflowRule[]>([]);
  const [form, setForm] = useState(EMPTY);
  const [editId, setEditId] = useState<string | null>(null);
  const [panelOpen, setPanelOpen] = useState(false);
  const [saving, setSaving] = useState(false);

  async function loadRules() {
    try {
      const d = await api.get("/api/ai/workflows");
      setRules((d as { rules: WorkflowRule[] }).rules ?? []);
    } catch (e: unknown) {
      const err = e as { status?: number };
      if (err.status === 401) router.push(`/${locale}/auth/login`);
      else toast.error("Failed to load workflows.");
    }
  }

  useEffect(() => { loadRules(); }, []); // eslint-disable-line react-hooks/exhaustive-deps

  function openNew() {
    setForm(EMPTY);
    setEditId(null);
    setPanelOpen(true);
  }

  function openEdit(r: WorkflowRule) {
    setForm({
      name: r.name,
      description: r.description ?? "",
      trigger_type: r.trigger_type,
      trigger_conditions: JSON.stringify(r.trigger_conditions, null, 2),
      actions: JSON.stringify(r.actions, null, 2),
      is_active: r.is_active,
    });
    setEditId(r.id);
    setPanelOpen(true);
  }

  async function save() {
    let conditions: unknown;
    let actions: unknown;
    try {
      conditions = JSON.parse(form.trigger_conditions);
      actions = JSON.parse(form.actions);
    } catch {
      toast.error("Conditions or actions contain invalid JSON.");
      return;
    }
    setSaving(true);
    try {
      const payload = {
        name: form.name,
        description: form.description || null,
        trigger_type: form.trigger_type,
        trigger_conditions: conditions,
        actions,
        is_active: form.is_active,
      };
      if (editId) {
        await api.patch(`/api/ai/workflows/${editId}`, payload);
        toast.success("Workflow updated.");
      } else {
        await api.post("/api/ai/workflows", payload);
        toast.success("Workflow created.");
      }
      setPanelOpen(false);
      loadRules();
    } catch {
      toast.error("Failed to save workflow.");
    } finally {
      setSaving(false);
    }
  }

  async function deleteRule(id: string) {
    if (!confirm("Delete this workflow?")) return;
    try {
      await api.delete(`/api/ai/workflows/${id}`);
      toast.success("Deleted.");
      loadRules();
    } catch {
      toast.error("Failed to delete workflow.");
    }
  }

  async function runNow(id: string) {
    try {
      const result = await api.post(`/api/ai/workflows/${id}/run`, {});
      const r = result as { triggered: number; message: string };
      toast.success(`Run complete — ${r.triggered ?? 0} entity(s) matched.`);
      loadRules();
    } catch {
      toast.error("Failed to run workflow.");
    }
  }

  return (
    <div className="max-w-5xl mx-auto p-6 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold flex items-center gap-2">
            <GitBranch className="w-6 h-6 text-violet-500" />
            Automated Workflows
          </h1>
          <p className="text-sm text-gray-500 mt-1">Configure trigger rules that execute actions automatically</p>
        </div>
        <button onClick={openNew} className="flex items-center gap-2 px-4 py-2 bg-violet-600 text-white text-sm rounded-lg hover:bg-violet-700">
          <Plus className="w-4 h-4" /> New Workflow
        </button>
      </div>

      {/* Rules list */}
      <div className="space-y-3">
        {rules.length === 0 && (
          <p className="text-sm text-gray-400 text-center py-8">No workflows yet. Create one to get started.</p>
        )}
        {rules.map((r) => (
          <div key={r.id} className="p-4 border rounded-lg flex items-center gap-4">
            <div className={`w-2 h-2 rounded-full flex-shrink-0 ${r.is_active ? "bg-green-500" : "bg-gray-300"}`} />
            <div className="flex-1 min-w-0">
              <p className="font-medium truncate">{r.name}</p>
              <p className="text-xs text-gray-400 mt-0.5">
                {TRIGGER_TYPES.find(t => t.value === r.trigger_type)?.label ?? r.trigger_type}
                {" · "}Run {r.run_count}× {r.last_run_at ? `· last ${new Date(r.last_run_at).toLocaleDateString()}` : ""}
              </p>
            </div>
            <div className="flex gap-2">
              <button onClick={() => runNow(r.id)} className="text-xs px-2 py-1 border rounded hover:bg-gray-50">
                Run now
              </button>
              <button onClick={() => openEdit(r)} className="text-xs px-2 py-1 border rounded hover:bg-gray-50">
                <Pencil className="w-3 h-3" />
              </button>
              <button onClick={() => deleteRule(r.id)} className="text-xs px-2 py-1 border rounded text-red-600 hover:bg-red-50">
                <Trash2 className="w-3 h-3" />
              </button>
            </div>
          </div>
        ))}
      </div>

      {/* Slide-over panel */}
      {panelOpen && (
        <div className="fixed inset-0 z-40 flex justify-end">
          <div className="absolute inset-0 bg-black/30" onClick={() => setPanelOpen(false)} />
          <div className="relative bg-white w-full max-w-md h-full overflow-y-auto shadow-xl p-6 space-y-4 z-50">
            <div className="flex items-center justify-between">
              <h2 className="text-lg font-bold">{editId ? "Edit Workflow" : "New Workflow"}</h2>
              <button onClick={() => setPanelOpen(false)}><X className="w-5 h-5" /></button>
            </div>

            <div className="space-y-3">
              <div>
                <label className="text-sm font-medium">Name *</label>
                <input
                  value={form.name}
                  onChange={e => setForm(f => ({ ...f, name: e.target.value }))}
                  className="mt-1 w-full border rounded px-3 py-2 text-sm"
                  placeholder="7-day overdue reminder"
                />
              </div>
              <div>
                <label className="text-sm font-medium">Description</label>
                <input
                  value={form.description}
                  onChange={e => setForm(f => ({ ...f, description: e.target.value }))}
                  className="mt-1 w-full border rounded px-3 py-2 text-sm"
                />
              </div>
              <div>
                <label className="text-sm font-medium">Trigger</label>
                <select
                  value={form.trigger_type}
                  onChange={e => setForm(f => ({ ...f, trigger_type: e.target.value }))}
                  className="mt-1 w-full border rounded px-3 py-2 text-sm"
                >
                  {TRIGGER_TYPES.map(t => (
                    <option key={t.value} value={t.value}>{t.label}</option>
                  ))}
                </select>
              </div>
              <div>
                <label className="text-sm font-medium">Conditions (JSON)</label>
                <textarea
                  value={form.trigger_conditions}
                  onChange={e => setForm(f => ({ ...f, trigger_conditions: e.target.value }))}
                  rows={4}
                  className="mt-1 w-full border rounded px-3 py-2 text-sm font-mono"
                />
              </div>
              <div>
                <label className="text-sm font-medium">Actions (JSON array)</label>
                <textarea
                  value={form.actions}
                  onChange={e => setForm(f => ({ ...f, actions: e.target.value }))}
                  rows={5}
                  className="mt-1 w-full border rounded px-3 py-2 text-sm font-mono"
                />
              </div>
              <label className="flex items-center gap-2 text-sm">
                <input
                  type="checkbox"
                  checked={form.is_active}
                  onChange={e => setForm(f => ({ ...f, is_active: e.target.checked }))}
                />
                Active
              </label>
            </div>

            <button
              onClick={save}
              disabled={saving || !form.name}
              className="w-full flex items-center justify-center gap-2 py-2 bg-violet-600 text-white rounded-lg hover:bg-violet-700 disabled:opacity-50"
            >
              <Save className="w-4 h-4" />
              {saving ? "Saving…" : "Save Workflow"}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
