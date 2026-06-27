"use client";

import { useCallback, useEffect, useState } from "react";
import { Link2, Plus, Loader2, X, Copy, CheckCircle2, ToggleLeft, ToggleRight } from "lucide-react";
import { toast } from "sonner";
import { api } from "@/lib/api-client";

interface FormField {
  name: string;
  label: string;
  type: string;
  required?: boolean;
  options?: string[];
}

interface LeadForm {
  id: string;
  slug: string;
  title: string;
  is_active: boolean;
  fields: FormField[];
  redirect_url: string | null;
  notify_email: string | null;
}

interface Submission {
  id: string;
  submitter_name: string | null;
  submitter_email: string | null;
  data: Record<string, string>;
  converted_to_deal_id: string | null;
  created_at: string;
}

export default function CrmLeadsPage() {
  const [forms, setForms] = useState<LeadForm[]>([]);
  const [loading, setLoading] = useState(true);
  const [selected, setSelected] = useState<LeadForm | null>(null);
  const [submissions, setSubmissions] = useState<Submission[]>([]);
  const [showNew, setShowNew] = useState(false);
  const [newTitle, setNewTitle] = useState("");
  const [saving, setSaving] = useState(false);
  const [copied, setCopied] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const data = await api.get<LeadForm[]>("/api/crm/lead-forms");
      setForms(data);
    } catch {
      toast.error("Failed to load forms");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  async function selectForm(form: LeadForm) {
    setSelected(form);
    try {
      const subs = await api.get<Submission[]>(`/api/crm/lead-forms/${form.id}/submissions`);
      setSubmissions(subs);
    } catch {
      setSubmissions([]);
    }
  }

  async function handleCreate() {
    if (!newTitle.trim()) return;
    setSaving(true);
    try {
      await api.post("/api/crm/lead-forms", {
        title: newTitle,
        fields: [
          { name: "name", label: "Name", type: "text", required: true },
          { name: "email", label: "Email", type: "email", required: true },
        ],
      });
      setShowNew(false); setNewTitle("");
      toast.success("Form created");
      load();
    } catch {
      toast.error("Failed to create form");
    } finally {
      setSaving(false);
    }
  }

  async function toggleActive(form: LeadForm) {
    try {
      await api.patch(`/api/crm/lead-forms/${form.id}`, { is_active: !form.is_active });
      setForms((prev) => prev.map((f) => f.id === form.id ? { ...f, is_active: !form.is_active } : f));
    } catch {
      toast.error("Failed to update form");
    }
  }

  async function handleConvert(sub: Submission) {
    if (!selected) return;
    try {
      const r = await api.post<{ deal_id: string }>(
        `/api/crm/lead-forms/${selected.id}/submissions/${sub.id}/convert`,
        {}
      );
      toast.success(`Deal created: ${r.deal_id.slice(0, 8)}`);
      const subs = await api.get<Submission[]>(`/api/crm/lead-forms/${selected.id}/submissions`);
      setSubmissions(subs);
    } catch {
      toast.error("Failed to convert submission");
    }
  }

  function copyEmbedCode(slug: string) {
    const code = `<iframe src="${window.location.origin}/forms/${slug}" width="100%" height="600" frameborder="0"></iframe>`;
    navigator.clipboard.writeText(code).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    });
  }

  const publicBase = typeof window !== "undefined" ? window.location.origin : "";

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Link2 className="h-5 w-5 vf-text-m" />
          <h1 className="text-[15px] font-semibold vf-text-1">Lead Forms</h1>
        </div>
        <button
          onClick={() => setShowNew(true)}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-indigo-600 text-white text-xs font-medium hover:bg-indigo-700 transition-colors"
        >
          <Plus className="h-3.5 w-3.5" /> New Form
        </button>
      </div>

      <div className="grid lg:grid-cols-[280px_1fr] gap-5">
        {/* Form list */}
        <div className="space-y-2">
          {showNew && (
            <div className="vf-card p-3 space-y-2">
              <input
                autoFocus
                type="text"
                placeholder="Form title"
                value={newTitle}
                onChange={(e) => setNewTitle(e.target.value)}
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
          ) : forms.length === 0 ? (
            <p className="text-sm vf-text-m text-center py-8">No forms yet.</p>
          ) : forms.map((form) => (
            <div
              key={form.id}
              onClick={() => selectForm(form)}
              className={`vf-card p-3 cursor-pointer hover:bg-[var(--vf-hover)] transition-colors ${selected?.id === form.id ? "border-indigo-500/50" : ""}`}
            >
              <div className="flex items-start justify-between gap-2">
                <div className="min-w-0">
                  <p className="text-[13px] font-medium vf-text-1 truncate">{form.title}</p>
                  <p className="text-[11px] font-mono vf-text-m mt-0.5">/forms/{form.slug}</p>
                </div>
                <button onClick={(e) => { e.stopPropagation(); toggleActive(form); }} className="shrink-0 vf-text-m">
                  {form.is_active
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
              <h2 className="text-[14px] font-semibold vf-text-1">{selected.title}</h2>
              <button onClick={() => setSelected(null)}><X className="h-4 w-4 vf-text-m" /></button>
            </div>

            {/* Embed snippet */}
            <div>
              <h3 className="text-[12px] font-semibold vf-text-m uppercase tracking-wider mb-2">Public URL & Embed</h3>
              <div className="flex items-center gap-2">
                <code className="flex-1 text-[11px] font-mono bg-[var(--vf-bg-elevated)] px-3 py-2 rounded-lg truncate vf-text-m">
                  {publicBase}/forms/{selected.slug}
                </code>
                <button
                  onClick={() => copyEmbedCode(selected.slug)}
                  className="shrink-0 p-2 rounded-lg vf-btn-ghost"
                  title="Copy embed code"
                >
                  {copied ? <CheckCircle2 className="h-4 w-4 text-emerald-500" /> : <Copy className="h-4 w-4 vf-text-m" />}
                </button>
              </div>
            </div>

            {/* Fields */}
            <div>
              <h3 className="text-[12px] font-semibold vf-text-m uppercase tracking-wider mb-2">
                Fields ({selected.fields.length})
              </h3>
              <div className="space-y-1">
                {selected.fields.map((f) => (
                  <div key={f.name} className="flex items-center gap-2 text-xs px-3 py-2 rounded-lg bg-[var(--vf-bg-elevated)]">
                    <span className="font-mono vf-text-m">{f.name}</span>
                    <span className="vf-text-m">·</span>
                    <span className="px-1.5 py-0.5 rounded bg-indigo-500/10 text-indigo-500 text-[10px]">{f.type}</span>
                    {f.required && <span className="text-[10px] text-red-500">required</span>}
                    <span className="ml-auto vf-text-1">{f.label}</span>
                  </div>
                ))}
              </div>
            </div>

            {/* Submissions */}
            <div>
              <h3 className="text-[12px] font-semibold vf-text-m uppercase tracking-wider mb-2">
                Submissions ({submissions.length})
              </h3>
              {submissions.length === 0 ? (
                <p className="text-xs vf-text-m">No submissions yet.</p>
              ) : (
                <div className="space-y-2">
                  {submissions.map((sub) => (
                    <div key={sub.id} className="border border-[var(--vf-border)] rounded-xl p-3">
                      <div className="flex items-start justify-between gap-2">
                        <div>
                          <p className="text-[13px] font-medium vf-text-1">{sub.submitter_name ?? "—"}</p>
                          <p className="text-[11px] vf-text-m">{sub.submitter_email}</p>
                          <p className="text-[10px] vf-text-m mt-0.5">{new Date(sub.created_at).toLocaleDateString()}</p>
                        </div>
                        {!sub.converted_to_deal_id ? (
                          <button
                            onClick={() => handleConvert(sub)}
                            className="shrink-0 px-2 py-1 rounded-lg bg-indigo-600 text-white text-[10px] font-medium hover:bg-indigo-700 transition-colors"
                          >
                            → Deal
                          </button>
                        ) : (
                          <span className="text-[10px] text-emerald-500 font-medium">Converted</span>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
