"use client";
import { useEffect, useState } from "react";
// next-intl Link (not next/link): keeps the locale prefix so /quotes/new resolves
// to the app page (/en/quotes/new) instead of the public /quotes/[token] route.
import { Link } from "@/i18n/navigation";
import { api } from "@/lib/api-client";
import styles from "./page.module.scss";
import ContentPanel from "@/components/console/ContentPanel";

interface QuoteSummary { id: string; quote_number: string | null; revision: number; title: string; status: string; total: number; currency: string; customer_id: string; valid_until: string | null; created_at: string | null; }

export default function QuotesPage() {
  const [quotes, setQuotes] = useState<QuoteSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [selected, setSelected] = useState<QuoteSummary | null>(null);
  const [filter, setFilter] = useState("");

  const load = () => {
    const params = filter ? `?status=${filter}` : "";
    setLoading(true);
    api.get<QuoteSummary[]>(`/api/quotes${params}`).then(setQuotes).catch(() => {}).finally(() => setLoading(false));
  };

  useEffect(() => { load(); }, [filter]);

  const badge = (s: string) => {
    const STATUS_MODULE: Record<string, keyof typeof styles> = {
      draft:    "statusDraft",
      sent:     "statusSent",
      accepted: "statusAccepted",
      rejected: "statusRejected",
      expired:  "statusExpired",
      invoiced: "statusInvoiced",
    };
    return <span className={styles[STATUS_MODULE[s] ?? "statusDraft"]}>{s}</span>;
  };

  return (
    <div className="p-6 space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Quotes & Proposals</h1>
        <div className="flex gap-2">
          <Link href="/quotes/analytics" className="px-4 py-2 border rounded hover:bg-gray-50 text-sm">Analytics</Link>
          <Link href="/quotes/new" className="px-4 py-2 bg-[var(--vf-brand-primary)] text-white rounded hover:bg-[var(--vf-brand-primary-hover)]">New Quote</Link>
        </div>
      </div>
      <div className="flex gap-2">
        {["", "draft", "sent", "accepted", "rejected", "invoiced"].map(s => (
          <button key={s} onClick={() => setFilter(s)} className={`px-3 py-1 rounded text-sm ${filter === s ? "bg-[var(--vf-brand-primary)] text-white" : "bg-gray-100"}`}>{s || "All"}</button>
        ))}
      </div>
      <div className="overflow-hidden rounded border">
        <ContentPanel<QuoteSummary>
          hideHeader
          title="Quotes"
          rows={quotes}
          loading={loading}
          getRowId={(q) => q.id}
          columns={[
            { key: "title", header: "Title", render: (q) => q.title },
            { key: "quote_number", header: "#", render: (q) => `${q.quote_number || "—"} v${q.revision}` },
            { key: "total", header: "Total", className: "text-right", render: (q) => `${q.total.toLocaleString()} ${q.currency}` },
            { key: "status", header: "Status", render: (q) => badge(q.status) },
            { key: "valid_until", header: "Valid Until", render: (q) => q.valid_until || "—" },
          ]}
          selected={selected}
          onSelect={setSelected}
          detailTitle={(q) => q.title}
          detailDescription={(q) => `${q.quote_number || "—"} v${q.revision}`}
          renderDetail={(q) => (
            <div className="space-y-4">
              <dl className="divide-y">
                <div className="grid grid-cols-3 gap-2 py-2.5">
                  <dt className="text-xs font-medium text-muted-foreground">Status</dt>
                  <dd className="col-span-2">{badge(q.status)}</dd>
                </div>
                {([
                  ["Total", `${q.total.toLocaleString()} ${q.currency}`],
                  ["Valid until", q.valid_until || "—"],
                ] as [string, string][]).map(([label, val]) => (
                  <div key={label} className="grid grid-cols-3 gap-2 py-2.5">
                    <dt className="text-xs font-medium text-muted-foreground">{label}</dt>
                    <dd className="col-span-2 text-sm text-foreground">{val}</dd>
                  </div>
                ))}
              </dl>
              {/* next-intl Link → /sv/quotes/{id} (app), not the public /quotes/[token] */}
              <Link href={`/quotes/${q.id}`} className="inline-flex px-4 py-2 bg-[var(--vf-brand-primary)] text-white rounded hover:bg-[var(--vf-brand-primary-hover)] text-sm">
                Open quote
              </Link>
            </div>
          )}
        />
      </div>
    </div>
  );
}
