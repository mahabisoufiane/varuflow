"use client";
import { useEffect, useState } from "react";
import { List, Search, ChevronDown, Target } from "lucide-react";
import Link from "next/link";
import { api } from "@/lib/api-client";
import styles from "./page.module.scss";

interface Deal {
  id: string; title: string; stage: string; value: number | null; currency: string;
  close_date: string | null; customer_id: string | null; probability: number | null;
  win_reason: string | null; loss_reason: string | null;
  sales_cycle_days: number | null; created_at: string;
}

interface Stage { slug: string; name: string; color: string; is_won: boolean; is_lost: boolean; }

const STAGE_COLORS: Record<string, string> = {
  lead: "bg-gray-100 text-gray-700",
  qualified: "bg-blue-100 text-blue-700",
  proposal_sent: "bg-yellow-100 text-yellow-700",
  negotiation: "bg-orange-100 text-orange-700",
  won: "bg-green-100 text-green-700",
  lost: "bg-red-100 text-red-700",
  prospect: "bg-gray-100 text-gray-700",
  proposal: "bg-yellow-100 text-yellow-700",
};

const STAGE_MODULE: Record<string, keyof typeof styles> = {
  lead:          "stageLead",
  qualified:     "stageQualified",
  proposal_sent: "stageProposalSent",
  negotiation:   "stageNegotiation",
  won:           "stageWon",
  lost:          "stageLost",
  prospect:      "stageProspect",
  proposal:      "stageProposal",
};

function fmt(v: number | null, currency = "SEK") {
  if (v == null) return "—";
  return v.toLocaleString(undefined, { maximumFractionDigits: 0 }) + " " + currency;
}

export default function CrmListPage() {
  const [deals, setDeals] = useState<Deal[]>([]);
  const [stages, setStages] = useState<Stage[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [stageFilter, setStageFilter] = useState("");
  const [closedFilter, setClosedFilter] = useState<"" | "open" | "closed">("");
  const [sort, setSort] = useState<"created_at" | "value" | "close_date">("created_at");

  const load = async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams();
      if (stageFilter) params.set("stage", stageFilter);
      if (closedFilter === "open") params.set("is_closed", "false");
      if (closedFilter === "closed") params.set("is_closed", "true");
      if (search) params.set("search", search);
      params.set("limit", "200");
      const [d, s] = await Promise.all([
        api.get<Deal[]>(`/api/crm/deals?${params.toString()}`),
        api.get<Stage[]>("/api/crm/stages"),
      ]);
      setDeals(d);
      setStages(s);
    } catch { /* silent */ }
    finally { setLoading(false); }
  };

  useEffect(() => { load(); }, [stageFilter, closedFilter]);

  const handleSearch = (e: React.FormEvent) => { e.preventDefault(); load(); };

  const sorted = [...deals].sort((a, b) => {
    if (sort === "value") return (b.value ?? 0) - (a.value ?? 0);
    if (sort === "close_date") return (a.close_date ?? "9999").localeCompare(b.close_date ?? "9999");
    return b.created_at.localeCompare(a.created_at);
  });

  const totalValue = deals.reduce((acc, d) => acc + (d.value ?? 0), 0);
  const stageMap = Object.fromEntries(stages.map(s => [s.slug, s]));

  return (
    <div className="p-6 space-y-4">
      <div className="flex items-center justify-between flex-wrap gap-2">
        <div className="flex items-center gap-2">
          <List size={20} className="text-[#1a2332]" />
          <h1 className="text-xl font-bold">Deals</h1>
          <span className="text-xs text-gray-400 ml-1">{deals.length} deals · {fmt(totalValue)}</span>
        </div>
        <Link href="/crm" className="flex items-center gap-1.5 px-3 py-1.5 border rounded text-sm hover:bg-gray-50 text-gray-600">
          <Target size={14} /> Board
        </Link>
      </div>

      {/* Filters */}
      <div className="flex flex-wrap gap-2 items-center">
        <form onSubmit={handleSearch} className="flex items-center gap-1.5">
          <div className="relative">
            <Search size={13} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-gray-400" />
            <input
              className="pl-7 pr-3 py-1.5 border rounded text-sm focus:outline-none focus:ring-1 focus:ring-[#1a2332] w-48"
              placeholder="Search deals…"
              value={search}
              onChange={e => setSearch(e.target.value)}
            />
          </div>
          <button type="submit" className="px-3 py-1.5 bg-[#1a2332] text-white rounded text-sm hover:opacity-90">Search</button>
        </form>

        <select
          className="border rounded px-2 py-1.5 text-sm focus:outline-none"
          value={stageFilter}
          onChange={e => setStageFilter(e.target.value)}
        >
          <option value="">All stages</option>
          {stages.map(s => <option key={s.slug} value={s.slug}>{s.name}</option>)}
        </select>

        <select
          className="border rounded px-2 py-1.5 text-sm focus:outline-none"
          value={closedFilter}
          onChange={e => setClosedFilter(e.target.value as any)}
        >
          <option value="">All deals</option>
          <option value="open">Open</option>
          <option value="closed">Closed</option>
        </select>

        <select
          className="border rounded px-2 py-1.5 text-sm focus:outline-none"
          value={sort}
          onChange={e => setSort(e.target.value as any)}
        >
          <option value="created_at">Newest first</option>
          <option value="value">Highest value</option>
          <option value="close_date">Close date</option>
        </select>
      </div>

      {/* Table */}
      <div className="bg-white border rounded-xl overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-gray-50 text-xs text-gray-500">
            <tr>
              <th className="px-4 py-3 text-left">Title</th>
              <th className="px-4 py-3 text-left">Stage</th>
              <th className="px-4 py-3 text-right">Value</th>
              <th className="px-4 py-3 text-right">Probability</th>
              <th className="px-4 py-3 text-left">Close date</th>
              <th className="px-4 py-3 text-right">Cycle</th>
              <th className="px-4 py-3 text-left">Created</th>
            </tr>
          </thead>
          <tbody className="divide-y">
            {loading ? (
              <tr><td colSpan={7} className="text-center py-8 text-gray-300">Loading…</td></tr>
            ) : sorted.length === 0 ? (
              <tr><td colSpan={7} className="text-center py-8 text-gray-300">No deals found</td></tr>
            ) : sorted.map(deal => {
              const si = stageMap[deal.stage];
              const color = STAGE_COLORS[deal.stage] ?? "bg-gray-100 text-gray-600";
              const stageClass = STAGE_MODULE[deal.stage] ?? "stageLead";
              return (
                <tr key={deal.id} className="hover:bg-gray-50">
                  <td className="px-4 py-3">
                    <Link href={`/crm/deals/${deal.id}`} className="font-medium text-gray-900 hover:text-blue-600 hover:underline">
                      {deal.title}
                    </Link>
                  </td>
                  <td className="px-4 py-3">
                    <span className={styles[stageClass]}>
                      {si?.name ?? deal.stage}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-right font-medium">{fmt(deal.value, deal.currency)}</td>
                  <td className="px-4 py-3 text-right">
                    {deal.probability !== null ? (
                      <div className="flex items-center justify-end gap-1.5">
                        <div className="w-12 h-1.5 bg-gray-100 rounded-full overflow-hidden">
                          <div className="h-full bg-blue-400 rounded-full" style={{ width: `${deal.probability}%` }} />
                        </div>
                        <span>{deal.probability}%</span>
                      </div>
                    ) : "—"}
                  </td>
                  <td className="px-4 py-3 text-gray-500">{deal.close_date ?? "—"}</td>
                  <td className="px-4 py-3 text-right text-gray-500">
                    {deal.sales_cycle_days !== null ? `${deal.sales_cycle_days}d` : "—"}
                  </td>
                  <td className="px-4 py-3 text-gray-400">{new Date(deal.created_at).toLocaleDateString()}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
