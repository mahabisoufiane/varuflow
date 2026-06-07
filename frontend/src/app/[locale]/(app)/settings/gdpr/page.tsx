"use client";

/**
 * GDPR data-subject page — owner-only export + account deletion.
 *
 * Wires:
 *   GET    /api/gdpr/export         → downloads a JSON dump
 *   DELETE /api/gdpr/organization   → hard-deletes the organization
 */
import { useState } from "react";
import { useRouter } from "next/navigation";
import { useTranslations, useLocale } from "next-intl";
import { AlertTriangle, Download, Loader2, Trash2 } from "lucide-react";
import { toast } from "sonner";

import { api } from "@/lib/api-client";
import { createClient, isSupabaseConfigured } from "@/lib/supabase/client";

export default function GdprPage() {
  const router   = useRouter();
  const locale   = useLocale();
  const t        = useTranslations("gdpr");

  const [exporting, setExporting] = useState(false);
  const [bokforingExporting, setBokforingExporting] = useState(false);
  const [sie4Exporting, setSie4Exporting] = useState(false);
  const [deleting, setDeleting]   = useState(false);
  const [confirmText, setConfirmText] = useState("");

  async function handleExport() {
    setExporting(true);
    try {
      const today = new Date().toISOString().slice(0, 10);
      await api.downloadBlob("/api/gdpr/export", `varuflow-export-${today}.json`);
      toast.success(t("exportStarted"));
    } catch {
      // error toast already fired by api-client
    } finally {
      setExporting(false);
    }
  }

  async function handleBokforingExport() {
    setBokforingExporting(true);
    try {
      const year = new Date().getFullYear();
      await api.downloadBlob(
        "/api/gdpr/bokforing-export",
        `varuflow-bokforing-${year}.zip`,
        "POST",
      );
      toast.success(t("exportStarted"));
    } catch {
      // error toast already fired by api-client
    } finally {
      setBokforingExporting(false);
    }
  }

  async function handleSie4Export() {
    setSie4Exporting(true);
    try {
      const year = new Date().getFullYear();
      await api.downloadBlob(
        `/api/accounting/sie4-export?year=${year}`,
        `varuflow-SIE4-${year}.se`,
        "POST",
      );
      toast.success(t("exportStarted"));
    } catch {
      // error toast already fired by api-client
    } finally {
      setSie4Exporting(false);
    }
  }

  async function handleDelete() {
    if (confirmText !== "DELETE") {
      toast.error(t("confirmRequired"));
      return;
    }
    setDeleting(true);
    try {
      await api.delete<void>("/api/gdpr/organization", { "X-Confirm-Delete": "DELETE" });
      if (isSupabaseConfigured) {
        await createClient().auth.signOut();
      }
      toast.success(t("deleted"));
      router.push(`/${locale}/auth/login`);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : t("deleteFailed"));
    } finally {
      setDeleting(false);
    }
  }

  return (
    <div className="max-w-3xl space-y-6 p-6">
      <header>
        <h1 className="text-2xl font-semibold">{t("title")}</h1>
        <p className="text-sm vf-text-m mt-1">{t("subtitle")}</p>
      </header>

      {/* ── Export ─────────────────────────────────────────────── */}
      <section className="vf-section p-6 space-y-3" >
        <h2 className="text-lg font-medium flex items-center gap-2">
          <Download size={18} /> {t("exportTitle")}
        </h2>
        <p className="text-sm vf-text-m">{t("exportBody")}</p>
        <button
          type="button"
          onClick={handleExport}
          disabled={exporting}
          className="vf-btn vf-btn-primary disabled:opacity-60"
        >
          {exporting ? <Loader2 className="animate-spin" size={16} /> : <Download size={16} />}
          {exporting ? t("exporting") : t("exportButton")}
        </button>
      </section>

      {/* ── Bokföring compliance export ────────────────────────── */}
      <section className="vf-section p-6 space-y-3" >
        <h2 className="text-lg font-medium flex items-center gap-2">
          <Download size={18} /> {t("bokforing_export_title")}
        </h2>
        <p className="text-sm vf-text-m">{t("bokforing_export_description")}</p>
        <button
          type="button"
          onClick={handleBokforingExport}
          disabled={bokforingExporting}
          className="vf-btn vf-btn-primary disabled:opacity-60"
        >
          {bokforingExporting ? (
            <Loader2 className="animate-spin" size={16} />
          ) : (
            <Download size={16} />
          )}
          {bokforingExporting ? t("bokforing_exporting") : t("bokforing_export_button")}
        </button>
      </section>

      {/* ── SIE4 accounting export ─────────────────────────────── */}
      <section className="vf-section p-6 space-y-3" >
        <h2 className="text-lg font-medium flex items-center gap-2">
          <Download size={18} /> {t("sie4_export_title")}
        </h2>
        <p className="text-sm vf-text-m">{t("sie4_export_description")}</p>
        <button
          type="button"
          onClick={handleSie4Export}
          disabled={sie4Exporting}
          className="vf-btn vf-btn-primary disabled:opacity-60"
        >
          {sie4Exporting ? (
            <Loader2 className="animate-spin" size={16} />
          ) : (
            <Download size={16} />
          )}
          {sie4Exporting ? t("sie4_exporting") : t("sie4_export_button")}
        </button>
      </section>

      {/* ── Delete ─────────────────────────────────────────────── */}
      <section
        className="vf-section p-6 space-y-3 border border-red-500/40"
        
      >
        <h2 className="text-lg font-medium flex items-center gap-2 text-red-600">
          <AlertTriangle size={18} /> {t("deleteTitle")}
        </h2>
        <p className="text-sm vf-text-m">{t("deleteBody")}</p>
        <label className="block space-y-1">
          <span className="text-xs font-medium vf-text-m">{t("confirmLabel")}</span>
          <input
            type="text"
            value={confirmText}
            onChange={(e) => setConfirmText(e.target.value)}
            placeholder="DELETE"
            className="vf-input w-full max-w-sm"
          />
        </label>
        <button
          type="button"
          onClick={handleDelete}
          disabled={deleting || confirmText !== "DELETE"}
          className="vf-btn bg-red-600 hover:bg-red-700 text-white disabled:opacity-50"
        >
          {deleting ? <Loader2 className="animate-spin" size={16} /> : <Trash2 size={16} />}
          {deleting ? t("deleting") : t("deleteButton")}
        </button>
      </section>
    </div>
  );
}
