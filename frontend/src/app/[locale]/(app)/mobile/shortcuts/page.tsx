"use client";

import { api } from "@/lib/api-client";
import { useEffect, useState } from "react";
import { toast } from "sonner";
import { useRouter, useParams } from "next/navigation";
import { cn } from "@/lib/utils";
import {
  Mic, Plus, Trash2, X, Play, Edit2, Clock,
  CheckCircle2, Lightbulb,
} from "lucide-react";

interface VoiceShortcut {
  id: string;
  platform: "siri" | "google_assistant" | "bixby";
  phrase: string;
  action_type: string;
  response_template: string;
  last_triggered_at?: string;
  trigger_count: number;
  is_active: boolean;
}

const ACTION_TYPES = [
  { value: "create_invoice", label: "Create invoice" },
  { value: "check_inventory", label: "Check inventory" },
  { value: "view_revenue", label: "View today's revenue" },
  { value: "list_bookings", label: "List today's bookings" },
  { value: "check_low_stock", label: "Check low stock" },
  { value: "send_reminder", label: "Send payment reminder" },
  { value: "create_customer", label: "Create customer" },
  { value: "custom", label: "Custom action" },
];

const PLATFORM_META: Record<VoiceShortcut["platform"], { label: string; color: string; bg: string }> = {
  siri: { label: "Siri", color: "text-indigo-400", bg: "bg-indigo-500/10" },
  google_assistant: { label: "Google Assistant", color: "text-blue-400", bg: "bg-blue-500/10" },
  bixby: { label: "Bixby", color: "text-violet-400", bg: "bg-violet-500/10" },
};

const SUGGESTED_SHORTCUTS = [
  { phrase: "Hey Siri, show my revenue today", platform: "Siri", action: "View today's revenue" },
  { phrase: "OK Google, check Varuflow low stock", platform: "Google Assistant", action: "Check low stock" },
  { phrase: "Hey Siri, create Varuflow invoice", platform: "Siri", action: "Create invoice" },
  { phrase: "OK Google, show today's bookings", platform: "Google Assistant", action: "List today's bookings" },
  { phrase: "Hey Siri, send payment reminder", platform: "Siri", action: "Send payment reminder" },
  { phrase: "Bixby, check Varuflow inventory", platform: "Bixby", action: "Check inventory" },
];

const EMPTY_FORM = {
  platform: "siri" as VoiceShortcut["platform"],
  phrase: "",
  action_type: "view_revenue",
  response_template: "",
};

export default function ShortcutsPage() {
  const router = useRouter();
  const params = useParams<{ locale: string }>();
  const locale = params.locale;

  const [shortcuts, setShortcuts] = useState<VoiceShortcut[]>([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState(EMPTY_FORM);
  const [submitting, setSubmitting] = useState(false);
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [testingId, setTestingId] = useState<string | null>(null);
  const [editingId, setEditingId] = useState<string | null>(null);

  useEffect(() => {
    api.get<VoiceShortcut[]>("/api/voice-shortcuts")
      .then(setShortcuts)
      .catch((e: { status?: number; message?: string }) => {
        if (e.status === 401) { router.push(`/${locale}/auth/login`); return; }
        toast.error(e.message ?? "Failed to load shortcuts");
      })
      .finally(() => setLoading(false));
  }, [locale, router]);

  function resetForm() {
    setForm(EMPTY_FORM);
    setShowForm(false);
    setEditingId(null);
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!form.phrase.trim()) { toast.error("Phrase is required"); return; }
    setSubmitting(true);
    try {
      if (editingId) {
        const updated = await api.patch<VoiceShortcut>(`/api/voice-shortcuts/${editingId}`, form);
        setShortcuts((prev) => prev.map((s) => (s.id === editingId ? updated : s)));
        toast.success("Shortcut updated");
      } else {
        const created = await api.post<VoiceShortcut>("/api/voice-shortcuts", form);
        setShortcuts((prev) => [...prev, created]);
        toast.success("Shortcut added");
      }
      resetForm();
    } catch (e: unknown) {
      const err = e as { status?: number; message?: string };
      if (err.status === 401) { router.push(`/${locale}/auth/login`); return; }
      toast.error(err.message ?? "Failed to save shortcut");
    } finally {
      setSubmitting(false);
    }
  }

  async function handleDelete(id: string) {
    setDeletingId(id);
    try {
      await api.delete(`/api/voice-shortcuts/${id}`);
      setShortcuts((prev) => prev.filter((s) => s.id !== id));
      toast.success("Shortcut removed");
    } catch (e: unknown) {
      const err = e as { status?: number; message?: string };
      if (err.status === 401) { router.push(`/${locale}/auth/login`); return; }
      toast.error(err.message ?? "Failed to delete shortcut");
    } finally {
      setDeletingId(null);
    }
  }

  async function handleTest(id: string) {
    setTestingId(id);
    try {
      const result = await api.post<{ spoken_response: string }>(`/api/voice-shortcuts/${id}/trigger`, {});
      toast.success(result.spoken_response ?? "Shortcut triggered successfully");
    } catch (e: unknown) {
      const err = e as { status?: number; message?: string };
      if (err.status === 401) { router.push(`/${locale}/auth/login`); return; }
      toast.error(err.message ?? "Failed to test shortcut");
    } finally {
      setTestingId(null);
    }
  }

  function handleEdit(s: VoiceShortcut) {
    setForm({
      platform: s.platform,
      phrase: s.phrase,
      action_type: s.action_type,
      response_template: s.response_template,
    });
    setEditingId(s.id);
    setShowForm(true);
  }

  return (
    <div className="space-y-6">

      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold tracking-tight vf-text-1">Siri Shortcuts &amp; Google Assistant</h1>
          <p className="text-xs vf-text-m mt-0.5">Configure voice commands across Siri, Google Assistant, and Bixby</p>
        </div>
        <button onClick={() => { resetForm(); setShowForm(true); }} className="vf-btn text-xs">
          <Plus className="h-3.5 w-3.5" />Add shortcut
        </button>
      </div>

      {/* Add / Edit Form */}
      {showForm && (
        <div className="vf-section p-5" style={{ borderRadius: 14 }}>
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-[13px] font-semibold vf-text-1">
              {editingId ? "Edit shortcut" : "Add shortcut"}
            </h2>
            <button onClick={resetForm} className="vf-text-m hover:text-red-400 transition-colors">
              <X className="h-4 w-4" />
            </button>
          </div>
          <form onSubmit={handleSubmit} className="space-y-3">
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <div>
                <label className="text-[11px] font-semibold uppercase tracking-wide vf-text-m mb-1 block">Platform</label>
                <select
                  value={form.platform}
                  onChange={(e) => setForm({ ...form, platform: e.target.value as VoiceShortcut["platform"] })}
                  className="vf-input text-xs w-full"
                  style={{ height: 36 }}
                  disabled={submitting}
                >
                  <option value="siri">Siri</option>
                  <option value="google_assistant">Google Assistant</option>
                  <option value="bixby">Bixby</option>
                </select>
              </div>
              <div>
                <label className="text-[11px] font-semibold uppercase tracking-wide vf-text-m mb-1 block">Action type</label>
                <select
                  value={form.action_type}
                  onChange={(e) => setForm({ ...form, action_type: e.target.value })}
                  className="vf-input text-xs w-full"
                  style={{ height: 36 }}
                  disabled={submitting}
                >
                  {ACTION_TYPES.map((a) => (
                    <option key={a.value} value={a.value}>{a.label}</option>
                  ))}
                </select>
              </div>
            </div>
            <div>
              <label className="text-[11px] font-semibold uppercase tracking-wide vf-text-m mb-1 block">Phrase</label>
              <input
                value={form.phrase}
                onChange={(e) => setForm({ ...form, phrase: e.target.value })}
                placeholder={`e.g. "Hey Siri, check my Varuflow revenue"`}
                className="vf-input text-xs w-full"
                style={{ height: 36 }}
                disabled={submitting}
              />
            </div>
            <div>
              <label className="text-[11px] font-semibold uppercase tracking-wide vf-text-m mb-1 block">Response template</label>
              <input
                value={form.response_template}
                onChange={(e) => setForm({ ...form, response_template: e.target.value })}
                placeholder={`e.g. "Today's revenue is {amount}"`}
                className="vf-input text-xs w-full"
                style={{ height: 36 }}
                disabled={submitting}
              />
              <p className="text-[11px] vf-text-m mt-1">Use {"{"}<span>variables</span>{"}"} in your template</p>
            </div>
            <div className="flex gap-2 pt-1">
              <button type="submit" disabled={submitting} className="vf-btn text-xs">
                <CheckCircle2 className="h-3.5 w-3.5" />
                {submitting ? "Saving…" : editingId ? "Update shortcut" : "Add shortcut"}
              </button>
              <button type="button" onClick={resetForm} className="vf-btn-secondary text-xs">Cancel</button>
            </div>
          </form>
        </div>
      )}

      {/* Shortcuts list */}
      <div className="vf-section">
        <div className="vf-section-header">
          <h2 className="text-[13px] font-semibold vf-text-1">Your shortcuts</h2>
          <span className="text-[11px] vf-text-m">{shortcuts.length} configured</span>
        </div>

        {loading ? (
          Array.from({ length: 3 }).map((_, i) => (
            <div key={i} className="flex gap-4 px-5 py-4" style={{ borderBottom: "1px solid var(--vf-divider)" }}>
              <div className="h-4 w-48 skeleton rounded" />
              <div className="h-4 w-24 skeleton rounded ml-auto" />
            </div>
          ))
        ) : shortcuts.length === 0 ? (
          <div className="py-16 text-center">
            <div className="mx-auto mb-3 flex h-12 w-12 items-center justify-center rounded-2xl"
              style={{ background: "var(--vf-bg-elevated)" }}>
              <Mic className="h-6 w-6 vf-text-m" />
            </div>
            <p className="text-sm font-medium vf-text-2">No shortcuts configured</p>
            <p className="text-xs vf-text-m mt-1">Add a voice shortcut to control Varuflow hands-free</p>
          </div>
        ) : (
          shortcuts.map((s, i) => {
            const meta = PLATFORM_META[s.platform];
            const actionLabel = ACTION_TYPES.find((a) => a.value === s.action_type)?.label ?? s.action_type;
            return (
              <div key={s.id} className="px-5 py-4"
                style={{ borderBottom: i < shortcuts.length - 1 ? "1px solid var(--vf-divider)" : "none" }}>
                <div className="flex items-start gap-3">
                  <div className={cn("flex h-9 w-9 shrink-0 items-center justify-center rounded-xl mt-0.5", meta.bg)}>
                    <Mic className={cn("h-4 w-4", meta.color)} />
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 flex-wrap">
                      <p className="text-[13px] font-semibold vf-text-1 italic">&ldquo;{s.phrase}&rdquo;</p>
                      <span className={cn("rounded-full px-2 py-0.5 text-[10px] font-semibold", meta.bg, meta.color)}>
                        {meta.label}
                      </span>
                    </div>
                    <p className="text-xs vf-text-m mt-0.5">{actionLabel}</p>
                    {s.response_template && (
                      <p className="text-[11px] vf-text-m mt-0.5 italic truncate">
                        Response: &ldquo;{s.response_template}&rdquo;
                      </p>
                    )}
                    <div className="flex items-center gap-3 mt-1.5">
                      {s.last_triggered_at && (
                        <span className="flex items-center gap-1 text-[11px] vf-text-m">
                          <Clock className="h-3 w-3" />
                          Last used {new Date(s.last_triggered_at).toLocaleDateString()}
                        </span>
                      )}
                      {s.trigger_count > 0 && (
                        <span className="text-[11px] vf-text-m">{s.trigger_count} uses</span>
                      )}
                    </div>
                  </div>
                  <div className="flex items-center gap-1 shrink-0">
                    <button
                      disabled={testingId === s.id}
                      onClick={() => handleTest(s.id)}
                      className="flex h-8 w-8 items-center justify-center rounded-lg transition-colors hover:bg-indigo-500/10 hover:text-indigo-400 vf-text-m disabled:opacity-50"
                      title="Test shortcut"
                    >
                      <Play className={cn("h-3.5 w-3.5", testingId === s.id && "animate-pulse")} />
                    </button>
                    <button
                      onClick={() => handleEdit(s)}
                      className="flex h-8 w-8 items-center justify-center rounded-lg transition-colors hover:bg-indigo-500/10 hover:text-indigo-400 vf-text-m"
                      title="Edit shortcut"
                    >
                      <Edit2 className="h-3.5 w-3.5" />
                    </button>
                    <button
                      disabled={deletingId === s.id}
                      onClick={() => handleDelete(s.id)}
                      className="flex h-8 w-8 items-center justify-center rounded-lg transition-colors hover:bg-red-500/10 hover:text-red-400 vf-text-m disabled:opacity-50"
                      title="Delete shortcut"
                    >
                      <Trash2 className="h-3.5 w-3.5" />
                    </button>
                  </div>
                </div>
              </div>
            );
          })
        )}
      </div>

      {/* Suggested shortcuts */}
      <div className="vf-section p-5" style={{ borderRadius: 14 }}>
        <div className="flex items-center gap-2 mb-4">
          <Lightbulb className="h-4 w-4 text-amber-400" />
          <h2 className="text-[13px] font-semibold vf-text-1">Suggested shortcuts</h2>
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
          {SUGGESTED_SHORTCUTS.map((s, i) => (
            <div key={i} className="rounded-xl p-3"
              style={{ background: "var(--vf-bg-elevated)", border: "1px solid var(--vf-border)" }}>
              <p className="text-[13px] font-semibold vf-text-1 italic mb-1">&ldquo;{s.phrase}&rdquo;</p>
              <div className="flex items-center justify-between">
                <p className="text-xs vf-text-m">{s.action}</p>
                <span className="rounded-full bg-amber-500/10 px-2 py-0.5 text-[10px] font-semibold text-amber-400">
                  {s.platform}
                </span>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
