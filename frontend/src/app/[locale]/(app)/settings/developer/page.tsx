"use client";

/**
 * Developer API Keys (Item 45) — ENTERPRISE plan only.
 *
 * Issue, rotate, and revoke programmatic API keys. The plaintext is
 * shown exactly once at creation / rotation time and never again.
 *
 * Wires: GET/POST    /api/developer/keys
 *        POST        /api/developer/keys/{id}/rotate
 *        POST        /api/developer/keys/{id}/revoke
 *        GET         /api/developer/keys/{id}/usage
 */
import { useCallback, useEffect, useMemo, useState } from "react";
import { useTranslations } from "next-intl";
import { toast } from "sonner";
import {
  AlertTriangle,
  Copy,
  KeyRound,
  Loader2,
  RefreshCw,
  RotateCw,
  ShieldAlert,
  Trash2,
  Eye,
} from "lucide-react";

import { api } from "@/lib/api-client";


interface ApiKeyRow {
  id: string;
  name: string;
  key_prefix: string;
  scopes: string[];
  last_used_at: string | null;
  expires_at: string | null;
  is_revoked: boolean;
  created_at: string;
  created_by: string | null;
}

interface ApiKeyIssued extends ApiKeyRow {
  plaintext: string;
}

interface UsageRow {
  id: string;
  called_at: string;
  method: string;
  path: string;
  status_code: number | null;
  ip: string | null;
}


const SCOPES = ["read", "write", "admin"] as const;


export default function DeveloperKeysPage() {
  const t = useTranslations("developer");
  const [rows, setRows] = useState<ApiKeyRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [issuing, setIssuing] = useState(false);
  const [justIssued, setJustIssued] = useState<ApiKeyIssued | null>(null);
  const [usageKeyId, setUsageKeyId] = useState<string | null>(null);
  const [usage, setUsage] = useState<UsageRow[]>([]);

  // Form state for new key.
  const [newName, setNewName] = useState("");
  const [newScopes, setNewScopes] = useState<string[]>(["read"]);
  const [newExpiry, setNewExpiry] = useState("");

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      const data = await api.get<ApiKeyRow[]>("/api/developer/keys");
      setRows(Array.isArray(data) ? data : []);
    } catch (err: any) {
      toast.error(err?.message || t("load_failed"));
    } finally {
      setLoading(false);
    }
  }, [t]);

  useEffect(() => { void refresh(); }, [refresh]);

  const issue = useCallback(async () => {
    if (!newName.trim()) {
      toast.error(t("name_required"));
      return;
    }
    if (newScopes.length === 0) {
      toast.error(t("scope_required"));
      return;
    }
    setIssuing(true);
    try {
      const data = await api.post<ApiKeyIssued>("/api/developer/keys", {
          name: newName.trim(),
          scopes: newScopes,
          expires_at: newExpiry || null,
        });
      setJustIssued(data);
      setNewName(""); setNewScopes(["read"]); setNewExpiry("");
      await refresh();
    } catch (err: any) {
      toast.error(err?.message || t("issue_failed"));
    } finally {
      setIssuing(false);
    }
  }, [newName, newScopes, newExpiry, refresh, t]);

  const rotate = useCallback(async (id: string) => {
    if (!confirm(t("confirm_rotate"))) return;
    try {
      const data = await api.post<ApiKeyIssued>(
        `/api/developer/keys/${id}/rotate`, {},
      );
      setJustIssued(data);
      toast.success(t("rotated"));
      await refresh();
    } catch (err: any) {
      toast.error(err?.message || t("rotate_failed"));
    }
  }, [refresh, t]);

  const revoke = useCallback(async (id: string) => {
    if (!confirm(t("confirm_revoke"))) return;
    try {
      await api.post(`/api/developer/keys/${id}/revoke`, {});
      toast.success(t("revoked"));
      await refresh();
    } catch (err: any) {
      toast.error(err?.message || t("revoke_failed"));
    }
  }, [refresh, t]);

  const loadUsage = useCallback(async (id: string) => {
    setUsageKeyId(id);
    try {
      const data = await api.get<UsageRow[]>(`/api/developer/keys/${id}/usage`);
      setUsage(Array.isArray(data) ? data : []);
    } catch (err) {
      toast.error(t("usage_failed"));
    }
  }, [t]);

  const copy = useCallback((text: string) => {
    navigator.clipboard.writeText(text);
    toast.success(t("copied"));
  }, [t]);

  return (
    <div className="space-y-6 p-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold">{t("title")}</h1>
          <p className="text-sm text-muted-foreground">{t("subtitle")}</p>
        </div>
        <button
          onClick={() => void refresh()}
          className="flex items-center gap-2 rounded-md border px-3 py-2 text-sm hover:bg-accent"
        >
          <RefreshCw className="h-4 w-4" /> {t("refresh")}
        </button>
      </div>

      <div className="rounded-md border border-yellow-400 bg-yellow-50 p-3 text-sm text-yellow-900 dark:bg-yellow-950 dark:text-yellow-200">
        <ShieldAlert className="mr-2 inline h-4 w-4" />
        {t("enterprise_only")}
      </div>

      {/* "Just issued" banner — shown exactly once. */}
      {justIssued && (
        <div className="rounded-md border border-green-400 bg-green-50 p-4 dark:bg-green-950">
          <div className="flex items-center gap-2 font-medium text-green-900 dark:text-green-200">
            <AlertTriangle className="h-4 w-4" />
            {t("shown_once_warning")}
          </div>
          <div className="mt-3 flex items-center gap-2 rounded bg-white p-2 font-mono text-xs dark:bg-black">
            <code className="flex-1 break-all">{justIssued.plaintext}</code>
            <button
              onClick={() => copy(justIssued.plaintext)}
              className="rounded border p-1 hover:bg-accent"
              title={t("copy")}
            >
              <Copy className="h-3.5 w-3.5" />
            </button>
          </div>
          <button
            onClick={() => setJustIssued(null)}
            className="mt-3 rounded-md border px-3 py-1 text-sm hover:bg-accent"
          >
            {t("acknowledged")}
          </button>
        </div>
      )}

      {/* New key form */}
      <section className="rounded-lg border p-4">
        <h2 className="mb-3 flex items-center gap-2 text-lg font-medium">
          <KeyRound className="h-5 w-5" /> {t("new_key")}
        </h2>
        <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
          <input
            className="rounded-md border px-3 py-2 text-sm"
            placeholder={t("name_placeholder")}
            value={newName}
            onChange={(e) => setNewName(e.target.value)}
          />
          <input
            type="date"
            className="rounded-md border px-3 py-2 text-sm"
            value={newExpiry}
            onChange={(e) => setNewExpiry(e.target.value)}
          />
          <div className="md:col-span-2 flex flex-wrap gap-2">
            {SCOPES.map(s => (
              <label key={s} className="flex items-center gap-2 rounded-md border px-3 py-1.5 text-sm">
                <input
                  type="checkbox"
                  checked={newScopes.includes(s)}
                  onChange={(e) => setNewScopes(
                    e.target.checked
                      ? [...newScopes, s]
                      : newScopes.filter(x => x !== s),
                  )}
                />
                {t(`scope_${s}`)}
              </label>
            ))}
          </div>
          <div className="md:col-span-2 flex justify-end">
            <button
              onClick={() => void issue()}
              disabled={issuing}
              className="flex items-center gap-2 rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground disabled:opacity-50"
            >
              {issuing ? <Loader2 className="h-4 w-4 animate-spin" /> : <KeyRound className="h-4 w-4" />}
              {t("issue")}
            </button>
          </div>
        </div>
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
              className={`flex items-center gap-3 rounded-md border p-3 ${row.is_revoked ? "opacity-60" : ""}`}
            >
              <KeyRound className="h-5 w-5 shrink-0 text-muted-foreground" />
              <div className="min-w-0 flex-1">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="font-medium">{row.name}</span>
                  <code className="rounded bg-muted px-1.5 text-xs">vk_{row.key_prefix}…</code>
                  {row.scopes.map(s => (
                    <span key={s} className="rounded-sm border px-1.5 text-xs">{t(`scope_${s}`, { defaultValue: s })}</span>
                  ))}
                  {row.is_revoked && (
                    <span className="rounded-sm bg-red-100 px-1.5 text-xs text-red-800 dark:bg-red-950 dark:text-red-300">
                      {t("revoked_badge")}
                    </span>
                  )}
                </div>
                <div className="text-xs text-muted-foreground">
                  {row.last_used_at
                    ? t("last_used", { when: new Date(row.last_used_at).toLocaleString() })
                    : t("never_used")}
                </div>
              </div>
              <button
                onClick={() => void loadUsage(row.id)}
                className="rounded-md border p-2 text-sm hover:bg-accent"
                title={t("view_usage")}
              >
                <Eye className="h-4 w-4" />
              </button>
              {!row.is_revoked && (
                <>
                  <button
                    onClick={() => void rotate(row.id)}
                    className="rounded-md border p-2 text-sm hover:bg-accent"
                    title={t("rotate")}
                  >
                    <RotateCw className="h-4 w-4" />
                  </button>
                  <button
                    onClick={() => void revoke(row.id)}
                    className="rounded-md border p-2 text-sm text-destructive hover:bg-destructive/10"
                    title={t("revoke")}
                  >
                    <Trash2 className="h-4 w-4" />
                  </button>
                </>
              )}
            </div>
          ))}
        </div>
      )}

      {/* Usage log modal-lite */}
      {usageKeyId && (
        <div className="rounded-lg border p-4">
          <div className="mb-3 flex items-center justify-between">
            <h3 className="font-medium">{t("usage_title")}</h3>
            <button
              onClick={() => { setUsageKeyId(null); setUsage([]); }}
              className="rounded-md border px-3 py-1 text-sm hover:bg-accent"
            >
              {t("close")}
            </button>
          </div>
          {usage.length === 0 ? (
            <div className="text-sm text-muted-foreground">{t("no_usage")}</div>
          ) : (
            <div className="max-h-96 overflow-y-auto text-sm">
              <table className="w-full">
                <thead className="text-xs text-muted-foreground">
                  <tr><th className="text-left">{t("col_when")}</th><th className="text-left">{t("col_method")}</th><th className="text-left">{t("col_path")}</th><th className="text-left">{t("col_status")}</th><th className="text-left">{t("col_ip")}</th></tr>
                </thead>
                <tbody>
                  {usage.map(u => (
                    <tr key={u.id} className="border-t">
                      <td className="py-1">{new Date(u.called_at).toLocaleString()}</td>
                      <td>{u.method}</td>
                      <td className="font-mono text-xs">{u.path}</td>
                      <td>{u.status_code ?? "—"}</td>
                      <td>{u.ip ?? "—"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
