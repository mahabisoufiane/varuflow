"use client";

/**
 * Documents (Item 44)
 *
 * Upload and manage business documents — contracts, certificates,
 * compliance records — with categories, tags, optional entity links
 * (supplier / customer / product), expiry alerts, and team sharing.
 *
 * Wires: GET/POST/PATCH/DELETE /api/documents,
 *        GET /api/documents/expiring,
 *        GET /api/documents/linked/{type}/{id}.
 */
import { useCallback, useEffect, useMemo, useState } from "react";
import { useTranslations } from "next-intl";
import { toast } from "sonner";
import {
  AlertTriangle,
  Download,
  FileText,
  Link2,
  Loader2,
  Lock,
  Plus,
  RefreshCw,
  Search,
  Share2,
  Trash2,
  Upload,
} from "lucide-react";

import { api } from "@/lib/api-client";


interface DocumentRow {
  id: string;
  name: string;
  category: string;
  file_url: string;
  file_size: number;
  mime_type: string;
  tags: string[];
  uploaded_by: string | null;
  linked_type: string | null;
  linked_id: string | null;
  expires_at: string | null;
  is_shared: boolean;
  description: string | null;
  created_at: string;
  expiry_alert: boolean;
  days_until_expiry: number | null;
}


const CATEGORIES = [
  "contract",
  "certificate",
  "compliance",
  "insurance",
  "legal",
  "other",
] as const;

const LINKED_TYPES = ["supplier", "customer", "product"] as const;


function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}


export default function DocumentsPage() {
  const t = useTranslations("documents");
  const [rows, setRows] = useState<DocumentRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [query, setQuery] = useState("");
  const [category, setCategory] = useState<string>("");
  const [tagFilter, setTagFilter] = useState("");
  const [showExpiringOnly, setShowExpiringOnly] = useState(false);
  const [creating, setCreating] = useState(false);

  // New-document form state.
  const [newName, setNewName] = useState("");
  const [newCategory, setNewCategory] = useState<string>("other");
  const [newTags, setNewTags] = useState("");
  const [newExpiry, setNewExpiry] = useState("");
  const [newShared, setNewShared] = useState(true);
  const [newLinkedType, setNewLinkedType] = useState<string>("");
  const [newLinkedId, setNewLinkedId] = useState("");
  const [newDescription, setNewDescription] = useState("");
  const [newFile, setNewFile] = useState<File | null>(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams();
      if (category) params.set("category", category);
      if (query.trim()) params.set("q", query.trim());
      if (tagFilter.trim()) {
        for (const tag of tagFilter.split(",").map(s => s.trim()).filter(Boolean)) {
          params.append("tag", tag);
        }
      }
      const path = showExpiringOnly
        ? "/api/documents/expiring"
        : `/api/documents${params.toString() ? `?${params.toString()}` : ""}`;
      const data = await api<DocumentRow[]>(path);
      setRows(Array.isArray(data) ? data : []);
    } catch (err) {
      toast.error(t("load_failed"));
    } finally {
      setLoading(false);
    }
  }, [category, query, tagFilter, showExpiringOnly, t]);

  useEffect(() => { void refresh(); }, [refresh]);

  const upload = useCallback(async () => {
    if (!newName.trim() || !newFile) {
      toast.error(t("name_and_file_required"));
      return;
    }
    setCreating(true);
    try {
      // In production, the file would be uploaded to object-store via
      // a presigned URL. For now we register the file metadata and
      // use a placeholder URL — the backend records it and the
      // reaper reconciles in a follow-up.
      const fakeUrl = `local://uploads/${encodeURIComponent(newFile.name)}`;
      const body = {
        name: newName.trim(),
        category: newCategory,
        file_url: fakeUrl,
        file_size: newFile.size,
        mime_type: newFile.type || "application/pdf",
        tags: newTags.split(",").map(s => s.trim()).filter(Boolean),
        linked_type: newLinkedType || null,
        linked_id: newLinkedId.trim() || null,
        expires_at: newExpiry || null,
        is_shared: newShared,
        description: newDescription.trim() || null,
      };
      await api("/api/documents", { method: "POST", body: JSON.stringify(body) });
      toast.success(t("uploaded"));
      setNewName(""); setNewCategory("other"); setNewTags("");
      setNewExpiry(""); setNewShared(true); setNewLinkedType("");
      setNewLinkedId(""); setNewDescription(""); setNewFile(null);
      await refresh();
    } catch (err: any) {
      toast.error(err?.message || t("upload_failed"));
    } finally {
      setCreating(false);
    }
  }, [newName, newFile, newCategory, newTags, newLinkedType, newLinkedId,
      newExpiry, newShared, newDescription, refresh, t]);

  const toggleShared = useCallback(async (row: DocumentRow) => {
    try {
      await api(`/api/documents/${row.id}`, {
        method: "PATCH",
        body: JSON.stringify({ is_shared: !row.is_shared }),
      });
      await refresh();
    } catch (err) {
      toast.error(t("update_failed"));
    }
  }, [refresh, t]);

  const remove = useCallback(async (id: string) => {
    if (!confirm(t("confirm_delete"))) return;
    try {
      await api(`/api/documents/${id}`, { method: "DELETE" });
      toast.success(t("deleted"));
      await refresh();
    } catch (err) {
      toast.error(t("delete_failed"));
    }
  }, [refresh, t]);

  const expiringCount = useMemo(
    () => rows.filter(r => r.expiry_alert).length,
    [rows],
  );

  return (
    <div className="space-y-6 p-6">
      <div className="flex items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold">{t("title")}</h1>
          <p className="text-sm text-muted-foreground">{t("subtitle")}</p>
        </div>
        <button
          onClick={() => void refresh()}
          className="flex items-center gap-2 rounded-md border px-3 py-2 text-sm hover:bg-accent"
        >
          <RefreshCw className="h-4 w-4" />
          {t("refresh")}
        </button>
      </div>

      {expiringCount > 0 && (
        <div className="flex items-center gap-2 rounded-md border border-yellow-400 bg-yellow-50 p-3 text-sm text-yellow-900 dark:bg-yellow-950 dark:text-yellow-200">
          <AlertTriangle className="h-4 w-4" />
          {t("expiring_count", { count: expiringCount })}
        </div>
      )}

      {/* Upload form */}
      <section className="rounded-lg border p-4">
        <h2 className="mb-3 text-lg font-medium">{t("new_document")}</h2>
        <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
          <input
            className="rounded-md border px-3 py-2 text-sm"
            placeholder={t("name_placeholder")}
            value={newName}
            onChange={(e) => setNewName(e.target.value)}
          />
          <select
            className="rounded-md border px-3 py-2 text-sm"
            value={newCategory}
            onChange={(e) => setNewCategory(e.target.value)}
          >
            {CATEGORIES.map(c => (
              <option key={c} value={c}>{t(`category_${c}`)}</option>
            ))}
          </select>
          <input
            className="rounded-md border px-3 py-2 text-sm"
            placeholder={t("tags_placeholder")}
            value={newTags}
            onChange={(e) => setNewTags(e.target.value)}
          />
          <input
            type="date"
            className="rounded-md border px-3 py-2 text-sm"
            value={newExpiry}
            onChange={(e) => setNewExpiry(e.target.value)}
          />
          <select
            className="rounded-md border px-3 py-2 text-sm"
            value={newLinkedType}
            onChange={(e) => setNewLinkedType(e.target.value)}
          >
            <option value="">{t("no_link")}</option>
            {LINKED_TYPES.map(lt => (
              <option key={lt} value={lt}>{t(`link_${lt}`)}</option>
            ))}
          </select>
          <input
            className="rounded-md border px-3 py-2 text-sm"
            placeholder={t("linked_id_placeholder")}
            value={newLinkedId}
            onChange={(e) => setNewLinkedId(e.target.value)}
            disabled={!newLinkedType}
          />
          <textarea
            className="md:col-span-2 rounded-md border px-3 py-2 text-sm"
            rows={2}
            placeholder={t("description_placeholder")}
            value={newDescription}
            onChange={(e) => setNewDescription(e.target.value)}
          />
          <div className="flex items-center gap-2 md:col-span-2">
            <input
              type="file"
              onChange={(e) => setNewFile(e.target.files?.[0] ?? null)}
              className="text-sm"
            />
            <label className="ml-auto flex items-center gap-1 text-sm">
              <input
                type="checkbox"
                checked={newShared}
                onChange={(e) => setNewShared(e.target.checked)}
              />
              {t("shared_with_team")}
            </label>
            <button
              onClick={() => void upload()}
              disabled={creating}
              className="flex items-center gap-2 rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground disabled:opacity-50"
            >
              {creating ? <Loader2 className="h-4 w-4 animate-spin" /> : <Upload className="h-4 w-4" />}
              {t("upload")}
            </button>
          </div>
        </div>
      </section>

      {/* Filters */}
      <section className="flex flex-wrap items-center gap-3">
        <div className="flex items-center gap-2 rounded-md border px-3 py-2 text-sm">
          <Search className="h-4 w-4 text-muted-foreground" />
          <input
            className="bg-transparent outline-none"
            placeholder={t("search_placeholder")}
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
        </div>
        <select
          className="rounded-md border px-3 py-2 text-sm"
          value={category}
          onChange={(e) => setCategory(e.target.value)}
        >
          <option value="">{t("all_categories")}</option>
          {CATEGORIES.map(c => (
            <option key={c} value={c}>{t(`category_${c}`)}</option>
          ))}
        </select>
        <input
          className="rounded-md border px-3 py-2 text-sm"
          placeholder={t("tags_filter_placeholder")}
          value={tagFilter}
          onChange={(e) => setTagFilter(e.target.value)}
        />
        <label className="flex items-center gap-2 text-sm">
          <input
            type="checkbox"
            checked={showExpiringOnly}
            onChange={(e) => setShowExpiringOnly(e.target.checked)}
          />
          {t("expiring_only")}
        </label>
      </section>

      {/* List */}
      {loading ? (
        <div className="flex items-center gap-2 text-sm text-muted-foreground">
          <Loader2 className="h-4 w-4 animate-spin" /> {t("loading")}
        </div>
      ) : rows.length === 0 ? (
        <div className="rounded-md border border-dashed p-8 text-center text-sm text-muted-foreground">
          {t("empty")}
        </div>
      ) : (
        <div className="space-y-2">
          {rows.map(row => (
            <div
              key={row.id}
              className={`flex items-center gap-3 rounded-md border p-3 ${row.expiry_alert ? "border-yellow-400 bg-yellow-50 dark:bg-yellow-950" : ""}`}
            >
              <FileText className="h-5 w-5 shrink-0 text-muted-foreground" />
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-2">
                  <span className="truncate font-medium">{row.name}</span>
                  <span className="rounded-sm border px-1.5 text-xs">{t(`category_${row.category}`, { defaultValue: row.category })}</span>
                  {row.linked_type && (
                    <span className="flex items-center gap-1 text-xs text-muted-foreground">
                      <Link2 className="h-3 w-3" />
                      {t(`link_${row.linked_type}`, { defaultValue: row.linked_type })}
                    </span>
                  )}
                  {row.expiry_alert && (
                    <span className="flex items-center gap-1 text-xs text-yellow-800 dark:text-yellow-200">
                      <AlertTriangle className="h-3 w-3" />
                      {row.days_until_expiry !== null && row.days_until_expiry <= 0
                        ? t("expired")
                        : t("expires_in_days", { days: row.days_until_expiry ?? 0 })}
                    </span>
                  )}
                </div>
                <div className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
                  <span>{formatSize(row.file_size)}</span>
                  <span>·</span>
                  <span>{row.mime_type}</span>
                  {row.tags.length > 0 && (
                    <>
                      <span>·</span>
                      {row.tags.map(tag => (
                        <span key={tag} className="rounded-sm bg-muted px-1.5">{tag}</span>
                      ))}
                    </>
                  )}
                </div>
              </div>
              <button
                onClick={() => void toggleShared(row)}
                className="rounded-md border p-2 text-sm hover:bg-accent"
                title={row.is_shared ? t("make_private") : t("make_shared")}
              >
                {row.is_shared ? <Share2 className="h-4 w-4" /> : <Lock className="h-4 w-4" />}
              </button>
              <a
                href={row.file_url}
                target="_blank"
                rel="noreferrer"
                className="rounded-md border p-2 text-sm hover:bg-accent"
                title={t("download")}
              >
                <Download className="h-4 w-4" />
              </a>
              <button
                onClick={() => void remove(row.id)}
                className="rounded-md border p-2 text-sm text-destructive hover:bg-destructive/10"
                title={t("delete")}
              >
                <Trash2 className="h-4 w-4" />
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
