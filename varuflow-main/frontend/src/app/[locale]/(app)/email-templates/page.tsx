"use client";
import { useEffect, useState } from "react";
import { api } from "@/lib/api-client";
import styles from "./page.module.scss";
import { toast } from "sonner";
import { Mail, Plus, Trash2, Copy, Send, ChevronRight, Tag, Eye, History, ToggleLeft, ToggleRight } from "lucide-react";
import { sanitizeHtml } from "@/lib/sanitize-html";

interface Template {
  id: string;
  name: string;
  subject: string;
  body_html: string;
  category: string;
  variables: Record<string, string> | null;
  is_system: boolean;
  is_active: boolean;
  version: number;
  parent_id: string | null;
  created_at: string;
  updated_at: string;
}

interface SendRecord {
  id: string;
  template_id: string | null;
  to_email: string;
  subject: string;
  sent_at: string;
  opened_at: string | null;
  clicked_at: string | null;
}

const CATEGORIES = ["general", "invoice", "reminder", "welcome", "marketing", "transactional"];

const DEFAULT_VARS: Record<string, string> = {
  customer_name: "Placeholder",
  invoice_number: "INV-001",
  amount: "0.00",
  currency: "SEK",
  due_date: "2026-01-01",
  company_name: "Your Company",
  portal_link: "https://...",
};

export default function EmailTemplatesPage() {
  const [templates, setTemplates] = useState<Template[]>([]);
  const [sends, setSends] = useState<SendRecord[]>([]);
  const [selected, setSelected] = useState<Template | null>(null);
  const [tab, setTab] = useState<"templates" | "history">("templates");
  const [detailTab, setDetailTab] = useState<"preview" | "edit" | "send">("preview");
  const [filterCat, setFilterCat] = useState("");
  const [loading, setLoading] = useState(true);
  const [showCreate, setShowCreate] = useState(false);
  const [sendModal, setSendModal] = useState(false);
  const [previewVars, setPreviewVars] = useState<Record<string, string>>({});

  // Create form
  const [form, setForm] = useState({ name: "", subject: "", body_html: "", category: "general" });
  // Edit form
  const [editForm, setEditForm] = useState({ name: "", subject: "", body_html: "", category: "general" });
  const [editing, setEditing] = useState(false);
  // Send form
  const [sendForm, setSendForm] = useState({ to_email: "", subject: "" });

  useEffect(() => { load(); }, []);
  useEffect(() => { if (tab === "history") loadSends(); }, [tab]);
  useEffect(() => {
    if (selected) {
      setEditForm({ name: selected.name, subject: selected.subject, body_html: selected.body_html, category: selected.category });
      // Extract variables from body_html
      const matches = selected.body_html.match(/\{\{(\w+)\}\}/g) ?? [];
      const vars: Record<string, string> = {};
      matches.forEach(m => {
        const key = m.slice(2, -2);
        vars[key] = DEFAULT_VARS[key] ?? key;
      });
      setPreviewVars(vars);
    }
  }, [selected]);

  async function load() {
    setLoading(true);
    try {
      const data = await api.get("/api/email-templates" + (filterCat ? `?category=${filterCat}` : ""));
      setTemplates(Array.isArray(data) ? data : []);
    } catch { toast.error("Failed to load templates"); }
    finally { setLoading(false); }
  }

  async function loadSends() {
    try {
      const data = await api.get("/api/email-templates/sends?limit=100");
      setSends(Array.isArray(data) ? data : []);
    } catch { toast.error("Failed to load send history"); }
  }

  async function create() {
    if (!form.name || !form.subject || !form.body_html) { toast.error("Name, subject, and body are required"); return; }
    try {
      const t = await api.post("/api/email-templates", form);
      setTemplates(prev => [t, ...prev]);
      setShowCreate(false);
      setForm({ name: "", subject: "", body_html: "", category: "general" });
      toast.success("Template created");
    } catch { toast.error("Failed to create template"); }
  }

  async function saveEdit() {
    if (!selected) return;
    try {
      const updated = await api.patch(`/api/email-templates/${selected.id}`, editForm);
      setTemplates(prev => prev.map(t => t.id === updated.id ? updated : t));
      setSelected(updated);
      setEditing(false);
      toast.success("Template saved");
    } catch { toast.error("Failed to save"); }
  }

  async function revise() {
    if (!selected) return;
    try {
      const newVer = await api.post(`/api/email-templates/${selected.id}/revise`, {});
      setTemplates(prev => prev.map(t => t.id === selected.id ? { ...t, is_active: false } : t).concat([newVer]));
      setSelected(newVer);
      toast.success(`Version ${newVer.version} created`);
    } catch { toast.error("Failed to create revision"); }
  }

  async function toggleActive() {
    if (!selected || selected.is_system) return;
    try {
      const updated = await api.patch(`/api/email-templates/${selected.id}`, { is_active: !selected.is_active });
      setTemplates(prev => prev.map(t => t.id === updated.id ? updated : t));
      setSelected(updated);
    } catch { toast.error("Failed to update"); }
  }

  async function del() {
    if (!selected || selected.is_system) return;
    if (!confirm(`Delete template "${selected.name}"?`)) return;
    try {
      await api.delete(`/api/email-templates/${selected.id}`);
      setTemplates(prev => prev.filter(t => t.id !== selected.id));
      setSelected(null);
      toast.success("Deleted");
    } catch { toast.error("Failed to delete"); }
  }

  async function sendNow() {
    if (!selected) return;
    if (!sendForm.to_email) { toast.error("Recipient email required"); return; }
    try {
      await api.post(`/api/email-templates/${selected.id}/send`, {
        to_email: sendForm.to_email,
        subject: sendForm.subject || undefined,
        variables: previewVars,
      });
      setSendModal(false);
      setSendForm({ to_email: "", subject: "" });
      toast.success("Sent successfully");
    } catch { toast.error("Failed to send"); }
  }

  function renderPreview(html: string) {
    let rendered = html;
    Object.entries(previewVars).forEach(([k, v]) => {
      rendered = rendered.replace(new RegExp(`\\{\\{${k}\\}\\}`, "g"), v);
    });
    return rendered;
  }

  const grouped = CATEGORIES.reduce<Record<string, Template[]>>((acc, cat) => {
    const cat_templates = templates.filter(t => t.category === cat && (!filterCat || filterCat === cat));
    if (cat_templates.length) acc[cat] = cat_templates;
    return acc;
  }, {});

  return (
    <div className="flex h-[calc(100vh-4rem)] overflow-hidden">
      {/* ── Left sidebar ──────────────────────────────────────────────── */}
      <aside className="w-72 border-r flex flex-col shrink-0 bg-white">
        <div className="p-3 border-b flex items-center justify-between">
          <h2 className="font-semibold text-sm flex items-center gap-2">
            <Mail size={16} /> Email Templates
          </h2>
          <button onClick={() => setShowCreate(true)} className="p-1 rounded hover:bg-gray-100" title="New template">
            <Plus size={15} />
          </button>
        </div>

        {/* Tab toggle */}
        <div className="flex border-b text-xs">
          {(["templates", "history"] as const).map(t => (
            <button key={t} onClick={() => setTab(t)}
              className={`flex-1 py-2 font-medium capitalize ${tab === t ? "border-b-2 border-[var(--vf-brand-primary)] text-[var(--vf-text-primary)]" : "text-gray-500"}`}>
              {t}
            </button>
          ))}
        </div>

        {tab === "templates" && (
          <>
            <select value={filterCat} onChange={e => { setFilterCat(e.target.value); load(); }}
              className="mx-3 mt-2 mb-1 text-xs border rounded px-2 py-1">
              <option value="">All categories</option>
              {CATEGORIES.map(c => <option key={c} value={c}>{c}</option>)}
            </select>

            <div className="flex-1 overflow-y-auto">
              {loading ? (
                <p className="p-3 text-xs text-gray-400">Loading…</p>
              ) : templates.length === 0 ? (
                <div className="p-4 text-center text-xs text-gray-400">
                  <Mail size={24} className="mx-auto mb-2 opacity-30" />
                  No templates yet. Click + to create one.
                </div>
              ) : (
                Object.entries(grouped).map(([cat, items]) => (
                  <div key={cat}>
                    <p className="px-3 py-1.5 text-[10px] font-semibold text-gray-400 uppercase tracking-wide bg-gray-50">{cat}</p>
                    {items.map(t => (
                      <button key={t.id} onClick={() => { setSelected(t); setDetailTab("preview"); setEditing(false); }}
                        className={`w-full text-left px-3 py-2 hover:bg-gray-50 border-b border-gray-50 ${selected?.id === t.id ? "bg-blue-50" : ""}`}>
                        <div className="flex items-center justify-between gap-1">
                          <span className={`text-xs font-medium truncate ${!t.is_active ? "line-through text-gray-400" : ""}`}>{t.name}</span>
                          <div className="flex items-center gap-1 shrink-0">
                            {t.version > 1 && <span className="text-[10px] text-gray-400">v{t.version}</span>}
                            {t.is_system && <span className="text-[10px] bg-purple-100 text-purple-700 px-1 rounded">sys</span>}
                          </div>
                        </div>
                        <p className="text-[10px] text-gray-400 truncate mt-0.5">{t.subject}</p>
                      </button>
                    ))}
                  </div>
                ))
              )}
            </div>
          </>
        )}

        {tab === "history" && (
          <div className="flex-1 overflow-y-auto">
            {sends.length === 0 ? (
              <p className="p-3 text-xs text-gray-400">No sends recorded yet.</p>
            ) : sends.map(s => (
              <div key={s.id} className="px-3 py-2 border-b text-xs">
                <p className="font-medium truncate">{s.subject}</p>
                <p className="text-gray-500">{s.to_email}</p>
                <div className="flex gap-3 mt-0.5 text-[10px] text-gray-400">
                  <span>{new Date(s.sent_at).toLocaleDateString()}</span>
                  {s.opened_at && <span className="text-green-600">Opened</span>}
                  {s.clicked_at && <span className="text-blue-600">Clicked</span>}
                </div>
              </div>
            ))}
          </div>
        )}
      </aside>

      {/* ── Detail panel ─────────────────────────────────────────────── */}
      {selected ? (
        <div className="flex-1 flex flex-col min-w-0 bg-white">
          {/* Header */}
          <div className="border-b px-4 py-3 flex items-center justify-between gap-2 shrink-0">
            <div className="min-w-0">
              <h3 className="font-semibold text-sm truncate">{selected.name}
                {selected.version > 1 && <span className="ml-1 text-xs text-gray-400">v{selected.version}</span>}
              </h3>
              <p className="text-xs text-gray-500 truncate">{selected.subject}</p>
            </div>
            <div className="flex items-center gap-1 shrink-0">
              <button onClick={toggleActive} title={selected.is_active ? "Deactivate" : "Activate"}
                className={styles.actionBtn} disabled={selected.is_system}>
                {selected.is_active ? <ToggleRight size={16} className="text-green-600" /> : <ToggleLeft size={16} />}
              </button>
              <button onClick={revise} title="Create new version" className={styles.actionBtn}>
                <History size={15} />
              </button>
              <button onClick={() => setSendModal(true)} title="Send" className={`${styles.actionBtn} text-blue-600`}>
                <Send size={15} />
              </button>
              {!selected.is_system && (
                <button onClick={del} title="Delete" className={`${styles.actionBtn} text-red-500`}>
                  <Trash2 size={15} />
                </button>
              )}
            </div>
          </div>

          {/* Sub-tabs */}
          <div className={`${styles.tabBar} text-xs px-4`}>
            {(["preview", "edit", "send"] as const).map(t => (
              <button key={t} onClick={() => { setDetailTab(t); if (t === "edit") setEditing(true); }}
                className={`${styles.tab} ${detailTab === t ? styles.tabActive : ""} capitalize`}>
                {t === "preview" ? <><Eye size={12} className="inline mr-1" />Preview</> :
                 t === "edit" ? "Edit" : <><Send size={12} className="inline mr-1" />Send</>}
              </button>
            ))}
          </div>

          <div className="flex-1 overflow-y-auto p-4">
            {/* Preview tab */}
            {detailTab === "preview" && (
              <div className="space-y-4">
                {/* Variable substitution controls */}
                {Object.keys(previewVars).length > 0 && (
                  <div className="border rounded p-3 bg-gray-50">
                    <p className="text-xs font-semibold text-gray-600 mb-2 flex items-center gap-1"><Tag size={12} /> Preview variables</p>
                    <div className="grid grid-cols-2 gap-2">
                      {Object.entries(previewVars).map(([k, v]) => (
                        <div key={k} className="flex items-center gap-1">
                          <span className="text-[10px] text-gray-500 w-28 shrink-0">{`{{${k}}}`}</span>
                          <input value={v} onChange={e => setPreviewVars(p => ({ ...p, [k]: e.target.value }))}
                            className="flex-1 text-[10px] border rounded px-1.5 py-1" />
                        </div>
                      ))}
                    </div>
                  </div>
                )}
                {/* Rendered preview */}
                <div className="border rounded p-4 bg-white shadow-sm">
                  <p className="text-xs text-gray-400 mb-1">Subject:</p>
                  <p className="font-medium text-sm mb-4">{renderPreview(selected.subject)}</p>
                  <hr className="mb-4" />
                  <div
                    className="prose prose-sm max-w-none"
                    dangerouslySetInnerHTML={{ __html: sanitizeHtml(renderPreview(selected.body_html)) }}
                  />
                </div>
              </div>
            )}

            {/* Edit tab */}
            {detailTab === "edit" && (
              <div className="space-y-3 max-w-2xl">
                {selected.is_system && (
                  <div className="p-2 bg-amber-50 border border-amber-200 rounded text-xs text-amber-700">
                    System templates cannot be edited. Use "Revise" to create an editable copy.
                  </div>
                )}
                <div>
                  <label className="block text-xs font-medium mb-1">Name</label>
                  <input value={editForm.name} onChange={e => setEditForm(p => ({ ...p, name: e.target.value }))}
                    className="input w-full" disabled={selected.is_system} />
                </div>
                <div>
                  <label className="block text-xs font-medium mb-1">Subject</label>
                  <input value={editForm.subject} onChange={e => setEditForm(p => ({ ...p, subject: e.target.value }))}
                    className="input w-full" disabled={selected.is_system} />
                </div>
                <div>
                  <label className="block text-xs font-medium mb-1">Category</label>
                  <select value={editForm.category} onChange={e => setEditForm(p => ({ ...p, category: e.target.value }))}
                    className="input w-full" disabled={selected.is_system}>
                    {CATEGORIES.map(c => <option key={c} value={c}>{c}</option>)}
                  </select>
                </div>
                <div>
                  <label className="block text-xs font-medium mb-1">Body HTML
                    <span className="ml-2 font-normal text-gray-400">(use {`{{variable_name}}`} for substitution)</span>
                  </label>
                  <textarea value={editForm.body_html} onChange={e => setEditForm(p => ({ ...p, body_html: e.target.value }))}
                    rows={16} className="input w-full font-mono text-xs" disabled={selected.is_system} />
                </div>
                {!selected.is_system && (
                  <div className="flex gap-2">
                    <button onClick={saveEdit} className="btn-primary">Save changes</button>
                    <button onClick={() => { setEditing(false); setDetailTab("preview"); }} className="btn-secondary">Cancel</button>
                  </div>
                )}
              </div>
            )}

            {/* Send tab */}
            {detailTab === "send" && (
              <div className="space-y-3 max-w-sm">
                <p className="text-sm text-gray-600">Send a test or live copy of this template.</p>
                <div>
                  <label className="block text-xs font-medium mb-1">Recipient email</label>
                  <input value={sendForm.to_email} onChange={e => setSendForm(p => ({ ...p, to_email: e.target.value }))}
                    className="input w-full" placeholder="customer@example.com" type="email" />
                </div>
                <div>
                  <label className="block text-xs font-medium mb-1">Subject override <span className="text-gray-400">(optional)</span></label>
                  <input value={sendForm.subject} onChange={e => setSendForm(p => ({ ...p, subject: e.target.value }))}
                    className="input w-full" placeholder={selected.subject} />
                </div>
                {Object.keys(previewVars).length > 0 && (
                  <div className="border rounded p-3 bg-gray-50">
                    <p className="text-xs font-semibold text-gray-600 mb-2">Variable values</p>
                    <div className="space-y-1.5">
                      {Object.entries(previewVars).map(([k, v]) => (
                        <div key={k} className="flex items-center gap-2">
                          <span className="text-[10px] font-mono text-gray-500 w-32 shrink-0">{`{{${k}}}`}</span>
                          <input value={v} onChange={e => setPreviewVars(p => ({ ...p, [k]: e.target.value }))}
                            className="flex-1 text-xs border rounded px-2 py-1" />
                        </div>
                      ))}
                    </div>
                  </div>
                )}
                <button onClick={sendNow} className="btn-primary w-full flex items-center justify-center gap-2">
                  <Send size={14} /> Send email
                </button>
              </div>
            )}
          </div>
        </div>
      ) : (
        <div className="flex-1 flex items-center justify-center text-gray-400">
          <div className="text-center space-y-2">
            <Mail size={40} className="mx-auto opacity-30" />
            <p className="text-sm">Select a template to preview or edit</p>
          </div>
        </div>
      )}

      {/* ── Create modal ──────────────────────────────────────────────── */}
      {showCreate && (
        <div className={styles.modal}>
          <div className={`${styles.modalPanel} space-y-3`}>
            <h3 className="font-semibold">New Email Template</h3>
            <div>
              <label className={styles.formLabel}>Name</label>
              <input value={form.name} onChange={e => setForm(p => ({ ...p, name: e.target.value }))} className="input w-full" />
            </div>
            <div>
              <label className={styles.formLabel}>Subject</label>
              <input value={form.subject} onChange={e => setForm(p => ({ ...p, subject: e.target.value }))} className="input w-full" />
            </div>
            <div>
              <label className={styles.formLabel}>Category</label>
              <select value={form.category} onChange={e => setForm(p => ({ ...p, category: e.target.value }))} className="input w-full">
                {CATEGORIES.map(c => <option key={c} value={c}>{c}</option>)}
              </select>
            </div>
            <div>
              <label className="block text-xs font-medium mb-1">Body HTML</label>
              <textarea value={form.body_html} onChange={e => setForm(p => ({ ...p, body_html: e.target.value }))}
                rows={8} className="input w-full font-mono text-xs" placeholder="<p>Hello {{customer_name}},</p>" />
            </div>
            <div className="flex gap-2 justify-end">
              <button onClick={() => setShowCreate(false)} className="btn-secondary">Cancel</button>
              <button onClick={create} className="btn-primary">Create template</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
