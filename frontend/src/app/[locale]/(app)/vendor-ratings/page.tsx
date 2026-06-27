"use client";

import { api } from "@/lib/api-client";
import { useEffect, useState } from "react";
import { useRouter, useParams } from "next/navigation";
import { toast } from "sonner";
import { Star, RefreshCw, Trophy, TrendingUp, Clock, ShieldCheck, ChevronDown, ChevronUp, AlertTriangle } from "lucide-react";

interface RatingCache {
  supplier_id: string;
  supplier_name?: string;
  on_time_rate: number;
  quality_score: number;
  price_stability: number;
  manual_avg: number;
  overall_score: number;
  po_count: number;
  last_updated: string;
}

interface ManualRating {
  id: string;
  supplier_id?: string;
  purchase_order_id?: string;
  stars: number;
  comment?: string;
  delivery_ok: boolean;
  quality_ok: boolean;
  rated_by_staff_id?: string;
  created_at: string;
}

function StarRow({ value, max = 5 }: { value: number; max?: number }) {
  return (
    <div className="flex gap-0.5">
      {Array.from({ length: max }).map((_, i) => (
        <Star
          key={i}
          className={`h-3.5 w-3.5 ${i < Math.round(value) ? "fill-amber-400 text-amber-400" : "text-gray-200"}`}
        />
      ))}
    </div>
  );
}

function ScoreBar({ value, color = "bg-primary" }: { value: number; color?: string }) {
  return (
    <div className="flex items-center gap-2">
      <div className="flex-1 h-2 bg-muted rounded-full overflow-hidden">
        <div className={`h-full ${color} rounded-full transition-all`} style={{ width: `${Math.min(value, 100)}%` }} />
      </div>
      <span className="text-xs font-medium w-10 text-right">{value.toFixed(0)}%</span>
    </div>
  );
}

function overallColor(score: number) {
  if (score >= 80) return "text-green-600";
  if (score >= 60) return "text-amber-500";
  return "text-red-500";
}

export default function VendorRatingsPage() {
  const router = useRouter();
  const params = useParams();
  const locale = params.locale as string;

  const [ranking, setRanking] = useState<RatingCache[]>([]);
  const [ratings, setRatings] = useState<ManualRating[]>([]);
  const [loading, setLoading] = useState(true);
  const [expanded, setExpanded] = useState<string | null>(null);
  const [showRate, setShowRate] = useState(false);
  const [tab, setTab] = useState<"ranking" | "history">("ranking");

  const [form, setForm] = useState({
    supplier_id: "",
    purchase_order_id: "",
    stars: 3,
    comment: "",
    delivery_ok: true,
    quality_ok: true,
  });

  async function load() {
    try {
      const [rankData, histData] = await Promise.all([
        api.get("/api/vendor-ratings/ranking"),
        api.get("/api/vendor-ratings"),
      ]);
      setRanking(rankData.items ?? rankData);
      setRatings(histData.items ?? histData);
    } catch (err: any) {
      if (err?.status === 401) router.push(`/${locale}/auth/login`);
      else toast.error("Failed to load vendor ratings");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { load(); }, []);

  async function handleRate(e: React.FormEvent) {
    e.preventDefault();
    try {
      await api.post("/api/vendor-ratings", {
        ...form,
        purchase_order_id: form.purchase_order_id || undefined,
      });
      toast.success("Rating submitted");
      setShowRate(false);
      setForm({ supplier_id: "", purchase_order_id: "", stars: 3, comment: "", delivery_ok: true, quality_ok: true });
      load();
    } catch {
      toast.error("Failed to submit rating");
    }
  }

  const topSupplier = ranking[0];
  const atRisk = ranking.filter(r => r.overall_score < 60);

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Vendor Ratings</h1>
          <p className="text-sm text-muted-foreground mt-1">
            Supplier performance: on-time delivery, quality, price stability, and manual ratings
          </p>
        </div>
        <button className="btn-primary flex items-center gap-2" onClick={() => setShowRate(true)}>
          <Star className="h-4 w-4" /> Rate Supplier
        </button>
      </div>

      {/* Summary cards */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <div className="rounded-2xl border bg-card p-5">
          <p className="text-sm text-muted-foreground">Suppliers Rated</p>
          <p className="text-2xl font-bold mt-1">{ranking.length}</p>
        </div>
        <div className="rounded-2xl border bg-card p-5 flex items-start gap-3">
          <Trophy className="h-5 w-5 text-amber-500 mt-0.5" />
          <div>
            <p className="text-sm text-muted-foreground">Top Supplier</p>
            <p className="font-semibold mt-0.5">
              {topSupplier ? (topSupplier.supplier_name ?? topSupplier.supplier_id) : "—"}
            </p>
            {topSupplier && (
              <p className={`text-sm font-bold ${overallColor(topSupplier.overall_score)}`}>
                {topSupplier.overall_score.toFixed(0)} / 100
              </p>
            )}
          </div>
        </div>
        <div className="rounded-2xl border bg-card p-5 flex items-start gap-3">
          <AlertTriangle className={`h-5 w-5 mt-0.5 ${atRisk.length > 0 ? "text-red-500" : "text-muted-foreground"}`} />
          <div>
            <p className="text-sm text-muted-foreground">At Risk (&lt; 60)</p>
            <p className={`text-2xl font-bold mt-1 ${atRisk.length > 0 ? "text-red-600" : ""}`}>{atRisk.length}</p>
          </div>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex border-b gap-1">
        {(["ranking", "history"] as const).map(t => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={`px-4 py-2 text-sm font-medium border-b-2 -mb-px transition-colors capitalize ${
              tab === t ? "border-primary text-primary" : "border-transparent text-muted-foreground hover:text-foreground"
            }`}
          >
            {t === "ranking" ? "Supplier Ranking" : "Rating History"}
          </button>
        ))}
      </div>

      {loading ? (
        <div className="flex justify-center py-16">
          <RefreshCw className="h-6 w-6 animate-spin text-muted-foreground" />
        </div>
      ) : tab === "ranking" ? (
        /* Ranking tab */
        ranking.length === 0 ? (
          <div className="rounded-2xl border bg-card flex flex-col items-center justify-center py-20 text-center">
            <Star className="h-12 w-12 text-muted-foreground mb-4" />
            <p className="font-medium">No ratings yet</p>
            <p className="text-sm text-muted-foreground mt-1">
              Rate a supplier to start building your scorecard
            </p>
          </div>
        ) : (
          <div className="space-y-3">
            {ranking.map((r, idx) => (
              <div key={r.supplier_id} className="rounded-2xl border bg-card overflow-hidden">
                {/* Header row */}
                <div
                  className="flex items-center gap-4 p-4 cursor-pointer hover:bg-muted/40 transition-colors"
                  onClick={() => setExpanded(expanded === r.supplier_id ? null : r.supplier_id)}
                >
                  <span className={`text-sm font-bold w-6 text-center ${idx === 0 ? "text-amber-500" : "text-muted-foreground"}`}>
                    #{idx + 1}
                  </span>
                  <div className="flex-1 min-w-0">
                    <p className="font-medium truncate">
                      {r.supplier_name ?? r.supplier_id}
                    </p>
                    <p className="text-xs text-muted-foreground">{r.po_count} POs rated</p>
                  </div>
                  <StarRow value={(r.manual_avg / 20)} max={5} />
                  <span className={`text-lg font-bold ${overallColor(r.overall_score)} min-w-[3.5rem] text-right`}>
                    {r.overall_score.toFixed(0)}
                  </span>
                  {expanded === r.supplier_id ? (
                    <ChevronUp className="h-4 w-4 text-muted-foreground" />
                  ) : (
                    <ChevronDown className="h-4 w-4 text-muted-foreground" />
                  )}
                </div>

                {/* Expanded scorecard */}
                {expanded === r.supplier_id && (
                  <div className="border-t px-4 pb-4 pt-3 space-y-3">
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-x-8 gap-y-3">
                      <div className="space-y-1">
                        <div className="flex items-center gap-2 text-sm font-medium">
                          <Clock className="h-3.5 w-3.5 text-blue-500" /> On-Time Delivery
                        </div>
                        <ScoreBar value={r.on_time_rate} color="bg-blue-500" />
                      </div>
                      <div className="space-y-1">
                        <div className="flex items-center gap-2 text-sm font-medium">
                          <ShieldCheck className="h-3.5 w-3.5 text-green-500" /> Quality Score
                        </div>
                        <ScoreBar value={r.quality_score} color="bg-green-500" />
                      </div>
                      <div className="space-y-1">
                        <div className="flex items-center gap-2 text-sm font-medium">
                          <TrendingUp className="h-3.5 w-3.5 text-purple-500" /> Price Stability
                        </div>
                        <ScoreBar value={r.price_stability} color="bg-purple-500" />
                      </div>
                      <div className="space-y-1">
                        <div className="flex items-center gap-2 text-sm font-medium">
                          <Star className="h-3.5 w-3.5 text-amber-500" /> Manual Rating
                        </div>
                        <ScoreBar value={r.manual_avg} color="bg-amber-400" />
                      </div>
                    </div>
                    <div className="flex items-center justify-between pt-2 border-t">
                      <span className="text-sm text-muted-foreground">
                        Last updated {new Date(r.last_updated).toLocaleDateString("sv-SE")}
                      </span>
                      <span className={`text-lg font-bold ${overallColor(r.overall_score)}`}>
                        Overall: {r.overall_score.toFixed(1)} / 100
                      </span>
                    </div>
                  </div>
                )}
              </div>
            ))}
          </div>
        )
      ) : (
        /* History tab */
        <div className="rounded-2xl border bg-card overflow-hidden">
          {ratings.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-20 text-center">
              <Star className="h-12 w-12 text-muted-foreground mb-4" />
              <p className="font-medium">No rating history yet</p>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="bg-muted/50">
                  <tr>
                    <th className="text-left px-4 py-3 font-medium">Supplier</th>
                    <th className="text-left px-4 py-3 font-medium">Stars</th>
                    <th className="text-left px-4 py-3 font-medium">On Time</th>
                    <th className="text-left px-4 py-3 font-medium">Quality</th>
                    <th className="text-left px-4 py-3 font-medium">Comment</th>
                    <th className="text-left px-4 py-3 font-medium">Date</th>
                  </tr>
                </thead>
                <tbody>
                  {ratings.map(r => (
                    <tr key={r.id} className="border-t hover:bg-muted/30">
                      <td className="px-4 py-3 font-medium">{r.supplier_id ?? "—"}</td>
                      <td className="px-4 py-3">
                        <StarRow value={r.stars} />
                      </td>
                      <td className="px-4 py-3">
                        <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${r.delivery_ok ? "bg-green-100 text-green-700" : "bg-red-100 text-red-700"}`}>
                          {r.delivery_ok ? "Yes" : "No"}
                        </span>
                      </td>
                      <td className="px-4 py-3">
                        <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${r.quality_ok ? "bg-green-100 text-green-700" : "bg-red-100 text-red-700"}`}>
                          {r.quality_ok ? "Yes" : "No"}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-muted-foreground max-w-xs truncate">{r.comment ?? "—"}</td>
                      <td className="px-4 py-3 text-muted-foreground">
                        {new Date(r.created_at).toLocaleDateString("sv-SE")}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {/* Rate supplier modal */}
      {showRate && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
          <div className="bg-background rounded-2xl shadow-xl w-full max-w-md p-6 space-y-4">
            <h2 className="text-lg font-semibold">Rate Supplier</h2>
            <form onSubmit={handleRate} className="space-y-4">
              <div>
                <label className="text-sm font-medium">Supplier ID</label>
                <input
                  required
                  className="input mt-1 w-full"
                  placeholder="Supplier ID"
                  value={form.supplier_id}
                  onChange={e => setForm(f => ({ ...f, supplier_id: e.target.value }))}
                />
              </div>
              <div>
                <label className="text-sm font-medium">Purchase Order ID (optional)</label>
                <input
                  className="input mt-1 w-full"
                  placeholder="Leave blank for general rating"
                  value={form.purchase_order_id}
                  onChange={e => setForm(f => ({ ...f, purchase_order_id: e.target.value }))}
                />
              </div>
              <div>
                <label className="text-sm font-medium">Stars (1–5)</label>
                <div className="flex gap-2 mt-2">
                  {[1, 2, 3, 4, 5].map(s => (
                    <button
                      key={s}
                      type="button"
                      onClick={() => setForm(f => ({ ...f, stars: s }))}
                      className="focus:outline-none"
                    >
                      <Star
                        className={`h-7 w-7 transition-colors ${s <= form.stars ? "fill-amber-400 text-amber-400" : "text-gray-300 hover:text-amber-300"}`}
                      />
                    </button>
                  ))}
                </div>
              </div>
              <div className="flex gap-6">
                <label className="flex items-center gap-2 text-sm cursor-pointer">
                  <input
                    type="checkbox"
                    checked={form.delivery_ok}
                    onChange={e => setForm(f => ({ ...f, delivery_ok: e.target.checked }))}
                  />
                  Delivered on time
                </label>
                <label className="flex items-center gap-2 text-sm cursor-pointer">
                  <input
                    type="checkbox"
                    checked={form.quality_ok}
                    onChange={e => setForm(f => ({ ...f, quality_ok: e.target.checked }))}
                  />
                  Quality acceptable
                </label>
              </div>
              <div>
                <label className="text-sm font-medium">Comment (optional)</label>
                <textarea
                  className="input mt-1 w-full resize-none"
                  rows={3}
                  placeholder="Notes about this delivery or supplier"
                  value={form.comment}
                  onChange={e => setForm(f => ({ ...f, comment: e.target.value }))}
                />
              </div>
              <div className="flex gap-3 pt-2">
                <button type="button" className="btn-secondary flex-1" onClick={() => setShowRate(false)}>Cancel</button>
                <button type="submit" className="btn-primary flex-1">Submit Rating</button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
