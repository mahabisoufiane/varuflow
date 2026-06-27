"use client";

/**
 * Settings → Security → IP Allowlist (Item 25).
 *
 * Enterprise-only feature. Owners can add/remove CIDR entries that
 * restrict which IPs can reach the org's authenticated API.
 *
 *   • Empty list = allowlist disabled (allow-by-default).
 *   • ≥ 1 entry  = deny-by-default, only listed CIDRs pass.
 *
 * The backend enforces the rule inside ``get_current_member`` so every
 * authenticated route is gated without per-route wiring.
 */
import { api } from "@/lib/api-client";
import { useEffect, useState } from "react";
import { toast } from "sonner";
import { useTranslations } from "next-intl";
import { useParams, useRouter } from "next/navigation";
import { ArrowLeft, Plus, Trash2, Shield } from "lucide-react";

interface Entry {
  id: string;
  cidr: string;
  label: string | null;
  created_at: string;
}

export default function IpAllowlistPage() {
  const t = useTranslations("settings.security.ip_allowlist");
  const router = useRouter();
  const params = useParams<{ locale: string }>();
  const locale = params?.locale ?? "en";

  const [entries, setEntries] = useState<Entry[]>([]);
  const [loading, setLoading] = useState(true);
  const [cidr, setCidr]       = useState("");
  const [label, setLabel]     = useState("");
  const [busy, setBusy]       = useState(false);

  async function load() {
    try {
      const rows = await api.get<Entry[]>("/api/settings/security/ip-allowlist");
      setEntries(rows);
    } catch {
      // 403 (wrong plan / non-owner) renders an empty list; the
      // informational banner below explains why.
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { load(); }, []);

  async function handleAdd(e: React.FormEvent) {
    e.preventDefault();
    if (!cidr.trim()) return;
    setBusy(true);
    try {
      await api.post("/api/settings/security/ip-allowlist", {
        cidr: cidr.trim(),
        label: label.trim() || null,
      });
      toast.success(t("added"));
      setCidr(""); setLabel("");
      await load();
    } catch (err: unknown) {
      const msg = (err as Error).message || t("add_failed");
      toast.error(msg);
    } finally { setBusy(false); }
  }

  async function handleDelete(id: string) {
    if (!confirm(t("confirm_remove"))) return;
    setBusy(true);
    try {
      await api.delete(`/api/settings/security/ip-allowlist/${id}`);
      toast.success(t("removed"));
      await load();
    } catch {
      toast.error(t("remove_failed"));
    } finally { setBusy(false); }
  }

  if (loading) {
    return (
      <div className="max-w-2xl space-y-4">
        <div className="h-8 w-48 skeleton rounded" />
        <div className="h-48 skeleton rounded-xl" />
      </div>
    );
  }

  return (
    <div className="max-w-2xl space-y-6">
      <button
        onClick={() => router.push(`/${locale}/settings/security`)}
        className="inline-flex items-center gap-1.5 text-xs vf-text-m hover:vf-text-2"
      >
        <ArrowLeft className="h-3.5 w-3.5" /> {t("back")}
      </button>

      <div>
        <h1 className="text-xl font-bold vf-text-1 flex items-center gap-2">
          <Shield className="h-5 w-5" /> {t("title")}
        </h1>
        <p className="text-xs vf-text-m mt-0.5">{t("subtitle")}</p>
      </div>

      <div className="vf-section p-4 space-y-2 text-xs vf-text-m" >
        <p>{t("info_empty")}</p>
        <p>{t("info_nonempty")}</p>
        <p className="text-red-400">{t("info_warning")}</p>
      </div>

      {/* Add form ──────────────────────────────────────────────────── */}
      <form onSubmit={handleAdd} className="vf-section p-5 space-y-4" >
        <h2 className="text-sm font-semibold vf-text-1">{t("add_title")}</h2>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          <div className="space-y-1.5">
            <label className="text-xs font-medium vf-text-m">{t("cidr_label")}</label>
            <input value={cidr} onChange={e => setCidr(e.target.value)}
                   placeholder="203.0.113.0/24" className="vf-input font-mono" />
          </div>
          <div className="space-y-1.5">
            <label className="text-xs font-medium vf-text-m">{t("label_label")}</label>
            <input value={label} onChange={e => setLabel(e.target.value)}
                   placeholder={t("label_placeholder")} className="vf-input" maxLength={255} />
          </div>
        </div>
        <button type="submit" disabled={busy || !cidr.trim()} className="vf-btn-primary text-sm inline-flex items-center gap-1.5">
          <Plus className="h-3.5 w-3.5" />
          {busy ? t("working") : t("add")}
        </button>
      </form>

      {/* List ─────────────────────────────────────────────────────── */}
      <div className="vf-section p-5 space-y-3" >
        <h2 className="text-sm font-semibold vf-text-1">{t("entries_title")}</h2>
        {entries.length === 0 ? (
          <p className="text-xs vf-text-m">{t("no_entries")}</p>
        ) : (
          <ul className="space-y-2">
            {entries.map(e => (
              <li key={e.id} className="flex items-center gap-3 py-2 border-b border-white/5 last:border-b-0">
                <code className="font-mono text-xs vf-text-1">{e.cidr}</code>
                {e.label && <span className="text-xs vf-text-m">{e.label}</span>}
                <span className="flex-1" />
                <button onClick={() => handleDelete(e.id)} disabled={busy}
                        className="text-xs text-red-400 hover:text-red-300 inline-flex items-center gap-1">
                  <Trash2 className="h-3 w-3" /> {t("remove")}
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}
