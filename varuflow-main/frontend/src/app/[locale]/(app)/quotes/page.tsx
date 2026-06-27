"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { api } from "@/lib/api-client";
import styles from "./page.module.scss";

interface QuoteSummary { id: string; quote_number: string | null; revision: number; title: string; status: string; total: number; currency: string; customer_id: string; valid_until: string | null; created_at: string | null; }

export default function QuotesPage() {
  const [quotes, setQuotes] = useState<QuoteSummary[]>([]);
  const [filter, setFilter] = useState("");

  const load = () => {
    const params = filter ? `?status=${filter}` : "";
    api.get<QuoteSummary[]>(`/api/quotes${params}`).then(setQuotes).catch(() => {});
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
          <Link href="/quotes/new" className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700">New Quote</Link>
        </div>
      </div>
      <div className="flex gap-2">
        {["", "draft", "sent", "accepted", "rejected", "invoiced"].map(s => (
          <button key={s} onClick={() => setFilter(s)} className={`px-3 py-1 rounded text-sm ${filter === s ? "bg-blue-600 text-white" : "bg-gray-100"}`}>{s || "All"}</button>
        ))}
      </div>
      <table className="w-full text-sm border">
        <thead className="bg-gray-50">
          <tr>
            <th className="px-4 py-2 text-left">Title</th>
            <th className="px-4 py-2 text-left">#</th>
            <th className="px-4 py-2 text-right">Total</th>
            <th className="px-4 py-2 text-left">Status</th>
            <th className="px-4 py-2 text-left">Valid Until</th>
          </tr>
        </thead>
        <tbody>
          {quotes.map(q => (
            <tr key={q.id} className="border-t hover:bg-gray-50 cursor-pointer" onClick={() => window.location.href = `/quotes/${q.id}`}>
              <td className="px-4 py-2">{q.title}</td>
              <td className="px-4 py-2 text-xs">{q.quote_number || "—"} v{q.revision}</td>
              <td className="px-4 py-2 text-right">{q.total.toLocaleString()} {q.currency}</td>
              <td className="px-4 py-2">{badge(q.status)}</td>
              <td className="px-4 py-2">{q.valid_until || "—"}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
