"use client";

import { api } from "@/lib/api-client";
import { useTranslations } from "next-intl";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useLocale } from "next-intl";
import { toast } from "sonner";
import { Key, Plus, Trash2, Copy, Eye, EyeOff, Clock, Shield } from "lucide-react";

interface ApiKey {
  id: string;
  name: string;
  key_prefix: string;
  scopes: string[];
  last_used_at: string | null;
  expires_at: string | null;
  created_at: string;
}

interface CreatedKey extends ApiKey {
  plaintext_key: string;
}

const AVAILABLE_SCOPES = [
  "invoices:read", "invoices:write",
  "customers:read", "customers:write",
  "inventory:read", "inventory:write",
  "analytics:read",
  "webhooks:read", "webhooks:write",
];

export default function ApiKeysPage() {
  const t      = useTranslations();
  const router = useRouter();
  const locale = useLocale();

  const [keys, setKeys]             = useState<ApiKey[]>([]);
  const [loading, setLoading]       = useState(true);
  const [showForm, setShowForm]     = useState(false);
  const [newKey, setNewKey]         = useState<CreatedKey | null>(null);
  const [revealedKey, setRevealedKey] = useState(false);

  const [form, setForm] = useState({
    name: "",
    scopes: [] as string[],
    expires_at: "",
  });

  useEffect(() => {
    api.get<ApiKey[]>("/api/api-keys")
      .then(setKeys)
      .catch((e: Error) => {
        if (e.message.includes("session")) router.push(`/${locale}/auth/login`);
        else toast.error(e.message);
      })
      .finally(() => setLoading(false));
  }, [locale, router]);

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    try {
      const created = await api.post<CreatedKey>("/api/api-keys", form);
      setKeys(prev => [created, ...prev]);
      setNewKey(created);
      setRevealedKey(false);
      setShowForm(false);
      setForm({ name: "", scopes: [], expires_at: "" });
    } catch (err: unknown) { toast.error((err as Error).message); }
  }

  async function handleRevoke(id: string) {
    try {
      await api.delete(`/api/api-keys/${id}`);
      setKeys(prev => prev.filter(k => k.id !== id));
      toast.success(t("keyRevoked"));
    } catch (err: unknown) { toast.error((err as Error).message); }
  }

  function toggleScope(scope: string) {
    setForm(f => ({
      ...f,
      scopes: f.scopes.includes(scope)
        ? f.scopes.filter(s => s !== scope)
        : [...f.scopes, scope],
    }));
  }

  function isExpired(expiresAt: string | null) {
    if (!expiresAt) return false;
    return new Date(expiresAt) < new Date();
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold tracking-tight vf-text-1">{t("apiKeys")}</h1>
          <p className="text-xs vf-text-m mt-0.5">{t("apiKeysDesc")}</p>
        </div>
        <button onClick={() => setShowForm(v => !v)} className="vf-btn text-xs">
          <Plus className="h-3.5 w-3.5" />{t("createKey")}
        </button>
      </div>

      {/* New key plaintext reveal modal */}
      {newKey && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
          <div className="absolute inset-0 bg-black/40 backdrop-blur-sm" />
          <div className="relative w-full max-w-lg vf-section rounded-2xl p-6 space-y-4">
            <div className="flex items-center gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-emerald-500/10">
                <Key className="h-5 w-5 text-emerald-400" />
              </div>
              <div>
                <p className="text-sm font-semibold vf-text-1">{t("keyCreatedTitle")}</p>
                <p className="text-xs vf-text-m">{t("keyCreatedWarning")}</p>
              </div>
            </div>
            <div className="rounded-xl p-3 font-mono text-xs bg-[var(--vf-bg-elevated)] border border-[var(--vf-border)]">
              <div className="flex items-center gap-2">
                <span className="flex-1 break-all vf-text-1">
                  {revealedKey ? newKey.plaintext_key : "•".repeat(48)}
                </span>
                <button onClick={() => setRevealedKey(v => !v)}
                  className="shrink-0 vf-text-m hover:vf-text-1 transition-colors">
                  {revealedKey ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                </button>
                <button onClick={() => {
                  navigator.clipboard.writeText(newKey.plaintext_key);
                  toast.success(t("copied"));
                }} className="shrink-0 vf-text-m hover:vf-text-1 transition-colors">
                  <Copy className="h-4 w-4" />
                </button>
              </div>
            </div>
            <button onClick={() => setNewKey(null)} className="vf-btn text-xs w-full">
              {t("iSavedMyKey")}
            </button>
          </div>
        </div>
      )}

      {/* Create key form */}
      {showForm && (
        <div className="vf-section p-5">
          <h2 className="text-[13px] font-semibold vf-text-1 mb-4">{t("newApiKey")}</h2>
          <form onSubmit={handleCreate} className="space-y-4">
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div>
                <label className="text-xs font-medium vf-text-m block mb-1">{t("keyName")}</label>
                <input required value={form.name}
                  onChange={e => setForm(f => ({ ...f, name: e.target.value }))}
                  placeholder="Production integration" className="vf-input text-xs w-full" />
              </div>
              <div>
                <label className="text-xs font-medium vf-text-m block mb-1">{t("expiresAt")} ({t("optional")})</label>
                <input type="date" value={form.expires_at}
                  onChange={e => setForm(f => ({ ...f, expires_at: e.target.value }))}
                  className="vf-input text-xs w-full" />
              </div>
            </div>
            <div>
              <label className="text-xs font-medium vf-text-m block mb-2">{t("scopes")}</label>
              <div className="flex flex-wrap gap-2">
                {AVAILABLE_SCOPES.map(scope => (
                  <button type="button" key={scope}
                    onClick={() => toggleScope(scope)}
                    className={`rounded-full px-3 py-1 text-[11px] font-medium transition-colors ${
                      form.scopes.includes(scope)
                        ? "bg-indigo-500 text-white"
                        : "vf-text-m hover:vf-text-1"
                    }`}
                    style={!form.scopes.includes(scope) ? { border: "1px solid var(--vf-border)" } : {}}>
                    {scope}
                  </button>
                ))}
              </div>
            </div>
            <div className="flex gap-2 justify-end">
              <button type="button" onClick={() => setShowForm(false)}
                className="vf-btn-secondary text-xs">
                {t("cancel")}
              </button>
              <button type="submit" className="vf-btn text-xs">{t("generate")}</button>
            </div>
          </form>
        </div>
      )}

      {/* Keys list */}
      <div className="vf-section">
        <div className="vf-section-header">
          <h2 className="text-[13px] font-semibold vf-text-1">{t("yourApiKeys")}</h2>
        </div>
        {loading ? (
          <div className="space-y-3 p-5">
            {[1, 2].map(i => <div key={i} className="h-14 skeleton rounded-xl" />)}
          </div>
        ) : keys.length === 0 ? (
          <div className="py-14 text-center">
            <div className="mx-auto mb-3 flex h-12 w-12 items-center justify-center rounded-2xl"
              >
              <Key className="h-6 w-6 vf-text-m" />
            </div>
            <p className="text-sm font-medium vf-text-2">{t("noApiKeys")}</p>
          </div>
        ) : (
          <div className="vf-divide">
            {keys.map(key => (
              <div key={key.id} className="flex items-center gap-4 px-5 py-4 vf-row">
                <div className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-xl ${
                  isExpired(key.expires_at) ? "bg-red-500/10" : "bg-indigo-500/10"
                }`}>
                  <Shield className={`h-4 w-4 ${isExpired(key.expires_at) ? "text-red-400" : "text-indigo-400"}`} />
                </div>
                <div className="flex-1 min-w-0">
                  <p className="text-[13px] font-semibold vf-text-1">{key.name}</p>
                  <p className="font-mono text-xs vf-text-m">{key.key_prefix}••••••••</p>
                  <div className="flex flex-wrap gap-1 mt-1">
                    {key.scopes.slice(0, 4).map(s => (
                      <span key={s} className="rounded-full bg-indigo-500/10 px-2 py-0.5 text-[10px] font-medium text-indigo-400">
                        {s}
                      </span>
                    ))}
                    {key.scopes.length > 4 && (
                      <span className="text-[11px] vf-text-m">+{key.scopes.length - 4}</span>
                    )}
                  </div>
                </div>
                <div className="text-right shrink-0">
                  {key.last_used_at ? (
                    <p className="text-[11px] vf-text-m flex items-center gap-1">
                      <Clock className="h-3 w-3" />
                      {new Date(key.last_used_at).toLocaleDateString()}
                    </p>
                  ) : (
                    <p className="text-[11px] vf-text-m">{t("neverUsed")}</p>
                  )}
                  {key.expires_at && (
                    <p className={`text-[11px] mt-0.5 ${isExpired(key.expires_at) ? "text-red-400" : "vf-text-m"}`}>
                      {isExpired(key.expires_at) ? t("expired") : t("expires")} {new Date(key.expires_at).toLocaleDateString()}
                    </p>
                  )}
                </div>
                <button onClick={() => handleRevoke(key.id)}
                  className="flex h-8 w-8 items-center justify-center rounded-lg text-red-400 hover:bg-red-500/10 transition-colors">
                  <Trash2 className="h-4 w-4" />
                </button>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
