"use client";

/**
 * Audit log — owner-only view of sensitive actions taken on the organization.
 *
 * Wires: GET /api/audit?action=&limit=&offset=
 */
import { useEffect, useState } from "react";
import { useLocale, useTranslations } from "next-intl";
import { api } from "@/lib/api-client";
import { ShieldCheck, Loader2 } from "lucide-react";

type AuditEntry = {
  id: string;
  action: string;
  target_type: string | null;
  target_id: string | null;
  actor_user_id: string | null;
  ip_address: string | null;
  extra: Record<string, unknown> | null;
  created_at: string;
};

const PAGE_SIZE = 50;

const KNOWN_ACTIONS = [
  "",
  "gdpr.org_anonymise",
  "billing.plan_upgraded",
  "billing.plan_downgraded",
  "team.role_changed",
  "team.member_removed",
];

export default function AuditPage() {
  const locale = useLocale();
  const t = useTranslations("audit");

  const [entries, setEntries] = useState<AuditEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [action, setAction] = useState<string>("");
  const [offset, setOffset] = useState(0);
  const [hasMore, setHasMore] = useState(false);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      setLoading(true);
      try {
        const q = new URLSearchParams({
          limit: String(PAGE_SIZE),
          offset: String(offset),
        });
        if (action) q.set("action", action);
        const rows = await api.get<AuditEntry[]>(`/api/audit?${q.toString()}`);
        if (!cancelled) {
          setEntries(rows);
          setHasMore(rows.length === PAGE_SIZE);
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    load();
    return () => {
      cancelled = true;
    };
  }, [action, offset]);

  return (
    <div className="mx-auto max-w-5xl p-6">
      <div className="mb-6 flex items-center gap-3">
        <ShieldCheck className="h-6 w-6 text-emerald-600" />
        <h1 className="text-2xl font-semibold">{t("title")}</h1>
      </div>
      <p className="mb-6 text-sm text-muted-foreground">{t("description")}</p>

      <div className="mb-4 flex items-center gap-3">
        <label className="text-sm font-medium">{t("filterLabel")}</label>
        <select
          value={action}
          onChange={(e) => {
            setAction(e.target.value);
            setOffset(0);
          }}
          className="rounded border border-border bg-background px-3 py-1.5 text-sm"
        >
          {KNOWN_ACTIONS.map((a) => (
            <option key={a} value={a}>
              {a || t("allActions")}
            </option>
          ))}
        </select>
      </div>

      <div className="overflow-x-auto rounded-lg border border-border">
        <table className="w-full text-sm">
          <thead className="bg-muted/50">
            <tr>
              <th className="px-3 py-2 text-left font-medium">{t("col.when")}</th>
              <th className="px-3 py-2 text-left font-medium">{t("col.action")}</th>
              <th className="px-3 py-2 text-left font-medium">{t("col.target")}</th>
              <th className="px-3 py-2 text-left font-medium">{t("col.actor")}</th>
              <th className="px-3 py-2 text-left font-medium">{t("col.ip")}</th>
            </tr>
          </thead>
          <tbody>
            {loading && (
              <tr>
                <td colSpan={5} className="px-3 py-6 text-center text-muted-foreground">
                  <Loader2 className="mx-auto h-4 w-4 animate-spin" />
                </td>
              </tr>
            )}
            {!loading && entries.length === 0 && (
              <tr>
                <td colSpan={5} className="px-3 py-6 text-center text-muted-foreground">
                  {t("empty")}
                </td>
              </tr>
            )}
            {!loading &&
              entries.map((e) => (
                <tr key={e.id} className="border-t border-border">
                  <td className="px-3 py-2 font-mono text-xs">
                    {new Date(e.created_at).toLocaleString(locale)}
                  </td>
                  <td className="px-3 py-2 font-medium">{e.action}</td>
                  <td className="px-3 py-2 text-xs">
                    {e.target_type && <span>{e.target_type}</span>}
                    {e.target_id && (
                      <span className="ml-1 font-mono text-muted-foreground">
                        {e.target_id.slice(0, 8)}…
                      </span>
                    )}
                  </td>
                  <td className="px-3 py-2 font-mono text-xs">
                    {e.actor_user_id ? e.actor_user_id.slice(0, 8) + "…" : "—"}
                  </td>
                  <td className="px-3 py-2 font-mono text-xs">
                    {e.ip_address ?? "—"}
                  </td>
                </tr>
              ))}
          </tbody>
        </table>
      </div>

      <div className="mt-4 flex items-center justify-between">
        <button
          type="button"
          onClick={() => setOffset(Math.max(0, offset - PAGE_SIZE))}
          disabled={offset === 0 || loading}
          className="rounded border border-border px-3 py-1.5 text-sm disabled:opacity-40"
        >
          {t("prev")}
        </button>
        <span className="text-xs text-muted-foreground">
          {t("page", { from: offset + 1, to: offset + entries.length })}
        </span>
        <button
          type="button"
          onClick={() => setOffset(offset + PAGE_SIZE)}
          disabled={!hasMore || loading}
          className="rounded border border-border px-3 py-1.5 text-sm disabled:opacity-40"
        >
          {t("next")}
        </button>
      </div>
    </div>
  );
}
