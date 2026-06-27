"use client";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { portalApi, PORTAL_TOKEN_KEY } from "@/lib/portal-client";

interface QuoteSummary { id: string; title: string; quote_number: string | null; revision: number; status: string; total: number; currency: string; valid_until: string | null; created_at: string; }

export default function PortalQuotesPage() {
  const router = useRouter();
  const [quotes, setQuotes] = useState<QuoteSummary[]>([]);

  useEffect(() => {
    if (!localStorage.getItem(PORTAL_TOKEN_KEY)) { router.replace("/portal/login"); return; }
    portalApi.get<QuoteSummary[]>("/api/portal/quotes").then(setQuotes);
  }, []);

  const badge = (s: string) => {
    const c: Record<string, string> = { sent: "bg-blue-100 text-blue-800", accepted: "bg-green-100 text-green-800", rejected: "bg-red-100 text-red-800", expired: "bg-gray-100 text-gray-800", invoiced: "bg-purple-100 text-purple-800" };
    return <span className={`px-2 py-0.5 rounded text-xs font-medium ${c[s] || "bg-gray-100"}`}>{s}</span>;
  };

  return (
    <div className="space-y-4">
      <h1 className="text-xl font-bold">Quotes & Proposals</h1>
      {quotes.length === 0 && <p className="text-gray-500 text-sm">No quotes yet.</p>}
      <div className="space-y-2">
        {quotes.map(q => (
          <Link key={q.id} href={`/portal/quotes/${q.id}`} className="block bg-white border rounded p-3 hover:bg-gray-50">
            <div className="flex justify-between items-center">
              <div>
                <span className="font-medium">{q.title}</span>
                {q.quote_number && <span className="text-xs text-gray-500 ml-2">#{q.quote_number} v{q.revision}</span>}
              </div>
              {badge(q.status)}
            </div>
            <div className="flex justify-between text-xs text-gray-500 mt-1">
              <span>{q.total.toLocaleString()} {q.currency}</span>
              <span>{q.valid_until ? `Valid until ${q.valid_until}` : ""}</span>
            </div>
          </Link>
        ))}
      </div>
    </div>
  );
}
