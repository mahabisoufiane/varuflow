"use client";

import { api } from "@/lib/api-client";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { useEffect, useState } from "react";
import { Star, Download, AlertTriangle, Eye, EyeOff } from "lucide-react";
import { useTranslations } from "next-intl";

interface Review {
  id: string;
  rating: number;
  comment: string | null;
  is_public: boolean;
  source_type: string;
  source_id: string;
  customer_id: string | null;
  created_at: string;
  low: boolean;
  reasons: string[];
}

interface Summary {
  total: number;
  average: number;
  low_count: number;
  histogram: Record<string, number>;
}

function Stars({ rating }: { rating: number }) {
  return (
    <div className="flex gap-0.5">
      {[1, 2, 3, 4, 5].map((n) => (
        <Star
          key={n}
          className={`h-4 w-4 ${
            n <= rating ? "fill-amber-400 text-amber-400" : "text-muted-foreground/30"
          }`}
        />
      ))}
    </div>
  );
}

export default function ReviewsPage() {
  const t = useTranslations("reviews");
  const [reviews, setReviews] = useState<Review[]>([]);
  const [summary, setSummary] = useState<Summary | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [lowOnly, setLowOnly] = useState(false);

  async function load() {
    setLoading(true);
    setError(null);
    try {
      const [rs, sm] = await Promise.all([
        api.get<Review[]>(`/api/reviews${lowOnly ? "?low_only=true" : ""}`),
        api.get<Summary>("/api/reviews/summary"),
      ]);
      setReviews(rs);
      setSummary(sm);
    } catch (e: any) {
      setError(e.message || String(e));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [lowOnly]);

  async function togglePublic(r: Review) {
    try {
      const updated = await api.post<Review>(`/api/reviews/${r.id}/public`, {
        is_public: !r.is_public,
      });
      setReviews((prev) => prev.map((x) => (x.id === r.id ? updated : x)));
    } catch (e: any) {
      setError(e.message || String(e));
    }
  }

  async function exportCsv() {
    await api.downloadBlob("/api/reviews/export.csv", "reviews.csv");
  }

  const histBars = summary
    ? [5, 4, 3, 2, 1].map((n) => ({
        n,
        count: summary.histogram[String(n)] ?? 0,
        pct: summary.total ? ((summary.histogram[String(n)] ?? 0) / summary.total) * 100 : 0,
      }))
    : [];

  return (
    <div className="space-y-6">
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-2xl font-semibold">{t("title")}</h1>
          <p className="text-sm text-muted-foreground">{t("subtitle")}</p>
        </div>
        <Button onClick={exportCsv} variant="outline" className="gap-2">
          <Download className="h-4 w-4" /> {t("export_csv")}
        </Button>
      </div>

      {summary && (
        <div className="grid gap-4 md:grid-cols-3">
          <div className="rounded-lg border bg-card p-4">
            <div className="text-sm text-muted-foreground">{t("average")}</div>
            <div className="mt-1 flex items-end gap-2">
              <div className="text-3xl font-semibold">{summary.average.toFixed(1)}</div>
              <Stars rating={Math.round(summary.average)} />
            </div>
            <div className="mt-1 text-xs text-muted-foreground">
              {t("total", { count: summary.total })}
            </div>
          </div>
          <div className="rounded-lg border bg-card p-4 md:col-span-2">
            <div className="text-sm text-muted-foreground">{t("histogram")}</div>
            <div className="mt-2 space-y-1">
              {histBars.map((b) => (
                <div key={b.n} className="flex items-center gap-2 text-xs">
                  <span className="w-3 font-mono">{b.n}</span>
                  <div className="h-2 flex-1 overflow-hidden rounded bg-muted">
                    <div
                      className="h-full bg-amber-400 transition-all"
                      style={{ width: `${b.pct}%` }}
                    />
                  </div>
                  <span className="w-8 text-right font-mono text-muted-foreground">
                    {b.count}
                  </span>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      <div className="flex items-center gap-2">
        <Button
          variant={lowOnly ? "default" : "outline"}
          size="sm"
          onClick={() => setLowOnly((v) => !v)}
          className="gap-2"
        >
          <AlertTriangle className="h-4 w-4" />
          {lowOnly ? t("showing_low") : t("show_low_only")}
          {summary && summary.low_count > 0 && (
            <Badge variant="destructive">{summary.low_count}</Badge>
          )}
        </Button>
      </div>

      {error && (
        <div className="rounded-md border border-destructive/50 bg-destructive/10 p-3 text-sm text-destructive">
          {error}
        </div>
      )}

      <div className="space-y-3">
        {reviews.length === 0 && !loading && (
          <div className="rounded-lg border bg-card p-8 text-center text-muted-foreground">
            {t("empty")}
          </div>
        )}
        {reviews.map((r) => (
          <div
            key={r.id}
            className={
              r.low
                ? "rounded-lg border border-red-200 bg-red-50/60 p-4 dark:bg-red-950/20"
                : "rounded-lg border bg-card p-4"
            }
          >
            <div className="flex items-start justify-between gap-3">
              <div className="flex-1">
                <div className="flex items-center gap-2">
                  <Stars rating={r.rating} />
                  {r.low && (
                    <Badge variant="destructive" className="gap-1">
                      <AlertTriangle className="h-3 w-3" />
                      {t("low_flag")}
                    </Badge>
                  )}
                  <span className="text-xs text-muted-foreground">
                    {new Date(r.created_at).toLocaleDateString()}
                  </span>
                </div>
                {r.comment && (
                  <p className="mt-2 text-sm">{r.comment}</p>
                )}
                <div className="mt-2 text-xs text-muted-foreground">
                  {t("source_type_" + r.source_type)} · {r.source_id.slice(0, 8)}
                </div>
              </div>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => togglePublic(r)}
                className="gap-1"
                title={r.is_public ? t("hide_public") : t("show_public")}
              >
                {r.is_public ? (
                  <>
                    <Eye className="h-4 w-4" /> {t("public")}
                  </>
                ) : (
                  <>
                    <EyeOff className="h-4 w-4" /> {t("private")}
                  </>
                )}
              </Button>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
