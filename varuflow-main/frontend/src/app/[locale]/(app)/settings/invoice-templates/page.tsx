"use client";

/**
 * Settings → Invoice Templates (Item 42)
 *
 * Manage branded invoice templates per org. Choose logo, brand
 * colors, font, toggle bank/QR/footer sections, and preview live.
 *
 * Wires: GET/POST /api/invoice-templates,
 *        PATCH/DELETE /api/invoice-templates/{id},
 *        POST /api/invoice-templates/{id}/set-default,
 *        POST /api/invoice-templates/{id}/preview.
 */
import { useCallback, useEffect, useMemo, useState } from "react";
import { useTranslations } from "next-intl";
import { toast } from "sonner";
import { FileText, Loader2, Plus, Star, Trash2 } from "lucide-react";

import { api } from "@/lib/api-client";

interface TemplateOut {
  id: string | null;
  name: string;
  is_default: boolean;
  logo_url: string | null;
  primary_color: string;
  accent_color: string;
  font_family: string;
  show_bank_details: boolean;
  show_qr_code: boolean;
  footer_text: string | null;
  header_text: string | null;
  is_active: boolean;
}

const FONT_OPTIONS = ["Helvetica", "Times-Roman", "Courier"];

export default function InvoiceTemplatesPage() {
  const t = useTranslations("invoice_templates");
  const [templates, setTemplates] = useState<TemplateOut[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [draft, setDraft] = useState<TemplateOut | null>(null);
  const [saving, setSaving] = useState(false);
  const [previewHtml, setPreviewHtml] = useState<string>("");

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const data = await api.get<TemplateOut[]>("/api/invoice-templates");
      setTemplates(data);
      if (data.length > 0 && !selectedId) {
        setSelectedId(data[0].id);
        setDraft(data[0]);
      }
    } catch {
      toast.error(t("load_failed"));
    } finally {
      setLoading(false);
    }
  }, [t, selectedId]);

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    const active = templates.find((x) => x.id === selectedId) ?? null;
    setDraft(active);
  }, [selectedId, templates]);

  const refreshPreview = useCallback(async () => {
    if (!draft?.id) {
      setPreviewHtml("");
      return;
    }
    try {
      const res = await api.post<{ html: string }>(
        `/api/invoice-templates/${draft.id}/preview`,
        { org_name: "Example AB", invoice_number: "INV-000123" },
      );
      setPreviewHtml(res.html);
    } catch {
      setPreviewHtml("");
    }
  }, [draft?.id]);

  useEffect(() => {
    refreshPreview();
  }, [refreshPreview]);

  const createTemplate = async () => {
    setSaving(true);
    try {
      const created = await api.post<TemplateOut>("/api/invoice-templates", {
        name: t("new_template_name"),
        primary_color: "#2f5ea8",
        accent_color: "#2563eb",
        font_family: "Helvetica",
        show_bank_details: true,
        show_qr_code: false,
      });
      toast.success(t("created"));
      setSelectedId(created.id);
      await load();
    } catch {
      toast.error(t("create_failed"));
    } finally {
      setSaving(false);
    }
  };

  const saveDraft = async () => {
    if (!draft?.id) return;
    setSaving(true);
    try {
      await api.patch(`/api/invoice-templates/${draft.id}`, {
        name: draft.name,
        logo_url: draft.logo_url,
        primary_color: draft.primary_color,
        accent_color: draft.accent_color,
        font_family: draft.font_family,
        show_bank_details: draft.show_bank_details,
        show_qr_code: draft.show_qr_code,
        footer_text: draft.footer_text,
        header_text: draft.header_text,
      });
      toast.success(t("saved"));
      await load();
      await refreshPreview();
    } catch {
      toast.error(t("save_failed"));
    } finally {
      setSaving(false);
    }
  };

  const makeDefault = async () => {
    if (!draft?.id) return;
    try {
      await api.post(`/api/invoice-templates/${draft.id}/set-default`, {});
      toast.success(t("default_set"));
      await load();
    } catch {
      toast.error(t("default_failed"));
    }
  };

  const deleteTemplate = async () => {
    if (!draft?.id) return;
    if (!confirm(t("delete_confirm"))) return;
    try {
      await api.delete(`/api/invoice-templates/${draft.id}`);
      toast.success(t("deleted"));
      setSelectedId(null);
      await load();
    } catch {
      toast.error(t("delete_failed"));
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center p-12">
        <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
      </div>
    );
  }

  return (
    <div className="container mx-auto p-6 space-y-6">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <FileText className="h-6 w-6" />
          <h1 className="text-2xl font-semibold">{t("title")}</h1>
        </div>
        <button
          onClick={createTemplate}
          disabled={saving}
          className="inline-flex items-center gap-1 rounded bg-primary text-primary-foreground px-3 py-1.5 text-sm"
        >
          <Plus className="h-4 w-4" />
          {t("new_template")}
        </button>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-[240px_1fr_1fr] gap-4">
        {/* List */}
        <div className="rounded-lg border divide-y">
          {templates.length === 0 && (
            <div className="p-4 text-sm text-muted-foreground">{t("empty")}</div>
          )}
          {templates.map((tpl) => (
            <button
              key={tpl.id ?? tpl.name}
              onClick={() => setSelectedId(tpl.id)}
              className={`w-full text-left p-3 text-sm flex items-center justify-between ${
                tpl.id === selectedId ? "bg-muted" : ""
              }`}
            >
              <span className="truncate">{tpl.name}</span>
              {tpl.is_default && <Star className="h-4 w-4 text-yellow-500" />}
            </button>
          ))}
        </div>

        {/* Editor */}
        <div className="rounded-lg border p-4 space-y-3">
          {draft ? (
            <>
              <div>
                <label className="text-xs text-muted-foreground">
                  {t("field_name")}
                </label>
                <input
                  className="w-full border rounded px-2 py-1 text-sm"
                  value={draft.name}
                  onChange={(e) => setDraft({ ...draft, name: e.target.value })}
                />
              </div>
              <div>
                <label className="text-xs text-muted-foreground">
                  {t("field_logo_url")}
                </label>
                <input
                  className="w-full border rounded px-2 py-1 text-sm"
                  value={draft.logo_url ?? ""}
                  onChange={(e) =>
                    setDraft({ ...draft, logo_url: e.target.value || null })
                  }
                  placeholder="https://cdn.example/logo.png"
                />
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="text-xs text-muted-foreground">
                    {t("field_primary_color")}
                  </label>
                  <input
                    type="color"
                    className="w-full h-9 border rounded"
                    value={draft.primary_color}
                    onChange={(e) =>
                      setDraft({ ...draft, primary_color: e.target.value })
                    }
                  />
                </div>
                <div>
                  <label className="text-xs text-muted-foreground">
                    {t("field_accent_color")}
                  </label>
                  <input
                    type="color"
                    className="w-full h-9 border rounded"
                    value={draft.accent_color}
                    onChange={(e) =>
                      setDraft({ ...draft, accent_color: e.target.value })
                    }
                  />
                </div>
              </div>
              <div>
                <label className="text-xs text-muted-foreground">
                  {t("field_font_family")}
                </label>
                <select
                  className="w-full border rounded px-2 py-1 text-sm"
                  value={draft.font_family}
                  onChange={(e) =>
                    setDraft({ ...draft, font_family: e.target.value })
                  }
                >
                  {FONT_OPTIONS.map((f) => (
                    <option key={f} value={f}>
                      {f}
                    </option>
                  ))}
                </select>
              </div>
              <label className="flex items-center gap-2 text-sm">
                <input
                  type="checkbox"
                  checked={draft.show_bank_details}
                  onChange={(e) =>
                    setDraft({ ...draft, show_bank_details: e.target.checked })
                  }
                />
                {t("toggle_bank")}
              </label>
              <label className="flex items-center gap-2 text-sm">
                <input
                  type="checkbox"
                  checked={draft.show_qr_code}
                  onChange={(e) =>
                    setDraft({ ...draft, show_qr_code: e.target.checked })
                  }
                />
                {t("toggle_qr")}
              </label>
              <div>
                <label className="text-xs text-muted-foreground">
                  {t("field_header_text")}
                </label>
                <textarea
                  className="w-full border rounded px-2 py-1 text-sm"
                  rows={2}
                  value={draft.header_text ?? ""}
                  onChange={(e) =>
                    setDraft({ ...draft, header_text: e.target.value || null })
                  }
                />
              </div>
              <div>
                <label className="text-xs text-muted-foreground">
                  {t("field_footer_text")}
                </label>
                <textarea
                  className="w-full border rounded px-2 py-1 text-sm"
                  rows={2}
                  value={draft.footer_text ?? ""}
                  onChange={(e) =>
                    setDraft({ ...draft, footer_text: e.target.value || null })
                  }
                />
              </div>
              <div className="flex items-center gap-2 pt-2">
                <button
                  onClick={saveDraft}
                  disabled={saving}
                  className="rounded bg-primary text-primary-foreground px-3 py-1.5 text-sm"
                >
                  {saving ? t("saving") : t("save")}
                </button>
                <button
                  onClick={makeDefault}
                  disabled={draft.is_default}
                  className="rounded border px-3 py-1.5 text-sm"
                >
                  {draft.is_default ? t("is_default") : t("make_default")}
                </button>
                <button
                  onClick={deleteTemplate}
                  className="ml-auto inline-flex items-center gap-1 rounded border px-3 py-1.5 text-sm text-red-600"
                >
                  <Trash2 className="h-4 w-4" />
                  {t("delete")}
                </button>
              </div>
            </>
          ) : (
            <div className="text-sm text-muted-foreground">
              {t("select_or_create")}
            </div>
          )}
        </div>

        {/* Preview */}
        <div className="rounded-lg border overflow-hidden">
          <div className="bg-muted px-3 py-2 text-xs font-medium">
            {t("preview_heading")}
          </div>
          {previewHtml ? (
            <iframe
              title="invoice-preview"
              srcDoc={previewHtml}
              className="w-full h-[500px]"
            />
          ) : (
            <div className="p-4 text-sm text-muted-foreground">
              {t("preview_empty")}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
